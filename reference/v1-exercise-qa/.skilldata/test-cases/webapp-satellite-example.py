#!/usr/bin/env python3
"""
Red Hat Satellite UI WebApp Testing Example

Demonstrates automated testing of Red Hat Satellite web UI exercises using
the chrome_webapp_tester framework.

Test scenarios:
- Satellite web UI accessibility
- Login functionality
- Host management
- Content management (repos, content views)
- Activation keys
- Lifecycle environments
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.chrome_webapp_tester import ChromeWebAppTester


def test_satellite_ui_basic():
    """
    Test basic Satellite UI accessibility and login.

    Verifies:
    - Satellite UI is accessible
    - Login page loads
    - Satellite branding present
    """
    print("=" * 60)
    print("Satellite UI - Basic Accessibility Test")
    print("=" * 60)

    tester = ChromeWebAppTester(
        exercise_name="satellite-ui-basic",
        mode="auto",
        headless=False  # Set to True for CI/CD
    )

    if not tester.setup_driver():
        print("❌ Failed to setup Chrome WebDriver")
        return False

    try:
        # Test 1: Navigate to Satellite UI
        print("\n1. Testing Satellite UI accessibility...")
        satellite_url = "https://satellite.lab.example.com/"
        result = tester.navigate(satellite_url)
        print(f"   {'✅' if result else '❌'} Satellite UI accessible")

        # Test 2: Verify Satellite branding
        print("\n2. Verifying Satellite branding...")
        result = tester.verify_text("Satellite")
        print(f"   {'✅' if result else '❌'} Satellite branding present")

        # Test 3: Capture screenshot
        print("\n3. Capturing screenshot...")
        result = tester.capture_screenshot("satellite_login_page")
        print(f"   {'✅' if result else '❌'} Screenshot captured")

        # Test 4: Check for login form
        print("\n4. Checking for login form...")
        result = tester.verify_text("Log In") or tester.verify_text("Username")
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


def test_satellite_host_management():
    """
    Test Satellite host management interface.

    Verifies:
    - Hosts menu is accessible
    - All Hosts view loads
    - Host registration options visible
    """
    print("=" * 60)
    print("Satellite UI - Host Management Test")
    print("=" * 60)

    tester = ChromeWebAppTester(
        exercise_name="satellite-host-management",
        mode="auto",
        headless=False
    )

    if not tester.setup_driver():
        print("❌ Failed to setup Chrome WebDriver")
        return False

    try:
        # Navigate to Satellite
        satellite_url = "https://satellite.lab.example.com/"
        tester.navigate(satellite_url)

        # Note: Actual host management would require authentication
        # This example shows the structure for testing the workflow

        print("\n1. Checking Hosts menu...")
        result = tester.verify_text("Hosts")
        print(f"   {'✅' if result else '❌'} Hosts menu visible")
        tester.capture_screenshot("hosts_menu")

        print("\n2. Checking All Hosts view...")
        # In real test: navigate to Hosts > All Hosts
        result = tester.verify_text("All Hosts") or tester.verify_text("Host")
        print(f"   {'✅' if result else '❌'} All Hosts section accessible")

        print("\n3. Capturing host list...")
        tester.capture_screenshot("all_hosts_view")

        summary = tester.get_summary()
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")

        return summary['failed'] == 0

    finally:
        tester.cleanup()


def test_satellite_content_management():
    """
    Test Satellite content management features.

    Verifies:
    - Content menu accessible
    - Products visible
    - Repositories visible
    - Content Views accessible
    """
    print("=" * 60)
    print("Satellite UI - Content Management Test")
    print("=" * 60)

    tester = ChromeWebAppTester(
        exercise_name="satellite-content-management",
        mode="auto",
        headless=False
    )

    if not tester.setup_driver():
        print("❌ Failed to setup Chrome WebDriver")
        return False

    try:
        satellite_url = "https://satellite.lab.example.com/"
        tester.navigate(satellite_url)

        print("\n1. Checking Content menu...")
        result = tester.verify_text("Content")
        print(f"   {'✅' if result else '❌'} Content menu visible")

        print("\n2. Checking Products section...")
        result = tester.verify_text("Product")
        print(f"   {'✅' if result else '❌'} Products section accessible")
        tester.capture_screenshot("products_view")

        print("\n3. Checking Content Views...")
        result = tester.verify_text("Content View")
        print(f"   {'✅' if result else '❌'} Content Views accessible")
        tester.capture_screenshot("content_views")

        summary = tester.get_summary()
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")

        return summary['failed'] == 0

    finally:
        tester.cleanup()


def test_satellite_activation_keys():
    """
    Test Satellite activation keys interface.

    Verifies:
    - Content > Activation Keys accessible
    - Can view activation keys list
    - Create button visible
    """
    print("=" * 60)
    print("Satellite UI - Activation Keys Test")
    print("=" * 60)

    tester = ChromeWebAppTester(
        exercise_name="satellite-activation-keys",
        mode="auto",
        headless=False
    )

    if not tester.setup_driver():
        print("❌ Failed to setup Chrome WebDriver")
        return False

    try:
        satellite_url = "https://satellite.lab.example.com/"
        tester.navigate(satellite_url)

        print("\n1. Navigating to Activation Keys...")
        result = tester.verify_text("Activation Key")
        print(f"   {'✅' if result else '❌'} Activation Keys section visible")

        print("\n2. Checking activation keys list...")
        tester.capture_screenshot("activation_keys_list")

        print("\n3. Checking for Create button...")
        result = tester.verify_text("Create") or tester.verify_text("New")
        print(f"   {'✅' if result else '❌'} Create button visible")

        summary = tester.get_summary()
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")

        return summary['failed'] == 0

    finally:
        tester.cleanup()


def test_satellite_lifecycle_environments():
    """
    Test Satellite lifecycle environments interface.

    Verifies:
    - Content > Lifecycle Environments accessible
    - Environment paths visible
    - Can view environment details
    """
    print("=" * 60)
    print("Satellite UI - Lifecycle Environments Test")
    print("=" * 60)

    tester = ChromeWebAppTester(
        exercise_name="satellite-lifecycle-environments",
        mode="auto",
        headless=False
    )

    if not tester.setup_driver():
        print("❌ Failed to setup Chrome WebDriver")
        return False

    try:
        satellite_url = "https://satellite.lab.example.com/"
        tester.navigate(satellite_url)

        print("\n1. Checking Lifecycle Environments...")
        result = tester.verify_text("Lifecycle Environment")
        print(f"   {'✅' if result else '❌'} Lifecycle Environments visible")

        print("\n2. Checking environment paths...")
        result = tester.verify_text("Library") or tester.verify_text("Path")
        print(f"   {'✅' if result else '❌'} Environment paths visible")
        tester.capture_screenshot("lifecycle_environments")

        print("\n3. Capturing environment details...")
        tester.capture_screenshot("environment_details")

        summary = tester.get_summary()
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")

        return summary['failed'] == 0

    finally:
        tester.cleanup()


def test_satellite_comprehensive():
    """
    Comprehensive Satellite UI test suite.

    Runs all test scenarios in sequence:
    1. Basic accessibility
    2. Host management
    3. Content management
    4. Activation keys
    5. Lifecycle environments
    """
    print("\n" + "=" * 60)
    print("COMPREHENSIVE SATELLITE UI TEST SUITE")
    print("=" * 60 + "\n")

    results = {
        'Basic Accessibility': test_satellite_ui_basic(),
        'Host Management': test_satellite_host_management(),
        'Content Management': test_satellite_content_management(),
        'Activation Keys': test_satellite_activation_keys(),
        'Lifecycle Environments': test_satellite_lifecycle_environments()
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
    """Run Satellite UI tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Satellite UI WebApp Testing")
    parser.add_argument(
        "--test",
        choices=['basic', 'hosts', 'content', 'activation', 'lifecycle', 'comprehensive'],
        default='comprehensive',
        help="Test scenario to run"
    )

    args = parser.parse_args()

    test_map = {
        'basic': test_satellite_ui_basic,
        'hosts': test_satellite_host_management,
        'content': test_satellite_content_management,
        'activation': test_satellite_activation_keys,
        'lifecycle': test_satellite_lifecycle_environments,
        'comprehensive': test_satellite_comprehensive
    }

    success = test_map[args.test]()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
