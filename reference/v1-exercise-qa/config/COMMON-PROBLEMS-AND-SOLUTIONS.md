# Problem-Solution Patterns for QA Testing

**Purpose**: Common problems and their solutions for automated QA diagnostics.

---

## Problem Pattern: Missing Ansible Collection

### Detection Signature
```
ERROR! couldn't resolve module/action 'ansible.posix.firewalld'
ERROR! couldn't resolve module/action '<collection>.<module>'
```

### Root Cause Analysis
- Required Ansible collection not installed
- Collection path not configured correctly
- Wrong collection name or version

### Investigation Steps
1. Check which collection is missing from error message
2. Verify if collection should be in requirements.yml
3. Check if collection_path is configured in ansible.cfg
4. Verify if collection is available in automation hub or galaxy

### Solution Options

#### OPTION 1: Install Collection (Quick Fix) ✅ RECOMMENDED
**What it fixes**: Immediately installs missing collection

**Commands**:
```bash
# For ansible.posix
ssh workstation "ansible-galaxy collection install ansible.posix"

# For specific version
ssh workstation "ansible-galaxy collection install ansible.posix:1.5.4"

# Verify installation
ssh workstation "ansible-galaxy collection list | grep ansible.posix"
```

**Trade-offs**:
- ✅ Fast, immediate fix
- ✅ Works for manual testing
- ⚠️ Doesn't fix root cause if collection should be in requirements
- ⚠️ Not persistent across lab resets

**Verification**:
```bash
# Test the previously failing playbook
cd <exercise-dir>
cp solutions/<playbook>.sol <playbook>.yml
ansible-navigator run <playbook>.yml -m stdout
# Should now succeed
```

#### OPTION 2: Add to requirements.yml (Proper Fix)
**What it fixes**: Ensures collection is installed during lab setup

**Commands**:
```bash
# 1. Check current requirements.yml
cat /home/developer/git-repos/active/AU00XXL/classroom/grading/src/au00xxl/ansible/requirements.yml

# 2. Add collection (if not present)
# Edit requirements.yml to add:
---
collections:
  - name: ansible.posix
    version: ">=1.5.0"

# 3. Install from requirements
ssh workstation "cd <exercise-dir> && ansible-galaxy collection install -r requirements.yml"

# 4. Commit changes
cd /home/developer/git-repos/active/AU00XXL
git add classroom/grading/src/au00xxl/ansible/requirements.yml
git commit -m "Add ansible.posix to requirements.yml"
```

**Trade-offs**:
- ✅ Proper solution, fixes root cause
- ✅ Persistent across lab setups
- ✅ Students will have collection available
- ⚠️ Requires repo modification
- ⚠️ Need to rebuild lab scripts

**Verification**:
```bash
# Test fresh install
ssh workstation "lab finish au00XXl && lab start au00XXl"
# Collection should be present
```

#### OPTION 3: Use Alternative Module
**What it fixes**: Avoids dependency on external collection

**Example**: Replace ansible.posix.firewalld with firewalld module or command
```yaml
# Before:
- name: Allow http through firewall
  ansible.posix.firewalld:
    service: http
    permanent: true
    state: enabled
    immediate: true

# After Option 3a: Use community.general.firewalld (if available)
- name: Allow http through firewall
  community.general.firewalld:
    service: http
    permanent: true
    state: enabled
    immediate: true

# After Option 3b: Use firewall-cmd command
- name: Allow http through firewall
  ansible.builtin.command:
    cmd: firewall-cmd --permanent --add-service=http
  notify: Reload firewall

# Add handler:
- name: Reload firewall
  ansible.builtin.command:
    cmd: firewall-cmd --reload
```

**Commands to implement**:
```bash
# 1. Edit the solution playbook
vi /home/developer/git-repos/active/AU00XXL/.../solutions/<file>.sol

# 2. Replace module as shown above

# 3. Test
cd <exercise-dir>
cp solutions/<file>.sol <file>.yml
ansible-navigator run <file>.yml -m stdout

# 4. Commit if successful
git add solutions/<file>.sol
git commit -m "Replace ansible.posix.firewalld with command module"
```

**Trade-offs**:
- ✅ No external dependencies
- ✅ Works immediately
- ⚠️ Less idempotent than module
- ⚠️ More verbose, harder to maintain
- ⚠️ May not match course teaching objectives

---

## Problem Pattern: Module Execution Failure

### Detection Signature
```
fatal: [host]: FAILED! => {"changed": false, "msg": "..."}
TASK [task name] failed
```

### Root Cause Analysis
- Module parameters incorrect
- Target host state doesn't match expectations
- Permissions issue
- Service/package not available

### Investigation Steps
1. Read full error message for specific failure reason
2. Check task parameters against module documentation
3. Verify target host state manually
4. Check if become/privilege escalation is needed

