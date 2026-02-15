"""TC-IDEM: Idempotency testing.

Tests that exercises can be run multiple times:
- Start -> Finish -> Start works correctly
- Multiple cycles don't cause errors
- No state leakage between cycles
- Resources are properly reset
"""

from datetime import datetime
from typing import List, Dict, Optional
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext, ExerciseType
from ..clients.ssh import SSHConnection


class TC_IDEM:
    """Idempotency test category."""

    # Number of cycles to test
    DEFAULT_CYCLES = 3

    def __init__(self, cycles: int = None):
        """Initialize idempotency tester.

        Args:
            cycles: Number of start/finish cycles to test (default: 3)
        """
        self.cycles = cycles or self.DEFAULT_CYCLES

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test multi-cycle idempotency.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-IDEM: Testing idempotency ({self.cycles} cycles)...")

        bugs_found = []
        start_time = datetime.now()
        cycle_results = []

        # Test multiple start/finish cycles
        for cycle in range(1, self.cycles + 1):
            print(f"   → Cycle {cycle}/{self.cycles}...")
            cycle_result = self._run_cycle(cycle, exercise, ssh, bugs_found)
            cycle_results.append(cycle_result)

            # If a cycle completely failed, stop testing
            if cycle_result.get('fatal_error'):
                print(f"   ✗ Cycle {cycle} had fatal error, stopping")
                break

        # Final cycle: leave lab started for subsequent tests
        print(f"   → Final: Starting lab (leave running)...")
        final_start = ssh.run(f"lab start {exercise.lab_name}", timeout=120)
        if not final_start.success:
            bugs_found.append(Bug(
                id=f"IDEM-FINAL-START-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-IDEM",
                exercise_id=exercise.id,
                description="Lab cannot start after multiple cycles",
                fix_recommendation="Check for state leakage between cycles",
                verification_steps=[
                    f"Run: lab start {exercise.lab_name}",
                    f"Run: lab finish {exercise.lab_name}",
                    f"Repeat 3 times",
                    f"Final: lab start {exercise.lab_name} should succeed"
                ]
            ))
        else:
            print(f"   ✓ Lab started successfully after {self.cycles} cycles")

        # Calculate statistics
        total_starts = sum(1 for r in cycle_results if r.get('start_success'))
        total_finishes = sum(1 for r in cycle_results if r.get('finish_success'))
        avg_start_time = sum(r.get('start_duration', 0) for r in cycle_results) / len(cycle_results) if cycle_results else 0
        avg_finish_time = sum(r.get('finish_duration', 0) for r in cycle_results) / len(cycle_results) if cycle_results else 0

        # Check for performance degradation
        if len(cycle_results) >= 2:
            first_start = cycle_results[0].get('start_duration', 0)
            last_start = cycle_results[-1].get('start_duration', 0)
            if last_start > first_start * 2 and first_start > 0:  # More than 2x slower
                bugs_found.append(Bug(
                    id=f"IDEM-PERF-001-{exercise.id}",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-IDEM",
                    exercise_id=exercise.id,
                    description=f"Start time degraded: {first_start:.1f}s -> {last_start:.1f}s after cycles",
                    fix_recommendation="Check for accumulated state causing slowdown",
                    verification_steps=[
                        "Run multiple start/finish cycles",
                        "Compare start times",
                        "Check for leftover resources"
                    ]
                ))

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-IDEM",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'cycles_tested': len(cycle_results),
                'successful_starts': total_starts,
                'successful_finishes': total_finishes,
                'avg_start_time': avg_start_time,
                'avg_finish_time': avg_finish_time,
                'cycle_results': cycle_results
            }
        )

    def _run_cycle(self, cycle_num: int, exercise: ExerciseContext,
                   ssh: SSHConnection, bugs_found: List[Bug]) -> Dict:
        """Run a single start/finish cycle.

        Args:
            cycle_num: Current cycle number
            exercise: Exercise context
            ssh: SSH connection
            bugs_found: List to append bugs to

        Returns:
            Dict with cycle results
        """
        result = {
            'cycle': cycle_num,
            'start_success': False,
            'finish_success': False,
            'start_duration': 0.0,
            'finish_duration': 0.0,
            'fatal_error': False,
        }

        # Run lab start
        start_time = datetime.now()
        start_result = ssh.run(f"lab start {exercise.lab_name}", timeout=120)
        result['start_duration'] = (datetime.now() - start_time).total_seconds()

        if start_result.success:
            result['start_success'] = True
            print(f"      ✓ Start ({result['start_duration']:.1f}s)")
        else:
            error_msg = start_result.stderr[:200] if start_result.stderr else 'unknown error'
            bugs_found.append(Bug(
                id=f"IDEM-START-C{cycle_num}-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-IDEM",
                exercise_id=exercise.id,
                description=f"Lab start failed on cycle {cycle_num}: {error_msg}",
                fix_recommendation="Check lab start script for idempotency issues",
                verification_steps=[
                    f"Run: lab start {exercise.lab_name}",
                    f"Run: lab finish {exercise.lab_name}",
                    f"Run: lab start {exercise.lab_name}",
                    "Should succeed without errors"
                ]
            ))
            print(f"      ✗ Start failed")
            result['fatal_error'] = True
            return result

        # Optionally run solution to simulate actual use
        if exercise.type == ExerciseType.LAB and exercise.solution_files:
            self._apply_solution(exercise, ssh)

        # Run lab finish
        finish_time = datetime.now()
        finish_result = ssh.run(f"lab finish {exercise.lab_name}", timeout=120)
        result['finish_duration'] = (datetime.now() - finish_time).total_seconds()

        if finish_result.success:
            result['finish_success'] = True
            print(f"      ✓ Finish ({result['finish_duration']:.1f}s)")
        else:
            error_msg = finish_result.stderr[:200] if finish_result.stderr else 'unknown error'
            bugs_found.append(Bug(
                id=f"IDEM-FINISH-C{cycle_num}-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-IDEM",
                exercise_id=exercise.id,
                description=f"Lab finish failed on cycle {cycle_num}: {error_msg}",
                fix_recommendation="Check lab finish script for idempotency issues",
                verification_steps=[
                    f"Run: lab start {exercise.lab_name}",
                    f"Run: lab finish {exercise.lab_name}",
                    "Should succeed without errors"
                ]
            ))
            print(f"      ✗ Finish failed")
            result['fatal_error'] = True
            return result

        # Verify lab is in clean state after finish
        verify_result = self._verify_clean_state(exercise, ssh)
        if not verify_result['clean']:
            bugs_found.append(Bug(
                id=f"IDEM-STATE-C{cycle_num}-{exercise.id}",
                severity=BugSeverity.P2_HIGH,
                category="TC-IDEM",
                exercise_id=exercise.id,
                description=f"Lab not in clean state after cycle {cycle_num}: {verify_result['issue']}",
                fix_recommendation="Ensure finish script fully cleans up",
                verification_steps=[
                    f"Run: lab finish {exercise.lab_name}",
                    "Verify no leftover processes or files"
                ]
            ))
            print(f"      ⚠  State not clean: {verify_result['issue']}")

        return result

    def _apply_solution(self, exercise: ExerciseContext, ssh: SSHConnection):
        """Apply solution files during cycle testing."""
        # This is a simplified solution application for testing purposes
        base_id = exercise.id.removesuffix('-ge').removesuffix('-lab')

        for sol_file in exercise.solution_files:
            # Copy solution file to working location
            if exercise.materials_dir:
                src = exercise.materials_dir / "solutions" / sol_file.name
                # Get the base filename without .sol extension
                dest_name = sol_file.stem
                if dest_name.endswith('.sol'):
                    dest_name = dest_name[:-4]
                dest = f"/home/student/{base_id}/{dest_name}"

                ssh.run(f"cp {src} {dest}", timeout=5)

    def _verify_clean_state(self, exercise: ExerciseContext, ssh: SSHConnection) -> Dict:
        """Verify lab is in clean state after finish.

        Returns:
            Dict with 'clean' bool and 'issue' string if not clean
        """
        base_id = exercise.id.removesuffix('-ge').removesuffix('-lab')

        # Check for leftover processes
        result = ssh.run(f"pgrep -f {base_id}", timeout=5)
        if result.success and result.stdout.strip():
            return {'clean': False, 'issue': 'leftover processes running'}

        # Check for leftover lock files
        lock_files = [
            f"/tmp/{base_id}.lock",
            f"/var/lock/{base_id}",
        ]
        for lock_file in lock_files:
            result = ssh.run(f"test -f {lock_file}", timeout=5)
            if result.success:
                return {'clean': False, 'issue': f'leftover lock file: {lock_file}'}

        return {'clean': True, 'issue': ''}


