#!/usr/bin/env python3
"""Course profile builder - analyzes EPUB content to understand the course.

All output is JSON to stdout, diagnostics to stderr.

Usage:
    python3 profile_tool.py build <epub_extract_dir>
"""

import argparse
import json
import re
import sys
from pathlib import Path


def _output(data):
    print(json.dumps(data, default=str))


def _err(msg):
    print(msg, file=sys.stderr)


NAVIGATOR_PATTERNS = [
    r'ansible-navigator',
    r'navigator\s+run',
    r'-m\s+stdout',
    r'ansible-navigator\.ya?ml',
]

DEV_TOOLS_PATTERNS = [
    r'ansible\s+development\s+tools',
    r'ansible-dev-tools',
    r'ansible-devtools',
    r'adt\b',
    r'vscode.*ansible',
    r'ansible\s+extension',
    r'devcontainer',
]

AAP_PATTERNS = [
    r'automation\s+controller',
    r'ansible\s+controller',
    r'ansible\s+tower',
    r'AAP\s+controller',
    r'controller\.example\.com',
]

CONTAINER_PATTERNS = [
    r'\bpodman\b',
    r'\bdocker\b',
    r'container\s+image',
    r'execution\s+environment',
    r'\bEE\b',
    r'ee-supported',
    r'ee-minimal',
]

OPENSHIFT_PATTERNS = [
    r'\boc\s+',
    r'openshift',
    r'kubernetes',
    r'\bkubectl\b',
]

INTENTIONAL_ERROR_PATTERNS = [
    r'intentional(?:ly)?\s+(?:broken|incorrect|wrong|error)',
    r'deliberate(?:ly)?\s+(?:broken|incorrect|wrong|error)',
    r'fix\s+the\s+(?:broken|incorrect|error)',
    r'troubleshoot(?:ing)?\s+the',
    r'identify\s+the\s+(?:error|problem|issue|bug)',
    r'find\s+(?:and\s+fix|the\s+error)',
    r'debug(?:ging)?\s+the',
    r'what\s+is\s+wrong',
    r'correct\s+the\s+(?:error|mistake|problem)',
]

VM_SSH_KEY_PATTERNS = [
    r'ssh_authorized_keys',
    r'ssh-rsa\s+AAAA',
    r'authorized_keys',
    r'identity.*file',
    r'virtctl\s+ssh\b',
]

VM_PASSWORD_PATTERNS = [
    r'log\s*in\s+as\s+(?:the\s+)?root\s+user\s+with\s+\w+\s+as\s+the\s+password',
    r'password.*redhat',
    r'chpasswd',
    r'passwd\s+--stdin',
    r'console\s+tab.*log\s*in',
]

STANDARD_HOSTS = {
    'servera', 'serverb', 'serverc', 'serverd', 'servere',
    'workstation', 'bastion', 'utility',
}

TOOL_PATTERNS = {
    'lab': r'\blab\s+(?:start|finish|grade)',
    'ansible-navigator': r'ansible-navigator',
    'ansible-playbook': r'ansible-playbook',
    'ansible-lint': r'ansible-lint',
    'yamllint': r'yamllint',
    'ansible-galaxy': r'ansible-galaxy',
    'podman': r'\bpodman\b',
    'docker': r'\bdocker\b',
    'oc': r'\boc\s+(?:login|get|create|apply)',
    'git': r'\bgit\s+(?:clone|pull|push|commit)',
    'python3': r'\bpython3?\b',
    'pip': r'\bpip3?\s+install',
    'uv': r'\buv\s+run',
    'ansible-builder': r'ansible-builder',
    'molecule': r'\bmolecule\b',
    'ansible-dev-tools': r'ansible.*dev.*tools',
}