### Solution Options

#### OPTION 1: Fix Module Parameters
**Detection**: Error mentions "unsupported parameter" or "required parameter missing"

**Commands**:
```bash
# 1. Check module documentation
ansible-doc <module-name>

# 2. Read the failing task
cat solutions/<playbook>.sol | grep -A 10 "task-name"

# 3. Fix parameters in solution file
vi solutions/<playbook>.sol

# 4. Test with corrected playbook
cd <exercise-dir>
cp solutions/<playbook>.sol <playbook>.yml
ansible-navigator run <playbook>.yml -m stdout
```

#### OPTION 2: Add Become/Privilege Escalation
**Detection**: Error mentions "Permission denied" or "requires root"

**Fix**:
```yaml
# Add to task:
- name: Task requiring root
  ansible.builtin.<module>:
    ...
  become: true

# Or add to play:
- name: Play name
  hosts: all
  become: true
  tasks:
    ...
```

#### OPTION 3: Check Target Host State
**Detection**: Error mentions "not found", "does not exist", "already exists"

**Investigation**:
```bash
# SSH to target host and verify state
ssh workstation "ssh <target-host> <check-command>"

# Example: Check if package exists
ssh workstation "ssh servera rpm -q httpd"

# Example: Check if file exists
ssh workstation "ssh servera ls -la /path/to/file"

# Example: Check service status
ssh workstation "ssh servera systemctl status httpd"
```

---

## Problem Pattern: Inventory/Host Unreachable

### Detection Signature
```
fatal: [host]: UNREACHABLE!
Could not connect to host
ssh: connect to host <hostname> port 22: Connection refused
```

### Root Cause Analysis
- Host not defined in inventory
- Hostname resolution failure
- SSH connectivity issue
- Host not started/available

### Investigation Steps
```bash
# 1. Check inventory
cat <exercise-dir>/inventory

# 2. Test SSH connectivity
ssh workstation "ssh <hostname> hostname"

# 3. Check if host in /etc/hosts
ssh workstation "grep <hostname> /etc/hosts"

# 4. Ping host
ssh workstation "ping -c 2 <hostname>"
```

### Solution Options

#### OPTION 1: Fix Inventory File
**Commands**:
```bash
# 1. Check inventory syntax
cat inventory

# 2. Verify host is defined
grep "<hostname>" inventory

# 3. Fix inventory
vi inventory

# 4. Test inventory
ansible-navigator inventory --list -m stdout

# 5. Test connectivity
ansible-navigator run -m ping <hostname>
```

#### OPTION 2: Fix Hostname Resolution
**Commands**:
```bash
# Add to /etc/hosts if missing
ssh workstation "echo '172.25.250.X <hostname>.lab.example.com <hostname>' | sudo tee -a /etc/hosts"
```

#### OPTION 3: Start/Restart Lab Environment
**Commands**:
```bash
# Restart lab
ssh workstation "lab finish <lesson-code> && lab start <lesson-code>"
```

---

## Problem Pattern: File Not Found

### Detection Signature
```
Could not find or access '<filename>'
Unable to retrieve file contents
No such file or directory
```

### Root Cause Analysis
- File path incorrect in playbook
- File not present in expected location
- Case sensitivity issue
- File in wrong directory

### Investigation Steps
```bash
# 1. Check what playbook expects
grep -n "src:" <playbook>.sol
grep -n "file:" <playbook>.sol

# 2. Check if file exists
ls -la <exercise-dir>/files/
ls -la <exercise-dir>/templates/

# 3. Find file in exercise
find <exercise-dir> -name "<filename>"
```

### Solution Options

#### OPTION 1: Fix File Path in Playbook
```yaml
# Before:
- name: Copy file
  ansible.builtin.copy:
    src: index.html
    dest: /var/www/html/

# After (relative to playbook location):
- name: Copy file
  ansible.builtin.copy:
    src: files/index.html
    dest: /var/www/html/
```

#### OPTION 2: Create Missing File
```bash
# If file should exist but doesn't
cd <exercise-dir>/files/
cat > <filename> << 'EOF'
<content>
EOF

# Verify
ls -la files/<filename>
```

#### OPTION 3: Copy from Another Exercise
```bash
# Find file in other exercises
find /home/developer/git-repos/active/AU00XXL -name "<filename>"

# Copy from similar exercise
cp <source-path> <exercise-dir>/files/
```

---

## Problem Pattern: Template/Variable Undefined

### Detection Signature
```
AnsibleUndefinedVariable: '<variable>' is undefined
template error while templating string
```

### Root Cause Analysis
- Variable not defined in playbook, vars file, or inventory
- Typo in variable name
- Variable scope issue

