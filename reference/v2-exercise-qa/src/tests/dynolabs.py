"""TC-DYNOLABS: DynoLabs Framework Testing.

Tests using DynoLabs 5 built-in testing capabilities when available.
Leverages the Rust CLI's autotest and coursetest commands.

Features:
- Auto-detects DynoLabs 5 Rust CLI
- Runs autotest for randomized comprehensive validation
- Runs coursetest for sequential workflow testing
- Falls back gracefully on older frameworks
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext
from ..clients.ssh import SSHConnection


class TC_DYNOLABS:
    """DynoLabs framework test category."""

    def __init__(self, use_autotest: bool = False, use_coursetest: bool = False):
        """
        Initialize DynoLabs test category.

        Args:
            use_autotest: Run lab autotest (randomized comprehensive testing)
            use_coursetest: Run lab coursetest (sequential workflow testing)
        """
        self.use_autotest = use_autotest
        self.use_coursetest = use_coursetest

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test using DynoLabs built-in testing features.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n   TC-DYNOLABS: Testing DynoLabs framework capabilities...")

        bugs_found = []
        start_time = datetime.now()
        details = {}

        # Detect framework
        framework, prefix = ssh.detect_lab_framework()
        details['framework'] = framework
        details['command_prefix'] = prefix

        print(f"   Detected framework: {framework}")

        # Check if DynoLabs 5 Rust CLI is available
        if framework == 'dynolabs5-rust':
            print(f"   DynoLabs 5 Rust CLI detected - advanced testing available")

            # Run autotest if enabled
            if self.use_autotest:
                self._run_autotest(ssh, bugs_found, details)

            # Run coursetest if enabled
            if self.use_coursetest:
                self._run_coursetest(ssh, exercise, bugs_found, details)

        elif framework == 'dynolabs5-python':
            print(f"   DynoLabs 5 Python detected (uv-based)")
            # Python grading doesn't have autotest/coursetest
            details['note'] = 'Python grading mode - autotest/coursetest not available'

        elif framework == 'wrapper':
            print(f"   Factory wrapper detected")
            details['note'] = 'Factory wrapper - using standard lab commands'

        elif framework == 'dynolabs':
            print(f"   Legacy DynoLabs detected")
            details['note'] = 'Legacy DynoLabs - using standard lab commands'

        else:
            print(f"   Unknown framework - using fallback")
            details['note'] = 'Unknown framework - may have limited functionality'

        # Verify basic lab command works
        self._verify_lab_command(ssh, exercise, bugs_found, details)

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-DYNOLABS",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details=details
        )

    def _run_autotest(self, ssh: SSHConnection, bugs_found: List[Bug],
                      details: dict):
        """Run DynoLabs 5 autotest."""
        print(f"   Running autotest (randomized comprehensive testing)...")

        result = ssh.run_autotest(ignore_errors=True, timeout=1800)
        details['autotest_exit_code'] = result.return_code
        details['autotest_duration'] = result.duration_seconds

        if not result.success:
            # Parse autotest output for failures
            output = result.stdout + result.stderr
            if 'FAIL' in output or 'ERROR' in output:
                bugs_found.append(Bug(
                    id=f"DYNOLABS-AUTOTEST-FAIL-001",
                    severity=BugSeverity.P1_CRITICAL,
                    category="TC-DYNOLABS",
                    exercise_id="course",
                    description="DynoLabs autotest reported failures",
                    fix_recommendation=f"Review autotest output: {output[:500]}"
                ))
            else:
                print(f"   Autotest completed with warnings")
        else:
            print(f"   Autotest passed ({result.duration_seconds:.1f}s)")

    def _run_coursetest(self, ssh: SSHConnection, exercise: ExerciseContext,
                        bugs_found: List[Bug], details: dict):
        """Run DynoLabs 5 coursetest."""
        print(f"   Running coursetest (sequential workflow testing)...")

        # First do a dry run to see what would happen
        result = ssh.run_coursetest(dry_run=True, timeout=60)
        details['coursetest_dry_run'] = result.success

        if not result.success:
            print(f"   Coursetest dry-run failed - skipping actual run")
            return

        # Run actual coursetest
        result = ssh.run_coursetest(timeout=3600)
        details['coursetest_exit_code'] = result.return_code
        details['coursetest_duration'] = result.duration_seconds

        if not result.success:
            output = result.stdout + result.stderr
            bugs_found.append(Bug(
                id=f"DYNOLABS-COURSETEST-FAIL-001",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-DYNOLABS",
                exercise_id="course",
                description="DynoLabs coursetest reported failures",
                fix_recommendation=f"Review coursetest output: {output[:500]}"
            ))
        else:
            print(f"   Coursetest passed ({result.duration_seconds:.1f}s)")

    def _verify_lab_command(self, ssh: SSHConnection, exercise: ExerciseContext,
                           bugs_found: List[Bug], details: dict):
        """Verify basic lab command functionality."""
        print(f"   Verifying lab command...")

        # Check lab --help works
        result = ssh.run("lab --help 2>/dev/null | head -5", timeout=30)
        details['lab_help_works'] = result.success

        if not result.success:
            bugs_found.append(Bug(
                id=f"DYNOLABS-CMD-FAIL-001-{exercise.id}",
                severity=BugSeverity.P0_BLOCKER,
                category="TC-DYNOLABS",
                exercise_id=exercise.id,
                description="lab command not working",
                fix_recommendation="Verify lab CLI is installed and accessible"
            ))
            return

        # Check lab list works (if available)
        result = ssh.run("lab list 2>/dev/null | head -10", timeout=30)
        if result.success:
            details['lab_list_output'] = result.stdout[:200]
            print(f"   lab command verified")
        else:
            # list may not be available on all frameworks
            print(f"   lab --help works, list not available")
