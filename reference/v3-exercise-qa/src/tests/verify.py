"""TC-VERIFY: Verification playbook testing.

Tests that verification playbooks correctly validate exercise completion:
- Verification playbook exists
- Executes without errors
- Correctly detects when work is complete
- Correctly detects when work is incomplete
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext
from ..clients.ssh import SSHConnection


class TC_VERIFY:
    """Verification playbook test category."""

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test verification playbook functionality.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-VERIFY: Testing verification playbook...")

        bugs_found = []
        start_time = datetime.now()

        # Find verification playbook
        verify_playbook = self._find_verify_playbook(exercise)
        if not verify_playbook:
            # Verification is optional - not finding one is not an error
            print(f"   ⏭  No verification playbook found (optional)")
            duration = (datetime.now() - start_time).total_seconds()
            return TestResult(
                category="TC-VERIFY",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=duration,
                bugs_found=[],
                details={'status': 'skipped', 'reason': 'no_verify_playbook'}
            )

        print(f"   Found verification playbook: {verify_playbook.name}")

        # Test verification playbook
        self._test_verify_execution(exercise, verify_playbook, ssh, bugs_found)

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-VERIFY",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'verify_playbook': str(verify_playbook) if verify_playbook else None
            }
        )

    def _find_verify_playbook(self, exercise: ExerciseContext) -> Optional[Path]:
        """Find verification playbook for exercise."""
        if not exercise.materials_dir:
            return None

        # Common verification playbook names
        candidates = [
            exercise.materials_dir / "verify.yml",
            exercise.materials_dir / "verify.yaml",
            exercise.materials_dir / "playbook-verify.yml",
            exercise.materials_dir / "playbook-verify.yaml",
            exercise.materials_dir / "check.yml",
            exercise.materials_dir / "check.yaml",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None

    def _test_verify_execution(self, exercise: ExerciseContext,
                               verify_playbook: Path, ssh: SSHConnection,
                               bugs_found: List[Bug]):
        """Test verification playbook execution."""

        # Test 1: Verify playbook runs without solution (should detect incomplete work)
        print(f"   → Testing verification without solution...")
        result = ssh.run(f"lab start {exercise.lab_name}")
        if result.exit_code != 0:
            bugs_found.append(Bug(
                id=f"VERIFY-START-FAIL-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-VERIFY",
                exercise_id=exercise.id,
                description="Lab start failed before verification test",
                fix_recommendation=f"Fix lab start script for {exercise.id}"
            ))
            return

        # Run verification playbook
        verify_cmd = f"cd {exercise.materials_dir} && ansible-navigator run {verify_playbook.name} -m stdout"
        result = ssh.run(verify_cmd, timeout=300)

        if result.exit_code != 0:
            # Check if this is expected (verification should fail when work is incomplete)
            if "FAILED" in result.stdout or "failed" in result.stdout.lower():
                print(f"      ✓ Correctly detected incomplete work")
            else:
                bugs_found.append(Bug(
                    id=f"VERIFY-EXEC-FAIL-001-{exercise.id}",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-VERIFY",
                    exercise_id=exercise.id,
                    description="Verification playbook execution failed unexpectedly",
                    fix_recommendation=f"Fix verification playbook syntax/logic: {result.stderr[:200]}"
                ))
                return

        # Test 2: Verify playbook runs with solution (should pass)
        if exercise.solution_files:
            print(f"   → Testing verification with solution...")

            # Apply solution files
            for sol_file in exercise.solution_files:
                base_name = sol_file.name.removesuffix('.sol')
                target = exercise.materials_dir / base_name
                ssh.run(f"cp {sol_file} {target}")

            # Run verification again
            result = ssh.run(verify_cmd, timeout=300)

            if result.exit_code != 0:
                bugs_found.append(Bug(
                    id=f"VERIFY-SOLUTION-FAIL-001-{exercise.id}",
                    severity=BugSeverity.P1_CRITICAL,
                    category="TC-VERIFY",
                    exercise_id=exercise.id,
                    description="Verification failed even with solution applied",
                    fix_recommendation="Verification playbook or solution files may be incorrect"
                ))
            else:
                print(f"      ✓ Correctly validated complete work")