### Investigation Steps
```bash
# 1. Find variable usage
grep -n "<variable>" <playbook>.sol

# 2. Check where variables are defined
grep -r "<variable>" <exercise-dir>/

# 3. Check inventory variables
cat inventory | grep -A 5 "\[.*:vars\]"
```

### Solution Options

#### OPTION 1: Define Missing Variable
```yaml
# In playbook:
- name: Play name
  hosts: all
  vars:
    <variable>: <value>

# Or in separate vars file:
# vars.yml
<variable>: <value>

# Reference in playbook:
- name: Play name
  hosts: all
  vars_files:
    - vars.yml
```

#### OPTION 2: Fix Variable Name Typo
```bash
# Find all references
grep -n "<wrong-variable>" <playbook>.sol

# Replace with correct name
sed -i 's/<wrong-variable>/<correct-variable>/g' <playbook>.sol
```

#### OPTION 3: Use Default Filter
```yaml
# Make variable optional with default
- name: Task
  ansible.builtin.debug:
    msg: "{{ variable | default('default_value') }}"
```

---

## Problem Pattern: Syntax Error in Playbook

### Detection Signature
```
ERROR! Syntax Error while loading YAML
mapping values are not allowed here
```

### Root Cause Analysis
- YAML indentation error
- Missing colon or dash
- Quote mismatch
- Invalid YAML structure

### Investigation Steps
```bash
# 1. Check YAML syntax
yamllint <playbook>.sol

# 2. Find specific line
# Error usually shows line number
head -n <line-number> <playbook>.sol | tail -10

# 3. Use online YAML validator if needed
```

### Solution Options

#### OPTION 1: Fix Indentation
```yaml
# Before (wrong):
tasks:
- name: Task
ansible.builtin.debug:
  msg: "test"

# After (correct):
tasks:
  - name: Task
    ansible.builtin.debug:
      msg: "test"
```

#### OPTION 2: Fix Quoting
```yaml
# Before:
msg: "It's a test"  # ERROR: unescaped quote

# After:
msg: "It's a test"  # Escaped quote
# Or:
msg: 'It'\''s a test'
# Or:
msg: It's a test  # No quotes needed
```

---

## Problem Pattern: Missing Prerequisite Resources (Users/Groups)

### Detection Signature
```
chown failed: failed to look up user <username>
chgrp failed: failed to look up group <groupname>
User <username> does not exist
Group <groupname> does not exist
```

### Root Cause Analysis
- Task attempts to set file/directory ownership to non-existent user or group
- User/group creation task missing from playbook
- User/group creation task in wrong order (after ownership task)
- User/group name typo or variable not defined

### Investigation Steps
1. Check error message for specific user/group that's missing
2. Search playbook for user/group creation tasks
3. Verify task order - resource creation must come before usage
4. Check if user/group name is defined as variable
5. Look for similar patterns in other working exercises

### Solution Options

#### OPTION 1: Add User/Group Creation Task (Proper Fix) ✅ RECOMMENDED
**What it fixes**: Creates missing user/group before attempting to use it

**Commands**:
```bash
# For missing user:
# Add to playbook BEFORE any tasks that use the user:
- name: Create <service> user
  ansible.builtin.user:
    name: "{{ username_var }}"
    state: present
    shell: /sbin/nologin  # For service accounts (security best practice)
    create_home: true     # If home directory needed
    system: true          # For system service accounts

# For missing group:
- name: Create <service> group
  ansible.builtin.group:
    name: "{{ groupname_var }}"
    state: present
    system: true  # For system groups
```

**Example Fix** (FTP server scenario):
```yaml
# Add this task BEFORE directory creation:
- name: Create FTP demo user
  ansible.builtin.user:
    name: "{{ ftp_user }}"
    state: present
    shell: /sbin/nologin
    create_home: true

# Then this task will work:
- name: Create FTP demo upload directory
  ansible.builtin.file:
    path: "{{ upload_path }}"
    state: directory
    owner: "{{ ftp_user }}"
    group: "{{ ftp_user }}"
    mode: '0755'
```

**Trade-offs**:
- ✅ Proper solution, fixes root cause
- ✅ Follows Ansible best practices (create before use)
- ✅ Security best practice: `/sbin/nologin` prevents interactive login for service accounts
- ✅ Makes playbook idempotent
- ⚠️ Requires playbook modification
- ⚠️ Must verify correct task order

**Verification**:
```bash
# Test playbook
ansible-navigator run <playbook>.yml -m stdout
# Should succeed now

# Verify user created on target
ssh workstation "ssh <target-host> id <username>"
# Should show user details

# Verify ownership
ssh workstation "ssh <target-host> ls -la <path>"
# Should show correct owner/group
```

#### OPTION 2: Use Existing System User (Alternative)
**What it fixes**: Uses pre-existing system user instead of creating custom one

