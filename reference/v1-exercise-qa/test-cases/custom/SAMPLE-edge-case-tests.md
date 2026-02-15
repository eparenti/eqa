# Sample: Edge Case Test Cases

**Purpose**: Example test cases for testing exercises with unusual but valid inputs.

**Use this as a template** when creating custom edge case tests.

---

## Sample 1: Large Inventory

### TC-EDGE-001: Performance with 100 Hosts

**Priority**: P3
**Category**: Edge Cases - Performance

**Prerequisites**:
- Exercise started: `lab start <exercise-name>`
- Test fixture created: `test-data/fixtures/inventories/large-inventory.yml`

**Test Steps**:
1. Copy large inventory to exercise directory:
   ```bash
   ssh workstation "cp ~/.claude/skills/qa/test-data/fixtures/inventories/large-inventory.yml ~/<exercise-name>/inventory"
   ```

2. Run solution playbook:
   ```bash
   ssh workstation "cd ~/<exercise-name> && ansible-navigator run solutions/site.yml.sol -m stdout"
   ```

3. Measure execution time

**Expected Result**:
✅ Playbook completes successfully
✅ Execution time < 5 minutes
✅ No timeout errors
✅ All hosts processed correctly

**Pass/Fail Criteria**:
- ✅ PASS: Completes successfully within reasonable time
- ❌ FAIL: Timeouts, errors, or excessive execution time

**Notes**:
- Adjust host count based on exercise complexity
- Consider infrastructure limitations

---

## Sample 2: Special Characters in Variables

### TC-EDGE-002: Variables with Special Characters

**Priority**: P2
**Category**: Edge Cases - Data Validation

**Prerequisites**:
- Exercise started
- Test fixture: `test-data/fixtures/vars/special-chars.yml`

**Test Steps**:
1. Create variables file with special characters:
   ```yaml
   app_name: "My App (Production) [v2.0]"
   file_path: "/var/www/html/index.html"
   description: "Test's \"special\" characters: @#$%"
   ```

2. Run playbook that uses these variables:
   ```bash
   ssh workstation "cd ~/exercise && ansible-navigator run -e @special-chars.yml site.yml -m stdout"
   ```

3. Verify correct handling

**Expected Result**:
✅ Playbook processes special characters correctly
✅ Files/templates contain exact strings
✅ No escaping issues

**Pass/Fail Criteria**:
- ✅ PASS: Special characters handled correctly
- ❌ FAIL: Escaping errors or data corruption

---

## Sample 3: IPv6 Addresses in Inventory

### TC-EDGE-003: IPv6 Host Addresses

**Priority**: P2
**Category**: Edge Cases - Network Configuration

**Prerequisites**:
- Exercise supports network configuration
- Test fixture: `test-data/fixtures/inventories/ipv6-hosts.yml`

**Test Steps**:
1. Create inventory with IPv6 addresses:
   ```ini
   [webservers]
   web[2001:db8::1]

   [databases]
   db[2001:db8::2]
   ```

2. Run playbook:
   ```bash
   ssh workstation "ansible-navigator run -i ipv6-hosts.yml site.yml -m stdout"
   ```

3. Check connectivity and execution

**Expected Result**:
✅ Ansible connects to IPv6 hosts
✅ Playbook executes successfully
✅ No parsing errors

**Pass/Fail Criteria**:
- ✅ PASS: IPv6 addresses work correctly
- ❌ FAIL: Connection or parsing errors

**Notes**:
- Only applicable if lab environment supports IPv6
- May need to configure IPv6 connectivity first

---

## Sample 4: Empty Inventory Group

### TC-EDGE-004: Playbook with Empty Host Group

**Priority**: P3
**Category**: Edge Cases - Boundary Conditions

**Prerequisites**:
- Exercise started
- Test fixture: `test-data/fixtures/inventories/empty-group.yml`

**Test Steps**:
1. Create inventory with empty group:
   ```ini
   [webservers]
   # No hosts defined

   [databases]
   db1.example.com
   ```

