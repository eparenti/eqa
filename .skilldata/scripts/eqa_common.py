"""Shared utilities for EQA tool scripts.

Provides common I/O helpers, cache directory management, state file I/O,
a @json_safe decorator for consistent error handling, secret redaction,
debug logging, and config file loading.
"""

import functools
import json
import logging
import logging.handlers
import os
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

_secrets: set = set()
_secret_re: re.Pattern | None = None


def register_secrets(*values):
    """Register strings to be redacted from all JSON output."""
    global _secret_re
    changed = False
    for v in values:
        if v and isinstance(v, str) and len(v) >= 4:
            if v not in _secrets:
                _secrets.add(v)
                changed = True
    if changed:
        # Recompile once per batch of new secrets.  Longest-first so
        # "Student@123" is matched before "Student".
        ordered = sorted(_secrets, key=len, reverse=True)
        _secret_re = re.compile('|'.join(re.escape(s) for s in ordered))


def _redact(text: str) -> str:
    """Replace registered secrets in a string with '***'."""
    if _secret_re is None:
        return text
    return _secret_re.sub('***', text)


def _redact_data(obj):
    """Recursively redact secrets in dicts, lists, and strings."""
    if isinstance(obj, str):
        return _redact(obj)
    if isinstance(obj, dict):
        return {k: _redact_data(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_data(v) for v in obj]
    return obj


def _output(data):
    """Print JSON to stdout (fd 1), redacting registered secrets.

    Writes directly to fd 1 to bypass any sys.stdout redirection from
    the stdout_guard context manager, ensuring clean JSON output even
    if third-party libraries have written to sys.stdout.
    """
    line = json.dumps(_redact_data(data), default=str) + "\n"
    os.write(1, line.encode())


class stdout_guard:
    """Context manager that redirects sys.stdout to sys.stderr.

    Prevents third-party library stdout pollution from corrupting JSON
    output.  The _output() function writes directly to fd 1, so it is
    unaffected by this redirection.

    Usage::

        with stdout_guard():
            # Any print() or sys.stdout.write() goes to stderr
            do_work()
        # _output({...}) still writes clean JSON to fd 1
    """

    def __enter__(self):
        self._orig = sys.stdout
        sys.stdout = sys.stderr
        return self

    def __exit__(self, *exc):
        sys.stdout = self._orig
        return False


def _err(msg):
    """Print diagnostic message to stderr."""
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# Debug log  (~/.cache/eqa/debug.log, rotating, 2 MB × 3 backups)
# ---------------------------------------------------------------------------

_debug_logger: logging.Logger | None = None


def _get_debug_logger() -> logging.Logger:
    """Lazily initialise and return the rotating debug logger."""
    global _debug_logger
    if _debug_logger is not None:
        return _debug_logger

    cache_dir = get_cache_dir()
    log_path = os.path.join(cache_dir, "debug.log")

    logger = logging.getLogger("eqa.debug")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False          # don't leak to root / stderr

    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=2 * 1024 * 1024, backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-5s [%(caller)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(handler)

    _debug_logger = logger
    return logger


def debug_log(msg: str, *, level: int = logging.DEBUG, caller: str = ""):
    """Append a redacted message to the rotating debug log.

    Parameters
    ----------
    msg : str
        Free-form message.  Registered secrets are redacted before writing.
    level : int
        Logging level (default DEBUG).
    caller : str
        Short label for the calling tool (e.g. "ssh", "epub").  Shown in
        the ``[caller]`` field of each log line.
    """
    logger = _get_debug_logger()
    logger.log(level, _redact(msg), extra={"caller": caller or "eqa"})


def get_cache_dir():
    """Return ~/.cache/eqa/, creating with 0o700 if needed."""
    cache_dir = os.path.expanduser("~/.cache/eqa")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, mode=0o700, exist_ok=True)
    return cache_dir


def get_state_path(tool_name):
    """Return ~/.cache/eqa/{tool_name}-state.json."""
    return os.path.join(get_cache_dir(), f"{tool_name}-state.json")


def load_state(path):
    """Load JSON state from file. Returns {} on missing/corrupt file."""
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_state(path, data):
    """Save JSON state to file, creating cache dir if needed."""
    get_cache_dir()  # ensure directory exists
    with open(path, 'w') as f:
        json.dump(data, f)


def find_epub(directory):
    """Find most recent EPUB in directory or its .cache/generated/en-US/ subdir."""
    directory = Path(directory)
    for location in [directory, directory / ".cache" / "generated" / "en-US"]:
        if location.exists():
            epubs = list(location.glob("*.epub"))
            if epubs:
                return max(epubs, key=lambda p: p.stat().st_mtime)
    return None


def build_epub(directory: Path) -> tuple[Path | None, str | None]:
    """Build EPUB using sk. Returns (epub_path, error_message).

    Locates the sk build tool, ensures ssh-agent is loaded, and runs
    'sk build epub3'. On success returns (Path, None). On failure
    returns (None, human-readable error string).
    """
    sk_path = shutil.which("sk")
    if not sk_path:
        for p in ["/usr/bin/sk", "/usr/local/bin/sk"]:
            if os.path.exists(p):
                sk_path = p
                break

    if not sk_path:
        return None, "sk tool not found"

    if not (directory / "outline.yml").exists():
        return None, "Not a scaffolding course (no outline.yml)"

    # Ensure ssh-agent has a key loaded (sk needs it for submodule access)
    try:
        result = subprocess.run(
            ["ssh-add", "-l"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            for key in [Path.home() / ".ssh" / "id_ed25519",
                        Path.home() / ".ssh" / "id_rsa"]:
                if key.exists():
                    subprocess.run(
                        ["ssh-add", str(key)],
                        capture_output=True, text=True, timeout=10,
                    )
                    break
    except Exception:
        pass

    _err(f"Building EPUB for {directory.name}...")
    try:
        result = subprocess.run(
            [sk_path, "build", "epub3"],
            cwd=directory, capture_output=True, text=True, timeout=600,
        )
        if result.returncode == 0:
            epub = find_epub(directory)
            return (epub, None) if epub else (None, "Build completed but EPUB not found")
        output = result.stdout + result.stderr
        if "Auth fail" in output or "JSchException" in output:
            return None, "SSH auth failed. Run: eval $(ssh-agent) && ssh-add"
        return None, f"Build failed (exit {result.returncode})"
    except subprocess.TimeoutExpired:
        return None, "Build timed out"
    except Exception as e:
        return None, str(e)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_config: dict | None = None

_CONFIG_DEFAULTS = {
    "repos_dir": "~/git-repos/active",
    "archive_dir": "~/git-repos/archive",
}


def load_config() -> dict:
    """Load config from ~/.config/eqa/config.yaml (or EQA_CONFIG env var).

    Returns a dict with at least repos_dir and archive_dir keys.
    Missing file or keys fall back to defaults.
    """
    global _config
    if _config is not None:
        return _config

    config_path = os.environ.get("EQA_CONFIG",
                                 os.path.expanduser("~/.config/eqa/config.yaml"))
    _config = dict(_CONFIG_DEFAULTS)

    if os.path.exists(config_path):
        try:
            import yaml
            with open(config_path) as f:
                user = yaml.safe_load(f)
            if isinstance(user, dict):
                _config.update(user)
        except Exception as e:
            _err(f"Warning: failed to parse {config_path}: {e}")

    # Expand ~ in path values
    for key in ("repos_dir", "archive_dir"):
        if key in _config and isinstance(_config[key], str):
            _config[key] = os.path.expanduser(_config[key])

    return _config


def json_safe(func):
    """Decorator: catch unhandled exceptions, output JSON error, traceback to stderr.

    Also wraps execution in stdout_guard so that any stray print()
    calls from dependencies go to stderr instead of corrupting JSON.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with stdout_guard():
            try:
                return func(*args, **kwargs)
            except SystemExit:
                raise
            except Exception as e:
                traceback.print_exc(file=sys.stderr)
                _output({"success": False, "error": f"Unhandled error: {e}"})
    return wrapper
