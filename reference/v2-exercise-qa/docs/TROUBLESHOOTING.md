# Troubleshooting Guide

This guide covers common problems encountered during exercise QA testing and their solutions.

## Bug Severity Classification

### P0 - Blocker
Completely blocks testing or prevents exercise from working at all.

**Examples:**
- SSH connection to workstation failed
- `lab start` command fails completely
- YAML syntax errors preventing playbook parsing
- Host unreachable (DNS or network failure)

**Action:** Must fix immediately before any testing can proceed.

### P1 - Critical
Core functionality is broken; exercise cannot be completed correctly.

**Examples:**
- Solution playbook fails to execute
- Grading fails with correct solution applied
- Required Ansible collection missing
- Undefined variable in playbook
- Module execution failed

**Action:** Fix before release. These are blocking issues for students.

### P2 - High
Important issue but exercise may still be completable with workarounds.

**Examples:**
- SSH authentication issues to managed nodes
- EE image not available (but alternatives exist)
- Poor error messages in grading output
- Cleanup incomplete (artifacts remain)

**Action:** Should fix before release. May impact student experience.

### P3 - Low
Minor issues, cosmetic problems, or warnings.

**Examples:**
- Lab host not reachable (may not be needed for exercise)
- ansible-navigator.yml config file missing (defaults work)
- Registry connectivity issues in airgapped environment
- Naming convention violations

**Action:** Fix if time permits. Low impact on students.

## Common Problems and Solutions

### SSH Connection Issues

#### Problem: "SSH connection to workstation failed"
```
Cannot connect to workstation: workstation
```

**Solution:**
1. Verify workstation is running in your lab environment
2. Check SSH configuration:
   ```bash
   ssh student@workstation
   ```
3. Ensure SSH keys are configured:
   ```bash
   ssh-copy-id student@workstation
   ```
4. Check ~/.ssh/config:
   ```
   Host workstation
       HostName workstation.lab.example.com
       User student
       IdentityFile ~/.ssh/id_rsa
   ```

#### Problem: "SSH authentication failed"
```
Permission denied (publickey)
```

**Solution:**
1. Check SSH key permissions:
   ```bash
   chmod 600 ~/.ssh/id_rsa
   chmod 644 ~/.ssh/id_rsa.pub
   ```
2. Regenerate keys if corrupted:
   ```bash
   ssh-keygen -t rsa -b 4096
   ssh-copy-id student@workstation
   ```

### Ansible Collection Issues

#### Problem: "Missing Ansible Collection"
```
couldn't resolve module/action 'ansible.posix.firewalld'
```

**Solution:**
1. Quick install (immediate fix):
   ```bash
   ssh workstation "ansible-galaxy collection install ansible.posix"
   ```

2. Permanent fix (add to requirements.yml):
   ```yaml
   # requirements.yml
   collections:
     - name: ansible.posix
       version: ">=1.5.0"
   ```
   Then:
   ```bash
   ansible-galaxy collection install -r requirements.yml
   ```

### Variable Issues

#### Problem: "Undefined Variable"
```
AnsibleUndefinedVariable: 'my_variable' is undefined
```

**Solution:**
1. Define in playbook vars:
   ```yaml
   - name: Play name
     hosts: all
     vars:
       my_variable: value
   ```

2. Use default filter for optional variables:
   ```yaml
   "{{ my_variable | default('default_value') }}"
   ```

3. Define in vars file:
   ```bash
   echo "my_variable: value" >> vars.yml
   ```

### YAML Syntax Errors

#### Problem: "Syntax Error while loading YAML"
```
mapping values are not allowed here
```

**Solution:**
1. Check indentation (use 2 spaces, not tabs):
   ```bash
   yamllint playbook.yml
   ```

2. Common fixes:
   - Ensure consistent 2-space indentation
   - Add space after colons: `key: value`
   - Check quote matching
   - List items start with `- `

3. Validate syntax:
   ```bash
   ansible-playbook --syntax-check playbook.yml
   ```

### Lab Command Failures

#### Problem: "lab start failed"
```
Error starting lab
```

