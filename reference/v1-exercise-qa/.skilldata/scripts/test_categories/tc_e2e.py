#!/usr/bin/env python3
"""
TC-E2E: End-to-End Testing Suite

Validates exercise independence and cleanup (guideline #5).

Test Categories:
- TC-E2E-CLEAN: Each exercise starts with clean state
- TC-E2E-ISOLATION: Exercise works without prerequisites
- TC-E2E-SEQUENCE: All exercises work sequentially
- TC-E2E-LEAKAGE: No artifacts leak between exercises
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.ssh_connection import SSHConnection
from lib.state_capture import SystemState, capture_system_state, compare_states, format_diff_report
from lib.test_result import TestResult, ExerciseContext, Bug, BugSeverity


class TC_E2E:
    """
    Test Category: End-to-End Testing

    Validates that exercises can be completed sequentially without interference.
    """

    def test_clean(self, exercise: ExerciseContext, previous_exercise: ExerciseContext,
                   ssh: SSHConnection) -> TestResult:
        """
        TC-E2E-CLEAN: Validate clean starting state after previous exercise.

        Args:
            exercise: Current exercise
            previous_exercise: Previous exercise
            ssh: SSH connection

        Returns:
            TestResult for clean state validation
        """
        start_time = datetime.now()

        print(f"\n🧹 Testing clean state: {previous_exercise.id} → {exercise.id}")

        bugs_found = []

        # Finish previous exercise
        print(f"  - Finishing previous: lab finish {previous_exercise.id}")
        finish_result = ssh.run(f"lab finish {previous_exercise.id}", timeout=300)

        if not finish_result.success:
            print(f"  ⚠️  Previous lab finish had errors: {finish_result.stderr}")

        # Capture state after previous finish
        print(f"  - Capturing state after previous finish...")
        state_after_previous = capture_system_state(ssh, exercise_id=previous_exercise.id)

        # Start current exercise
        print(f"  - Starting current: lab start {exercise.id}")
        start_result = ssh.run(f"lab start {exercise.id}", timeout=300)

        if not start_result.success:
            bug = Bug(
                id=f"E2E-CLEAN-{exercise.id}-001",
                severity=BugSeverity.P0_BLOCKER,
                exercise_id=exercise.id,
                category="TC-E2E-CLEAN",
                description=f"lab start failed after {previous_exercise.id} cleanup",
                fix_recommendation=f"Fix cleanup in {previous_exercise.id} or setup in {exercise.id}",
                verification_steps=[
                    f"lab finish {previous_exercise.id}",
                    f"lab start {exercise.id}",
                    "Verify no errors"
                ]
            )
            bugs_found.append(bug)

        # Capture state after current start
        print(f"  - Capturing state after current start...")
        state_after_current = capture_system_state(ssh, exercise_id=exercise.id)

        # Look for artifacts from previous exercise
        # We expect current state to be a superset of previous state
        # (current exercise may create new things, but nothing from previous should remain)
        diff = compare_states(state_after_previous, state_after_current)

        # Check if any users/groups/containers from previous exercise leaked through
        leaked_artifacts = self._detect_leaked_artifacts(previous_exercise, exercise, diff)

        if leaked_artifacts:
            print(f"  ❌ Artifacts from {previous_exercise.id} leaked into {exercise.id}")
            bug = Bug(
                id=f"E2E-CLEAN-{exercise.id}-002",
                severity=BugSeverity.P1_CRITICAL,
                exercise_id=previous_exercise.id,
                category="TC-E2E-CLEAN",
                description=f"Incomplete cleanup - artifacts leaked to {exercise.id}",
                fix_recommendation=f"Update finish.yml for {previous_exercise.id}:\n{leaked_artifacts}",
                verification_steps=[
                    f"lab finish {previous_exercise.id}",
                    "Verify all artifacts removed",
                    f"lab start {exercise.id}",
                    "Verify clean state"
                ]
            )
            bugs_found.append(bug)
        else:
            print(f"  ✅ Clean state confirmed")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        passed = (len(bugs_found) == 0)

        return TestResult(
            category="TC-E2E-CLEAN",
            exercise_id=exercise.id,
            passed=passed,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            details={
                'previous_exercise': previous_exercise.id,
                'leaked_artifacts': leaked_artifacts if leaked_artifacts else None
            },
            bugs_found=bugs_found
        )

    def test_isolation(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        TC-E2E-ISOLATION: Test that exercise works without any prerequisites.

        Args:
            exercise: Exercise to test
            ssh: SSH connection

        Returns:
            TestResult for isolation validation
        """
        start_time = datetime.now()

        print(f"\n🔒 Testing isolation: {exercise.id}")

        bugs_found = []

        # Force clean state by finishing all exercises in lesson
        print(f"  - Forcing clean state: lab finish {exercise.lesson_code}")
        ssh.run(f"lab finish {exercise.lesson_code}", timeout=300)

        # Start exercise
        print(f"  - Starting in isolation: lab start {exercise.id}")
        start_result = ssh.run(f"lab start {exercise.id}", timeout=300)

        if not start_result.success:
            bug = Bug(
                id=f"E2E-ISO-{exercise.id}-001",
                severity=BugSeverity.P0_BLOCKER,
                exercise_id=exercise.id,
                category="TC-E2E-ISOLATION",
                description="Exercise cannot start in isolation (may depend on previous exercises)",
                fix_recommendation=f"Ensure {exercise.id} creates all required resources in start.yml",
                verification_steps=[
                    f"lab finish {exercise.lesson_code}",
                    f"lab start {exercise.id}",
                    "Verify exercise starts successfully"
                ]
            )
            bugs_found.append(bug)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        passed = (len(bugs_found) == 0)

        if passed:
            print(f"  ✅ Exercise is independent")
        else:
            print(f"  ❌ Exercise depends on previous exercises")

        return TestResult(
            category="TC-E2E-ISOLATION",
            exercise_id=exercise.id,
            passed=passed,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            details={'can_run_isolated': passed},
            bugs_found=bugs_found
        )

    def test_sequence(self, exercises: List[ExerciseContext], ssh: SSHConnection) -> TestResult:
        """
        TC-E2E-SEQUENCE: Test all exercises work sequentially.

        Args:
            exercises: List of exercises to test in sequence
            ssh: SSH connection

        Returns:
            TestResult for sequential workflow validation
        """
        start_time = datetime.now()

        print(f"\n📋 Testing sequential workflow: {len(exercises)} exercises")

        bugs_found = []
        exercise_results = []

        for i, exercise in enumerate(exercises, 1):
            print(f"\n  [{i}/{len(exercises)}] {exercise.id}")

            # Start exercise
            start_result = ssh.run(f"lab start {exercise.id}", timeout=300)

            success = start_result.success

            if not success:
                bug = Bug(
                    id=f"E2E-SEQ-{exercise.id}-{i:03d}",
                    severity=BugSeverity.P1_CRITICAL,
                    exercise_id=exercise.id,
                    category="TC-E2E-SEQUENCE",
                    description=f"Exercise {i} failed in sequence",
                    fix_recommendation=f"Fix lab start for {exercise.id}",
                    verification_steps=[
                        f"Run exercises 1-{i-1} in sequence",
                        f"lab start {exercise.id}",
                        "Verify success"
                    ]
                )
                bugs_found.append(bug)
                print(f"    ❌ Failed to start")
            else:
                print(f"    ✅ Started successfully")

            # Finish exercise
            finish_result = ssh.run(f"lab finish {exercise.id}", timeout=300)

            if not finish_result.success:
                print(f"    ⚠️  Cleanup had errors")

            exercise_results.append({
                'exercise_id': exercise.id,
                'position': i,
                'success': success
            })

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        passed_count = sum(1 for r in exercise_results if r['success'])
        all_passed = (passed_count == len(exercises))

        if all_passed:
            print(f"\n✅ All {len(exercises)} exercises passed in sequence")
        else:
            print(f"\n❌ {len(exercises) - passed_count}/{len(exercises)} exercises failed")

        return TestResult(
            category="TC-E2E-SEQUENCE",
            exercise_id=f"chapter-{exercises[0].chapter}" if exercises else "unknown",
            passed=all_passed,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            details={
                'total_exercises': len(exercises),
                'exercises_passed': passed_count,
                'exercises_failed': len(exercises) - passed_count,
                'exercise_results': exercise_results
            },
            bugs_found=bugs_found
        )

    def _detect_leaked_artifacts(self, previous_ex: ExerciseContext,
                                 current_ex: ExerciseContext, diff) -> str:
        """
        Detect artifacts that leaked from previous exercise.

        Args:
            previous_ex: Previous exercise
            current_ex: Current exercise
            diff: State difference

        Returns:
            Description of leaked artifacts or empty string
        """
        # This is a simplified implementation
        # In production, would analyze exercise context to know what artifacts to expect

        leaked = []

        if diff.users_removed:
            leaked.append(f"Users not cleaned up from {previous_ex.id}:")
            for user in sorted(diff.users_removed):
                leaked.append(f"  - {user}")

        if diff.groups_removed:
            leaked.append(f"Groups not cleaned up from {previous_ex.id}:")
            for group in sorted(diff.groups_removed):
                leaked.append(f"  - {group}")

        if diff.containers_removed:
            leaked.append(f"Containers not cleaned up from {previous_ex.id}:")
            for container in sorted(diff.containers_removed):
                leaked.append(f"  - {container}")

        return "\n".join(leaked) if leaked else ""


