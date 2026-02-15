"""Browser Automation Client using Playwright.

Provides browser automation for testing UI-based exercises.
Based on patterns from exercise-reviewer agent.

Features:
- Headless browser automation
- Screenshot capture at each step
- Element clicking and verification
- Authentication flow handling
- Page state snapshots

Usage:
    browser = BrowserClient()
    if browser.connect(headless=True):
        browser.navigate("https://console.example.com")
        browser.click("text=Projects")
        browser.screenshot("step-1.png")
        browser.close()
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class PageElement:
    """Represents a clickable element on the page."""
    selector: str
    text: str
    visible: bool
    enabled: bool


@dataclass
class PageState:
    """Snapshot of current page state."""
    url: str
    title: str
    elements: List[PageElement]
    timestamp: str


@dataclass
class BrowserResult:
    """Result of a browser action."""
    success: bool
    message: str
    screenshot_path: Optional[Path] = None
    page_state: Optional[PageState] = None
    error: Optional[str] = None


class BrowserClient:
    """
    Browser automation client using Playwright.

    Provides headless browser automation for testing UI-based exercises.
    Falls back gracefully if Playwright is not installed.
    """

    def __init__(self, screenshots_dir: Optional[Path] = None):
        """
        Initialize browser client.

        Args:
            screenshots_dir: Directory for screenshots (default: ~/.cache/exercise-qa-3/screenshots/)
        """
        self.screenshots_dir = screenshots_dir or Path.home() / ".cache" / "exercise-qa-3" / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        self.browser = None
        self.context = None
        self.page = None
        self._playwright = None
        self._available = None

    def is_available(self) -> bool:
        """Check if Playwright is installed and available."""
        if self._available is not None:
            return self._available

        try:
            from playwright.sync_api import sync_playwright
            self._available = True
        except ImportError:
            self._available = False

        return self._available

    def connect(self, headless: bool = True, browser_type: str = "chromium") -> bool:
        """
        Launch browser and connect.

        Args:
            headless: Run in headless mode (default: True)
            browser_type: Browser to use: chromium, firefox, webkit (default: chromium)

        Returns:
            True if connected successfully
        """
        if not self.is_available():
            print("   Playwright not installed. Install with: pip install playwright && playwright install")
            return False

        try:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()

            # Select browser
            if browser_type == "chromium":
                self.browser = self._playwright.chromium.launch(headless=headless)
            elif browser_type == "firefox":
                self.browser = self._playwright.firefox.launch(headless=headless)
            elif browser_type == "webkit":
                self.browser = self._playwright.webkit.launch(headless=headless)
            else:
                self.browser = self._playwright.chromium.launch(headless=headless)

            # Create browser context
            self.context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True  # Lab environments often have self-signed certs
            )

            self.page = self.context.new_page()
            return True

        except Exception as e:
            print(f"   Browser launch failed: {e}")
            return False

    def close(self):
        """Close browser and cleanup."""
        if self.page:
            self.page.close()
            self.page = None
        if self.context:
            self.context.close()
            self.context = None
        if self.browser:
            self.browser.close()
            self.browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def navigate(self, url: str, wait_for: str = "networkidle") -> BrowserResult:
        """
        Navigate to URL.

        Args:
            url: URL to navigate to
            wait_for: Wait strategy: load, domcontentloaded, networkidle

        Returns:
            BrowserResult with success/failure
        """
        if not self.page:
            return BrowserResult(False, "Browser not connected")

        try:
            self.page.goto(url, wait_until=wait_for, timeout=30000)
            return BrowserResult(
                success=True,
                message=f"Navigated to {url}",
                page_state=self._get_page_state()
            )
        except Exception as e:
            return BrowserResult(False, f"Navigation failed: {e}", error=str(e))

    def click(self, selector: str, timeout: int = 10000) -> BrowserResult:
        """
        Click an element.

        Args:
            selector: Playwright selector (e.g., "text=Submit", "#button-id", "button.primary")
            timeout: Timeout in milliseconds

        Returns:
            BrowserResult with success/failure
        """
        if not self.page:
            return BrowserResult(False, "Browser not connected")

        try:
            self.page.click(selector, timeout=timeout)
            # Wait for any navigation/updates
            self.page.wait_for_load_state("networkidle", timeout=timeout)
            return BrowserResult(
                success=True,
                message=f"Clicked: {selector}",
                page_state=self._get_page_state()
            )
        except Exception as e:
            return BrowserResult(False, f"Click failed: {e}", error=str(e))

    def fill(self, selector: str, value: str, timeout: int = 10000) -> BrowserResult:
        """
        Fill a form field.

        Args:
            selector: Playwright selector for input field
            value: Value to fill
            timeout: Timeout in milliseconds

        Returns:
            BrowserResult with success/failure
        """
        if not self.page:
            return BrowserResult(False, "Browser not connected")

        try:
            self.page.fill(selector, value, timeout=timeout)
            return BrowserResult(success=True, message=f"Filled: {selector}")
        except Exception as e:
            return BrowserResult(False, f"Fill failed: {e}", error=str(e))

    def wait_for_selector(self, selector: str, timeout: int = 10000,
                          state: str = "visible") -> BrowserResult:
        """
        Wait for an element to appear.

        Args:
            selector: Playwright selector
            timeout: Timeout in milliseconds
            state: Element state: attached, visible, hidden

        Returns:
            BrowserResult with success/failure
        """
        if not self.page:
            return BrowserResult(False, "Browser not connected")

        try:
            self.page.wait_for_selector(selector, timeout=timeout, state=state)
            return BrowserResult(success=True, message=f"Found: {selector}")
        except Exception as e:
            return BrowserResult(False, f"Wait failed: {e}", error=str(e))

    def screenshot(self, name: str, full_page: bool = False) -> BrowserResult:
        """
        Capture screenshot.

        Args:
            name: Screenshot filename (without extension)
            full_page: Capture full scrollable page

        Returns:
            BrowserResult with screenshot path
        """
        if not self.page:
            return BrowserResult(False, "Browser not connected")

        try:
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            screenshot_path = self.screenshots_dir / f"{name}-{timestamp}.png"

            self.page.screenshot(path=str(screenshot_path), full_page=full_page)

            return BrowserResult(
                success=True,
                message=f"Screenshot saved: {screenshot_path}",
                screenshot_path=screenshot_path
            )
        except Exception as e:
            return BrowserResult(False, f"Screenshot failed: {e}", error=str(e))

    def get_text(self, selector: str, timeout: int = 5000) -> Optional[str]:
        """Get text content of an element."""
        if not self.page:
            return None

        try:
            return self.page.text_content(selector, timeout=timeout)
        except Exception:
            return None

    def is_visible(self, selector: str, timeout: int = 5000) -> bool:
        """Check if element is visible."""
        if not self.page:
            return False

        try:
            return self.page.is_visible(selector, timeout=timeout)
        except Exception:
            return False

    def authenticate(self, username: str, password: str,
                    username_selector: str = "#username",
                    password_selector: str = "#password",
                    submit_selector: str = "button[type='submit']") -> BrowserResult:
        """
        Perform authentication.

        Args:
            username: Username to enter
            password: Password to enter
            username_selector: Selector for username field
            password_selector: Selector for password field
            submit_selector: Selector for submit button

        Returns:
            BrowserResult with success/failure
        """
        if not self.page:
            return BrowserResult(False, "Browser not connected")

        try:
            # Fill credentials
            self.page.fill(username_selector, username, timeout=10000)
            self.page.fill(password_selector, password, timeout=10000)

            # Submit
            self.page.click(submit_selector, timeout=10000)

            # Wait for navigation
            self.page.wait_for_load_state("networkidle", timeout=30000)

            return BrowserResult(
                success=True,
                message="Authentication completed",
                page_state=self._get_page_state()
            )
        except Exception as e:
            return BrowserResult(False, f"Authentication failed: {e}", error=str(e))

    def _get_page_state(self) -> PageState:
        """Get current page state snapshot."""
        if not self.page:
            return None

        return PageState(
            url=self.page.url,
            title=self.page.title(),
            elements=[],  # Could enumerate visible elements
            timestamp=datetime.now().isoformat()
        )

    def execute_ui_steps(self, steps: List[Dict[str, Any]]) -> List[BrowserResult]:
        """
        Execute a sequence of UI steps.

        Args:
            steps: List of step dictionaries with 'action' and action-specific params
                   e.g., [{'action': 'click', 'selector': 'text=Submit'},
                          {'action': 'fill', 'selector': '#name', 'value': 'test'}]

        Returns:
            List of BrowserResults for each step
        """
        results = []

        for i, step in enumerate(steps):
            action = step.get('action', '')

            if action == 'navigate':
                result = self.navigate(step.get('url', ''))
            elif action == 'click':
                result = self.click(step.get('selector', ''))
            elif action == 'fill':
                result = self.fill(step.get('selector', ''), step.get('value', ''))
            elif action == 'wait':
                result = self.wait_for_selector(step.get('selector', ''))
            elif action == 'screenshot':
                result = self.screenshot(step.get('name', f'step-{i}'))
            elif action == 'authenticate':
                result = self.authenticate(
                    step.get('username', ''),
                    step.get('password', ''),
                    step.get('username_selector', '#username'),
                    step.get('password_selector', '#password'),
                    step.get('submit_selector', "button[type='submit']")
                )
            else:
                result = BrowserResult(False, f"Unknown action: {action}")

            results.append(result)

            # Stop on failure unless step has 'continue_on_failure'
            if not result.success and not step.get('continue_on_failure', False):
                break

        return results
