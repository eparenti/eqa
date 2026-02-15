# EXAMPLE: Complete Custom Test Workflow

**This is a complete example** showing how to create custom tests from start to finish.

Follow this example when you need to create custom tests for your course.

---

## Scenario

**You want to test**: Does the "<exercise-name>" exercise give helpful error messages when students make common mistakes?

**Course**: <ANSIBLE-COURSE> - Developing Advanced Automation with Ansible
**Exercise**: <exercise-name> (Guided Exercise)
**Focus**: Error handling for common student mistakes

---

## Step 1: Plan Your Tests

**What mistakes do students commonly make?**

1. Forget colon after `tasks` in playbook
2. Use undefined variables
3. Make typos in module names
4. Forget to install required collections

**Decision**: Create test cases for items #1, #2, and #3.

---

## Step 2: Create Test Fixtures

### Fixture 1: Missing Colon

```bash
cat > ~/.claude/skills/qa/test-data/fixtures/playbooks/<ANSIBLE-COURSE>-missing-colon.yml <<'EOF'
---
# TEST FIXTURE: Missing colon after "tasks"
# Purpose: Test error message when student forgets colon
# Expected: Clear syntax error pointing to line 4

- name: Configure web server
  hosts: webservers
  tasks  # ERROR: Missing colon after "tasks"
    - name: Install httpd
      ansible.builtin.dnf:
        name: httpd
        state: present
EOF
```

### Fixture 2: Undefined Variable

```bash
cat > ~/.claude/skills/qa/test-data/fixtures/playbooks/<ANSIBLE-COURSE>-undefined-var.yml <<'EOF'
---
# TEST FIXTURE: Undefined variable
# Purpose: Test error message when variable is not defined
# Expected: Clear error identifying the undefined variable

- name: Install package
  hosts: all
  tasks:
    - name: Install web server
      ansible.builtin.dnf:
        name: "{{ web_package }}"  # ERROR: web_package not defined
        state: present
EOF
```

### Fixture 3: Wrong Module Name

```bash
cat > ~/.claude/skills/qa/test-data/fixtures/playbooks/<ANSIBLE-COURSE>-wrong-module.yml <<'EOF'
---
# TEST FIXTURE: Typo in module name
# Purpose: Test error message when module name is misspelled
# Expected: Clear error indicating module not found

- name: Install package
  hosts: all
  tasks:
    - name: Install web server
      ansibl.builtin.dnf:  # ERROR: Should be "ansible.builtin.dnf"
        name: httpd
        state: present
EOF
```

---

## Step 3: Create Custom Test Case File

```bash
cat > ~/.claude/skills/qa/test-cases/custom/<ANSIBLE-COURSE>-<exercise-name>-errors.md <<'EOF'
# Custom Test Cases: <ANSIBLE-COURSE> <exercise-name> Error Handling

**Course**: <ANSIBLE-COURSE> - Developing Advanced Automation with Ansible
**Exercise**: <exercise-name> (Guided Exercise)
**Purpose**: Verify students receive helpful error messages for common mistakes

---

## TC-ERROR-001: Missing Colon After Tasks

**Priority**: P2
**Category**: Error Handling

**Prerequisites**:
- Exercise started: `lab start <exercise-name>`
- Test fixture exists: `test-data/fixtures/playbooks/<ANSIBLE-COURSE>-missing-colon.yml`

**Test Steps**:

1. SSH to workstation:
   ```bash
   ssh workstation
   ```

2. Navigate to exercise directory:
   ```bash
   cd ~/<exercise-name>
   ```

3. Copy test fixture:
   ```bash
   cp ~/.claude/skills/qa/test-data/fixtures/playbooks/<ANSIBLE-COURSE>-missing-colon.yml ./
   ```

4. Run the playbook:
   ```bash
   ansible-navigator run <ANSIBLE-COURSE>-missing-colon.yml -m stdout
   ```

5. Observe error message

**Expected Result**:
✅ Command fails with syntax error
✅ Error message mentions YAML parsing or syntax
✅ Error points to line 4 (the `tasks` line)
✅ Message is clear enough for students to understand

**Pass/Fail Criteria**:
- ✅ PASS: Error message clearly identifies the syntax issue
- ❌ FAIL: Cryptic error or no indication of what's wrong

**Notes**:
- This is the #1 mistake students make in this exercise
- Good error messages reduce support tickets

---

## TC-ERROR-002: Undefined Variable

**Priority**: P2
**Category**: Error Handling

**Prerequisites**:
- Exercise started: `lab start <exercise-name>`
- Test fixture exists: `test-data/fixtures/playbooks/<ANSIBLE-COURSE>-undefined-var.yml`

**Test Steps**:

1. Run playbook with undefined variable:
   ```bash
   ssh workstation "cd ~/<exercise-name> && ansible-navigator run ~/.claude/skills/qa/test-data/fixtures/playbooks/<ANSIBLE-COURSE>-undefined-var.yml -m stdout"
   ```

2. Check error message quality

**Expected Result**:
✅ Error clearly states: "'web_package' is undefined"
✅ Shows which task triggered the error
✅ May suggest using |default filter or defining the variable

**Pass/Fail Criteria**:
- ✅ PASS: Error clearly identifies the undefined variable
- ❌ FAIL: Generic error or unclear message

**Notes**:
- Students often copy-paste without defining all variables
- Clear error saves debugging time

---

## TC-ERROR-003: Wrong Module Name

**Priority**: P2
**Category**: Error Handling

**Prerequisites**:
- Exercise started: `lab start <exercise-name>`
- Test fixture exists: `test-data/fixtures/playbooks/<ANSIBLE-COURSE>-wrong-module.yml`

**Test Steps**:

1. Run playbook with typo in module name:
   ```bash
   ssh workstation "cd ~/<exercise-name> && ansible-navigator run ~/.claude/skills/qa/test-data/fixtures/playbooks/<ANSIBLE-COURSE>-wrong-module.yml -m stdout"
   ```

2. Verify error message

**Expected Result**:
✅ Error indicates module not found: "ansibl.builtin.dnf"
✅ Clear message about the issue
✅ May suggest checking module name spelling

**Pass/Fail Criteria**:
- ✅ PASS: Error clearly indicates module not found
- ❌ FAIL: Unclear what went wrong

**Notes**:
- Typos in FQCN (Fully Qualified Collection Names) are common
- Good error messages prevent frustration

---

## Summary

**Total Tests**: 3
**Category**: Error Handling
**Priority**: P2 (High)

**Rationale**: These are the top 3 mistakes students make. Clear error messages directly reduce:
- Support ticket volume
- Student frustration
- Time spent debugging
EOF
```

