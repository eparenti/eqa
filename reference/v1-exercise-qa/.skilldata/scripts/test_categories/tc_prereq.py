#!/usr/bin/env python3
"""
TC-PREREQ: Prerequisites Testing

Tests that the lab environment is ready for testing:
- SSH connectivity to workstation
- Required tools installed
- Managed hosts reachable
- `lab start <exercise>` succeeds
- Exercise files created
- Solution files available

This is the foundation test that must pass before other tests run.
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.test_result import TestResult, Bug, BugSeverity, ExerciseContext
from lib.ssh_connection import SSHConnection


class TC_PREREQ:
    """
    Prerequisites testing.

    Validates environment is ready for exercise testing.
    """

    def __init__(self):
        """Initialize prerequisites tester."""
        pass

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test prerequisites.

        Args:
            exercise: Exercise context
            ssh: SSH connection to workstation

        Returns:
            TestResult with prerequisite test results
        """
        start_time = datetime.now()
        bugs_found = []
        test_details = {
            'ssh_connected': False,
            'lab_start_success': False,
            'exercise_dir_created': False,
            'solution_files_found': [],
            'tools_available': {}
        }

        print(f"\n✅ TC-PREREQ: Prerequisites Testing")
        print("=" * 60)

        # 1. Test SSH connectivity
        print("\n  1. Testing SSH connection...")
        if not ssh.test_connection():
            bugs_found.append(Bug(
                id=f"BUG-{exercise.id.upper()}-SSH",
                severity=BugSeverity.P0_BLOCKER,
                exercise_id=exercise.id,
                category="TC-PREREQ",
                description=f"Cannot connect to workstation via SSH",
                fix_recommendation=(
                    "Fix SSH connectivity:\n\n"
                    "1. Verify workstation is running\n"
                    "2. Check SSH configuration in ~/.ssh/config\n"
                    "3. Test manual SSH: ssh student@workstation\n"
                    "4. Check network connectivity\n"
                    "5. Verify SSH keys are configured"
                ),
                verification_steps=[
                    "1. ssh student@workstation",
                    "2. Verify connection succeeds",
                    "3. Re-run test"
                ]
            ))
            print("    ❌ SSH connection failed")

            # Cannot continue without SSH
            return self._build_result(start_time, exercise, bugs_found, test_details)
        else:
            test_details['ssh_connected'] = True
            print("    ✅ SSH connection OK")

        # 2. Check required tools
        print("\n  2. Checking required tools...")
        required_tools = self._get_required_tools(exercise)

        for tool in required_tools:
            result = ssh.run(f"which {tool}", timeout=5)
            tool_available = result['exit_code'] == 0

            test_details['tools_available'][tool] = tool_available

            if not tool_available:
                bugs_found.append(Bug(
                    id=f"BUG-{exercise.id.upper()}-TOOL-{tool.upper()}",
                    severity=BugSeverity.P0_BLOCKER,
                    exercise_id=exercise.id,
                    category="TC-PREREQ",
                    description=f"Required tool not found: {tool}",
                    fix_recommendation=(
                        f"Install {tool}:\n\n"
                        f"For RHEL/Fedora:\n"
                        f"  sudo dnf install {tool}\n\n"
                        f"Or check if tool is in PATH."
                    ),
                    verification_steps=[
                        f"1. Install {tool}",
                        f"2. Run: which {tool}",
                        "3. Verify tool found"
                    ]
                ))
                print(f"    ❌ {tool} not found")
            else:
                print(f"    ✅ {tool} available")

        # 3. Run lab start
        print(f"\n  3. Running: lab start {exercise.id}")
        lab_start_result = ssh.run(
            f"cd ~ && lab start {exercise.id}",
            timeout=600  # 10 minutes for setup
        )

        if lab_start_result['exit_code'] != 0:
            bugs_found.append(Bug(
                id=f"BUG-{exercise.id.upper()}-LABSTART",
                severity=BugSeverity.P0_BLOCKER,
                exercise_id=exercise.id,
                category="TC-PREREQ",
                description=f"`lab start {exercise.id}` failed",
                fix_recommendation=(
                    f"Fix lab start:\n\n"
                    f"Error output:\n{lab_start_result['stderr']}\n\n"
                    f"Common solutions:\n"
                    f"1. Wait for lab environment to be ready\n"
                    f"2. Check cluster connectivity\n"
                    f"3. Verify course package installed\n"
                    f"4. Check lab script for errors\n"
                    f"5. Review lab start output for specific issues"
                ),
                verification_steps=[
                    "1. Check error message",
                    "2. Fix identified issue",
                    f"3. Run: lab start {exercise.id}",
                    "4. Verify success"
                ]
            ))
            print(f"    ❌ lab start failed")
            print(f"       Error: {lab_start_result['stderr'][:200]}")

            # Cannot continue without successful lab start
            return self._build_result(start_time, exercise, bugs_found, test_details)
        else:
            test_details['lab_start_success'] = True
            print("    ✅ lab start succeeded")

        # 4. Verify exercise directory created
        print("\n  4. Checking exercise directory...")
        exercise_dir = f"~/DO{exercise.lesson_code.upper()}/labs/{exercise.id}/"
        ls_result = ssh.run(f"ls -la {exercise_dir}", timeout=5)

        if ls_result['exit_code'] != 0:
            bugs_found.append(Bug(
                id=f"BUG-{exercise.id.upper()}-NODIR",
                severity=BugSeverity.P1_CRITICAL,
                exercise_id=exercise.id,
                category="TC-PREREQ",
                description=f"Exercise directory not created: {exercise_dir}",
                fix_recommendation=(
                    f"Fix exercise directory creation:\n\n"
                    f"Directory should be created by lab start.\n"
                    f"Check grading script start.yml:\n"
                    f"1. Verify directory creation task exists\n"
                    f"2. Check for path errors\n"
                    f"3. Verify lab start completed successfully"
                ),
                verification_steps=[
                    "1. Review grading script start.yml",
                    "2. Add directory creation if missing",
                    f"3. Run: lab start {exercise.id}",
                    f"4. Verify: ls {exercise_dir}"
                ]
            ))
            print(f"    ❌ Directory not found: {exercise_dir}")
        else:
            test_details['exercise_dir_created'] = True
            print(f"    ✅ Directory exists: {exercise_dir}")

        # 5. Check for solution files
        print("\n  5. Checking solution files...")
        solutions_dir = f"~/DO{exercise.lesson_code.upper()}/solutions/{exercise.id}/"
        find_result = ssh.run(f"find {solutions_dir} -name '*.sol' 2>/dev/null", timeout=10)

        if find_result['exit_code'] == 0 and find_result['stdout'].strip():
            solution_files = [f.strip() for f in find_result['stdout'].strip().split('\n')]
            test_details['solution_files_found'] = solution_files
            print(f"    ✅ Found {len(solution_files)} solution files")
            for sol in solution_files[:5]:  # Show first 5
                print(f"       - {sol}")
            if len(solution_files) > 5:
                print(f"       ... and {len(solution_files) - 5} more")
        else:
            print("    ⚠️  No solution files found (may be intentional)")

        # 6. Check managed hosts connectivity (if applicable)
        if self._requires_managed_hosts(exercise):
            print("\n  6. Testing managed hosts connectivity...")
            managed_hosts = self._get_managed_hosts(exercise)

            for host in managed_hosts:
                ping_result = ssh.run(f"ping -c 1 -W 2 {host}", timeout=5)

                if ping_result['exit_code'] != 0:
                    bugs_found.append(Bug(
                        id=f"BUG-{exercise.id.upper()}-HOST-{host.upper()}",
                        severity=BugSeverity.P0_BLOCKER,
                        exercise_id=exercise.id,
                        category="TC-PREREQ",
                        description=f"Cannot reach managed host: {host}",
                        fix_recommendation=(
                            f"Fix connectivity to {host}:\n\n"
                            f"1. Verify {host} is running\n"
                            f"2. Check network configuration\n"
                            f"3. Test: ping {host}\n"
                            f"4. Test: ssh {host}"
                        ),
                        verification_steps=[
                            f"1. Start {host} if stopped",
                            f"2. ping -c 1 {host}",
                            "3. Verify connectivity"
                        ]
                    ))
                    print(f"    ❌ Cannot reach {host}")
                else:
                    print(f"    ✅ {host} reachable")

        # 7. Check execution environment prerequisites (if applicable)
        if self._requires_execution_environment(exercise):
            print("\n  7. Checking execution environment prerequisites...")

            from lib.ansible_executor import AnsibleExecutor

            executor = AnsibleExecutor(ssh)
            exercise_dir = f"~/DO{exercise.lesson_code.upper()}/labs/{exercise.id}/"

            # Check EE prerequisites
            ee_ok, ee_issues = executor.check_ee_prerequisites(exercise_dir)

            if not ee_ok:
                for issue in ee_issues:
                    bugs_found.append(Bug(
                        id=f"BUG-{exercise.id.upper()}-EE-PREREQ",
                        severity=BugSeverity.P0_BLOCKER,
                        exercise_id=exercise.id,
                        category="TC-PREREQ",
                        description=f"Execution environment prerequisite issue: {issue}",
                        fix_recommendation=(
                            "Fix execution environment setup:\n\n"
                            f"{issue}\n\n"
                            "Solutions:\n"
                            "1. Install ansible-navigator: pip3 install ansible-navigator\n"
                            "2. Pull required EE images: podman pull <image-name>\n"
                            "3. Run 'lab start' to download EE images\n"
                            "4. Check ansible-navigator.yml configuration"
                        ),
                        verification_steps=[
                            "1. which ansible-navigator",
                            "2. podman images",
                            "3. Check ansible-navigator.yml",
                            "4. podman pull <ee-image>"
                        ]
                    ))
                    print(f"    ❌ {issue}")
            else:
                print("    ✅ Execution environment prerequisites OK")

        # 8. Check network devices connectivity (if applicable)
        if self._requires_network_devices(exercise):
            print("\n  8. Testing network devices connectivity...")
            network_devices = self._get_network_devices(exercise)

            from lib.ssh_connection import SSHConnectionPool

            pool = SSHConnectionPool()

            for device_info in network_devices:
                device_name = device_info['hostname']
                device_type = device_info.get('type')

                # Add connection to pool with device type
                device_conn = pool.add_connection(
                    device_name,
                    device_type=device_type,
                    auto_detect=True
                )

                print(f"    Testing {device_name} ({device_conn.device_type or 'Linux'})...")

                # Test connection with longer timeout for network devices
                if not device_conn.test_connection(timeout=15):
                    bugs_found.append(Bug(
                        id=f"BUG-{exercise.id.upper()}-NETDEV-{device_name.upper()}",
                        severity=BugSeverity.P0_BLOCKER,
                        exercise_id=exercise.id,
                        category="TC-PREREQ",
                        description=f"Cannot connect to network device: {device_name}",
                        fix_recommendation=(
                            f"Fix connectivity to network device {device_name}:\n\n"
                            f"Device type: {device_type}\n"
                            f"1. Verify device is running\n"
                            f"2. Check SSH configuration\n"
                            f"3. Test: ssh student@{device_name}\n"
                            f"4. For network devices, verify credentials and enable mode\n"
                            f"5. Check inventory file has correct connection settings"
                        ),
                        verification_steps=[
                            f"1. Start {device_name} if stopped",
                            f"2. Test: ssh student@{device_name}",
                            "3. Test show version command",
                            "4. Verify connectivity"
                        ]
                    ))
                    print(f"      ❌ Cannot connect to {device_name}")
                else:
                    print(f"      ✅ {device_name} reachable")

                    # For network devices, test basic command execution
                    if device_conn.is_network_device:
                        test_cmd = "show version" if device_type and 'cisco' in device_type else "show version"
                        cmd_result = device_conn.run(test_cmd, timeout=15)

                        if cmd_result['exit_code'] != 0:
                            bugs_found.append(Bug(
                                id=f"BUG-{exercise.id.upper()}-NETDEV-CMD-{device_name.upper()}",
                                severity=BugSeverity.P2_HIGH,
                                exercise_id=exercise.id,
                                category="TC-PREREQ",
                                description=f"Network device {device_name} connected but commands fail",
                                fix_recommendation=(
                                    f"Fix command execution on {device_name}:\n\n"
                                    f"1. Verify device credentials\n"
                                    f"2. Check enable mode password\n"
                                    f"3. Test command manually: {test_cmd}\n"
                                    f"4. Review Ansible inventory settings"
                                ),
                                verification_steps=[
                                    f"1. ssh student@{device_name}",
                                    f"2. Run: {test_cmd}",
                                    "3. Verify command works"
                                ]
                            ))
                            print(f"      ⚠️  Command execution failed on {device_name}")
                        else:
                            print(f"      ✅ Commands work on {device_name}")

        return self._build_result(start_time, exercise, bugs_found, test_details)

    def _get_required_tools(self, exercise: ExerciseContext) -> List[str]:
        """Get list of required tools based on exercise type."""
        tools = ['lab']  # Always need lab command

        # Add technology-specific tools
        if exercise.lesson_code.upper().startswith('AU') or exercise.lesson_code.upper().startswith('<NETWORK-COURSE>'):
            # Ansible course
            tools.extend(['ansible-navigator', 'ansible', 'python3'])

            # Network automation courses need additional tools
            if exercise.lesson_code.upper() in ['<NETWORK-COURSE>', '<NETWORK-COURSE>']:
                tools.extend(['ansible-galaxy'])  # For network collections

        elif exercise.lesson_code.upper().startswith('DO') and not exercise.lesson_code.upper().startswith('DO4'):
            # OpenShift course (not DO4xx which are automation courses)
            tools.extend(['oc', 'kubectl', 'helm'])
        elif exercise.lesson_code.upper().startswith('RH'):
            # RHEL course - basic tools
            tools.extend(['systemctl', 'firewall-cmd'])

        return tools

    def _requires_managed_hosts(self, exercise: ExerciseContext) -> bool:
        """Check if exercise requires managed hosts."""
        # Ansible courses typically need managed hosts
        # But network automation courses use network devices instead
        if exercise.lesson_code.upper() in ['<NETWORK-COURSE>', '<NETWORK-COURSE>']:
            return False  # These use network devices

        return exercise.lesson_code.upper().startswith('AU')

    def _get_managed_hosts(self, exercise: ExerciseContext) -> List[str]:
        """Get list of managed hosts."""
        # Default managed hosts for most courses
        return ['servera', 'serverb', 'serverc', 'serverd']

    def _requires_execution_environment(self, exercise: ExerciseContext) -> bool:
        """Check if exercise requires execution environments."""
        # Modern Ansible courses and network automation courses use EE
        return exercise.lesson_code.upper() in ['<NETWORK-COURSE>', '<NETWORK-COURSE>', '<AAP-COURSE>']

    def _requires_network_devices(self, exercise: ExerciseContext) -> bool:
        """Check if exercise requires network devices."""
        # Network automation courses need network devices
        return exercise.lesson_code.upper() in ['<NETWORK-COURSE>', '<NETWORK-COURSE>']

    def _get_network_devices(self, exercise: ExerciseContext) -> List[Dict[str, str]]:
        """
        Get list of network devices.

        Returns:
            List of dicts with 'hostname' and 'type' keys
        """
        # Common network devices for <NETWORK-COURSE>/<NETWORK-COURSE>
        if exercise.lesson_code.upper() == '<NETWORK-COURSE>':
            return [
                {'hostname': 'iosxe1', 'type': 'cisco_iosxe'},
                {'hostname': 'iosxe2', 'type': 'cisco_iosxe'},
                {'hostname': 'junos1', 'type': 'juniper_junos'},
                {'hostname': 'junos2', 'type': 'juniper_junos'}
            ]
        elif exercise.lesson_code.upper() == '<NETWORK-COURSE>':
            return [
                {'hostname': 'iosxe1', 'type': 'cisco_iosxe'},
                {'hostname': 'junos1', 'type': 'juniper_junos'}
            ]

        return []

    def _build_result(self, start_time: datetime, exercise: ExerciseContext,
                     bugs_found: List[Bug], test_details: Dict) -> TestResult:
        """Build test result."""
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        passed = len(bugs_found) == 0

        return TestResult(
            category="TC-PREREQ",
            exercise_id=exercise.id,
            passed=passed,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details=test_details,
            summary=f"Prerequisites {'passed' if passed else 'failed'} - {len(bugs_found)} issues found"
        )


def main():
    """Test TC_PREREQ functionality."""
    import argparse

    parser = argparse.ArgumentParser(description="Test TC-PREREQ category")
    parser.add_argument("exercise_id", help="Exercise ID to test")
    parser.add_argument("--workstation", default="workstation", help="Workstation hostname")
    parser.add_argument("--lesson-code", help="Lesson code")

    args = parser.parse_args()

    # Create minimal exercise context
    from lib.test_result import ExerciseContext, ExerciseType
    exercise = ExerciseContext(
        id=args.exercise_id,
        type=ExerciseType.LAB,
        lesson_code=args.lesson_code or "",
        chapter=1,
        chapter_title="Chapter",
        title=args.exercise_id
    )

    # Create SSH connection
    ssh = SSHConnection(args.workstation)

    # Run test
    tester = TC_PREREQ()
    result = tester.test(exercise, ssh)

    # Print results
    print("\n" + "=" * 60)
    print(f"Result: {'PASS' if result.passed else 'FAIL'}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Bugs Found: {len(result.bugs_found)}")
    print("=" * 60)

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
