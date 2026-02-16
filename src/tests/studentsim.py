"""TC-STUDENTSIM: Student simulation.

Simulates a student following exercise instructions from the EPUB:
1. Extract instructions from EPUB
2. Execute EPUB instructions step-by-step
3. Create/modify files as instructed
4. Verify commands execute successfully

This is the core test that validates the student experience.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..epub import InstructionExtractor, InstructionStep, FileAction
from ..models import (
    TestResult, Bug, BugSeverity, ExerciseContext, ExerciseType,
    ExecutedStep, StepResult
)
from ..ssh import SSHConnection


CONTAINER_NAME = "qa-devcontainer"


class TC_STUDENTSIM:
    """Student simulation test category.

    This is special among test categories because it needs the EPUB path
    to extract instructions.
    """

    def __init__(self, epub_path: Path, timeout_command: int = 120):
        """Initialize student simulator.

        Args:
            epub_path: Path to EPUB file
            timeout_command: Command execution timeout in seconds
        """
        self.epub_path = epub_path
        self.timeout_command = timeout_command
        self._extractor: Optional[InstructionExtractor] = None
        self._devcontainer_active = False
        self._devcontainer_workdir: Optional[str] = None
        self._devcontainer_user: Optional[str] = None

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """Simulate student completing an exercise."""
        print(f"\n   TC-STUDENTSIM: Simulating student workflow...")

        bugs_found = []
        start_time = datetime.now()
        details = {}

        # 1. Extract instructions from EPUB (reuses extraction across calls)
        print(f"      Extracting instructions from EPUB...")
        if self._extractor is None:
            self._extractor = InstructionExtractor(self.epub_path)
        instructions = self._extractor.extract(exercise.id)

        if not instructions:
            bugs_found.append(Bug(
                id=f"STUDENTSIM-NOEPUB-{exercise.id}",
                severity=BugSeverity.P0_BLOCKER,
                category="TC-STUDENTSIM",
                exercise_id=exercise.id,
                description=f"Could not find exercise '{exercise.id}' in EPUB",
                fix_recommendation="Verify exercise ID matches EPUB content",
                verification_steps=["Check EPUB for exercise section ID"]
            ))
            return TestResult(
                category="TC-STUDENTSIM",
                exercise_id=exercise.id,
                passed=False,
                timestamp=datetime.now().isoformat(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                bugs_found=bugs_found,
                details={'phase': 'extract'}
            )

        print(f"      Found {len(instructions.steps)} steps, {instructions.total_commands} commands")
        details['steps_in_epub'] = len(instructions.steps)
        details['commands_in_epub'] = instructions.total_commands

        # 2. Set up dev container if course uses one (lab start already done by TC-PREREQ)
        uses_devcontainer = (exercise.course_profile and
                             exercise.course_profile.uses_dev_containers)
        if uses_devcontainer:
            self._setup_devcontainer(exercise, ssh)

        # 3. Execute instructions
        try:
            print(f"      Following instructions...")
            executed_steps, all_passed = self._execute_instructions(
                exercise, ssh, instructions, bugs_found
            )
        finally:
            # Stop dev container after instructions (grading runs on workstation)
            self._stop_devcontainer(ssh)

        details['steps_executed'] = len(executed_steps)
        details['steps_passed'] = sum(1 for s in executed_steps if s.result == StepResult.PASS)
        details['steps_failed'] = sum(1 for s in executed_steps if s.result == StepResult.FAIL)
        details['steps_warned'] = sum(1 for s in executed_steps if s.result == StepResult.WARN)

        # Store executed steps in details for reporting
        details['executed_steps'] = [
            {
                'number': s.number,
                'text': s.text,
                'result': s.result.value,
                'command': s.command,
                'duration': s.duration_seconds
            }
            for s in executed_steps
        ]

        duration = (datetime.now() - start_time).total_seconds()

        print(f"      Results: {details['steps_passed']} passed, "
              f"{details['steps_failed']} failed, {details['steps_warned']} warned")

        return TestResult(
            category="TC-STUDENTSIM",
            exercise_id=exercise.id,
            passed=all_passed and len(bugs_found) == 0,
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details=details
        )

    def cleanup(self):
        """Clean up EPUB extraction temp files."""
        if self._extractor:
            self._extractor.cleanup()
            self._extractor = None

    def _setup_devcontainer(self, exercise: ExerciseContext,
                            ssh: SSHConnection):
        """Detect and start dev container for the exercise."""
        project_dir = f"/home/student/{exercise.lab_name}"

        print(f"      Setting up dev container...")
        dc_info = ssh.ensure_devcontainer(project_dir, CONTAINER_NAME)

        if dc_info:
            self._devcontainer_active = True
            self._devcontainer_workdir = dc_info['workdir']
            self._devcontainer_user = dc_info['user']
            print(f"      Dev container ready (workdir: {self._devcontainer_workdir})")
        else:
            print(f"      No dev container config found, running on workstation")

    def _stop_devcontainer(self, ssh: SSHConnection):
        """Stop dev container if active."""
        if self._devcontainer_active:
            ssh.stop_devcontainer(CONTAINER_NAME)
            self._devcontainer_active = False
            self._devcontainer_workdir = None
            self._devcontainer_user = None

    def _run_command(self, command: str, ssh: SSHConnection,
                     timeout: int = 120):
        """Run command, routing through dev container if active."""
        if self._devcontainer_active:
            return ssh.run_in_devcontainer(
                command,
                container_name=CONTAINER_NAME,
                workdir=self._devcontainer_workdir,
                user=self._devcontainer_user,
                timeout=timeout,
            )
        return ssh.run(command, timeout=timeout)

    def _translate_for_devcontainer(self, cmd_text: str) -> str:
        """Translate commands for dev container execution.

        Inside the dev container, ansible-navigator would try to start a
        nested EE container (podman-in-podman) which fails without a TTY.
        Convert to ansible-playbook which runs directly in the dev container
        -- it has ansible + all collections pre-installed.
        """
        cmd = cmd_text.strip()

        if not cmd.startswith('ansible-navigator'):
            return cmd_text

        # ansible-navigator run playbook.yml [opts] -> ansible-playbook playbook.yml [opts]
        nav_match = re.match(r'^ansible-navigator\s+run\s+(.+)$', cmd)
        if nav_match:
            rest = nav_match.group(1)
            # Remove navigator-specific flags
            rest = re.sub(r'-m\s+\S+', '', rest)        # --mode
            rest = re.sub(r'--mode\s+\S+', '', rest)
            rest = re.sub(r'--pp\s+\S+', '', rest)      # --pull-policy
            rest = re.sub(r'--eei\s+\S+', '', rest)     # --execution-environment-image
            rest = re.sub(r'--ce\s+\S+', '', rest)      # --container-engine
            rest = re.sub(r'\s+', ' ', rest).strip()
            return f"ansible-playbook {rest}"

        nav_doc = re.match(r'^ansible-navigator\s+doc\s+(.+)$', cmd)
        if nav_doc:
            return f"ansible-doc {nav_doc.group(1)}"

        nav_lint = re.match(r'^ansible-navigator\s+lint\s+(.+)$', cmd)
        if nav_lint:
            return f"ansible-lint {nav_lint.group(1)}"

        return cmd_text

    def _execute_instructions(self, exercise: ExerciseContext,
                               ssh: SSHConnection,
                               instructions,
                               bugs: List[Bug]) -> tuple:
        """Execute all instruction steps.

        Returns:
            Tuple of (executed_steps, all_passed)
        """
        executed_steps: List[ExecutedStep] = []
        current_dir = None

        def execute_step(step: InstructionStep, depth: int = 0) -> bool:
            nonlocal current_dir
            indent = "      " + ("  " * depth)

            print(f"{indent}Step {step.number}: {step.text[:50]}...")

            # Process file actions before commands
            for file_action in step.file_actions:
                step_start = datetime.now()
                success = self._execute_file_action(
                    file_action, current_dir, ssh, indent
                )
                duration = (datetime.now() - step_start).total_seconds()

                if success:
                    print(f"{indent}  ✓ ({duration:.1f}s)")
                    executed_steps.append(ExecutedStep(
                        number=step.number,
                        text=step.text,
                        result=StepResult.PASS,
                        command=f"[write] {file_action.filename}",
                        output=f"Wrote {len(file_action.content)} bytes",
                        duration_seconds=duration,
                        is_file_action=True,
                    ))
                else:
                    print(f"{indent}  ✗ Failed")
                    executed_steps.append(ExecutedStep(
                        number=step.number,
                        text=step.text,
                        result=StepResult.FAIL,
                        command=f"[write] {file_action.filename}",
                        error=f"Failed to write {file_action.filename}",
                        duration_seconds=duration,
                        is_file_action=True,
                    ))
                    bugs.append(Bug(
                        id=f"STUDENTSIM-FILE-{step.number}-{exercise.id}",
                        severity=BugSeverity.P2_HIGH,
                        category="TC-STUDENTSIM",
                        exercise_id=exercise.id,
                        description=f"Failed to write file {file_action.filename}",
                        fix_recommendation="Check file permissions and path",
                        verification_steps=[]
                    ))
                    return False

            # Process commands
            for cmd in step.commands:
                step_start = datetime.now()

                # Convert interactive/TTY commands
                actual_cmd, reason = self._convert_interactive_command(cmd.text)

                if actual_cmd is None:
                    print(f"{indent}  [skip] {reason}")
                    executed_steps.append(ExecutedStep(
                        number=step.number,
                        text=step.text,
                        result=StepResult.SKIP,
                        command=cmd.text,
                    ))
                    continue

                if reason:
                    print(f"{indent}  $ {actual_cmd[:40]}... ({reason})")
                else:
                    print(f"{indent}  $ {cmd.text[:40]}...")

                # Translate for devcontainer (navigator -> playbook, etc.)
                if self._devcontainer_active:
                    actual_cmd = self._translate_for_devcontainer(actual_cmd)

                # Track cd commands for working directory
                home_dir = (self._devcontainer_workdir
                            if self._devcontainer_active
                            else "/home/student")
                cd_match = re.match(r'^cd\s+(.+)$', actual_cmd.strip())
                if cd_match:
                    new_dir = cd_match.group(1).strip().replace('~', home_dir)
                    if not new_dir.startswith('/'):
                        new_dir = f"{current_dir or home_dir}/{new_dir}"
                    current_dir = new_dir
                    actual_cmd = f"cd {current_dir} && pwd"
                elif current_dir:
                    actual_cmd = f"cd {current_dir} && {actual_cmd}"

                result = self._run_command(actual_cmd, ssh,
                                           timeout=self.timeout_command)
                duration = (datetime.now() - step_start).total_seconds()

                if result.success:
                    print(f"{indent}  ✓ ({duration:.1f}s)")
                    executed_steps.append(ExecutedStep(
                        number=step.number,
                        text=step.text,
                        result=StepResult.PASS,
                        command=cmd.text,
                        output=result.stdout[:500] if result.stdout else None,
                        duration_seconds=duration,
                    ))
                else:
                    # Warn but continue (exercises may demo failures)
                    print(f"{indent}  ⚠ (rc={result.return_code}, continuing)")
                    executed_steps.append(ExecutedStep(
                        number=step.number,
                        text=step.text,
                        result=StepResult.WARN,
                        command=cmd.text,
                        output=result.stdout[:500] if result.stdout else None,
                        error=result.stderr or result.stdout,
                        duration_seconds=duration,
                    ))

            # Process sub-steps
            for sub_step in step.sub_steps:
                if not execute_step(sub_step, depth + 1):
                    return False

            return True

        # Execute all steps
        all_passed = True
        for step in instructions.steps:
            if not execute_step(step):
                all_passed = False
                break

        return executed_steps, all_passed

    def _convert_interactive_command(self, cmd_text: str) -> tuple:
        """Convert interactive/TTY commands to non-interactive form.

        Returns:
            Tuple of (converted_command, reason). If None, skip the command.
        """
        cmd = cmd_text.strip()

        if cmd.startswith('watch '):
            match = re.match(r'watch\s+(?:-[nd]\s+\d*\s*)*(.+)$', cmd)
            if match:
                return match.group(1).strip(), "converted 'watch' to single execution"
            return cmd[6:].strip(), "converted 'watch' to single execution"

        if cmd == 'top' or cmd.startswith('top '):
            return "top -b -n 1 | head -20", "converted 'top' to batch mode"

        if cmd == 'htop' or cmd.startswith('htop '):
            return None, "skipped 'htop' (requires TTY)"

        if cmd.startswith('less ') or cmd.startswith('more '):
            file_arg = cmd.split(None, 1)[1] if ' ' in cmd else ''
            if file_arg:
                return f"cat {file_arg}", "converted pager to 'cat'"
            return None, "skipped pager (no file argument)"

        for editor in ['vim ', 'vi ', 'nano ', 'emacs ']:
            if cmd.startswith(editor) or cmd == editor.strip():
                return None, f"skipped '{editor.strip()}' (editor requires TTY)"

        if re.match(r'^ssh\s+\S+$', cmd):
            return None, "skipped interactive SSH session"

        # Only convert tail -f (follow mode), not -f flags on other commands
        if cmd.startswith('tail') and (' -f ' in cmd or cmd.endswith(' -f')):
            converted = cmd.replace(' -f ', ' ').replace(' -f', '')
            return f"{converted} | head -50", "converted 'tail -f' to single read"

        return cmd_text, ""

    def _execute_file_action(self, file_action: FileAction,
                              current_dir: Optional[str],
                              ssh: SSHConnection,
                              indent: str) -> bool:
        """Write a file to the workstation.

        File writes always go to the workstation because the project directory
        is bind-mounted into the dev container. Changes on the workstation
        are visible inside the container.
        """
        filename = file_action.filename
        home_dir = "/home/student"

        # Resolve full path
        if filename.startswith('/'):
            full_path = filename
        elif current_dir:
            # If dev container is active, current_dir is in container space.
            # Translate back to workstation path for file writes.
            if self._devcontainer_active and current_dir.startswith('/workspaces/'):
                # /workspaces/exercise-name/... -> /home/student/exercise-name/...
                ws_relative = current_dir[len('/workspaces/'):]
                full_path = f"{home_dir}/{ws_relative}/{filename}"
            else:
                full_path = f"{current_dir}/{filename}"
        else:
            full_path = f"{home_dir}/{filename}"

        print(f"{indent}  [file] {filename} -> {full_path}")

        result = ssh.write_file(full_path, file_action.content)

        if not result.success:
            print(f"{indent}    Error: {(result.stderr or result.stdout or 'unknown')[:100]}")
        return result.success
