#!/usr/bin/env python3
"""
TC-SOLVE: Solve Playbook Testing

Tests solve.yml playbooks that automatically complete exercises.

Many courses use solve.yml playbooks instead of or in addition to .sol files.
This test category validates that solve playbooks work correctly.
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.test_result import TestResult, Bug, BugSeverity, ExerciseContext
from lib.ssh_connection import SSHConnection


class TC_SOLVE:
    """
    Solve playbook testing.

    Tests that solve.yml playbooks automatically complete exercises correctly.
    """

    def __init__(self):
        """Initialize solve playbook tester."""
        pass

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test solve playbook.

        Args:
            exercise: Exercise context
            ssh: SSH connection to workstation

        Returns:
            TestResult with solve playbook test results
        """
        start_time = datetime.now()
        bugs_found = []
        test_details = {
            'solve_playbook_found': False,
            'solve_playbook_path': None,
            'execution_successful': False,
            'grading_after_solve': None
        }

        print(f"\n🔧 TC-SOLVE: Solve Playbook Testing")
        print("=" * 60)

        # Find solve playbook
        solve_playbook = self._find_solve_playbook(exercise, ssh)

        if not solve_playbook:
            print("  ⏭️  No solve playbook found (this is OK)")
            return TestResult(
                category="TC-SOLVE",
                exercise_id=exercise.id,
                passed=True,
                timestamp=start_time.isoformat(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                bugs_found=[],
                details={'skipped': True, 'reason': 'No solve playbook found'},
                summary="Skipped: No solve playbook"
            )

        test_details['solve_playbook_found'] = True
        test_details['solve_playbook_path'] = solve_playbook
        print(f"  Found solve playbook: {solve_playbook}")

        # Reset exercise first
        print("\n  Resetting exercise before solve...")
        ssh.run(f"cd ~ && lab finish {exercise.id}", timeout=300)
        ssh.run(f"cd ~ && lab start {exercise.id}", timeout=600)

        # Execute solve playbook
        print(f"\n  Running solve playbook...")

        # Determine execution method
        if solve_playbook.endswith('.yml') or solve_playbook.endswith('.yaml'):
            # Ansible playbook - check if we need ansible-navigator or ansible-playbook
            nav_config_check = ssh.run(
                f"ls ~/DO{exercise.lesson_code.upper()}/labs/{exercise.id}/ansible-navigator.yml 2>/dev/null",
                timeout=5
            )

            if nav_config_check['exit_code'] == 0:
                # Use ansible-navigator
                cmd = f"cd ~/DO{exercise.lesson_code.upper()}/labs/{exercise.id}/ && ansible-navigator run {solve_playbook} -m stdout"
            else:
                # Use ansible-playbook
                cmd = f"cd ~/DO{exercise.lesson_code.upper()}/labs/{exercise.id}/ && ansible-playbook {solve_playbook}"

            result = ssh.run(cmd, timeout=600)

            if result['exit_code'] != 0:
                bugs_found.append(Bug(
                    id=f"BUG-{exercise.id.upper()}-SOLVE-FAILED",
                    severity=BugSeverity.P1_CRITICAL,
                    exercise_id=exercise.id,
                    category="TC-SOLVE",
                    description=f"Solve playbook failed to execute: {solve_playbook}",
                    fix_recommendation=(
                        f"Fix solve playbook:\n\n"
                        f"Playbook: {solve_playbook}\n"
                        f"Error: {result['stderr']}\n\n"
                        f"The solve playbook should complete the exercise successfully.\n"
                        f"Review the playbook for errors and test it manually."
                    ),
                    verification_steps=[
                        f"1. Review {solve_playbook}",
                        "2. Fix playbook errors",
                        "3. lab start",
                        f"4. Run: {cmd}",
                        "5. Verify playbook succeeds"
                    ]
                ))
                print(f"    ❌ Solve playbook failed")
                print(f"       Error: {result['stderr'][:200]}")
            else:
                test_details['execution_successful'] = True
                print("    ✅ Solve playbook executed successfully")

        # If it's a Lab, test grading after solve
        if exercise.type.value == "Lab" and test_details['execution_successful']:
            print("\n  Testing grading after solve...")

            grade_result = ssh.run(f"cd ~ && lab grade {exercise.id}", timeout=300)

            if grade_result['exit_code'] != 0:
                bugs_found.append(Bug(
                    id=f"BUG-{exercise.id.upper()}-SOLVE-NO-PASS",
                    severity=BugSeverity.P1_CRITICAL,
                    exercise_id=exercise.id,
                    category="TC-SOLVE",
                    description="Grading failed after solve playbook completed",
                    fix_recommendation=(
                        "Fix solve playbook to complete all required tasks:\n\n"
                        f"The solve playbook completed without errors, but grading failed.\n"
                        f"This means the solve playbook is not completing all tasks.\n\n"
                        f"Grading output:\n{grade_result['stdout'][:500]}\n\n"
                        "Update solve playbook to complete all grading requirements."
                    ),
                    verification_steps=[
                        "1. lab start",
                        "2. Run solve playbook",
                        "3. lab grade",
                        "4. Verify 100/100",
                        "5. Update solve playbook if needed"
                    ]
                ))
                print("    ❌ Grading failed after solve")
            else:
                # Check if it actually passed (100%)
                if 'PASS' in grade_result['stdout'] or '100' in grade_result['stdout']:
                    test_details['grading_after_solve'] = 'PASS'
                    print("    ✅ Grading passed after solve")
                else:
                    test_details['grading_after_solve'] = 'PARTIAL'
                    bugs_found.append(Bug(
                        id=f"BUG-{exercise.id.upper()}-SOLVE-PARTIAL",
                        severity=BugSeverity.P2_HIGH,
                        exercise_id=exercise.id,
                        category="TC-SOLVE",
                        description="Solve playbook completed but did not achieve 100%",
                        fix_recommendation=(
                            "Update solve playbook to complete all tasks:\n\n"
                            f"Grading output:\n{grade_result['stdout']}\n\n"
                            "The solve playbook should complete ALL tasks to get 100%."
                        ),
                        verification_steps=[
                            "1. Review grading output",
                            "2. Identify incomplete tasks",
                            "3. Update solve playbook",
                            "4. Test again"
                        ]
                    ))
                    print("    ⚠️  Grading passed but not 100%")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        passed = len(bugs_found) == 0

        return TestResult(
            category="TC-SOLVE",
            exercise_id=exercise.id,
            passed=passed,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details=test_details,
            summary=f"Solve playbook {'passed' if passed else 'failed'} - {len(bugs_found)} issues found"
        )

    def _find_solve_playbook(self, exercise: ExerciseContext,
                            ssh: SSHConnection) -> str:
        """
        Find solve playbook for exercise.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            Path to solve playbook or None
        """
        # Common locations for solve playbooks
        possible_locations = [
            f"~/DO{exercise.lesson_code.upper()}/labs/{exercise.id}/solve.yml",
            f"~/DO{exercise.lesson_code.upper()}/solutions/{exercise.id}/solve.yml",
            f"solve.yml",  # Relative to exercise dir
            f"../solutions/{exercise.id}/solve.yml"
        ]

        for location in possible_locations:
            result = ssh.run(f"ls {location} 2>/dev/null", timeout=5)
            if result['exit_code'] == 0:
                return location

        # Also check in grading directory (like <NETWORK-COURSE>)
        grading_solve = f"/home/student/DO{exercise.lesson_code.upper()}/grading/ansible/{exercise.id}/solve.yml"
        result = ssh.run(f"ls {grading_solve} 2>/dev/null", timeout=5)
        if result['exit_code'] == 0:
            return grading_solve

        return None


def main():
    """Test TC_SOLVE functionality."""
    import argparse

    parser = argparse.ArgumentParser(description="Test TC-SOLVE category")
    parser.add_argument("exercise_id", help="Exercise ID to test")
    parser.add_argument("--workstation", default="workstation", help="Workstation hostname")
    parser.add_argument("--lesson-code", help="Lesson code")

    args = parser.parse_args()

    # Create minimal exercise context
    from lib.test_result import ExerciseContext, ExerciseType
    exercise = ExerciseContext(
        id=args.exercise_id,
        type=ExerciseType.LAB,
        lesson_code=args.lesson_code or "",
        chapter=1,
        chapter_title="Chapter",
        title=args.exercise_id
    )

    # Create SSH connection
    ssh = SSHConnection(args.workstation)

    if not ssh.test_connection():
        print(f"Cannot connect to {args.workstation}")
        return 1

    # Run test
    tester = TC_SOLVE()
    result = tester.test(exercise, ssh)

    # Print results
    print("\n" + "=" * 60)
    print(f"Result: {'PASS' if result.passed else 'FAIL'}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Bugs Found: {len(result.bugs_found)}")
    print("=" * 60)

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
