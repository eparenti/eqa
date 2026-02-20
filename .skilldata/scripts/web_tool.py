#!/usr/bin/env python3
"""Browser automation and web testing via Playwright.

All output is JSON to stdout, diagnostics to stderr.
Supports a persistent browser daemon to avoid relaunching Chromium for every
operation.

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
    python3 web_tool.py login <url> --username <user> --password <pass>
    python3 web_tool.py start-daemon [--timeout 300]
    python3 web_tool.py stop-daemon
    python3 web_tool.py close
"""

import argparse
import json
import os
import signal
import socket
import struct
import subprocess
import sys
import time

from eqa_common import _output, _err, get_cache_dir, get_state_path, load_state, save_state, json_safe


STATE_FILE = get_state_path("web")
STORAGE_STATE_FILE = os.path.join(get_cache_dir(), "web-storage.json")
DAEMON_SOCKET_PATH = os.path.join(get_cache_dir(), "web-daemon.sock")
DAEMON_PID_FILE = os.path.join(get_cache_dir(), "web-daemon.pid")

# Truncation limits for text returned in JSON output
MAX_PAGE_TEXT = 5000
MAX_API_BODY = 10000


# ---------------------------------------------------------------------------
# Daemon protocol helpers
# ---------------------------------------------------------------------------

def _send_message(sock, data):
    """Send a length-prefixed JSON message over a socket."""
    payload = json.dumps(data).encode('utf-8')
    sock.sendall(struct.pack('!I', len(payload)) + payload)


def _recv_message(sock):
    """Receive a length-prefixed JSON message from a socket."""
    raw_len = _recvall(sock, 4)
    if not raw_len:
        return None
    msg_len = struct.unpack('!I', raw_len)[0]
    data = _recvall(sock, msg_len)
    if not data:
        return None
    return json.loads(data.decode('utf-8'))


def _recvall(sock, n):
    """Receive exactly n bytes from socket."""
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def _daemon_running():
    """Check if daemon is running and reachable."""
    if not os.path.exists(DAEMON_SOCKET_PATH):
        return False
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.settimeout(2)
        s.connect(DAEMON_SOCKET_PATH)
        _send_message(s, {"subcommand": "ping"})
        resp = _recv_message(s)
        return resp is not None and resp.get("pong")
    except (ConnectionRefusedError, OSError, socket.timeout):
        # Stale socket file — clean up
        try:
            os.unlink(DAEMON_SOCKET_PATH)
        except OSError:
            pass
        return False
    finally:
        s.close()


