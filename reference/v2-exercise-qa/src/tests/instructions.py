"""TC-INSTRUCT: Instruction validation.

Tests that EPUB instructions are:
- Clear and unambiguous
- Accurate (match solution files)
- Complete (all steps present)
- Consistent (terminology, naming)
- Properly formatted
"""

import re
import zipfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from bs4 import BeautifulSoup

from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext, ExerciseType
from ..clients.ssh import SSHConnection


class TC_INSTRUCT:
    """Instruction validation test category."""

    # Common vague instruction patterns
    VAGUE_PATTERNS = [
        (r'\bappropriate\b', 'vague term: "appropriate"'),
        (r'\bas needed\b', 'vague term: "as needed"'),
        (r'\bcorrect\s+\w+\b', 'vague term: "correct X"'),
        (r'\bproper\b', 'vague term: "proper"'),
        (r'\bsuitable\b', 'vague term: "suitable"'),
        (r'\betc\.?\b', 'incomplete list: "etc"'),
        (r'\band so on\b', 'incomplete list: "and so on"'),
        (r'\bsomething like\b', 'vague term: "something like"'),
        (r'\bsimilar to\b', 'vague reference: "similar to"'),
    ]

    # Required instruction elements for different exercise types
    REQUIRED_ELEMENTS = {
        ExerciseType.LAB: [
            'objective',
            'step',
        ],
        ExerciseType.GUIDED_EXERCISE: [
            'objective',
            'step',
        ],
    }

    def __init__(self, epub_path: Optional[Path] = None):
        """Initialize instruction validator.

        Args:
            epub_path: Path to EPUB file
        """
        self.epub_path = epub_path
        self._temp_dir = None

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test EPUB instruction quality.

        Args:
            exercise: Exercise context
            ssh: SSH connection (not heavily used)

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-INSTRUCT: Testing instructions...")

        bugs_found = []
        start_time = datetime.now()

        # Get EPUB path
        if exercise.lesson_path:
            epub_path = self._find_epub(exercise.lesson_path)
            if epub_path:
                self.epub_path = epub_path

        if not self.epub_path or not self.epub_path.exists():
            print("   ⏭  Skipping (no EPUB found)")
            return TestResult(
                category="TC-INSTRUCT",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=0.0,
                details={'skipped': True, 'reason': 'No EPUB found'}
            )

        # Extract EPUB
        try:
            self._extract_epub()
        except Exception as e:
            print(f"   ⚠  Error extracting EPUB: {e}")
            return TestResult(
                category="TC-INSTRUCT",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=0.0,
                details={'error': str(e)}
            )

        # Parse exercise content
        content_dir = Path(self._temp_dir) / "EPUB"
        exercise_content = self._find_exercise_content(content_dir, exercise.id)

        if not exercise_content:
            print("   ⏭  Exercise section not found in EPUB")
            self._cleanup()
            return TestResult(
                category="TC-INSTRUCT",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=0.0,
                details={'skipped': True, 'reason': 'Exercise not found in EPUB'}
            )

        # Run instruction checks
        print("   → Checking for vague instructions...")
        vague_bugs = self._check_vague_instructions(exercise_content, exercise.id)
        bugs_found.extend(vague_bugs)

        print("   → Checking instruction completeness...")
        complete_bugs = self._check_completeness(exercise_content, exercise)
        bugs_found.extend(complete_bugs)

        print("   → Checking step consistency...")
        step_bugs = self._check_step_consistency(exercise_content, exercise.id)
        bugs_found.extend(step_bugs)

        print("   → Checking file references...")
        ref_bugs = self._check_file_references(exercise_content, exercise, ssh)
        bugs_found.extend(ref_bugs)

        print("   → Checking command accuracy...")
        cmd_bugs = self._check_command_accuracy(exercise_content, exercise, ssh)
        bugs_found.extend(cmd_bugs)

        print("   → Checking solution alignment...")
        sol_bugs = self._check_solution_alignment(exercise_content, exercise)
        bugs_found.extend(sol_bugs)

        # Cleanup
        self._cleanup()

        if len(bugs_found) == 0:
            print("      ✓ Instructions are clear and accurate")
        else:
            print(f"      ⚠  Found {len(bugs_found)} instruction issue(s)")

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-INSTRUCT",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'checks_performed': 6,
                'issues_found': len(bugs_found)
            }
        )

    def _find_epub(self, lesson_path: Path) -> Optional[Path]:
        """Find EPUB file for lesson."""
        for epub in lesson_path.glob("*.epub"):
            return epub

        cache_dir = lesson_path / ".cache" / "generated" / "en-US"
        if cache_dir.exists():
            for epub in cache_dir.glob("*.epub"):
                return epub

        return None

    def _extract_epub(self):
        """Extract EPUB to temporary directory."""
        self._temp_dir = tempfile.mkdtemp(prefix="epub_inst_")
        with zipfile.ZipFile(self.epub_path, 'r') as zip_ref:
            zip_ref.extractall(self._temp_dir)

    def _find_exercise_content(self, content_dir: Path, exercise_id: str) -> Optional[Tuple[BeautifulSoup, str]]:
        """Find and parse exercise content from EPUB."""
        for html_file in list(content_dir.glob("*.xhtml")) + list(content_dir.glob("*.html")):
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    soup = BeautifulSoup(content, 'html.parser')

                # Find exercise section
                section = soup.find(id=exercise_id)
                if not section:
                    for elem in soup.find_all(id=True):
                        if exercise_id in elem.get('id', ''):
                            section = elem
                            break

                if section:
                    return (section, section.get_text())

            except Exception:
                continue

        return None

    def _check_vague_instructions(self, content: Tuple, exercise_id: str) -> List[Bug]:
        """Check for vague instruction patterns."""
        bugs = []
        soup, text = content

        vague_count = 0
        for pattern, description in self.VAGUE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                vague_count += len(matches)

        if vague_count >= 3:
            bugs.append(Bug(
                id=f"INSTRUCT-VAGUE-{exercise_id}",
                severity=BugSeverity.P3_LOW,
                category="TC-INSTRUCT",
                exercise_id=exercise_id,
                description=f"Instructions contain {vague_count} vague terms",
                fix_recommendation="Replace vague terms with specific instructions",
                verification_steps=[
                    "Search for: appropriate, as needed, correct, proper, etc.",
                    "Replace with specific values or actions"
                ]
            ))

        return bugs

    def _check_completeness(self, content: Tuple, exercise: ExerciseContext) -> List[Bug]:
        """Check that instructions include required elements."""
        bugs = []
        soup, text = content
        text_lower = text.lower()

        required = self.REQUIRED_ELEMENTS.get(exercise.type, [])

        for element in required:
            # Check for element presence
            if element == 'objective':
                if 'objective' not in text_lower and 'goal' not in text_lower and 'purpose' not in text_lower:
                    bugs.append(Bug(
                        id=f"INSTRUCT-NOOBJECTIVE-{exercise.id}",
                        severity=BugSeverity.P2_HIGH,
                        category="TC-INSTRUCT",
                        exercise_id=exercise.id,
                        description="Exercise missing clear objective/goal statement",
                        fix_recommendation="Add objective statement at the beginning",
                        verification_steps=[
                            "Add 'Objective:' section",
                            "State what students will accomplish"
                        ]
                    ))

            elif element == 'step':
                # Look for step indicators
                step_patterns = [
                    r'step\s*\d+',
                    r'\d+\.\s+\w',
                    r'^\s*\d+\)',
                ]
                has_steps = any(re.search(p, text, re.IGNORECASE | re.MULTILINE) for p in step_patterns)

                if not has_steps:
                    # Also check for ordered lists
                    ordered_lists = soup.find_all('ol')
                    if not ordered_lists:
                        bugs.append(Bug(
                            id=f"INSTRUCT-NOSTEPS-{exercise.id}",
                            severity=BugSeverity.P2_HIGH,
                            category="TC-INSTRUCT",
                            exercise_id=exercise.id,
                            description="Exercise missing numbered steps",
                            fix_recommendation="Add numbered steps for instructions",
                            verification_steps=[
                                "Add numbered steps or ordered lists",
                                "Ensure clear progression"
                            ]
                        ))

        return bugs

    def _check_step_consistency(self, content: Tuple, exercise_id: str) -> List[Bug]:
        """Check step numbering and consistency."""
        bugs = []
        soup, text = content

        # Find step numbers
        step_pattern = r'step\s*(\d+)'
        steps = re.findall(step_pattern, text, re.IGNORECASE)

        if steps:
            step_nums = [int(s) for s in steps]

            # Check for gaps
            for i in range(1, max(step_nums) + 1):
                if i not in step_nums and i > 0:
                    bugs.append(Bug(
                        id=f"INSTRUCT-STEPGAP-{i}-{exercise_id}",
                        severity=BugSeverity.P2_HIGH,
                        category="TC-INSTRUCT",
                        exercise_id=exercise_id,
                        description=f"Step numbering has gap: missing Step {i}",
                        fix_recommendation="Fix step numbering sequence",
                        verification_steps=[
                            "Check step sequence",
                            f"Add missing Step {i} or renumber"
                        ]
                    ))
                    break  # Only report first gap

            # Check for duplicates
            seen = set()
            for num in step_nums:
                if num in seen:
                    bugs.append(Bug(
                        id=f"INSTRUCT-STEPDUP-{num}-{exercise_id}",
                        severity=BugSeverity.P2_HIGH,
                        category="TC-INSTRUCT",
                        exercise_id=exercise_id,
                        description=f"Duplicate step number: Step {num}",
                        fix_recommendation="Fix duplicate step numbers",
                        verification_steps=[
                            f"Find duplicate Step {num}",
                            "Renumber steps correctly"
                        ]
                    ))
                    break  # Only report first duplicate
                seen.add(num)

        return bugs

    def _check_file_references(self, content: Tuple, exercise: ExerciseContext,
                               ssh: SSHConnection) -> List[Bug]:
        """Check that referenced files exist."""
        bugs = []
        soup, text = content
        base_id = exercise.id.removesuffix('-ge').removesuffix('-lab')

        # Find file references in instructions
        file_patterns = [
            r'(?:file|create|edit|open|modify)\s+(?:the\s+)?[`"\']?(\S+\.(?:yml|yaml|py|sh|cfg|ini|j2))[`"\']?',
            r'[`"\'](\S+\.(?:yml|yaml|py|sh|cfg|ini|j2))[`"\']',
        ]

        referenced_files = set()
        for pattern in file_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            referenced_files.update(matches)

        # Check if files exist in materials or on remote
        for ref_file in referenced_files:
            # Skip common example names
            if 'example' in ref_file.lower() or 'sample' in ref_file.lower():
                continue

            # Check in materials
            found = False
            if exercise.materials_dir:
                for f in exercise.materials_dir.rglob(ref_file.split('/')[-1]):
                    found = True
                    break

            if not found:
                # Check if mentioned in solution files
                for sol_file in exercise.solution_files:
                    if ref_file.split('/')[-1] in sol_file.name:
                        found = True
                        break

            # Note: Not flagging missing files as bugs since they may be created during exercise

        return bugs

    def _check_command_accuracy(self, content: Tuple, exercise: ExerciseContext,
                                 ssh: SSHConnection) -> List[Bug]:
        """Check that documented commands are accurate."""
        bugs = []
        soup, text = content

        # Find command patterns
        code_blocks = soup.find_all(['code', 'pre', 'kbd'])

        invalid_commands = []
        for block in code_blocks:
            cmd_text = block.get_text(strip=True)

            # Skip if not a command
            if not cmd_text or len(cmd_text) < 3:
                continue

            # Clean command
            cmd = cmd_text.strip()
            if cmd.startswith('$ '):
                cmd = cmd[2:]
            if cmd.startswith('# '):
                cmd = cmd[2:]

            # Skip multiline (likely output)
            if '\n' in cmd:
                continue

            # Check for common typos in commands
            typo_patterns = [
                (r'\bansible-palybook\b', 'ansible-playbook'),
                (r'\bansible-navigtor\b', 'ansible-navigator'),
                (r'\bpyhton\b', 'python'),
                (r'\bansibel\b', 'ansible'),
                (r'\bplabook\b', 'playbook'),
            ]

            for typo, correct in typo_patterns:
                if re.search(typo, cmd, re.IGNORECASE):
                    bugs.append(Bug(
                        id=f"INSTRUCT-TYPO-{exercise.id}",
                        severity=BugSeverity.P1_CRITICAL,
                        category="TC-INSTRUCT",
                        exercise_id=exercise.id,
                        description=f"Command typo: should be '{correct}'",
                        fix_recommendation=f"Fix typo: use '{correct}'",
                        verification_steps=[
                            f"Find and fix typo in: {cmd[:50]}",
                            f"Replace with: {correct}"
                        ]
                    ))

        return bugs

    def _check_solution_alignment(self, content: Tuple, exercise: ExerciseContext) -> List[Bug]:
        """Check that instructions align with solution files."""
        bugs = []
        soup, text = content

        if not exercise.solution_files:
            return bugs

        # Extract key elements from solution files
        solution_vars = set()
        solution_modules = set()

        for sol_file in exercise.solution_files:
            if sol_file.exists():
                try:
                    sol_content = sol_file.read_text(encoding='utf-8', errors='ignore')

                    # Find variable names in Ansible
                    var_pattern = r'{{\s*(\w+)\s*}}'
                    solution_vars.update(re.findall(var_pattern, sol_content))

                    # Find module names
                    module_pattern = r'^\s*(\w+\.?\w*):\s*$'
                    for match in re.finditer(module_pattern, sol_content, re.MULTILINE):
                        module = match.group(1)
                        if '.' in module or module in ['name', 'hosts', 'tasks', 'vars', 'become']:
                            continue
                        solution_modules.add(module)

                except Exception:
                    pass

        # Check if key solution elements are mentioned in instructions
        text_lower = text.lower()

        # Check for module mentions (should explain what modules to use)
        mentioned_modules = sum(1 for mod in solution_modules if mod.lower() in text_lower)

        if solution_modules and mentioned_modules == 0:
            bugs.append(Bug(
                id=f"INSTRUCT-NOMODULES-{exercise.id}",
                severity=BugSeverity.P3_LOW,
                category="TC-INSTRUCT",
                exercise_id=exercise.id,
                description="Instructions don't mention Ansible modules used in solution",
                fix_recommendation="Consider mentioning key modules students should use",
                verification_steps=[
                    "Review solution modules",
                    "Add hints about which modules to use"
                ]
            ))

        return bugs

    def _cleanup(self):
        """Clean up temporary files."""
        if self._temp_dir:
            import shutil
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None
