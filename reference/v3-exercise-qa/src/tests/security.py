"""TC-SECURITY: Security validation.

Tests for security issues in exercise materials:
- Hardcoded credentials/passwords
- Insecure file permissions
- Command injection vulnerabilities
- Exposed secrets/tokens
- Insecure practices in examples
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext
from ..clients.ssh import SSHConnection


class TC_SECURITY:
    """Security validation test category."""

    # Patterns that indicate hardcoded credentials
    CREDENTIAL_PATTERNS = [
        (r'password\s*[=:]\s*["\']?(?!{{)(?!\$\{)[a-zA-Z0-9!@#$%^&*]{4,}["\']?', 'hardcoded password'),
        (r'api_key\s*[=:]\s*["\']?[a-zA-Z0-9_-]{16,}["\']?', 'hardcoded API key'),
        (r'secret\s*[=:]\s*["\']?[a-zA-Z0-9_-]{8,}["\']?', 'hardcoded secret'),
        (r'token\s*[=:]\s*["\']?[a-zA-Z0-9_-]{16,}["\']?', 'hardcoded token'),
        (r'aws_access_key_id\s*[=:]\s*[A-Z0-9]{20}', 'AWS access key'),
        (r'aws_secret_access_key\s*[=:]\s*[a-zA-Z0-9/+=]{40}', 'AWS secret key'),
        (r'private_key\s*[=:]\s*-----BEGIN', 'private key'),
        (r'ssh_pass\s*[=:]\s*["\']?[^\s"\']+', 'SSH password'),
        (r'ansible_password\s*[=:]\s*["\']?(?!{{)[^\s"\']+', 'Ansible password'),
        (r'ansible_become_pass\s*[=:]\s*["\']?(?!{{)[^\s"\']+', 'become password'),
    ]

    # Patterns that indicate command injection risks
    INJECTION_PATTERNS = [
        (r'shell:\s*.*\$\{?\w+\}?(?!.*\|.*quote)', 'unquoted variable in shell'),
        (r'command:\s*.*\$\{?\w+\}?(?!.*\|.*quote)', 'unquoted variable in command'),
        (r'raw:\s*.*\$\{?\w+\}?', 'unquoted variable in raw'),
        (r'os\.system\s*\([^)]*\+', 'os.system with concatenation'),
        (r'subprocess\.(call|run|Popen)\s*\([^)]*shell\s*=\s*True', 'subprocess with shell=True'),
        (r'eval\s*\([^)]*\+', 'eval with concatenation'),
    ]

    # Insecure permission patterns
    PERMISSION_PATTERNS = [
        (r'mode:\s*["\']?0?777', 'world-writable permissions (777)'),
        (r'mode:\s*["\']?0?666', 'world-writable file (666)'),
        (r'chmod\s+777\s+', 'chmod 777 command'),
        (r'chmod\s+666\s+', 'chmod 666 command'),
        (r'chmod\s+-R\s+777', 'recursive chmod 777'),
    ]

    # Files that should never contain credentials
    SENSITIVE_FILE_PATTERNS = [
        '.env',
        'credentials',
        'secrets',
        '.password',
        '.key',
        '.pem',
    ]

    # Allowlisted patterns (false positives)
    ALLOWLIST_PATTERNS = [
        r'password:\s*["\']?\{\{',  # Jinja2 variable
        r'password:\s*["\']?\$\{',   # Shell variable
        r'password:\s*["\']?vault_', # Vault reference
        r'password:\s*["\']?lookup\(',  # Lookup plugin
        r'password:\s*!vault',  # Ansible vault
        r'#.*password',  # Comments
        r'example\.com',  # Example domains
        r'redhat123',  # Known training password
        r'student',  # Standard training password
    ]

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test for security issues in exercise materials.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-SECURITY: Testing security...")

        bugs_found = []
        start_time = datetime.now()
        files_scanned = 0
        issues_found = 0

        # Scan solution files
        print("   → Scanning solution files...")
        for sol_file in exercise.solution_files:
            if sol_file.exists():
                file_bugs = self._scan_file(sol_file, exercise.id)
                bugs_found.extend(file_bugs)
                files_scanned += 1
                issues_found += len(file_bugs)

        # Scan grading script
        if exercise.grading_script and exercise.grading_script.exists():
            print("   → Scanning grading script...")
            file_bugs = self._scan_file(exercise.grading_script, exercise.id)
            bugs_found.extend(file_bugs)
            files_scanned += 1
            issues_found += len(file_bugs)

        # Scan materials directory
        if exercise.materials_dir and exercise.materials_dir.exists():
            print("   → Scanning materials directory...")
            materials_bugs = self._scan_directory(exercise.materials_dir, exercise.id)
            bugs_found.extend(materials_bugs)
            issues_found += len(materials_bugs)

        # Check for sensitive files on remote system
        print("   → Checking remote system...")
        remote_bugs = self._check_remote_security(exercise, ssh)
        bugs_found.extend(remote_bugs)
        issues_found += len(remote_bugs)

        if issues_found == 0:
            print("      ✓ No security issues found")
        else:
            print(f"      ⚠  Found {issues_found} security issue(s)")

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-SECURITY",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'files_scanned': files_scanned,
                'issues_found': issues_found
            }
        )

    def _scan_file(self, file_path: Path, exercise_id: str) -> List[Bug]:
        """Scan a single file for security issues."""
        bugs = []

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            return bugs

        # Check credentials
        cred_bugs = self._check_credentials(content, file_path, exercise_id)
        bugs.extend(cred_bugs)

        # Check injection vulnerabilities
        injection_bugs = self._check_injection(content, file_path, exercise_id)
        bugs.extend(injection_bugs)

        # Check permissions
        perm_bugs = self._check_permissions(content, file_path, exercise_id)
        bugs.extend(perm_bugs)

        return bugs

    def _scan_directory(self, dir_path: Path, exercise_id: str) -> List[Bug]:
        """Scan a directory for security issues."""
        bugs = []

        # Scan relevant file types
        file_patterns = ['*.yml', '*.yaml', '*.py', '*.sh', '*.cfg', '*.ini', '*.j2', '*.json']

        for pattern in file_patterns:
            for file_path in dir_path.rglob(pattern):
                if file_path.is_file():
                    file_bugs = self._scan_file(file_path, exercise_id)
                    bugs.extend(file_bugs)

        # Check for sensitive files
        for file_path in dir_path.rglob('*'):
            if file_path.is_file():
                for sensitive_pattern in self.SENSITIVE_FILE_PATTERNS:
                    if sensitive_pattern in file_path.name.lower():
                        bugs.append(Bug(
                            id=f"SEC-SENSITIVE-{file_path.stem}-{exercise_id}",
                            severity=BugSeverity.P1_CRITICAL,
                            category="TC-SECURITY",
                            exercise_id=exercise_id,
                            description=f"Potentially sensitive file in materials: {file_path.name}",
                            fix_recommendation="Remove sensitive files or ensure they contain only examples",
                            verification_steps=[
                                f"Review: {file_path}",
                                "Ensure no real credentials are included"
                            ]
                        ))

        return bugs

    def _check_credentials(self, content: str, file_path: Path, exercise_id: str) -> List[Bug]:
        """Check for hardcoded credentials."""
        bugs = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            # Skip if line matches allowlist
            if self._is_allowlisted(line):
                continue

            for pattern, issue_type in self.CREDENTIAL_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    # Double-check against allowlist
                    if not self._is_allowlisted(line):
                        bugs.append(Bug(
                            id=f"SEC-CRED-{file_path.stem}-L{i}-{exercise_id}",
                            severity=BugSeverity.P1_CRITICAL,
                            category="TC-SECURITY",
                            exercise_id=exercise_id,
                            description=f"Possible {issue_type} at {file_path.name}:{i}",
                            fix_recommendation="Use variables, vault, or remove credentials",
                            verification_steps=[
                                f"Review line {i} of {file_path.name}",
                                "Replace with Ansible vault or variable"
                            ]
                        ))
                        break  # One bug per line

        return bugs

    def _check_injection(self, content: str, file_path: Path, exercise_id: str) -> List[Bug]:
        """Check for command injection vulnerabilities."""
        bugs = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            for pattern, issue_type in self.INJECTION_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    bugs.append(Bug(
                        id=f"SEC-INJ-{file_path.stem}-L{i}-{exercise_id}",
                        severity=BugSeverity.P2_HIGH,
                        category="TC-SECURITY",
                        exercise_id=exercise_id,
                        description=f"Possible {issue_type} at {file_path.name}:{i}",
                        fix_recommendation="Use proper quoting or parameterized commands",
                        verification_steps=[
                            f"Review line {i} of {file_path.name}",
                            "Use quote filter for variables in shell commands"
                        ]
                    ))
                    break  # One bug per line

        return bugs

    def _check_permissions(self, content: str, file_path: Path, exercise_id: str) -> List[Bug]:
        """Check for insecure file permissions."""
        bugs = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            for pattern, issue_type in self.PERMISSION_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    bugs.append(Bug(
                        id=f"SEC-PERM-{file_path.stem}-L{i}-{exercise_id}",
                        severity=BugSeverity.P2_HIGH,
                        category="TC-SECURITY",
                        exercise_id=exercise_id,
                        description=f"{issue_type} at {file_path.name}:{i}",
                        fix_recommendation="Use more restrictive permissions (e.g., 0644, 0755)",
                        verification_steps=[
                            f"Review line {i} of {file_path.name}",
                            "Change to appropriate permissions"
                        ]
                    ))
                    break  # One bug per line

        return bugs

    def _is_allowlisted(self, line: str) -> bool:
        """Check if a line matches allowlist patterns."""
        for pattern in self.ALLOWLIST_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        return False

    def _check_remote_security(self, exercise: ExerciseContext, ssh: SSHConnection) -> List[Bug]:
        """Check security issues on remote system."""
        bugs = []
        base_id = exercise.id.removesuffix('-ge').removesuffix('-lab')

        # Check for world-readable sensitive files
        sensitive_paths = [
            f'/home/student/{base_id}/vault-password',
            f'/home/student/{base_id}/.vault_pass',
            f'/home/student/{base_id}/credentials.yml',
            f'/home/student/{base_id}/secrets.yml',
        ]

        for path in sensitive_paths:
            result = ssh.run(f"test -f {path} && stat -c %a {path}", timeout=5)
            if result.success:
                perms = result.stdout.strip()
                if perms and int(perms[-1]) >= 4:  # World readable
                    bugs.append(Bug(
                        id=f"SEC-REMOTE-PERM-{exercise.id}",
                        severity=BugSeverity.P2_HIGH,
                        category="TC-SECURITY",
                        exercise_id=exercise.id,
                        description=f"Sensitive file is world-readable: {path} ({perms})",
                        fix_recommendation="Set restrictive permissions: chmod 600",
                        verification_steps=[
                            f"Run: chmod 600 {path}",
                            f"Verify: stat {path}"
                        ]
                    ))

        # Check for .env files with credentials
        result = ssh.run(f"find /home/student/{base_id} -name '.env' -o -name '*.env' 2>/dev/null", timeout=10)
        if result.success and result.stdout.strip():
            env_files = result.stdout.strip().split('\n')
            for env_file in env_files:
                if env_file.strip():
                    # Check if it contains passwords
                    check = ssh.run(f"grep -i 'password\\|secret\\|key\\|token' {env_file.strip()} 2>/dev/null | head -1", timeout=5)
                    if check.success and check.stdout.strip():
                        bugs.append(Bug(
                            id=f"SEC-ENVFILE-{exercise.id}",
                            severity=BugSeverity.P1_CRITICAL,
                            category="TC-SECURITY",
                            exercise_id=exercise.id,
                            description=f"Environment file with credentials: {env_file.strip()}",
                            fix_recommendation="Use Ansible vault or remove credentials",
                            verification_steps=[
                                f"Review: cat {env_file.strip()}",
                                "Encrypt with ansible-vault"
                            ]
                        ))

        return bugs
