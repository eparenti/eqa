# Error Summary Pattern

## Overview

The Error Summary Pattern is a UX improvement for automated testing. Instead of failing on the first error, test categories collect ALL bugs/issues and display them together at the end.

## Benefits

1. **Better UX**: Students see all problems at once, not just the first one
2. **More informative**: Complete picture of what needs to be fixed
3. **Saves time**: Fix multiple issues in one iteration instead of discovering them one-by-one
4. **Professional**: Matches industry-standard grading behavior

## How It Works

### Ansible Grading Pattern

```yaml
tasks:
  - name: Set error_summary fact
    ansible.builtin.set_fact:
      error_summary: []

  - name: Check something
    block:
      - name: Do validation
        ansible.builtin.assert:
          that: condition
          fail_msg: "Problem description"
        register: result
    rescue:
      - name: Update error_summary
        vars:
          the_error:
            - "{{ result['msg'] }}"
        ansible.builtin.set_fact:
          error_summary: "{{ error_summary + the_error }}"

  - name: Display all errors at end
    ansible.builtin.assert:
      that: error_summary | length == 0
      fail_msg: "{{ error_summary | flatten }}"
```

### Our Pattern (Python)

```python
from lib.test_result import Bug, BugSeverity

class TC_EXAMPLE:
    def test(self, exercise, ssh):
        bugs_found = []  # Collect all bugs

        # Test 1
        if not check_1():
            bugs_found.append(Bug(
                id="BUG-EXAMPLE-CHECK1",
                severity=BugSeverity.P1_CRITICAL,
                exercise_id=exercise.id,
                category="TC-EXAMPLE",
                description="Check 1 failed",
                fix_recommendation="Fix check 1...",
                verification_steps=["1. Fix", "2. Verify"]
            ))

        # Test 2 - CONTINUE TESTING even if test 1 failed
        if not check_2():
            bugs_found.append(Bug(
                id="BUG-EXAMPLE-CHECK2",
                severity=BugSeverity.P2_HIGH,
                exercise_id=exercise.id,
                category="TC-EXAMPLE",
                description="Check 2 failed",
                fix_recommendation="Fix check 2...",
                verification_steps=["1. Fix", "2. Verify"]
            ))

        # Test 3 - Keep collecting bugs
        if not check_3():
            bugs_found.append(Bug(
                id="BUG-EXAMPLE-CHECK3",
                severity=BugSeverity.P3_MEDIUM,
                exercise_id=exercise.id,
                category="TC-EXAMPLE",
                description="Check 3 failed",
                fix_recommendation="Fix check 3...",
                verification_steps=["1. Fix", "2. Verify"]
            ))

        # Return result with ALL bugs
        passed = len(bugs_found) == 0

        return TestResult(
            category="TC-EXAMPLE",
            exercise_id=exercise.id,
            passed=passed,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,  # ALL bugs collected
            details=test_details,
            summary=f"Found {len(bugs_found)} issues"
        )
```

## Exception: Blocker Bugs

For **P0_BLOCKER** bugs that prevent further testing, you MAY stop early:

```python
bugs_found = []

# Critical prerequisite check
if not ssh.test_connection():
    bugs_found.append(Bug(
        id="BUG-SSH-FAILED",
        severity=BugSeverity.P0_BLOCKER,  # Blocker!
        exercise_id=exercise.id,
        category="TC-PREREQ",
        description="Cannot connect via SSH",
        fix_recommendation="Fix SSH connection...",
        verification_steps=["1. Test SSH"]
    ))

    # Return early - can't continue without SSH
    return TestResult(
        category="TC-PREREQ",
        exercise_id=exercise.id,
        passed=False,
        timestamp=start_time.isoformat(),
        duration_seconds=duration,
        bugs_found=bugs_found,
        details={'blocked': True},
        summary="Blocked by SSH failure"
    )

# Continue with other tests...
```

## Implementation Status

### ✅ Implemented

All test categories use the error summary pattern:

- **TC-PREREQ**: Collects all prerequisite issues before returning
- **TC-VERIFY**: Collects all verification failures
- **TC-GRADE**: Collects all grading issues
- **TC-CLEAN**: Collects all cleanup issues
- **TC-SOLVE**: Collects all solve playbook issues
- **TC-AAP**: Collects all AAP Controller issues
- **TC-SOL**: Collects all solution file issues
- **TC-IDEM**: Collects all idempotency issues
- **TC-E2E**: Collects all end-to-end issues

### Example from TC-AAP

```python
def test(self, exercise, ssh):
    bugs_found = []

    # Test credentials
    success, message = grade_credentials(...)
    if not success:
        bugs_found.append(Bug(...))  # Add but continue

    # Test projects - STILL RUN even if credentials failed
    success, message = grade_projects(...)
    if not success:
        bugs_found.append(Bug(...))  # Add but continue

    # Test job templates - STILL RUN even if projects failed
    success, message = grade_job_templates(...)
    if not success:
        bugs_found.append(Bug(...))  # Collect all issues

    # Return all bugs at once
    return TestResult(
        ...
        bugs_found=bugs_found,
        passed=(len(bugs_found) == 0)
    )
```

## Benefits Demonstrated

### Before (Fail-Fast)
```
❌ TC-AAP: AAP Controller Testing

   Testing credentials...
      ✗ Credential 'Git-Cred' not found

FAILED: Cannot continue testing
```

Student fixes credential, re-runs test...

```
❌ TC-AAP: AAP Controller Testing

   Testing credentials...
      ✓ All credentials OK
   Testing projects...
      ✗ Project 'My-Project' has wrong SCM URL

FAILED: Cannot continue testing
```

Student fixes project, re-runs test...

```
❌ TC-AAP: AAP Controller Testing

   Testing credentials...
      ✓ All credentials OK
   Testing projects...
      ✓ All projects OK
   Testing job templates...
      ✗ Job template 'Deploy-App' missing

FAILED
```

**Result: 3 test runs needed to discover 3 issues**

### After (Error Summary)
```
❌ TC-AAP: AAP Controller Testing

   Testing credentials...
      ✗ Credential 'Git-Cred' not found
   Testing projects...
      ✗ Project 'My-Project' has wrong SCM URL
   Testing job templates...
      ✗ Job template 'Deploy-App' missing

FAILED: 3 issues found

Issues:
  1. BUG-AAP-CREDENTIALS: Credential 'Git-Cred' not found
  2. BUG-AAP-PROJECTS: Project 'My-Project' has wrong SCM URL
  3. BUG-AAP-JOB-TEMPLATES: Job template 'Deploy-App' missing
```

**Result: 1 test run discovers all 3 issues**

## Guidelines for Test Category Authors

1. **Always use `bugs_found` list**: Never raise exceptions for test failures
2. **Continue testing**: Don't return early unless P0 blocker
3. **Collect all bugs**: Test as much as possible before returning
4. **Clear bug descriptions**: Each bug should have actionable fix recommendations
5. **Return comprehensive results**: Include all bugs in TestResult

## Code Review Checklist

When reviewing test category code, verify:

- [ ] Uses `bugs_found = []` list
- [ ] Continues testing after failures (except P0 blockers)
- [ ] Returns `TestResult` with all bugs collected
- [ ] Each bug has clear description and fix recommendation
- [ ] No premature returns (except for P0 blockers)
- [ ] Test result includes comprehensive details

## Further Reading

- `lib/test_result.py` - Bug and TestResult data structures
- Ansible grading scripts - Reference implementation in Ansible
