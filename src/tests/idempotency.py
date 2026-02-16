"""TC-IDEM: Idempotency testing.

Tests that lab scripts are idempotent by running them multiple times:
1. lab start -> lab finish -> lab start (should succeed)
2. Verify cleanup is complete between runs
3. No state pollution across cycles
"""

from datetime import datetime

from ..models import TestResult, Bug, BugSeverity, ExerciseContext
from ..ssh import SSHConnection


class TC_IDEM:
    """Idempotency test category."""

    def test(self, exercise: ExerciseContext, ssh: SSHConnection,
             cycles: int = 2) -> TestResult:
        """Test lab script idempotency."""
        print(f"\n   TC-IDEM: Testing idempotency ({cycles} cycles)...")

        bugs_found = []
        start_time = datetime.now()

        for cycle in range(1, cycles + 1):
            print(f"      Cycle {cycle}/{cycles}...")

            # lab finish (cleanup from previous test)
            finish_result = ssh.run_lab_command('finish', exercise.id, timeout=300)
            if not finish_result.success:
                bugs_found.append(Bug(
                    id=f"IDEM-FINISH-CYCLE{cycle}-{exercise.id}",
                    severity=BugSeverity.P1_CRITICAL,
                    category="TC-IDEM",
                    exercise_id=exercise.id,
                    description=f"lab finish failed on cycle {cycle}",
                    fix_recommendation="Fix lab finish script to clean up properly",
                    verification_steps=[f"lab finish {exercise.lab_name}"]
                ))
                print(f"         ✗ lab finish failed")
                break

            # lab start (should work after finish)
            start_result = ssh.run_lab_command('start', exercise.id, timeout=300)
            if not start_result.success:
                bugs_found.append(Bug(
                    id=f"IDEM-START-CYCLE{cycle}-{exercise.id}",
                    severity=BugSeverity.P1_CRITICAL,
                    category="TC-IDEM",
                    exercise_id=exercise.id,
                    description=f"lab start failed on cycle {cycle} (not idempotent)",
                    fix_recommendation="Fix lab start to be idempotent",
                    verification_steps=[
                        f"lab finish {exercise.lab_name}",
                        f"lab start {exercise.lab_name}"
                    ]
                ))
                print(f"         ✗ lab start failed")
                break

            print(f"         ✓ Cycle {cycle} passed")

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-IDEM",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={'cycles_tested': cycles}
        )