---

## Step 4: Run Your Custom Tests

```bash
# Run custom tests alongside standard QA tests
cd ~/.claude/skills/qa/
/qa <lesson-code> <exercise-name> test-cases/custom/<ANSIBLE-COURSE>-<exercise-name>-errors.md
```

**What happens:**

1. QA skill runs standard tests (TC-PREREQ, TC-INSTRUCT, TC-EXEC, TC-SOL, TC-VERIFY, TC-CLEAN)
2. QA skill then runs your custom tests (TC-ERROR-001, TC-ERROR-002, TC-ERROR-003)
3. Generates comprehensive report

---

## Step 5: Review Results

**Example output:**

```
=== STANDARD TESTS ===
✅ TC-PREREQ-01: Environment ready
✅ TC-INSTRUCT-01: Instructions complete
✅ TC-EXEC-01: Exercise steps work
✅ TC-SOL-01: Solutions work
✅ TC-VERIFY-01: Verification passes
✅ TC-CLEAN-01: Cleanup works

=== CUSTOM TESTS (Error Handling) ===
✅ TC-ERROR-001: Missing colon error - PASS
   Error message: "Syntax Error while loading YAML...mapping values are not allowed here"
   ✅ Clear and points to line 4

✅ TC-ERROR-002: Undefined variable - PASS
   Error message: "The task includes an option with an undefined variable. 'web_package' is undefined"
   ✅ Very clear, identifies the variable

❌ TC-ERROR-003: Wrong module name - FAIL (P2)
   Error message: "couldn't resolve module/action 'ansibl.builtin.dnf'"
   ⚠️  Doesn't suggest checking spelling
   ⚠️  Could be more helpful

📊 Results: 8/9 (89%)
- P0: 0
- P1: 0
- P2: 1 (Error message could be clearer)

Status: ✅ READY (Consider improving error messages)
```

---

## Step 6: Document Issues Found

If tests fail, document in `results/known-issues/`:

```bash
cat > ~/.claude/skills/qa/results/known-issues/<ANSIBLE-COURSE>-P2-001.md <<'EOF'
# BUG-<ANSIBLE-COURSE>-001 (P2): Module Name Error Could Be More Helpful

**Discovered**: 2026-01-06
**Exercise**: <ANSIBLE-COURSE> - <exercise-name>
**Test Case**: TC-ERROR-003
**Severity**: P2 (High - Quality Issue)
**Status**: Open

## Problem

When student makes typo in module name (e.g., "ansibl.builtin.dnf" instead of "ansible.builtin.dnf"), error message is:

```
couldn't resolve module/action 'ansibl.builtin.dnf'
```

This is technically correct but not very helpful for students.

## Impact

- Students have to spend time debugging
- Not immediately obvious it's a typo
- May think collection is missing

## Suggested Improvement

Better error message would be:

```
Module 'ansibl.builtin.dnf' not found.
Did you mean 'ansible.builtin.dnf'?
Check module name spelling and collection installation.
```

## Workaround

Instructors should emphasize checking spelling of FQCN during class.

## Resolution Steps

- [ ] Request feature in Ansible upstream
- [ ] Add note to exercise instructions about common typos
- [ ] Move to RESOLVED/ when addressed
EOF
```

---

## Complete Workflow Summary

1. ✅ **Plan**: Identify what to test (common mistakes)
2. ✅ **Create fixtures**: Invalid playbooks for testing
3. ✅ **Write test cases**: Document expected behavior
4. ✅ **Run tests**: Execute via QA skill
5. ✅ **Review results**: Analyze pass/fail
6. ✅ **Document issues**: Track bugs found

---

## Tips

**When creating custom tests:**

✅ **DO:**
- Focus on real student issues
- Make fixtures minimal
- Document why each test matters
- Use clear pass/fail criteria

❌ **DON'T:**
- Test every possible error
- Make fixtures overly complex
- Create tests without clear purpose
- Forget to document expected results

---

## Scaling This Approach

**For one exercise**: 3-5 custom tests is reasonable

**For whole course**:
- Create one file per exercise with custom needs
- Example:
  ```
  test-cases/custom/
  ├── <ANSIBLE-COURSE>-<exercise-name>-errors.md  (3 tests)
  ├── <ANSIBLE-COURSE>-<exercise-name>-edge-cases.md    (4 tests)
  └── <ANSIBLE-COURSE>-<exercise-name>-performance.md   (2 tests)
  ```

**For course releases**:
- Run all custom tests before major releases
- Update tests when course content changes
- Archive obsolete tests

---

This example shows the complete workflow. Use it as a template for your own custom testing!