**Example**:
```yaml
# Instead of custom user, use system user
- name: Create directory
  ansible.builtin.file:
    path: /var/ftp/upload
    state: directory
    owner: root      # System user always exists
    group: root
    mode: '0755'
```

**Trade-offs**:
- ✅ No user creation needed
- ✅ Simpler playbook
- ⚠️ May not align with course teaching objectives
- ⚠️ Less secure (root ownership vs dedicated service account)
- ⚠️ Doesn't demonstrate user management best practices

**Verification**:
```bash
# Test playbook
ansible-navigator run <playbook>.yml -m stdout
```

### Security Best Practices

**Service Account Creation**:
```yaml
- name: Create service account
  ansible.builtin.user:
    name: serviceuser
    state: present
    shell: /sbin/nologin      # Prevents interactive login
    system: true              # Creates system user (UID < 1000)
    create_home: false        # No home directory for services (unless needed)
    comment: "Service account for X"
```

**Why `/sbin/nologin`?**
- Prevents unauthorized interactive access
- Standard for service accounts
- User can still own files/processes but cannot login

### Common Scenarios

**Scenario 1**: Web Server
```yaml
# Create web service user
- name: Create apache user
  ansible.builtin.user:
    name: apache
    state: present
    shell: /sbin/nologin
    system: true

# Then use it
- name: Deploy web content
  ansible.builtin.copy:
    src: index.html
    dest: /var/www/html/
    owner: apache
    group: apache
```

**Scenario 2**: FTP Server
```yaml
# Create FTP user with home directory
- name: Create FTP user
  ansible.builtin.user:
    name: ftpuser
    state: present
    shell: /sbin/nologin
    create_home: true

# Create upload directory
- name: Create upload directory
  ansible.builtin.file:
    path: /home/ftpuser/upload
    state: directory
    owner: ftpuser
    group: ftpuser
    mode: '0755'
```

---

## Problem Pattern: Service Start Failure

### Detection Signature
```
Unable to start service <service-name>
Job for <service>.service failed because the control process exited with error code
systemd[1]: <service>.service: Failed with result 'exit-code'
Failed to start <service-name> service
```

### Root Cause Analysis
- Service configuration file syntax error
- Port conflict (service port already in use)
- SELinux policy denial
- Missing dependencies
- Incorrect file permissions
- Service binary not found or not executable

### Investigation Steps
1. Check service status and logs
```bash
# Check service status
ssh workstation "ssh <target-host> systemctl status <service>"

# Check service logs
ssh workstation "ssh <target-host> journalctl -u <service> -n 50 --no-pager"

# Check for syntax errors in config
ssh workstation "ssh <target-host> <service> -t"  # For nginx, apache, etc.
```

2. Check for port conflicts
```bash
# Check if port is already in use
ssh workstation "ssh <target-host> ss -tuln | grep <port>"

# Check what's using the port
ssh workstation "ssh <target-host> lsof -i :<port>"
```

3. Check SELinux denials
```bash
# Check for SELinux denials
ssh workstation "ssh <target-host> ausearch -m avc -ts recent"

# Check SELinux boolean
ssh workstation "ssh <target-host> getsebool -a | grep <service>"
```

4. Verify configuration files
```bash
# Check config file syntax (nginx example)
ssh workstation "ssh <target-host> nginx -t"

# Check apache config
ssh workstation "ssh <target-host> apachectl configtest"

# Read config file
ssh workstation "ssh <target-host> cat /etc/<service>/<service>.conf"
```

### Solution Options

#### OPTION 1: Fix Configuration File Syntax
**Detection**: Service config test shows syntax error

**Commands**:
```bash
# Test configuration
ssh workstation "ssh <target-host> nginx -t"
# Output shows: nginx: [emerg] unexpected "}" in /etc/nginx/nginx.conf:45

# Read the problematic section
ssh workstation "ssh <target-host> sed -n '40,50p' /etc/nginx/nginx.conf"

# Fix the syntax error
# Edit the playbook template or config file to correct syntax
```

**Trade-offs**:
- ✅ Fixes root cause
- ✅ Service will start successfully
- ⚠️ Requires identifying exact syntax error
- ⚠️ May need to fix Jinja2 template in playbook

#### OPTION 2: Resolve Port Conflict
**Detection**: Logs show "address already in use" or port conflict

**Investigation**:
```bash
# Find what's using the port
ssh workstation "ssh <target-host> ss -tuln | grep :80"
ssh workstation "ssh <target-host> lsof -i :80"

# Stop conflicting service
ssh workstation "ssh <target-host> systemctl stop <conflicting-service>"

# Or change service port in config
```