def main():
    """Test TC_E2E functionality."""
    import argparse
    from lib.test_result import ExerciseType

    parser = argparse.ArgumentParser(description="Test end-to-end exercise sequence")
    parser.add_argument("--workstation", default="workstation", help="Workstation hostname")
    parser.add_argument("--test", choices=['clean', 'isolation', 'sequence'], required=True,
                       help="E2E test type")
    parser.add_argument("--exercises", nargs='+', required=True, help="Exercise IDs")
    parser.add_argument("--lesson", default="<lesson-code>", help="Lesson code")

    args = parser.parse_args()

    # Create exercise contexts
    exercises = [
        ExerciseContext(
            id=ex_id,
            type=ExerciseType.GUIDED_EXERCISE,
            lesson_code=args.lesson,
            chapter=1,
            chapter_title="Test Chapter",
            title=f"Test: {ex_id}"
        )
        for ex_id in args.exercises
    ]

    # Create SSH connection
    ssh = SSHConnection(args.workstation)

    if not ssh.test_connection():
        print(f"❌ Cannot connect to {args.workstation}")
        return 1

    # Run E2E test
    tester = TC_E2E()

    if args.test == 'clean' and len(exercises) >= 2:
        result = tester.test_clean(exercises[1], exercises[0], ssh)
    elif args.test == 'isolation':
        result = tester.test_isolation(exercises[0], ssh)
    elif args.test == 'sequence':
        result = tester.test_sequence(exercises, ssh)
    else:
        print("❌ Invalid test configuration")
        return 1

    # Print results
    print("\n" + "=" * 60)
    print(f"Test Result: {'PASS' if result.passed else 'FAIL'}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Bugs Found: {len(result.bugs_found)}")

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
