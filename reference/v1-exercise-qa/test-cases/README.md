# Custom Test Cases

**You should add custom test cases here** to test edge cases and specific scenarios not covered by default testing.

---

## When to Add Custom Test Cases

Add custom test cases when you need to:

✅ **Test edge cases** - Unusual inputs, boundary conditions
✅ **Test error handling** - How exercises handle common student mistakes
✅ **Test specific requirements** - Course-specific validation
✅ **Test prerequisites** - Environment setup, package versions
✅ **Test cleanup** - Ensure lab reset works correctly
✅ **Test performance** - Playbook execution time, resource usage
✅ **Test security** - Permissions, credentials, sensitive data

---

## 📁 Directory Structure

### custom/

**Your custom test cases go here.**

Create one file per exercise or group of related tests:

```
custom/
├── <RHEL-COURSE>-ch1-servicemgmt-edge-cases.md
├── <ANSIBLE-COURSE>-install-prerequisites.md
└── <ANSIBLE-COURSE>-roles-custom-validation.md
```

### templates/

**Template to copy when creating new test cases.**

```bash
cp templates/test-case-template.md custom/MY-TEST-CASES.md
```

---

## Creating Custom Test Cases

### Step 1: Copy Template

```bash
cd ~/.claude/skills/qa/test-cases/
cp templates/test-case-template.md custom/COURSE-exercise-custom.md
```

### Step 2: Define Test Cases

Use the standard test case format:

```markdown
### TC-CUSTOM-001: Test Edge Case Name

**Priority**: P0/P1/P2/P3
**Category**: Custom

**Prerequisites**:
- List what must be true before this test
- Reference standard test cases if needed (TC-EXEC-001)

**Test Steps**:
1. Specific action to take
2. Expected behavior
3. Verification step

**Expected Result**:
✅ First thing that should be true
✅ Second thing that should be true

**Pass/Fail Criteria**:
- ✅ PASS: All expected results met
- ❌ FAIL: Any expected result not met
```

### Step 3: Run Your Tests

Tell the QA skill about your custom tests:

```bash
/qa au0025l <exercise-name> test-cases/custom/MY-TEST-CASES.md
```

---

## Example: Testing Edge Cases

**File:** `custom/<ANSIBLE-COURSE>-<exercise-name>-edge-cases.md`

```markdown
# Custom Test Cases: <ANSIBLE-COURSE> Roles Create

## Edge Cases

### TC-CUSTOM-001: Role Creation with Special Characters

**Priority**: P2
**Category**: Custom - Edge Cases

**Prerequisites**:
- TC-PREREQ-001 passed (Environment ready)
- Lab started: `lab start <exercise-name>`

**Test Steps**:
1. Try to create role with name containing spaces:
   `ansible-galaxy role init roles/"my role"`
2. Try to create role with special characters:
   `ansible-galaxy role init roles/my-role@v1`
3. Verify error handling

**Expected Result**:
✅ Spaces in role name: Rejected with clear error
✅ Special chars: Rejected or sanitized appropriately
✅ Error messages guide student to correct format

**Pass/Fail Criteria**:
- ✅ PASS: All invalid names rejected with helpful errors
- ❌ FAIL: Invalid names accepted or cryptic errors

### TC-CUSTOM-002: Role Creation with Insufficient Permissions

**Priority**: P2
**Category**: Custom - Error Handling

**Prerequisites**:
- TC-PREREQ-001 passed

**Test Steps**:
1. Remove write permissions: `chmod 555 roles/`
2. Try to create role: `ansible-galaxy role init roles/test`
3. Check error message quality

**Expected Result**:
✅ Command fails appropriately
✅ Error message mentions permission issue
✅ Suggests how to fix (check permissions)

**Pass/Fail Criteria**:
- ✅ PASS: Clear error about permissions
- ❌ FAIL: Cryptic error or no error
```

---

## Example: Testing Student Mistakes

**File:** `custom/<RHEL-COURSE>-common-mistakes.md`

```markdown
# Common Student Mistakes - <RHEL-COURSE>

### TC-MISTAKE-001: Forgot to Enable Service

**Priority**: P1
**Category**: Common Mistakes

**Prerequisites**:
- TC-EXEC-001 passed (Exercise steps work)

**Test Steps**:
1. Complete exercise but skip `enabled: true` in service task
2. Reboot the server
3. Check if service starts automatically

**Expected Result**:
❌ Service does NOT start on boot (as expected)
✅ Student discovers issue during verification
✅ Exercise includes verification step to catch this

**Pass/Fail Criteria**:
- ✅ PASS: Verification step catches missing enabled
- ❌ FAIL: Student can complete without enabling service
```

---

## Test Case Categories

Use these categories for custom tests:

| Category | Use For |
|----------|---------|
| **Custom** | General custom tests |
| **Edge Cases** | Boundary conditions, unusual inputs |
| **Error Handling** | Common mistakes, invalid inputs |
| **Prerequisites** | Environment setup, package versions |
| **Performance** | Speed, resource usage |
| **Security** | Permissions, credentials |
| **Cleanup** | Lab reset, environment cleanup |
| **Integration** | Multi-exercise workflows |

---

## Test Naming Convention

Use `TC-CUSTOM-XXX` for custom test cases:

- `TC-CUSTOM-001` through `TC-CUSTOM-999`
- Keeps them separate from standard test cases
- Easy to identify as custom tests

Or use specific prefixes:

- `TC-EDGE-XXX` - Edge cases
- `TC-MISTAKE-XXX` - Common mistakes
- `TC-PERF-XXX` - Performance tests
- `TC-SEC-XXX` - Security tests

---

## Running Custom Tests

### Option 1: Include with Standard Testing

```bash
# QA skill will find and use custom tests automatically
/qa au294 <exercise-name> test-cases/custom/<ANSIBLE-COURSE>-<exercise-name>-edge-cases.md
```

### Option 2: Run Custom Tests Only

```bash
# Skip standard tests, run only custom
/qa --custom-only au294 <exercise-name> test-cases/custom/<ANSIBLE-COURSE>-<exercise-name>-edge-cases.md
```

### Option 3: Add to Course Mapping

Edit `config/courses/<ANSIBLE-COURSE>-mapping.json`:

```json
{
  "exercises": [
    {
      "id": "<exercise-name>",
      "type": "ge",
      "custom_tests": "test-cases/custom/<ANSIBLE-COURSE>-<exercise-name>-edge-cases.md"
    }
  ]
}
```

---

## Tips

✅ **DO:**
- Test things students actually get wrong
- Include clear expected results
- Document why each test is important
- Keep tests focused (one concept per test)
- Update tests when course content changes

❌ **DON'T:**
- Duplicate standard test cases
- Test things already covered
- Make tests too complex
- Forget to document prerequisites
- Leave unclear pass/fail criteria

---

## Best Practices

### 1. Focus on Real Issues

Base custom tests on:
- Student support tickets
- Common forum questions
- Instructor feedback
- Known problem areas

### 2. Make Tests Actionable

Each failed test should:
- Clearly indicate what's wrong
- Suggest how to fix it
- Point to relevant documentation

### 3. Maintain Test Cases

- Review after each course update
- Archive obsolete tests
- Update when exercises change
- Document test history

---

**Need Help?**
- See `templates/test-case-template.md` for template
- See `.skilldata/guides/01-testing-guided-exercises-vs-labs.md` for standard test categories
- See `results/known-issues/` for documented bugs that need tests
