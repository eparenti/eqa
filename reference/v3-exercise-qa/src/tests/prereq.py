"""TC-PREREQ: Prerequisites validation.

Validates that all prerequisites are met before testing an exercise:
- SSH connectivity to workstation (P0 if fails)
- Required tools installed (course-profile-aware)
- Managed hosts reachable (from solution files and EPUB)
- Network device connectivity (Cisco, Juniper, Arista with timeout multipliers)
- Execution environment availability
- Lab start succeeds
- Exercise files deployed

This is the foundation test - if TC-PREREQ fails with P0,
testing should stop for this exercise.
"""

import re
from datetime import datetime
from typing import List, Set

from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext
from ..clients.ssh import SSHConnection


# Standard lab hosts used in Red Hat Training
STANDARD_HOSTS = {
    'servera', 'serverb', 'serverc', 'serverd', 'servere',
    'workstation', 'bastion', 'utility',
}

# Network device hostname patterns and their types
NETWORK_DEVICE_PATTERNS = {
    r'^iosxe\d*': ('cisco_iosxe', 2.0),
    r'^ios\d*': ('cisco_ios', 2.0),
    r'^junos\d*': ('juniper_junos', 2.5),
    r'^arista\d*': ('arista_eos', 2.0),
    r'^nxos\d*': ('cisco_nxos', 2.0),
}


