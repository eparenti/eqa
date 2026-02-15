#!/usr/bin/env python3
"""
Diagnose Ansible Errors and Suggest Fixes

Analyzes ansible-navigator error output and provides actionable solutions.

Usage:
    python diagnose_error.py <error-text-file>
    python diagnose_error.py - < error.txt
    echo "ERROR!" | python diagnose_error.py -
"""

import sys
import re
from pathlib import Path


# Compiled regex patterns for common extractions
LINE_NUMBER_RE = re.compile(r'line (\d+)')
FILE_PATH_RE = re.compile(r"in '([^']+\.ya?ml)")

ERROR_PATTERNS = {
    'missing_collection': {
        'regex': re.compile(r"couldn't resolve module/action '([^']+)'", re.IGNORECASE | re.MULTILINE),
        'title': 'Missing Ansible Collection',
        'severity': 'P1',
    },
    'unreachable_host': {
        'regex': re.compile(r'(UNREACHABLE!|connect to host.*Connection refused)', re.IGNORECASE | re.MULTILINE),
        'title': 'Host Unreachable',
        'severity': 'P0',
    },
    'file_not_found': {
        'regex': re.compile(r"(Could not find or access|No such file or directory|Unable to retrieve file contents).*?['\"]([^'\"]+)['\"]", re.IGNORECASE | re.MULTILINE),
        'title': 'File Not Found',
        'severity': 'P1',
    },
    'undefined_variable': {
        'regex': re.compile(r"(AnsibleUndefinedVariable:|is undefined).*?['\"]([^'\"]+)['\"]", re.IGNORECASE | re.MULTILINE),
        'title': 'Undefined Variable',
        'severity': 'P1',
    },
    'syntax_error': {
        'regex': re.compile(r'(Syntax Error while loading YAML|mapping values are not allowed)', re.IGNORECASE | re.MULTILINE),
        'title': 'YAML Syntax Error',
        'severity': 'P0',
    },
    'module_failed': {
        'regex': re.compile(r'FAILED! => \{.*"msg":\s*"([^"]+)"', re.IGNORECASE | re.MULTILINE),
        'title': 'Module Execution Failed',
        'severity': 'P1',
    },
    'permission_denied': {
        'regex': re.compile(r'(Permission denied|requires root|Operation not permitted)', re.IGNORECASE | re.MULTILINE),
        'title': 'Permission/Privilege Issue',
        'severity': 'P1',
    },
}


def extract_details(error_text, pattern_name):
    """Extract specific details from error text based on pattern."""
    pattern = ERROR_PATTERNS[pattern_name]
    match = pattern['regex'].search(error_text)

    if not match:
        return None

    details = {'groups': match.groups()}

    # Extract line number if present
    line_match = LINE_NUMBER_RE.search(error_text)
    if line_match:
        details['line_number'] = line_match.group(1)

    # Extract file path if present
    file_match = FILE_PATH_RE.search(error_text)
    if file_match:
        details['file_path'] = file_match.group(1)

    return details


