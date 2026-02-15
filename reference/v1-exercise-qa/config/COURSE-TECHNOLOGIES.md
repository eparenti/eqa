# Red Hat Training Course Technologies

**The QA skill works for ALL Red Hat Training courses**, regardless of technology.

**CRITICAL**: All testing is **fully automated** and runs on **live lab environments**:
- ✅ Zero manual execution - Commands auto-executed via SSH/CLI
- ✅ Live systems only - Real VMs, clusters, and machines (RHEL, Windows, etc.)
- ✅ Real validation - Checks actual system state, not mocked data
- ✅ Human involvement - Only to confirm "Is lab ready?" at start

---

## Supported Course Types

### Ansible Automation Courses (AU*)

**Technology**: Ansible, ansible-navigator, playbooks, roles, collections

**Solution Testing**:
- Run playbooks: `ansible-navigator run solutions/playbook.yml.sol -m stdout`
- Use execution environment containers
- Verify with verify_*.yml playbooks or `lab grade`

**Grading Scripts**: Python scripts using Ansible modules

---

### OpenShift/Kubernetes Courses (DO*)

**Technology**: OpenShift, Kubernetes, `oc` CLI, web console, containers, VMs

**Solution Testing**:
- Apply resources: `oc apply -f solutions/manifest.yaml`
- Create resources via web console
- Verify with `oc get`, `oc describe`
- Test applications via HTTP/SSH

**Grading Scripts**: Python scripts using Kubernetes/OpenShift client libraries

---

### RHEL System Administration Courses (RH*)

**Technology**: Linux system administration, security tools, configuration files

**Solution Testing**:
- Execute commands via SSH on lab machines
- Verify configuration files
- Check service status
- Validate system state

**Grading Scripts**: Python scripts using SSH to run commands on lab machines

---

### Red Hat Satellite Courses

**Technology**: Satellite, content management, system lifecycle

**Solution Testing**:
- Use Satellite web UI
- Execute hammer CLI commands
- Verify content views, subscriptions

**Grading Scripts**: Python scripts using Satellite API

---

### Other Technologies

The QA skill adapts to any course technology because it follows the same pattern:
1. **Prerequisites** - Environment ready?
2. **Instructions** - Clear and complete?
3. **Execution** - Steps work?
4. **Solutions** - Solution files work?
5. **Grading/Verification** - Automated checks pass?
6. **Cleanup** - Environment resets?

---

## Common Patterns Across All Courses

### Exercise Structure

```
course-repo/
├── classroom/grading/src/<course-code>/
│   ├── <exercise-name>.py      # Grading script
│   ├── ansible/<exercise-name>/ # Setup/grade playbooks (if applicable)
│   └── materials/
│       └── labs/<exercise-name>/ # Exercise materials (if applicable)
└── content/<chapter-keyword>/
    ├── ge.adoc                 # Guided exercise
    └── lab.adoc                # Lab
```

### Grading Script Pattern

**All courses** use Python grading scripts with:
- `start()` - Setup environment
- `finish()` - Cleanup environment
- `grade()` - Automated grading (Labs only)

**Detection**: Check for `grade()` method
- Has `grade()` → Lab (automated grading)
- No `grade()` → Guided Exercise (manual verification)

### Testing Approach by Course Type

| Course Type | Solution Execution | Verification Method |
|-------------|-------------------|---------------------|
| **Ansible** | `ansible-navigator run *.yml.sol` | verify_*.yml or `lab grade` |
| **OpenShift** | `oc apply` or web console | `oc get/describe` or `lab grade` |
| **RHEL Admin** | SSH commands, edit configs | Check configs, services, `lab grade` |
| **Satellite** | Hammer CLI, web UI | API calls, `lab grade` |

---

## Fully Automated QA Testing Process (Technology-Agnostic)

### For ALL Guided Exercises (Fully Automated on Live Systems):

