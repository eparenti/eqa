# Technology-Specific Testing Guide

**Purpose:** How Exercise QA adapts to different course technologies.

---

## Auto-Detection

Exercise QA automatically detects course technology and adapts:

1. **From course code** - AU* = Ansible, DO* = OpenShift, RH* = RHEL
2. **From grading script** - Imports and module usage indicate technology
3. **From solution files** - File extensions (`.yml.sol`, `.yaml`, `.sh`, `.conf`)
4. **From EPUB** - Tools mentioned in instructions

---

## Ansible Courses (AU*)

**Examples:** AU0022L, <ANSIBLE-COURSE>

### Solution Files
- Format: `*.yml.sol` (Ansible playbooks)
- Location: `materials/labs/<exercise>/solutions/`

### Execution
```bash
cd ~/exercise-directory
cp solutions/playbook.yml.sol playbook.yml
ansible-navigator run playbook.yml -m stdout
```

### Verification (GE)
**Option 1:** Verify playbooks
```bash
ansible-navigator run verify_service.yml -m stdout
ansible-navigator run verify_config.yml -m stdout
```

**Option 2:** EPUB steps
- Check service status
- Verify file content
- Test endpoints

### Grading (Labs)
```bash
lab grade <exercise-name>
# Runs Python grading script that executes Ansible playbooks
```

### Common Issues
- Missing collections (`ansible.posix`, `community.*`)
- YAML syntax errors
- Inventory configuration
- Privilege escalation (`become: true`)

---

## OpenShift/Kubernetes (DO*)


### Solution Files
- Format: `*.yaml.sol` (Kubernetes manifests with .sol extension)
- Location: `materials/labs/<exercise>/solutions/`

### Execution
```bash
# Copy solution files to exercise directory
cp solutions/deployment.yaml.sol deployment.yaml
cp solutions/service.yaml.sol service.yaml
oc apply -f deployment.yaml
oc apply -f service.yaml
# Or via web console per EPUB instructions
```

### Verification (GE)
**Option 1:** CLI commands
```bash
oc get pods -n namespace
oc get svc -n namespace
oc describe deployment/myapp
```

**Option 2:** HTTP checks
```bash
curl http://route-url
```

**Option 3:** Web console
- Navigate to Developer/Administrator view
- Verify resources exist and status is Running

### Grading (Labs)
```bash
lab grade <exercise-name>
# Runs Python grading script that uses OpenShift/Kubernetes client libraries
```