2. Run playbook targeting empty group:
   ```bash
   ssh workstation "ansible-navigator run -i empty-group.yml site.yml -m stdout"
   ```

3. Verify graceful handling

**Expected Result**:
✅ Playbook runs without errors
✅ Clear message: "skipping: no hosts matched"
✅ Tasks for other groups execute normally
✅ No crashes or failures

**Pass/Fail Criteria**:
- ✅ PASS: Gracefully handles empty group
- ❌ FAIL: Crashes, errors, or unclear behavior

---

## Sample 5: Long File Paths

### TC-EDGE-005: Deeply Nested File Paths

**Priority**: P3
**Category**: Edge Cases - File System

**Prerequisites**:
- Exercise involves file operations
- Test fixture: Long directory path

**Test Steps**:
1. Create deeply nested directory:
   ```bash
   ssh workstation "mkdir -p ~/exercise/very/long/path/to/test/deep/nesting/files"
   ```

2. Configure playbook to use long path:
   ```yaml
   template:
     src: template.j2
     dest: ~/exercise/very/long/path/to/test/deep/nesting/files/config.conf
   ```

3. Run playbook

**Expected Result**:
✅ File created successfully
✅ No path length errors
✅ Correct permissions

**Pass/Fail Criteria**:
- ✅ PASS: Long paths work correctly
- ❌ FAIL: Path length errors or failures

---

## Sample 6: Very Large Files

### TC-EDGE-006: Template with 10000+ Lines

**Priority**: P3
**Category**: Edge Cases - Performance

**Prerequisites**:
- Exercise uses templates
- Test fixture: Large template file

**Test Steps**:
1. Create large template file:
   ```bash
   # Generate 10000-line template
   for i in {1..10000}; do
     echo "line_$i: value_$i" >> large-template.j2
   done
   ```

2. Use template in playbook:
   ```bash
   ssh workstation "ansible-navigator run site.yml -m stdout"
   ```

3. Monitor performance

**Expected Result**:
✅ Template processed successfully
✅ No memory errors
✅ Reasonable processing time

**Pass/Fail Criteria**:
- ✅ PASS: Large file handled correctly
- ❌ FAIL: Crashes, timeouts, or errors

---

## How to Use These Samples

1. **Copy this file** for your course:
   ```bash
   cp test-cases/custom/SAMPLE-edge-case-tests.md \
      test-cases/custom/<ANSIBLE-COURSE>-edge-cases.md
   ```

2. **Select relevant edge cases**:
   - Not all edge cases apply to all exercises
   - Pick cases that match exercise functionality

3. **Create test fixtures**:
   ```bash
   # Large inventory
   cat > test-data/fixtures/inventories/large-inventory.yml <<'EOF'
   [webservers]
   web[001:100].example.com
   EOF

   # IPv6 hosts
   cat > test-data/fixtures/inventories/ipv6-hosts.yml <<'EOF'
   [webservers]
   web[2001:db8::1]
   EOF
   ```

4. **Run tests**:
   ```bash
   /qa au294 <exercise-name> test-cases/custom/<ANSIBLE-COURSE>-edge-cases.md
   ```

---

## Tips for Edge Case Testing

✅ **DO:**
- Test realistic edge cases students might encounter
- Focus on boundary conditions
- Test unusual but valid inputs
- Document infrastructure requirements

❌ **DON'T:**
- Test impossible scenarios
- Create overly complex edge cases
- Test implementation details
- Expect perfect handling of extreme cases

---

## Common Edge Cases by Exercise Type

### Playbook Development Exercises
- Large inventories (100+ hosts)
- Empty inventory groups
- Special characters in variables
- Long file paths

### Role Development Exercises
- Role with many dependencies
- Circular role dependencies
- Deeply nested role structure

### Template Exercises
- Very large templates
- Special characters in template variables
- Complex Jinja2 expressions

### Inventory Exercises
- IPv6 addresses
- Mixed IPv4/IPv6
- Unusual hostnames
- Port specifications
