"""Student simulation runner.

Simulates a student following exercise instructions from the EPUB:
1. lab start
2. Follow EPUB instructions (run commands)
3. lab grade (for Labs)
4. lab finish

If this works, the exercise works.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from .epub import InstructionExtractor, ExerciseInstructions, InstructionStep, Command, FileAction, FileActionType
from .models import (
    ExerciseType, SimulationResult, ExecutedStep, StepResult, Bug, BugSeverity,
)
from .ssh import SSHConnection


class StudentSimulator:
    """Simulates a student following exercise instructions."""

    CONTAINER_NAME = "qa-devcontainer"

    def __init__(self, epub_path: Path, workstation: str = "workstation",
                 timeout_lab: int = 300, timeout_command: int = 120,
                 lesson_code: Optional[str] = None):
        self.epub_path = epub_path
        self.workstation = workstation
        self.ssh: Optional[SSHConnection] = None
        self.timeout_lab = timeout_lab
        self.timeout_command = timeout_command
        self.lesson_code = lesson_code
        self._devcontainer_active = False
        self._devcontainer_workdir: Optional[str] = None
        self._devcontainer_user: Optional[str] = None

    def run(self, exercise_id: str, exercise_type: Optional[ExerciseType] = None) -> SimulationResult:
        """Simulate student completing an exercise."""
        start_time = datetime.now()
        if exercise_type is None:
            exercise_type = self._detect_exercise_type(exercise_id)

        print(f"\n{'='*60}")
        print(f"STUDENT SIMULATION: {exercise_id}")
        print(f"{'='*60}")

        # 1. Extract instructions from EPUB
        print("\n1. Extracting instructions from EPUB...")
        extractor = InstructionExtractor(self.epub_path)
        try:
            instructions = extractor.extract(exercise_id)
        finally:
            extractor.cleanup()

        if not instructions:
            return SimulationResult(
                exercise_id=exercise_id,
                exercise_type=exercise_type,
                success=False,
                phase="extract",
                error_message=f"Could not find exercise '{exercise_id}' in EPUB",
            )

        print(f"   Found {len(instructions.steps)} steps, {instructions.total_commands} commands")

        # 2. Connect to workstation
        print("\n2. Connecting to workstation...")
        self.ssh = SSHConnection(self.workstation)
        if not self.ssh.connect():
            return SimulationResult(
                exercise_id=exercise_id,
                exercise_type=exercise_type,
                success=False,
                phase="connect",
                error_message=f"Cannot connect to {self.workstation}",
            )
        print("   Connected")

        # 3. Force lesson (for multi-repo courses)
        if self.lesson_code:
            print(f"\n3. Forcing lesson: {self.lesson_code}")
            force_result = self.ssh.force_lesson(self.lesson_code, timeout=self.timeout_lab)
            if not force_result.success:
                print(f"   Warning: lab force failed: {(force_result.stderr or force_result.stdout)[:200]}")

        # lab start
        start_cmd = instructions.prerequisites_command or f"lab start {exercise_id}"
        print(f"\n   Starting lab: {start_cmd}")
        start_result = self._run_lab_start(exercise_id, exercise_type, instructions)
        if not start_result.success:
            start_result.total_duration_seconds = (datetime.now() - start_time).total_seconds()
            start_result.bugs = self._detect_bugs(start_result)
            self.ssh.close()
            return start_result

        # For Labs: Test grading WITHOUT solution (should fail)
        grade_without_solution_passed = None
        if exercise_type == ExerciseType.LAB:
            print("\n   Testing grading WITHOUT solution (should fail)...")
            grade_result = self.ssh.run_lab_command("grade", exercise_id, timeout=self.timeout_lab)
            grade_without_solution_passed = grade_result.success
            if grade_without_solution_passed:
                # Grading passed without solution - this is a bug!
                print("   WARNING: Grading passed without solution (expected to fail)")
            else:
                print("   Grading correctly failed without solution")

        # Detect and start dev container if exercise uses one
        self._setup_devcontainer(exercise_id)

        # Execute EPUB instructions
        print(f"\n   Following instructions ({len(instructions.steps)} steps)...")
        instruction_result = self._execute_instructions(exercise_id, exercise_type, instructions)

        # Stop dev container before grading/finish (those run on workstation)
        self._stop_devcontainer()

        if not instruction_result.success:
            self._run_lab_finish(exercise_id, exercise_type)
            instruction_result.total_duration_seconds = (datetime.now() - start_time).total_seconds()
            instruction_result.bugs = self._detect_bugs(instruction_result)
            self.ssh.close()
            return instruction_result

        # For Labs, run grading WITH solution (on workstation, not in container)
        grade_with_solution_passed = None
        if exercise_type == ExerciseType.LAB:
            print("\n   Testing grading WITH solution (should pass)...")
            grade_result = self._run_grading(exercise_id, exercise_type)
            grade_with_solution_passed = grade_result.success
            if not grade_result.success:
                print("   WARNING: Grading failed with solution (expected to pass)")
                self._run_lab_finish(exercise_id, exercise_type)
                grade_result.total_duration_seconds = (datetime.now() - start_time).total_seconds()
                grade_result.grade_without_solution_passed = grade_without_solution_passed
                grade_result.grade_with_solution_passed = grade_with_solution_passed
                grade_result.bugs = self._detect_bugs(grade_result)
                self.ssh.close()
                return grade_result
            else:
                print("   Grading passed with solution")

        # lab finish
        step_num = 6 if exercise_type == ExerciseType.LAB else 5
        print(f"\n{step_num}. Finishing lab...")
        finish_result = self._run_lab_finish(exercise_id, exercise_type)

        # Build final result
        duration = (datetime.now() - start_time).total_seconds()
        all_steps = instruction_result.steps_executed

        self.ssh.close()

        if not finish_result.success:
            finish_result.steps_executed = all_steps
            finish_result.total_duration_seconds = duration
            finish_result.bugs = self._detect_bugs(finish_result)
            return finish_result

        result = SimulationResult(
            exercise_id=exercise_id,
            exercise_type=exercise_type,
            success=True,
            phase="complete",
            steps_executed=all_steps,
            steps_passed=sum(1 for s in all_steps if s.result == StepResult.PASS),
            steps_failed=sum(1 for s in all_steps if s.result == StepResult.FAIL),
            total_duration_seconds=duration,
            lab_start_output=start_result.lab_start_output,
            lab_finish_output=finish_result.lab_finish_output,
            grade_without_solution_passed=grade_without_solution_passed,
            grade_with_solution_passed=grade_with_solution_passed,
        )
        result.bugs = self._detect_bugs(result)
        return result

    def run_idempotency(self, exercise_id: str, cycles: int = 2,
                        exercise_type: Optional[ExerciseType] = None) -> List[SimulationResult]:
        """Run exercise multiple times to test idempotency.

        Args:
            exercise_id: Exercise to test
            cycles: Number of cycles to run (default: 2)
            exercise_type: Exercise type (GE or Lab)

        Returns:
            List of SimulationResults, one per cycle

        Flow:
            Cycle 1: lab start → simulate → grade (if Lab) → finish
            Cycle 2: lab start → simulate → grade (if Lab) → finish
            ...
            Cycle N: lab start → simulate → grade (if Lab) → finish

        This tests:
            - Scripts are idempotent (can run multiple times)
            - Grading passes on subsequent runs
            - Cleanup is complete (finish actually removes everything)
            - No state pollution between cycles
        """
        if exercise_type is None:
            exercise_type = self._detect_exercise_type(exercise_id)

        print(f"\n{'='*60}")
        print(f"IDEMPOTENCY TESTING: {exercise_id} ({cycles} cycles)")
        print(f"{'='*60}")

        overall_start = datetime.now()
        results = []

        for cycle_num in range(1, cycles + 1):
            print(f"\n{'='*60}")
            print(f"CYCLE {cycle_num}/{cycles}")
            print(f"{'='*60}")

            # Run the exercise (includes finish)
            result = self.run(exercise_id, exercise_type=exercise_type)
            result.cycle = cycle_num
            results.append(result)

            # Report cycle result
            status = "✓ PASSED" if result.success else "✗ FAILED"
            print(f"\n   Cycle {cycle_num}/{cycles}: {status}")

            # Stop if a cycle fails
            if not result.success:
                print(f"\n   WARNING: Cycle {cycle_num} failed - stopping idempotency test")
                break

        overall_duration = (datetime.now() - overall_start).total_seconds()

        # Analyze idempotency
        print(f"\n{'='*60}")
        print(f"IDEMPOTENCY ANALYSIS")
        print(f"{'='*60}")

        passed_cycles = [r.cycle for r in results if r.success]
        failed_cycles = [r.cycle for r in results if not r.success]

        print(f"\nCycles passed: {len(passed_cycles)}/{len(results)}")
        print(f"Cycles failed: {len(failed_cycles)}/{len(results)}")

        if len(passed_cycles) == len(results):
            print(f"\n✓ IDEMPOTENT: All {len(results)} cycles passed")
        elif len(passed_cycles) > 0 and len(failed_cycles) > 0:
            print(f"\n✗ NOT IDEMPOTENT: Cycle {passed_cycles[0]} passed but cycle {failed_cycles[0]} failed")
            # Add idempotency bug to failed cycles
            for result in results:
                if not result.success and result.cycle > 1:
                    result.bugs.append(Bug(
                        id=f"{exercise_id}-P1-IDEM-{result.cycle:03d}",
                        severity=BugSeverity.P1_CRITICAL,
                        category="LEGACY",
                        exercise_id=exercise_id,
                        description=f"Exercise not idempotent: Cycle {result.cycle} failed after Cycle 1 passed",
                        fix_recommendation="Review lab scripts for state pollution, ensure cleanup is complete, check for hardcoded values",
                        verification_steps=[
                            "1. Run lab start → simulate → grade",
                            "2. Run lab start → simulate → grade again (without finish)",
                            "3. Should pass both times",
                        ],
                    ))
        else:
            print(f"\n✗ ALL CYCLES FAILED: Exercise has fundamental issues")

        print(f"\nTotal duration: {overall_duration:.1f}s")
        print(f"Average per cycle: {overall_duration/len(results):.1f}s")

        return results

    def test_solutions(self, exercise_id: str, exercise_type: Optional[ExerciseType] = None) -> SimulationResult:
        """Test solution files for an exercise.

        Skips student simulation and directly tests that solution files work.
        Flow: lab start → copy solutions → run solutions → lab grade → lab finish
        """
        start_time = datetime.now()
        if exercise_type is None:
            exercise_type = self._detect_exercise_type(exercise_id)

        print(f"\n{'='*60}")
        print(f"SOLUTION TESTING: {exercise_id}")
        print(f"{'='*60}")

        # Extract exercise context to get solution files
        print("\n1. Finding solution files...")
        extractor = InstructionExtractor(self.epub_path)
        try:
            # Parse to get exercise context with solution files
            from .epub import EPUBParser
            parser = EPUBParser(self.epub_path, self.epub_path.parent)
            course_data = parser.parse()
            exercise_ctx = next((e for e in course_data.exercises if e.id == exercise_id), None)

            if not exercise_ctx or not exercise_ctx.solution_files:
                return SimulationResult(
                    exercise_id=exercise_id, exercise_type=exercise_type,
                    success=False, phase="solutions",
                    error_message="No solution files found for this exercise",
                )

            solution_files = exercise_ctx.solution_files
            print(f"   Found {len(solution_files)} solution file(s)")
        finally:
            extractor.cleanup()

        # Connect to workstation
        print("\n2. Connecting to workstation...")
        self.ssh = SSHConnection(self.workstation)
        if not self.ssh.connect():
            return SimulationResult(
                exercise_id=exercise_id, exercise_type=exercise_type,
                success=False, phase="connect",
                error_message=f"Cannot connect to {self.workstation}",
            )
        print("   Connected")

        # Force lesson if needed
        if self.lesson_code:
            print(f"\n3. Forcing lesson: {self.lesson_code}")
            self.ssh.force_lesson(self.lesson_code, timeout=self.timeout_lab)

        # lab start
        print(f"\n   Starting lab: lab start {exercise_id}")
        start_result = self._run_lab_start(exercise_id, exercise_type, None)
        if not start_result.success:
            start_result.total_duration_seconds = (datetime.now() - start_time).total_seconds()
            self.ssh.close()
            return start_result

        # Set up dev container if lesson uses it
        self._setup_devcontainer(exercise_id)
        if not self._devcontainer_active:
            print("   No dev container configured, using workstation directly")

        # Test each solution file
        print(f"\n   Testing {len(solution_files)} solution file(s)...")
        executed_steps = []
        for sol_file in solution_files:
            step_start = datetime.now()
            target_name = sol_file.name.removesuffix('.sol')

            # Determine target path based on whether devcontainer is active
            if self._devcontainer_active:
                target_path = f"{self._devcontainer_workdir}/{target_name}"
            else:
                target_path = f"/home/student/{exercise_id}/{target_name}"

            # Copy solution to exercise directory
            print(f"     {sol_file.name} → {target_name}")
            content = sol_file.read_text()

            if self._devcontainer_active:
                copy_result = self.ssh.write_file_in_devcontainer(
                    target_path, content, user="root"
                )
            else:
                copy_result = self.ssh.write_file(target_path, content)

            if not copy_result.success:
                print(f"       FAILED to copy")
                executed_steps.append(ExecutedStep(
                    number="sol", text=f"Copy {sol_file.name}",
                    result=StepResult.FAIL, command=f"[copy] {sol_file.name}",
                    error="Failed to copy solution file",
                    duration_seconds=(datetime.now() - step_start).total_seconds(),
                ))
                break

            # If it's a playbook, run it
            if target_name.endswith('.yml') or target_name.endswith('.yaml'):
                if self._devcontainer_active:
                    run_result = self.ssh.run_in_devcontainer(
                        f"ansible-playbook {target_name}",
                        workdir=self._devcontainer_workdir,
                        user="root",
                        timeout=self.timeout_command
                    )
                else:
                    run_result = self.ssh.run(
                        f"cd /home/student/{exercise_id} && ansible-playbook {target_name}",
                        timeout=self.timeout_command
                    )
                duration = (datetime.now() - step_start).total_seconds()

                if run_result.success:
                    print(f"       OK ({duration:.1f}s)")
                    executed_steps.append(ExecutedStep(
                        number="sol", text=f"Run {target_name}",
                        result=StepResult.PASS, command=f"ansible-playbook {target_name}",
                        output=run_result.stdout[:200],
                        duration_seconds=duration,
                    ))
                else:
                    print(f"       FAILED ({duration:.1f}s)")
                    executed_steps.append(ExecutedStep(
                        number="sol", text=f"Run {target_name}",
                        result=StepResult.FAIL, command=f"ansible-playbook {target_name}",
                        error=run_result.stderr or run_result.stdout,
                        duration_seconds=duration,
                    ))
                    break
            else:
                # Non-playbook file, just copied
                executed_steps.append(ExecutedStep(
                    number="sol", text=f"Copy {sol_file.name}",
                    result=StepResult.PASS, command=f"[copy] {sol_file.name}",
                    duration_seconds=(datetime.now() - step_start).total_seconds(),
                ))

        passed = sum(1 for s in executed_steps if s.result == StepResult.PASS)
        failed = sum(1 for s in executed_steps if s.result == StepResult.FAIL)
        print(f"\n   Results: {passed} passed, {failed} failed")

        all_passed = failed == 0

        # For Labs, run grading
        if exercise_type == ExerciseType.LAB and all_passed:
            print("\n   Running grading with solutions...")
            grade_result = self._run_grading(exercise_id, exercise_type)
            if not grade_result.success:
                self._run_lab_finish(exercise_id, exercise_type)
                grade_result.total_duration_seconds = (datetime.now() - start_time).total_seconds()
                grade_result.steps_executed = executed_steps
                self.ssh.close()
                return grade_result

        # lab finish
        print(f"\n4. Finishing lab...")
        finish_result = self._run_lab_finish(exercise_id, exercise_type)

        duration = (datetime.now() - start_time).total_seconds()
        self.ssh.close()

        if not finish_result.success:
            finish_result.steps_executed = executed_steps
            finish_result.total_duration_seconds = duration
            return finish_result

        return SimulationResult(
            exercise_id=exercise_id, exercise_type=exercise_type,
            success=all_passed, phase="solutions" if all_passed else "solutions",
            steps_executed=executed_steps, steps_passed=passed, steps_failed=failed,
            total_duration_seconds=duration,
            error_message=None if all_passed else "Solution file testing failed",
        )

    def _run_lab_start(self, exercise_id: str, exercise_type: ExerciseType,
                        instructions: Optional[ExerciseInstructions]) -> SimulationResult:
        """Run lab start."""

        if instructions and instructions.prerequisites_command:
            result = self.ssh.run(instructions.prerequisites_command, timeout=self.timeout_lab)
        else:
            result = self.ssh.run_lab_command("start", exercise_id, timeout=self.timeout_lab)

        if not result.success:
            return SimulationResult(
                exercise_id=exercise_id,
                exercise_type=exercise_type,
                success=False,
                phase="start",
                error_message=f"lab start failed: {(result.stderr or result.stdout)[:300]}",
                lab_start_output=result.stdout,
            )

        print("   Lab started successfully")
        return SimulationResult(
            exercise_id=exercise_id,
            exercise_type=exercise_type,
            success=True,
            phase="start",
            lab_start_output=result.stdout,
        )

    def _execute_instructions(self, exercise_id: str, exercise_type: ExerciseType,
                               instructions: ExerciseInstructions) -> SimulationResult:
        """Execute all instruction steps."""
        executed_steps: List[ExecutedStep] = []
        current_dir = None

        def execute_step(step: InstructionStep, depth: int = 0) -> bool:
            nonlocal current_dir
            indent = "   " + ("  " * depth)

            print(f"{indent}Step {step.number}: {step.text[:60]}...")

            # Process file actions before commands
            for file_action in step.file_actions:
                step_start = datetime.now()
                success = self._execute_file_action(file_action, current_dir, indent)
                duration = (datetime.now() - step_start).total_seconds()

                if success:
                    print(f"{indent}  OK ({duration:.1f}s)")
                    executed_steps.append(ExecutedStep(
                        number=step.number, text=step.text,
                        result=StepResult.PASS,
                        command=f"[write] {file_action.filename}",
                        output=f"Wrote {len(file_action.content)} bytes",
                        duration_seconds=duration,
                        is_file_action=True,
                    ))
                else:
                    print(f"{indent}  FAILED")
                    executed_steps.append(ExecutedStep(
                        number=step.number, text=step.text,
                        result=StepResult.FAIL,
                        command=f"[write] {file_action.filename}",
                        error=f"Failed to write {file_action.filename}",
                        duration_seconds=duration,
                        is_file_action=True,
                    ))
                    return False

            for cmd in step.commands:
                step_start = datetime.now()

                # Convert interactive/TTY commands
                actual_cmd, reason = self._convert_interactive_command(cmd.text)

                if actual_cmd is None:
                    print(f"{indent}  [skip] {reason}: {cmd.text[:40]}...")
                    executed_steps.append(ExecutedStep(
                        number=step.number, text=step.text,
                        result=StepResult.SKIP, command=cmd.text,
                    ))
                    continue

                # Handle interactive auth prompts
                if cmd.is_interactive and cmd.prompts:
                    converted = self._convert_to_non_interactive(cmd)
                    if converted:
                        print(f"{indent}  $ {converted[:50]}... (auto-auth)")
                        actual_cmd = converted
                    else:
                        print(f"{indent}  [skip] Interactive: {cmd.text[:40]}...")
                        executed_steps.append(ExecutedStep(
                            number=step.number, text=step.text,
                            result=StepResult.SKIP, command=cmd.text,
                        ))
                        continue
                elif reason:
                    print(f"{indent}  $ {actual_cmd[:50]}... ({reason})")
                else:
                    print(f"{indent}  $ {cmd.text[:50]}...")

                # Translate for devcontainer (ansible-navigator -> ansible-playbook)
                if self._devcontainer_active:
                    actual_cmd = self._translate_for_devcontainer(actual_cmd)

                # Track cd commands for working directory
                home_dir = self._devcontainer_workdir if self._devcontainer_active else "/home/student"
                cd_match = re.match(r'^cd\s+(.+)$', actual_cmd.strip())
                if cd_match:
                    new_dir = cd_match.group(1).strip().replace('~', home_dir)
                    if not new_dir.startswith('/'):
                        new_dir = f"{current_dir or home_dir}/{new_dir}"
                    current_dir = new_dir
                    actual_cmd = f"cd {current_dir} && pwd"
                elif current_dir:
                    actual_cmd = f"cd {current_dir} && {actual_cmd}"

                result = self._run_command(actual_cmd, timeout=self.timeout_command)
                duration = (datetime.now() - step_start).total_seconds()

                if result.success:
                    print(f"{indent}  OK ({duration:.1f}s)")
                    executed_steps.append(ExecutedStep(
                        number=step.number, text=step.text,
                        result=StepResult.PASS, command=cmd.text,
                        output=result.stdout[:500] if result.stdout else None,
                        duration_seconds=duration,
                    ))
                else:
                    # Don't stop on command failures — exercises often
                    # demonstrate error scenarios (ignore_errors, rescue
                    # blocks, etc.) where the student is told to observe
                    # the failure and then continue to the next step.
                    # Record as WARN and keep going.
                    print(f"{indent}  WARN (rc={result.return_code}, continuing)")
                    executed_steps.append(ExecutedStep(
                        number=step.number, text=step.text,
                        result=StepResult.WARN, command=cmd.text,
                        output=result.stdout[:500] if result.stdout else None,
                        error=result.stderr or result.stdout,
                        duration_seconds=duration,
                    ))

            for sub_step in step.sub_steps:
                if not execute_step(sub_step, depth + 1):
                    return False

            return True

        all_passed = True
        for step in instructions.steps:
            if not execute_step(step):
                all_passed = False
                break

        passed = sum(1 for s in executed_steps if s.result == StepResult.PASS)
        warned = sum(1 for s in executed_steps if s.result == StepResult.WARN)
        failed = sum(1 for s in executed_steps if s.result == StepResult.FAIL)
        status_parts = [f"{passed} passed"]
        if warned:
            status_parts.append(f"{warned} warned")
        if failed:
            status_parts.append(f"{failed} failed")
        print(f"\n   Results: {', '.join(status_parts)}")

        return SimulationResult(
            exercise_id=exercise_id,
            exercise_type=exercise_type,
            success=all_passed,
            phase="instructions",
            steps_executed=executed_steps,
            steps_passed=passed,
            steps_failed=failed,
            error_message=None if all_passed else "Instruction step failed",
        )

    def _convert_interactive_command(self, cmd_text: str) -> Tuple[Optional[str], str]:
        """Convert interactive/TTY commands to non-interactive form.

        Returns (converted_command, reason). If converted_command is None,
        the command should be skipped.
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

        if cmd.startswith('tail') and (' -f ' in cmd or cmd.endswith(' -f')):
            converted = cmd.replace(' -f ', ' ').replace(' -f', '')
            return f"{converted} | head -50", "converted 'tail -f' to single read"

        return cmd_text, ""

    def _convert_to_non_interactive(self, cmd: Command) -> Optional[str]:
        """Convert interactive commands (with prompts) to non-interactive form."""
        username = None
        password = None
        for prompt, response in cmd.prompts:
            if 'username' in prompt.lower():
                username = response
            elif 'password' in prompt.lower():
                password = response

        if cmd.text.startswith('podman login') and username and password:
            match = re.match(r'podman login\s+(\S+)', cmd.text)
            if match:
                return f"podman login {match.group(1)} --username {username} --password {password}"

        if cmd.text.startswith('docker login') and username and password:
            match = re.match(r'docker login\s+(\S+)', cmd.text)
            if match:
                return f"docker login {match.group(1)} --username {username} --password {password}"

        return None

    def _run_grading(self, exercise_id: str, exercise_type: ExerciseType) -> SimulationResult:
        """Run lab grade.

        DynoLabs grading uses GradingSteps (non-fatal), so:
        - Exit code 0 = script completed (doesn't mean checks passed!)
        - Exit code != 0 = script crashed (fatal error)
        - To determine pass/fail, parse output for SUCCESS/FAIL step statuses
        """
        result = self.ssh.run_lab_command("grade", exercise_id, timeout=self.timeout_lab)

        # Check if script crashed (fatal error)
        if not result.success or result.return_code != 0:
            output = (result.stdout or "") + (result.stderr or "")
            return SimulationResult(
                exercise_id=exercise_id, exercise_type=exercise_type,
                success=False, phase="grade",
                error_message=f"Grading script crashed (rc={result.return_code}): {output[:200]}",
                lab_grade_output=result.stdout,
            )

        # Parse output for step status indicators (DynoLabs v4/v5)
        pass_count = len(re.findall(r'\b(SUCCESS|PASS)\b', result.stdout))
        fail_count = len(re.findall(r'\b(FAIL)\b', result.stdout))

        # If any checks failed, grading failed
        if fail_count > 0:
            print(f"   Grading failed ({fail_count} checks failed)")
            return SimulationResult(
                exercise_id=exercise_id, exercise_type=exercise_type,
                success=False, phase="grade",
                error_message=f"Grading failed: {fail_count}/{pass_count + fail_count} checks failed",
                lab_grade_output=result.stdout,
            )

        # All checks passed (or no checks found - be lenient)
        print(f"   Grading passed ({pass_count} checks passed)")
        return SimulationResult(
            exercise_id=exercise_id, exercise_type=exercise_type,
            success=True, phase="grade",
            lab_grade_output=result.stdout,
        )

    def _run_lab_finish(self, exercise_id: str, exercise_type: ExerciseType) -> SimulationResult:
        """Run lab finish and verify cleanup by re-running lab start.

        The only reliable way to verify cleanup is to check that the
        exercise can be started fresh. If lab start succeeds after
        lab finish, the cleanup worked. This is also what a student
        experiences when redoing an exercise.
        """
        result = self.ssh.run_lab_command("finish", exercise_id, timeout=self.timeout_lab)

        if not result.success:
            print(f"   FAILED: lab finish returned non-zero exit code")
            print(f"     {(result.stderr or result.stdout or 'unknown')[:200]}")
            return SimulationResult(
                exercise_id=exercise_id, exercise_type=exercise_type,
                success=False, phase="finish",
                error_message=f"lab finish failed (rc={result.return_code})",
                lab_finish_output=result.stdout,
            )

        # Check finish output for failure indicators
        finish_output = (result.stdout or "").lower()
        if 'lab finish failed' in finish_output or 'cannot continue' in finish_output:
            print(f"   FAILED: lab finish reported errors")
            print(f"     {result.stdout[:200]}")
            return SimulationResult(
                exercise_id=exercise_id, exercise_type=exercise_type,
                success=False, phase="finish",
                error_message="lab finish reported errors in output",
                lab_finish_output=result.stdout,
            )

        print("   Lab finished")

        # Verify cleanup: try lab start again — if it succeeds,
        # finish properly cleaned up the environment
        print("   Verifying cleanup (lab start)...")
        verify_start = self.ssh.run_lab_command("start", exercise_id, timeout=self.timeout_lab)
        if not verify_start.success:
            start_output = (verify_start.stderr or verify_start.stdout or "")[:200]
            print(f"   FAILED: lab start failed after finish — cleanup incomplete")
            print(f"     {start_output}")
            return SimulationResult(
                exercise_id=exercise_id, exercise_type=exercise_type,
                success=False, phase="finish",
                error_message=f"Cleanup verification failed: lab start fails after finish: {start_output}",
                lab_finish_output=result.stdout,
            )

        # Clean up the verification start
        print("   Cleanup verified, finishing again...")
        self.ssh.run_lab_command("finish", exercise_id, timeout=self.timeout_lab)

        # Verify devcontainer is stopped
        container_check = self.ssh.run(
            f"podman ps -q --filter name={self.CONTAINER_NAME} 2>/dev/null", timeout=10)
        if container_check.success and container_check.stdout.strip():
            print(f"   Warning: dev container still running, stopping it")
            self.ssh.stop_devcontainer(self.CONTAINER_NAME)

        print("   Cleanup verified")
        return SimulationResult(
            exercise_id=exercise_id, exercise_type=exercise_type,
            success=True, phase="finish",
            lab_finish_output=result.stdout,
        )

    # --- Devcontainer support ---

    def _setup_devcontainer(self, exercise_id: str):
        """Detect and start devcontainer if the exercise uses one."""
        project_dir = f"/home/student/{exercise_id}"

        # Check for devcontainer config on workstation
        dc_path = f"{project_dir}/.devcontainer/podman/devcontainer.json"
        dc_content = self.ssh.read_file(dc_path)
        if not dc_content:
            # Try alternate path
            dc_path = f"{project_dir}/.devcontainer/devcontainer.json"
            dc_content = self.ssh.read_file(dc_path)

        if not dc_content:
            return

        try:
            config = json.loads(dc_content)
        except json.JSONDecodeError:
            print(f"   Warning: Could not parse devcontainer config")
            return

        image = config.get("image", "")
        run_args = config.get("runArgs", [])
        container_user = config.get("containerUser")
        if not image:
            return

        print(f"   Setting up dev container ({image.split('/')[-1]})...")
        result = self.ssh.start_devcontainer(
            image=image, run_args=run_args,
            project_dir=project_dir,
            container_name=self.CONTAINER_NAME,
            container_user=container_user,
        )

        if result.success:
            self._devcontainer_active = True
            self._devcontainer_workdir = f"/workspaces/{exercise_id}"
            self._devcontainer_user = container_user
            print(f"   Dev container ready (workdir: {self._devcontainer_workdir})")
        else:
            print(f"   Warning: Dev container setup failed, running commands directly")
            print(f"   {(result.stderr or result.stdout)[:200]}")

    def _stop_devcontainer(self):
        """Stop devcontainer if active."""
        if self._devcontainer_active:
            self.ssh.stop_devcontainer(self.CONTAINER_NAME)
            self._devcontainer_active = False
            self._devcontainer_user = None

    def _detect_bugs(self, result: SimulationResult) -> List[Bug]:
        """Auto-detect bugs from simulation failures.

        Severity classification:
        - P0 (Blocker): SSH fails, lab command unavailable, infrastructure broken
        - P1 (Critical): Lab start/grade/finish fails, solution fails
        - P2 (High): Instruction steps fail, file writes fail
        - P3 (Low): Warnings, expected failures (error-handling exercises)
        """
        bugs = []

        # P0: Infrastructure failures
        if result.phase == "connect":
            bugs.append(Bug(
                id=f"{result.exercise_id}-P0-001",
                severity=BugSeverity.P0_BLOCKER,
                category="LEGACY",
                exercise_id=result.exercise_id,
                description=f"Cannot connect to workstation: {result.error_message}",
                fix_recommendation="Check SSH configuration, workstation availability, and network connectivity",
                verification_steps=["1. Verify workstation is running", "2. Test SSH manually", "3. Check ~/.ssh/config"],
            ))
        elif result.phase == "extract" and "lab command not found" in (result.error_message or "").lower():
            bugs.append(Bug(
                id=f"{result.exercise_id}-P0-002",
                severity=BugSeverity.P0_BLOCKER,
                category="LEGACY",
                exercise_id=result.exercise_id,
                description="Lab command not available on workstation",
                fix_recommendation="Install rht-labs-core package or verify course environment setup",
                verification_steps=["1. SSH to workstation", "2. Run 'which lab'", "3. Install missing package"],
            ))

        # P1: Lab command failures
        elif result.phase == "start":
            bugs.append(Bug(
                id=f"{result.exercise_id}-P1-001",
                severity=BugSeverity.P1_CRITICAL,
                category="LEGACY",
                exercise_id=result.exercise_id,
                description=f"Lab start failed: {result.error_message}",
                fix_recommendation="Review start playbook, check managed host connectivity, verify prerequisites",
                verification_steps=["1. Run lab start manually", "2. Check playbook syntax", "3. Verify hosts are reachable"],
            ))
        elif result.phase == "grade":
            bugs.append(Bug(
                id=f"{result.exercise_id}-P1-002",
                severity=BugSeverity.P1_CRITICAL,
                category="LEGACY",
                exercise_id=result.exercise_id,
                description=f"Grading failed: {result.error_message}",
                fix_recommendation="Review grading script, ensure validation logic is correct, test grading manually",
                verification_steps=["1. Review grade playbook", "2. Test grading with solution", "3. Check expected vs actual state"],
            ))
        elif result.phase == "finish":
            bugs.append(Bug(
                id=f"{result.exercise_id}-P1-003",
                severity=BugSeverity.P1_CRITICAL,
                category="LEGACY",
                exercise_id=result.exercise_id,
                description=f"Lab finish failed: {result.error_message}",
                fix_recommendation="Review finish playbook, ensure cleanup tasks are idempotent and handle missing resources gracefully",
                verification_steps=["1. Run lab finish manually", "2. Check cleanup playbook", "3. Verify resources are removed"],
            ))
        elif result.phase == "solutions":
            bugs.append(Bug(
                id=f"{result.exercise_id}-P1-004",
                severity=BugSeverity.P1_CRITICAL,
                category="LEGACY",
                exercise_id=result.exercise_id,
                description="Solution files don't work",
                fix_recommendation="Test solution files manually, check for missing variables or configuration",
                verification_steps=["1. Copy solution manually", "2. Run playbook", "3. Check for errors"],
            ))

        # P2: Instruction failures (commands fail)
        elif result.phase == "instructions" and result.steps_failed > 0:
            failed_steps = [s for s in result.steps_executed if s.result == StepResult.FAIL]
            for step in failed_steps[:3]:  # Report first 3 failures
                bug_id = f"{result.exercise_id}-P2-{len(bugs)+1:03d}"
                bugs.append(Bug(
                    id=bug_id,
                    severity=BugSeverity.P2_HIGH,
                    category="LEGACY",
                    exercise_id=result.exercise_id,
                    description=f"Instruction step failed: {step.text[:100]}",
                    fix_recommendation=f"Review command: {step.command}. Error: {(step.error or '')[:200]}",
                    verification_steps=["1. Test command manually", "2. Check prerequisites", "3. Verify expected output"],
                ))

        # P1: Grading validation failures (for Labs that completed successfully)
        if result.exercise_type == ExerciseType.LAB and result.phase == "complete":
            # Grading passed without solution (should fail)
            if result.grade_without_solution_passed:
                bugs.append(Bug(
                    id=f"{result.exercise_id}-P1-005",
                    severity=BugSeverity.P1_CRITICAL,
                    category="LEGACY",
                    exercise_id=result.exercise_id,
                    description="Grading passed without solution (should fail)",
                    fix_recommendation="Review grading script to ensure it validates student work, not just checks if files exist",
                    verification_steps=["1. Run 'lab grade' immediately after 'lab start'", "2. Should fail", "3. Fix grading logic"],
                ))
            # Grading failed with solution (should pass)
            if result.grade_with_solution_passed is False:
                bugs.append(Bug(
                    id=f"{result.exercise_id}-P1-006",
                    severity=BugSeverity.P1_CRITICAL,
                    category="LEGACY",
                    exercise_id=result.exercise_id,
                    description="Grading failed with solution (should pass)",
                    fix_recommendation="Review grading script validation logic, compare with solution files",
                    verification_steps=["1. Run solution manually", "2. Run 'lab grade'", "3. Should pass", "4. Fix grading logic"],
                ))

        return bugs

    def _detect_exercise_type(self, exercise_id: str) -> ExerciseType:
        """Detect exercise type by finding the exercise section in the EPUB.

        Exercises are identified by CSS class (sect2 ge / sect2 lab) and
        matched by 'lab start <exercise_id>' in the Prerequisites block.
        """
        extractor = InstructionExtractor(self.epub_path)
        try:
            extractor._extract_epub()
            for html_file in extractor.content_dir.glob("*.xhtml"):
                try:
                    with open(html_file, 'r', encoding='utf-8') as f:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(f, 'html.parser')
                    for section in soup.find_all('section'):
                        classes = section.get('class', [])
                        if not isinstance(classes, list):
                            classes = classes.split()
                        if 'sect2' not in classes:
                            continue
                        # Check if this section matches the exercise
                        for pre in section.find_all('pre'):
                            text = pre.get_text()
                            if re.search(
                                rf'lab start(?:\s+-t\s+[\w-]+)?\s+{re.escape(exercise_id)}\b',
                                text,
                            ):
                                if 'lab' in classes:
                                    return ExerciseType.LAB
                                return ExerciseType.GUIDED_EXERCISE
                except Exception:
                    continue
        finally:
            extractor.cleanup()
        return ExerciseType.GUIDED_EXERCISE

    def _execute_file_action(self, file_action: FileAction, current_dir: Optional[str],
                              indent: str) -> bool:
        """Write a file to the workstation or devcontainer."""
        filename = file_action.filename
        home_dir = self._devcontainer_workdir if self._devcontainer_active else "/home/student"

        # Resolve full path
        if filename.startswith('/'):
            full_path = filename
        elif current_dir:
            full_path = f"{current_dir}/{filename}"
        else:
            full_path = f"{home_dir}/{filename}"

        print(f"{indent}  [file] {filename} -> {full_path}")

        if self._devcontainer_active:
            result = self.ssh.write_file_in_devcontainer(
                full_path, file_action.content,
                container_name=self.CONTAINER_NAME,
                user=self._devcontainer_user,
            )
        else:
            result = self.ssh.write_file(full_path, file_action.content)

        if not result.success:
            print(f"{indent}    Error: {(result.stderr or result.stdout or 'unknown')[:100]}")
        return result.success

    def _run_command(self, command: str, timeout: int = 120):
        """Run command, routing through devcontainer if active."""
        if self._devcontainer_active:
            return self.ssh.run_in_devcontainer(
                command,
                container_name=self.CONTAINER_NAME,
                workdir=self._devcontainer_workdir,
                user=self._devcontainer_user,
                timeout=timeout,
            )
        return self.ssh.run(command, timeout=timeout)

    def _translate_for_devcontainer(self, cmd_text: str) -> str:
        """Translate commands for devcontainer execution.

        Inside the dev container, ansible-navigator would try to start a
        nested EE container (podman-in-podman) which fails without a TTY.
        Convert to ansible-playbook which runs directly in the dev container
        — it has ansible + all collections pre-installed.
        """
        cmd = cmd_text.strip()

        if not cmd.startswith('ansible-navigator'):
            return cmd_text

        # Parse the ansible-navigator command and convert to ansible-playbook
        # ansible-navigator run playbook.yml [opts] -> ansible-playbook playbook.yml [opts]
        nav_match = re.match(r'^ansible-navigator\s+run\s+(.+)$', cmd)
        if nav_match:
            rest = nav_match.group(1)
            # Remove navigator-specific flags that ansible-playbook doesn't understand
            rest = re.sub(r'-m\s+\S+', '', rest)        # --mode
            rest = re.sub(r'--mode\s+\S+', '', rest)
            rest = re.sub(r'--pp\s+\S+', '', rest)      # --pull-policy
            rest = re.sub(r'--eei\s+\S+', '', rest)     # --execution-environment-image
            rest = re.sub(r'--ce\s+\S+', '', rest)      # --container-engine
            rest = re.sub(r'\s+', ' ', rest).strip()
            return f"ansible-playbook {rest}"

        # For other navigator subcommands (doc, lint, etc.), try direct equivalents
        nav_doc = re.match(r'^ansible-navigator\s+doc\s+(.+)$', cmd)
        if nav_doc:
            return f"ansible-doc {nav_doc.group(1)}"

        nav_lint = re.match(r'^ansible-navigator\s+lint\s+(.+)$', cmd)
        if nav_lint:
            return f"ansible-lint {nav_lint.group(1)}"

        return cmd_text


def simulate_student(epub_path: Path, exercise_id: str,
                     workstation: str = "workstation") -> SimulationResult:
    """Convenience function to run student simulation."""
    simulator = StudentSimulator(epub_path, workstation)
    return simulator.run(exercise_id)
