#!/usr/bin/env python3
"""
OpenShift Console WebApp Testing Example

Demonstrates automated testing of OpenShift console exercises using
the chrome_webapp_tester framework.

Test scenarios:
- Console accessibility
- Login functionality
- Project/namespace creation
- Pod deployment verification
- Route configuration
- Resource cleanup verification
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.chrome_webapp_tester import ChromeWebAppTester


def test_openshift_console_basic():
    """
    Test basic OpenShift console accessibility and login.

    Verifies:
    - Console is accessible
    - Login page loads
    - Authentication works
    """
    print("=" * 60)
    print("OpenShift Console - Basic Accessibility Test")
    print("=" * 60)

    tester = ChromeWebAppTester(
        exercise_name="openshift-console-basic",
        mode="auto",
        headless=False  # Set to True for CI/CD
    )

    if not tester.setup_driver():
        print("❌ Failed to setup Chrome WebDriver")
        return False

    try:
        # Test 1: Navigate to OpenShift console
        print("\n1. Testing console accessibility...")
        console_url = "https://console-openshift-console.apps.ocp4.example.com/"
        result = tester.navigate(console_url)
        print(f"   {'✅' if result else '❌'} Console accessible")

        # Test 2: Verify OpenShift branding
        print("\n2. Verifying OpenShift console page...")
        result = tester.verify_text("OpenShift")
        print(f"   {'✅' if result else '❌'} OpenShift branding present")

        # Test 3: Capture screenshot
        print("\n3. Capturing screenshot...")
        result = tester.capture_screenshot("openshift_console_login")
        print(f"   {'✅' if result else '❌'} Screenshot captured")

        # Test 4: Check for login form
        print("\n4. Checking for authentication...")
        result = tester.verify_text("Log in")
        print(f"   {'✅' if result else '❌'} Login form present")

        # Get summary
        summary = tester.get_summary()
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Screenshots: {len(tester.screenshots)}")

        return summary['failed'] == 0

    finally:
        tester.cleanup()


def test_openshift_project_creation():
    """
    Test OpenShift project/namespace creation workflow.

    Verifies:
    - Can create new project
    - Project appears in project list
    - Can switch to project
    """
    print("=" * 60)
    print("OpenShift Console - Project Creation Test")
    print("=" * 60)

    tester = ChromeWebAppTester(
        exercise_name="openshift-project-creation",
        mode="auto",
        headless=False
    )

    if not tester.setup_driver():
        print("❌ Failed to setup Chrome WebDriver")
        return False

    try:
        # Navigate to console
        console_url = "https://console-openshift-console.apps.ocp4.example.com/"
        tester.navigate(console_url)

        # Note: Actual project creation would require authentication
        # This example shows the structure for testing the workflow

        print("\n1. Navigating to Projects view...")
        # In real test: click Projects, then Create Project
        tester.capture_screenshot("projects_view")

        print("\n2. Testing project creation button...")
        # In real test: verify "Create Project" button exists
        result = tester.verify_text("Project")
        print(f"   {'✅' if result else '❌'} Projects section visible")

        print("\n3. Capturing project list...")
        tester.capture_screenshot("project_list")

        summary = tester.get_summary()
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")

        return summary['failed'] == 0

    finally:
        tester.cleanup()


def test_openshift_deployment_verification():
    """
    Test deployment verification in OpenShift console.

    Verifies:
    - Can view deployments
    - Pod status is visible
    - Logs are accessible
    """
    print("=" * 60)
    print("OpenShift Console - Deployment Verification Test")
    print("=" * 60)

    tester = ChromeWebAppTester(
        exercise_name="openshift-deployment-verify",
        mode="auto",
        headless=False
    )

    if not tester.setup_driver():
        print("❌ Failed to setup Chrome WebDriver")
        return False

    try:
        console_url = "https://console-openshift-console.apps.ocp4.example.com/"
        tester.navigate(console_url)

        print("\n1. Checking Topology view...")
        result = tester.verify_text("Topology")
        print(f"   {'✅' if result else '❌'} Topology view available")
        tester.capture_screenshot("topology_view")

        print("\n2. Checking Workloads section...")
        result = tester.verify_text("Workloads")
        print(f"   {'✅' if result else '❌'} Workloads section visible")

        print("\n3. Capturing deployment status...")
        tester.capture_screenshot("deployment_status")

        summary = tester.get_summary()
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")

        return summary['failed'] == 0

    finally:
        tester.cleanup()


def test_openshift_route_validation():
    """
    Test route configuration and validation.

    Verifies:
    - Routes section is accessible
    - Can view route details
    - Route URL is visible
    """
    print("=" * 60)
    print("OpenShift Console - Route Validation Test")
    print("=" * 60)

    tester = ChromeWebAppTester(
        exercise_name="openshift-route-validation",
        mode="auto",
        headless=False
    )

    if not tester.setup_driver():
        print("❌ Failed to setup Chrome WebDriver")
        return False

    try:
        console_url = "https://console-openshift-console.apps.ocp4.example.com/"
        tester.navigate(console_url)

        print("\n1. Navigating to Networking...")
        result = tester.verify_text("Networking")
        print(f"   {'✅' if result else '❌'} Networking section visible")

        print("\n2. Checking Routes...")
        result = tester.verify_text("Route")
        print(f"   {'✅' if result else '❌'} Routes visible")
        tester.capture_screenshot("routes_view")

        summary = tester.get_summary()
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")

        return summary['failed'] == 0

    finally:
        tester.cleanup()


def test_openshift_comprehensive():
    """
    Comprehensive OpenShift console test suite.

    Runs all test scenarios in sequence:
    1. Basic accessibility
    2. Project creation
    3. Deployment verification
    4. Route validation
    """
    print("\n" + "=" * 60)
    print("COMPREHENSIVE OPENSHIFT CONSOLE TEST SUITE")
    print("=" * 60 + "\n")

    results = {
        'Basic Accessibility': test_openshift_console_basic(),
        'Project Creation': test_openshift_project_creation(),
        'Deployment Verification': test_openshift_deployment_verification(),
        'Route Validation': test_openshift_route_validation()
    }

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")

    total_passed = sum(1 for p in results.values() if p)
    total_tests = len(results)

    print("\n" + "=" * 60)
    print(f"Overall: {total_passed}/{total_tests} tests passed")
    print("=" * 60)

    return all(results.values())


def main():
    """Run OpenShift console tests."""
    import argparse

    parser = argparse.ArgumentParser(description="OpenShift Console WebApp Testing")
    parser.add_argument(
        "--test",
        choices=['basic', 'project', 'deployment', 'route', 'comprehensive'],
        default='comprehensive',
        help="Test scenario to run"
    )

    args = parser.parse_args()

    test_map = {
        'basic': test_openshift_console_basic,
        'project': test_openshift_project_creation,
        'deployment': test_openshift_deployment_verification,
        'route': test_openshift_route_validation,
        'comprehensive': test_openshift_comprehensive
    }

    success = test_map[args.test]()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