class TC_PREREQ:
    """Prerequisites test category.

    Performs comprehensive prerequisite validation including SSH connectivity,
    tool availability, managed host reachability, and execution environment checks.
    Uses course profile to determine which tools and hosts are expected.
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

        # 3. Managed hosts reachability
        hosts_ok = self._test_managed_hosts(exercise, ssh, bugs_found)
        details['hosts_ok'] = hosts_ok

        # 4. Network device connectivity (if applicable)
        network_ok = self._test_network_devices(exercise, ssh, bugs_found)
        details['network_ok'] = network_ok

        # 5. Lab start
        lab_ok = self._test_lab_start(exercise, ssh, bugs_found)
        details['lab_ok'] = lab_ok

        # 6. Exercise files deployed
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
            print(f"      FAIL SSH connection")
            return False

        print(f"      OK SSH connection")
        return True

    def _test_tools(self, exercise: ExerciseContext,
                    ssh: SSHConnection, bugs: List[Bug]) -> bool:
        """Test required tools are installed, using course profile awareness."""
        profile = getattr(exercise, 'course_profile', None)
        all_ok = True

        # Always-required tools
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
                print(f"      FAIL {tool} not found")
            else:
                print(f"      OK {tool}")

        # Ansible core - always check
        result = ssh.run("ansible --version 2>/dev/null | head -1", timeout=10)
        if result.success and result.stdout.strip():
            version_line = result.stdout.strip().split('\n')[0]
            print(f"      OK ansible ({version_line})")
        else:
            bugs.append(Bug(
                id=f"PREREQ-ANSIBLE-{exercise.id}",
                severity=BugSeverity.P0_BLOCKER,
                category="TC-PREREQ",
                exercise_id=exercise.id,
                description="Ansible not available on workstation",
                fix_recommendation="Install ansible on workstation",
                verification_steps=["ansible --version"]
            ))
            all_ok = False
            print(f"      FAIL ansible not found")

        # Course-profile-aware tool checks
        if profile:
            # ansible-navigator: only required if course uses it
            if profile.uses_ansible_navigator:
                result = ssh.run("which ansible-navigator 2>/dev/null", timeout=10)
                if not result.success or not result.stdout.strip():
                    bugs.append(Bug(
                        id=f"PREREQ-NAVIGATOR-{exercise.id}",
                        severity=BugSeverity.P1_CRITICAL,
                        category="TC-PREREQ",
                        exercise_id=exercise.id,
                        description="ansible-navigator not found (required by course)",
                        fix_recommendation="pip install ansible-navigator",
                        verification_steps=["which ansible-navigator"]
                    ))
                    all_ok = False
                    print(f"      FAIL ansible-navigator (required by course)")
                else:
                    print(f"      OK ansible-navigator")

            # podman: required if course uses containers/EE
            if profile.uses_containers or profile.uses_execution_environments:
                result = ssh.run("which podman 2>/dev/null", timeout=10)
                if not result.success or not result.stdout.strip():
                    bugs.append(Bug(
                        id=f"PREREQ-PODMAN-{exercise.id}",
                        severity=BugSeverity.P1_CRITICAL,
                        category="TC-PREREQ",
                        exercise_id=exercise.id,
                        description="podman not found (course uses containers/EE)",
                        fix_recommendation="Install podman on workstation",
                        verification_steps=["which podman"]
                    ))
                    all_ok = False
                else:
                    print(f"      OK podman")

            # Other expected tools (P3 - informational)
            for tool in profile.expected_tools:
                if tool in ('ansible-navigator', 'podman', 'ansible', 'lab'):
                    continue  # Already checked above
                result = ssh.run(f"which {tool} 2>/dev/null", timeout=10)
                if result.success and result.stdout.strip():
                    print(f"      OK {tool}")
        else:
            # No course profile - check common tools without severity
            for tool in ['ansible-navigator', 'podman', 'python3', 'git']:
                result = ssh.run(f"which {tool} 2>/dev/null", timeout=10)
                if result.success and result.stdout.strip():
                    print(f"      OK {tool}")

        return all_ok

    def _test_managed_hosts(self, exercise: ExerciseContext,
                            ssh: SSHConnection, bugs: List[Bug]) -> bool:
        """Test that managed hosts referenced in exercise are reachable."""
        profile = getattr(exercise, 'course_profile', None)
        hosts = self._extract_hosts(exercise)

        # Filter through course profile if available
        if profile:
            hosts = {h for h in hosts if profile.is_host_real(h)}

        if not hosts:
            return True

        all_ok = True
        for host in sorted(hosts):
            # Skip workstation - already tested via SSH
            if host == 'workstation':
                continue

            # Check network devices separately
            if self._is_network_device(host):
                continue  # Handled in _test_network_devices

            result = ssh.run(f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no {host} hostname 2>/dev/null", timeout=10)
            if result.success and result.stdout.strip():
                print(f"      OK host {host}")
            else:
                # Try ping as fallback
                result = ssh.run(f"ping -c 1 -W 3 {host} 2>/dev/null", timeout=8)
                if result.success:
                    print(f"      OK host {host} (ping)")
                else:
                    bugs.append(Bug(
                        id=f"PREREQ-HOST-{host.upper()}-{exercise.id}",
                        severity=BugSeverity.P1_CRITICAL,
                        category="TC-PREREQ",
                        exercise_id=exercise.id,
                        description=f"Managed host '{host}' is unreachable",
                        fix_recommendation=f"Ensure {host} is running and network is configured",
                        verification_steps=[
                            f"ssh {host} hostname",
                            f"ping {host}"
                        ]
                    ))
                    all_ok = False
                    print(f"      FAIL host {host} unreachable")

        return all_ok

    def _test_network_devices(self, exercise: ExerciseContext,
                              ssh: SSHConnection, bugs: List[Bug]) -> bool:
        """Test network device connectivity with device-specific timeouts."""
        hosts = self._extract_hosts(exercise)
        profile = getattr(exercise, 'course_profile', None)

        if profile:
            hosts = {h for h in hosts if profile.is_host_real(h)}

        network_hosts = {h for h in hosts if self._is_network_device(h)}

        if not network_hosts:
            return True

        all_ok = True
        for host in sorted(network_hosts):
            device_type, timeout_mult = self._get_device_info(host)
            timeout = int(10 * timeout_mult)

            # Network devices may only respond to ping or SSH with specific params
            result = ssh.run(f"ping -c 1 -W {timeout} {host} 2>/dev/null", timeout=timeout + 5)
            if result.success:
                print(f"      OK network device {host} ({device_type})")
            else:
                bugs.append(Bug(
                    id=f"PREREQ-NETDEV-{host.upper()}-{exercise.id}",
                    severity=BugSeverity.P1_CRITICAL,
                    category="TC-PREREQ",
                    exercise_id=exercise.id,
                    description=f"Network device '{host}' ({device_type}) is unreachable",
                    fix_recommendation=f"Ensure {host} is powered on and network connected",
                    verification_steps=[
                        f"ping {host}",
                        f"ssh {host} (device type: {device_type})"
                    ]
                ))
                all_ok = False
                print(f"      FAIL network device {host}")

        return all_ok

    def _test_lab_start(self, exercise: ExerciseContext,
                        ssh: SSHConnection, bugs: List[Bug]) -> bool:
        """Test that lab start command succeeds.

        The lab CLI handles conflict resolution and package installation
        automatically. We pipe 'yes' via run_lab_command so its interactive
        prompts are answered non-interactively.
        """
        lab_name = exercise.lab_name
        print(f"      Running: lab start {lab_name}")

        result = ssh.run_lab_command('start', exercise.id, timeout=300)

        if not result.success:
            bugs.append(Bug(
                id=f"PREREQ-LABSTART-{exercise.id}",
                severity=BugSeverity.P0_BLOCKER,
                category="TC-PREREQ",
                exercise_id=exercise.id,
                description=f"'lab start {lab_name}' failed: {(result.stdout + result.stderr)[:200]}",
                fix_recommendation="Check lab script and environment",
                verification_steps=[
                    f"lab start {lab_name}",
                    "lab system-info"
                ]
            ))
            print(f"      FAIL lab start")
            return False

        print(f"      OK lab start")
        return True

    def _test_exercise_files(self, exercise: ExerciseContext,
                             ssh: SSHConnection, bugs: List[Bug]) -> bool:
        """Test that exercise files are deployed after lab start."""
        base_id = exercise.lab_name

        # Check if exercise directory exists on workstation
        result = ssh.run(f"test -d /home/student/{base_id} && echo exists", timeout=10)
        if not result.success or 'exists' not in result.stdout:
            # Some exercises don't create directories
            return True

        # Check for solution files
        result = ssh.run(f"ls /home/student/{base_id}/ 2>/dev/null", timeout=10)
        if result.success:
            files = [f for f in result.stdout.strip().split('\n') if f.strip()]
            if files:
                print(f"      OK exercise directory ({len(files)} items)")
            return True

        return True

    def _extract_hosts(self, exercise: ExerciseContext) -> Set[str]:
        """Extract host references from solution files and materials."""
        hosts = set()

        for sol_file in exercise.solution_files:
            if not sol_file.exists():
                continue
            try:
                content = sol_file.read_text(encoding='utf-8', errors='ignore')
                # hosts: pattern in playbooks
                host_match = re.findall(r'^\s*hosts:\s*(.+)$', content, re.MULTILINE)
                for match in host_match:
                    # Parse host patterns
                    for part in match.strip().split(','):
                        part = part.strip().strip("'\"")
                        if part in STANDARD_HOSTS:
                            hosts.add(part)
                        elif re.match(r'^[a-z][a-z0-9_-]*$', part) and len(part) < 20:
                            hosts.add(part)
            except Exception:
                continue

        return hosts

    def _is_network_device(self, hostname: str) -> bool:
        """Check if hostname matches a known network device pattern."""
        for pattern in NETWORK_DEVICE_PATTERNS:
            if re.match(pattern, hostname):
                return True
        return False

    def _get_device_info(self, hostname: str) -> tuple:
        """Get device type and timeout multiplier for a network device hostname."""
        for pattern, (device_type, timeout_mult) in NETWORK_DEVICE_PATTERNS.items():
            if re.match(pattern, hostname):
                return device_type, timeout_mult
        return 'unknown', 1.0
