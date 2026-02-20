#!/usr/bin/env python3
"""Browser automation and web testing via Playwright.

All output is JSON to stdout, diagnostics to stderr.

Usage:
    python3 web_tool.py navigate <url> [--screenshot <path>]
    python3 web_tool.py click <selector> [--screenshot <path>]
    python3 web_tool.py fill <selector> <value>
    python3 web_tool.py text <selector>
    python3 web_tool.py screenshot <path>
    python3 web_tool.py page-text
    python3 web_tool.py wait <selector> [--timeout 10000]
    python3 web_tool.py evaluate <js_expression>
    python3 web_tool.py api-get <url> [--headers <json>]
    python3 web_tool.py api-post <url> --data <json> [--headers <json>]
    python3 web_tool.py close
"""

import argparse
import json
import os
import sys

STATE_FILE = "/tmp/eqa-web-state.json"


def _output(data):
    print(json.dumps(data, default=str))


def _err(msg):
    print(msg, file=sys.stderr)


def _load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)


STORAGE_STATE_FILE = "/tmp/eqa-web-storage.json"


def _get_browser():
    """Get or start Playwright browser and page.

    Persists cookies and storage state between calls so that login sessions
    survive across separate fill/click/navigate invocations.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _output({"success": False, "error": "playwright not installed. Run: pip install playwright && playwright install chromium"})
        sys.exit(1)

    state = _load_state()

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(headless=True)

        # Restore cookies/session from previous calls
        storage_state = None
        if os.path.exists(STORAGE_STATE_FILE):
            try:
                storage_state = STORAGE_STATE_FILE
            except Exception:
                pass

        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 720},
            storage_state=storage_state,
        )
        page = context.new_page()

        # Restore last URL if we have one
        last_url = state.get("last_url")
        if last_url:
            try:
                page.goto(last_url, wait_until="domcontentloaded", timeout=15000)
            except Exception:
                pass

        return pw, browser, page
    except Exception:
        try:
            pw.stop()
        except Exception:
            pass
        raise


def _cleanup(pw, browser, page, save_url=True):
    """Save state, cookies, and close browser."""
    if save_url:
        try:
            state = _load_state()
            state["last_url"] = page.url
            _save_state(state)
        except Exception:
            pass
        # Persist cookies and storage state for next invocation
        try:
            page.context.storage_state(path=STORAGE_STATE_FILE)
        except Exception:
            pass
    try:
        browser.close()
        pw.stop()
    except Exception:
        pass


def cmd_navigate(args):
    """Navigate to a URL."""
    pw, browser, page = _get_browser()
    try:
        page.goto(args.url, wait_until="domcontentloaded", timeout=30000)
        title = page.title()
        url = page.url

        result = {"success": True, "url": url, "title": title}

        if args.screenshot:
            page.screenshot(path=args.screenshot)
            result["screenshot"] = args.screenshot

        _output(result)
    except Exception as e:
        _output({"success": False, "error": str(e)})
    finally:
        _cleanup(pw, browser, page)


def cmd_click(args):
    """Click an element by selector."""
    pw, browser, page = _get_browser()
    try:
        page.click(args.selector, timeout=10000)
        page.wait_for_load_state("domcontentloaded")

        result = {"success": True, "url": page.url}

        if args.screenshot:
            page.screenshot(path=args.screenshot)
            result["screenshot"] = args.screenshot

        _output(result)
    except Exception as e:
        _output({"success": False, "error": str(e)})
    finally:
        _cleanup(pw, browser, page)


def cmd_fill(args):
    """Fill a form field."""
    pw, browser, page = _get_browser()
    try:
        page.fill(args.selector, args.value, timeout=10000)
        _output({"success": True})
    except Exception as e:
        _output({"success": False, "error": str(e)})
    finally:
        _cleanup(pw, browser, page)


def cmd_text(args):
    """Get text content of an element."""
    pw, browser, page = _get_browser()
    try:
        text = page.text_content(args.selector, timeout=10000)
        _output({"success": True, "text": text})
    except Exception as e:
        _output({"success": False, "error": str(e)})
    finally:
        _cleanup(pw, browser, page)


def cmd_screenshot(args):
    """Take a screenshot of the current page."""
    pw, browser, page = _get_browser()
    try:
        page.screenshot(path=args.path)
        _output({"success": True, "path": args.path, "url": page.url})
    except Exception as e:
        _output({"success": False, "error": str(e)})
    finally:
        _cleanup(pw, browser, page)


def cmd_page_text(args):
    """Get full page text content."""
    pw, browser, page = _get_browser()
    try:
        text = page.inner_text("body")
        _output({"success": True, "text": text[:5000], "url": page.url, "title": page.title()})
    except Exception as e:
        _output({"success": False, "error": str(e)})
    finally:
        _cleanup(pw, browser, page)


def cmd_wait(args):
    """Wait for an element to appear."""
    pw, browser, page = _get_browser()
    try:
        page.wait_for_selector(args.selector, timeout=args.timeout)
        _output({"success": True})
    except Exception as e:
        _output({"success": False, "error": str(e)})
    finally:
        _cleanup(pw, browser, page)


def cmd_evaluate(args):
    """Evaluate JavaScript expression on the page."""
    pw, browser, page = _get_browser()
    try:
        result = page.evaluate(args.expression)
        _output({"success": True, "result": result})
    except Exception as e:
        _output({"success": False, "error": str(e)})
    finally:
        _cleanup(pw, browser, page)


def cmd_api_get(args):
    """Make an HTTP GET request (no browser needed)."""
    import urllib.request
    import ssl

    headers = json.loads(args.headers) if args.headers else {}
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        req = urllib.request.Request(args.url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            _output({
                "success": True,
                "status": resp.status,
                "headers": dict(resp.headers),
                "body": body[:10000],
            })
    except Exception as e:
        _output({"success": False, "error": str(e)})


def cmd_api_post(args):
    """Make an HTTP POST request (no browser needed)."""
    import urllib.request
    import ssl

    headers = json.loads(args.headers) if args.headers else {}
    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        data = args.data.encode('utf-8')
        req = urllib.request.Request(args.url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            _output({
                "success": True,
                "status": resp.status,
                "headers": dict(resp.headers),
                "body": body[:10000],
            })
    except Exception as e:
        _output({"success": False, "error": str(e)})


def cmd_login(args):
    """Login to a web application (navigate + fill + submit in one session).

    Handles the full login flow in a single browser session to avoid
    losing form state between separate fill/click calls. Use --then
    to navigate to a specific page after login (e.g., the VMs page).
    """
    pw, browser, page = _get_browser()
    try:
        import time as _time

        page.goto(args.url, timeout=30000)
        # Wait for login form (page may redirect through OAuth first)
        page.wait_for_selector(args.username_selector, timeout=30000)
        _time.sleep(1)

        page.fill(args.username_selector, args.username, timeout=10000)
        page.fill(args.password_selector, args.password, timeout=10000)

        page.click(args.submit_selector, timeout=10000)
        _time.sleep(10)  # Wait for OAuth redirect chain to complete

        # Navigate to target page after login
        if args.then:
            page.goto(args.then, wait_until="domcontentloaded", timeout=30000)
            # Wait for SPA content to render
            _time.sleep(5)
            # Try to wait for page content (non-fatal)
            try:
                page.wait_for_selector("nav, [data-test], .pf-v6-c-page, .co-m-pane__body", timeout=15000)
            except Exception:
                pass  # SPA may not have these selectors

        result = {
            "success": True,
            "url": page.url,
            "title": page.title(),
        }

        # Get page text if we navigated to a target
        if args.then:
            try:
                result["text"] = page.inner_text("body")[:5000]
            except Exception:
                result["text"] = ""

        if args.screenshot:
            page.screenshot(path=args.screenshot)
            result["screenshot"] = args.screenshot

        _output(result)
    except Exception as e:
        _output({"success": False, "error": str(e), "url": getattr(page, 'url', '')})
    finally:
        _cleanup(pw, browser, page)


def cmd_close(args):
    """Clear web state and session cookies."""
    for f in [STATE_FILE, STORAGE_STATE_FILE]:
        if os.path.exists(f):
            os.unlink(f)
    _output({"success": True})


def main():
    parser = argparse.ArgumentParser(description="Web/browser tool for eqa")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    p = subparsers.add_parser("navigate")
    p.add_argument("url")
    p.add_argument("--screenshot", default=None)
    p.set_defaults(func=cmd_navigate)

    p = subparsers.add_parser("login")
    p.add_argument("url", help="Login page URL")
    p.add_argument("--username-selector", default="#inputUsername")
    p.add_argument("--password-selector", default="#inputPassword")
    p.add_argument("--submit-selector", default="button[type='submit']")
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--then", default=None, help="URL to navigate to after login")
    p.add_argument("--screenshot", default=None)
    p.set_defaults(func=cmd_login)

    p = subparsers.add_parser("click")
    p.add_argument("selector")
    p.add_argument("--screenshot", default=None)
    p.set_defaults(func=cmd_click)

    p = subparsers.add_parser("fill")
    p.add_argument("selector")
    p.add_argument("value")
    p.set_defaults(func=cmd_fill)

    p = subparsers.add_parser("text")
    p.add_argument("selector")
    p.set_defaults(func=cmd_text)

    p = subparsers.add_parser("screenshot")
    p.add_argument("path")
    p.set_defaults(func=cmd_screenshot)

    p = subparsers.add_parser("page-text")
    p.set_defaults(func=cmd_page_text)

    p = subparsers.add_parser("wait")
    p.add_argument("selector")
    p.add_argument("--timeout", type=int, default=10000)
    p.set_defaults(func=cmd_wait)

    p = subparsers.add_parser("evaluate")
    p.add_argument("expression")
    p.set_defaults(func=cmd_evaluate)

    p = subparsers.add_parser("api-get")
    p.add_argument("url")
    p.add_argument("--headers", default=None)
    p.set_defaults(func=cmd_api_get)

    p = subparsers.add_parser("api-post")
    p.add_argument("url")
    p.add_argument("--data", required=True)
    p.add_argument("--headers", default=None)
    p.set_defaults(func=cmd_api_post)

    p = subparsers.add_parser("close")
    p.set_defaults(func=cmd_close)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