**Fix**:
```yaml
# Option A: Stop conflicting service first
- name: Stop conflicting service
  ansible.builtin.systemd:
    name: <conflicting-service>
    state: stopped
    enabled: false

# Option B: Change port in config
- name: Configure service on different port
  ansible.builtin.lineinfile:
    path: /etc/<service>/<service>.conf
    regexp: '^Listen'
    line: 'Listen 8080'
```

**Trade-offs**:
- ✅ Resolves immediate conflict
- ⚠️ May not be desired solution (port 8080 vs 80)
- ⚠️ Stopping other services may break things

#### OPTION 3: Fix SELinux Context
**Detection**: SELinux denials in logs

**Commands**:
```bash
# Check SELinux denials
ssh workstation "ssh <target-host> ausearch -m avc -ts recent | grep <service>"

# Fix file context
ssh workstation "ssh <target-host> restorecon -Rv /etc/<service>/"

# Set SELinux boolean
ssh workstation "ssh <target-host> setsebool -P httpd_can_network_connect on"
```

**Fix in playbook**:
```yaml
# Add SELinux tasks
- name: Set SELinux context
  ansible.builtin.sefcontext:
    target: '/etc/<service>(/.*)?'
    setype: <service>_config_t
    state: present

- name: Apply SELinux context
  ansible.builtin.command:
    cmd: restorecon -Rv /etc/<service>/

# Or set boolean
- name: Enable SELinux boolean
  ansible.posix.seboolean:
    name: <boolean-name>
    state: true
    persistent: true
```

**Trade-offs**:
- ✅ Proper solution for SELinux systems
- ✅ Maintains security policies
- ⚠️ Requires understanding of SELinux contexts
- ⚠️ May require ansible.posix collection

#### OPTION 4: Check File Permissions and Ownership
**Detection**: Service fails with permission denied errors

**Investigation**:
```bash
# Check config file permissions
ssh workstation "ssh <target-host> ls -la /etc/<service>/"

# Check service binary permissions
ssh workstation "ssh <target-host> ls -la /usr/sbin/<service>"
```

**Fix**:
```yaml
# Add permission tasks
- name: Set config file permissions
  ansible.builtin.file:
    path: /etc/<service>/<service>.conf
    owner: root
    group: root
    mode: '0644'

- name: Set directory permissions
  ansible.builtin.file:
    path: /etc/<service>
    state: directory
    owner: root
    group: root
    mode: '0755'
```

**Trade-offs**:
- ✅ Fixes permission issues
- ✅ Standard permissions for system services
- ⚠️ Requires knowing correct ownership/permissions

### Common Scenarios

**Scenario 1: Nginx Configuration Template Error**
```yaml
# Problem: Template generates invalid nginx config
# Investigation:
# 1. Test nginx config: nginx -t
# 2. Read generated config: cat /etc/nginx/nginx.conf
# 3. Check template: cat templates/nginx.conf.j2

# Fix template syntax error:
- name: Deploy nginx configuration
  ansible.builtin.template:
    src: templates/nginx.conf.j2
    dest: /etc/nginx/nginx.conf
    owner: root
    group: root
    mode: '0644'
    validate: 'nginx -t -c %s'  # Add validation!

# Restart service
- name: Restart nginx
  ansible.builtin.systemd:
    name: nginx
    state: restarted
```

**Scenario 2: Apache Port Conflict**
```yaml
# Problem: Port 80 already in use
# Investigation shows nginx running on port 80

# Option A: Stop nginx first
- name: Stop nginx (port conflict)
  ansible.builtin.systemd:
    name: nginx
    state: stopped
    enabled: false

# Option B: Configure apache on different port
- name: Configure apache on port 8080
  ansible.builtin.lineinfile:
    path: /etc/httpd/conf/httpd.conf
    regexp: '^Listen'
    line: 'Listen 8080'
```

**Scenario 3: Service Dependencies Not Met**
```yaml
# Problem: Service requires database that isn't started

# Fix: Ensure dependency order
- name: Start database service
  ansible.builtin.systemd:
    name: mariadb
    state: started
    enabled: true

# Then start application
- name: Start application service
  ansible.builtin.systemd:
    name: webapp
    state: started
    enabled: true
```

### Verification Commands
```bash
# Verify service started successfully
ssh workstation "ssh <target-host> systemctl is-active <service>"
# Should output: active

# Verify service enabled
ssh workstation "ssh <target-host> systemctl is-enabled <service>"
# Should output: enabled

# Check service is listening on expected port
ssh workstation "ssh <target-host> ss -tuln | grep <port>"

# Test service functionality (HTTP example)
ssh workstation "ssh <target-host> curl -I http://localhost"
```

---

## Problem Pattern: Intentional Error (Teaching Exercise)

