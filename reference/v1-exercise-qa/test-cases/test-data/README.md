# Test Data

**Optional directory** for test fixtures and sample data used in testing.

⚠️ **Most course testing does NOT need this directory!**

---

## What Are Test Fixtures?

**Test fixtures** are pre-made test files you create specifically for testing edge cases or error handling.

Think of them as "test props" - fake or simplified versions of real data used to test specific scenarios.

### Examples:

**Invalid inventory file** (to test error handling):
```yaml
# fixtures/inventories/invalid-syntax.yml
[webservers
server1.example.com  # Missing closing bracket - syntax error
```

**Edge case playbook** (to test unusual inputs):
```yaml
# fixtures/playbooks/special-chars.yml
- name: Test special characters
  vars:
    app_name: "My App (Production) [v2.0]"
```

**Expected output file** (to compare actual vs expected):
```json
// fixtures/expected-outputs/service-check.json
{"httpd": {"status": "active", "enabled": true}}
```

---

## Do You Need Test Fixtures?

### For Regular Course Testing: NO

**You DON'T need test fixtures because:**

✅ Exercise materials already exist in the lesson repository
✅ You're testing real course content with real student files
✅ Each exercise has its own inventory, configs, solutions
✅ The QA skill uses actual exercise materials automatically

**Just run the QA skill:**
```bash
/qa au0025l <exercise-name>
```

The skill automatically finds and uses the exercise's actual files.

---

### For Advanced Testing: MAYBE

**Only create test fixtures when testing:**

1. **Error Handling** - "What if a student makes this mistake?"
   - Create invalid files to test error messages

2. **Edge Cases** - "Does it work with unusual inputs?"
   - Create edge case inventories (100 hosts, special characters, IPv6)

3. **Regression Testing** - "Did the output change from last release?"
   - Save expected outputs as "golden files" for comparison

---

## When to Add Test Data

Add test data here **ONLY** when you need:

✅ **Test fixtures** - Invalid/edge case inputs for custom tests
✅ **Golden files** - Known-good outputs for comparison
✅ **Mock data** - Simulated responses for testing error paths
✅ **Edge case data** - Unusual but valid test inputs

---

## 📁 Directory Structure

### fixtures/

**Reusable test inputs** that multiple tests can use.

```
fixtures/
├── inventories/
│   ├── minimal-inventory.yml
│   ├── complex-inventory.yml
│   └── invalid-inventory.yml
├── playbooks/
│   ├── simple-playbook.yml
│   └── invalid-syntax.yml
└── configs/
    ├── ansible.cfg
    └── navigator.yml
```

**Example use case:**
Testing how exercises handle different inventory formats.

### samples/

**Example files** to demonstrate patterns or for manual testing.

```
samples/
├── role-templates/
│   ├── basic-role/
│   └── complex-role/
├── solution-examples/
│   ├── good-solution.yml
│   └── bad-solution.yml
└── outputs/
    ├── expected-output.txt
    └── error-output.txt
```

**Example use case:**
Providing sample solutions for comparison during testing.

---

## Creating Test Fixtures

### Example: Inventory Fixtures

**File:** `fixtures/inventories/edge-cases.yml`

```yaml
# Test inventory with edge cases

[webservers]
# Host with unusual characters
web-server-01.example.com
web_server_02.example.com

[databases]
# IPv6 address
db[2001:db8::1]

# Localhost variations
localhost ansible_connection=local
127.0.0.1 ansible_connection=local

[all:vars]
# Variable with special characters
app_name="My App (Production)"
```

**Use in tests:**
```bash
# Test exercise with edge-case inventory
ansible-navigator run playbook.yml \
  -i test-data/fixtures/inventories/edge-cases.yml
```

---

## Creating Sample Data

### Example: Golden File (Expected Output)

**File:** `samples/outputs/verify-service-expected.json`

```json
{
  "service_status": {
    "httpd": {
      "running": true,
      "enabled": true,
      "status": "active"
    }
  }
}
```