def get_solutions_missing_collection(details):
    """Generate solutions for missing collection error."""
    module_path = details['groups'][0] if details['groups'] else 'unknown.module'
    collection = module_path.split('.')[0] + '.' + module_path.split('.')[1] if '.' in module_path else 'unknown'

    solutions = []

    # OPTION 1: Quick Install
    solutions.append({
        'option': 1,
        'title': 'Install Collection (Quick Fix) ✅ RECOMMENDED',
        'description': 'Immediately install the missing collection',
        'commands': [
            f'# Install {collection} collection',
            f'ssh workstation "ansible-galaxy collection install {collection}"',
            '',
            '# Verify installation',
            f'ssh workstation "ansible-galaxy collection list | grep {collection}"',
        ],
        'pros': [
            'Fast, immediate fix',
            'Works for manual testing',
            'No code changes needed',
        ],
        'cons': [
            'Not persistent across lab resets',
            'Doesn\'t fix root cause if collection should be in requirements',
        ],
        'verification': [
            '# Re-run the failing playbook',
            'ansible-navigator run solutions/<playbook>.sol -m stdout',
        ],
    })

    # OPTION 2: Add to requirements.yml
    solutions.append({
        'option': 2,
        'title': 'Add to requirements.yml (Proper Fix)',
        'description': 'Ensures collection is installed during lab setup',
        'commands': [
            '# 1. Navigate to lesson repo',
            'cd /home/developer/git-repos/active/<COURSE>/classroom/grading/src/<lesson>/ansible/',
            '',
            '# 2. Edit requirements.yml',
            'vi requirements.yml',
            '',
            '# Add this to collections section:',
            f'  - name: {collection}',
            '    version: ">=1.5.0"',
            '',
            '# 3. Install from requirements',
            'ssh workstation "ansible-galaxy collection install -r requirements.yml"',
            '',
            '# 4. Commit changes',
            'git add requirements.yml',
            f'git commit -m "Add {collection} to requirements.yml"',
        ],
        'pros': [
            'Proper solution, fixes root cause',
            'Persistent across lab setups',
            'Students will have collection available',
        ],
        'cons': [
            'Requires repo modification',
            'Need to update lab scripts',
        ],
        'verification': [
            '# Test with fresh lab',
            'ssh workstation "lab finish <lesson> && lab start <lesson>"',
        ],
    })

    # OPTION 3: Alternative Module
    if 'firewalld' in module_path:
        solutions.append({
            'option': 3,
            'title': 'Use command Module (Alternative)',
            'description': 'Replace module with firewall-cmd command',
            'commands': [
                '# Replace in playbook:',
                '# Before:',
                '- name: Configure firewall',
                '  ansible.posix.firewalld:',
                '    service: http',
                '    permanent: true',
                '    state: enabled',
                '',
                '# After:',
                '- name: Configure firewall',
                '  ansible.builtin.command:',
                '    cmd: firewall-cmd --permanent --add-service=http',
                '  notify: Reload firewall',
                '',
                '# Add handler:',
                'handlers:',
                '  - name: Reload firewall',
                '    ansible.builtin.command:',
                '      cmd: firewall-cmd --reload',
            ],
            'pros': [
                'No external dependencies',
                'Works immediately',
            ],
            'cons': [
                'Less idempotent than module',
                'More verbose',
                'May not match course objectives',
            ],
            'verification': [],
        })

    return solutions


def get_solutions_unreachable_host(details):
    """Generate solutions for unreachable host error."""
    solutions = []

    solutions.append({
        'option': 1,
        'title': 'Verify Lab Environment ✅ RECOMMENDED',
        'description': 'Check if lab is started and hosts are running',
        'commands': [
            '# 1. Check lab status',
            'ssh workstation "lab status"',
            '',
            '# 2. Restart lab if needed',
            'ssh workstation "lab finish <lesson> && lab start <lesson>"',
            '',
            '# 3. Test SSH connectivity',
            'ssh workstation "ssh servera hostname"',
            'ssh workstation "ssh serverb hostname"',
        ],
        'pros': [
            'Fixes most connectivity issues',
            'Resets environment to known state',
        ],
        'cons': [
            'Takes time to restart lab',
        ],
        'verification': [
            '# Test connectivity',
            'ssh workstation "ansible all -i inventory -m ping"',
        ],
    })

    solutions.append({
        'option': 2,
        'title': 'Check Inventory Configuration',
        'description': 'Verify inventory file has correct host definitions',
        'commands': [
            '# 1. Check inventory',
            'cat <exercise-dir>/inventory',
            '',
            '# 2. Verify hosts are defined',
            'ansible-navigator inventory --list -m stdout',
            '',
            '# 3. Test connectivity to specific host',
            'ansible-navigator run -m ping <hostname>',
        ],
        'pros': [
            'Identifies inventory misconfiguration',
        ],
        'cons': [
            'Requires manual inspection',
        ],
        'verification': [],
    })

    return solutions