### Detection Signature
```
Course book explicitly mentions:
- "intentional error"
- "troubleshoot the following"
- "debug this problem"
- "fix the error"
- Exercise objectives include "troubleshooting" or "debugging"
```

### Root Cause Analysis
This is **NOT A BUG** - it's a pedagogical tool.

Course developers intentionally introduce errors to:
- Teach troubleshooting skills
- Practice debugging techniques
- Build problem-solving confidence
- Simulate real-world scenarios

### Investigation Steps

1. Check course book for error mention
```bash
# Search course book for troubleshooting language
grep -i "troubleshoot\|debug\|intentional\|fix the error" <course-book-section>
```

2. Review exercise objectives
```markdown
# Look for objectives like:
- "Practice debugging configuration files"
- "Learn to troubleshoot Ansible errors"
- "Identify and correct common mistakes"
```

3. Check if guidance provided
```markdown
# Course book should provide:
- Hints about where to look
- Troubleshooting methodology
- Expected error messages
- How to verify fix
```

4. Verify error is educational
```
Question: Does student learn from this error?
- If YES: Document as intentional
- If NO: May be unintentional bug
```

### How to Distinguish from Real Bugs

| Indicator | Intentional Error | Real Bug |
|-----------|-------------------|----------|
| Course book | Explicitly mentions error | Says it should work |
| Objectives | Include "troubleshoot/debug" | Focus on building, not fixing |
| Guidance | Provides hints/methodology | No troubleshooting help |
| Learning value | Teaches specific skill | Just frustrating |
| Student can fix | Yes, with course book help | No way to proceed |

### Documentation Format

**DO NOT report as bug**. Instead, document as:

```markdown
## Intentional Errors (Teaching Exercises)

**INTENTIONAL-001**: ansible.cfg intentionally misconfigured
- **Component**: Supporting file (ansible.cfg)
- **Course Book Reference**: Chapter 2, Section 2.5, Step 4
- **Objective**: "Practice debugging Ansible configuration"
- **Error Description**: Inventory path points to /etc/ansible/hosts (empty)
- **Expected Student Action**: Identify error, fix path to ./inventory
- **Hints Provided**:
  - "Step 3: Observe the 'No hosts matched' error"
  - "Step 4: Check the inventory configuration in ansible.cfg"
  - "Hint: Compare with previous exercises"
- **Assessment**: ✅ GOOD - Error is educational with clear guidance
- **Action**: Document only, NO FIX NEEDED
```

### Quality Assessment for Intentional Errors

Even intentional errors can be poorly designed:

**Good Intentional Error**:
```markdown
✅ Clear objective (teaches specific skill)
✅ Course book mentions error
✅ Hints guide student to solution
✅ Error message is informative
✅ Student can fix with course book help
✅ Learning value is clear

Example:
Course book: "The ansible.cfg file has an intentional configuration error.
             Step 3: Run the playbook and observe the error.
             Step 4: Check the inventory path in ansible.cfg.
             Hint: Where is the inventory file located?"
```

**Poor Intentional Error** (Report as BUG-GUIDANCE):
```markdown
❌ Course book just says "fix the error"
❌ No hints provided
❌ No troubleshooting methodology taught
❌ Student stuck with no learning path
❌ Error too complex for skill level

Example:
Course book: "Step 3: The configuration is wrong. Fix it."
             (No hints, no guidance, no learning value)

Report as: BUG-GUIDANCE-001 (P1)
```

### Example Scenarios

**Scenario 1: Configuration Error (Good)**
```yaml
# ansible.cfg (intentionally wrong)
[defaults]
inventory = /etc/ansible/hosts  # Wrong path

# Course book says:
"Guided Exercise: Troubleshooting Configuration

Objectives:
- Practice debugging Ansible configuration files
- Learn to identify inventory path errors

Step 1: Review the ansible.cfg file
Step 2: Run: ansible-navigator run playbook.yml -m stdout
Step 3: Observe the error: 'No hosts matched'
Step 4: Troubleshoot: Where is the inventory file actually located?
Step 5: Fix the inventory path in ansible.cfg
Step 6: Re-run the playbook to verify the fix

Hint: Use 'ls -la' to see all files in the exercise directory"
```

**QA Action**:
```markdown
INTENTIONAL-001: ansible.cfg inventory path error
- Course Book: Chapter 2, Guided Exercise: Troubleshooting Configuration
- Objective: Teach inventory path debugging
- Hints Provided: Yes, step-by-step guidance
- Assessment: ✅ GOOD - Clear, educational, achievable
- Action: Document, verify error exists and hints work
```

**Scenario 2: YAML Syntax Error (Poor - No Guidance)**
```yaml
# playbook.yml (intentionally broken)
---
- name: Deploy web server
  hosts: web
  tasks
    - name: Install httpd  # Missing colon after 'tasks'
      package:
        name: httpd
```

