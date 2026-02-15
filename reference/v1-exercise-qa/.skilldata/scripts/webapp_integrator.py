#!/usr/bin/env python3
"""
WebApp Integrator - Integrates chrome_webapp_tester into main testing flow.

Auto-detects webapp exercises and runs appropriate tests.
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.test_result import TestResult, ExerciseContext
from scripts.chrome_webapp_tester import ChromeWebAppTester


class WebAppIntegrator:
    """
    Integrates webapp testing into main exercise testing flow.

    Auto-detects webapp exercises and executes appropriate tests.
    """

    def __init__(self, course_context=None):
        """
        Initialize webapp integrator.

        Args:
            course_context: Optional CourseContext for auto-detection
        """
        self.context = course_context
        self.webapp_keywords = [
            'web console', 'aap', 'ansible automation platform',
            'openshift console', 'satellite ui', 'browser',
            'web interface', 'web ui', 'cockpit'
        ]

    def test_webapp_exercise(self, exercise: ExerciseContext, headless: bool = True) -> TestResult:
        """
        Run webapp tests for exercise.

        Args:
            exercise: Exercise context
            headless: Run browser in headless mode

        Returns:
            TestResult with webapp testing results
        """
        start_time = datetime.now()

        print(f"\n🌐 Testing webapp components for {exercise.id}")

        # Initialize webapp tester
        tester = ChromeWebAppTester(
            exercise_name=exercise.id,
            mode="auto",
            headless=headless
        )

        if not tester.setup_driver():
            end_time = datetime.now()
            return TestResult(
                category="TC-WEB",
                exercise_id=exercise.id,
                passed=False,
                timestamp=start_time.isoformat(),
                duration_seconds=(end_time - start_time).total_seconds(),
                error_message="Failed to setup Chrome WebDriver"
            )

        try:
            # Detect platform and run appropriate tests
            platform = self._detect_platform(exercise)

            if platform == "AAP":
                results = self._test_aap(exercise, tester)
            elif platform == "OpenShift":
                results = self._test_openshift(exercise, tester)
            elif platform == "Satellite":
                results = self._test_satellite(exercise, tester)
            else:
                results = self._test_generic_webapp(exercise, tester)

            # Get test summary
            summary = tester.get_summary()

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return TestResult(
                category="TC-WEB",
                exercise_id=exercise.id,
                passed=(summary['failed'] == 0),
                timestamp=start_time.isoformat(),
                duration_seconds=duration,
                details={
                    'platform': platform,
                    'tests_passed': summary['passed'],
                    'tests_failed': summary['failed'],
                    'screenshots_captured': len(tester.screenshots)
                },
                screenshots=tester.screenshots
            )

        finally:
            tester.cleanup()

    def _detect_platform(self, exercise: ExerciseContext) -> str:
        """Detect webapp platform from exercise content."""
        content_lower = exercise.epub_content.lower() if exercise.epub_content else ""

        if 'ansible automation platform' in content_lower or 'aap' in content_lower:
            return "AAP"
        elif 'openshift' in content_lower:
            return "OpenShift"
        elif 'satellite' in content_lower:
            return "Satellite"
        else:
            return "Generic"

    def _test_aap(self, exercise: ExerciseContext, tester: ChromeWebAppTester) -> List:
        """Run AAP-specific tests."""
        results = []

        # Determine AAP URL (standard lab URL)
        aap_url = "https://aap.lab.example.com/"

        # Test 1: Accessibility
        results.append(tester.navigate(aap_url))

        # Test 2: Login page
        results.append(tester.verify_text("Automation Platform"))

        # Capture screenshot
        results.append(tester.capture_screenshot("aap_login_page"))

        return results

    def _test_openshift(self, exercise: ExerciseContext, tester: ChromeWebAppTester) -> List:
        """Run OpenShift-specific tests."""
        results = []

        # Determine OpenShift console URL
        console_url = "https://console-openshift-console.apps.ocp4.example.com/"

        # Test 1: Accessibility
        results.append(tester.navigate(console_url))

        # Test 2: Console accessible
        results.append(tester.verify_text("OpenShift"))

        # Capture screenshot
        results.append(tester.capture_screenshot("openshift_console"))

        return results

    def _test_satellite(self, exercise: ExerciseContext, tester: ChromeWebAppTester) -> List:
        """Run Satellite-specific tests."""
        results = []

        # Determine Satellite URL
        satellite_url = "https://satellite.lab.example.com/"

        # Test 1: Accessibility
        results.append(tester.navigate(satellite_url))

        # Test 2: Satellite UI
        results.append(tester.verify_text("Satellite"))

        # Capture screenshot
        results.append(tester.capture_screenshot("satellite_ui"))

        return results

    def _test_generic_webapp(self, exercise: ExerciseContext, tester: ChromeWebAppTester) -> List:
        """Run generic webapp tests."""
        results = []

        # Try to extract URL from exercise content
        url = self._extract_url_from_content(exercise.epub_content)

        if url:
            results.append(tester.navigate(url))
            results.append(tester.capture_screenshot("webapp"))

        return results

    def _extract_url_from_content(self, content: str) -> Optional[str]:
        """Extract URL from exercise content."""
        import re

        if not content:
            return None

        # Look for URLs in content
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+[^\s<>"{}|\\^`\[\].,;!?]'
        matches = re.findall(url_pattern, content)

        if matches:
            return matches[0]

        return None


def main():
    """Test webapp integrator."""
    import argparse
    from lib.test_result import ExerciseType

    parser = argparse.ArgumentParser(description="Test webapp integration")
    parser.add_argument("exercise_id", help="Exercise ID")
    parser.add_argument("--content", help="Path to exercise content file")

    args = parser.parse_args()

    # Load content if provided
    content = ""
    if args.content:
        with open(args.content, 'r') as f:
            content = f.read()

    # Create exercise context
    exercise = ExerciseContext(
        id=args.exercise_id,
        type=ExerciseType.GUIDED_EXERCISE,
        lesson_code="test",
        chapter=1,
        chapter_title="Test",
        title=args.exercise_id,
        epub_content=content
    )

    # Run webapp tests
    integrator = WebAppIntegrator()
    result = integrator.test_webapp_exercise(exercise)

    print("\n" + "=" * 60)
    print(f"Result: {'PASS' if result.passed else 'FAIL'}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    if result.details:
        print(f"Platform: {result.details.get('platform', 'Unknown')}")
        print(f"Tests Passed: {result.details.get('tests_passed', 0)}")
        print(f"Tests Failed: {result.details.get('tests_failed', 0)}")

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
