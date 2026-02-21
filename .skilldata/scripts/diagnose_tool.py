#!/usr/bin/env python3
"""Error diagnosis tool — pattern-based error analysis with fix suggestions.

Analyzes command output and lab logs to identify root causes and suggest fixes.
All output is JSON to stdout, diagnostics to stderr.

Usage:
    python3 diagnose_tool.py analyze <text>
    python3 diagnose_tool.py analyze --file <path>
    echo "error output" | python3 diagnose_tool.py analyze -
"""

import argparse
import os
import re
import sys
from pathlib import Path

from eqa_common import _output, _err, json_safe


def _load_error_patterns() -> list:
    """Load error patterns from .skilldata/config/errors.yaml.

    Falls back to a minimal built-in set if the YAML file is missing
    or pyyaml is not installed.
    """
    yaml_path = Path(__file__).parent.parent / "config" / "errors.yaml"
    if yaml_path.exists():
        try:
            import yaml
            with open(yaml_path) as f:
                patterns = yaml.safe_load(f)
            if isinstance(patterns, list):
                return patterns
        except Exception as e:
            _err(f"Warning: Failed to load {yaml_path}: {e}")

    # Minimal fallback — covers the most common cases
    return [
        {"id": "ssh_unreachable", "regex": r"(UNREACHABLE!|connect to host.*Connection refused|No route to host)",
         "category": "SSH/connectivity", "severity": "P0", "title": "Host Unreachable",
         "fix": "Check that the target host is running and SSH is enabled."},
        {"id": "yaml_syntax", "regex": r"(Syntax Error while loading YAML|mapping values are not allowed)",
         "category": "Syntax error", "severity": "P0", "title": "YAML Syntax Error",
         "fix": "Check YAML indentation and syntax."},
        {"id": "disk_full", "regex": r"(no space left on device|disk quota exceeded)",
         "category": "Environment", "severity": "ENV", "title": "Disk Full",
         "fix": "Free disk space: `podman system prune -af && rm -rf ~/.cache/uv`."},
    ]


ERROR_PATTERNS = _load_error_patterns()


def diagnose(text: str) -> dict:
    """Analyze text for known error patterns.

    Returns:
        dict with findings list, each containing id, title, severity, category, fix, matched_text
    """
    findings = []
    seen_ids = set()

    for pattern in ERROR_PATTERNS:
        match = re.search(pattern["regex"], text, re.IGNORECASE | re.MULTILINE)
        if match and pattern["id"] not in seen_ids:
            seen_ids.add(pattern["id"])
            findings.append({
                "id": pattern["id"],
                "title": pattern["title"],
                "severity": pattern["severity"],
                "category": pattern["category"],
                "fix": pattern["fix"],
                "matched_text": match.group(0)[:200],
            })

    # Sort by severity priority
    severity_order = {"P0": 0, "ENV": 1, "P1": 2, "P2": 3, "P3": 4}
    findings.sort(key=lambda f: severity_order.get(f["severity"], 5))

    return {
        "success": True,
        "findings": findings,
        "has_errors": len(findings) > 0,
        "highest_severity": findings[0]["severity"] if findings else None,
    }


@json_safe
def cmd_analyze(args):
    """Analyze error text for known patterns."""
    if args.text == "-":
        text = sys.stdin.read()
    elif args.file:
        with open(args.file) as f:
            text = f.read()
    else:
        text = args.text

    result = diagnose(text)
    _output(result)


def main():
    parser = argparse.ArgumentParser(description="Error diagnosis tool for eqa")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    p = subparsers.add_parser("analyze")
    p.add_argument("text", nargs="?", default="-")
    p.add_argument("--file", "-f", default=None)
    p.set_defaults(func=cmd_analyze)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
