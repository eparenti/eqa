"""TC-AAP: Ansible Automation Platform Controller validation.

Tests AAP-specific exercises:
- Controller connectivity
- Authentication
- Organization/project/inventory access
- Job template validation
- Workflow template validation
- Execution environment checks
"""

import re
from datetime import datetime
from typing import List, Dict, Optional
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext
from ..clients.ssh import SSHConnection


class TC_AAP:
    """AAP Controller validation test category."""

    # Default AAP Controller URL patterns
    CONTROLLER_HOSTS = [
        'controller.lab.example.com',
        'tower.lab.example.com',
        'automation-controller.lab.example.com',
    ]

    def __init__(self, controller_host: str = None):
        """Initialize AAP tester.

        Args:
            controller_host: Hostname of AAP Controller (auto-detected if not specified)
        """
        self.controller_host = controller_host

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test AAP Controller connectivity and exercise configuration.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-AAP: Testing AAP Controller...")

        bugs_found = []
        start_time = datetime.now()

        # Check if this is an AAP-related exercise
        if not self._is_aap_exercise(exercise):
            print("   ⏭  Skipping (not an AAP exercise)")
            return TestResult(
                category="TC-AAP",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=0.0,
                details={'skipped': True, 'reason': 'Not an AAP exercise'}
            )

        # Step 1: Detect controller host
        print("   → Detecting AAP Controller...")
        controller = self._detect_controller(ssh)
        if not controller:
            print("   ⚠  No AAP Controller detected")
            return TestResult(
                category="TC-AAP",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=0.0,
                details={'skipped': True, 'reason': 'No AAP Controller detected'}
            )

        print(f"   ✓ Found controller: {controller}")

        # Step 2: Test network connectivity
        print("   → Testing network connectivity...")
        connectivity_bugs = self._test_connectivity(controller, ssh)
        bugs_found.extend(connectivity_bugs)

        # Step 3: Test awx CLI availability
        print("   → Checking awx CLI...")
        cli_bugs = self._test_awx_cli(ssh)
        bugs_found.extend(cli_bugs)

        # Step 4: Test authentication
        print("   → Testing authentication...")
        auth_bugs = self._test_authentication(controller, ssh)
        bugs_found.extend(auth_bugs)

        # If authentication failed, skip remaining tests
        if any(b.id.startswith('AAP-AUTH') for b in auth_bugs):
            print("   ⏭  Skipping remaining tests (auth failed)")
        else:
            # Step 5: Test organizations
            print("   → Checking organizations...")
            org_bugs = self._test_organizations(ssh)
            bugs_found.extend(org_bugs)

            # Step 6: Test projects
            print("   → Checking projects...")
            project_bugs = self._test_projects(exercise, ssh)
            bugs_found.extend(project_bugs)

            # Step 7: Test inventories
            print("   → Checking inventories...")
            inventory_bugs = self._test_inventories(exercise, ssh)
            bugs_found.extend(inventory_bugs)

            # Step 8: Test job templates
            print("   → Checking job templates...")
            template_bugs = self._test_job_templates(exercise, ssh)
            bugs_found.extend(template_bugs)

            # Step 9: Test execution environments
            print("   → Checking execution environments...")
            ee_bugs = self._test_execution_environments(ssh)
            bugs_found.extend(ee_bugs)

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-AAP",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'controller_host': controller,
                'tests_run': 9 - (1 if any(b.id.startswith('AAP-AUTH') for b in auth_bugs) else 0)
            }
        )

    def _is_aap_exercise(self, exercise: ExerciseContext) -> bool:
        """Check if exercise is AAP-related."""
        # Check exercise ID and lesson code for AAP indicators
        aap_indicators = [
            'aap', 'tower', 'controller', 'automation-platform',
            'automation_platform', 'awx', 'ee-', 'execution-environment'
        ]

        exercise_id_lower = exercise.id.lower()
        lesson_lower = exercise.lesson_code.lower()
        title_lower = exercise.title.lower() if exercise.title else ''

        for indicator in aap_indicators:
            if indicator in exercise_id_lower:
                return True
            if indicator in lesson_lower:
                return True
            if indicator in title_lower:
                return True

        # Check for AAP-related courses
        aap_courses = ['DO374', 'DO467', 'DO447', 'AAP', 'AA']
        for course in aap_courses:
            if course.upper() in lesson_lower.upper():
                return True

        return False

    def _detect_controller(self, ssh: SSHConnection) -> Optional[str]:
        """Detect AAP Controller host."""
        # Check provided controller first
        if self.controller_host:
            result = ssh.run(f"ping -c 1 -W 2 {self.controller_host}", timeout=5)
            if result.success:
                return self.controller_host

        # Try common controller hostnames
        for host in self.CONTROLLER_HOSTS:
            result = ssh.run(f"ping -c 1 -W 2 {host}", timeout=5)
            if result.success:
                return host

        # Check /etc/hosts for controller entries
        result = ssh.run("grep -i controller /etc/hosts | awk '{print $2}' | head -1", timeout=5)
        if result.success and result.stdout.strip():
            host = result.stdout.strip()
            return host

        # Check if awx CLI has configured host
        result = ssh.run("awx config 2>/dev/null | grep host | awk '{print $2}'", timeout=5)
        if result.success and result.stdout.strip():
            return result.stdout.strip()

        return None

    def _test_connectivity(self, controller: str, ssh: SSHConnection) -> List[Bug]:
        """Test network connectivity to controller."""
        bugs = []

        # Test HTTPS port (443)
        result = ssh.run(f"timeout 5 bash -c 'echo > /dev/tcp/{controller}/443'", timeout=10)
        if not result.success:
            bugs.append(Bug(
                id=f"AAP-CONN-443",
                severity=BugSeverity.P0_BLOCKER,
                category="TC-AAP",
                exercise_id="",
                description=f"Cannot connect to AAP Controller on port 443: {controller}",
                fix_recommendation="Verify controller is running and firewall allows HTTPS",
                verification_steps=[
                    f"Test: curl -k https://{controller}",
                    "Check controller pod/service status"
                ]
            ))
        else:
            print(f"      ✓ Port 443 accessible")

        # Test API endpoint
        result = ssh.run(f"curl -k -s -o /dev/null -w '%{{http_code}}' https://{controller}/api/v2/ping/", timeout=10)
        if result.success and result.stdout.strip() == '200':
            print(f"      ✓ API responding")
        else:
            bugs.append(Bug(
                id=f"AAP-API-001",
                severity=BugSeverity.P0_BLOCKER,
                category="TC-AAP",
                exercise_id="",
                description=f"AAP Controller API not responding: {controller}",
                fix_recommendation="Check controller application status",
                verification_steps=[
                    f"Test: curl -k https://{controller}/api/v2/ping/",
                    "Check controller logs"
                ]
            ))

        return bugs

    def _test_awx_cli(self, ssh: SSHConnection) -> List[Bug]:
        """Test awx CLI availability and version."""
        bugs = []

        result = ssh.run("which awx", timeout=5)
        if not result.success:
            bugs.append(Bug(
                id=f"AAP-CLI-001",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-AAP",
                exercise_id="",
                description="awx CLI not installed",
                fix_recommendation="Install awxkit: pip install awxkit",
                verification_steps=["Run: pip install awxkit", "Verify: which awx"]
            ))
        else:
            print(f"      ✓ awx CLI installed")

            # Check version
            result = ssh.run("awx --version", timeout=5)
            if result.success:
                print(f"      ✓ Version: {result.stdout.strip()}")

        return bugs

    def _test_authentication(self, controller: str, ssh: SSHConnection) -> List[Bug]:
        """Test authentication to controller."""
        bugs = []

        # Try to get current user info
        result = ssh.run("awx me 2>&1", timeout=10)
        if not result.success or 'error' in result.stdout.lower():
            # Check if credentials are configured
            cred_result = ssh.run("test -f ~/.tower_cli.cfg || test -n \"$CONTROLLER_HOST\"", timeout=5)
            if not cred_result.success:
                bugs.append(Bug(
                    id=f"AAP-AUTH-CONFIG",
                    severity=BugSeverity.P1_CRITICAL,
                    category="TC-AAP",
                    exercise_id="",
                    description="AAP credentials not configured",
                    fix_recommendation="Configure awx CLI with controller credentials",
                    verification_steps=[
                        "Create ~/.tower_cli.cfg with host, username, password",
                        "Or set CONTROLLER_HOST, CONTROLLER_USERNAME, CONTROLLER_PASSWORD env vars"
                    ]
                ))
            else:
                bugs.append(Bug(
                    id=f"AAP-AUTH-FAIL",
                    severity=BugSeverity.P1_CRITICAL,
                    category="TC-AAP",
                    exercise_id="",
                    description="AAP authentication failed",
                    fix_recommendation="Verify credentials are correct",
                    verification_steps=[
                        "Run: awx me",
                        "Check username/password in ~/.tower_cli.cfg"
                    ]
                ))
        else:
            print(f"      ✓ Authentication successful")

        return bugs

    def _test_organizations(self, ssh: SSHConnection) -> List[Bug]:
        """Test organization access."""
        bugs = []

        result = ssh.run("awx organizations list --format json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(len(d.get(\"results\",[])))'", timeout=15)
        if result.success and result.stdout.strip().isdigit():
            org_count = int(result.stdout.strip())
            print(f"      ✓ {org_count} organization(s) accessible")
            if org_count == 0:
                bugs.append(Bug(
                    id=f"AAP-ORG-NONE",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-AAP",
                    exercise_id="",
                    description="No organizations accessible",
                    fix_recommendation="Verify user has organization access",
                    verification_steps=["Run: awx organizations list", "Check RBAC settings"]
                ))
        else:
            print(f"      ⚠  Could not list organizations")

        return bugs

    def _test_projects(self, exercise: ExerciseContext, ssh: SSHConnection) -> List[Bug]:
        """Test project access."""
        bugs = []

        result = ssh.run("awx projects list --format json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(len(d.get(\"results\",[])))'", timeout=15)
        if result.success and result.stdout.strip().isdigit():
            project_count = int(result.stdout.strip())
            print(f"      ✓ {project_count} project(s) accessible")

            # Check for exercise-specific project
            base_id = exercise.id.removesuffix('-ge').removesuffix('-lab')
            result = ssh.run(f"awx projects list --name '{base_id}' --format json 2>/dev/null", timeout=15)
            if result.success and '"name":' in result.stdout:
                print(f"      ✓ Found exercise project: {base_id}")

        return bugs

    def _test_inventories(self, exercise: ExerciseContext, ssh: SSHConnection) -> List[Bug]:
        """Test inventory access."""
        bugs = []

        result = ssh.run("awx inventory list --format json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(len(d.get(\"results\",[])))'", timeout=15)
        if result.success and result.stdout.strip().isdigit():
            inv_count = int(result.stdout.strip())
            print(f"      ✓ {inv_count} inventory/inventories accessible")

            if inv_count == 0:
                bugs.append(Bug(
                    id=f"AAP-INV-NONE",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-AAP",
                    exercise_id="",
                    description="No inventories accessible",
                    fix_recommendation="Create or grant access to inventories",
                    verification_steps=["Run: awx inventory list", "Check RBAC settings"]
                ))

        return bugs

    def _test_job_templates(self, exercise: ExerciseContext, ssh: SSHConnection) -> List[Bug]:
        """Test job template access."""
        bugs = []

        result = ssh.run("awx job_templates list --format json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(len(d.get(\"results\",[])))'", timeout=15)
        if result.success and result.stdout.strip().isdigit():
            template_count = int(result.stdout.strip())
            print(f"      ✓ {template_count} job template(s) accessible")

            # Check for exercise-specific template
            base_id = exercise.id.removesuffix('-ge').removesuffix('-lab')
            result = ssh.run(f"awx job_templates list --name '{base_id}' --format json 2>/dev/null", timeout=15)
            if result.success and '"name":' in result.stdout:
                print(f"      ✓ Found exercise template: {base_id}")

        return bugs

    def _test_execution_environments(self, ssh: SSHConnection) -> List[Bug]:
        """Test execution environment availability."""
        bugs = []

        result = ssh.run("awx execution_environments list --format json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(len(d.get(\"results\",[])))'", timeout=15)
        if result.success and result.stdout.strip().isdigit():
            ee_count = int(result.stdout.strip())
            print(f"      ✓ {ee_count} execution environment(s) available")

            if ee_count == 0:
                bugs.append(Bug(
                    id=f"AAP-EE-NONE",
                    severity=BugSeverity.P1_CRITICAL,
                    category="TC-AAP",
                    exercise_id="",
                    description="No execution environments available",
                    fix_recommendation="Configure at least one execution environment",
                    verification_steps=[
                        "Run: awx execution_environments list",
                        "Add EE via Controller UI or API"
                    ]
                ))
        else:
            # EE list might not be available in older versions
            print(f"      ⚠  Could not list execution environments (may not be supported)")

        return bugs


