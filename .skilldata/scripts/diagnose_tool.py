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
import json
import re
import sys


def _output(data):
    print(json.dumps(data, default=str))


ERROR_PATTERNS = [
    # SSH / Connectivity
    {
        "id": "ssh_unreachable",
        "regex": r"(UNREACHABLE!|connect to host.*Connection refused|No route to host|Connection timed out)",
        "category": "SSH/connectivity",
        "severity": "P0",
        "title": "Host Unreachable",
        "fix": "Check that the target host is running and SSH is enabled. Verify network connectivity with `ping <host>`.",
    },
    {
        "id": "ssh_permission",
        "regex": r"Permission denied \([^)]+\)",
        "category": "SSH/connectivity",
        "severity": "ENV",
        "title": "SSH Authentication Failed",
        "fix": "Check SSH key configuration. For VMs, use `vm-exec` which handles password auth via serial console.",
    },
    {
        "id": "ssh_host_key",
        "regex": r"REMOTE HOST IDENTIFICATION HAS CHANGED|Host key verification failed",
        "category": "SSH/connectivity",
        "severity": "ENV",
        "title": "SSH Host Key Changed",
        "fix": "Run `ssh-keygen -R <host>` to remove the old host key, then reconnect.",
    },
    # Ansible
    {
        "id": "missing_collection",
        "regex": r"couldn't resolve module/action '([^']+)'",
        "category": "Missing dependency",
        "severity": "P1",
        "title": "Missing Ansible Collection",
        "fix": "Install the required collection: `ansible-galaxy collection install <namespace>.<collection>`",
    },
    {
        "id": "undefined_variable",
        "regex": r"(AnsibleUndefinedVariable|'[^']+' is undefined)",
        "category": "Syntax error",
        "severity": "P1",
        "title": "Undefined Variable",
        "fix": "Check variable name spelling and ensure the variable is defined in vars, group_vars, or host_vars.",
    },
    {
        "id": "yaml_syntax",
        "regex": r"(Syntax Error while loading YAML|mapping values are not allowed|could not find expected ':')",
        "category": "Syntax error",
        "severity": "P0",
        "title": "YAML Syntax Error",
        "fix": "Check YAML indentation and syntax. Use `yamllint` or `ansible-navigator run --syntax-check`.",
    },
    {
        "id": "module_failed",
        "regex": r'FAILED! => \{.*"msg":\s*"([^"]+)"',
        "category": "Module error",
        "severity": "P1",
        "title": "Module Execution Failed",
        "fix": "Check the module parameters and target host state.",
    },
    {
        "id": "file_not_found",
        "regex": r"(Could not find or access|No such file or directory|Unable to retrieve file contents).*?['\"]([^'\"]+)['\"]",
        "category": "Missing file",
        "severity": "P1",
        "title": "File Not Found",
        "fix": "Verify the file path exists. Check if a previous step was supposed to create it.",
    },
    # OCP / Kubernetes
    {
        "id": "ocp_not_found",
        "regex": r"Error from server \(NotFound\): (.+) not found",
        "category": "Missing resource",
        "severity": "P1",
        "title": "Kubernetes Resource Not Found",
        "fix": "Check the resource name, namespace, and type. Use `oc get <type> -n <ns>` to verify.",
    },
    {
        "id": "ocp_forbidden",
        "regex": r"Error from server \(Forbidden\)|cannot .+ in the namespace",
        "category": "Permission error",
        "severity": "ENV",
        "title": "Kubernetes Permission Denied",
        "fix": "Check user permissions. Login as admin: `oc login -u admin -p redhatocp`.",
    },
    {
        "id": "ocp_timeout",
        "regex": r"timed out waiting for the condition",
        "category": "Timeout",
        "severity": "P2",
        "title": "Resource Condition Timeout",
        "fix": "Increase the timeout or check resource status with `oc describe <resource>`.",
    },
    {
        "id": "pvc_pending",
        "regex": r"(waiting for a volume to be created|PVC.*Pending)",
        "category": "Storage",
        "severity": "P2",
        "title": "PVC Not Binding",
        "fix": "Check storage class availability: `oc get sc`. Verify PV capacity and access modes match.",
    },
    {
        "id": "resourcelist_error",
        "regex": r"ResourceList\.__init__\(\) got an unexpected keyword argument",
        "category": "Environment",
        "severity": "ENV",
        "title": "Python Kubernetes Library Incompatibility",
        "fix": "The kubernetes Python library version is incompatible. Try `lab force <sku>` or reinstall the grading package.",
    },
    # DynoLabs / Grading
    {
        "id": "lab_not_found",
        "regex": r"Lab ID '([^']+)'.*not found in manifest",
        "category": "Missing dependency",
        "severity": "ENV",
        "title": "Exercise Not in Lab Manifest",
        "fix": "Install the correct package: `lab force <sku>`. Check `lab list` for available SKUs.",
    },
    {
        "id": "lab_blocked",
        "regex": r"another lab is in progress|lab finish (\S+)",
        "category": "Lab state",
        "severity": "ENV",
        "title": "Another Lab is Running",
        "fix": "Finish the blocking lab: `lab finish <name>` or reset: `lab status <name> --reset`.",
    },
    {
        "id": "catalog_source",
        "regex": r"Checking CatalogSource.*FAIL|CatalogSource.*failed",
        "category": "Environment",
        "severity": "ENV",
        "title": "CatalogSource Check Failed",
        "fix": "Verify CatalogSource is healthy: `oc get catalogsource -n openshift-marketplace`. May be a transient issue or library incompatibility.",
    },
    {
        "id": "disk_full",
        "regex": r"(no space left on device|disk quota exceeded|Disk full)",
        "category": "Environment",
        "severity": "ENV",
        "title": "Disk Full",
        "fix": "Free disk space: `podman system prune -af && rm -rf ~/.cache/uv`.",
    },
    {
        "id": "ee_pull_failed",
        "regex": r"(Error:.*pulling image|unable to pull|manifest unknown)",
        "category": "Environment",
        "severity": "ENV",
        "title": "Execution Environment Pull Failed",
        "fix": "Check registry access and image name. Try `podman pull <image>` manually.",
    },
    # Generic
    {
        "id": "permission_denied",
        "regex": r"(Permission denied|Operation not permitted|requires root)",
        "category": "Permission error",
        "severity": "P1",
        "title": "Permission/Privilege Issue",
        "fix": "Check if `become: true` is needed in the playbook, or if the user has sufficient permissions.",
    },
]


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


def cmd_analyze(args):
    """Analyze error text for known patterns."""
    if args.text == "-":
        text = sys.stdin.read()
    elif args.file:
        text = open(args.file).read()
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
