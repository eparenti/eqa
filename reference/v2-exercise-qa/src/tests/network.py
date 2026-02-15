"""TC-NETWORK: Network requirements validation.

Tests network connectivity:
- Required hosts are reachable
- DNS resolution works
- Required ports are open
- SSH connectivity to managed nodes
- Network device detection with appropriate timeouts
"""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext
from ..clients.ssh import SSHConnection


class NetworkDeviceType(Enum):
    """Types of network devices with different timeout requirements."""
    LINUX = "linux"
    CISCO_IOS = "cisco_ios"
    CISCO_NXOS = "cisco_nxos"
    JUNIPER_JUNOS = "juniper_junos"
    ARISTA_EOS = "arista_eos"
    UNKNOWN = "unknown"


@dataclass
class DeviceInfo:
    """Information about a detected network device."""
    hostname: str
    device_type: NetworkDeviceType
    timeout_multiplier: float
    ssh_timeout: int
    detected_by: str  # How it was detected (banner, inventory, etc.)


class TC_NETWORK:
    """Network requirements validation test category."""

    # Standard lab hosts
    STANDARD_HOSTS = [
        'servera',
        'serverb',
        'serverc',
        'serverd',
        'workstation',
    ]

    # Common ports to check
    COMMON_PORTS = {
        22: 'SSH',
        80: 'HTTP',
        443: 'HTTPS',
        5432: 'PostgreSQL',
        3306: 'MySQL',
    }

    # Network device timeout configuration
    DEVICE_TIMEOUTS = {
        NetworkDeviceType.LINUX: {
            'multiplier': 1.0,
            'ssh_timeout': 10,
            'command_timeout': 30
        },
        NetworkDeviceType.CISCO_IOS: {
            'multiplier': 2.0,
            'ssh_timeout': 20,
            'command_timeout': 60
        },
        NetworkDeviceType.CISCO_NXOS: {
            'multiplier': 2.0,
            'ssh_timeout': 25,
            'command_timeout': 60
        },
        NetworkDeviceType.JUNIPER_JUNOS: {
            'multiplier': 2.5,
            'ssh_timeout': 30,
            'command_timeout': 90
        },
        NetworkDeviceType.ARISTA_EOS: {
            'multiplier': 2.0,
            'ssh_timeout': 20,
            'command_timeout': 60
        },
        NetworkDeviceType.UNKNOWN: {
            'multiplier': 1.5,
            'ssh_timeout': 15,
            'command_timeout': 45
        }
    }

    # Banner patterns for device detection
    BANNER_PATTERNS = {
        NetworkDeviceType.CISCO_IOS: [
            re.compile(r'Cisco IOS Software', re.IGNORECASE),
            re.compile(r'Cisco Internetwork Operating System', re.IGNORECASE),
            re.compile(r'IOS-XE Software', re.IGNORECASE),
        ],
        NetworkDeviceType.CISCO_NXOS: [
            re.compile(r'Cisco Nexus', re.IGNORECASE),
            re.compile(r'NX-OS', re.IGNORECASE),
        ],
        NetworkDeviceType.JUNIPER_JUNOS: [
            re.compile(r'JUNOS', re.IGNORECASE),
            re.compile(r'Juniper Networks', re.IGNORECASE),
        ],
        NetworkDeviceType.ARISTA_EOS: [
            re.compile(r'Arista', re.IGNORECASE),
            re.compile(r'EOS', re.IGNORECASE),
        ],
    }

    # Inventory variable patterns for device type detection
    INVENTORY_DEVICE_PATTERNS = {
        'ansible_network_os': {
            'cisco.ios.ios': NetworkDeviceType.CISCO_IOS,
            'cisco.nxos.nxos': NetworkDeviceType.CISCO_NXOS,
            'junipernetworks.junos.junos': NetworkDeviceType.JUNIPER_JUNOS,
            'arista.eos.eos': NetworkDeviceType.ARISTA_EOS,
            'ios': NetworkDeviceType.CISCO_IOS,
            'nxos': NetworkDeviceType.CISCO_NXOS,
            'junos': NetworkDeviceType.JUNIPER_JUNOS,
            'eos': NetworkDeviceType.ARISTA_EOS,
        },
        'ansible_connection': {
            'network_cli': NetworkDeviceType.UNKNOWN,  # Generic network device
            'netconf': NetworkDeviceType.UNKNOWN,
        }
    }

    def __init__(self):
        """Initialize network test category."""
        self._device_cache: Dict[str, DeviceInfo] = {}

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test network connectivity requirements.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-NETWORK: Testing network connectivity...")

        bugs_found = []
        start_time = datetime.now()

        # Extract hosts from exercise files
        print("   → Scanning for host requirements...")
        required_hosts = self._extract_hosts(exercise)
        print(f"      Found {len(required_hosts)} required host(s)")

        # Detect network devices
        print("   → Detecting network devices...")
        network_devices = self._detect_network_devices(exercise, required_hosts, ssh)
        if network_devices:
            print(f"      Found {len(network_devices)} network device(s)")
            for device in network_devices.values():
                print(f"      - {device.hostname}: {device.device_type.value} "
                      f"(timeout: {device.ssh_timeout}s, multiplier: {device.timeout_multiplier}x)")

        # Test DNS resolution
        print("   → Testing DNS resolution...")
        dns_bugs = self._test_dns(required_hosts, exercise.id, ssh)
        bugs_found.extend(dns_bugs)

        # Test ping connectivity
        print("   → Testing ping connectivity...")
        ping_bugs = self._test_ping(required_hosts, exercise.id, ssh)
        bugs_found.extend(ping_bugs)

        # Test SSH connectivity (with device-aware timeouts)
        print("   → Testing SSH connectivity...")
        ssh_bugs = self._test_ssh(required_hosts, exercise.id, ssh, network_devices)
        bugs_found.extend(ssh_bugs)

        # Extract and test required ports
        print("   → Testing required ports...")
        required_ports = self._extract_ports(exercise)
        port_bugs = self._test_ports(required_hosts, required_ports, exercise.id, ssh)
        bugs_found.extend(port_bugs)

        # Test internet connectivity (if needed)
        if self._requires_internet(exercise):
            print("   → Testing internet connectivity...")
            inet_bugs = self._test_internet(exercise.id, ssh)
            bugs_found.extend(inet_bugs)

        if len(bugs_found) == 0:
            print("      ✓ All network requirements satisfied")

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-NETWORK",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'hosts_checked': list(required_hosts),
                'ports_checked': required_ports,
                'issues_found': len(bugs_found),
                'network_devices': {
                    host: {
                        'type': info.device_type.value,
                        'timeout_multiplier': info.timeout_multiplier,
                        'ssh_timeout': info.ssh_timeout
                    }
                    for host, info in network_devices.items()
                }
            }
        )

    def _detect_network_devices(
        self,
        exercise: ExerciseContext,
        hosts: Set[str],
        ssh: SSHConnection
    ) -> Dict[str, DeviceInfo]:
        """
        Detect network devices and their types from inventory and banners.

        Args:
            exercise: Exercise context
            hosts: Set of hosts to check
            ssh: SSH connection

        Returns:
            Dictionary mapping hostname to DeviceInfo
        """
        devices = {}

        # First, check inventory files for device type hints
        inventory_devices = self._detect_from_inventory(exercise)
        devices.update(inventory_devices)

        # Then, try banner-based detection for undetected hosts
        for host in hosts:
            if host in devices:
                continue  # Already detected from inventory

            if host == 'workstation':
                continue  # Skip workstation

            # Check if this might be a network device
            device_info = self._detect_from_banner(host, ssh)
            if device_info:
                devices[host] = device_info

        return devices

    def _detect_from_inventory(self, exercise: ExerciseContext) -> Dict[str, DeviceInfo]:
        """Detect network devices from inventory files."""
        devices = {}

        if not exercise.materials_dir or not exercise.materials_dir.exists():
            return devices

        # Scan inventory files
        for inv_file in exercise.materials_dir.rglob("inventory*"):
            if not inv_file.is_file():
                continue

            try:
                content = inv_file.read_text(encoding='utf-8', errors='ignore')
                devices.update(self._parse_inventory_for_devices(content))
            except Exception:
                pass

        # Scan group_vars for network device configuration
        for vars_file in exercise.materials_dir.rglob("group_vars/*.yml"):
            try:
                content = vars_file.read_text(encoding='utf-8', errors='ignore')
                devices.update(self._parse_vars_for_devices(content))
            except Exception:
                pass

        return devices

    def _parse_inventory_for_devices(self, content: str) -> Dict[str, DeviceInfo]:
        """Parse inventory content for network device indicators."""
        devices = {}
        current_host = None

        for line in content.split('\n'):
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith('#') or line.startswith('['):
                continue

            # Check for host line with variables
            parts = line.split()
            if parts:
                # First part is hostname
                hostname = parts[0]

                # Check remaining parts for device type indicators
                for part in parts[1:]:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        value = value.strip('"\'')

                        if key in self.INVENTORY_DEVICE_PATTERNS:
                            device_map = self.INVENTORY_DEVICE_PATTERNS[key]
                            for pattern, device_type in device_map.items():
                                if pattern in value:
                                    timeout_config = self.DEVICE_TIMEOUTS[device_type]
                                    devices[hostname] = DeviceInfo(
                                        hostname=hostname,
                                        device_type=device_type,
                                        timeout_multiplier=timeout_config['multiplier'],
                                        ssh_timeout=timeout_config['ssh_timeout'],
                                        detected_by='inventory'
                                    )
                                    break

        return devices

    def _parse_vars_for_devices(self, content: str) -> Dict[str, DeviceInfo]:
        """Parse vars file content for network device configuration."""
        devices = {}

        # Look for ansible_network_os patterns
        network_os_pattern = re.compile(r'ansible_network_os:\s*["\']?(\S+?)["\']?\s*$', re.MULTILINE)

        for match in network_os_pattern.finditer(content):
            network_os = match.group(1).lower()

            for pattern, device_type in self.INVENTORY_DEVICE_PATTERNS.get('ansible_network_os', {}).items():
                if pattern.lower() in network_os:
                    # This is a group_vars file, so we don't know specific host
                    # Mark as detected for general awareness
                    timeout_config = self.DEVICE_TIMEOUTS[device_type]
                    devices['_group_network_device'] = DeviceInfo(
                        hostname='_group',
                        device_type=device_type,
                        timeout_multiplier=timeout_config['multiplier'],
                        ssh_timeout=timeout_config['ssh_timeout'],
                        detected_by='group_vars'
                    )
                    break

        return devices

    def _detect_from_banner(self, host: str, ssh: SSHConnection) -> Optional[DeviceInfo]:
        """
        Detect device type from SSH banner.

        Args:
            host: Hostname to check
            ssh: SSH connection

        Returns:
            DeviceInfo if network device detected, None otherwise
        """
        # Check cache first
        if host in self._device_cache:
            return self._device_cache[host]

        # Try to get SSH banner
        result = ssh.run(
            f"ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no "
            f"{host} 'show version 2>/dev/null || uname -a 2>/dev/null' 2>&1",
            timeout=15
        )

        output = result.stdout + result.stderr if result else ""

        # Check for network device banners
        for device_type, patterns in self.BANNER_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(output):
                    timeout_config = self.DEVICE_TIMEOUTS[device_type]
                    device_info = DeviceInfo(
                        hostname=host,
                        device_type=device_type,
                        timeout_multiplier=timeout_config['multiplier'],
                        ssh_timeout=timeout_config['ssh_timeout'],
                        detected_by='banner'
                    )
                    self._device_cache[host] = device_info
                    return device_info

        # Not a network device (or couldn't detect)
        return None

    def get_timeout_for_host(
        self,
        host: str,
        base_timeout: int = 10,
        network_devices: Optional[Dict[str, DeviceInfo]] = None
    ) -> int:
        """
        Get appropriate timeout for a host.

        Args:
            host: Hostname
            base_timeout: Base timeout in seconds
            network_devices: Dict of detected network devices

        Returns:
            Adjusted timeout in seconds
        """
        if network_devices and host in network_devices:
            device = network_devices[host]
            return int(base_timeout * device.timeout_multiplier)

        # Check for group-level network device detection
        if network_devices and '_group_network_device' in network_devices:
            device = network_devices['_group_network_device']
            return int(base_timeout * device.timeout_multiplier)

        return base_timeout

    def _extract_hosts(self, exercise: ExerciseContext) -> Set[str]:
        """Extract required hosts from exercise files."""
        hosts = set()

        # Add standard hosts that are commonly used
        # We'll verify which ones are actually needed by checking inventory

        # Scan solution files for host references
        for sol_file in exercise.solution_files:
            if sol_file.exists():
                file_hosts = self._extract_hosts_from_file(sol_file)
                hosts.update(file_hosts)

        # Scan materials
        if exercise.materials_dir and exercise.materials_dir.exists():
            # Check inventory files
            for inv_file in exercise.materials_dir.rglob("inventory*"):
                if inv_file.is_file():
                    file_hosts = self._extract_hosts_from_inventory(inv_file)
                    hosts.update(file_hosts)

            # Check playbooks
            for yml_file in exercise.materials_dir.rglob("*.yml"):
                file_hosts = self._extract_hosts_from_file(yml_file)
                hosts.update(file_hosts)

        # Filter out example/group hostnames using course profile
        profile = getattr(exercise, 'course_profile', None)
        if profile:
            hosts = {h for h in hosts if profile.is_host_real(h)}

        # If no hosts found, use common lab hosts
        if not hosts:
            hosts = set(self.STANDARD_HOSTS[:3])  # servera, serverb, serverc

        return hosts

    def _extract_hosts_from_file(self, file_path: Path) -> Set[str]:
        """Extract host references from a YAML file."""
        hosts = set()

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return hosts

        # Find hosts: directive
        hosts_pattern = r'hosts:\s*([^\n]+)'
        for match in re.finditer(hosts_pattern, content):
            host_spec = match.group(1).strip()
            # Handle common patterns
            if host_spec in ['all', 'localhost', 'all:!localhost']:
                continue
            # Could be a group or host
            for host in re.findall(r'\b(server[a-z]|workstation|node\d+|web\d*|db\d*)\b', host_spec):
                hosts.add(host)

        # Find delegate_to references
        delegate_pattern = r'delegate_to:\s*([^\n]+)'
        for match in re.finditer(delegate_pattern, content):
            host = match.group(1).strip().strip('"\'')
            if host and not host.startswith('{{'):
                hosts.add(host)

        return hosts

    def _extract_hosts_from_inventory(self, file_path: Path) -> Set[str]:
        """Extract hosts from an inventory file."""
        hosts = set()

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return hosts

        for line in content.split('\n'):
            line = line.strip()
            # Skip comments and group headers
            if not line or line.startswith('#') or line.startswith('['):
                continue
            # Extract hostname (first word)
            match = re.match(r'^([a-zA-Z][a-zA-Z0-9_-]*)', line)
            if match:
                host = match.group(1)
                # Skip variable definitions
                if '=' not in host:
                    hosts.add(host)

        return hosts

    def _extract_ports(self, exercise: ExerciseContext) -> Dict[str, int]:
        """Extract required ports from exercise files."""
        ports = {}

        # Scan for common port references
        port_patterns = [
            (r'port:\s*(\d+)', 'port'),
            (r'listen\s+(\d+)', 'listen'),
            (r':(\d+)/', 'url_port'),
        ]

        files_to_scan = list(exercise.solution_files)
        if exercise.materials_dir:
            files_to_scan.extend(exercise.materials_dir.rglob("*.yml"))

        for file_path in files_to_scan:
            if not file_path.exists():
                continue
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                for pattern, desc in port_patterns:
                    for match in re.finditer(pattern, content):
                        port = int(match.group(1))
                        if 1 <= port <= 65535 and port not in [22]:  # Skip SSH
                            ports[f"{desc}_{port}"] = port
            except Exception:
                pass

        return ports

    def _requires_internet(self, exercise: ExerciseContext) -> bool:
        """Check if exercise requires internet access."""
        internet_indicators = [
            'galaxy.ansible.com',
            'pypi.org',
            'github.com',
            'registry.redhat.io',
            'quay.io',
            'ansible-galaxy',
            'pip install',
            'dnf install',
            'yum install',
        ]

        files_to_scan = list(exercise.solution_files)
        if exercise.materials_dir:
            files_to_scan.extend(exercise.materials_dir.rglob("*.yml"))

        for file_path in files_to_scan:
            if not file_path.exists():
                continue
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore').lower()
                for indicator in internet_indicators:
                    if indicator.lower() in content:
                        return True
            except Exception:
                pass

        return False

    def _test_dns(self, hosts: Set[str], exercise_id: str,
                  ssh: SSHConnection) -> List[Bug]:
        """Test DNS resolution for hosts."""
        bugs = []

        for host in hosts:
            result = ssh.run(f"getent hosts {host}", timeout=5)
            if not result.success:
                # Try with domain suffix
                result = ssh.run(f"getent hosts {host}.lab.example.com", timeout=5)
                if not result.success:
                    bugs.append(Bug(
                        id=f"NET-DNS-{host}-{exercise_id}",
                        severity=BugSeverity.P1_CRITICAL,
                        category="TC-NETWORK",
                        exercise_id=exercise_id,
                        description=f"DNS resolution failed for host: {host}",
                        fix_recommendation=f"Add {host} to /etc/hosts or DNS",
                        verification_steps=[
                            f"Run: getent hosts {host}",
                            f"Or add to /etc/hosts"
                        ]
                    ))
                else:
                    print(f"      ✓ DNS OK: {host}.lab.example.com")
            else:
                print(f"      ✓ DNS OK: {host}")

        return bugs

    def _test_ping(self, hosts: Set[str], exercise_id: str,
                   ssh: SSHConnection) -> List[Bug]:
        """Test ping connectivity to hosts."""
        bugs = []

        for host in hosts:
            result = ssh.run(f"ping -c 1 -W 2 {host}", timeout=5)
            if not result.success:
                bugs.append(Bug(
                    id=f"NET-PING-{host}-{exercise_id}",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-NETWORK",
                    exercise_id=exercise_id,
                    description=f"Cannot ping host: {host}",
                    fix_recommendation=f"Verify {host} is running and network is configured",
                    verification_steps=[
                        f"Run: ping {host}",
                        "Check host is running",
                        "Check network/firewall"
                    ]
                ))

        return bugs

    def _test_ssh(
        self,
        hosts: Set[str],
        exercise_id: str,
        ssh: SSHConnection,
        network_devices: Optional[Dict[str, DeviceInfo]] = None
    ) -> List[Bug]:
        """Test SSH connectivity to hosts with device-aware timeouts."""
        bugs = []

        for host in hosts:
            if host == 'workstation':
                continue  # Already connected

            # Get appropriate timeout for this host
            connect_timeout = 5
            command_timeout = 10

            if network_devices and host in network_devices:
                device = network_devices[host]
                connect_timeout = device.ssh_timeout
                command_timeout = int(device.ssh_timeout * 1.5)

            # Test SSH connection
            result = ssh.run(
                f"ssh -o BatchMode=yes -o ConnectTimeout={connect_timeout} "
                f"-o StrictHostKeyChecking=no {host} 'echo ok' 2>&1",
                timeout=command_timeout
            )

            if not result.success or 'ok' not in result.stdout:
                # Check if it's a key issue vs connectivity
                output = result.stdout + result.stderr
                if 'permission denied' in output.lower() or 'host key' in output.lower():
                    bugs.append(Bug(
                        id=f"NET-SSH-AUTH-{host}-{exercise_id}",
                        severity=BugSeverity.P2_HIGH,
                        category="TC-NETWORK",
                        exercise_id=exercise_id,
                        description=f"SSH authentication failed to {host}",
                        fix_recommendation="Configure SSH keys or check known_hosts",
                        verification_steps=[
                            f"Run: ssh {host}",
                            "Accept host key if prompted",
                            "Check SSH key configuration"
                        ]
                    ))
                elif 'connection refused' in output.lower() or 'no route' in output.lower():
                    bugs.append(Bug(
                        id=f"NET-SSH-CONN-{host}-{exercise_id}",
                        severity=BugSeverity.P1_CRITICAL,
                        category="TC-NETWORK",
                        exercise_id=exercise_id,
                        description=f"SSH connection refused by {host}",
                        fix_recommendation=f"Verify SSH service is running on {host}",
                        verification_steps=[
                            f"Check: systemctl status sshd on {host}",
                            "Check firewall allows port 22"
                        ]
                    ))
                elif 'timed out' in output.lower() or 'timeout' in output.lower():
                    # Special handling for network devices
                    if network_devices and host in network_devices:
                        device = network_devices[host]
                        bugs.append(Bug(
                            id=f"NET-SSH-TIMEOUT-{host}-{exercise_id}",
                            severity=BugSeverity.P1_CRITICAL,
                            category="TC-NETWORK",
                            exercise_id=exercise_id,
                            description=(
                                f"SSH connection to {device.device_type.value} device "
                                f"'{host}' timed out after {connect_timeout}s"
                            ),
                            fix_recommendation=(
                                f"Increase timeout for {device.device_type.value} devices "
                                f"or check device availability"
                            ),
                            verification_steps=[
                                f"ping {host}",
                                f"ssh -o ConnectTimeout=60 {host}"
                            ]
                        ))
                    else:
                        bugs.append(Bug(
                            id=f"NET-SSH-TIMEOUT-{host}-{exercise_id}",
                            severity=BugSeverity.P1_CRITICAL,
                            category="TC-NETWORK",
                            exercise_id=exercise_id,
                            description=f"SSH connection to {host} timed out",
                            fix_recommendation=f"Check host {host} is running and reachable",
                            verification_steps=[
                                f"ping {host}",
                                f"ssh {host}"
                            ]
                        ))
            else:
                device_type_str = ""
                if network_devices and host in network_devices:
                    device = network_devices[host]
                    device_type_str = f" ({device.device_type.value})"
                print(f"      ✓ SSH OK: {host}{device_type_str}")

        return bugs

    def _test_ports(self, hosts: Set[str], ports: Dict[str, int],
                    exercise_id: str, ssh: SSHConnection) -> List[Bug]:
        """Test specific port connectivity."""
        bugs = []

        for port_name, port in ports.items():
            # Test on first available host
            for host in hosts:
                result = ssh.run(
                    f"timeout 2 bash -c 'echo > /dev/tcp/{host}/{port}' 2>/dev/null",
                    timeout=5
                )
                if result.success:
                    print(f"      ✓ Port {port} open on {host}")
                    break
            # Don't flag as error - port might only be needed on specific host

        return bugs

    def _test_internet(self, exercise_id: str, ssh: SSHConnection) -> List[Bug]:
        """Test internet connectivity."""
        bugs = []

        # Test common endpoints
        test_urls = [
            ('https://galaxy.ansible.com', 'Ansible Galaxy'),
            ('https://pypi.org', 'PyPI'),
        ]

        for url, name in test_urls:
            result = ssh.run(f"curl -s -o /dev/null -w '%{{http_code}}' --connect-timeout 5 {url}", timeout=10)
            if result.success and result.stdout.strip() in ['200', '301', '302']:
                print(f"      ✓ Internet OK: {name}")
                return bugs  # If one works, internet is available

        # If none worked, might be airgapped (not necessarily an error)
        print("      ⚠  Internet access may be limited (airgapped environment?)")

        return bugs
