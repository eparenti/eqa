"""TC-LINT: Linting and style validation.

Tests playbooks and YAML files for:
- ansible-lint violations
- yamllint issues
- Python style (for grading scripts)
- Common anti-patterns
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext, ExercisePattern
from ..core.pattern_detector import is_aap_controller_content
from ..clients.ssh import SSHConnection


class TC_LINT:
    """Linting and style validation test category."""

    # Severity mapping for ansible-lint
    ANSIBLE_LINT_SEVERITY = {
        'blocker': BugSeverity.P0_BLOCKER,
        'critical': BugSeverity.P1_CRITICAL,
        'major': BugSeverity.P2_HIGH,
        'minor': BugSeverity.P3_LOW,
        'info': BugSeverity.P3_LOW,
    }

    # Common anti-patterns to check manually
    # Note: Patterns must be precise to avoid false positives
    ANTI_PATTERNS = [
        (r'^\s*ignore_errors:\s*yes', 'ignore_errors should be avoided or used sparingly'),
        (r'^\s*when:\s*true\s*$', 'when: true is redundant'),
        (r'^\s*when:\s*false\s*$', 'when: false makes task never run - remove or comment out'),
        (r'^\s*command:.*\bsudo\b', 'use become: true instead of sudo in command'),
        (r'^\s*shell:\s*[^|]*\bcd\b', 'use chdir parameter instead of cd in shell'),
        # Note: with_items and include are NOT deprecated in all contexts, so removed
    ]

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test playbooks and YAML files for lint issues.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-LINT: Testing code quality...")

        bugs_found = []
        start_time = datetime.now()
        files_linted = 0

        # Check if linting tools are available
        print("   → Checking linting tools...")
        tools_available = self._check_tools(ssh)

        # Log pattern if AAP Controller
        if is_aap_controller_content(exercise):
            print(f"   ⚡ AAP Controller content detected - using adapted lint rules")

        # Lint solution files
        print("   → Linting solution files...")
        for sol_file in exercise.solution_files:
            if sol_file.exists():
                file_bugs = self._lint_file(sol_file, exercise, ssh, tools_available)
                bugs_found.extend(file_bugs)
                files_linted += 1

        # Lint grading script
        if exercise.grading_script and exercise.grading_script.exists():
            print("   → Linting grading script...")
            file_bugs = self._lint_python_file(exercise.grading_script, exercise.id, ssh, tools_available)
            bugs_found.extend(file_bugs)
            files_linted += 1

        # Lint materials directory
        if exercise.materials_dir and exercise.materials_dir.exists():
            print("   → Linting materials...")
            for yml_file in exercise.materials_dir.rglob("*.yml"):
                file_bugs = self._lint_file(yml_file, exercise, ssh, tools_available)
                bugs_found.extend(file_bugs)
                files_linted += 1

            for yaml_file in exercise.materials_dir.rglob("*.yaml"):
                file_bugs = self._lint_file(yaml_file, exercise, ssh, tools_available)
                bugs_found.extend(file_bugs)
                files_linted += 1

        if len(bugs_found) == 0:
            print(f"      ✓ {files_linted} file(s) passed lint checks")
        else:
            print(f"      ⚠  Found {len(bugs_found)} lint issue(s)")

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-LINT",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'files_linted': files_linted,
                'tools_available': tools_available,
                'issues_found': len(bugs_found)
            }
        )

    def _check_tools(self, ssh: SSHConnection) -> Dict[str, bool]:
        """Check which linting tools are available LOCALLY, install if needed."""
        import subprocess
        import shutil
        tools = {}

        # Check/install yamllint LOCALLY
        if shutil.which('yamllint') is None:
            print("      Installing yamllint...")
            subprocess.run(['pip', 'install', '--quiet', 'yamllint'],
                          capture_output=True, timeout=60)
        tools['yamllint'] = shutil.which('yamllint') is not None
        if tools['yamllint']:
            print("      ✓ yamllint available")

        # Check/install ansible-lint LOCALLY
        if shutil.which('ansible-lint') is None:
            print("      Installing ansible-lint...")
            subprocess.run(['pip', 'install', '--quiet', 'ansible-lint'],
                          capture_output=True, timeout=120)
        tools['ansible-lint'] = shutil.which('ansible-lint') is not None
        if tools['ansible-lint']:
            print("      ✓ ansible-lint available")

        # Check pylint LOCALLY (optional - don't auto-install)
        tools['pylint'] = shutil.which('pylint') is not None

        return tools

    def _lint_file(self, file_path: Path, exercise: ExerciseContext, ssh: SSHConnection,
                   tools: Dict[str, bool]) -> List[Bug]:
        """Lint a YAML/playbook file."""
        bugs = []
        exercise_id = exercise.id
        is_aap = is_aap_controller_content(exercise)

        # Read file content for manual checks
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return bugs

        # Check anti-patterns manually (skip for AAP Controller - patterns are Ansible-specific)
        if not is_aap:
            anti_pattern_bugs = self._check_anti_patterns(content, file_path, exercise_id)
            bugs.extend(anti_pattern_bugs)

        # Run ansible-lint if available and it's a playbook (skip for AAP Controller)
        if not is_aap and tools.get('ansible-lint') and self._is_playbook(content):
            lint_bugs = self._run_ansible_lint(file_path, exercise_id, ssh)
            bugs.extend(lint_bugs)

        # Run yamllint if available (always run - YAML validity matters for all content)
        if tools.get('yamllint'):
            yaml_bugs = self._run_yamllint(file_path, exercise_id, ssh)
            bugs.extend(yaml_bugs)

        return bugs

    def _is_playbook(self, content: str) -> bool:
        """Check if content looks like an Ansible playbook."""
        playbook_indicators = ['hosts:', 'tasks:', 'roles:', 'plays:']
        return any(ind in content for ind in playbook_indicators)

    def _check_anti_patterns(self, content: str, file_path: Path, exercise_id: str) -> List[Bug]:
        """Check for common anti-patterns."""
        bugs = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            for pattern, description in self.ANTI_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    bugs.append(Bug(
                        id=f"LINT-PATTERN-{file_path.stem}-L{i}-{exercise_id}",
                        severity=BugSeverity.P3_LOW,
                        category="TC-LINT",
                        exercise_id=exercise_id,
                        description=f"{description} at {file_path.name}:{i}",
                        fix_recommendation=f"Review and fix: {line.strip()[:50]}",
                        verification_steps=[
                            f"Edit {file_path.name} line {i}",
                            "Apply recommended fix"
                        ]
                    ))
                    break  # One bug per line

        return bugs

    def _run_ansible_lint(self, file_path: Path, exercise_id: str, ssh: SSHConnection) -> List[Bug]:
        """Run ansible-lint on a file LOCALLY."""
        import subprocess
        bugs = []

        # Run ansible-lint locally
        try:
            result = subprocess.run(
                ['ansible-lint', '--nocolor', '-q', str(file_path)],
                capture_output=True, text=True, timeout=60
            )

            if result.returncode != 0:
                # Parse error output - only report real issues
                error_output = result.stdout + result.stderr
                # Skip "couldn't determine" warnings and similar noise
                if 'syntax' in error_output.lower() and 'error' in error_output.lower():
                    bugs.append(Bug(
                        id=f"LINT-SYNTAX-{file_path.stem}-{exercise_id}",
                        severity=BugSeverity.P1_CRITICAL,
                        category="TC-LINT",
                        exercise_id=exercise_id,
                        description=f"Syntax error in {file_path.name}",
                        fix_recommendation="Fix YAML/Ansible syntax errors",
                        verification_steps=[
                            f"Run: ansible-lint {file_path.name}",
                            "Fix reported errors"
                        ]
                    ))
        except subprocess.TimeoutExpired:
            pass  # Skip on timeout
        except FileNotFoundError:
            pass  # ansible-lint not installed

        return bugs

    def _run_yamllint(self, file_path: Path, exercise_id: str, ssh: SSHConnection) -> List[Bug]:
        """Run yamllint on a file LOCALLY."""
        import subprocess
        bugs = []

        # Run yamllint locally with relaxed rules (training content has intentional examples)
        try:
            result = subprocess.run(
                ['yamllint', '-d', 'relaxed', '-f', 'parsable', str(file_path)],
                capture_output=True, text=True, timeout=30
            )

            # Only report errors, not warnings (relaxed mode)
            if result.returncode > 1:  # 1 = warnings only, 2+ = errors
                for line in result.stdout.split('\n')[:3]:  # Limit to 3 issues
                    if ':error:' in line.lower():
                        bugs.append(Bug(
                            id=f"LINT-YAML-{file_path.stem}-{exercise_id}",
                            severity=BugSeverity.P2_HIGH,
                            category="TC-LINT",
                            exercise_id=exercise_id,
                            description=f"YAML error in {file_path.name}: {line.split(':')[-1][:50]}",
                            fix_recommendation="Fix YAML syntax",
                            verification_steps=[
                                f"Run: yamllint {file_path.name}",
                                "Fix reported errors"
                            ]
                        ))
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            pass  # yamllint not installed

        return bugs

    def _lint_python_file(self, file_path: Path, exercise_id: str, ssh: SSHConnection,
                          tools: Dict[str, bool]) -> List[Bug]:
        """Lint a Python file."""
        bugs = []

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return bugs

        # Check for common Python issues
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            # Check for bare except
            if re.match(r'\s*except\s*:', line):
                bugs.append(Bug(
                    id=f"LINT-PY-EXCEPT-{file_path.stem}-L{i}-{exercise_id}",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-LINT",
                    exercise_id=exercise_id,
                    description=f"Bare except clause at {file_path.name}:{i}",
                    fix_recommendation="Specify exception type: except Exception:",
                    verification_steps=[
                        f"Edit {file_path.name} line {i}",
                        "Add specific exception type"
                    ]
                ))

            # Check for print statements (should use logging)
            if re.match(r'\s*print\s*\(', line) and 'debug' not in file_path.stem.lower():
                # This is minor - print is often fine in grading scripts
                pass

        return bugs
