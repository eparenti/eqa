#!/usr/bin/env python3
"""
TC-SECURITY: Security Best Practices Validation

Tests exercises for security anti-patterns and provides improvement suggestions.
Reports findings as P2/P3 severity (improvement suggestions, not critical bugs).

Security checks:
- Hardcoded credentials in solutions
- Insecure file permissions
- Passwordless sudo configurations
- Secrets in version control
- Unencrypted sensitive data
"""

import sys
import re
from pathlib import Path
from typing import List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.test_result import TestResult, Bug, BugSeverity, ExerciseContext
from lib.ssh_connection import SSHConnection


class TC_SECURITY:
    """
    Security best practices validation test category.

    Reports findings as improvement suggestions (P2/P3), not critical bugs.
    """

    def __init__(self):
        """Initialize security tester."""
        pass

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test exercise for security best practices.

        All findings are reported as P2/P3 (improvement suggestions).

        Args:
            exercise: Exercise context
            ssh: SSH connection to workstation

        Returns:
            TestResult with security improvement suggestions
        """
        print(f"\n🔒 TC-SECURITY: Security Best Practices")
        print("=" * 60)
        print("  Note: Findings are improvement suggestions, not critical bugs")

        bugs_found = []

        # Check 1: Hardcoded credentials
        print("\n  1. Checking for hardcoded credentials...")
        hardcoded_creds = self._check_hardcoded_credentials(exercise, ssh)
        bugs_found.extend(hardcoded_creds)
        if hardcoded_creds:
            print(f"     ⚠️  Found {len(hardcoded_creds)} hardcoded credential(s)")
        else:
            print("     ✅ No hardcoded credentials found")

        # Check 2: Insecure file permissions
        print("\n  2. Checking file permissions...")
        insecure_perms = self._check_insecure_permissions(exercise, ssh)
        bugs_found.extend(insecure_perms)
        if insecure_perms:
            print(f"     ⚠️  Found {len(insecure_perms)} file(s) with insecure permissions")
        else:
            print("     ✅ File permissions look good")

        # Check 3: Passwordless sudo
        print("\n  3. Checking for passwordless sudo...")
        sudo_issues = self._check_passwordless_sudo(exercise, ssh)
        bugs_found.extend(sudo_issues)
        if sudo_issues:
            print(f"     ⚠️  Found passwordless sudo configuration")
        else:
            print("     ✅ No passwordless sudo found")

        # Check 4: Secrets in files
        print("\n  4. Checking for secrets in solution files...")
        secrets = self._check_secrets_in_files(exercise, ssh)
        bugs_found.extend(secrets)
        if secrets:
            print(f"     ⚠️  Found {len(secrets)} potential secret(s)")
        else:
            print("     ✅ No obvious secrets found")

        # Summary
        print(f"\n{'=' * 60}")
        if bugs_found:
            print(f"Security Suggestions: {len(bugs_found)} improvement(s) recommended")
        else:
            print("Security: ✅ No security improvements needed")
        print(f"{'=' * 60}")

        return TestResult(
            category="TC-SECURITY",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp="",
            duration_seconds=0,
            bugs_found=bugs_found,
            details={
                'checks_performed': 4,
                'suggestions_count': len(bugs_found)
            },
            summary=f"Security: {len(bugs_found)} improvement suggestions"
        )

    def _check_hardcoded_credentials(
        self, exercise: ExerciseContext, ssh: SSHConnection
    ) -> List[Bug]:
        """
        Check for hardcoded credentials in solution files.

        Returns P2 suggestions (not critical bugs).
        """
        bugs = []

        # Find solution files
        find_result = ssh.run(
            f"find ~/*/solutions/{exercise.id}/ -name '*.sol' 2>/dev/null || true",
            timeout=30
        )

        if find_result.return_code != 0 or not find_result.stdout.strip():
            return bugs

        solution_files = find_result.stdout.strip().split('\n')

        # Patterns that suggest hardcoded credentials
        credential_patterns = [
            (r'password:\s*[\'"]([^\'"\s]{3,})[\'"]', 'hardcoded password'),
            (r'passwd:\s*[\'"]([^\'"\s]{3,})[\'"]', 'hardcoded password'),
            (r'api[_-]?key:\s*[\'"]([A-Za-z0-9_-]{20,})[\'"]', 'hardcoded API key'),
            (r'token:\s*[\'"]([A-Za-z0-9_-]{20,})[\'"]', 'hardcoded token'),
            (r'secret:\s*[\'"]([^\'"\s]{10,})[\'"]', 'hardcoded secret'),
        ]

        for sol_file in solution_files:
            # Read file content
            cat_result = ssh.run(f"cat {sol_file}", timeout=30)
            if cat_result.return_code != 0:
                continue

            content = cat_result.stdout

            # Check patterns
            for pattern, cred_type in credential_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    bugs.append(Bug(
                        id=f"SEC-HARDCODED-{exercise.id}-{Path(sol_file).name}",
                        severity=BugSeverity.P2_HIGH,  # Improvement suggestion
                        exercise_id=exercise.id,
                        category="TC-SECURITY",
                        description=f"Security Improvement: {cred_type} appears to be hardcoded in {Path(sol_file).name}",
                        fix_recommendation=f"""