class TC_AAP_JOBS(TC_AAP):
    """Extended AAP testing with job execution validation."""

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """Run extended AAP tests including job execution."""
        # Run base tests first
        base_result = super().test(exercise, ssh)

        if not base_result.details.get('skipped'):
            bugs_found = list(base_result.bugs_found)
            start_time = datetime.now()

            # Test job execution if no critical bugs
            if not any(b.severity in [BugSeverity.P0_BLOCKER, BugSeverity.P1_CRITICAL] for b in bugs_found):
                print("   → Testing job execution...")
                job_bugs = self._test_job_execution(exercise, ssh)
                bugs_found.extend(job_bugs)

            duration = base_result.duration_seconds + (datetime.now() - start_time).total_seconds()

            return TestResult(
                category="TC-AAP",
                exercise_id=exercise.id,
                passed=(len(bugs_found) == 0),
                timestamp=datetime.now().isoformat(),
                duration_seconds=duration,
                bugs_found=bugs_found,
                details={
                    **base_result.details,
                    'job_execution_tested': True
                }
            )

        return base_result

    def _test_job_execution(self, exercise: ExerciseContext, ssh: SSHConnection) -> List[Bug]:
        """Test that a sample job can be launched."""
        bugs = []

        # Find a simple job template to test
        result = ssh.run("awx job_templates list --format json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); r=d.get(\"results\",[]); print(r[0][\"id\"] if r else \"\")'", timeout=15)

        if result.success and result.stdout.strip().isdigit():
            template_id = result.stdout.strip()
            print(f"      Testing job template ID: {template_id}")

            # Launch job
            launch_result = ssh.run(f"awx job_templates launch {template_id} --wait --format json 2>/dev/null", timeout=300)
            if launch_result.success and '"status": "successful"' in launch_result.stdout:
                print(f"      ✓ Job execution successful")
            elif launch_result.success and '"status": "failed"' in launch_result.stdout:
                bugs.append(Bug(
                    id=f"AAP-JOB-FAIL",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-AAP",
                    exercise_id="",
                    description="Sample job execution failed",
                    fix_recommendation="Check job template configuration and playbook",
                    verification_steps=["Run job from Controller UI", "Check job output for errors"]
                ))
            else:
                print(f"      ⚠  Job execution status unclear")
        else:
            print(f"      ⏭  No job templates to test")

        return bugs
