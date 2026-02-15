#!/usr/bin/env python3
"""
TC-CLEAN: Cleanup Validation

Tests that `lab finish <exercise>` properly cleans up all artifacts:
- Files removed from exercise directory
- Solution files removed
- Resources cleaned up (users, services, containers, etc.)
- System returned to baseline state

This ensures students can practice exercises repeatedly.
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.test_result import TestResult, Bug, BugSeverity, ExerciseContext
from lib.ssh_connection import SSHConnection
from lib.state_capture import capture_system_state, compare_states


class TC_CLEAN:
    """
    Cleanup validation.

    Tests that lab finish properly cleans up all artifacts.
    """

    def __init__(self):
        """Initialize cleanup tester."""
        pass

    def test(self, exercise: ExerciseContext, ssh: SSHConnection,
             initial_state: Dict = None) -> TestResult:
        """
        Test cleanup.

        Args:
            exercise: Exercise context
            ssh: SSH connection to workstation
            initial_state: Optional initial system state (before lab start)

        Returns:
            TestResult with cleanup test results
        """
        start_time = datetime.now()
        bugs_found = []
        test_details = {
            'lab_finish_success': False,
            'exercise_dir_removed': False,
            'solutions_dir_removed': False,
            'artifacts_remaining': [],
            'state_comparison': {}
        }

        print(f"\n🧹 TC-CLEAN: Cleanup Validation")
        print("=" * 60)

        # Capture state before cleanup (after exercise completion)
        print("\n  1. Capturing pre-cleanup state...")
        pre_cleanup_state = capture_system_state(ssh, exercise.id)
        print("     ✅ State captured")

        # Run lab finish
        print(f"\n  2. Running: lab finish {exercise.id}")
        finish_result = ssh.run(f"cd ~ && lab finish {exercise.id}", timeout=600)

        if finish_result['exit_code'] != 0:
            bugs_found.append(Bug(
                id=f"BUG-{exercise.id.upper()}-FINISH-FAIL",
                severity=BugSeverity.P1_CRITICAL,
                exercise_id=exercise.id,
                category="TC-CLEAN",
                description=f"`lab finish {exercise.id}` failed",
                fix_recommendation=(
                    f"Fix lab finish:\n\n"
                    f"Error output:\n{finish_result['stderr']}\n\n"
                    "Review grading script finish.yml for errors:\n"
                    "1. Check for syntax errors\n"
                    "2. Verify cleanup tasks are correct\n"
                    "3. Test finish playbook manually"
                ),
                verification_steps=[
                    "1. Review finish.yml",
                    "2. Fix identified errors",
                    f"3. Run: lab finish {exercise.id}",
                    "4. Verify success"
                ]
            ))
            print(f"     ❌ lab finish failed")
            print(f"        Error: {finish_result['stderr'][:200]}")

            # Continue to check what was cleaned up
        else:
            test_details['lab_finish_success'] = True
            print("     ✅ lab finish succeeded")

        # Check exercise directory removed
        print("\n  3. Checking exercise directory cleanup...")
        exercise_dir = f"~/DO{exercise.lesson_code.upper()}/labs/{exercise.id}/"
        ls_result = ssh.run(f"ls {exercise_dir} 2>&1", timeout=5)

        if ls_result['exit_code'] == 0 and 'No such file' not in ls_result['stdout']:
            # Directory still exists
            bugs_found.append(Bug(
                id=f"BUG-{exercise.id.upper()}-DIR-NOT-REMOVED",
                severity=BugSeverity.P1_CRITICAL,
                exercise_id=exercise.id,
                category="TC-CLEAN",
                description=f"Exercise directory not removed: {exercise_dir}",
                fix_recommendation=(
                    f"Fix directory cleanup in finish.yml:\n\n"
                    f"Add task to remove exercise directory:\n"
                    f"```yaml\n"
                    f"- name: Remove exercise directory\n"
                    f"  file:\n"
                    f"    path: {exercise_dir}\n"
                    f"    state: absent\n"
                    f"```"
                ),
                verification_steps=[
                    "1. Update finish.yml with directory cleanup",
                    f"2. Run: lab finish {exercise.id}",
                    f"3. Verify: ls {exercise_dir} fails",
                    "4. Re-test cleanup"
                ]
            ))
            print(f"     ❌ Directory still exists: {exercise_dir}")

            # List remaining files
            find_result = ssh.run(f"find {exercise_dir} -type f", timeout=10)
            if find_result['stdout'].strip():
                remaining_files = find_result['stdout'].strip().split('\n')
                test_details['artifacts_remaining'].extend(remaining_files[:10])  # First 10
                print(f"        {len(remaining_files)} files remaining")
        else:
            test_details['exercise_dir_removed'] = True
            print("     ✅ Exercise directory removed")

        # Check solutions directory removed
        print("\n  4. Checking solutions directory cleanup...")
        solutions_dir = f"~/DO{exercise.lesson_code.upper()}/solutions/{exercise.id}/"
        ls_result = ssh.run(f"ls {solutions_dir} 2>&1", timeout=5)

        if ls_result['exit_code'] == 0 and 'No such file' not in ls_result['stdout']:
            bugs_found.append(Bug(
                id=f"BUG-{exercise.id.upper()}-SOL-NOT-REMOVED",
                severity=BugSeverity.P2_HIGH,
                exercise_id=exercise.id,
                category="TC-CLEAN",
                description=f"Solutions directory not removed: {solutions_dir}",
                fix_recommendation=(
                    f"Fix solutions cleanup in finish.yml:\n\n"
                    f"Add task to remove solutions directory:\n"
                    f"```yaml\n"
                    f"- name: Remove solutions directory\n"
                    f"  file:\n"
                    f"    path: {solutions_dir}\n"
                    f"    state: absent\n"
                    f"```"
                ),
                verification_steps=[
                    "1. Update finish.yml with solutions cleanup",
                    f"2. Run: lab finish {exercise.id}",
                    f"3. Verify: ls {solutions_dir} fails",
                    "4. Re-test cleanup"
                ]
            ))
            print(f"     ❌ Solutions directory still exists")
        else:
            test_details['solutions_dir_removed'] = True
            print("     ✅ Solutions directory removed")

        # Capture state after cleanup
        print("\n  5. Capturing post-cleanup state...")
        post_cleanup_state = capture_system_state(ssh, exercise.id)
        print("     ✅ State captured")

        # Compare states if initial state provided
        if initial_state:
            print("\n  6. Comparing with initial state...")
            comparison = compare_states(initial_state, post_cleanup_state)
            test_details['state_comparison'] = comparison

            # Check for differences
            differences_found = False

            if comparison['users']['added']:
                differences_found = True
                users = ', '.join(comparison['users']['added'])
                bugs_found.append(Bug(
                    id=f"BUG-{exercise.id.upper()}-USERS-NOT-REMOVED",
                    severity=BugSeverity.P1_CRITICAL,
                    exercise_id=exercise.id,
                    category="TC-CLEAN",
                    description=f"Users not removed: {users}",
                    fix_recommendation=(
                        f"Fix user cleanup in finish.yml:\n\n"
                        f"Add tasks to remove users:\n"
                        f"```yaml\n"
                        f"- name: Remove exercise users\n"
                        f"  user:\n"
                        f"    name: '{{{{ item }}}}'\n"
                        f"    state: absent\n"
                        f"    remove: yes\n"
                        f"  loop:\n"
                        f"{chr(10).join('    - ' + u for u in comparison['users']['added'][:5])}\n"
                        f"  failed_when: false\n"
                        f"```"
                    ),
                    verification_steps=[
                        "1. Update finish.yml with user cleanup",
                        f"2. Run: lab finish {exercise.id}",
                        "3. Verify users removed",
                        "4. Re-test cleanup"
                    ]
                ))
                print(f"     ❌ Users not removed: {users}")

            if comparison['services']['added']:
                differences_found = True
                services = ', '.join(comparison['services']['added'])
                bugs_found.append(Bug(
                    id=f"BUG-{exercise.id.upper()}-SERVICES-NOT-STOPPED",
                    severity=BugSeverity.P1_CRITICAL,
                    exercise_id=exercise.id,
                    category="TC-CLEAN",
                    description=f"Services not stopped: {services}",
                    fix_recommendation=(
                        f"Fix service cleanup in finish.yml:\n\n"
                        f"Add tasks to stop and disable services:\n"
                        f"```yaml\n"
                        f"- name: Stop and disable exercise services\n"
                        f"  systemd:\n"
                        f"    name: '{{{{ item }}}}'\n"
                        f"    state: stopped\n"
                        f"    enabled: no\n"
                        f"  loop:\n"
                        f"{chr(10).join('    - ' + s for s in comparison['services']['added'][:5])}\n"
                        f"  failed_when: false\n"
                        f"```"
                    ),
                    verification_steps=[
                        "1. Update finish.yml with service cleanup",
                        f"2. Run: lab finish {exercise.id}",
                        "3. Verify services stopped",
                        "4. Re-test cleanup"
                    ]
                ))
                print(f"     ❌ Services not stopped: {services}")

            if comparison['packages']['added']:
                print(f"     ⚠️  Packages added: {', '.join(comparison['packages']['added'][:5])}")
                print("        (Package removal usually not required)")

            if not differences_found:
                print("     ✅ System state matches initial state")
        else:
            print("     ⏭️  Skipping state comparison (no initial state)")

        return self._build_result(start_time, exercise, bugs_found, test_details)

    def _build_result(self, start_time: datetime, exercise: ExerciseContext,
                     bugs_found: List[Bug], test_details: Dict) -> TestResult:
        """Build test result."""
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        passed = len(bugs_found) == 0

        return TestResult(
            category="TC-CLEAN",
            exercise_id=exercise.id,
            passed=passed,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details=test_details,
            summary=f"Cleanup {'passed' if passed else 'failed'} - {len(bugs_found)} issues found"
        )


def main():
    """Test TC_CLEAN functionality."""
    import argparse

    parser = argparse.ArgumentParser(description="Test TC-CLEAN category")
    parser.add_argument("exercise_id", help="Exercise ID to test")
    parser.add_argument("--workstation", default="workstation", help="Workstation hostname")
    parser.add_argument("--lesson-code", help="Lesson code")

    args = parser.parse_args()

    # Create minimal exercise context
    from lib.test_result import ExerciseContext, ExerciseType
    exercise = ExerciseContext(
        id=args.exercise_id,
        type=ExerciseType.UNKNOWN,
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

    # Capture initial state
    print("Capturing initial state...")
    initial_state = capture_system_state(ssh, exercise.id)

    # Run test
    tester = TC_CLEAN()
    result = tester.test(exercise, ssh, initial_state)

    # Print results
    print("\n" + "=" * 60)
    print(f"Result: {'PASS' if result.passed else 'FAIL'}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Bugs Found: {len(result.bugs_found)}")
    print("=" * 60)

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
