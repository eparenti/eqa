# Test Fixtures

**Test fixtures** are pre-made test files for testing error handling and edge cases.

---

## 📁 What's Here

### SAMPLE-* Files

**These are examples** showing you how to create your own fixtures. Don't edit these - copy and modify them for your needs.

```
fixtures/
├── playbooks/
│   ├── SAMPLE-invalid-tasks-syntax.yml    # Example: Missing colon
│   └── SAMPLE-undefined-variable.yml      # Example: Undefined vars
├── inventories/
│   ├── SAMPLE-large-inventory.yml         # Example: 100 hosts
│   └── SAMPLE-ipv6-hosts.yml             # Example: IPv6 addresses
└── vars/
    └── SAMPLE-special-characters.yml      # Example: Special chars
```

---

## Creating Your Own Fixtures

### Step 1: Copy a Sample

```bash
# Copy sample as starting point
cp test-data/fixtures/playbooks/SAMPLE-invalid-tasks-syntax.yml \
   test-data/fixtures/playbooks/<ANSIBLE-COURSE>-missing-colon.yml
```

### Step 2: Modify for Your Needs

```bash
# Edit to match your test case
vim test-data/fixtures/playbooks/<ANSIBLE-COURSE>-missing-colon.yml
```

### Step 3: Reference in Custom Test

In `test-cases/custom/<ANSIBLE-COURSE>-error-handling.md`:

```markdown
### TC-ERROR-001: Missing Colon Error

**Test Steps**:
1. Copy fixture:
   `cp test-data/fixtures/playbooks/<ANSIBLE-COURSE>-missing-colon.yml ~/exercise/`
2. Run: `ansible-navigator run <ANSIBLE-COURSE>-missing-colon.yml -m stdout`
3. Verify error message is clear
```

---

## Fixture Categories

### playbooks/

**Invalid playbooks** for testing error handling:
- Syntax errors (missing colons, wrong indentation)
- Undefined variables
- Wrong module names
- Missing required parameters

**When to create**:
- Testing error messages
- Verifying student mistakes are caught
- Ensuring clear error guidance

---

### inventories/

**Edge case inventories** for testing unusual inputs:
- Large inventories (100+ hosts)
- IPv6 addresses
- Empty groups
- Special characters in hostnames

**When to create**:
- Performance testing
- Edge case validation
- Boundary condition testing

---

### vars/

**Variable files** with edge cases:
- Special characters (@, #, $, etc.)
- Long strings
- Multi-line content
- Unusual but valid values

**When to create**:
- Testing template rendering
- Variable substitution testing
- Special character handling

---

## Naming Convention

**Format**: `<COURSE>-<purpose>.yml`

Examples:
- `<ANSIBLE-COURSE>-invalid-syntax.yml`
- `<RHEL-COURSE>-large-inventory.yml`
- `<ANSIBLE-COURSE>-special-chars.yml`

**For samples**: Use `SAMPLE-` prefix so they're clearly templates:
- `SAMPLE-invalid-tasks-syntax.yml`
- `SAMPLE-large-inventory.yml`

---

## Best Practices

### ✅ DO:

- **Keep fixtures minimal** - Only include what's needed for the test
- **Add comments** - Explain what makes this fixture special
- **Use descriptive names** - `invalid-tasks-syntax.yml` not `bad.yml`
- **Document expected behavior** - What should happen when using this?

### ❌ DON'T:

- **Include sensitive data** - No real passwords, keys, or secrets
- **Make fixtures too complex** - Keep them simple and focused
- **Duplicate lesson materials** - Use actual exercise files when possible
- **Create unused fixtures** - Only create what you'll actually test

---

## Example: Creating Error Handling Fixture

**Goal**: Test error message when student forgets colon after `tasks`.

**1. Create the fixture**:

```bash
cat > test-data/fixtures/playbooks/<ANSIBLE-COURSE>-missing-colon.yml <<'EOF'
---
# TEST FIXTURE: Missing colon after "tasks"
# Expected: Syntax error pointing to line 4

- name: Configure web server
  hosts: webservers
  tasks  # ERROR: Missing colon here
    - name: Install httpd
      ansible.builtin.dnf:
        name: httpd
EOF
```

**2. Create the test case**:

```bash
cat > test-cases/custom/<ANSIBLE-COURSE>-error-tests.md <<'EOF'
### TC-ERROR-001: Missing Colon Error Handling

**Test Steps**:
1. Run: `ansible-navigator run test-data/fixtures/playbooks/<ANSIBLE-COURSE>-missing-colon.yml -m stdout`

**Expected Result**:
✅ Syntax error on line 4
✅ Error mentions "tasks"
✅ Message is clear
EOF
```

**3. Run the test**:

```bash
/qa au294 <exercise-name> test-cases/custom/<ANSIBLE-COURSE>-error-tests.md
```

---

## Common Fixture Patterns

### Invalid YAML Syntax

```yaml
# Missing colon
- name: Test
  hosts: all
  tasks  # <-- Missing :
    - name: Do something
```

### Undefined Variable

```yaml
- name: Test
  hosts: all
  tasks:
    - name: Use undefined var
      debug:
        msg: "{{ undefined_var }}"  # <-- Not defined
```

### Wrong Module Name

```yaml
- name: Test
  hosts: all
  tasks:
    - name: Typo in module
      ansibl.builtin.debug:  # <-- Should be "ansible"
        msg: "Hello"
```

### Large Inventory

```ini
[webservers]
web[001:100].example.com  # 100 hosts

[databases]
db[001:050].example.com   # 50 hosts
```

---

## Cleanup

**Before committing**:

```bash
# Check for sensitive data
grep -ri "password\|secret\|key" test-data/fixtures/

# Verify file sizes (keep small)
find test-data/fixtures/ -size +50k
```

**Remove unused fixtures**:

```bash
# Find fixtures not referenced in any test
grep -r "test-data/fixtures" test-cases/

# Delete orphaned fixtures
rm test-data/fixtures/old-unused-fixture.yml
```

---

## Summary

**Purpose**: Test error handling and edge cases

**99% of testing**: Don't need fixtures (use actual exercise materials)

**1% of testing**: Create fixtures for:
- Error message validation
- Edge case testing
- Boundary condition testing

**Remember**: Copy SAMPLE-* files as templates, don't edit them directly.
