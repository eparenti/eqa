#!/usr/bin/env python3
"""
Test Execution Engine - Actually EXECUTES parsed EPUB workflows.

CRITICAL GAP FIX: parse_epub_workflow.py extracts steps but nothing executes them.
This module provides the execution capability for all test categories.
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.ssh_connection import SSHConnection, CommandResult
from lib.test_result import CourseContext, ExerciseContext, TestResult


@dataclass
class StepResult:
    """Result from executing a single workflow step."""
    step_number: int
    description: str
    commands_executed: List[str]
    success: bool
    output: str
    error_message: Optional[str] = None
    duration_seconds: float = 0.0


class TestExecutor:
    """
    Executes tests on live lab environment.

    Provides capability to:
    - Execute EPUB workflow steps
    - Run commands on remote systems
    - Validate outputs
    - Handle errors and retries
    """

    def __init__(self, workstation: str, course_context: Optional[CourseContext] = None,
                 username: str = "student"):
        """
        Initialize test executor.

        Args:
            workstation: Workstation hostname or IP
            course_context: Optional course context for enhanced validation
            username: SSH username (default: "student")
        """
        self.ssh = SSHConnection(workstation, username)
        self.context = course_context
        self.workstation = workstation

    def test_connection(self) -> bool:
        """
        Test SSH connectivity to lab environment.

        Returns:
            True if connected, False otherwise
        """
        return self.ssh.test_connection()

    def execute_workflow(self, exercise_id: str, workflow: Dict) -> TestResult:
        """
        Execute parsed EPUB workflow step-by-step.

        Args:
            exercise_id: Exercise identifier
            workflow: Workflow dictionary from parse_epub_workflow.py

        Returns:
            TestResult with execution results
        """
        start_time = datetime.now()
        step_results = []
        all_success = True

        total_steps = workflow.get('total_steps', len(workflow.get('steps', [])))

        print(f"\n🧪 Executing workflow for {exercise_id} ({total_steps} steps)")

        for step in workflow.get('steps', []):
            step_result = self.execute_step(step)
            step_results.append(step_result)

            if not step_result.success:
                all_success = False
                print(f"  ❌ Step {step_result.step_number}: {step_result.description}")
                if step_result.error_message:
                    print(f"     Error: {step_result.error_message}")
            else:
                print(f"  ✅ Step {step_result.step_number}: {step_result.description}")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        return TestResult(
            category="TC-WORKFLOW",
            exercise_id=exercise_id,
            passed=all_success,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            details={
                'total_steps': total_steps,
                'steps_passed': sum(1 for r in step_results if r.success),
                'steps_failed': sum(1 for r in step_results if not r.success),
                'step_results': [self._step_result_to_dict(r) for r in step_results]
            }
        )

    def execute_step(self, step: Dict) -> StepResult:
        """
        Execute single workflow step.

        Args:
            step: Step dictionary with commands and expected output

        Returns:
            StepResult with execution status
        """
        start_time = datetime.now()

        step_number = step.get('step_number', 0)
        description = step.get('description', 'Unknown step')
        commands = step.get('commands', [])
        expected_output = step.get('expected_output', '')

        if not commands:
            # No commands to execute, consider it successful
            return StepResult(
                step_number=step_number,
                description=description,
                commands_executed=[],
                success=True,
                output="No commands to execute",
                duration_seconds=0.0
            )

        # Execute each command
        all_outputs = []
        all_success = True
        error_message = None

        for cmd in commands:
            result = self.ssh.run(cmd)
            all_outputs.append(result.output)

            if not result.success:
                all_success = False
                error_message = f"Command failed: {cmd}\nReturn code: {result.return_code}\nOutput: {result.output}"
                break

        combined_output = '\n'.join(all_outputs)

        # Validate output if expected output provided
        if expected_output and all_success:
            if not self.validate_output(combined_output, expected_output):
                all_success = False
                error_message = f"Output validation failed. Expected pattern: {expected_output[:100]}"

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        return StepResult(
            step_number=step_number,
            description=description,
            commands_executed=commands,
            success=all_success,
            output=combined_output,
            error_message=error_message,
            duration_seconds=duration
        )

    def validate_output(self, actual: str, expected: str) -> bool:
        """
        Validate actual output matches expected output.

        Args:
            actual: Actual command output
            expected: Expected output pattern

        Returns:
            True if output matches, False otherwise
        """
        # Simple substring match for now
        # Could be enhanced with regex patterns
        if not expected:
            return True

        return expected.lower() in actual.lower()

    def run_lab_command(self, command: str, exercise_id: str) -> CommandResult:
        """
        Run lab command (lab start, lab finish, lab grade).

        Args:
            command: Lab command to run
            exercise_id: Exercise identifier

        Returns:
            CommandResult
        """
        full_command = f"{command} {exercise_id}"
        return self.ssh.run(full_command, timeout=300)

    def test_prerequisites(self, exercise: ExerciseContext) -> TestResult:
        """
        Test that prerequisites are met for exercise.

        Args:
            exercise: Exercise context

        Returns:
            TestResult for prerequisite check
        """
        start_time = datetime.now()

        # Run lab start
        result = self.run_lab_command("lab start", exercise.id)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        return TestResult(
            category="TC-PREREQ",
            exercise_id=exercise.id,
            passed=result.success,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            details={
                'command': f"lab start {exercise.id}",
                'return_code': result.return_code,
                'output': result.output
            },
            error_message=result.stderr if not result.success else None
        )

    def test_cleanup(self, exercise: ExerciseContext) -> TestResult:
        """
        Test cleanup with lab finish.

        Args:
            exercise: Exercise context

        Returns:
            TestResult for cleanup check
        """
        start_time = datetime.now()

        # Run lab finish
        result = self.run_lab_command("lab finish", exercise.id)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        return TestResult(
            category="TC-CLEAN",
            exercise_id=exercise.id,
            passed=result.success,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            details={
                'command': f"lab finish {exercise.id}",
                'return_code': result.return_code,
                'output': result.output
            },
            error_message=result.stderr if not result.success else None
        )

    def test_solution_file(self, exercise: ExerciseContext, solution_file: Path) -> Tuple[bool, str]:
        """
        Test a single solution file.

        Args:
            exercise: Exercise context
            solution_file: Path to solution file

        Returns:
            Tuple of (success, output_message)
        """
        # Determine target filename (remove .sol extension)
        target_name = solution_file.stem  # Removes last extension

        # Determine exercise directory
        exercise_dir = f"~student/{exercise.lesson_code}/labs/{exercise.id}"

        # Copy solution file to exercise directory
        target_path = f"{exercise_dir}/{target_name}"

        # First, copy file to remote
        copy_result = self.ssh.copy_file(solution_file, target_path)
        if not copy_result.success:
            return False, f"Failed to copy solution file: {copy_result.stderr}"

        # Determine how to execute based on file type
        if solution_file.suffix in ['.yml', '.yaml']:
            # Ansible playbook
            cmd = f"cd {exercise_dir} && ansible-navigator run {target_name} -m stdout"
        elif solution_file.suffix == '.sh':
            # Shell script
            cmd = f"cd {exercise_dir} && bash {target_name}"
        else:
            # Unknown type, just verify it copied
            return True, "Solution file copied successfully"

        # Execute solution
        exec_result = self.ssh.run(cmd, timeout=300)

        if exec_result.success:
            return True, f"Solution executed successfully:\n{exec_result.output}"
        else:
            return False, f"Solution execution failed:\n{exec_result.output}"

    def _step_result_to_dict(self, step_result: StepResult) -> Dict:
        """Convert StepResult to dictionary."""
        return {
            'step_number': step_result.step_number,
            'description': step_result.description,
            'commands_executed': step_result.commands_executed,
            'success': step_result.success,
            'output': step_result.output[:500] if step_result.output else None,  # Truncate long output
            'error_message': step_result.error_message,
            'duration_seconds': step_result.duration_seconds
        }


def main():
    """Test executor functionality."""
    import argparse

    parser = argparse.ArgumentParser(description="Execute exercise workflow on lab environment")
    parser.add_argument("workstation", help="Workstation hostname or IP")
    parser.add_argument("--exercise", "-e", required=True, help="Exercise ID")
    parser.add_argument("--workflow", "-w", help="Path to workflow JSON file")
    parser.add_argument("--test-connection", action="store_true", help="Only test connection")

    args = parser.parse_args()

    executor = TestExecutor(args.workstation)

    # Test connection
    print(f"Testing connection to {args.workstation}...")
    if not executor.test_connection():
        print("❌ Cannot connect to workstation")
        return 1

    print("✅ Connected to workstation")

    if args.test_connection:
        return 0

    # Execute workflow if provided
    if args.workflow:
        import json
        workflow_path = Path(args.workflow)

        if not workflow_path.exists():
            print(f"❌ Workflow file not found: {workflow_path}")
            return 1

        with open(workflow_path, 'r') as f:
            workflow = json.load(f)

        print(f"\nExecuting workflow for {args.exercise}...")
        result = executor.execute_workflow(args.exercise, workflow)

        print("\n" + "=" * 60)
        print(f"Result: {'PASS' if result.passed else 'FAIL'}")
        print(f"Duration: {result.duration_seconds:.2f}s")
        print(f"Steps: {result.details['steps_passed']}/{result.details['total_steps']} passed")

        return 0 if result.passed else 1

    else:
        print("No workflow file specified. Use --workflow to provide workflow JSON.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