Consider using Ansible Vault or environment variables for credentials:

**Option 1: Ansible Vault**
```bash
# Encrypt the variable
ansible-vault encrypt_string '{matches[0]}' --name 'the_password'

# Use in playbook:
vars:
  password: !vault |
    $ANSIBLE_VAULT;1.1;AES256
    ...
```

**Option 2: Environment Variables**
```yaml
# In playbook:
vars:
  password: "{{{{ lookup('env', 'DB_PASSWORD') }}}}"
```

**Best Practice**: Never commit real credentials to version control.
""",
                        verification_steps=[
                            f"Review {sol_file} for hardcoded credentials",
                            "Use Ansible Vault or environment variables for sensitive data",
                            "Verify no real credentials in git history"
                        ]
                    ))

        return bugs

    def _check_insecure_permissions(
        self, exercise: ExerciseContext, ssh: SSHConnection
    ) -> List[Bug]:
        """
        Check for insecure file permissions (777, world-writable).

        Returns P2 suggestions.
        """
        bugs = []

        # Find solution files
        find_result = ssh.run(
            f"find ~/*/solutions/{exercise.id}/ -name '*.sol' 2>/dev/null || true",
            timeout=30
        )

        if find_result.return_code != 0 or not find_result.stdout.strip():
            return bugs

        solution_files = find_result.stdout.strip().split('\n')

        # Check for permission-related patterns
        for sol_file in solution_files:
            cat_result = ssh.run(f"cat {sol_file}", timeout=30)
            if cat_result.return_code != 0:
                continue

            content = cat_result.stdout

            # Look for mode: 0777 or similar insecure permissions
            insecure_patterns = [
                (r'mode:\s*[\'"]?0?777[\'"]?', '777 (world-writable)'),
                (r'mode:\s*[\'"]?0?666[\'"]?', '666 (world-writable)'),
                (r'chmod\s+777', 'chmod 777'),
                (r'chmod\s+666', 'chmod 666'),
            ]

            for pattern, perm_type in insecure_patterns:
                if re.search(pattern, content):
                    bugs.append(Bug(
                        id=f"SEC-PERMS-{exercise.id}-{Path(sol_file).name}",
                        severity=BugSeverity.P3_LOW,  # Low priority suggestion
                        exercise_id=exercise.id,
                        category="TC-SECURITY",
                        description=f"Security Improvement: File permissions {perm_type} found in {Path(sol_file).name}",
                        fix_recommendation=f"""
Use least-privilege file permissions:

**Instead of:**
```yaml
mode: '0777'  # Too permissive
```

**Use:**
```yaml
mode: '0644'  # Owner: rw, Group: r, Others: r (for files)
mode: '0755'  # Owner: rwx, Group: rx, Others: rx (for directories/scripts)
mode: '0600'  # Owner: rw, Group: none, Others: none (for sensitive files)
```

**Best Practice**: Only grant necessary permissions.
""",
                        verification_steps=[
                            f"Review {sol_file} for permission settings",
                            "Use restrictive permissions (644/755/600 instead of 777/666)",
                            "Test that solution still works with secure permissions"
                        ]
                    ))

        return bugs

    def _check_passwordless_sudo(
        self, exercise: ExerciseContext, ssh: SSHConnection
    ) -> List[Bug]:
        """
        Check for passwordless sudo configurations.

        Returns P3 suggestions.
        """
        bugs = []

        # Find solution files
        find_result = ssh.run(
            f"find ~/*/solutions/{exercise.id}/ -name '*.sol' 2>/dev/null || true",
            timeout=30
        )

        if find_result.return_code != 0 or not find_result.stdout.strip():
            return bugs

        solution_files = find_result.stdout.strip().split('\n')

        for sol_file in solution_files:
            cat_result = ssh.run(f"cat {sol_file}", timeout=30)
            if cat_result.return_code != 0:
                continue

            content = cat_result.stdout

            # Look for NOPASSWD in sudoers configuration
            if re.search(r'NOPASSWD:\s*ALL', content, re.IGNORECASE):
                bugs.append(Bug(
                    id=f"SEC-SUDO-{exercise.id}",
                    severity=BugSeverity.P3_LOW,  # Low priority suggestion
                    exercise_id=exercise.id,
                    category="TC-SECURITY",
                    description=f"Security Improvement: Passwordless sudo (NOPASSWD) found in {Path(sol_file).name}",
                    fix_recommendation="""