def get_solutions_file_not_found(details):
    """Generate solutions for file not found error."""
    filename = details['groups'][1] if len(details['groups']) > 1 else 'unknown'

    solutions = []

    solutions.append({
        'option': 1,
        'title': 'Check File Path in Playbook ✅ RECOMMENDED',
        'description': 'Verify the src path is correct relative to playbook',
        'commands': [
            '# 1. Check current playbook reference',
            f'grep -n "{filename}" <playbook>.sol',
            '',
            '# 2. Check if file exists',
            'ls -la <exercise-dir>/files/',
            'ls -la <exercise-dir>/templates/',
            '',
            '# 3. Find the file',
            f'find <exercise-dir> -name "{filename}"',
            '',
            '# 4. Update path in playbook (if found)',
            '# Change: src: {filename}',
            '# To: src: files/{filename}',
        ],
        'pros': [
            'Fixes incorrect path references',
            'Most common issue',
        ],
        'cons': [
            'Requires playbook modification',
        ],
        'verification': [
            '# Re-run playbook',
            'ansible-navigator run solutions/<playbook>.sol -m stdout',
        ],
    })

    solutions.append({
        'option': 2,
        'title': 'Create Missing File',
        'description': 'Create the file if it should exist but doesn\'t',
        'commands': [
            '# 1. Navigate to files directory',
            'cd <exercise-dir>/files/',
            '',
            '# 2. Create file',
            f'cat > {filename} << \'EOF\'',
            '<content here>',
            'EOF',
            '',
            '# 3. Verify',
            f'ls -la {filename}',
        ],
        'pros': [
            'Provides missing file',
        ],
        'cons': [
            'Need to know correct content',
        ],
        'verification': [],
    })

    return solutions


def get_solutions_undefined_variable(details):
    """Generate solutions for undefined variable error."""
    variable = details['groups'][1] if len(details['groups']) > 1 else 'unknown'

    solutions = []

    solutions.append({
        'option': 1,
        'title': 'Define Missing Variable ✅ RECOMMENDED',
        'description': 'Add variable definition to playbook or vars file',
        'commands': [
            '# Option A: In playbook vars section',
            '- name: Play name',
            '  hosts: all',
            '  vars:',
            f'    {variable}: <value>',
            '',
            '# Option B: In separate vars file',
            'echo "{variable}: <value>" > vars.yml',
            '',
            '# Reference in playbook:',
            '- name: Play name',
            '  hosts: all',
            '  vars_files:',
            '    - vars.yml',
        ],
        'pros': [
            'Proper solution',
            'Makes variable explicit',
        ],
        'cons': [
            'Need to determine correct value',
        ],
        'verification': [
            '# Re-run playbook',
            'ansible-navigator run solutions/<playbook>.sol -m stdout',
        ],
    })

    solutions.append({
        'option': 2,
        'title': 'Use Default Filter',
        'description': 'Make variable optional with a default value',
        'commands': [
            '# In playbook, change:',
            f'# From: "{{{{ {variable} }}}}"',
            f'# To:   "{{{{ {variable} | default(\'default_value\') }}}}"',
        ],
        'pros': [
            'Graceful fallback',
            'Playbook still runs',
        ],
        'cons': [
            'May hide configuration issues',
            'Default might not be appropriate',
        ],
        'verification': [],
    })

    return solutions


def get_solutions_syntax_error(details):
    """Generate solutions for YAML syntax error."""
    solutions = []

    line = details.get('line_number', 'unknown')

    solutions.append({
        'option': 1,
        'title': 'Fix YAML Indentation ✅ RECOMMENDED',
        'description': 'Check indentation around the error line',
        'commands': [
            f'# 1. View lines around error (line {line})',
            f'head -n {int(line)+5} <playbook>.sol | tail -15',
            '',
            '# 2. Validate YAML syntax',
            'yamllint <playbook>.sol',
            '',
            '# Common fixes:',
            '# - Ensure consistent 2-space indentation',
            '# - Check that list items start with "- "',
            '# - Verify colons have space after them',
            '# - Check quote matching',
        ],
        'pros': [
            'Fixes root cause',
        ],
        'cons': [
            'Requires manual inspection',
        ],
        'verification': [
            '# Validate syntax',
            'yamllint <playbook>.sol',
            '',
            '# Test playbook',
            'ansible-navigator run <playbook>.sol -m stdout --syntax-check',
        ],
    })

    return solutions


