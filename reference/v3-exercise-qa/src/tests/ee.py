"""TC-EE: Execution Environment validation.

Validates Ansible Execution Environment (EE) configuration:
- ansible-navigator availability and version
- Configuration file presence (ansible-navigator.yml)
- Container runtime (podman/docker)
- EE images availability
"""

import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext
from ..clients.ssh import SSHConnection


class TC_EE:
    """Execution Environment validation test category."""

    # Default EE images to check for
    DEFAULT_EE_IMAGES = [
        'registry.redhat.io/ansible-automation-platform-24/ee-supported-rhel8',
        'registry.redhat.io/ansible-automation-platform-24/ee-supported-rhel9',
        'registry.redhat.io/ansible-automation-platform-25/ee-supported-rhel9',
        'quay.io/ansible/creator-ee',
        'quay.io/ansible/ansible-runner',
    ]

    # Config file locations to check
    CONFIG_LOCATIONS = [
        '~/.ansible-navigator.yml',
        '~/.ansible-navigator.yaml',
        './ansible-navigator.yml',
        './ansible-navigator.yaml',
    ]

    def __init__(self):
        """Initialize EE test category."""
        self._ee_image_cache: Optional[List[str]] = None

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test execution environment configuration.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-EE: Testing execution environment...")

        bugs_found = []
        start_time = datetime.now()
        details = {}

        # Test 1: Check ansible-navigator availability
        # Only check if the course actually uses ansible-navigator
        profile = getattr(exercise, 'course_profile', None)
        course_uses_navigator = not profile or profile.uses_ansible_navigator or not profile.uses_ansible_dev_tools

        if course_uses_navigator:
            print("   → Checking ansible-navigator...")
            nav_ok, nav_version, nav_bug = self._check_ansible_navigator(exercise.id, ssh)
            if nav_bug:
                bugs_found.append(nav_bug)
            else:
                print(f"      ✓ ansible-navigator {nav_version} available")
                details['navigator_version'] = nav_version
        else:
            print("   → Skipping ansible-navigator (course uses ansible dev tools)")
            nav_ok = True

        # Test 2: Check configuration file
        print("   → Checking configuration file...")
        config_ok, config_path, config_bug = self._check_config_file(exercise, ssh)
        if config_bug:
            bugs_found.append(config_bug)
        elif config_path:
            print(f"      ✓ Config file found: {config_path}")
            details['config_file'] = config_path

            # Parse config for EE settings
            ee_config = self._parse_ee_config(config_path, ssh)
            if ee_config:
                details['ee_config'] = ee_config

        # Test 3: Check container runtime
        print("   → Checking container runtime...")
        runtime_ok, runtime_name, runtime_bug = self._check_container_runtime(exercise.id, ssh)
        if runtime_bug:
            bugs_found.append(runtime_bug)
        else:
            print(f"      ✓ Container runtime: {runtime_name}")
            details['container_runtime'] = runtime_name

        # Test 4: Check EE images
        print("   → Checking EE images...")
        images_ok, available_images, image_bugs = self._check_ee_images(exercise, ssh)
        bugs_found.extend(image_bugs)
        if available_images:
            print(f"      ✓ {len(available_images)} EE image(s) available")
            details['available_images'] = available_images
        else:
            print("      ⚠ No EE images found")

        # Test 5: Check EE connectivity (can pull from registry)
        if runtime_ok:
            print("   → Checking registry connectivity...")
            registry_ok, registry_bugs = self._check_registry_connectivity(exercise.id, ssh)
            bugs_found.extend(registry_bugs)
            if registry_ok:
                print("      ✓ Registry connectivity OK")
                details['registry_connectivity'] = True

        if len(bugs_found) == 0:
            print("      ✓ All EE requirements satisfied")

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-EE",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details=details
        )

    def _check_ansible_navigator(
        self,
        exercise_id: str,
        ssh: SSHConnection
    ) -> Tuple[bool, Optional[str], Optional[Bug]]:
        """Check if ansible-navigator is available."""
        # Check if ansible-navigator exists
        result = ssh.run("which ansible-navigator", timeout=5)
        if not result.success:
            return False, None, Bug(
                id=f"EE-NAVIGATOR-MISSING-{exercise_id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-EE",
                exercise_id=exercise_id,
                description="ansible-navigator not found on workstation",
                fix_recommendation="Install ansible-navigator: pip install ansible-navigator",
                verification_steps=[
                    "which ansible-navigator",
                    "pip install ansible-navigator"
                ]
            )

        # Get version
        version_result = ssh.run("ansible-navigator --version 2>&1 | head -1", timeout=10)
        version = "unknown"
        if version_result.success:
            # Parse version from output like "ansible-navigator 3.0.0"
            match = re.search(r'(\d+\.\d+\.\d+)', version_result.stdout)
            if match:
                version = match.group(1)

        return True, version, None

    def _check_config_file(
        self,
        exercise: ExerciseContext,
        ssh: SSHConnection
    ) -> Tuple[bool, Optional[str], Optional[Bug]]:
        """Check for ansible-navigator configuration file."""
        # Check standard locations
        for config_path in self.CONFIG_LOCATIONS:
            result = ssh.run(f"test -f {config_path} && echo 'found'", timeout=5)
            if result.success and 'found' in result.stdout:
                return True, config_path, None

        # Check in exercise materials directory
        if exercise.materials_dir and exercise.materials_dir.exists():
            for config_name in ['ansible-navigator.yml', 'ansible-navigator.yaml']:
                local_config = exercise.materials_dir / config_name
                if local_config.exists():
                    return True, str(local_config), None

        # No config is a warning, not an error (defaults work)
        return False, None, Bug(
            id=f"EE-CONFIG-MISSING-{exercise.id}",
            severity=BugSeverity.P3_LOW,
            category="TC-EE",
            exercise_id=exercise.id,
            description="ansible-navigator.yml not found (using defaults)",
            fix_recommendation="Create ansible-navigator.yml with EE configuration",
            verification_steps=[
                "ls ~/.ansible-navigator.yml",
                "ansible-navigator settings --effective"
            ]
        )

    def _parse_ee_config(
        self,
        config_path: str,
        ssh: SSHConnection
    ) -> Optional[Dict]:
        """Parse EE configuration from config file."""
        result = ssh.run(f"cat {config_path} 2>/dev/null", timeout=5)
        if not result.success:
            return None

        config = {}
        content = result.stdout

        # Extract execution-environment settings
        ee_image_match = re.search(
            r'execution-environment:\s*\n.*?image:\s*["\']?([^\s"\'\n]+)',
            content,
            re.MULTILINE | re.DOTALL
        )
        if ee_image_match:
            config['image'] = ee_image_match.group(1)

        # Extract pull policy
        pull_policy_match = re.search(
            r'pull:\s*\n.*?policy:\s*([^\s\n]+)',
            content,
            re.MULTILINE | re.DOTALL
        )
        if pull_policy_match:
            config['pull_policy'] = pull_policy_match.group(1)

        # Extract container runtime
        runtime_match = re.search(
            r'container-engine:\s*([^\s\n]+)',
            content,
            re.MULTILINE
        )
        if runtime_match:
            config['container_engine'] = runtime_match.group(1)

        return config if config else None

    def _check_container_runtime(
        self,
        exercise_id: str,
        ssh: SSHConnection
    ) -> Tuple[bool, Optional[str], Optional[Bug]]:
        """Check for podman or docker."""
        # Check podman first (preferred for RHEL)
        result = ssh.run("which podman && podman --version", timeout=10)
        if result.success:
            version_match = re.search(r'podman version (\S+)', result.stdout)
            version = version_match.group(1) if version_match else "unknown"
            return True, f"podman {version}", None

        # Check docker
        result = ssh.run("which docker && docker --version", timeout=10)
        if result.success:
            version_match = re.search(r'Docker version (\S+)', result.stdout)
            version = version_match.group(1) if version_match else "unknown"
            return True, f"docker {version}", None

        return False, None, Bug(
            id=f"EE-RUNTIME-MISSING-{exercise_id}",
            severity=BugSeverity.P1_CRITICAL,
            category="TC-EE",
            exercise_id=exercise_id,
            description="No container runtime (podman/docker) found",
            fix_recommendation="Install podman: dnf install podman",
            verification_steps=[
                "which podman",
                "podman --version",
                "dnf install podman"
            ]
        )

    def _check_ee_images(
        self,
        exercise: ExerciseContext,
        ssh: SSHConnection
    ) -> Tuple[bool, List[str], List[Bug]]:
        """Check for available EE images."""
        bugs = []
        available_images = []

        # List available images
        result = ssh.run("podman images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null || "
                        "docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null",
                        timeout=30)

        if result.success:
            images = result.stdout.strip().split('\n')
            images = [img.strip() for img in images if img.strip()]
            self._ee_image_cache = images

            # Check for EE images
            for image in images:
                for ee_pattern in self.DEFAULT_EE_IMAGES:
                    if ee_pattern in image or image.startswith('ee-'):
                        available_images.append(image)
                        break

        # Check if exercise requires specific EE
        required_ee = self._get_required_ee(exercise)
        if required_ee and required_ee not in available_images:
            # Check if any variation of the required EE exists
            found = False
            for img in available_images:
                if required_ee.split(':')[0] in img:
                    found = True
                    break

            if not found:
                bugs.append(Bug(
                    id=f"EE-IMAGE-MISSING-{exercise.id}",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-EE",
                    exercise_id=exercise.id,
                    description=f"Required EE image not found: {required_ee}",
                    fix_recommendation=f"Pull the EE image: podman pull {required_ee}",
                    verification_steps=[
                        f"podman pull {required_ee}",
                        "podman images | grep ee"
                    ]
                ))

        return len(available_images) > 0, available_images, bugs

    def _get_required_ee(self, exercise: ExerciseContext) -> Optional[str]:
        """Get required EE image from exercise configuration."""
        if not exercise.materials_dir or not exercise.materials_dir.exists():
            return None

        # Check ansible-navigator.yml in materials
        for config_name in ['ansible-navigator.yml', 'ansible-navigator.yaml']:
            config_path = exercise.materials_dir / config_name
            if config_path.exists():
                try:
                    content = config_path.read_text()
                    match = re.search(
                        r'execution-environment:\s*\n.*?image:\s*["\']?([^\s"\'\n]+)',
                        content,
                        re.MULTILINE | re.DOTALL
                    )
                    if match:
                        return match.group(1)
                except Exception:
                    pass

        return None

    def _check_registry_connectivity(
        self,
        exercise_id: str,
        ssh: SSHConnection
    ) -> Tuple[bool, List[Bug]]:
        """Check connectivity to container registries."""
        bugs = []

        # Test registry connectivity
        registries = [
            'registry.redhat.io',
            'quay.io',
        ]

        for registry in registries:
            result = ssh.run(
                f"curl -s -o /dev/null -w '%{{http_code}}' "
                f"--connect-timeout 5 https://{registry}/v2/",
                timeout=10
            )

            if result.success:
                status_code = result.stdout.strip()
                if status_code in ['200', '401', '404']:
                    # 401 is expected (auth required), 404 may be OK for some registries
                    continue

            # Can't reach registry
            bugs.append(Bug(
                id=f"EE-REGISTRY-{registry.replace('.', '-')}-{exercise_id}",
                severity=BugSeverity.P2_HIGH,
                category="TC-EE",
                exercise_id=exercise_id,
                description=f"Cannot reach container registry: {registry}",
                fix_recommendation=f"Check network connectivity and proxy settings for {registry}",
                verification_steps=[
                    f"curl -I https://{registry}/v2/",
                    "Check proxy environment variables",
                    "podman login {registry}"
                ]
            ))

        return len(bugs) == 0, bugs
