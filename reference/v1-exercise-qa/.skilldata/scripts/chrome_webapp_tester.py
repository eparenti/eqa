#!/usr/bin/env python3
"""
Chrome WebApp Tester - Selenium-based browser automation for Red Hat Training exercises

Supports:
- Local and remote Chrome instances
- Navigation, interaction, and validation
- Screenshot capture for documentation
- Integration with exercise-qa testing framework
"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
except ImportError:
    print("ERROR: Selenium not installed. Run: pip install selenium")
    sys.exit(1)


@dataclass
class TestResult:
    """Result of a webapp test"""
    success: bool
    message: str
    screenshot_path: Optional[str] = None
    duration: float = 0.0
    details: Dict = None


class ChromeWebAppTester:
    """Selenium-based Chrome automation for webapp testing"""

    def __init__(self,
                 exercise_name: str,
                 mode: str = "auto",  # auto, local, remote
                 remote_host: Optional[str] = None,
                 headless: bool = False,
                 screenshot_dir: Optional[str] = None):
        """
        Initialize Chrome WebApp Tester

        Args:
            exercise_name: Name of exercise being tested
            mode: 'auto', 'local', or 'remote'
            remote_host: SSH host for remote Chrome (if mode=remote)
            headless: Run Chrome in headless mode
            screenshot_dir: Directory to save screenshots
        """
        self.exercise_name = exercise_name
        self.mode = mode
        self.remote_host = remote_host
        self.headless = headless
        self.driver = None
        self.test_results = []

        # Setup screenshot directory
        if screenshot_dir:
            self.screenshot_dir = Path(screenshot_dir)
        else:
            skill_dir = Path(__file__).parent.parent.parent
            self.screenshot_dir = skill_dir / "results" / "screenshots" / exercise_name

        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        # Auto-detect mode if needed
        if self.mode == "auto":
            self.mode = self._detect_mode()

    def _detect_mode(self) -> str:
        """Auto-detect whether to use local or remote Chrome"""
        # Check if Chrome is available locally
        try:
            result = subprocess.run(
                ["which", "google-chrome"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return "local"
        except Exception:
            pass

        # Check if remote workstation is configured
        if self.remote_host or self._has_ssh_workstation():
            return "remote"

        return "local"  # Default to local

    def _has_ssh_workstation(self) -> bool:
        """Check if SSH workstation is configured"""
        ssh_config = Path.home() / ".ssh" / "config"
        if ssh_config.exists():
            with open(ssh_config) as f:
                content = f.read()
                return "Host workstation" in content
        return False

    def setup_driver(self) -> bool:
        """
        Setup Selenium WebDriver (local or remote)

        Returns:
            True if successful, False otherwise
        """
        try:
            chrome_options = Options()

            if self.headless:
                chrome_options.add_argument("--headless=new")

            # Common options for stability
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")

            if self.mode == "local":
                # Local Chrome
                self.driver = webdriver.Chrome(options=chrome_options)
                print(f"✅ Chrome WebDriver initialized (local)")

            elif self.mode == "remote":
                # Remote Chrome via Selenium Grid or ChromeDriver on remote host
                # For now, use SSH port forwarding + local driver
                # Future: Implement actual remote WebDriver
                print("⚠️  Remote mode: Using local Chrome with SSH tunnel support")
                self.driver = webdriver.Chrome(options=chrome_options)

            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(10)

            return True

        except WebDriverException as e:
            print(f"❌ Failed to initialize Chrome WebDriver: {e}")
            print("\nTroubleshooting:")
            print("  1. Install ChromeDriver: sudo dnf install chromedriver")
            print("  2. Or download from: https://chromedriver.chromium.org/")
            print("  3. Ensure Chrome is installed: google-chrome --version")
            return False
        except Exception as e:
            print(f"❌ Unexpected error setting up WebDriver: {e}")
            return False

    def navigate(self, url: str, timeout: int = 30) -> TestResult:
        """
        Navigate to URL and verify page loads

        Args:
            url: URL to navigate to
            timeout: Page load timeout in seconds

        Returns:
            TestResult with navigation status
        """
        start_time = time.time()

        try:
            print(f"🌐 Navigating to: {url}")
            self.driver.get(url)

            # Wait for page to be ready
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            duration = time.time() - start_time
            title = self.driver.title

            # Take screenshot
            screenshot_path = self._capture_screenshot(f"navigate_{url.replace('://', '_').replace('/', '_')}")

            result = TestResult(
                success=True,
                message=f"Successfully loaded: {title}",
                screenshot_path=str(screenshot_path),
                duration=duration,
                details={"url": url, "title": title}
            )

            print(f"  ✅ Page loaded: {title} ({duration:.2f}s)")
            self.test_results.append(result)
            return result

        except TimeoutException:
            duration = time.time() - start_time
            screenshot_path = self._capture_screenshot(f"navigate_timeout_{url.replace('://', '_').replace('/', '_')}")

            result = TestResult(
                success=False,
                message=f"Timeout loading {url} after {timeout}s",
                screenshot_path=str(screenshot_path),
                duration=duration,
                details={"url": url, "timeout": timeout}
            )

            print(f"  ❌ Timeout loading {url}")
            self.test_results.append(result)
            return result

        except Exception as e:
            duration = time.time() - start_time
            result = TestResult(
                success=False,
                message=f"Error navigating to {url}: {str(e)}",
                duration=duration,
                details={"url": url, "error": str(e)}
            )

            print(f"  ❌ Error: {e}")
            self.test_results.append(result)
            return result

    def verify_text(self, text: str, timeout: int = 10) -> TestResult:
        """
        Verify text is present on page

        Args:
            text: Text to search for
            timeout: Wait timeout in seconds

        Returns:
            TestResult with verification status
        """
        start_time = time.time()

        try:
            print(f"🔍 Verifying text: '{text}'")

            # Wait for text to appear
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{text}')]"))
            )

            duration = time.time() - start_time
            screenshot_path = self._capture_screenshot(f"verify_text_{text[:30].replace(' ', '_')}")

            result = TestResult(
                success=True,
                message=f"Text found: '{text}'",
                screenshot_path=str(screenshot_path),
                duration=duration,
                details={"text": text}
            )

            print(f"  ✅ Text found ({duration:.2f}s)")
            self.test_results.append(result)
            return result

        except TimeoutException:
            duration = time.time() - start_time
            screenshot_path = self._capture_screenshot(f"verify_text_not_found_{text[:30].replace(' ', '_')}")

            result = TestResult(
                success=False,
                message=f"Text not found: '{text}'",
                screenshot_path=str(screenshot_path),
                duration=duration,
                details={"text": text, "timeout": timeout}
            )

            print(f"  ❌ Text not found: '{text}'")
            self.test_results.append(result)
            return result

    def click_element(self, selector: str, by: By = By.CSS_SELECTOR, timeout: int = 10) -> TestResult:
        """
        Click an element

        Args:
            selector: Element selector
            by: Selenium By type (CSS_SELECTOR, XPATH, ID, etc.)
            timeout: Wait timeout in seconds

        Returns:
            TestResult with click status
        """
        start_time = time.time()

        try:
            print(f"🖱️  Clicking element: {selector}")

            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, selector))
            )

            # Take screenshot before click
            screenshot_before = self._capture_screenshot(f"before_click_{selector.replace(' ', '_')[:30]}")

            element.click()
            time.sleep(0.5)  # Wait for click to register

            # Take screenshot after click
            screenshot_after = self._capture_screenshot(f"after_click_{selector.replace(' ', '_')[:30]}")

            duration = time.time() - start_time

            result = TestResult(
                success=True,
                message=f"Clicked: {selector}",
                screenshot_path=str(screenshot_after),
                duration=duration,
                details={
                    "selector": selector,
                    "screenshot_before": str(screenshot_before),
                    "screenshot_after": str(screenshot_after)
                }
            )

            print(f"  ✅ Clicked ({duration:.2f}s)")
            self.test_results.append(result)
            return result

        except TimeoutException:
            duration = time.time() - start_time
            screenshot_path = self._capture_screenshot(f"click_timeout_{selector.replace(' ', '_')[:30]}")

            result = TestResult(
                success=False,
                message=f"Element not clickable: {selector}",
                screenshot_path=str(screenshot_path),
                duration=duration,
                details={"selector": selector, "timeout": timeout}
            )

            print(f"  ❌ Element not clickable: {selector}")
            self.test_results.append(result)
            return result

    def fill_form(self, field_selector: str, value: str, by: By = By.CSS_SELECTOR, timeout: int = 10) -> TestResult:
        """
        Fill a form field

        Args:
            field_selector: Field selector
            value: Value to enter
            by: Selenium By type
            timeout: Wait timeout in seconds

        Returns:
            TestResult with fill status
        """
        start_time = time.time()

        try:
            print(f"✍️  Filling field '{field_selector}' with: {value}")

            field = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, field_selector))
            )

            field.clear()
            field.send_keys(value)

            duration = time.time() - start_time
            screenshot_path = self._capture_screenshot(f"fill_form_{field_selector.replace(' ', '_')[:30]}")

            result = TestResult(
                success=True,
                message=f"Filled field: {field_selector}",
                screenshot_path=str(screenshot_path),
                duration=duration,
                details={"field": field_selector, "value": value}
            )

            print(f"  ✅ Field filled ({duration:.2f}s)")
            self.test_results.append(result)
            return result

        except Exception as e:
            duration = time.time() - start_time
            screenshot_path = self._capture_screenshot(f"fill_form_error_{field_selector.replace(' ', '_')[:30]}")

            result = TestResult(
                success=False,
                message=f"Error filling field {field_selector}: {str(e)}",
                screenshot_path=str(screenshot_path),
                duration=duration,
                details={"field": field_selector, "error": str(e)}
            )

            print(f"  ❌ Error: {e}")
            self.test_results.append(result)
            return result

    def verify_element(self, selector: str, by: By = By.CSS_SELECTOR, timeout: int = 10) -> TestResult:
        """
        Verify element exists on page

        Args:
            selector: Element selector
            by: Selenium By type
            timeout: Wait timeout in seconds

        Returns:
            TestResult with verification status
        """
        start_time = time.time()

        try:
            print(f"🔍 Verifying element: {selector}")

            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )

            duration = time.time() - start_time
            screenshot_path = self._capture_screenshot(f"verify_element_{selector.replace(' ', '_')[:30]}")

            # Get element properties
            element_info = {
                "tag": element.tag_name,
                "text": element.text[:100] if element.text else "",
                "visible": element.is_displayed()
            }

            result = TestResult(
                success=True,
                message=f"Element found: {selector}",
                screenshot_path=str(screenshot_path),
                duration=duration,
                details={"selector": selector, "element": element_info}
            )

            print(f"  ✅ Element found: {element.tag_name} ({duration:.2f}s)")
            self.test_results.append(result)
            return result

        except TimeoutException:
            duration = time.time() - start_time
            screenshot_path = self._capture_screenshot(f"verify_element_not_found_{selector.replace(' ', '_')[:30]}")

            result = TestResult(
                success=False,
                message=f"Element not found: {selector}",
                screenshot_path=str(screenshot_path),
                duration=duration,
                details={"selector": selector, "timeout": timeout}
            )

            print(f"  ❌ Element not found: {selector}")
            self.test_results.append(result)
            return result

    def _capture_screenshot(self, name: str) -> Path:
        """
        Capture screenshot with timestamp

        Args:
            name: Screenshot name (without extension)

        Returns:
            Path to saved screenshot
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{timestamp}_{name}.png"
        filepath = self.screenshot_dir / filename

        try:
            self.driver.save_screenshot(str(filepath))
            return filepath
        except Exception as e:
            print(f"⚠️  Failed to capture screenshot: {e}")
            return None

    def capture_screenshot(self, name: str) -> TestResult:
        """
        Manually capture screenshot

        Args:
            name: Screenshot description

        Returns:
            TestResult with screenshot path
        """
        start_time = time.time()

        try:
            print(f"📸 Capturing screenshot: {name}")
            screenshot_path = self._capture_screenshot(name)
            duration = time.time() - start_time

            result = TestResult(
                success=True,
                message=f"Screenshot captured: {name}",
                screenshot_path=str(screenshot_path),
                duration=duration,
                details={"name": name}
            )

            print(f"  ✅ Saved to: {screenshot_path}")
            self.test_results.append(result)
            return result

        except Exception as e:
            duration = time.time() - start_time
            result = TestResult(
                success=False,
                message=f"Error capturing screenshot: {str(e)}",
                duration=duration,
                details={"name": name, "error": str(e)}
            )

            print(f"  ❌ Error: {e}")
            self.test_results.append(result)
            return result

    def get_summary(self) -> Dict:
        """
        Get test summary

        Returns:
            Dict with test statistics
        """
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r.success)
        failed = total - passed
        total_duration = sum(r.duration for r in self.test_results)

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": f"{(passed/total*100):.1f}%" if total > 0 else "0%",
            "total_duration": f"{total_duration:.2f}s",
            "screenshot_dir": str(self.screenshot_dir)
        }

    def print_summary(self):
        """Print test summary"""
        summary = self.get_summary()

        print("\n" + "="*60)
        print("CHROME WEBAPP TEST SUMMARY")
        print("="*60)
        print(f"Exercise: {self.exercise_name}")
        print(f"Mode: {self.mode}")
        print(f"Total Tests: {summary['total']}")
        print(f"Passed: {summary['passed']} ✅")
        print(f"Failed: {summary['failed']} ❌")
        print(f"Success Rate: {summary['success_rate']}")
        print(f"Total Duration: {summary['total_duration']}")
        print(f"Screenshots: {summary['screenshot_dir']}")
        print("="*60 + "\n")

    def cleanup(self):
        """Cleanup WebDriver resources"""
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Chrome WebDriver closed")
            except Exception as e:
                print(f"⚠️  Error closing WebDriver: {e}")


