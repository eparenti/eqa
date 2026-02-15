"""TC-CLEAN: Cleanup validation.

Tests that lab cleanup (finish) properly:
- Removes created resources
- Restores system to clean state
- Doesn't leave files/users/services behind
- Handles cleanup errors gracefully
"""

from datetime import datetime
from typing import List, Dict, Set, Optional
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext, ExerciseType
from ..clients.ssh import SSHConnection


class TC_CLEAN:
    """Cleanup validation test category."""

    # Common directories to check for leftover files
    CHECK_DIRS = [
        '/home/student',
        '/tmp',
        '/var/tmp',
    ]

    # File patterns that indicate exercise-created files
    EXERCISE_FILE_PATTERNS = [
        '*.yml',
        '*.yaml',
        '*.py',
        '*.sh',
        '*.cfg',
        '*.ini',
        '*.j2',
        'ansible.cfg',
        'inventory',
        'playbook*.yml',
        'hosts',
    ]

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test cleanup/finish functionality.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-CLEAN: Testing cleanup...")

        bugs_found = []
        start_time = datetime.now()

        # Step 1: Capture initial state (before lab start)
        print("   → Capturing initial state...")
        initial_state = self._capture_state(ssh, exercise.id)
        if not initial_state:
            print("   ⚠  Could not capture initial state")
            return TestResult(
                category="TC-CLEAN",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=0.0,
                details={'error': 'Could not capture initial state'}
            )

        # Step 2: Run lab start
        print("   → Starting lab...")
        start_result = ssh.run(f"lab start {exercise.lab_name}", timeout=120)
        if not start_result.success:
            bugs_found.append(Bug(
                id=f"CLEAN-START-001-{exercise.id}",
                severity=BugSeverity.P2_HIGH,
                category="TC-CLEAN",
                exercise_id=exercise.id,
                description=f"Lab start failed: {start_result.stderr[:200] if start_result.stderr else 'unknown error'}",
                fix_recommendation="Fix lab start script",
                verification_steps=[f"Run: lab start {exercise.lab_name}"]
            ))
            # Continue with cleanup test anyway

        # Step 3: Capture state after start
        print("   → Capturing post-start state...")
        post_start_state = self._capture_state(ssh, exercise.id)

        # Step 4: Create some resources (simulate student work)
        print("   → Simulating student work...")
        self._simulate_student_work(ssh, exercise)

        # Step 5: Capture state after work
        print("   → Capturing post-work state...")
        post_work_state = self._capture_state(ssh, exercise.id)

        # Step 6: Run lab finish
        print("   → Running lab finish...")
        finish_result = ssh.run(f"lab finish {exercise.lab_name}", timeout=120)
        if not finish_result.success:
            bugs_found.append(Bug(
                id=f"CLEAN-FINISH-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-CLEAN",
                exercise_id=exercise.id,
                description=f"Lab finish failed: {finish_result.stderr[:200] if finish_result.stderr else 'unknown error'}",
                fix_recommendation="Fix lab finish script",
                verification_steps=[f"Run: lab finish {exercise.lab_name}"]
            ))

        # Step 7: Capture state after cleanup
        print("   → Capturing post-cleanup state...")
        post_cleanup_state = self._capture_state(ssh, exercise.id)

        # Step 8: Compare states to find leftover resources
        print("   → Analyzing cleanup effectiveness...")
        leftover_files = self._find_leftovers(initial_state, post_cleanup_state)

        if leftover_files.get('files'):
            leftover_count = len(leftover_files['files'])
            if leftover_count > 0:
                # Only flag as critical if many files left behind
                severity = BugSeverity.P1_CRITICAL if leftover_count > 5 else BugSeverity.P2_HIGH
                bugs_found.append(Bug(
                    id=f"CLEAN-LEFTOVER-001-{exercise.id}",
                    severity=severity,
                    category="TC-CLEAN",
                    exercise_id=exercise.id,
                    description=f"Cleanup left {leftover_count} file(s) behind",
                    fix_recommendation="Update finish script to remove created files",
                    verification_steps=[
                        f"Run: lab finish {exercise.lab_name}",
                        "Check for leftover files: " + ", ".join(leftover_files['files'][:5])
                    ]
                ))
                print(f"   ⚠  Found {leftover_count} leftover files")

        if leftover_files.get('users'):
            for user in leftover_files['users']:
                bugs_found.append(Bug(
                    id=f"CLEAN-USER-{user}-{exercise.id}",
                    severity=BugSeverity.P1_CRITICAL,
                    category="TC-CLEAN",
                    exercise_id=exercise.id,
                    description=f"Cleanup left user '{user}' behind",
                    fix_recommendation=f"Add 'userdel {user}' to finish script",
                    verification_steps=[
                        f"Run: lab finish {exercise.lab_name}",
                        f"Check: id {user}"
                    ]
                ))

        if leftover_files.get('services'):
            for service in leftover_files['services']:
                bugs_found.append(Bug(
                    id=f"CLEAN-SERVICE-{service}-{exercise.id}",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-CLEAN",
                    exercise_id=exercise.id,
                    description=f"Cleanup left service '{service}' running",
                    fix_recommendation=f"Add service cleanup to finish script",
                    verification_steps=[
                        f"Run: lab finish {exercise.lab_name}",
                        f"Check: systemctl is-active {service}"
                    ]
                ))

        # Step 9: Test that lab can start again after finish
        print("   → Testing restart capability...")
        restart_result = ssh.run(f"lab start {exercise.lab_name}", timeout=120)
        if not restart_result.success:
            bugs_found.append(Bug(
                id=f"CLEAN-RESTART-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-CLEAN",
                exercise_id=exercise.id,
                description="Lab cannot restart after finish - incomplete cleanup",
                fix_recommendation="Fix finish script to fully reset state",
                verification_steps=[
                    f"Run: lab finish {exercise.lab_name}",
                    f"Run: lab start {exercise.lab_name}",
                    "Should succeed"
                ]
            ))
        else:
            print("   ✓ Lab restart successful")
            # Clean up after test
            ssh.run(f"lab finish {exercise.lab_name}", timeout=120)

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-CLEAN",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'initial_file_count': len(initial_state.get('files', [])),
                'post_cleanup_file_count': len(post_cleanup_state.get('files', [])),
                'leftover_files': len(leftover_files.get('files', [])),
                'leftover_users': len(leftover_files.get('users', [])),
                'leftover_services': len(leftover_files.get('services', []))
            }
        )

    def _capture_state(self, ssh: SSHConnection, exercise_id: str) -> Dict:
        """Capture current system state.

        Returns dict with:
        - files: List of files in checked directories
        - users: List of system users
        - services: List of running services
        """
        state = {
            'files': [],
            'users': [],
            'services': [],
        }

        # Strip -ge or -lab suffix for directory lookup
        base_id = exercise_id.removesuffix('-ge').removesuffix('-lab')

        # Get files in exercise working directory
        work_dirs = [
            f'/home/student/{base_id}',
            f'/home/student/{exercise_id}',
            '/home/student/ansible',
        ]

        for work_dir in work_dirs:
            result = ssh.run(f"find {work_dir} -type f 2>/dev/null | head -100", timeout=10)
            if result.success and result.stdout.strip():
                files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
                state['files'].extend(files)

        # Get non-system users (UID >= 1000)
        result = ssh.run("awk -F: '$3 >= 1000 && $3 < 65534 {print $1}' /etc/passwd", timeout=5)
        if result.success:
            users = [u.strip() for u in result.stdout.strip().split('\n') if u.strip()]
            # Filter out common default users
            default_users = ['student', 'nobody', 'nfsnobody']
            state['users'] = [u for u in users if u not in default_users]

        # Get running services related to ansible or lab
        result = ssh.run("systemctl list-units --type=service --state=running --no-legend | awk '{print $1}'", timeout=10)
        if result.success:
            services = [s.strip() for s in result.stdout.strip().split('\n') if s.strip()]
            # Filter to exercise-related services
            state['services'] = [s for s in services if base_id in s.lower()]

        return state

    def _simulate_student_work(self, ssh: SSHConnection, exercise: ExerciseContext):
        """Simulate some student work for cleanup testing."""
        base_id = exercise.id.removesuffix('-ge').removesuffix('-lab')

        # Create a simple test file in the working directory
        work_dir = f"/home/student/{base_id}"
        ssh.run(f"mkdir -p {work_dir}", timeout=5)
        ssh.run(f"touch {work_dir}/.cleanup-test-marker", timeout=5)

        # If there are solution files, we could apply them here
        # but for cleanup testing, just creating marker files is enough

    def _find_leftovers(self, initial_state: Dict, post_cleanup_state: Dict) -> Dict:
        """Find resources that weren't cleaned up.

        Args:
            initial_state: State before lab start
            post_cleanup_state: State after lab finish

        Returns:
            Dict with leftover files, users, services
        """
        leftovers = {
            'files': [],
            'users': [],
            'services': [],
        }

        # Find files that exist after cleanup but didn't exist initially
        initial_files = set(initial_state.get('files', []))
        post_files = set(post_cleanup_state.get('files', []))
        leftover_files = post_files - initial_files

        # Filter to only exercise-related files (not general system files)
        for f in leftover_files:
            # Skip system and cache files
            if '/cache/' in f or '/.cache/' in f:
                continue
            if f.endswith('.pyc') or '__pycache__' in f:
                continue
            if '/site-packages/' in f:
                continue
            leftovers['files'].append(f)

        # Find users created during exercise
        initial_users = set(initial_state.get('users', []))
        post_users = set(post_cleanup_state.get('users', []))
        leftovers['users'] = list(post_users - initial_users)

        # Find services started during exercise
        initial_services = set(initial_state.get('services', []))
        post_services = set(post_cleanup_state.get('services', []))
        leftovers['services'] = list(post_services - initial_services)

        return leftovers
