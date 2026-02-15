"""TC-PREREQ: Prerequisites validation.

Validates that all prerequisites are met before testing an exercise:
- SSH connectivity
- Required tools (ansible, python, etc.)
- Lab hosts reachable
- Execution environments available
"""

from datetime import datetime
from typing import List
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext
from ..clients.ssh import SSHConnection


class TC_PREREQ:
    """Prerequisites test category."""

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test all prerequisites for an exercise.

        Args:
            exercise: Exercise context
            ssh: SSH connection to workstation

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-PREREQ: Testing prerequisites...")

        bugs_found = []
        start_time = datetime.now()

        # Test 1: SSH connection
        if not ssh.test_connection():
            bugs_found.append(Bug(
                id=f"PREREQ-SSH-001-{exercise.id}",
                severity=BugSeverity.P0_BLOCKER,
                category="TC-PREREQ",
                exercise_id=exercise.id,
                description="SSH connection to workstation failed",
                fix_recommendation="Check SSH configuration and network connectivity",
                verification_steps=[
                    "Verify workstation is running",
                    "Check SSH keys are configured",
                    "Test: ssh student@workstation"
                ]
            ))

        # Test 2: Basic tools
        required_tools = ['ansible', 'python3', 'git']
        for tool in required_tools:
            result = ssh.run(f"which {tool}")
            if not result.success:
                bugs_found.append(Bug(
                    id=f"PREREQ-TOOL-{tool.upper()}-{exercise.id}",
                    severity=BugSeverity.P1_CRITICAL,
                    category="TC-PREREQ",
                    exercise_id=exercise.id,
                    description=f"Required tool '{tool}' not found on workstation",
                    fix_recommendation=f"Install {tool} on workstation",
                    verification_steps=[f"Run: which {tool}"]
                ))

        # Test 3: Ansible version
        result = ssh.run("ansible --version")
        if result.success:
            print(f"   ✓ Ansible available: {result.stdout.split()[1]}")
        else:
            bugs_found.append(Bug(
                id=f"PREREQ-ANSIBLE-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-PREREQ",
                exercise_id=exercise.id,
                description="Ansible not available",
                fix_recommendation="Install ansible on workstation",
                verification_steps=["Run: ansible --version"]
            ))

        # Test 4: Check for ansible-navigator (if needed)
        result = ssh.run("which ansible-navigator")
        if result.success:
            print(f"   ✓ ansible-navigator available")

        # Test 5: Lab hosts (if known)
        common_hosts = ['servera', 'serverb', 'serverc']
        for host in common_hosts:
            result = ssh.run(f"ping -c 1 -W 2 {host}", timeout=5)
            if not result.success:
                # This is only P3 since not all exercises use all hosts
                bugs_found.append(Bug(
                    id=f"PREREQ-HOST-{host.upper()}-{exercise.id}",
                    severity=BugSeverity.P3_LOW,
                    category="TC-PREREQ",
                    exercise_id=exercise.id,
                    description=f"Lab host '{host}' not reachable",
                    fix_recommendation=f"Ensure {host} is running and network is configured",
                    verification_steps=[f"Run: ping {host}"]
                ))

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-PREREQ",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'tests_run': 5,
                'ssh_working': ssh.test_connection(),
                'tools_checked': len(required_tools),
                'hosts_checked': len(common_hosts)
            }
        )