class TC_IDEM_EXTENDED(TC_IDEM):
    """Extended idempotency testing with additional checks."""

    def __init__(self, cycles: int = 5):
        """Initialize extended idempotency tester with more cycles."""
        super().__init__(cycles=cycles)

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """Run extended idempotency tests."""
        # Run base tests first
        base_result = super().test(exercise, ssh)

        # Add extended tests
        bugs_found = list(base_result.bugs_found)
        start_time = datetime.now()

        # Test rapid succession
        print(f"   → Testing rapid succession...")
        rapid_bugs = self._test_rapid_succession(exercise, ssh)
        bugs_found.extend(rapid_bugs)

        # Test with different timing
        print(f"   → Testing with delays...")
        delay_bugs = self._test_with_delays(exercise, ssh)
        bugs_found.extend(delay_bugs)

        duration = base_result.duration_seconds + (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-IDEM",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                **base_result.details,
                'extended_tests': True,
                'rapid_succession_tested': True,
                'delay_tested': True
            }
        )

    def _test_rapid_succession(self, exercise: ExerciseContext,
                                ssh: SSHConnection) -> List[Bug]:
        """Test rapid start/finish succession."""
        bugs = []

        # Quick start/finish 3 times in rapid succession
        for i in range(3):
            ssh.run(f"lab start {exercise.lab_name}", timeout=120)
            ssh.run(f"lab finish {exercise.lab_name}", timeout=120)

        # Final start should work
        result = ssh.run(f"lab start {exercise.lab_name}", timeout=120)
        if not result.success:
            bugs.append(Bug(
                id=f"IDEM-RAPID-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-IDEM",
                exercise_id=exercise.id,
                description="Lab fails after rapid start/finish succession",
                fix_recommendation="Add proper locking/cleanup for rapid operations",
                verification_steps=[
                    "Run rapid start/finish cycles",
                    "Verify final start succeeds"
                ]
            ))
        else:
            print(f"      ✓ Rapid succession OK")
            ssh.run(f"lab finish {exercise.lab_name}", timeout=120)

        return bugs

    def _test_with_delays(self, exercise: ExerciseContext,
                          ssh: SSHConnection) -> List[Bug]:
        """Test with intentional delays between operations."""
        bugs = []
        import time

        # Start, wait, finish
        ssh.run(f"lab start {exercise.lab_name}", timeout=120)
        time.sleep(5)  # Wait 5 seconds
        finish_result = ssh.run(f"lab finish {exercise.lab_name}", timeout=120)

        if not finish_result.success:
            bugs.append(Bug(
                id=f"IDEM-DELAY-001-{exercise.id}",
                severity=BugSeverity.P2_HIGH,
                category="TC-IDEM",
                exercise_id=exercise.id,
                description="Lab finish fails after delay",
                fix_recommendation="Ensure finish works regardless of timing",
                verification_steps=[
                    "Run: lab start",
                    "Wait 5+ seconds",
                    "Run: lab finish",
                    "Should succeed"
                ]
            ))
        else:
            print(f"      ✓ Delayed finish OK")

        return bugs