**Solution:**
1. Check lab status:
   ```bash
   lab status exercise-name
   ```

2. Reset lab environment:
   ```bash
   lab finish exercise-name
   lab start exercise-name
   ```

3. Check if OpenShift/VMs are running

#### Problem: "lab grade failed (false positive)"
```
Grading PASSED without solution
```

**Solution:**
The grading script may have logic errors allowing false positives.

1. Review grading script for correct validation
2. Ensure checks verify actual state, not just command success
3. Test both with and without solutions applied

### Execution Environment Issues

#### Problem: "ansible-navigator not found"
```
ansible-navigator not found on workstation
```

**Solution:**
```bash
pip install ansible-navigator
```

#### Problem: "No container runtime found"
```
No container runtime (podman/docker) found
```

**Solution:**
```bash
dnf install podman
```

#### Problem: "EE image not available"
```
Required EE image not found
```

**Solution:**
```bash
podman pull registry.redhat.io/ansible-automation-platform-24/ee-supported-rhel9
```

### Network Device Issues

#### Problem: "Connection timed out to network device"
```
SSH connection to cisco_ios device timed out after 10s
```

**Solution:**
Network devices often require longer timeouts. The QA tool automatically
applies timeout multipliers:

| Device Type | SSH Timeout | Command Timeout | Multiplier |
|-------------|-------------|-----------------|------------|
| Linux       | 10s         | 30s             | 1.0x       |
| Cisco IOS   | 20s         | 60s             | 2.0x       |
| Cisco NX-OS | 25s         | 60s             | 2.0x       |
| Juniper     | 30s         | 90s             | 2.5x       |
| Arista EOS  | 20s         | 60s             | 2.0x       |

For manual testing, increase timeouts in inventory:
```yaml
ansible_command_timeout: 60
ansible_connect_timeout: 30
```

### File Not Found Errors

#### Problem: "Could not find or access file"
```
Unable to retrieve file contents: /path/to/file
```

**Solution:**
1. Check if file exists:
   ```bash
   ls -la /path/to/file
   ```

2. Search for the file:
   ```bash
   find . -name "filename"
   ```

3. Common locations to check:
   - `files/` - Static files
   - `templates/` - Jinja2 templates
   - `vars/` - Variable files

4. Fix path in playbook (relative to playbook location)

## Error Pattern Reference

The QA tool automatically detects these error patterns and provides recommendations:

| Pattern | Title | Severity | Category |
|---------|-------|----------|----------|
| `couldn't resolve module/action` | Missing Ansible Collection | P1 | collection |
| `UNREACHABLE!` | Host Unreachable | P0 | connectivity |
| `Permission denied (publickey` | SSH Authentication Failed | P1 | connectivity |
| `No such file or directory` | File Not Found | P1 | file_system |
| `TemplateNotFound` | Template Not Found | P1 | file_system |
| `is undefined` | Undefined Variable | P1 | variable |
| `Syntax Error while loading YAML` | YAML Syntax Error | P0 | syntax |
| `TemplateSyntaxError` | Jinja2 Syntax Error | P1 | syntax |
| `FAILED! =>` | Module Execution Failed | P1 | module |
| `Permission denied` | Permission Denied | P1 | permission |
| `user does not exist` | User Not Found | P1 | user_group |
| `group does not exist` | Group Not Found | P1 | user_group |
| `Failed to start` | Service Failed | P1 | service |
| `timed out` | Network Device Timeout | P1 | network_device |
| `lab start.*failed` | Lab Start Failed | P0 | lab_command |

## Getting More Help

1. **Enable verbose output:**
   ```bash
   /exercise-qa AU0024L exercise-name 2>&1 | tee qa-output.log
   ```

2. **Run specific test categories:**
   ```bash
   /exercise-qa AU0024L --tests TC-PREREQ,TC-SOL
   ```

3. **Check AI diagnostics in report:**
   The generated report includes an "AI Diagnostics" section with
   pattern-matched recommendations for each bug.

4. **Manual debugging:**
   ```bash
   ssh workstation
   cd ~/git-repos/active/COURSE/labs/exercise-name
   ansible-playbook -vvv playbook.yml
   ```
