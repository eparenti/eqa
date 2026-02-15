#!/usr/bin/env python3
"""
TC-SOL: Solution File Testing

Test ALL solution files systematically (guideline #6 - thoroughness).

For each .sol file:
1. Copy to exercise directory
2. Remove .sol extension
3. Execute solution
4. Validate success
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.ssh_connection import SSHConnection
from lib.test_result import TestResult, ExerciseContext, Bug, BugSeverity


class TC_SOL:
    """
    Test Category: Solution File Testing

    Tests ALL solution files for an exercise to ensure they work correctly.
    """

    def test(self, exercise: ExerciseContext, solution_files: List[Path],
             ssh: SSHConnection) -> TestResult:
        """
        Test all solution files for exercise.

        Args:
            exercise: Exercise context
            solution_files: List of solution file paths
            ssh: SSH connection to workstation

        Returns:
            TestResult with solution testing results
        """
        start_time = datetime.now()

        print(f"\n📁 Testing {len(solution_files)} solution files for {exercise.id}")

        if not solution_files:
            print("  ⚠️  No solution files found")
            end_time = datetime.now()
            return TestResult(
                category="TC-SOL",
                exercise_id=exercise.id,
                passed=True,
                timestamp=start_time.isoformat(),
                duration_seconds=(end_time - start_time).total_seconds(),
                details={
                    'total_solutions': 0,
                    'solutions_passed': 0,
                    'solutions_failed': 0,
                    'message': 'No solution files to test'
                }
            )

        # Determine exercise directory
        exercise_dir = f"~student/{exercise.lesson_code}/labs/{exercise.id}"

        # Ensure exercise is started
        print(f"  🚀 Running: lab start {exercise.id}")
        start_result = ssh.run(f"lab start {exercise.id}", timeout=300)

        if not start_result.success:
            print(f"  ❌ lab start failed: {start_result.stderr}")
            end_time = datetime.now()
            return TestResult(
                category="TC-SOL",
                exercise_id=exercise.id,
                passed=False,
                timestamp=start_time.isoformat(),
                duration_seconds=(end_time - start_time).total_seconds(),
                details={'error': 'lab start failed'},
                error_message=start_result.stderr
            )

        # Test each solution file
        solution_results = []
        bugs_found = []

        for i, sol_file in enumerate(solution_files, 1):
            print(f"\n  [{i}/{len(solution_files)}] Testing: {sol_file.name}")

            success, output, bug = self._test_single_solution(
                exercise, sol_file, exercise_dir, ssh
            )

            solution_results.append({
                'file': sol_file.name,
                'success': success,
                'output': output[:500] if output else None  # Truncate long output
            })

            if bug:
                bugs_found.append(bug)

            if success:
                print(f"      ✅ Solution works")
            else:
                print(f"      ❌ Solution failed")

        # Calculate pass rate
        passed_count = sum(1 for r in solution_results if r['success'])
        failed_count = len(solution_results) - passed_count
        all_passed = (failed_count == 0)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        if all_passed:
            print(f"\n✅ All {len(solution_files)} solutions PASSED")
        else:
            print(f"\n❌ {failed_count}/{len(solution_files)} solutions FAILED")

        return TestResult(
            category="TC-SOL",
            exercise_id=exercise.id,
            passed=all_passed,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            details={
                'total_solutions': len(solution_files),
                'solutions_passed': passed_count,
                'solutions_failed': failed_count,
                'solution_results': solution_results
            },
            bugs_found=bugs_found
        )

    def _test_single_solution(self, exercise: ExerciseContext, sol_file: Path,
                              exercise_dir: str, ssh: SSHConnection) -> Tuple[bool, str, Bug]:
        """
        Test a single solution file.

        Args:
            exercise: Exercise context
            sol_file: Solution file path
            exercise_dir: Exercise directory on remote system
            ssh: SSH connection

        Returns:
            Tuple of (success, output, bug_or_none)
        """
        # Determine target filename (remove .sol extension)
        # Handle both .yml.sol and .yaml.sol
        if sol_file.suffix == '.sol':
            target_name = sol_file.stem  # Removes .sol
        else:
            target_name = sol_file.name

        # Determine target path
        target_path = f"{exercise_dir}/{target_name}"

        # Copy solution file to remote system
        print(f"      - Copying to: {target_path}")
        copy_result = ssh.copy_file(sol_file, target_path)

        if not copy_result.success:
            bug = Bug(
                id=f"SOL-{exercise.id}-{sol_file.stem}",
                severity=BugSeverity.P1_CRITICAL,
                exercise_id=exercise.id,
                category="TC-SOL",
                description=f"Failed to copy solution file {sol_file.name}",
                fix_recommendation=f"Verify solution file exists and has correct permissions: {sol_file}",
                verification_steps=[
                    f"ls -la {sol_file}",
                    f"scp {sol_file} workstation:{target_path}"
                ]
            )
            return False, copy_result.stderr, bug

        # Determine execution method based on file type
        execute_cmd = self._determine_execution_command(sol_file, target_name, exercise_dir)

        if not execute_cmd:
            # Unknown file type, just verify copy succeeded
            return True, "Solution file copied (execution method unknown)", None

        # Execute solution
        print(f"      - Executing: {execute_cmd}")
        exec_result = ssh.run(execute_cmd, timeout=300)

        if exec_result.success:
            return True, exec_result.output, None
        else:
            bug = Bug(
                id=f"SOL-{exercise.id}-{sol_file.stem}-exec",
                severity=BugSeverity.P1_CRITICAL,
                exercise_id=exercise.id,
                category="TC-SOL",
                description=f"Solution file {sol_file.name} execution failed",
                fix_recommendation=f"Fix solution file: {sol_file}\n\n{exec_result.output}",
                verification_steps=[
                    f"ssh workstation",
                    f"cd {exercise_dir}",
                    f"{execute_cmd}",
                    "Verify execution succeeds"
                ]
            )
            return False, exec_result.output, bug

    def _determine_execution_command(self, sol_file: Path, target_name: str,
                                     exercise_dir: str) -> str:
        """
        Determine how to execute solution file based on type.

        Args:
            sol_file: Solution file path
            target_name: Target filename (without .sol)
            exercise_dir: Exercise directory

        Returns:
            Command to execute, or empty string if unknown
        """
        # Get the actual file extension (before .sol)
        if sol_file.name.endswith('.yml.sol') or sol_file.name.endswith('.yaml.sol'):
            # Ansible playbook
            return f"cd {exercise_dir} && ansible-navigator run {target_name} -m stdout"

        elif sol_file.name.endswith('.sh.sol'):
            # Shell script
            return f"cd {exercise_dir} && bash {target_name}"

        elif sol_file.name.endswith('.py.sol'):
            # Python script
            return f"cd {exercise_dir} && python3 {target_name}"

        elif sol_file.name.endswith('.conf.sol') or sol_file.name.endswith('.cfg.sol'):
            # Configuration file - just copy, no execution
            return ""

        else:
            # Unknown type
            return ""


def main():
    """Test TC_SOL functionality."""
    import argparse
    from lib.test_result import ExerciseType

    parser = argparse.ArgumentParser(description="Test exercise solution files")
    parser.add_argument("exercise_id", help="Exercise ID to test")
    parser.add_argument("--workstation", default="workstation", help="Workstation hostname")
    parser.add_argument("--lesson", default="<lesson-code>", help="Lesson code")
    parser.add_argument("--solutions", nargs='+', required=True, help="Paths to solution files")

    args = parser.parse_args()

    # Create minimal exercise context
    exercise = ExerciseContext(
        id=args.exercise_id,
        type=ExerciseType.GUIDED_EXERCISE,
        lesson_code=args.lesson,
        chapter=1,
        chapter_title="Test Chapter",
        title=f"Test: {args.exercise_id}"
    )

    # Convert solution paths
    solution_files = [Path(sol) for sol in args.solutions]

    # Create SSH connection
    ssh = SSHConnection(args.workstation)

    if not ssh.test_connection():
        print(f"❌ Cannot connect to {args.workstation}")
        return 1

    # Run solution test
    tester = TC_SOL()
    result = tester.test(exercise, solution_files, ssh)

    # Print results
    print("\n" + "=" * 60)
    print(f"Test Result: {'PASS' if result.passed else 'FAIL'}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Solutions Tested: {result.details['total_solutions']}")
    print(f"Solutions Passed: {result.details['solutions_passed']}")
    print(f"Solutions Failed: {result.details['solutions_failed']}")
    print(f"Bugs Found: {len(result.bugs_found)}")

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
