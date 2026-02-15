# Live Lab Testing Guide

This skill tests exercises in live lab environments using actual `lab` commands.

## Lab Command Workflow

Students interact with lab environments using the `lab` command. This is the official way to test exercises.

### Key Lab Commands

```bash
# Install a course (automatic from PyPI)
lab install <sku>

# List available courses
lab list

# Start an exercise
lab start <exercise-name>
# - Auto-installs course package if needed
# - Creates exercise directories
# - Sets up OpenShift resources
# - Copies exercise files

# Finish/cleanup an exercise
lab finish <exercise-name>
# - Removes OpenShift projects/resources
# - Deletes exercise files
# - Resets environment

# Grade a lab (Labs only)
lab grade <exercise-name>

# Check status
lab status [exercise-name]

# View logs
lab logs [exercise-name]
```

### Directory Structure Created by `lab start`

```
~/DO<COURSE-SKU>/
├── labs/
│   └── <exercise-name>/      # Exercise working directory
│       └── files...           # Exercise-specific files
└── solutions/
    └── <exercise-name>/       # Solution files
        ├── file1.yaml.sol
        ├── file2.sh.sol
        └── ...
```

**Example**: For OpenShift courses:
```
~/DO0022L/                     # Note: 0022L is the lesson code
├── labs/
│   └── accessing-clicreate/
└── solutions/
    └── accessing-clicreate/
```

### Testing Workflow

#### 1. **Prerequisites**
```bash
# SSH to workstation
ssh student@workstation

# Verify connectivity
ping utility.ocp4.example.com
oc get nodes  # (if kubeconfig exists)
```

#### 2. **Start Exercise**
```bash
cd ~  # MUST be in home directory
lab start <exercise-name>
```

**What happens:**
- Downloads and installs course package from PyPI (first time)
- Verifies cluster state
- Checks required systems are reachable
- Configures prerequisites (operators, storage, etc.)
- Creates OpenShift projects/namespaces
- Copies exercise files to ~/DO<SKU>/labs/<exercise-name>/
- Copies solution files to ~/DO<SKU>/solutions/<exercise-name>/

**Duration**: 1-10 minutes depending on setup requirements

#### 3. **Execute Exercise**
Follow EPUB instructions:
```bash
# Students follow step-by-step instructions from EPUB
# Example for accessing-clicreate:
cd ~/DO0022L/labs/accessing-clicreate
oc new-project myproject
oc create deployment myapp --image=registry.example.com/myapp:latest
oc get pods
```

#### 4. **Test Solutions**
```bash
# Copy solution files to exercise directory
cd ~/DO0022L/labs/<exercise-name>
cp ../solutions/<exercise-name>/*.sol .

# Remove .sol extension and apply
for file in *.sol; do
    mv "$file" "${file%.sol}"
done

# Run/apply solutions
oc apply -f manifest.yaml
ansible-navigator run playbook.yml -m stdout
```

#### 5. **Verify (Guided Exercises)**
Follow verification steps from EPUB or run verification playbooks:
```bash
# Option 1: Follow EPUB verification steps
oc get deployment myapp
oc get pods -l app=myapp

# Option 2: Run verification playbook (if provided)
ansible-navigator run verify.yml -m stdout
```

#### 6. **Grade (Labs Only)**
```bash
cd ~  # MUST be in home directory
lab grade <exercise-name>
```

**Expected output:**
```
Grading the student's work for <exercise-name>

 · Task description........................ PASS
 · Another check........................... PASS
 · Final verification...................... PASS

Overall result: PASS
```

#### 7. **Cleanup**
```bash
cd ~  # MUST be in home directory
lab finish <exercise-name>
```

**What happens:**
- Verifies connectivity to workstation/utility
- Deletes OpenShift projects/namespaces
- Removes PVCs, VMs, pods, etc.
- Runs Ansible cleanup playbooks
- Deletes ~/DO<SKU>/labs/<exercise-name>/
- Deletes ~/DO<SKU>/solutions/<exercise-name>/
- Resets environment to baseline

---

## Testing Strategy

### Two-Pass Testing

