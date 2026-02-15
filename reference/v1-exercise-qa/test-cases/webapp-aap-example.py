#!/usr/bin/env python3
"""
Example: Testing Ansible Automation Platform (AAP) Web Interface

This example demonstrates how to use the Chrome WebApp Tester
to test Red Hat Ansible Automation Platform exercises.

Typical AAP exercises might include:
- Verifying AAP is accessible
- Logging into the web interface
- Creating/verifying projects
- Creating/verifying job templates
- Running and verifying jobs
- Checking inventory
"""

import sys
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent / ".skilldata" / "scripts"
sys.path.insert(0, str(scripts_dir))

from chrome_webapp_tester import ChromeWebAppTester
from selenium.webdriver.common.by import By


def test_aap_accessibility(exercise_name: str = "aap-basic-access"):
    """
    Test Case: AAP-001 - Verify AAP Web Interface Accessibility

    Tests that the AAP web interface is accessible and loads correctly.
    This is typically the first test for any AAP exercise.
    """
    print("\n" + "="*60)
    print("TEST CASE: AAP-001 - AAP Web Interface Accessibility")
    print("="*60 + "\n")

    # Initialize tester
    tester = ChromeWebAppTester(
        exercise_name=exercise_name,
        mode="auto",
        headless=False  # Set to True for automated testing
    )

    # Setup Chrome driver
    if not tester.setup_driver():
        print("❌ Failed to setup Chrome WebDriver")
        return False

    try:
        # Test 1: Navigate to AAP
        result = tester.navigate("https://aap.lab.example.com/")
        if not result.success:
            return False

        # Test 2: Verify AAP login page loads
        result = tester.verify_text("Automation Platform")
        if not result.success:
            # Alternative: Check for login form
            result = tester.verify_element("input[type='password']", by=By.CSS_SELECTOR)

        # Test 3: Capture screenshot of login page
        tester.capture_screenshot("aap_login_page")

        # Print summary
        tester.print_summary()

        return tester.get_summary()['failed'] == 0

    finally:
        tester.cleanup()


def test_aap_login(exercise_name: str = "aap-login-test",
                   username: str = "admin",
                   password: str = "redhat"):
    """
    Test Case: AAP-002 - AAP Login Workflow

    Tests the complete login workflow for AAP.
    This would be used in exercises where students need to access AAP.
    """
    print("\n" + "="*60)
    print("TEST CASE: AAP-002 - AAP Login Workflow")
    print("="*60 + "\n")

    tester = ChromeWebAppTester(
        exercise_name=exercise_name,
        mode="auto",
        headless=False
    )

    if not tester.setup_driver():
        return False

    try:
        # Navigate to AAP
        tester.navigate("https://aap.lab.example.com/")

        # Fill in username
        tester.fill_form("#login_username", username, by=By.CSS_SELECTOR)

        # Fill in password
        tester.fill_form("#login_password", password, by=By.CSS_SELECTOR)

        # Screenshot before login
        tester.capture_screenshot("before_login")

        # Click login button
        tester.click_element("button[type='submit']", by=By.CSS_SELECTOR)

        # Wait for dashboard to load
        tester.verify_element(".pf-c-page", by=By.CSS_SELECTOR, timeout=15)

        # Verify successful login
        tester.verify_text("Dashboard")

        # Screenshot after login
        tester.capture_screenshot("after_login_dashboard")

        # Print summary
        tester.print_summary()

        return tester.get_summary()['failed'] == 0

    finally:
        tester.cleanup()


def test_aap_job_template(exercise_name: str = "aap-job-template"):
    """
    Test Case: AAP-003 - Verify Job Template Exists

    Tests that a specific job template exists and is configured correctly.
    Common in exercises where students create job templates.
    """
    print("\n" + "="*60)
    print("TEST CASE: AAP-003 - Verify Job Template")
    print("="*60 + "\n")

    tester = ChromeWebAppTester(
        exercise_name=exercise_name,
        mode="auto",
        headless=False
    )

    if not tester.setup_driver():
        return False

    try:
        # Navigate to job templates page
        # Note: This assumes you're already logged in or using session cookies
        tester.navigate("https://aap.lab.example.com/#/templates")

        # Verify job templates page loaded
        tester.verify_text("Templates")

        # Search for specific job template (example: "Deploy Web Server")
        tester.fill_form("input[placeholder='Search']", "Deploy Web Server", by=By.CSS_SELECTOR)

        # Verify template appears in results
        tester.verify_text("Deploy Web Server")

        # Capture screenshot of job template
        tester.capture_screenshot("job_template_found")

        # Print summary
        tester.print_summary()

        return tester.get_summary()['failed'] == 0

    finally:
        tester.cleanup()