def _read_all_content(epub_dir: Path) -> str:
    """Read all text from extracted EPUB HTML files."""
    from bs4 import BeautifulSoup

    all_text = []
    for html_file in sorted(list(epub_dir.rglob("*.xhtml")) + list(epub_dir.rglob("*.html"))):
        try:
            content = html_file.read_text(encoding='utf-8', errors='ignore')
            soup = BeautifulSoup(content, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            all_text.append(text)
        except Exception:
            continue
    return '\n'.join(all_text)


def cmd_build(args):
    """Build course profile from extracted EPUB content."""
    epub_dir = Path(args.epub_extract_dir).expanduser().resolve()

    if not epub_dir.exists():
        _output({"success": False, "error": f"Directory not found: {epub_dir}"})
        return

    _err("Analyzing course content...")
    text = _read_all_content(epub_dir)

    if not text:
        _output({"success": False, "error": "No content found in EPUB"})
        return

    text_lower = text.lower()
    profile = {"success": True}

    # Dev environment
    devcontainer_indicators = [
        r'\.devcontainer', r'devcontainer\.json', r'development\s+container',
        r'dev\s+container', r'open.*folder.*inside.*dev', r'reopen.*in.*container',
    ]
    devcontainer_count = sum(1 for p in devcontainer_indicators if re.search(p, text_lower))
    profile["uses_dev_containers"] = devcontainer_count >= 2

    if profile["uses_dev_containers"]:
        image_match = re.search(r'(registry\.redhat\.io/[^\s"]+|quay\.io/[^\s"]+)', text)
        profile["dev_container_image"] = image_match.group(1) if image_match else None

    vscode_indicators = [
        r'visual\s+studio\s+code', r'\bvs\s+code\b', r'\bvscode\b',
        r'explorer\s+icon.*activity\s+bar', r'click.*file.*›.*new.*text.*file',
    ]
    vscode_count = sum(1 for p in vscode_indicators if re.search(p, text_lower))
    profile["uses_vscode"] = vscode_count >= 2

    # Tech stack
    nav_count = sum(1 for p in NAVIGATOR_PATTERNS if re.search(p, text_lower))
    profile["uses_ansible_navigator"] = nav_count >= 2

    dev_count = sum(1 for p in DEV_TOOLS_PATTERNS if re.search(p, text_lower))
    profile["uses_ansible_dev_tools"] = dev_count >= 1

    playbook_refs = len(re.findall(r'ansible-playbook\b', text_lower))
    profile["uses_ansible_playbook"] = playbook_refs > 3 and not profile["uses_ansible_navigator"]

    aap_count = sum(1 for p in AAP_PATTERNS if re.search(p, text_lower))
    profile["uses_aap_controller"] = aap_count >= 2

    container_count = sum(1 for p in CONTAINER_PATTERNS if re.search(p, text_lower))
    profile["uses_containers"] = container_count >= 2
    profile["uses_execution_environments"] = bool(re.search(r'execution.environment', text_lower))

    oc_count = sum(1 for p in OPENSHIFT_PATTERNS if re.search(p, text_lower))
    profile["uses_openshift"] = oc_count >= 2

    # Tools and locations
    workstation_tools = []
    container_tools = []
    expected_tools = []

    for tool, pattern in TOOL_PATTERNS.items():
        if re.search(pattern, text_lower):
            expected_tools.append(tool)
            if tool == 'lab':
                workstation_tools.append(tool)
            elif profile["uses_dev_containers"]:
                if tool in ['ansible-navigator', 'ansible-playbook', 'ansible-lint',
                            'yamllint', 'ansible-galaxy', 'ansible-builder', 'molecule']:
                    container_tools.append(tool)
                elif tool in ['git', 'podman', 'oc']:
                    workstation_tools.append(tool)
                else:
                    container_tools.append(tool)
            else:
                workstation_tools.append(tool)

    profile["workstation_tools"] = sorted(set(workstation_tools))
    profile["container_tools"] = sorted(set(container_tools))
    profile["expected_tools"] = sorted(set(expected_tools))

    # Teaching patterns
    profile["has_intentional_errors"] = any(
        re.search(p, text_lower) for p in INTENTIONAL_ERROR_PATTERNS
    )
    profile["progressive_exercises"] = bool(
        re.search(r'previous\s+exercise|building\s+on|continuation\s+of', text_lower)
    )

    # Conventions
    profile["uses_sol_files"] = bool(re.search(r'\.sol\b', text_lower))
    profile["uses_solve_playbooks"] = bool(re.search(r'lab\s+solve|solve\s+playbook', text_lower))
    profile["uses_lab_grade"] = bool(re.search(r'lab\s+grade', text_lower))

    # VM authentication
    ssh_key_count = sum(1 for p in VM_SSH_KEY_PATTERNS if re.search(p, text_lower))
    password_count = sum(1 for p in VM_PASSWORD_PATTERNS if re.search(p, text_lower))
    profile["vm_auth"] = "ssh_keys" if ssh_key_count >= 2 else ("password" if password_count >= 2 else "unknown")
    pw_match = re.search(r'log\s*in\s+as\s+(?:the\s+)?root\s+user\s+with\s+(\w+)\s+as\s+the\s+password', text_lower)
    profile["vm_default_password"] = pw_match.group(1) if pw_match else None

    # Real hosts
    real_hosts = []
    for host in STANDARD_HOSTS:
        if host in text_lower:
            real_hosts.append(host)
    profile["real_hosts"] = sorted(real_hosts)

    # Collections — filter out hostname FQDNs that look like namespace.collection
    collections = set()
    # Patterns that are hostnames, not Ansible collections
    hostname_patterns = [
        r'^server[a-e]\.lab$',
        r'^[a-z]+\.lab$',         # *.lab.example.com hostnames
        r'^[a-z]+\.example$',     # *.example.com hostnames
        r'^console\.redhat$',     # console.redhat.com
        r'^docs\.ansible$',       # docs.ansible.com
        r'^galaxy\.ansible$',     # galaxy.ansible.com
    ]
    for match in re.finditer(r'\b([a-z_]+\.[a-z_]+)\.[a-z_]+\b', text_lower):
        collection = match.group(1)
        if collection == 'ansible.builtin':
            continue
        if any(collection.startswith(p) for p in ['www.', 'e.g.', 'i.e.']):
            continue
        if any(re.match(hp, collection) for hp in hostname_patterns):
            continue
        collections.add(collection)
    profile["referenced_collections"] = sorted(collections)

    _output(profile)


def main():
    parser = argparse.ArgumentParser(description="Course profile tool for eqa")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    p_build = subparsers.add_parser("build")
    p_build.add_argument("epub_extract_dir")
    p_build.set_defaults(func=cmd_build)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