**Use in tests:**
```bash
# Compare actual output to golden file
actual_output=$(ansible webservers -m service_facts)
diff <(echo "$actual_output") test-data/samples/outputs/verify-service-expected.json
```

---

## Use Cases

### 1. Testing Invalid Inputs

**Scenario:** Verify exercises handle syntax errors gracefully

```
fixtures/playbooks/
├── valid-playbook.yml       # Should work
├── syntax-error.yml         # Should fail with clear error
├── undefined-var.yml        # Should fail on undefined variable
└── missing-hosts.yml        # Should fail on missing hosts
```

### 2. Testing Edge Cases

**Scenario:** Test with unusual but valid configurations

```
fixtures/inventories/
├── empty-inventory.yml      # No hosts
├── single-host.yml          # Only one host
├── large-inventory.yml      # 100+ hosts
└── special-chars.yml        # Hosts with unusual names
```

### 3. Providing Examples

**Scenario:** Sample solutions for comparison

```
samples/role-examples/
├── minimal-role/            # Bare minimum structure
├── complete-role/           # Fully-featured role
└── bad-role/                # Common mistakes
```

---

## Organizing Test Data

### By Course

```
test-data/
└── fixtures/
    ├── <ANSIBLE-COURSE>/
    │   ├── <exercise-name>/
    │   └── <exercise-name>/
    └── <RHEL-COURSE>/
        ├── servicemgmt/
        └── netlink/
```

### By Type

```
test-data/
└── fixtures/
    ├── inventories/
    ├── playbooks/
    ├── roles/
    └── configs/
```

**Recommendation:** Use by-type organization for reusable fixtures, by-course for course-specific data.

---

## Referencing Test Data in Custom Tests

In `test-cases/custom/MY-TEST.md`:

```markdown
### TC-CUSTOM-001: Test with Invalid Inventory

**Test Steps**:
1. Copy invalid inventory:
   `cp test-data/fixtures/inventories/invalid-syntax.yml ~/exercise/inventory`
2. Run playbook:
   `ansible-navigator run site.yml`
3. Verify error message is helpful

**Expected Result**:
✅ Clear error about inventory syntax
✅ Points to line number with issue
```

---

## Tips

