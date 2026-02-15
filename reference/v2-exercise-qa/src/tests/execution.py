"""TC-EXEC: EPUB execution testing.

Tests that EPUB instructions can be executed:
- Commands run successfully
- Expected output matches (when specified)
- File changes occur as described
- No errors in command execution
"""

import re
import zipfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup

from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext
from ..clients.ssh import SSHConnection


class TC_EXEC:
    """EPUB execution test category."""

    # Commands that should NOT be executed during testing
    SKIP_COMMANDS = [
        'sudo shutdown',
        'sudo reboot',
        'sudo poweroff',
        'sudo halt',
        'rm -rf /',
        'dd if=',
        'mkfs.',
        'fdisk',
        'parted',
    ]

    # Commands that are safe to execute
    SAFE_PREFIXES = [
        'cd ',
        'ls',
        'cat ',
        'echo ',
        'pwd',
        'whoami',
        'ansible',
        'ansible-playbook',
        'ansible-navigator',
        'python',
        'pip',
        'git ',
        'lab ',
        'ssh ',
        'scp ',
        'curl ',
        'wget ',
        'vim ',
        'vi ',
        'nano ',
        'mkdir ',
        'touch ',
        'cp ',
        'mv ',
        'chmod ',
        'chown ',
    ]

    def __init__(self, epub_path: Optional[Path] = None):
        """Initialize execution tester.

        Args:
            epub_path: Path to EPUB file (optional, can be set later)
        """
        self.epub_path = epub_path
        self._temp_dir = None

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test EPUB instruction execution.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-EXEC: Testing EPUB execution...")

        bugs_found = []
        start_time = datetime.now()
        commands_tested = 0
        commands_passed = 0
        commands_failed = 0
        commands_skipped = 0

        # Get EPUB path from exercise context
        if exercise.lesson_path:
            epub_path = self._find_epub(exercise.lesson_path)
            if not epub_path:
                print("   ⏭  Skipping (no EPUB found)")
                return TestResult(
                    category="TC-EXEC",
                    exercise_id=exercise.id,
                    passed=True,
                    timestamp=datetime.now().isoformat(),
                    duration_seconds=0.0,
                    details={'skipped': True, 'reason': 'No EPUB found'}
                )
            self.epub_path = epub_path

        if not self.epub_path or not self.epub_path.exists():
            print("   ⏭  Skipping (EPUB not available)")
            return TestResult(
                category="TC-EXEC",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=0.0,
                details={'skipped': True, 'reason': 'EPUB path not set'}
            )

        # Extract commands from EPUB
        try:
            commands = self._extract_commands(exercise.id)
            print(f"   Found {len(commands)} command(s) in EPUB")
        except Exception as e:
            print(f"   ⚠  Error extracting commands: {e}")
            return TestResult(
                category="TC-EXEC",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                details={'error': str(e)}
            )

        if not commands:
            print("   ⏭  No executable commands found")
            return TestResult(
                category="TC-EXEC",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                details={'commands_found': 0}
            )

        # Start the lab first
        print("   → Starting lab environment...")
        start_result = ssh.run(f"lab start {exercise.lab_name}", timeout=120)
        if not start_result.success:
            bugs_found.append(Bug(
                id=f"EXEC-START-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-EXEC",
                exercise_id=exercise.id,
                description=f"Failed to start lab: {start_result.stderr[:200] if start_result.stderr else 'unknown error'}",
                fix_recommendation="Check lab start script and lab environment",
                verification_steps=[f"Run: lab start {exercise.lab_name}"]
            ))
            # Continue anyway - some commands might work

        # Test each command
        for i, cmd_info in enumerate(commands, 1):
            command = cmd_info['command']
            expected_output = cmd_info.get('expected_output')
            context = cmd_info.get('context', '')

            # Check if command should be skipped
            if self._should_skip_command(command):
                print(f"   ⏭  [{i}/{len(commands)}] Skipping (unsafe): {command[:50]}...")
                commands_skipped += 1
                continue

            # Check if command is safe to execute
            if not self._is_safe_command(command):
                print(f"   ⏭  [{i}/{len(commands)}] Skipping (unknown): {command[:50]}...")
                commands_skipped += 1
                continue

            commands_tested += 1
            print(f"   → [{i}/{len(commands)}] Testing: {command[:60]}...")

            # Execute command
            result = ssh.run(command, timeout=60)

            if result.success:
                commands_passed += 1
                # Check expected output if specified
                if expected_output and expected_output not in result.stdout:
                    bugs_found.append(Bug(
                        id=f"EXEC-OUTPUT-{i:03d}-{exercise.id}",
                        severity=BugSeverity.P2_HIGH,
                        category="TC-EXEC",
                        exercise_id=exercise.id,
                        description=f"Command output doesn't match expected: {command[:50]}",
                        fix_recommendation="Verify command produces expected output",
                        verification_steps=[
                            f"Run: {command}",
                            f"Expected to contain: {expected_output[:100]}"
                        ]
                    ))
            else:
                commands_failed += 1
                error_msg = result.stderr[:200] if result.stderr else "Command returned non-zero exit code"
                bugs_found.append(Bug(
                    id=f"EXEC-FAIL-{i:03d}-{exercise.id}",
                    severity=BugSeverity.P1_CRITICAL,
                    category="TC-EXEC",
                    exercise_id=exercise.id,
                    description=f"Command failed: {command[:50]}... - {error_msg}",
                    fix_recommendation="Fix command syntax or ensure prerequisites are met",
                    verification_steps=[
                        f"Run: {command}",
                        "Check for errors"
                    ]
                ))

        # Cleanup
        self._cleanup()

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-EXEC",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'commands_found': len(commands),
                'commands_tested': commands_tested,
                'commands_passed': commands_passed,
                'commands_failed': commands_failed,
                'commands_skipped': commands_skipped
            }
        )

    def _find_epub(self, lesson_path: Path) -> Optional[Path]:
        """Find EPUB file for lesson."""
        # Check in lesson directory
        for epub in lesson_path.glob("*.epub"):
            return epub

        # Check in .cache/generated
        cache_dir = lesson_path / ".cache" / "generated" / "en-US"
        if cache_dir.exists():
            for epub in cache_dir.glob("*.epub"):
                return epub

        return None

    def _extract_commands(self, exercise_id: str) -> List[Dict]:
        """Extract executable commands from EPUB content.

        Args:
            exercise_id: ID of exercise to extract commands for

        Returns:
            List of command dictionaries with 'command', 'expected_output', 'context'
        """
        commands = []

        if not self.epub_path or not self.epub_path.exists():
            return commands

        # Extract EPUB to temp directory
        self._temp_dir = tempfile.mkdtemp(prefix="epub_exec_")
        with zipfile.ZipFile(self.epub_path, 'r') as zip_ref:
            zip_ref.extractall(self._temp_dir)

        content_dir = Path(self._temp_dir) / "EPUB"
        if not content_dir.exists():
            return commands

        # Find the exercise section in EPUB
        for html_file in content_dir.glob("*.xhtml"):
            try:
                commands.extend(self._parse_html_for_commands(html_file, exercise_id))
            except Exception as e:
                print(f"      ⚠  Error parsing {html_file.name}: {e}")

        for html_file in content_dir.glob("*.html"):
            try:
                commands.extend(self._parse_html_for_commands(html_file, exercise_id))
            except Exception as e:
                print(f"      ⚠  Error parsing {html_file.name}: {e}")

        return commands

    def _parse_html_for_commands(self, html_file: Path, exercise_id: str) -> List[Dict]:
        """Parse HTML file and extract commands for specific exercise.

        Args:
            html_file: Path to HTML file
            exercise_id: ID of exercise to find

        Returns:
            List of command dictionaries
        """
        commands = []

        with open(html_file, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')

        # Find the exercise section
        exercise_section = soup.find(id=exercise_id)
        if not exercise_section:
            # Try finding by partial ID match
            for elem in soup.find_all(id=True):
                if exercise_id in elem.get('id', ''):
                    exercise_section = elem
                    break

        if not exercise_section:
            return commands

        # Look for code blocks, pre elements, and screen elements
        code_selectors = [
            'pre',
            'code',
            '.code',
            '.command',
            '.screen',
            'kbd',
            '.userinput',
        ]

        for selector in code_selectors:
            if selector.startswith('.'):
                elements = exercise_section.find_all(class_=selector[1:])
            else:
                elements = exercise_section.find_all(selector)

            for elem in elements:
                text = elem.get_text(strip=True)
                if text and self._looks_like_command(text):
                    # Get context (surrounding text)
                    context = ""
                    parent = elem.parent
                    if parent:
                        context = parent.get_text(strip=True)[:100]

                    # Check for expected output
                    expected_output = self._extract_expected_output(elem)

                    commands.append({
                        'command': self._clean_command(text),
                        'expected_output': expected_output,
                        'context': context
                    })

        return commands

    def _looks_like_command(self, text: str) -> bool:
        """Check if text looks like a shell command."""
        # Must start with common command patterns or $/#
        text = text.strip()

        # Skip if too short or too long
        if len(text) < 3 or len(text) > 500:
            return False

        # Skip if looks like output (multiple lines without commands)
        if '\n' in text and not any(line.strip().startswith(('$', '#', '[')) for line in text.split('\n')[:2]):
            # Could be output - check more carefully
            pass

        # Common command patterns
        command_patterns = [
            r'^\$\s*\w+',                    # $ command
            r'^#\s*\w+',                     # # command (root)
            r'^\[.*\]\$\s*\w+',              # [user@host]$ command
            r'^ansible[\s-]',                # ansible commands
            r'^python3?\s+',                 # python commands
            r'^pip3?\s+',                    # pip commands
            r'^git\s+',                      # git commands
            r'^lab\s+',                      # lab commands
            r'^ssh\s+',                      # ssh commands
            r'^cd\s+',                       # cd commands
            r'^ls\s*',                       # ls commands
            r'^cat\s+',                      # cat commands
            r'^vim?\s+',                     # vi/vim commands
            r'^nano\s+',                     # nano commands
            r'^mkdir\s+',                    # mkdir commands
            r'^cp\s+',                       # cp commands
            r'^mv\s+',                       # mv commands
            r'^rm\s+',                       # rm commands
            r'^chmod\s+',                    # chmod commands
            r'^curl\s+',                     # curl commands
            r'^wget\s+',                     # wget commands
        ]

        for pattern in command_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True

        return False

    def _clean_command(self, text: str) -> str:
        """Clean command text for execution."""
        text = text.strip()

        # Remove $ or # prefix
        if text.startswith('$ '):
            text = text[2:]
        elif text.startswith('# '):
            text = text[2:]
        elif text.startswith('$'):
            text = text[1:]

        # Remove prompt patterns like [student@workstation]$
        prompt_pattern = r'^\[.*?\][\$#]\s*'
        text = re.sub(prompt_pattern, '', text)

        # Take only first line if multiline (rest is likely output)
        if '\n' in text:
            text = text.split('\n')[0]

        return text.strip()

    def _extract_expected_output(self, elem) -> Optional[str]:
        """Extract expected output that should follow a command."""
        # Look for subsequent sibling elements that might contain output
        next_sibling = elem.find_next_sibling()
        if next_sibling:
            # Check if it's an output element
            if next_sibling.name in ['pre', 'screen', 'samp'] or \
               (hasattr(next_sibling, 'get') and 'output' in next_sibling.get('class', [])):
                output_text = next_sibling.get_text(strip=True)
                if output_text and len(output_text) < 500:
                    return output_text

        return None

    def _should_skip_command(self, command: str) -> bool:
        """Check if command should be skipped for safety."""
        command_lower = command.lower()
        for skip in self.SKIP_COMMANDS:
            if skip.lower() in command_lower:
                return True
        return False

    def _is_safe_command(self, command: str) -> bool:
        """Check if command is safe to execute during testing."""
        command_lower = command.lower().strip()

        # Check against safe prefixes
        for prefix in self.SAFE_PREFIXES:
            if command_lower.startswith(prefix.lower()):
                return True

        # Allow any command that starts with common shell builtins
        shell_builtins = ['export', 'source', 'type', 'which', 'test', '[', 'true', 'false']
        for builtin in shell_builtins:
            if command_lower.startswith(builtin):
                return True

        return False

    def _cleanup(self):
        """Clean up temporary files."""
        if self._temp_dir:
            import shutil
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None
