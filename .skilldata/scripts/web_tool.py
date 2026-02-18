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


def _get_browser():
    """Get or start Playwright browser and page."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _output({"success": False, "error": "playwright not installed. Run: pip install playwright && playwright install chromium"})
        sys.exit(1)

    state = _load_state()

    # Playwright can't persist across processes, so we start fresh each call
    # but we track the URL to restore navigation state
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(
        ignore_https_errors=True,
        viewport={"width": 1280, "height": 720},
    )
    page = context.new_page()

    # Restore last URL if we have one
    last_url = state.get("last_url")
    if last_url:
        try:
            page.goto(last_url, wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pass  # Page may not be available anymore

    return pw, browser, page


def _cleanup(pw, browser, page, save_url=True):
    """Save state and close browser."""
    if save_url:
        try:
            state = _load_state()
            state["last_url"] = page.url
            _save_state(state)
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


def cmd_close(args):
    """Clear web state."""
    if os.path.exists(STATE_FILE):
        os.unlink(STATE_FILE)
    _output({"success": True})


def main():
    parser = argparse.ArgumentParser(description="Web/browser tool for eqa")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    p = subparsers.add_parser("navigate")
    p.add_argument("url")
    p.add_argument("--screenshot", default=None)
    p.set_defaults(func=cmd_navigate)

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
