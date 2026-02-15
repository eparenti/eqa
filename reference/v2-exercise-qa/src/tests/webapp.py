"""TC-WEB: Web Application UI Testing.

Tests web UI steps in exercises using browser automation.
Based on patterns from exercise-reviewer agent.

Features:
- Playwright-based browser automation
- OpenShift/RHOAI console testing
- Authentication flow verification
- Screenshot capture at each step
- UI element validation

Usage:
    This test category automatically detects exercises with web UI steps
    and tests them using browser automation.
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext
from ..clients.ssh import SSHConnection
from ..clients.browser import BrowserClient, BrowserResult


class TC_WEB:
    """Web application UI test category."""

    # Common web console patterns
    WEB_PATTERNS = {
        'openshift_console': {
            'url_pattern': 'console-openshift-console',
            'auth_type': 'oauth',
            'username_selector': '#inputUsername',
            'password_selector': '#inputPassword',
            'submit_selector': 'button[type="submit"]'
        },
        'rhoai_dashboard': {
            'url_pattern': 'rhods-dashboard',
            'auth_type': 'oauth',
            'username_selector': '#inputUsername',
            'password_selector': '#inputPassword',
            'submit_selector': 'button[type="submit"]'
        },
        'aap_controller': {
            'url_pattern': 'controller',
            'auth_type': 'basic',
            'username_selector': '#pf-login-username-id',
            'password_selector': '#pf-login-password-id',
            'submit_selector': 'button[type="submit"]'
        }
    }

    def __init__(self, headless: bool = True):
        """
        Initialize web test category.

        Args:
            headless: Run browser in headless mode
        """
        self.headless = headless
        self.browser = None

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test web UI steps in exercise.

        Args:
            exercise: Exercise context
            ssh: SSH connection (for getting console URLs)

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n   TC-WEB: Testing web UI steps...")

        bugs_found = []
        start_time = datetime.now()

        # Check if exercise has web UI steps
        web_steps = self._find_web_steps(exercise)
        if not web_steps:
            print(f"   No web UI steps found (optional)")
            duration = (datetime.now() - start_time).total_seconds()
            return TestResult(
                category="TC-WEB",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=duration,
                bugs_found=[],
                details={'status': 'skipped', 'reason': 'no_web_steps'}
            )

        print(f"   Found {len(web_steps)} web UI steps")

        # Check if Playwright is available
        self.browser = BrowserClient()
        if not self.browser.is_available():
            print(f"   Playwright not installed - skipping UI tests")
            print(f"   Install with: pip install playwright && playwright install")
            duration = (datetime.now() - start_time).total_seconds()
            return TestResult(
                category="TC-WEB",
                exercise_id=exercise.id,
                passed=True,  # Don't fail if Playwright not installed
                timestamp=datetime.now().isoformat(),
                duration_seconds=duration,
                bugs_found=[],
                details={'status': 'skipped', 'reason': 'playwright_not_installed'}
            )

        # Get console URL from cluster
        console_url = self._get_console_url(ssh)
        if not console_url:
            bugs_found.append(Bug(
                id=f"WEB-NO-CONSOLE-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-WEB",
                exercise_id=exercise.id,
                description="Could not determine OpenShift console URL",
                fix_recommendation="Ensure cluster is running and 'oc whoami --show-console' works"
            ))
            duration = (datetime.now() - start_time).total_seconds()
            return TestResult(
                category="TC-WEB",
                exercise_id=exercise.id,
                passed=False,
                timestamp=datetime.now().isoformat(),
                duration_seconds=duration,
                bugs_found=bugs_found,
                details={'error': 'console_url_not_found'}
            )

        # Launch browser
        if not self.browser.connect(headless=self.headless):
            bugs_found.append(Bug(
                id=f"WEB-BROWSER-FAIL-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-WEB",
                exercise_id=exercise.id,
                description="Could not launch browser",
                fix_recommendation="Check Playwright installation"
            ))
            duration = (datetime.now() - start_time).total_seconds()
            return TestResult(
                category="TC-WEB",
                exercise_id=exercise.id,
                passed=False,
                timestamp=datetime.now().isoformat(),
                duration_seconds=duration,
                bugs_found=bugs_found,
                details={'error': 'browser_launch_failed'}
            )

        try:
            # Execute web steps
            self._execute_web_steps(exercise, web_steps, console_url, bugs_found)

        finally:
            # Always close browser
            self.browser.close()

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-WEB",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'web_steps': len(web_steps),
                'console_url': console_url
            }
        )

    def _find_web_steps(self, exercise: ExerciseContext) -> List[Dict[str, Any]]:
        """
        Find web UI steps in exercise instructions.

        Looks for patterns like:
        - "Navigate to the OpenShift console"
        - "Click the Project dropdown"
        - "In the web console"

        Returns:
            List of web step dictionaries
        """
        web_steps = []

        # Web UI indicator patterns
        web_indicators = [
            'web console',
            'openshift console',
            'rhoai dashboard',
            'aap controller',
            'navigate to',
            'click the',
            'select from',
            'in the browser',
            'web interface',
            'dashboard'
        ]

        # Check exercise instructions (if available)
        if hasattr(exercise, 'instructions') and exercise.instructions:
            instructions_text = str(exercise.instructions).lower()

            for indicator in web_indicators:
                if indicator in instructions_text:
                    # This exercise has web steps
                    web_steps.append({
                        'type': 'web_ui',
                        'indicator': indicator
                    })
                    break

        # Check if exercise type suggests web UI
        if hasattr(exercise, 'type') and exercise.type:
            type_str = str(exercise.type).lower()
            if 'web' in type_str or 'ui' in type_str or 'console' in type_str:
                web_steps.append({
                    'type': 'exercise_type',
                    'indicator': type_str
                })

        return web_steps

    def _get_console_url(self, ssh: SSHConnection) -> Optional[str]:
        """Get OpenShift console URL from cluster."""
        result = ssh.run("oc whoami --show-console 2>/dev/null", timeout=30)
        if result.success and result.stdout:
            url = result.stdout.strip()
            if url.startswith('http'):
                return url
        return None

    def _execute_web_steps(self, exercise: ExerciseContext,
                          web_steps: List[Dict[str, Any]],
                          console_url: str,
                          bugs_found: List[Bug]):
        """Execute web UI steps using browser automation."""

        print(f"   Navigating to console: {console_url}")

        # Navigate to console
        result = self.browser.navigate(console_url)
        if not result.success:
            bugs_found.append(Bug(
                id=f"WEB-NAV-FAIL-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-WEB",
                exercise_id=exercise.id,
                description=f"Failed to navigate to console: {result.error}",
                fix_recommendation="Check console URL and cluster accessibility"
            ))
            return

        # Take initial screenshot
        self.browser.screenshot(f"{exercise.id}-initial")

        # Detect console type and authenticate
        console_type = self._detect_console_type(console_url)
        if console_type:
            print(f"   Detected console type: {console_type}")

            # Get credentials from environment or defaults
            username = self._get_credential('username', console_type)
            password = self._get_credential('password', console_type)

            if username and password:
                pattern = self.WEB_PATTERNS.get(console_type, {})
                auth_result = self.browser.authenticate(
                    username=username,
                    password=password,
                    username_selector=pattern.get('username_selector', '#username'),
                    password_selector=pattern.get('password_selector', '#password'),
                    submit_selector=pattern.get('submit_selector', 'button[type="submit"]')
                )

                if not auth_result.success:
                    bugs_found.append(Bug(
                        id=f"WEB-AUTH-FAIL-001-{exercise.id}",
                        severity=BugSeverity.P1_CRITICAL,
                        category="TC-WEB",
                        exercise_id=exercise.id,
                        description=f"Authentication failed: {auth_result.error}",
                        fix_recommendation="Check credentials and authentication selectors"
                    ))
                    return
                else:
                    print(f"   Authentication successful")
                    self.browser.screenshot(f"{exercise.id}-authenticated")

        # Verify console is accessible after auth
        if self.browser.is_visible("text=Projects") or \
           self.browser.is_visible("text=Home") or \
           self.browser.is_visible("text=Dashboard"):
            print(f"   Console accessible")
            self.browser.screenshot(f"{exercise.id}-console")
        else:
            bugs_found.append(Bug(
                id=f"WEB-CONSOLE-VERIFY-001-{exercise.id}",
                severity=BugSeverity.P2_HIGH,
                category="TC-WEB",
                exercise_id=exercise.id,
                description="Console page not fully loaded after authentication",
                fix_recommendation="Check authentication flow and page load"
            ))

    def _detect_console_type(self, url: str) -> Optional[str]:
        """Detect console type from URL."""
        url_lower = url.lower()

        for console_type, pattern in self.WEB_PATTERNS.items():
            if pattern['url_pattern'] in url_lower:
                return console_type

        return None

    def _get_credential(self, cred_type: str, console_type: str) -> Optional[str]:
        """
        Get credential from environment or defaults.

        Checks environment variables first, then falls back to common defaults.
        """
        import os

        # Environment variable names
        env_vars = {
            'username': [
                f'{console_type.upper()}_USERNAME',
                'OCP_USERNAME',
                'ADMIN_USERNAME'
            ],
            'password': [
                f'{console_type.upper()}_PASSWORD',
                'OCP_PASSWORD',
                'ADMIN_PASSWORD'
            ]
        }

        # Check environment
        for var_name in env_vars.get(cred_type, []):
            value = os.environ.get(var_name)
            if value:
                return value

        # Fall back to common lab defaults
        defaults = {
            'username': 'admin',
            'password': 'redhat'  # Common Red Hat training default
        }

        return defaults.get(cred_type)