For production environments, avoid passwordless sudo:

**Teaching Exception**: If this is intentional for lab convenience, add a comment:
```yaml
# NOTE: NOPASSWD is for lab convenience only
# In production, require password for sudo
lineinfile:
  path: /etc/sudoers.d/student
  line: "student ALL=(ALL) NOPASSWD: ALL"  # Lab only - not for production
```

**Production Recommendation**:
```yaml
# Require password for sudo (production standard)
lineinfile:
  path: /etc/sudoers.d/student
  line: "student ALL=(ALL) ALL"
```

**Best Practice**: Document when lab shortcuts differ from production practices.
""",
                    verification_steps=[
                        "Determine if passwordless sudo is intentional for lab",
                        "Add comment explaining lab vs production difference",
                        "Consider mentioning security implications in EPUB"
                    ]
                ))

        return bugs

    def _check_secrets_in_files(
        self, exercise: ExerciseContext, ssh: SSHConnection
    ) -> List[Bug]:
        """
        Check for potential secrets/keys in solution files.

        Returns P2 suggestions.
        """
        bugs = []

        # Find solution files
        find_result = ssh.run(
            f"find ~/*/solutions/{exercise.id}/ -name '*.sol' 2>/dev/null || true",
            timeout=30
        )

        if find_result.return_code != 0 or not find_result.stdout.strip():
            return bugs

        solution_files = find_result.stdout.strip().split('\n')

        # Patterns that might indicate secrets
        secret_patterns = [
            (r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----', 'private key'),
            (r'aws_secret_access_key\s*=\s*[\'"]\S+[\'"]', 'AWS secret key'),
            (r'[A-Za-z0-9]{40}', 'possible API token (40 chars)'),
        ]

        for sol_file in solution_files:
            # Skip obvious key files (might be intentional for teaching)
            if 'key' in Path(sol_file).name.lower() or 'cert' in Path(sol_file).name.lower():
                continue

            cat_result = ssh.run(f"cat {sol_file}", timeout=30)
            if cat_result.return_code != 0:
                continue

            content = cat_result.stdout

            for pattern, secret_type in secret_patterns:
                if re.search(pattern, content):
                    bugs.append(Bug(
                        id=f"SEC-SECRET-{exercise.id}-{Path(sol_file).name}",
                        severity=BugSeverity.P2_HIGH,  # Improvement suggestion
                        exercise_id=exercise.id,
                        category="TC-SECURITY",
                        description=f"Security Improvement: Possible {secret_type} found in {Path(sol_file).name}",
                        fix_recommendation=f"""
If this is a real secret/key, remove it:

**For Lab/Demo Keys**:
```yaml
# Add comment to clarify this is demo-only
# NOTE: This is a DEMO key for lab purposes only
# NEVER use in production - generate unique keys
```

**For Real Secrets**:
1. Remove from file
2. Use Ansible Vault: `ansible-vault encrypt_string '<secret>' --name 'the_secret'`
3. Check git history: `git log --all --full-history -- {sol_file}`
4. If committed, consider rotating the secret

**Best Practice**: Demo/test credentials should be clearly marked as such.
""",
                        verification_steps=[
                            "Verify if this is a demo/lab secret or real credential",
                            "Add comment clarifying lab vs production usage",
                            "Ensure no real secrets in version control"
                        ]
                    ))

        return bugs


def main():
    """Test TC-SECURITY."""
    from lib.test_result import ExerciseType

    print("TC-SECURITY: Security Best Practices Validation Demo")
    print("=" * 80)

    # Create test exercise
    exercise = ExerciseContext(
        id="example-exercise",
        type=ExerciseType.GUIDED_EXERCISE,
        lesson_code="test",
        chapter=1,
        chapter_title="Test",
        title="Example Exercise"
    )

    # Create SSH connection
    ssh = SSHConnection("localhost", username="student")

    # Run security checks
    tester = TC_SECURITY()
    result = tester.test(exercise, ssh)

    print("\n" + "=" * 80)
    print(f"Result: {'PASS' if result.passed else 'SUGGESTIONS'}")
    print(f"Security Suggestions: {len(result.bugs_found)}")
    print("=" * 80)

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