### Common Issues
- Resource not found (wrong namespace, name typo)
- RBAC permissions (user can't create resource)
- Image pull errors (wrong image name/tag)
- Routes not accessible (DNS, firewall)

---

## RHEL System Administration (RH*)


### Solution Files
- Format: Scripts (`.sh.sol`), configs (`.conf.sol`), various with `.sol` extension
- Location: May or may not have `materials/` directory

### Execution
**Via SSH:**
```bash
# Copy solution script and remove .sol extension
cp solutions/script.sh.sol script.sh
ssh servera "bash ~/exercise-directory/script.sh"
ssh servera "sudo systemctl enable httpd"
ssh servera "sudo firewall-cmd --add-service=http --permanent"
```

**Via configuration:**
```bash
# Copy solution config and remove .sol extension
cp solutions/myapp.conf.sol myapp.conf
scp myapp.conf servera:/etc/myapp/config.conf
ssh servera "sudo systemctl restart myapp"
```

### Verification (GE)
**Service status:**
```bash
ssh servera "systemctl status httpd"
ssh servera "systemctl is-enabled httpd"
```

**File content:**
```bash
ssh servera "cat /etc/myapp.conf"
ssh servera "grep '^Listen 8080' /etc/httpd/conf/httpd.conf"
```

**System state:**
```bash
ssh servera "firewall-cmd --list-services"
ssh servera "getenforce"  # SELinux
ssh servera "id username"
```

### Grading (Labs)
```bash
lab grade <exercise-name>
# Runs Python grading script that SSHs to hosts and checks state
```

### Common Issues
- Service not found (package not installed)
- Permission denied (need sudo)
- SELinux context issues
- Firewall blocking

---

## Satellite Courses


### Solution Files
- Format: `hammer` CLI commands, API calls
- Location: Often in EPUB, not separate files

### Execution
```bash
hammer content-view create --name "myCV" --organization "MyOrg"
hammer content-view publish --name "myCV" --organization "MyOrg"
```

### Verification (GE)
```bash
hammer content-view list --organization "MyOrg"
hammer content-view info --name "myCV" --organization "MyOrg"
```

### Grading (Labs)
```bash
lab grade <exercise-name>
# Uses Satellite API to verify configuration
```

### Common Issues
- hammer CLI not configured
- Authentication failures
- Organization/location context wrong
- API rate limits

---

## Mixed Technology Courses

Some courses use multiple technologies:
- Ansible + OpenShift (<NETWORK-COURSE>)
- RHEL + Satellite courses
- RHEL + Ansible courses

**Exercise QA adapts per exercise:**
- Detects primary technology from solution files
- Uses appropriate tools for that exercise
- May use multiple verification methods

---

## Testing Approach by Technology

### Ansible
1. **Parse EPUB** - Extract playbook creation steps
2. **Execute steps** - Using `ansible-navigator`
3. **Test solution** - Copy `*.sol` to exercise directory, rename to `.yml`, run with `ansible-navigator`
4. **Verify** - Run `verify_*.yml` or check EPUB verification
5. **For Labs** - `lab grade <exercise-name>`

### OpenShift
1. **Parse EPUB** - Extract `oc` commands or web console steps
2. **Execute steps** - Via `oc` CLI or document web console actions
3. **Test solution** - Copy `*.yaml.sol` to exercise directory, rename to `.yaml`, run with `oc apply`
4. **Verify** - `oc get/describe`, HTTP checks
5. **For Labs** - `lab grade <exercise-name>`

### RHEL
1. **Parse EPUB** - Extract SSH commands or configuration changes
2. **Execute steps** - `ssh <host> "<command>"`
3. **Test solution** - Copy `*.sol` to exercise directory, rename (`.sh`, `.conf`, etc.), run via SSH
4. **Verify** - Check service status, file content, system state
5. **For Labs** - `lab grade <exercise-name>`

---

## How to Add New Technology Support

Exercise QA is designed to adapt automatically. For new technologies:

1. **No code changes needed** - Skill follows EPUB
2. **Solution testing** - Uses tools specified in EPUB
3. **Verification** - Follows verification steps from EPUB
4. **Grading** - Uses standard `lab grade` (works for all)

**Example:** New Windows course
- EPUB says: `ssh winserver "powershell.exe Get-Service"`
- Skill executes that command
- No special Windows code needed

---

## Summary Table

| Technology | Solution Format | Execution Tool | Verification | Grading |
|------------|----------------|----------------|--------------|---------|
| **Ansible** | `*.yml.sol` | ansible-navigator | verify_*.yml or EPUB | lab grade <exercise-name> |
| **OpenShift** | `*.yaml.sol` | oc, kubectl | oc get/describe, HTTP | lab grade <exercise-name> |
| **RHEL** | `*.sh.sol`, `*.conf.sol` | ssh, bash | systemctl, cat, grep | lab grade <exercise-name> |
| **Satellite** | hammer commands | hammer | hammer list/info | lab grade <exercise-name> |
| **Other** | EPUB-specified | EPUB-specified | EPUB-specified | lab grade <exercise-name> |

---

**Key Principles:**
- Exercise QA follows the student guide (EPUB). Whatever tools students use, QA uses the same tools.
- **Solution files must be copied to exercise directory and `.sol` extension removed** before running (e.g., `cp solutions/playbook.yml.sol playbook.yml`).
