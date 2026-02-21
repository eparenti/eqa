"""Shared utilities for EQA tool scripts.

Provides common I/O helpers, cache directory management, state file I/O,
a @json_safe decorator for consistent error handling, secret redaction,
and config file loading.
"""

import functools
import json
import os
import sys
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

_secrets: set = set()


def register_secrets(*values):
    """Register strings to be redacted from all JSON output."""
    for v in values:
        if v and isinstance(v, str) and len(v) >= 4:
            _secrets.add(v)


def _redact(text: str) -> str:
    """Replace registered secrets in a string with '***'."""
    for s in _secrets:
        text = text.replace(s, "***")
    return text


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
    """Print JSON to stdout, redacting registered secrets."""
    print(json.dumps(_redact_data(data), default=str))


def _err(msg):
    """Print diagnostic message to stderr."""
    print(msg, file=sys.stderr)


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


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_config: dict = None

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
        except Exception:
            pass

    # Expand ~ in path values
    for key in ("repos_dir", "archive_dir"):
        if key in _config and isinstance(_config[key], str):
            _config[key] = os.path.expanduser(_config[key])

    return _config


def json_safe(func):
    """Decorator: catch unhandled exceptions, output JSON error, traceback to stderr."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SystemExit:
            raise
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            _output({"success": False, "error": f"Unhandled error: {e}"})
    return wrapper