def _send_to_daemon(subcommand, args_dict):
    """Send a command to the daemon, return the JSON response."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.settimeout(120)
        s.connect(DAEMON_SOCKET_PATH)
        _send_message(s, {"subcommand": subcommand, "args": args_dict})
        return _recv_message(s)
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Browser helpers (non-daemon path)
# ---------------------------------------------------------------------------

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

    state = load_state(STATE_FILE)

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(headless=True)

        # Restore cookies/session from previous calls
        storage_state = STORAGE_STATE_FILE if os.path.exists(STORAGE_STATE_FILE) else None

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
            state = load_state(STATE_FILE)
            state["last_url"] = page.url
            save_state(STATE_FILE, state)
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


# ---------------------------------------------------------------------------
# Daemon implementation
# ---------------------------------------------------------------------------

class BrowserDaemon:
    """Unix socket daemon that keeps Chromium alive between commands."""

    def __init__(self, idle_timeout=300):
        self.idle_timeout = idle_timeout
        self.pw = None
        self.browser = None
        self.context = None
        self.page = None
        self.last_activity = time.time()
        self._shutdown = False

    def start(self):
        """Launch browser and listen on Unix socket."""
        import atexit
        from playwright.sync_api import sync_playwright

        # Clean up stale socket
        if os.path.exists(DAEMON_SOCKET_PATH):
            os.unlink(DAEMON_SOCKET_PATH)

        # Write PID
        with open(DAEMON_PID_FILE, 'w') as f:
            f.write(str(os.getpid()))

        # Start browser
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=True)

        storage_state = STORAGE_STATE_FILE if os.path.exists(STORAGE_STATE_FILE) else None
        self.context = self.browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 720},
            storage_state=storage_state,
        )
        self.page = self.context.new_page()

        # Restore last URL
        state = load_state(STATE_FILE)
        last_url = state.get("last_url")
        if last_url:
            try:
                self.page.goto(last_url, wait_until="domcontentloaded", timeout=15000)
            except Exception:
                pass

        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        atexit.register(self._cleanup)

        # Listen
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(DAEMON_SOCKET_PATH)
        os.chmod(DAEMON_SOCKET_PATH, 0o600)
        server.listen(1)
        server.settimeout(10)  # check idle timeout periodically

        _err(f"Browser daemon started (PID {os.getpid()}, idle timeout {self.idle_timeout}s)")

        while not self._shutdown:
            # Check idle timeout
            if time.time() - self.last_activity > self.idle_timeout:
                _err("Idle timeout reached, shutting down daemon")
                break

            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                msg = _recv_message(conn)
                if msg:
                    self.last_activity = time.time()
                    resp = self._handle_command(msg)
                    _send_message(conn, resp)
                conn.close()
            except Exception as e:
                _err(f"Daemon error handling command: {e}")
                try:
                    _send_message(conn, {"success": False, "error": str(e)})
                    conn.close()
                except Exception:
                    pass

        server.close()
        self._cleanup()

    def _handle_signal(self, signum, frame):
        self._shutdown = True

    def _handle_command(self, msg):
        """Execute a browser command and return the result."""
        subcmd = msg.get("subcommand", "")
        args = msg.get("args", {})

        if subcmd == "ping":
            return {"pong": True}
        elif subcmd == "shutdown":
            self._shutdown = True
            return {"success": True}
        elif subcmd == "navigate":
            return self._do_navigate(args)
        elif subcmd == "click":
            return self._do_click(args)
        elif subcmd == "fill":
            return self._do_fill(args)
        elif subcmd == "text":
            return self._do_text(args)
        elif subcmd == "screenshot":
            return self._do_screenshot(args)
        elif subcmd == "page-text":
            return self._do_page_text(args)
        elif subcmd == "wait":
            return self._do_wait(args)
        elif subcmd == "evaluate":
            return self._do_evaluate(args)
        elif subcmd == "login":
            return self._do_login(args)
        else:
            return {"success": False, "error": f"Unknown daemon command: {subcmd}"}

    def _save_after_command(self):
        """Save state after each command for crash resilience."""
        try:
            state = load_state(STATE_FILE)
            state["last_url"] = self.page.url
            save_state(STATE_FILE, state)
        except Exception:
            pass
        try:
            self.page.context.storage_state(path=STORAGE_STATE_FILE)
        except Exception:
            pass

    def _do_navigate(self, args):
        try:
            self.page.goto(args["url"], wait_until="domcontentloaded", timeout=30000)
            result = {"success": True, "url": self.page.url, "title": self.page.title()}
            if args.get("screenshot"):
                self.page.screenshot(path=args["screenshot"])
                result["screenshot"] = args["screenshot"]
            self._save_after_command()
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _do_click(self, args):
        try:
            self.page.click(args["selector"], timeout=10000)
            self.page.wait_for_load_state("domcontentloaded")
            result = {"success": True, "url": self.page.url}
            if args.get("screenshot"):
                self.page.screenshot(path=args["screenshot"])
                result["screenshot"] = args["screenshot"]
            self._save_after_command()
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _do_fill(self, args):
        try:
            self.page.fill(args["selector"], args["value"], timeout=10000)
            self._save_after_command()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _do_text(self, args):
        try:
            text = self.page.text_content(args["selector"], timeout=10000)
            return {"success": True, "text": text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _do_screenshot(self, args):
        try:
            self.page.screenshot(path=args["path"])
            return {"success": True, "path": args["path"], "url": self.page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _do_page_text(self, args):
        try:
            text = self.page.inner_text("body")
            return {"success": True, "text": text[:MAX_PAGE_TEXT], "url": self.page.url, "title": self.page.title()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _do_wait(self, args):
        try:
            self.page.wait_for_selector(args["selector"], timeout=args.get("timeout", 10000))
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _do_evaluate(self, args):
        try:
            result = self.page.evaluate(args["expression"])
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _do_login(self, args):
        try:
            self.page.goto(args["url"], timeout=30000)
            self.page.wait_for_selector(args.get("username_selector", "#inputUsername"), timeout=30000)
            time.sleep(1)

            self.page.fill(args.get("username_selector", "#inputUsername"), args["username"], timeout=10000)
            self.page.fill(args.get("password_selector", "#inputPassword"), args["password"], timeout=10000)

            self.page.click(args.get("submit_selector", "button[type='submit']"), timeout=10000)
            time.sleep(10)

            if args.get("then"):
                self.page.goto(args["then"], wait_until="domcontentloaded", timeout=30000)
                time.sleep(5)
                try:
                    self.page.wait_for_selector("nav, [data-test], .pf-v6-c-page, .co-m-pane__body", timeout=15000)
                except Exception:
                    pass

            result = {
                "success": True,
                "url": self.page.url,
                "title": self.page.title(),
            }

            if args.get("then"):
                try:
                    result["text"] = self.page.inner_text("body")[:MAX_PAGE_TEXT]
                except Exception:
                    result["text"] = ""

            if args.get("screenshot"):
                self.page.screenshot(path=args["screenshot"])
                result["screenshot"] = args["screenshot"]

            self._save_after_command()
            return result
        except Exception as e:
            return {"success": False, "error": str(e), "url": getattr(self.page, 'url', '')}

    def _cleanup(self):
        """Clean shutdown of browser and socket."""
        try:
            self.page.context.storage_state(path=STORAGE_STATE_FILE)
        except Exception:
            pass
        try:
            self.browser.close()
        except Exception:
            pass
        try:
            self.pw.stop()
        except Exception:
            pass
        for f in [DAEMON_SOCKET_PATH, DAEMON_PID_FILE]:
            try:
                if os.path.exists(f):
                    os.unlink(f)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

@json_safe
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


@json_safe
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


@json_safe
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


@json_safe
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


@json_safe
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


@json_safe
def cmd_page_text(args):
    """Get full page text content."""
    pw, browser, page = _get_browser()
    try:
        text = page.inner_text("body")
        _output({"success": True, "text": text[:MAX_PAGE_TEXT], "url": page.url, "title": page.title()})
    except Exception as e:
        _output({"success": False, "error": str(e)})
    finally:
        _cleanup(pw, browser, page)


@json_safe
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


@json_safe
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


def _insecure_ssl_ctx():
    """Create an SSL context that skips certificate verification (for lab self-signed certs)."""
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


@json_safe
def cmd_api_get(args):
    """Make an HTTP GET request (no browser needed)."""
    import urllib.request

    headers = json.loads(args.headers) if args.headers else {}

    try:
        req = urllib.request.Request(args.url, headers=headers)
        with urllib.request.urlopen(req, context=_insecure_ssl_ctx(), timeout=30) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            _output({
                "success": True,
                "status": resp.status,
                "headers": dict(resp.headers),
                "body": body[:MAX_API_BODY],
            })
    except Exception as e:
        _output({"success": False, "error": str(e)})


@json_safe
def cmd_api_post(args):
    """Make an HTTP POST request (no browser needed)."""
    import urllib.request

    headers = json.loads(args.headers) if args.headers else {}
    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"

    try:
        data = args.data.encode('utf-8')
        req = urllib.request.Request(args.url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, context=_insecure_ssl_ctx(), timeout=30) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            _output({
                "success": True,
                "status": resp.status,
                "headers": dict(resp.headers),
                "body": body[:MAX_API_BODY],
            })
    except Exception as e:
        _output({"success": False, "error": str(e)})


@json_safe
def cmd_login(args):
    """Login to a web application (navigate + fill + submit in one session).

    Handles the full login flow in a single browser session to avoid
    losing form state between separate fill/click calls.
    """
    password = os.environ.get("EQA_WEB_PASSWORD") or args.password
    if not password:
        _output({"success": False, "error": "Password required. Set EQA_WEB_PASSWORD or use --password."})
        return

    pw, browser, page = _get_browser()
    try:
        page.goto(args.url, timeout=30000)
        # Wait for login form (page may redirect through OAuth first)
        page.wait_for_selector(args.username_selector, timeout=30000)
        time.sleep(1)

        page.fill(args.username_selector, args.username, timeout=10000)
        page.fill(args.password_selector, password, timeout=10000)

        page.click(args.submit_selector, timeout=10000)
        time.sleep(10)  # Wait for OAuth redirect chain to complete

        # Navigate to target page after login
        if args.then:
            page.goto(args.then, wait_until="domcontentloaded", timeout=30000)
            # Wait for SPA content to render
            time.sleep(5)
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
                result["text"] = page.inner_text("body")[:MAX_PAGE_TEXT]
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


@json_safe
def cmd_close(args):
    """Clear web state and session cookies. Also stops daemon if running."""
    # Stop daemon if running
    if _daemon_running():
        try:
            _send_to_daemon("shutdown", {})
        except Exception:
            pass

    for f in [STATE_FILE, STORAGE_STATE_FILE]:
        if os.path.exists(f):
            os.unlink(f)
    _output({"success": True})


@json_safe
def cmd_daemon(args):
    """Internal: run the browser daemon (foreground)."""
    daemon = BrowserDaemon(idle_timeout=args.timeout)
    daemon.start()


@json_safe
def cmd_start_daemon(args):
    """Start the browser daemon in the background."""
    if _daemon_running():
        _output({"success": True, "message": "Daemon already running"})
        return

    # Launch daemon as a detached subprocess
    script_path = os.path.abspath(__file__)
    proc = subprocess.Popen(
        [sys.executable, script_path, "daemon", "--timeout", str(args.timeout)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Wait for daemon to become reachable
    for _ in range(30):
        time.sleep(0.5)
        if _daemon_running():
            _output({"success": True, "pid": proc.pid, "socket": DAEMON_SOCKET_PATH})
            return

    _output({"success": False, "error": "Daemon did not start in time"})


@json_safe
def cmd_stop_daemon(args):
    """Stop the browser daemon."""
    if not _daemon_running():
        _output({"success": True, "message": "Daemon not running"})
        return

    try:
        resp = _send_to_daemon("shutdown", {})
        _output({"success": True, "message": "Daemon stopped"})
    except Exception as e:
        # Try SIGTERM via PID file
        if os.path.exists(DAEMON_PID_FILE):
            try:
                with open(DAEMON_PID_FILE) as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
                _output({"success": True, "message": f"Sent SIGTERM to {pid}"})
                return
            except Exception:
                pass
        _output({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Daemon-aware dispatch
# ---------------------------------------------------------------------------

# Subcommands that can be routed through the daemon
_DAEMON_COMMANDS = {
    "navigate", "click", "fill", "text", "screenshot",
    "page-text", "wait", "evaluate", "login",
}


def _args_to_dict(args):
    """Convert argparse Namespace to a dict suitable for daemon dispatch."""
    d = vars(args).copy()
    d.pop("func", None)
    d.pop("subcommand", None)
    return d


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
    p.add_argument("--password", default=None)
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

    p = subparsers.add_parser("daemon")
    p.add_argument("--timeout", type=int, default=300)
    p.set_defaults(func=cmd_daemon)

    p = subparsers.add_parser("start-daemon")
    p.add_argument("--timeout", type=int, default=300)
    p.set_defaults(func=cmd_start_daemon)

    p = subparsers.add_parser("stop-daemon")
    p.set_defaults(func=cmd_stop_daemon)

    args = parser.parse_args()

    # Route browser commands through daemon if it's running
    if args.subcommand in _DAEMON_COMMANDS and _daemon_running():
        try:
            resp = _send_to_daemon(args.subcommand, _args_to_dict(args))
            _output(resp)
            return
        except Exception:
            # Fall back to per-command browser launch
            _err("Daemon connection failed, falling back to direct browser launch")

    args.func(args)


if __name__ == "__main__":
    main()
