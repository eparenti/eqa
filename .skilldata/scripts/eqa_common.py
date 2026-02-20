"""Shared utilities for EQA tool scripts.

Provides common I/O helpers, cache directory management, state file I/O,
and a @json_safe decorator for consistent error handling.
"""

import functools
import json
import os
import sys
import traceback


def _output(data):
    """Print JSON to stdout with default=str for non-serializable types."""
    print(json.dumps(data, default=str))


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