**PASS 1 - Automated Student Simulation**:
1. **TC-PREREQ**: Auto-validates environment (packages, SSH access, tools)
2. **TC-INSTRUCT**: Auto-checks instructions complete and clear
3. **TC-EXEC**: Pre-flight command syntax validation (safety checks)
4. **TC-WORKFLOW**: **Auto-executes steps from EPUB** on live systems via SSH
5. **TC-SOL**: **Auto-tests all solution files** on live environment
6. **TC-VERIFY**: **Auto-runs verification** (varies by technology, on live systems)
6. **TC-CLEAN**: **Auto-verifies cleanup** with `lab finish`

**Human involvement**: Confirm "Is lab ready?" = yes. Everything else automated.

### For ALL Labs (Fully Automated on Live Systems):

**PASS 1 - Automated Lab Execution**:
1. **TC-PREREQ**: Auto-validates environment ready
2. **TC-INSTRUCT**: Auto-checks instructions provide enough guidance
3. **TC-EXEC**: Pre-flight command syntax validation (safety checks)
4. **TC-WORKFLOW**: **Auto-completes lab requirements** by executing EPUB steps

**PASS 2 - Automated Solution Validation**:
4. **TC-SOL**: **Auto-tests all solution files** on live systems

**PASS 3 - Automated Grading**:
5. **TC-GRADE**: **Auto-runs** `lab grade <exercise-name>` on workstation
6. **Auto-verifies** all grading checks pass (100%) against live system state

**Human involvement**: Confirm "Is lab ready?" = yes. Everything else automated.

---

## Technology-Specific Examples (Fully Automated)

### Ansible Course - Fully Automated

```bash
/qa <lesson-code> <exercise-name>

# AUTOMATED tests on live lab environment:
# - Auto-parses EPUB steps and executes on managed hosts
# - Auto-runs: ansible-navigator run solutions/playbook.yml.sol -m stdout
# - Auto-runs: ansible-navigator run verify_playbook.yml -m stdout (on live managed nodes)
#
# Human involvement: Confirm "Is lab ready?" = yes. Done.
```

### OpenShift Course - Fully Automated

```bash
/qa <lesson-code> <exercise-name>

# AUTOMATED tests on live OpenShift cluster:
# - Auto-parses EPUB steps and executes oc commands
# - Auto-runs: oc apply -f solutions/manifest.yaml (on live cluster)
# - Auto-validates: oc get resources -n namespace (checks live resource state)
# - Auto-runs: lab grade <exercise-name> (on workstation, validates live cluster)
#
# Human involvement: Confirm "Is lab ready?" = yes. Done.
```

### RHEL Course - Fully Automated

```bash
/qa <lesson-code> <exercise-name>

# AUTOMATED tests on live lab environment:
# - Auto-parses EPUB steps and executes via SSH on managed hosts
# - Auto-runs configuration commands (on live machines)
# - Auto-validates configuration files and system state (checks live config)
# - Auto-runs: lab grade <exercise-name> (validates live system state)
#
# Note: Lab environments may include RHEL, Windows, or other operating systems.
# Human involvement: Confirm "Is lab ready?" = yes. Done.
```

---

## Adapting QA Testing to Your Course

**The QA skill automatically adapts** by:

1. Reading the grading script to detect exercise type
2. Looking for solution files (*.sol, *.yaml, scripts, configs)
3. Detecting what verification method to use:
   - Ansible: verify_*.yml playbooks
   - OpenShift: `oc get/describe`
   - RHEL: config file checks, service status
4. Running `lab grade` for Labs (all technologies)

**You don't need to configure anything** - the QA skill figures it out from:
- Course code (AU*, DO*, RH*)
- Grading script structure
- Solution file types
- Available verification methods

---

## Summary

**Key Point**: The QA skill is **technology-agnostic**. It works for:
- Ansible courses (playbooks, roles)
- OpenShift courses (containers, VMs, Kubernetes)
- RHEL courses (system admin, security)
- Any Red Hat Training course

**How it works**: Tests the **process**, not the **technology**:
1. Prerequisites ready?
2. Instructions clear?
3. Steps work?
4. Solutions work?
5. Grading passes?
6. Cleanup works?

This pattern applies to ALL courses, regardless of technology stack.