```markdown
# Course book says:
"Step 3: Run the playbook. It has an error. Fix it."
# NO HINTS, NO GUIDANCE, NO LEARNING
```

**QA Action**:
```markdown
BUG-GUIDANCE-001: YAML error lacks troubleshooting guidance
- Component: Course book
- Severity: P1 (Critical)
- Issue: Intentional error with no learning path
- Impact: Students stuck, frustrated, no skill development
- Fix: Add troubleshooting guidance:
  "Step 3: Run the playbook. You'll see a YAML syntax error.
   Step 4: Read the error message - which line has the problem?
   Step 5: Check for missing colons or incorrect indentation.
   Hint: The error is between lines 3-5."
```

### Verification Commands

```bash
# 1. Verify error exists
ssh workstation "cd /home/student/<exercise> && ansible-navigator run playbook.yml -m stdout"
# Should produce expected error

# 2. Follow course book troubleshooting steps
# Execute each step as student would

# 3. Verify hints lead to solution
# Can student fix error using only course book guidance?

# 4. Verify fix works
ssh workstation "cd /home/student/<exercise> && ansible-navigator run playbook.yml -m stdout"
# Should succeed after fix
```

### Report Template

```markdown
## Intentional Errors Assessment

### INTENTIONAL-001: <Error Description>
- **Exercise**: <exercise-name>
- **Component**: <file or configuration>
- **Course Book Reference**: <chapter, section, page>
- **Learning Objective**: <what should students learn?>
- **Error Type**: <configuration, syntax, logic, etc.>
- **Error Description**: <what is wrong?>
- **Expected Student Action**: <what should they do?>
- **Hints Provided**:
  - <hint 1>
  - <hint 2>
- **Troubleshooting Steps**:
  - <step 1>
  - <step 2>
- **Can Student Fix**: YES / NO / WITH DIFFICULTY
- **Learning Value**: HIGH / MEDIUM / LOW
- **Quality Assessment**: GOOD / ACCEPTABLE / POOR
- **Recommendation**:
  - If GOOD: Document, verify error and hints
  - If ACCEPTABLE: Suggest minor hint improvements
  - If POOR: Report as BUG-GUIDANCE (need better hints)
```

---

## Problem Pattern: Pedagogical Mismatch

### Detection Signature
```
Solution doesn't match what course book teaches
- Different module used
- Different approach taken
- More complex than necessary
- Uses concepts not yet taught
```

### Root Cause Analysis
- Solution developer used different approach
- Solution created before course book finalized
- Best practices changed after solution written
- Copy-paste from different exercise

### Investigation Steps

1. Compare solution to course book
```bash
# Read course book approach
# Read solution approach
# Identify differences
```

2. Check if both work
```bash
# Test course book approach
# Test solution approach
```

3. Assess pedagogical impact
```
Question: Will students be confused?
- If approaches are equivalent: Document as alternative
- If solution is different: BUG-PEDAGOGY (P2)
- If solution won't work: BUG-SOL (P1)
```

### Examples

**Example 1: Module Mismatch**
```yaml
# Course book teaches:
- name: Copy static file
  ansible.builtin.copy:
    src: files/index.html
    dest: /var/www/html/

# Solution uses:
- name: Copy static file
  ansible.builtin.template:  # DIFFERENT MODULE
    src: templates/index.j2
    dest: /var/www/html/
```

**QA Report**:
```markdown
BUG-PEDAGOGY-001: Solution uses template instead of copy
- Component: Solution file (site.yml.sol)
- Severity: P2 (Pedagogical)
- Course Book: Chapter 2, teaches copy module
- Solution: Uses template module
- Impact: Students confused when to use copy vs template
- Fix: Update solution to match course book teaching:
  - Use ansible.builtin.copy
  - Reference files/index.html
  OR: Update course book to teach template module
```

**Example 2: Complexity Mismatch**
```yaml
# Course book: Simple variable usage
# Objective: "Learn to use variables in playbooks"

# Solution includes:
- Variables (OBJECTIVE)
- Vault encryption (NOT YET TAUGHT)
- Complex conditionals (NOT YET TAUGHT)
- Loops (NOT YET TAUGHT)
- Handlers (NOT YET TAUGHT)
```

**QA Report**:
```markdown
BUG-COMPLEXITY-001: Solution too complex for learning objective
- Component: Solution file
- Severity: P2 (Pedagogical)
- Objective: "Learn to use variables"
- Solution complexity: Variables + vault + conditionals + loops + handlers
- Impact: Students overwhelmed, miss main learning point
- Fix: Simplify solution to focus only on variables
  - Remove vault usage
  - Remove complex conditionals
  - Remove loops
  - Use simple variable substitution only
```

### Severity Guidelines

