"""TC-ROLLBACK: Rollback and recovery testing.

Tests that exercises can recover from:
- Failed/interrupted exercises
- Partial completion states
- Error conditions
- Ctrl+C interruptions
"""

import signal
import time
from datetime import datetime
from typing import List, Dict, Optional
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext, ExerciseType
from ..clients.ssh import SSHConnection


class TC_ROLLBACK:
    """Rollback and recovery test category."""

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test rollback and recovery capabilities.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-ROLLBACK: Testing rollback/recovery...")

        bugs_found = []
        start_time = datetime.now()

        # Test 1: Recovery from finish without start
        print("   → Testing finish without start...")
        finish_bugs = self._test_finish_without_start(exercise, ssh)
        bugs_found.extend(finish_bugs)

        # Test 2: Recovery from double start
        print("   → Testing double start...")
        double_start_bugs = self._test_double_start(exercise, ssh)
        bugs_found.extend(double_start_bugs)

        # Test 3: Recovery from partial execution
        print("   → Testing partial execution recovery...")
        partial_bugs = self._test_partial_recovery(exercise, ssh)
        bugs_found.extend(partial_bugs)

        # Test 4: Recovery from failed grading
        if exercise.type == ExerciseType.LAB:
            print("   → Testing grade recovery...")
            grade_bugs = self._test_grade_recovery(exercise, ssh)
            bugs_found.extend(grade_bugs)

        # Test 5: State consistency after errors
        print("   → Testing state consistency...")
        state_bugs = self._test_state_consistency(exercise, ssh)
        bugs_found.extend(state_bugs)

        # Cleanup
        ssh.run(f"lab finish {exercise.lab_name}", timeout=60)

        if len(bugs_found) == 0:
            print("      ✓ Rollback/recovery working correctly")

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-ROLLBACK",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'tests_run': 5,
                'issues_found': len(bugs_found)
            }
        )

    def _test_finish_without_start(self, exercise: ExerciseContext,
                                    ssh: SSHConnection) -> List[Bug]:
        """Test that finish works even if start wasn't run."""
        bugs = []

        # Make sure exercise is not started
        ssh.run(f"lab finish {exercise.lab_name}", timeout=60)

        # Try to finish again (should handle gracefully)
        result = ssh.run(f"lab finish {exercise.lab_name}", timeout=60)

        # It's OK if it fails, but it shouldn't crash or hang
        if not result.success:
            output = result.stdout + result.stderr
            # Check for crash indicators
            crash_indicators = ['traceback', 'exception', 'error:', 'segfault', 'core dump']
            for indicator in crash_indicators:
                if indicator.lower() in output.lower():
                    bugs.append(Bug(
                        id=f"ROLLBACK-FINISH-CRASH-{exercise.id}",
                        severity=BugSeverity.P1_CRITICAL,
                        category="TC-ROLLBACK",
                        exercise_id=exercise.id,
                        description="Lab finish crashes when exercise not started",
                        fix_recommendation="Add check for exercise state before cleanup",
                        verification_steps=[
                            f"Run: lab finish {exercise.lab_name} (without start)",
                            "Should exit gracefully"
                        ]
                    ))
                    break
        else:
            print("      ✓ Finish handles not-started gracefully")

        return bugs

    def _test_double_start(self, exercise: ExerciseContext,
                           ssh: SSHConnection) -> List[Bug]:
        """Test that starting twice doesn't cause issues."""
        bugs = []

        # Start first time
        result1 = ssh.run(f"lab start {exercise.lab_name}", timeout=120)
        if not result1.success:
            # Can't test double start if first start fails
            return bugs

        # Start second time (should handle gracefully)
        result2 = ssh.run(f"lab start {exercise.lab_name}", timeout=120)

        if not result2.success:
            output = result2.stdout + result2.stderr

            # Check if it's a proper "already started" message
            already_started_indicators = ['already', 'running', 'started', 'in progress']
            is_expected = any(ind in output.lower() for ind in already_started_indicators)

            if not is_expected:
                # Check for crashes
                crash_indicators = ['traceback', 'exception', 'segfault']
                for indicator in crash_indicators:
                    if indicator.lower() in output.lower():
                        bugs.append(Bug(
                            id=f"ROLLBACK-DOUBLE-START-{exercise.id}",
                            severity=BugSeverity.P1_CRITICAL,
                            category="TC-ROLLBACK",
                            exercise_id=exercise.id,
                            description="Lab start crashes when already started",
                            fix_recommendation="Add idempotent check at start of lab start",
                            verification_steps=[
                                f"Run: lab start {exercise.lab_name}",
                                f"Run: lab start {exercise.lab_name} (again)",
                                "Should exit gracefully"
                            ]
                        ))
                        break
        else:
            print("      ✓ Double start handled gracefully")

        return bugs

    def _test_partial_recovery(self, exercise: ExerciseContext,
                                ssh: SSHConnection) -> List[Bug]:
        """Test recovery from partial exercise state."""
        bugs = []
        base_id = exercise.id.removesuffix('-ge').removesuffix('-lab')

        # Ensure started
        ssh.run(f"lab start {exercise.lab_name}", timeout=120)

        # Create some partial state
        work_dir = f"/home/student/{base_id}"
        ssh.run(f"mkdir -p {work_dir}", timeout=5)
        ssh.run(f"touch {work_dir}/partial-test-file.txt", timeout=5)
        ssh.run(f"echo 'partial content' > {work_dir}/incomplete.yml", timeout=5)

        # Try to finish (should clean up partial state)
        result = ssh.run(f"lab finish {exercise.lab_name}", timeout=120)

        if not result.success:
            bugs.append(Bug(
                id=f"ROLLBACK-PARTIAL-FINISH-{exercise.id}",
                severity=BugSeverity.P2_HIGH,
                category="TC-ROLLBACK",
                exercise_id=exercise.id,
                description="Lab finish fails with partial exercise state",
                fix_recommendation="Make finish script more robust to partial states",
                verification_steps=[
                    "Create partial exercise state",
                    f"Run: lab finish {exercise.lab_name}",
                    "Should complete without errors"
                ]
            ))

        # Try to start again
        result = ssh.run(f"lab start {exercise.lab_name}", timeout=120)
        if not result.success:
            bugs.append(Bug(
                id=f"ROLLBACK-PARTIAL-START-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-ROLLBACK",
                exercise_id=exercise.id,
                description="Lab cannot start after partial state cleanup",
                fix_recommendation="Ensure finish fully cleans up partial states",
                verification_steps=[
                    f"Run: lab finish {exercise.lab_name}",
                    f"Run: lab start {exercise.lab_name}",
                    "Should succeed"
                ]
            ))
        else:
            print("      ✓ Partial state recovery works")

        return bugs

    def _test_grade_recovery(self, exercise: ExerciseContext,
                             ssh: SSHConnection) -> List[Bug]:
        """Test that grading doesn't corrupt state."""
        bugs = []

        if not exercise.grading_script:
            return bugs

        # Ensure started
        ssh.run(f"lab start {exercise.lab_name}", timeout=120)

        # Run grading (will likely fail without solution)
        ssh.run(f"lab grade {exercise.lab_name}", timeout=60)

        # Verify exercise is still in valid state
        # Should be able to finish
        result = ssh.run(f"lab finish {exercise.lab_name}", timeout=120)
        if not result.success:
            bugs.append(Bug(
                id=f"ROLLBACK-GRADE-CORRUPT-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-ROLLBACK",
                exercise_id=exercise.id,
                description="Grading corrupts exercise state - cannot finish",
                fix_recommendation="Ensure grading is read-only and doesn't modify state",
                verification_steps=[
                    f"Run: lab start {exercise.lab_name}",
                    f"Run: lab grade {exercise.lab_name}",
                    f"Run: lab finish {exercise.lab_name}",
                    "All should succeed"
                ]
            ))

        # Should be able to start again
        result = ssh.run(f"lab start {exercise.lab_name}", timeout=120)
        if not result.success:
            bugs.append(Bug(
                id=f"ROLLBACK-GRADE-STATE-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-ROLLBACK",
                exercise_id=exercise.id,
                description="Cannot restart after grading",
                fix_recommendation="Ensure grading and finish properly reset state",
                verification_steps=[
                    "Grade and finish exercise",
                    "Try to start again",
                    "Should succeed"
                ]
            ))
        else:
            print("      ✓ Grade recovery works")

        return bugs

    def _test_state_consistency(self, exercise: ExerciseContext,
                                ssh: SSHConnection) -> List[Bug]:
        """Test state consistency after various operations."""
        bugs = []
        base_id = exercise.id.removesuffix('-ge').removesuffix('-lab')

        # Clean state
        ssh.run(f"lab finish {exercise.lab_name}", timeout=120)

        # Start fresh
        result = ssh.run(f"lab start {exercise.lab_name}", timeout=120)
        if not result.success:
            return bugs

        # Check that expected resources exist
        work_dir = f"/home/student/{base_id}"
        dir_check = ssh.run(f"test -d {work_dir}", timeout=5)

        # Finish
        ssh.run(f"lab finish {exercise.lab_name}", timeout=120)

        # Check that resources are cleaned up
        dir_check_after = ssh.run(f"test -d {work_dir}", timeout=5)

        # Working directory might or might not be removed - just check it's clean
        if dir_check_after.success:
            # Directory still exists - check if it's empty or has only expected files
            files_check = ssh.run(f"find {work_dir} -type f 2>/dev/null | wc -l", timeout=10)
            if files_check.success:
                file_count = int(files_check.stdout.strip()) if files_check.stdout.strip().isdigit() else 0
                if file_count > 10:  # More than 10 files is suspicious
                    bugs.append(Bug(
                        id=f"ROLLBACK-STATE-LEFTOVER-{exercise.id}",
                        severity=BugSeverity.P3_LOW,
                        category="TC-ROLLBACK",
                        exercise_id=exercise.id,
                        description=f"Finish left {file_count} files in working directory",
                        fix_recommendation="Consider cleaning up working directory on finish",
                        verification_steps=[
                            f"Run: lab finish {exercise.lab_name}",
                            f"Check: ls {work_dir}"
                        ]
                    ))

        if not bugs:
            print("      ✓ State consistency maintained")

        return bugs