✅ **DO:**
- Use descriptive filenames (`invalid-yaml-syntax.yml` not `bad.yml`)
- Document what makes each fixture special
- Keep fixtures minimal (only what's needed to test)
- Version control test data
- Include comments in fixture files

❌ **DON'T:**
- Include sensitive data (passwords, keys)
- Duplicate data from lesson repos
- Create fixtures you never use
- Make fixtures too complex
- Hardcode absolute paths

---

## Best Practices

### 1. Keep Fixtures Minimal

```yaml
# Good: Only what's needed
[webservers]
server1.example.com

# Bad: Unnecessary complexity
[webservers]
server1.example.com ansible_host=192.168.1.10 ansible_port=22 ansible_user=root
server2.example.com ansible_host=192.168.1.11 ansible_port=22 ansible_user=root
```

### 2. Make Fixtures Self-Documenting

```yaml
# inventory-edge-case-ipv6.yml
# Tests: Exercise handles IPv6 addresses correctly
# Expected: Playbook runs without errors

[databases]
db[2001:db8::1]
```

### 3. Organize by Purpose

```
fixtures/
├── valid/          # Should work
├── invalid/        # Should fail
└── edge-cases/     # Unusual but valid
```

---

## Cleanup

Since test data can grow over time:

### Regular Maintenance

```bash
# Find unused fixtures (not referenced in any test)
grep -r "test-data/fixtures" test-cases/ config/

# Remove old/obsolete fixtures
rm test-data/fixtures/old-course-version/
```

### Before Committing

```bash
# Check for sensitive data
grep -ri "password\|secret\|key" test-data/

# Check file sizes (keep fixtures small)
find test-data/ -size +100k
```

---

## Quick Decision Guide

**Should I create test fixtures?**

| Situation | Need Fixtures? | What to Do |
|-----------|----------------|------------|
| Testing a basic exercise | ❌ NO | Just run `/qa au0025l exercise-name` |
| Testing all exercises | ❌ NO | Use `/qa chapter 2` |
| Testing if solution works | ❌ NO | QA skill tests solutions automatically |
| Testing error messages | ✅ YES | Create invalid fixture + custom test |
| Testing with 100+ hosts | ✅ YES | Create large inventory fixture |
| Testing edge cases | ✅ YES | Create edge case fixture + custom test |
| Checking if output changed | ✅ YES | Save expected output as golden file |

---

## Practical Examples

### Example 1: Regular Testing (No Fixtures Needed)

**Scenario**: Test if the `<exercise-name>` guided exercise works.

**What to do**:
```bash
# Just run the QA skill - no fixtures needed
/qa au0025l <exercise-name>
```

**Why no fixtures?** The exercise already has everything:
- `materials/labs/<exercise-name>/inventory`
- `materials/labs/<exercise-name>/ansible.cfg`
- `materials/labs/<exercise-name>/solutions/*.sol`

---

### Example 2: Testing Error Handling (Fixtures Needed)

**Scenario**: Test if students get helpful error messages when they make a YAML syntax mistake.

**What to do**:

1. **Create the invalid fixture**:
```bash
mkdir -p ~/.claude/skills/qa/test-data/fixtures/playbooks/
cat > ~/.claude/skills/qa/test-data/fixtures/playbooks/invalid-syntax.yml <<'EOF'
---
- name: Test playbook
  hosts: all
  tasks
    - name: Install httpd  # Missing colon after "tasks"
      ansible.builtin.dnf:
        name: httpd
EOF
```

2. **Create a custom test case**:
```bash
cat > ~/.claude/skills/qa/test-cases/custom/<ANSIBLE-COURSE>-error-handling.md <<'EOF'
### TC-CUSTOM-001: YAML Syntax Error Handling

**Priority**: P2
**Category**: Error Handling

**Test Steps**:
1. Copy invalid playbook to exercise directory
2. Run: `ansible-navigator run invalid-syntax.yml -m stdout`
3. Observe error message

**Expected Result**:
✅ Clear error message about YAML syntax
✅ Points to line number with issue
✅ Suggests how to fix (e.g., "add colon after tasks")
EOF
```

3. **Run the custom test**:
```bash
/qa au294 <exercise-name> test-cases/custom/<ANSIBLE-COURSE>-error-handling.md
```

---

### Example 3: Testing Edge Cases (Fixtures Needed)

**Scenario**: Test if the exercise works with 100 hosts.

**What to do**:

1. **Create large inventory fixture**:
```bash
mkdir -p ~/.claude/skills/qa/test-data/fixtures/inventories/
cat > ~/.claude/skills/qa/test-data/fixtures/inventories/large-inventory.yml <<'EOF'
[webservers]
web[01:100].example.com
EOF
```

2. **Create custom test**:
```bash
cat > ~/.claude/skills/qa/test-cases/custom/<ANSIBLE-COURSE>-performance.md <<'EOF'
### TC-PERF-001: Performance with 100 Hosts

**Priority**: P3
**Category**: Performance

**Test Steps**:
1. Copy large inventory: `cp test-data/fixtures/inventories/large-inventory.yml ~/exercise/`
2. Run playbook: `ansible-navigator run site.yml -m stdout`
3. Measure execution time

**Expected Result**:
✅ Playbook completes in under 5 minutes
✅ No timeout errors
EOF
```

3. **Run the test**:
```bash
/qa au294 <exercise-name> test-cases/custom/<ANSIBLE-COURSE>-performance.md
```

---

## Summary for Non-QA Engineers

**99% of the time**: Don't create test fixtures. Just run `/qa` command.

**1% of the time**: Create fixtures for advanced testing:
- Error handling (invalid files)
- Edge cases (unusual inputs)
- Performance testing (large datasets)
- Regression testing (golden files)

**When in doubt**: Don't create fixtures. Use the actual exercise materials.