**PASS 1: Student Simulation**
- Execute EPUB steps exactly as documented
- Test on live systems using actual commands
- Validate each step produces expected results

**PASS 2: QA Validation**
- Test ALL solution files comprehensively
- For Labs: Run `lab grade <exercise>` with/without solution
- Validate cleanup completeness
- Test idempotency (start → finish → start)

### Grading Validation (Labs)

**Scenario 1: WITH Solution (Must PASS)**
```bash
lab start <exercise-name>
cd ~/DO<SKU>/labs/<exercise-name>

# Copy and apply solution
cp ../solutions/<exercise-name>/*.sol .
for f in *.sol; do mv "$f" "${f%.sol}"; done
oc apply -f manifest.yaml  # or ansible-navigator run playbook.yml -m stdout

# Grade MUST pass 100%
cd ~
lab grade <exercise-name>
# Expected: PASS (100/100)
```

**Scenario 2: WITHOUT Solution (Must FAIL)**
```bash
lab finish <exercise-name>
lab start <exercise-name>

# Do NOT apply solution
cd ~
lab grade <exercise-name>
# Expected: FAIL (0/100) with clear error messages
```

### Idempotency Testing

Validates students can practice repeatedly:

```bash
# Cycle 1
lab start <exercise-name>
# Capture system state
# Execute exercise
lab finish <exercise-name>

# Cycle 2
lab start <exercise-name>
# Capture system state again
# State MUST be identical to Cycle 1

# Cycle 3
# Repeat to verify consistency
```

**Common idempotency issues:**
- Incomplete cleanup in finish.yml
- Asymmetric operations (create on Host A, remove from Host B)
- Conditional artifacts missed by cleanup
- User/group/file/service remnants

---

## Implementation

### Live Lab Tester Module

**File:** `.skilldata/scripts/live_lab_tester.py`

**Key features:**
- SSH connection to workstation
- Executes actual `lab` commands
- Captures and validates output
- Compares system state for idempotency
- Tests grading with/without solutions

**Usage:**
```python
from live_lab_tester import LiveLabTester

tester = LiveLabTester(workstation="workstation")
result = tester.test_exercise_live(exercise)

# Internally runs:
# 1. ssh student@workstation "cd ~ && lab start <exercise>"
# 2. Execute EPUB steps
# 3. Test solutions
# 4. ssh student@workstation "cd ~ && lab grade <exercise>"
# 5. ssh student@workstation "cd ~ && lab finish <exercise>"
# 6. Verify cleanup
```

---

## Common Issues

### "No active course found"
**Cause:** lab command called without installed course
**Solution:** Run `lab start <exercise>` - it auto-installs

### "The Lab environment is not ready"
**Cause:** OpenShift cluster not accessible
**Solution:** Wait 10 minutes, check network connectivity

### "The OpenShift cluster is not ready"
**Cause:** Cluster API not responding
**Solution:** Wait 5 minutes, verify cluster state with `oc get nodes`

### "Must run from HOME directory"
**Cause:** lab script called from wrong directory
**Solution:** Always `cd ~` before running lab commands

---

## Best Practices

1. **Always use live environments** - Never simulate lab commands
2. **Always run from home directory** - `cd ~` before lab commands
3. **Test solutions in exercise directory** - Copy to working directory first
4. **Remove .sol extension** - Never run solutions directly from solutions/ dir
5. **Validate grading both ways** - With and without solution applied
6. **Test idempotency** - Multiple start/finish cycles
7. **Capture system state** - Before/after for comparison
8. **Follow EPUB exactly** - Test from student guide, not source files

---

## Architecture Integration

The live lab testing approach integrates with:
- **TC-PREREQ** - Validates SSH and environment readiness
- **TC-EXEC** - Pre-flight command syntax validation
- **TC-WORKFLOW** - Executes EPUB steps on live systems
- **TC-SOL** - Tests solution files on live systems
- **TC-GRADE** - Validates grading with actual lab grade command
- **TC-CLEAN** - Verifies cleanup using state comparison
- **TC-IDEM** - Multi-cycle testing for repeatability

All test categories use live lab commands, not simulations.
