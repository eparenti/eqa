#!/usr/bin/env python3
"""
TC-IDEM: Idempotency Testing

Documented in SKILL.md lines 1122-1173 but NOT previously implemented.
This is CRITICAL for guideline #5 (repeatability).

Validates that students can practice exercises repeatedly with identical results:
- Cycle 1: lab start → capture state → test → lab finish
- Cycle 2: lab start → capture state → lab finish
- Cycle 3: lab start → capture state
- Verify: All initial states are IDENTICAL
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.ssh_connection import SSHConnection
from lib.state_capture import SystemState, StateDiff, capture_system_state, compare_states, format_diff_report
from lib.test_result import TestResult, ExerciseContext, Bug, BugSeverity


class TC_IDEM:
    """
    Test Category: Idempotency Testing

    Verifies that students can practice exercises repeatedly with identical results.
    Tests cleanup completeness by comparing system states across multiple cycles.
    """

    def __init__(self, cycles: int = 3):
        """
        Initialize idempotency tester.

        Args:
            cycles: Number of test cycles to run (default: 3)
        """
        self.cycles = cycles

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test multi-cycle idempotency for exercise.

        Args:
            exercise: Exercise context
            ssh: SSH connection to workstation

        Returns:
            TestResult with idempotency validation
        """
        start_time = datetime.now()

        print(f"\n🔄 Testing idempotency for {exercise.id} ({self.cycles} cycles)")

        states: List[SystemState] = []
        bugs_found = []

        # Run multiple cycles
        for cycle in range(1, self.cycles + 1):
            print(f"  Cycle {cycle}/{self.cycles}:")

            # Start exercise
            print(f"    - Running: lab start {exercise.id}")
            start_result = ssh.run(f"lab start {exercise.id}", timeout=300)

            if not start_result.success:
                # Lab start failed
                bug = Bug(
                    id=f"IDEM-{exercise.id}-001",
                    severity=BugSeverity.P0_BLOCKER,
                    exercise_id=exercise.id,
                    category="TC-IDEM",
                    description=f"lab start failed in cycle {cycle}",
                    fix_recommendation=f"Fix lab start script for {exercise.id}",
                    verification_steps=[
                        f"ssh workstation",
                        f"lab start {exercise.id}",
                        "Verify no errors"
                    ]
                )
                bugs_found.append(bug)

                end_time = datetime.now()
                return TestResult(
                    category="TC-IDEM",
                    exercise_id=exercise.id,
                    passed=False,
                    timestamp=start_time.isoformat(),
                    duration_seconds=(end_time - start_time).total_seconds(),
                    details={
                        'cycles_attempted': cycle,
                        'failure_reason': 'lab start failed',
                        'error': start_result.stderr
                    },
                    bugs_found=bugs_found
                )

            # Capture state after lab start
            print(f"    - Capturing system state...")
            state = capture_system_state(ssh, exercise_id=exercise.id)
            states.append(state)

            # Finish exercise (cleanup)
            print(f"    - Running: lab finish {exercise.id}")
            finish_result = ssh.run(f"lab finish {exercise.id}", timeout=300)

            if not finish_result.success:
                bug = Bug(
                    id=f"IDEM-{exercise.id}-002",
                    severity=BugSeverity.P1_CRITICAL,
                    exercise_id=exercise.id,
                    category="TC-IDEM",
                    description=f"lab finish failed in cycle {cycle}",
                    fix_recommendation=f"Fix lab finish script for {exercise.id}",
                    verification_steps=[
                        f"ssh workstation",
                        f"lab finish {exercise.id}",
                        "Verify no errors"
                    ]
                )
                bugs_found.append(bug)

        # Compare all states - they should be IDENTICAL
        print(f"\n  📊 Comparing states across {self.cycles} cycles...")

        state_diffs = []
        all_identical = True

        # Compare each state with the first state
        baseline_state = states[0]

        for i, state in enumerate(states[1:], 2):
            diff = compare_states(baseline_state, state)
            state_diffs.append((i, diff))

            if diff.has_changes:
                all_identical = False
                print(f"  ❌ Cycle {i} state differs from Cycle 1:")
                print(format_diff_report(diff))

                # Create bug for state difference
                bug = Bug(
                    id=f"IDEM-{exercise.id}-{i:03d}",
                    severity=BugSeverity.P1_CRITICAL,
                    exercise_id=exercise.id,
                    category="TC-IDEM",
                    description=f"System state differs between cycles (Cycle {i} vs Cycle 1)",
                    fix_recommendation=self._generate_fix_recommendation(diff, exercise),
                    verification_steps=[
                        f"ssh workstation",
                        f"lab start {exercise.id}",
                        "Capture state",
                        f"lab finish {exercise.id}",
                        f"lab start {exercise.id}",
                        "Capture state again",
                        "Compare states - should be identical"
                    ]
                )
                bugs_found.append(bug)
            else:
                print(f"  ✅ Cycle {i} state matches Cycle 1")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        if all_identical:
            print(f"\n✅ Idempotency PASSED: All {self.cycles} cycles produced identical states")
        else:
            print(f"\n❌ Idempotency FAILED: States differ across cycles")

        return TestResult(
            category="TC-IDEM",
            exercise_id=exercise.id,
            passed=all_identical,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            details={
                'cycles_tested': self.cycles,
                'states_captured': len(states),
                'all_identical': all_identical,
                'state_diffs': [{'cycle': i, 'changes': diff.change_count}
                               for i, diff in state_diffs]
            },
            bugs_found=bugs_found
        )

    def _generate_fix_recommendation(self, diff: StateDiff, exercise: ExerciseContext) -> str:
        """
        Generate fix recommendation based on state differences.

        Args:
            diff: State difference
            exercise: Exercise context

        Returns:
            Fix recommendation string
        """
        recommendations = []

        recommendations.append(f"Fix cleanup in finish.yml for {exercise.id}:")
        recommendations.append("")

        if diff.users_added or diff.users_removed:
            recommendations.append("# Remove all users created by exercise")
            recommendations.append("- name: Remove exercise users")
            recommendations.append("  ansible.builtin.user:")
            recommendations.append("    name: '{{ item }}'")
            recommendations.append("    state: absent")
            recommendations.append("    remove: yes")
            recommendations.append("  loop:")
            for user in sorted(diff.users_added.union(diff.users_removed)):
                recommendations.append(f"    - {user}")
            recommendations.append("  failed_when: false  # Idempotent")
            recommendations.append("")

        if diff.groups_added or diff.groups_removed:
            recommendations.append("# Remove all groups created by exercise")
            recommendations.append("- name: Remove exercise groups")
            recommendations.append("  ansible.builtin.group:")
            recommendations.append("    name: '{{ item }}'")
            recommendations.append("    state: absent")
            recommendations.append("  loop:")
            for group in sorted(diff.groups_added.union(diff.groups_removed)):
                recommendations.append(f"    - {group}")
            recommendations.append("  failed_when: false")
            recommendations.append("")

        if diff.files_added or diff.files_removed:
            recommendations.append("# Remove all files created by exercise")
            recommendations.append("- name: Remove exercise files")
            recommendations.append("  ansible.builtin.file:")
            recommendations.append("    path: '{{ item }}'")
            recommendations.append("    state: absent")
            recommendations.append("  loop:")
            # Show first 5 files as examples
            example_files = sorted(diff.files_added.union(diff.files_removed))[:5]
            for file in example_files:
                recommendations.append(f"    - {file}")
            if len(diff.files_added.union(diff.files_removed)) > 5:
                recommendations.append(f"    # ... and {len(diff.files_added.union(diff.files_removed)) - 5} more")
            recommendations.append("  failed_when: false")
            recommendations.append("")

        if diff.services_added or diff.services_removed:
            recommendations.append("# Stop and disable all services started by exercise")
            recommendations.append("- name: Stop exercise services")
            recommendations.append("  ansible.builtin.systemd:")
            recommendations.append("    name: '{{ item }}'")
            recommendations.append("    state: stopped")
            recommendations.append("    enabled: false")
            recommendations.append("  loop:")
            for service in sorted(diff.services_added.union(diff.services_removed)):
                recommendations.append(f"    - {service}")
            recommendations.append("  failed_when: false")
            recommendations.append("")

        if diff.containers_added or diff.containers_removed:
            recommendations.append("# Remove all containers created by exercise")
            recommendations.append("- name: Remove exercise containers")
            recommendations.append("  containers.podman.podman_container:")
            recommendations.append("    name: '{{ item }}'")
            recommendations.append("    state: absent")
            recommendations.append("  loop:")
            for container in sorted(diff.containers_added.union(diff.containers_removed)):
                recommendations.append(f"    - {container}")
            recommendations.append("  failed_when: false")
            recommendations.append("")

        return "\n".join(recommendations)


def main():
    """Test TC_IDEM functionality."""
    import argparse
    from lib.test_result import ExerciseType

    parser = argparse.ArgumentParser(description="Test exercise idempotency")
    parser.add_argument("exercise_id", help="Exercise ID to test")
    parser.add_argument("--workstation", default="workstation", help="Workstation hostname")
    parser.add_argument("--cycles", type=int, default=3, help="Number of test cycles")
    parser.add_argument("--lesson", default="<lesson-code>", help="Lesson code")

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

    # Create SSH connection
    ssh = SSHConnection(args.workstation)

    if not ssh.test_connection():
        print(f"❌ Cannot connect to {args.workstation}")
        return 1

    # Run idempotency test
    tester = TC_IDEM(cycles=args.cycles)
    result = tester.test(exercise, ssh)

    # Print results
    print("\n" + "=" * 60)
    print(f"Test Result: {'PASS' if result.passed else 'FAIL'}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Bugs Found: {len(result.bugs_found)}")

    if result.bugs_found:
        print("\nBugs:")
        for bug in result.bugs_found:
            print(f"\n{bug.id} ({bug.severity.value}): {bug.description}")
            print(f"Fix:\n{bug.fix_recommendation}")

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
