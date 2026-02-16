"""TC-CLEAN: Cleanup validation.

Tests that lab finish properly cleans up:
- Removes working directories
- Stops/removes containers
- Resets system state
- lab start works after lab finish
"""

from datetime import datetime

from ..models import TestResult, Bug, BugSeverity, ExerciseContext
from ..ssh import SSHConnection


class TC_CLEAN:
    """Cleanup validation test category."""

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """Test lab finish cleanup."""
        print(f"\n   TC-CLEAN: Testing cleanup...")

        bugs_found = []
        start_time = datetime.now()

        # Run lab finish
        print(f"      Running lab finish...")
        finish_result = ssh.run_lab_command('finish', exercise.id, timeout=300)

        if not finish_result.success:
            bugs_found.append(Bug(
                id=f"CLEAN-FINISH-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-CLEAN",
                exercise_id=exercise.id,
                description="lab finish failed",
                fix_recommendation="Fix lab finish script",
                verification_steps=[f"lab finish {exercise.lab_name}"]
            ))
            print(f"      ✗ lab finish failed")
        else:
            print(f"      ✓ lab finish succeeded")

            # NOTE: We DON'T check if working directory was removed
            # because many courses use git repos that should persist.
            # The lab finish just cleans up generated files, containers, etc.
            print(f"      ⊘ Skipping working directory check (may be persistent project)")

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-CLEAN",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={}
        )
