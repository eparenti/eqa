"""Error pattern definitions for diagnostic analysis.

Defines regex patterns for common Ansible and lab errors with associated
severity levels and metadata for generating fix recommendations.
"""

import re
from dataclasses import dataclass, field
from typing import List, Pattern, Optional
from enum import Enum


class ErrorCategory(Enum):
    """Categories of errors for grouping and prioritization."""
    COLLECTION = "collection"
    CONNECTIVITY = "connectivity"
    FILE_SYSTEM = "file_system"
    VARIABLE = "variable"
    SYNTAX = "syntax"
    MODULE = "module"
    PERMISSION = "permission"
    USER_GROUP = "user_group"
    SERVICE = "service"
    NETWORK_DEVICE = "network_device"
    LAB_COMMAND = "lab_command"


@dataclass
class PatternInfo:
    """Information about an error pattern."""
    name: str
    regex: Pattern
    title: str
    severity: str  # P0, P1, P2, P3
    category: ErrorCategory
    description: str
    fix_template: str
    verification_template: List[str] = field(default_factory=list)
    extract_groups: List[str] = field(default_factory=list)  # Named groups to extract


# Pre-compiled regex patterns for common errors
ERROR_PATTERNS: List[PatternInfo] = [
    # Collection-related errors
    PatternInfo(
        name="missing_collection",
        regex=re.compile(
            r"couldn't resolve module/action '(?P<module>[^']+)'",
            re.IGNORECASE | re.MULTILINE
        ),
        title="Missing Ansible Collection",
        severity="P1",
        category=ErrorCategory.COLLECTION,
        description="Required Ansible collection is not installed",
        fix_template=(
            "Install the missing collection:\n"
            "  ansible-galaxy collection install {collection_name}\n\n"
            "Or add to requirements.yml:\n"
            "  collections:\n"
            "    - name: {collection_name}"
        ),
        verification_template=[
            "ansible-galaxy collection list | grep {collection_name}",
            "ansible-navigator run <playbook> -m stdout --syntax-check"
        ],
        extract_groups=["module"]
    ),

    PatternInfo(
        name="collection_version_conflict",
        regex=re.compile(
            r"ERROR! Unexpected Exception.+Collection '(?P<collection>[^']+)'.+version conflict",
            re.IGNORECASE | re.DOTALL
        ),
        title="Collection Version Conflict",
        severity="P1",
        category=ErrorCategory.COLLECTION,
        description="Conflicting versions of an Ansible collection",
        fix_template=(
            "Resolve collection version conflict:\n"
            "  ansible-galaxy collection install {collection} --force"
        ),
        verification_template=[
            "ansible-galaxy collection list | grep {collection}"
        ],
        extract_groups=["collection"]
    ),

    # Connectivity errors
    PatternInfo(
        name="unreachable_host",
        regex=re.compile(
            r"(?:UNREACHABLE!|Failed to connect to the host|"
            r"connect to host.*(?:Connection refused|timed out|No route to host))",
            re.IGNORECASE | re.MULTILINE
        ),
        title="Host Unreachable",
        severity="P0",
        category=ErrorCategory.CONNECTIVITY,
        description="Cannot connect to target host",
        fix_template=(
            "1. Check if the host is running:\n"
            "   ping {host}\n\n"
            "2. Restart the lab if needed:\n"
            "   lab finish {exercise_id} && lab start {exercise_id}\n\n"
            "3. Verify SSH connectivity:\n"
            "   ssh {host} hostname"
        ),
        verification_template=[
            "ping -c 1 {host}",
            "ssh {host} hostname"
        ],
        extract_groups=[]
    ),

    PatternInfo(
        name="ssh_permission_denied",
        regex=re.compile(
            r"Permission denied \(publickey|Failed to authenticate|"
            r"Authentication failed",
            re.IGNORECASE | re.MULTILINE
        ),
        title="SSH Authentication Failed",
        severity="P1",
        category=ErrorCategory.CONNECTIVITY,
        description="SSH key or password authentication failed",
        fix_template=(
            "1. Check SSH key setup:\n"
            "   ssh-copy-id student@{host}\n\n"
            "2. Or configure key in ansible.cfg:\n"
            "   private_key_file = ~/.ssh/id_rsa"
        ),
        verification_template=[
            "ssh -o BatchMode=yes {host} hostname"
        ],
        extract_groups=[]
    ),

    # File system errors
    PatternInfo(
        name="file_not_found",
        regex=re.compile(
            r"(?:Could not find or access|No such file or directory|"
            r"Unable to retrieve file contents|"
            r"path '(?P<path>[^']+)' is not accessible).*?['\"]?(?P<file>[^'\"]+?)['\"]?",
            re.IGNORECASE | re.MULTILINE
        ),
        title="File Not Found",
        severity="P1",
        category=ErrorCategory.FILE_SYSTEM,
        description="Required file or directory does not exist",
        fix_template=(
            "1. Check if file exists:\n"
            "   ls -la {file}\n\n"
            "2. Search for the file:\n"
            "   find . -name '{basename}'\n\n"
            "3. Create missing file or fix path reference"
        ),
        verification_template=[
            "ls -la {file}",
            "test -f {file} && echo 'File exists'"
        ],
        extract_groups=["file", "path"]
    ),

    PatternInfo(
        name="template_not_found",
        regex=re.compile(
            r"TemplateNotFound|Could not locate template '(?P<template>[^']+)'",
            re.IGNORECASE | re.MULTILINE
        ),
        title="Template Not Found",
        severity="P1",
        category=ErrorCategory.FILE_SYSTEM,
        description="Jinja2 template file not found",
        fix_template=(
            "1. Check templates directory:\n"
            "   ls -la templates/\n\n"
            "2. Verify template path in playbook\n"
            "3. Create missing template file"
        ),
        verification_template=[
            "ls -la templates/{template}"
        ],
        extract_groups=["template"]
    ),

    # Variable errors
    PatternInfo(
        name="undefined_variable",
        regex=re.compile(
            r"(?:AnsibleUndefinedVariable|'(?P<variable>\w+)' is undefined)",
            re.IGNORECASE | re.MULTILINE
        ),
        title="Undefined Variable",
        severity="P1",
        category=ErrorCategory.VARIABLE,
        description="Variable used but not defined",
        fix_template=(
            "Define the variable:\n\n"
            "1. In playbook vars:\n"
            "   vars:\n"
            "     {variable}: <value>\n\n"
            "2. In vars file:\n"
            "   echo '{variable}: <value>' >> vars.yml\n\n"
            "3. Use default filter:\n"
            "   {{{{ {variable} | default('default_value') }}}}"
        ),
        verification_template=[
            "grep -r '{variable}' *.yml",
            "ansible-playbook --syntax-check <playbook>.yml"
        ],
        extract_groups=["variable"]
    ),

    PatternInfo(
        name="variable_type_error",
        regex=re.compile(
            r"(?:Unexpected templating type error|"
            r"'(?P<type>\w+)' object (?:has no attribute|is not iterable))",
            re.IGNORECASE | re.MULTILINE
        ),
        title="Variable Type Error",
        severity="P2",
        category=ErrorCategory.VARIABLE,
        description="Variable has unexpected type",
        fix_template=(
            "Check variable type and fix:\n"
            "1. Use type conversion filters: | int, | string, | list\n"
            "2. Verify variable structure in vars files"
        ),
        verification_template=[
            "ansible-playbook <playbook>.yml -e 'debug_mode=true'"
        ],
        extract_groups=["type"]
    ),

    # Syntax errors
    PatternInfo(
        name="yaml_syntax_error",
        regex=re.compile(
            r"(?:Syntax Error while loading YAML|"
            r"mapping values are not allowed|"
            r"found unexpected ':').*?(?:line (?P<line>\d+))?",
            re.IGNORECASE | re.MULTILINE
        ),
        title="YAML Syntax Error",
        severity="P0",
        category=ErrorCategory.SYNTAX,
        description="YAML file has syntax errors",
        fix_template=(
            "Fix YAML syntax:\n"
            "1. Check line {line} for:\n"
            "   - Incorrect indentation (use 2 spaces)\n"
            "   - Missing colon after key\n"
            "   - Mismatched quotes\n\n"
            "2. Validate with:\n"
            "   yamllint <file>.yml"
        ),
        verification_template=[
            "yamllint {file}",
            "ansible-playbook --syntax-check {file}"
        ],
        extract_groups=["line"]
    ),

    PatternInfo(
        name="jinja2_syntax_error",
        regex=re.compile(
            r"(?:TemplateSyntaxError|unexpected '(?P<token>[^']+)'|"
            r"Encountered unknown tag '(?P<tag>[^']+)')",
            re.IGNORECASE | re.MULTILINE
        ),
        title="Jinja2 Syntax Error",
        severity="P1",
        category=ErrorCategory.SYNTAX,
        description="Jinja2 template has syntax errors",
        fix_template=(
            "Fix Jinja2 syntax:\n"
            "1. Check for:\n"
            "   - Unclosed {{ or {%\n"
            "   - Missing filter arguments\n"
            "   - Invalid filter names\n\n"
            "2. Test template rendering locally"
        ),
        verification_template=[
            "ansible-playbook --syntax-check <playbook>.yml"
        ],
        extract_groups=["token", "tag"]
    ),

    # Module errors
    PatternInfo(
        name="module_failed",
        regex=re.compile(
            r"FAILED! => .*?\"msg\":\s*\"(?P<message>[^\"]+)\"",
            re.IGNORECASE | re.MULTILINE
        ),
        title="Module Execution Failed",
        severity="P1",
        category=ErrorCategory.MODULE,
        description="Ansible module execution failed",
        fix_template=(
            "Module failed with: {message}\n\n"
            "1. Check module documentation:\n"
            "   ansible-doc <module_name>\n\n"
            "2. Verify parameters are correct\n"
            "3. Check target system state"
        ),
        verification_template=[
            "ansible-doc <module_name>",
            "ansible-navigator run <playbook>.yml -m stdout"
        ],
        extract_groups=["message"]
    ),

    PatternInfo(
        name="module_not_found",
        regex=re.compile(
            r"(?:couldn't resolve module/action|"
            r"The module (?P<module>\w+) was not found)",
            re.IGNORECASE | re.MULTILINE
        ),
        title="Module Not Found",
        severity="P1",
        category=ErrorCategory.MODULE,
        description="Ansible module not found or not installed",
        fix_template=(
            "Install the required collection containing the module:\n"
            "  ansible-galaxy collection install <collection>\n\n"
            "Or use FQCN:\n"
            "  ansible.builtin.{module}"
        ),
        verification_template=[
            "ansible-doc -l | grep {module}"
        ],
        extract_groups=["module"]
    ),

    # Permission errors
    PatternInfo(
        name="permission_denied",
        regex=re.compile(
            r"(?:Permission denied|requires root|Operation not permitted|"
            r"Access denied|EACCES)",
            re.IGNORECASE | re.MULTILINE
        ),
        title="Permission Denied",
        severity="P1",
        category=ErrorCategory.PERMISSION,
        description="Operation requires elevated privileges",
        fix_template=(
            "1. Add become: true to the task or play:\n"
            "   - name: Task name\n"
            "     <module>: ...\n"
            "     become: true\n\n"
            "2. Check file permissions:\n"
            "   ls -la {file}"
        ),
        verification_template=[
            "ls -la {file}",
            "sudo -l"
        ],
        extract_groups=[]
    ),

    PatternInfo(
        name="selinux_denied",
        regex=re.compile(
            r"(?:SELinux is preventing|selinux.*denied|avc:.*denied)",
            re.IGNORECASE | re.MULTILINE
        ),
        title="SELinux Denial",
        severity="P2",
        category=ErrorCategory.PERMISSION,
        description="SELinux policy is blocking the operation",
        fix_template=(
            "1. Check SELinux audit log:\n"
            "   ausearch -m avc -ts recent\n\n"
            "2. Generate policy fix:\n"
            "   ausearch -m avc -ts recent | audit2allow\n\n"
            "3. Or set correct context:\n"
            "   restorecon -Rv <path>"
        ),
        verification_template=[
            "getenforce",
            "ls -lZ {file}"
        ],
        extract_groups=[]
    ),

    # User/Group errors
    PatternInfo(
        name="user_not_found",
        regex=re.compile(
            r"(?:user '(?P<user>[^']+)' does not exist|"
            r"invalid user|no such user)",
            re.IGNORECASE | re.MULTILINE
        ),
        title="User Not Found",
        severity="P1",
        category=ErrorCategory.USER_GROUP,
        description="Required user does not exist on system",
        fix_template=(
            "Create the user:\n"
            "  useradd {user}\n\n"
            "Or add to playbook:\n"
            "  - name: Create user\n"
            "    ansible.builtin.user:\n"
            "      name: {user}\n"
            "      state: present"
        ),
        verification_template=[
            "id {user}",
            "getent passwd {user}"
        ],
        extract_groups=["user"]
    ),

    PatternInfo(
        name="group_not_found",
        regex=re.compile(
            r"(?:group '(?P<group>[^']+)' does not exist|"
            r"invalid group|no such group)",
            re.IGNORECASE | re.MULTILINE
        ),
        title="Group Not Found",
        severity="P1",
        category=ErrorCategory.USER_GROUP,
        description="Required group does not exist on system",
        fix_template=(
            "Create the group:\n"
            "  groupadd {group}\n\n"
            "Or add to playbook:\n"
            "  - name: Create group\n"
            "    ansible.builtin.group:\n"
            "      name: {group}\n"
            "      state: present"
        ),
        verification_template=[
            "getent group {group}"
        ],
        extract_groups=["group"]
    ),

    # Service errors
    PatternInfo(
        name="service_failed",
        regex=re.compile(
            r"(?:Unit (?P<service>\S+) not found|"
            r"Failed to start (?P<service2>\S+)|"
            r"service (?P<service3>\S+).*(?:failed|not found))",
            re.IGNORECASE | re.MULTILINE
        ),
        title="Service Failed",
        severity="P1",
        category=ErrorCategory.SERVICE,
        description="Systemd service failed to start or not found",
        fix_template=(
            "1. Check service status:\n"
            "   systemctl status {service}\n\n"
            "2. Check logs:\n"
            "   journalctl -u {service} -n 50\n\n"
            "3. Verify service is installed:\n"
            "   systemctl list-unit-files | grep {service}"
        ),
        verification_template=[
            "systemctl status {service}",
            "systemctl is-active {service}"
        ],
        extract_groups=["service", "service2", "service3"]
    ),

    # Network device errors
    PatternInfo(
        name="network_device_timeout",
        regex=re.compile(
            r"(?:timed out|Connection timed out|"
            r"socket.timeout|Timeout exceeded)",
            re.IGNORECASE | re.MULTILINE
        ),
        title="Network Device Timeout",
        severity="P1",
        category=ErrorCategory.NETWORK_DEVICE,
        description="Connection to network device timed out",
        fix_template=(
            "Increase timeout for network device:\n"
            "1. Set ansible_command_timeout: 60\n"
            "2. For network_cli connection:\n"
            "   ansible_network_cli_ssh_type: libssh\n"
            "   ansible_command_timeout: 60"
        ),
        verification_template=[
            "ping {host}",
            "ssh {host} 'show version'"
        ],
        extract_groups=[]
    ),

    PatternInfo(
        name="network_cli_error",
        regex=re.compile(
            r"(?:command authorization failed|"
            r"Invalid command|Ambiguous command|"
            r"% (?P<error>.+))",
            re.IGNORECASE | re.MULTILINE
        ),
        title="Network CLI Error",
        severity="P1",
        category=ErrorCategory.NETWORK_DEVICE,
        description="Network device CLI command failed",
        fix_template=(
            "Check command syntax for the device:\n"
            "1. Verify command is valid for device type\n"
            "2. Check privilege level\n"
            "3. Review device documentation"
        ),
        verification_template=[
            "ssh {host} '{command}'"
        ],
        extract_groups=["error"]
    ),

    # Lab command errors
    PatternInfo(
        name="lab_start_failed",
        regex=re.compile(
            r"(?:lab start.*failed|Error starting lab|"
            r"Cannot start exercise)",
            re.IGNORECASE | re.MULTILINE
        ),
        title="Lab Start Failed",
        severity="P0",
        category=ErrorCategory.LAB_COMMAND,
        description="Lab start command failed",
        fix_template=(
            "1. Check lab status:\n"
            "   lab status {exercise_id}\n\n"
            "2. Reset lab environment:\n"
            "   lab finish {exercise_id}\n"
            "   lab start {exercise_id}\n\n"
            "3. Check OpenShift/VMs are running"
        ),
        verification_template=[
            "lab status {exercise_id}",
            "lab start {exercise_id}"
        ],
        extract_groups=[]
    ),

    PatternInfo(
        name="lab_grade_failed",
        regex=re.compile(
            r"(?:grading.*failed|FAIL|Overall grade: 0)",
            re.IGNORECASE | re.MULTILINE
        ),
        title="Lab Grading Failed",
        severity="P2",
        category=ErrorCategory.LAB_COMMAND,
        description="Lab grading did not pass",
        fix_template=(
            "1. Review grading output for specific failures\n"
            "2. Apply solution files if available:\n"
            "   cp solutions/*.sol .\n\n"
            "3. Re-run grading:\n"
            "   lab grade {exercise_id}"
        ),
        verification_template=[
            "lab grade {exercise_id}"
        ],
        extract_groups=[]
    ),
]


def get_patterns_by_category(category: ErrorCategory) -> List[PatternInfo]:
    """Get all patterns in a specific category."""
    return [p for p in ERROR_PATTERNS if p.category == category]


def get_patterns_by_severity(severity: str) -> List[PatternInfo]:
    """Get all patterns with a specific severity."""
    return [p for p in ERROR_PATTERNS if p.severity == severity]