def diagnose_error(error_text):
    """Diagnose error and provide solutions."""
    results = {
        'detected_problems': [],
    }

    # Check each pattern
    for pattern_name, pattern_info in ERROR_PATTERNS.items():
        if pattern_info['regex'].search(error_text):
            details = extract_details(error_text, pattern_name)

            # Get solutions based on pattern
            solutions = None
            if pattern_name == 'missing_collection':
                solutions = get_solutions_missing_collection(details)
            elif pattern_name == 'unreachable_host':
                solutions = get_solutions_unreachable_host(details)
            elif pattern_name == 'file_not_found':
                solutions = get_solutions_file_not_found(details)
            elif pattern_name == 'undefined_variable':
                solutions = get_solutions_undefined_variable(details)
            elif pattern_name == 'syntax_error':
                solutions = get_solutions_syntax_error(details)

            problem = {
                'pattern': pattern_name,
                'title': pattern_info['title'],
                'severity': pattern_info['severity'],
                'details': details,
                'solutions': solutions or [],
            }

            results['detected_problems'].append(problem)

    return results


def print_solutions(results):
    """Print formatted solutions."""
    if not results['detected_problems']:
        print("✅ No known error patterns detected")
        print("\n💡 For manual diagnosis, check:")
        print("   - Error message carefully")
        print("   - Playbook syntax")
        print("   - Host connectivity")
        print("   - File paths")
        return

    for i, problem in enumerate(results['detected_problems'], 1):
        print(f"\n{'='*80}")
        print(f"🔴 PROBLEM {i}: {problem['title']}")
        print(f"   Severity: {problem['severity']}")
        print(f"{'='*80}\n")

        if problem['details']:
            if problem['details'].get('line_number'):
                print(f"📍 Line: {problem['details']['line_number']}")
            if problem['details'].get('file_path'):
                print(f"📁 File: {problem['details']['file_path']}")
            if problem['details'].get('groups'):
                print(f"🔍 Details: {problem['details']['groups']}")
            print()

        if not problem['solutions']:
            print("⚠️  No automated solutions available for this error")
            continue

        for solution in problem['solutions']:
            print(f"\n{'─'*80}")
            print(f"🔧 OPTION {solution['option']}: {solution['title']}")
            print(f"{'─'*80}")
            print(f"\n📝 {solution['description']}\n")

            if solution['commands']:
                print("💻 COMMANDS:\n")
                for cmd in solution['commands']:
                    print(f"   {cmd}")
                print()

            if solution['pros']:
                print("✅ PROS:")
                for pro in solution['pros']:
                    print(f"   • {pro}")
                print()

            if solution['cons']:
                print("⚠️  CONS:")
                for con in solution['cons']:
                    print(f"   • {con}")
                print()

            if solution['verification']:
                print("🔍 VERIFICATION:\n")
                for verify in solution['verification']:
                    print(f"   {verify}")
                print()

        print(f"\n{'='*80}")
        print(f"💡 RECOMMENDATION: Use Option 1 (marked with ✅)")
        print(f"{'='*80}\n")


def main():
    if len(sys.argv) < 2:
        print("❌ Error: Error text required")
        print("\nUsage:")
        print("  python diagnose_error.py <error-file>")
        print("  python diagnose_error.py - < error.txt")
        print("  echo 'ERROR!' | python diagnose_error.py -")
        sys.exit(1)

    # Read error text
    if sys.argv[1] == '-':
        error_text = sys.stdin.read()
    else:
        error_file = Path(sys.argv[1])
        if not error_file.exists():
            print(f"❌ Error file not found: {error_file}")
            sys.exit(1)
        error_text = error_file.read_text()

    # Diagnose
    results = diagnose_error(error_text)

    # Print solutions
    print_solutions(results)


if __name__ == "__main__":
    main()