def test_aap_inventory(exercise_name: str = "aap-inventory-check"):
    """
    Test Case: AAP-004 - Verify Inventory Configuration

    Tests that an inventory is configured with the correct hosts.
    Common in exercises involving inventory setup.
    """
    print("\n" + "="*60)
    print("TEST CASE: AAP-004 - Verify Inventory")
    print("="*60 + "\n")

    tester = ChromeWebAppTester(
        exercise_name=exercise_name,
        mode="auto",
        headless=False
    )

    if not tester.setup_driver():
        return False

    try:
        # Navigate to inventories
        tester.navigate("https://aap.lab.example.com/#/inventories")

        # Verify inventories page
        tester.verify_text("Inventories")

        # Look for specific inventory (example: "Dev Servers")
        tester.verify_text("Dev Servers")

        # Click on the inventory
        tester.click_element("a:contains('Dev Servers')", by=By.CSS_SELECTOR)

        # Verify hosts tab
        tester.click_element("a[href*='hosts']", by=By.CSS_SELECTOR)

        # Verify expected hosts exist
        tester.verify_text("servera.lab.example.com")
        tester.verify_text("serverb.lab.example.com")

        # Capture screenshot
        tester.capture_screenshot("inventory_hosts")

        # Print summary
        tester.print_summary()

        return tester.get_summary()['failed'] == 0

    finally:
        tester.cleanup()


def test_aap_full_workflow(exercise_name: str = "aap-full-workflow"):
    """
    Test Case: AAP-005 - Complete Workflow Test

    Tests a complete student workflow:
    1. Access AAP
    2. Login
    3. Verify project exists
    4. Verify job template exists
    5. Launch job
    6. Verify job succeeds

    This represents a full exercise validation.
    """
    print("\n" + "="*60)
    print("TEST CASE: AAP-005 - Complete AAP Workflow")
    print("="*60 + "\n")

    tester = ChromeWebAppTester(
        exercise_name=exercise_name,
        mode="auto",
        headless=False
    )

    if not tester.setup_driver():
        return False

    try:
        # Step 1: Access AAP
        print("\n📋 Step 1: Access AAP Web Interface")
        tester.navigate("https://aap.lab.example.com/")
        tester.verify_element("input[type='password']", by=By.CSS_SELECTOR)
        tester.capture_screenshot("step1_aap_accessible")

        # Step 2: Login
        print("\n📋 Step 2: Login to AAP")
        tester.fill_form("#login_username", "admin", by=By.CSS_SELECTOR)
        tester.fill_form("#login_password", "redhat", by=By.CSS_SELECTOR)
        tester.click_element("button[type='submit']", by=By.CSS_SELECTOR)
        tester.verify_text("Dashboard")
        tester.capture_screenshot("step2_logged_in")

        # Step 3: Verify Project
        print("\n📋 Step 3: Verify Project Exists")
        tester.navigate("https://aap.lab.example.com/#/projects")
        tester.verify_text("Projects")
        tester.verify_text("MyProject")  # Example project name
        tester.capture_screenshot("step3_project_verified")

        # Step 4: Verify Job Template
        print("\n📋 Step 4: Verify Job Template Exists")
        tester.navigate("https://aap.lab.example.com/#/templates")
        tester.verify_text("Templates")
        tester.verify_text("Deploy Web Server")  # Example template
        tester.capture_screenshot("step4_template_verified")

        # Step 5: Launch Job (optional - could wait for completion)
        print("\n📋 Step 5: Launch Job (Verification Only)")
        # In a real test, you might click the launch button
        # For now, just verify the launch button exists
        tester.verify_element("button[aria-label='Launch']", by=By.CSS_SELECTOR)
        tester.capture_screenshot("step5_ready_to_launch")

        # Print summary
        tester.print_summary()

        return tester.get_summary()['failed'] == 0

    finally:
        tester.cleanup()


def main():
    """Run all AAP test cases"""
    import argparse

    parser = argparse.ArgumentParser(description="AAP WebApp Test Examples")
    parser.add_argument("--test", choices=[
        "accessibility", "login", "job-template", "inventory", "full-workflow", "all"
    ], default="accessibility", help="Test to run")
    parser.add_argument("--username", default="admin", help="AAP username")
    parser.add_argument("--password", default="redhat", help="AAP password")

    args = parser.parse_args()

    results = {}

    if args.test in ["accessibility", "all"]:
        results["accessibility"] = test_aap_accessibility()

    if args.test in ["login", "all"]:
        results["login"] = test_aap_login(username=args.username, password=args.password)

    if args.test in ["job-template", "all"]:
        results["job-template"] = test_aap_job_template()

    if args.test in ["inventory", "all"]:
        results["inventory"] = test_aap_inventory()

    if args.test in ["full-workflow", "all"]:
        results["full-workflow"] = test_aap_full_workflow()

    # Print overall results
    if args.test == "all":
        print("\n" + "="*60)
        print("OVERALL TEST RESULTS")
        print("="*60)
        for test_name, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {test_name}: {status}")
        print("="*60 + "\n")

        # Exit with error if any tests failed
        sys.exit(0 if all(results.values()) else 1)
    else:
        sys.exit(0 if results.get(args.test, False) else 1)


if __name__ == "__main__":
    main()
