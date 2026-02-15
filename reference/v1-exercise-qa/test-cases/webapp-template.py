#!/usr/bin/env python3
"""
WebApp Testing Template

Use this template to create custom webapp tests for any Red Hat Training exercise
that involves web interfaces.

Common use cases:
- AAP (Ansible Automation Platform) - https://aap.lab.example.com/
- OpenShift Console - https://console-openshift-console.apps...
- Satellite Web UI - https://satellite.lab.example.com/
- Cockpit - https://servera.lab.example.com:9090/
- Custom web applications deployed in exercises
"""

import sys
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent / ".skilldata" / "scripts"
sys.path.insert(0, str(scripts_dir))

from chrome_webapp_tester import ChromeWebAppTester
from selenium.webdriver.common.by import By


def test_webapp_template(
    exercise_name: str,
    webapp_url: str,
    expected_title_text: str = None,
    login_required: bool = False,
    username: str = None,
    password: str = None
):
    """
    Generic webapp test template

    Args:
        exercise_name: Name of the exercise being tested
        webapp_url: URL of the webapp to test
        expected_title_text: Text expected on the page (for verification)
        login_required: Whether login is required
        username: Username for login (if required)
        password: Password for login (if required)

    Returns:
        bool: True if all tests passed, False otherwise
    """
    print("\n" + "="*60)
    print(f"WEBAPP TEST: {exercise_name}")
    print(f"URL: {webapp_url}")
    print("="*60 + "\n")

    # Initialize tester
    tester = ChromeWebAppTester(
        exercise_name=exercise_name,
        mode="auto",
        headless=False  # Set to True for automated/headless testing
    )

    # Setup Chrome driver
    if not tester.setup_driver():
        print("❌ Failed to setup Chrome WebDriver")
        print("\nTroubleshooting:")
        print("  1. Install Selenium: pip install selenium")
        print("  2. Install ChromeDriver: sudo dnf install chromedriver")
        print("  3. Verify Chrome: google-chrome --version")
        return False

    try:
        # Test 1: Navigate to webapp
        print("📋 Test 1: Navigate to webapp")
        result = tester.navigate(webapp_url)
        if not result.success:
            print("❌ Failed to navigate to webapp")
            return False

        # Test 2: Verify page content (if expected text provided)
        if expected_title_text:
            print(f"📋 Test 2: Verify page contains '{expected_title_text}'")
            result = tester.verify_text(expected_title_text)
            if not result.success:
                print(f"⚠️  Expected text not found, continuing anyway...")

        # Test 3: Login (if required)
        if login_required and username and password:
            print("📋 Test 3: Login to webapp")

            # Customize these selectors based on your webapp
            # These are common patterns - adjust as needed

            # Fill username
            username_selectors = [
                "#login_username",           # AAP style
                "input[name='username']",    # Common pattern
                "input[type='text']",        # Generic
            ]

            for selector in username_selectors:
                try:
                    result = tester.fill_form(selector, username, by=By.CSS_SELECTOR, timeout=2)
                    if result.success:
                        break
                except:
                    continue

            # Fill password
            password_selectors = [
                "#login_password",           # AAP style
                "input[name='password']",    # Common pattern
                "input[type='password']",    # Generic
            ]

            for selector in password_selectors:
                try:
                    result = tester.fill_form(selector, password, by=By.CSS_SELECTOR, timeout=2)
                    if result.success:
                        break
                except:
                    continue

            # Click login button
            login_button_selectors = [
                "button[type='submit']",     # Most common
                "input[type='submit']",      # Traditional forms
                "#login-button",             # By ID
                ".login-button",             # By class
            ]

            for selector in login_button_selectors:
                try:
                    result = tester.click_element(selector, by=By.CSS_SELECTOR, timeout=2)
                    if result.success:
                        break
                except:
                    continue

            # Wait for login to complete (adjust timeout as needed)
            import time
            time.sleep(3)

            # Capture post-login screenshot
            tester.capture_screenshot("after_login")

        # Test 4: Final screenshot
        print("📋 Final: Capture screenshot of current state")
        tester.capture_screenshot("final_state")

        # Print test summary
        tester.print_summary()

        # Return success if no failed tests
        summary = tester.get_summary()
        return summary['failed'] == 0

    except Exception as e:
        print(f"❌ Unexpected error during testing: {e}")
        return False

    finally:
        # Always cleanup
        tester.cleanup()


def test_custom_workflow(exercise_name: str, webapp_url: str):
    """
    Custom workflow test - Modify this for your specific needs

    This is a skeleton that you can customize for complex
    multi-step webapp testing workflows.
    """
    print("\n" + "="*60)
    print(f"CUSTOM WORKFLOW TEST: {exercise_name}")
    print("="*60 + "\n")

    tester = ChromeWebAppTester(exercise_name=exercise_name, mode="auto", headless=False)

    if not tester.setup_driver():
        return False

    try:
        # Step 1: Navigate
        print("\n📋 Step 1: Navigate to webapp")
        tester.navigate(webapp_url)
        tester.capture_screenshot("step1_navigation")

        # Step 2: Your custom action here
        print("\n📋 Step 2: [Describe your action]")
        # Example: Click a button
        # tester.click_element("button#my-button", by=By.CSS_SELECTOR)
        # tester.capture_screenshot("step2_action")

        # Step 3: Verify result
        print("\n📋 Step 3: [Verify expected outcome]")
        # Example: Verify text appears
        # tester.verify_text("Success")
        # tester.capture_screenshot("step3_verification")

        # Add more steps as needed...

        # Final summary
        tester.print_summary()

        return tester.get_summary()['failed'] == 0

    finally:
        tester.cleanup()


def main():
    """
    Example usage of the webapp testing template

    Customize this main() function for your specific exercise.
    """
    import argparse

    parser = argparse.ArgumentParser(description="WebApp Testing Template")
    parser.add_argument("--exercise", required=True, help="Exercise name")
    parser.add_argument("--url", required=True, help="WebApp URL")
    parser.add_argument("--text", help="Expected text to verify")
    parser.add_argument("--login", action="store_true", help="Login required")
    parser.add_argument("--username", default="admin", help="Username for login")
    parser.add_argument("--password", default="redhat", help="Password for login")
    parser.add_argument("--custom", action="store_true", help="Run custom workflow")

    args = parser.parse_args()

    if args.custom:
        # Run custom workflow
        success = test_custom_workflow(args.exercise, args.url)
    else:
        # Run standard template test
        success = test_webapp_template(
            exercise_name=args.exercise,
            webapp_url=args.url,
            expected_title_text=args.text,
            login_required=args.login,
            username=args.username,
            password=args.password
        )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    # Quick test examples (uncomment to use):

    # Example 1: Simple accessibility test
    # test_webapp_template(
    #     exercise_name="my-exercise",
    #     webapp_url="https://aap.lab.example.com/",
    #     expected_title_text="Automation Platform"
    # )

    # Example 2: Test with login
    # test_webapp_template(
    #     exercise_name="my-exercise-login",
    #     webapp_url="https://aap.lab.example.com/",
    #     login_required=True,
    #     username="admin",
    #     password="redhat"
    # )

    # Example 3: Custom workflow
    # test_custom_workflow(
    #     exercise_name="my-custom-test",
    #     webapp_url="https://myapp.lab.example.com/"
    # )

    # Run with command line arguments
    main()
