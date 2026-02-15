# Sample: Error Handling Test Cases

**Purpose**: Example test cases for testing how exercises handle common student mistakes.

**Use this as a template** when creating custom error handling tests.

---

## Sample 1: Invalid YAML Syntax

### TC-ERROR-001: Missing Colon in Tasks Section

**Priority**: P2
**Category**: Error Handling

**Prerequisites**:
- Exercise started: `lab start <exercise-name>`
- Test fixture created: `test-data/fixtures/playbooks/invalid-tasks-syntax.yml`

**Test Steps**:
1. Navigate to exercise directory:
   ```bash
   ssh workstation "cd ~/<exercise-name>"
   ```

2. Copy invalid playbook:
   ```bash
   ssh workstation "cp ~/.claude/skills/qa/test-data/fixtures/playbooks/invalid-tasks-syntax.yml ~/<exercise-name>/"
   ```

3. Run the playbook:
   ```bash
   ssh workstation "cd ~/<exercise-name> && ansible-navigator run invalid-tasks-syntax.yml -m stdout"
   ```

4. Observe error message

**Expected Result**:
✅ Command fails with syntax error
✅ Error message mentions "tasks" section
✅ Error points to line number with issue
✅ Error message is clear and actionable

**Pass/Fail Criteria**:
- ✅ PASS: Error message is helpful and points to the issue
- ❌ FAIL: Cryptic error or no clear guidance

**Potential Issues**:
- Vague error messages
- No line number provided
- Error doesn't indicate what's wrong

---

## Sample 2: Undefined Variable

### TC-ERROR-002: Using Undefined Variable in Playbook

**Priority**: P2
**Category**: Error Handling

**Prerequisites**:
- Exercise started
- Test fixture: `test-data/fixtures/playbooks/undefined-var.yml`

**Test Steps**:
1. Run playbook with undefined variable:
   ```bash
   ssh workstation "ansible-navigator run test-data/fixtures/playbooks/undefined-var.yml -m stdout"
   ```

2. Check error message quality

**Expected Result**:
✅ Clear error: "'my_undefined_var' is undefined"
✅ Shows which task triggered the error
✅ Suggests defining the variable or using |default filter

**Pass/Fail Criteria**:
- ✅ PASS: Error clearly identifies undefined variable
- ❌ FAIL: Cryptic message or hard to understand

---

## Sample 3: Wrong Module Name

### TC-ERROR-003: Typo in Module Name

**Priority**: P2
**Category**: Error Handling

**Prerequisites**:
- Exercise started
- Test fixture: `test-data/fixtures/playbooks/wrong-module.yml`

**Test Steps**:
1. Run playbook with typo in module name:
   ```bash
   ssh workstation "ansible-navigator run test-data/fixtures/playbooks/wrong-module.yml -m stdout"
   ```

2. Verify error message

**Expected Result**:
✅ Error: "module 'ansibl.builtin.dnf' not found" (or similar)
✅ Suggests checking module name
✅ May suggest correct module name

**Pass/Fail Criteria**:
- ✅ PASS: Error clearly indicates module not found
- ❌ FAIL: Unclear what went wrong

---

## Sample 4: Missing File

### TC-ERROR-004: Template File Not Found

**Priority**: P2
**Category**: Error Handling

**Prerequisites**:
- Exercise started
- Playbook references non-existent template

**Test Steps**:
1. Run playbook that references missing file:
   ```bash
   ssh workstation "cd ~/exercise && ansible-navigator run site.yml -m stdout"
   ```

2. Check error handling

**Expected Result**:
✅ Error: "Could not find or access 'templates/my-file.j2'"
✅ Shows file path it tried
✅ Suggests checking path and file existence

**Pass/Fail Criteria**:
- ✅ PASS: Clear file-not-found error with path
- ❌ FAIL: Generic error or missing file path

---

## How to Use These Samples

1. **Copy this file** to create your own error handling tests:
   ```bash
   cp test-cases/custom/SAMPLE-error-handling-tests.md \
      test-cases/custom/<ANSIBLE-COURSE>-error-handling.md
   ```

2. **Modify for your course**:
   - Update exercise names
   - Adjust file paths
   - Add course-specific errors

3. **Create the test fixtures** referenced:
   ```bash
   # Create invalid YAML fixture
   cat > test-data/fixtures/playbooks/invalid-tasks-syntax.yml <<'EOF'
   ---
   - name: Test playbook
     hosts: all
     tasks  # Missing colon here
       - name: Install httpd
         ansible.builtin.dnf:
           name: httpd
   EOF
   ```

4. **Run your tests**:
   ```bash
   /qa au294 <exercise-name> test-cases/custom/<ANSIBLE-COURSE>-error-handling.md
   ```

---

## Tips for Error Handling Tests

✅ **DO:**
- Test common student mistakes
- Verify error messages are helpful
- Check that errors point to the issue
- Ensure errors suggest solutions

❌ **DON'T:**
- Test every possible error (focus on common ones)
- Expect perfect error messages (reasonable clarity is enough)
- Create overly complex error scenarios
