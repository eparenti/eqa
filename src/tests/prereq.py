"""TC-PREREQ: Prerequisites validation.

Validates that all prerequisites are met before testing an exercise:
- SSH connectivity to workstation (P0 if fails)
- Required tools installed (course-profile-aware)
- Lab start succeeds
- Exercise files deployed

This is the foundation test - if TC-PREREQ fails with P0,
testing should stop for this exercise.
"""

from datetime import datetime
from typing import List

from ..models import TestResult, Bug, BugSeverity, ExerciseContext
from ..ssh import SSHConnection


class TC_PREREQ:
    """Prerequisites test category.

    Performs comprehensive prerequisite validation including SSH connectivity,
    tool availability, and lab start validation.
    Uses course profile to determine which tools are expected.
    """

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """Test all prerequisites for an exercise."""
        print(f"\n   TC-PREREQ: Testing prerequisites...")

        bugs_found = []
        start_time = datetime.now()
        details = {}

        # 1. SSH connection (P0 blocker - stop if this fails)
        ssh_ok = self._test_ssh(exercise, ssh, bugs_found)
        details['ssh_ok'] = ssh_ok

        if not ssh_ok:
            # Can't continue without SSH
            duration = (datetime.now() - start_time).total_seconds()
            return TestResult(
                category="TC-PREREQ",
                exercise_id=exercise.id,
                passed=False,
                timestamp=datetime.now().isoformat(),
                duration_seconds=duration,
                bugs_found=bugs_found,
                details=details
            )

        # 2. Required tools (course-profile-aware)
        tools_ok = self._test_tools(exercise, ssh, bugs_found)
        details['tools_ok'] = tools_ok

        # 3. Lab start
        lab_ok = self._test_lab_start(exercise, ssh, bugs_found)
        details['lab_ok'] = lab_ok

        # 4. Exercise files deployed (if lab started successfully)
        if lab_ok:
            files_ok = self._test_exercise_files(exercise, ssh, bugs_found)
            details['files_ok'] = files_ok

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-PREREQ",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details=details
        )

    def _test_ssh(self, exercise: ExerciseContext,
                  ssh: SSHConnection, bugs: List[Bug]) -> bool:
        """Test SSH connectivity to workstation."""
        if not ssh.test_connection():
            bugs.append(Bug(
                id=f"PREREQ-SSH-{exercise.id}",
                severity=BugSeverity.P0_BLOCKER,
                category="TC-PREREQ",
                exercise_id=exercise.id,
                description="SSH connection to workstation failed",
                fix_recommendation="Check SSH configuration and network connectivity",
                verification_steps=[
                    "ssh student@workstation hostname",
                    "Check ~/.ssh/config for workstation entry",
                    "Verify lab environment is running"
                ]
            ))
            print(f"      ✗ SSH connection failed")
            return False

        print(f"      ✓ SSH connection")
        return True

    def _test_tools(self, exercise: ExerciseContext,
                    ssh: SSHConnection, bugs: List[Bug]) -> bool:
        """Test required tools are installed, using course profile awareness."""
        profile = exercise.course_profile
        all_ok = True

        # Always-required workstation tools
        essential = ['lab']
        for tool in essential:
            result = ssh.run(f"which {tool} 2>/dev/null", timeout=10)
            if not result.success or not result.stdout.strip():
                bugs.append(Bug(
                    id=f"PREREQ-TOOL-{tool.upper()}-{exercise.id}",
                    severity=BugSeverity.P0_BLOCKER,
                    category="TC-PREREQ",
                    exercise_id=exercise.id,
                    description=f"Essential tool '{tool}' not found on workstation",
                    fix_recommendation=f"Install {tool} on workstation",
                    verification_steps=[f"which {tool}"]
                ))
                all_ok = False
                print(f"      ✗ {tool} not found")
            else:
                print(f"      ✓ {tool}")

        # Course-specific tools (if profile available)
        if profile:
            # Only check tools that should be on the workstation
            for tool in profile.workstation_tools:
                if tool == 'lab':
                    continue  # Already checked above

                result = ssh.run(f"which {tool} 2>/dev/null", timeout=10)
                if not result.success or not result.stdout.strip():
                    # Severity depends on tool criticality
                    if tool in ['podman', 'git']:
                        severity = BugSeverity.P1_CRITICAL
                        desc = f"{tool} not found on workstation (required)"
                    else:
                        severity = BugSeverity.P2_HIGH
                        desc = f"{tool} not found on workstation (expected by course)"

                    bugs.append(Bug(
                        id=f"PREREQ-TOOL-{tool.upper()}-{exercise.id}",
                        severity=severity,
                        category="TC-PREREQ",
                        exercise_id=exercise.id,
                        description=desc,
                        fix_recommendation=f"Install {tool} on workstation",
                        verification_steps=[f"which {tool}"]
                    ))

                    if severity == BugSeverity.P1_CRITICAL:
                        all_ok = False
                        print(f"      ✗ {tool} not found")
                    else:
                        print(f"      ⚠ {tool} not found")
                else:
                    print(f"      ✓ {tool}")

            # Info about container tools (don't check them)
            if profile.container_tools and profile.uses_dev_containers:
                container_tool_list = sorted(profile.container_tools)[:3]
                more = f" + {len(profile.container_tools) - 3}" if len(profile.container_tools) > 3 else ""
                print(f"      ⊘ Container tools: {', '.join(container_tool_list)}{more} (not checked)")

        return all_ok

    def _test_lab_start(self, exercise: ExerciseContext,
                        ssh: SSHConnection, bugs: List[Bug]) -> bool:
        """Test lab start succeeds."""
        print(f"      Testing lab start...")
        result = ssh.run_lab_command('start', exercise.id, timeout=300)

        if not result.success:
            bugs.append(Bug(
                id=f"PREREQ-START-{exercise.id}",
                severity=BugSeverity.P0_BLOCKER,
                category="TC-PREREQ",
                exercise_id=exercise.id,
                description=f"'lab start {exercise.lab_name}' failed",
                fix_recommendation="Fix lab start script or check environment setup",
                verification_steps=[
                    f"lab start {exercise.lab_name}",
                    "Check lab script logs for errors"
                ]
            ))
            print(f"      ✗ lab start failed")
            return False

        print(f"      ✓ lab start")
        return True

    def _test_exercise_files(self, exercise: ExerciseContext,
                              ssh: SSHConnection, bugs: List[Bug]) -> bool:
        """Test that exercise working directory exists."""
        base_dir = f"/home/student/{exercise.lab_name}"
        result = ssh.run(f"test -d {base_dir} && echo 'exists'", timeout=10)

        if not result.success or 'exists' not in result.stdout:
            bugs.append(Bug(
                id=f"PREREQ-FILES-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-PREREQ",
                exercise_id=exercise.id,
                description=f"Exercise directory {base_dir} not created by lab start",
                fix_recommendation="Fix lab start script to create working directory",
                verification_steps=[
                    f"lab start {exercise.lab_name}",
                    f"ls -ld {base_dir}"
                ]
            ))
            print(f"      ✗ Exercise directory not found")
            return False

        print(f"      ✓ Exercise files deployed")
        return True