def main():
    """Example usage"""
    import argparse

    parser = argparse.ArgumentParser(description="Chrome WebApp Tester for Red Hat Training")
    parser.add_argument("exercise", help="Exercise name")
    parser.add_argument("--url", required=True, help="URL to test")
    parser.add_argument("--mode", choices=["auto", "local", "remote"], default="auto",
                       help="Chrome mode (default: auto)")
    parser.add_argument("--headless", action="store_true", help="Run headless")
    parser.add_argument("--verify-text", help="Text to verify on page")
    parser.add_argument("--screenshot", help="Take screenshot with this name")

    args = parser.parse_args()

    # Initialize tester
    tester = ChromeWebAppTester(
        exercise_name=args.exercise,
        mode=args.mode,
        headless=args.headless
    )

    # Setup driver
    if not tester.setup_driver():
        sys.exit(1)

    try:
        # Navigate to URL
        tester.navigate(args.url)

        # Verify text if specified
        if args.verify_text:
            tester.verify_text(args.verify_text)

        # Take screenshot if specified
        if args.screenshot:
            tester.capture_screenshot(args.screenshot)

        # Print summary
        tester.print_summary()

        # Exit with appropriate code
        summary = tester.get_summary()
        sys.exit(0 if summary['failed'] == 0 else 1)

    finally:
        tester.cleanup()


if __name__ == "__main__":
    main()