**P1 (Critical)** - Solution doesn't work or uses wrong approach:
- Solution fails when tested
- Uses deprecated module
- Uses insecure practice

**P2 (Minor)** - Solution works but pedagogically confusing:
- Different module than taught
- More complex than necessary
- Alternative approach (both valid)

### Report Template

```markdown
BUG-PEDAGOGY-XXX: <Description>
- **Component**: Solution file / Course book
- **Severity**: P2 (Pedagogical)
- **Learning Objective**: <stated objective>
- **Course Book Approach**: <what book teaches>
- **Solution Approach**: <what solution does>
- **Difference**: <specific mismatch>
- **Impact**: <student confusion description>
- **Fix Options**:
  1. Update solution to match course book
  2. Update course book to match solution
  3. Document as alternative approach
- **Recommended Fix**: <option 1/2/3 with reasoning>
```

---

## Diagnostic Decision Tree

```
Test Failed or Issue Found?
│
├─ FIRST: Check if intentional (teaching exercise)?
│  ├─ Course book mentions "troubleshoot" or "debug"?
│  │  └─ → Intentional Error Pattern (Document, don't fix)
│  └─ No mention of troubleshooting?
│     └─ Continue to technical diagnosis →
│
├─ Course book step fails?
│  ├─ Course book says "this should work"?
│  │  ├─ Required file missing?
│  │  │  └─ → Lab Script Bug (P0 - deployment issue)
│  │  ├─ Instruction unclear or wrong?
│  │  │  └─ → Course Book Bug (P0 - instruction issue)
│  │  └─ Supporting file has error?
│  │     └─ → Supporting File Bug (P1 - config/template issue)
│  └─ Course book says "troubleshoot this"?
│     └─ → Intentional Error Pattern
│
├─ Solution doesn't match course book teaching?
│  ├─ Different module or approach?
│  │  └─ → Pedagogical Mismatch Pattern (P2)
│  └─ More complex than objective?
│     └─ → Complexity Mismatch Pattern (P2)
│
├─ Technical Error Patterns:
│  ├─ Error contains "couldn't resolve module"?
│  │  └─ → Missing Collection Pattern
│  ├─ Error contains "UNREACHABLE"?
│  │  └─ → Inventory/Host Unreachable Pattern
│  ├─ Error contains "chown failed" or "failed to look up user/group"?
│  │  └─ → Missing Prerequisite Resources Pattern
│  ├─ Error contains "Unable to start service" or "Job for service failed"?
│  │  └─ → Service Start Failure Pattern
│  ├─ Error contains "FAILED" with module name?
│  │  └─ → Module Execution Failure Pattern
│  ├─ Error contains "No such file"?
│  │  ├─ Course book references file?
│  │  │  └─ Check if lab script deploys it → Lab Script Bug
│  │  └─ Solution references file?
│  │     └─ → File Not Found Pattern
│  ├─ Error contains "undefined"?
│  │  └─ → Template/Variable Undefined Pattern
│  └─ Error contains "Syntax Error"?
│     └─ → Syntax Error Pattern
│
└─ No error but pedagogical issue?
   ├─ Solution approach different?
   │  └─ → Pedagogical Mismatch Pattern
   ├─ Instruction unclear?
   │  └─ → Course Book Quality Issue (P2)
   └─ Exercise too complex for objective?
      └─ → Complexity Mismatch Pattern
```

**Decision Process**:

1. **Check for Intentional Errors FIRST**
   - Read course book for troubleshooting language
   - Review exercise objectives
   - If intentional: Document, verify hints, assess quality
   - If not mentioned: Continue to bug diagnosis

2. **Test from Student Perspective**
   - Follow course book steps exactly
   - Use only /home/student/<exercise>/ files
   - Document where students get stuck
   - Classify by component (book/lab/file/solution)

3. **Apply Technical Patterns**
   - Match error messages to known patterns
   - Investigate root cause
   - Generate solution options

4. **Assess Pedagogical Quality**
   - Does solution match teaching?
   - Is complexity appropriate?
   - Are instructions clear?
   - Is student experience good?

**Priority Order**:
1. P0 (Blocker): Course book steps fail, students stuck
2. P1 (Critical): Solutions broken, major confusion
3. P2 (Minor): Pedagogical issues, clarity improvements

---

## Best Practices for Solution Recommendations

1. **Always provide multiple options** (Quick Fix, Proper Fix, Alternative)
2. **Include exact commands** with full paths
3. **Explain trade-offs** clearly
4. **Verify solutions** with test commands
5. **Consider impact** on students and course goals
6. **Document why** each approach works
7. **Prefer proper fixes** over workarounds for course materials

---

**Usage**: When QA test fails, match error pattern → follow investigation steps → present solution options → recommend best fix
