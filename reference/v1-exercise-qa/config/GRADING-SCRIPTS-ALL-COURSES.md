# Grading Scripts: Universal Pattern Across All Courses

**CRITICAL**: ALL Red Hat Training courses use the same grading script pattern, regardless of technology.

---

## Universal Grading Script Pattern

**ALL courses** (Ansible, OpenShift, RHEL, Satellite, etc.) have Python grading scripts:

```
classroom/grading/src/<course-code>/<exercise-name>.py
```

**Structure**:
```python
class ExerciseName(SomeBaseClass):
    __LAB__ = "exercise-name"

    def start(self):
        """Setup environment for exercise"""
        # Create users, configure systems, deploy resources, etc.

    def finish(self):
        """Cleanup environment after exercise"""
        # Remove resources, reset configs, clean up

    # For LABS ONLY:
    def grade(self):
        """Automated grading checks"""
        # Verify student completed all requirements
        # Return PASS/FAIL for each check
```

---

## Detecting Exercise Type

**Guided Exercise (GE)**:
- Has `start()` and `finish()` methods
- **NO** `grade()` method
- Students verify manually using instructions or verify_*.yml playbooks

**Lab**:
- Has `start()`, `finish()`, **AND** `grade()` methods
- Students verify using `lab grade <exercise-name>` command
- Automated grading checks all requirements

**Detection method**: Check for presence of `grade()` method in grading script.

---

## Grading Script Examples by Technology

### Ansible Course

**File**: `classroom/grading/src/<lesson-code>/<exercise-name>.py`

```python
class RolesReview(GuidedExercise):
    __LAB__ = "<exercise-name>"

    def start(self):
        # Setup: Create directories, copy files
        pass

    def finish(self):
        # Cleanup: Remove directories, reset configs
        pass

    def grade(self):
        # Grading checks:
        # - Check ansible.cfg configured correctly
        # - Run solution playbook
        # - Verify services running
        # - Check firewall rules
        # - Verify web content accessible
        ansible.run_playbook_step(
            self,
            "<exercise-name>/verify-service.yml",
            step_message="Ensuring httpd service is started",
            grading=True,
        )
```

**Test command**: `lab grade <exercise-name>`

---

### OpenShift Course

**File**: `classroom/grading/src/<lesson-code>/<exercise-name>.py`

```python
from kubernetes.client.exceptions import ApiException
from ocp.utils import OpenShift

class ExampleReview(OpenShift):
    __LAB__ = "<exercise-name>"

    def start(self):
        # Setup: Create namespaces, deploy resources
        pass

    def finish(self):
        # Cleanup: Delete namespaces, remove resources
        pass

    def grade(self):
        # Grading checks:
        # - Verify VMs exist in correct namespaces
        # - Check VM specs (CPU, memory)
        # - Verify VMs are running
        # - Check networking configuration
        with Step("Verify VM exists", True, False):
            vm = self.kubernetes_api.read_namespaced_custom_object(
                group="kubevirt.io",
                version="v1",
                namespace="development-db",
                plural="virtualmachines",
                name="mariadb-vm"
            )
```

**Test command**: `lab grade <exercise-name>`

---

### RHEL Course

**File**: `classroom/grading/src/<lesson-code>/<exercise-name>.py`

```python
from labs.ui import Step
from labs.activities import Lab

class ExampleReview(Lab):
    __LAB__ = "<exercise-name>"

    def start(self):
        # Setup: Install packages, configure systems
        courselib.common_start(self.__LAB__)

    def finish(self):
        # Cleanup: Remove packages, reset configs
        courselib.remove_packages("serverb", "aide")
        courselib.clean_audit_rules("serverb")
        courselib.common_finish(self.__LAB__)

    def grade(self):
        # Grading checks:
        # - Check AIDE package installed
        # - Verify AIDE configuration
        # - Check SSH configuration
        courselib.check_installed_package("serverb", "aide")

        with Step("Check AIDE configuration", True, False):
            courselib.ssh_run_command(
                "serverb",
                "grep '/etc/ssh.*CONTENT_EX' /etc/aide.conf",
            )

        with Step("Check SSH config", True, False):
            courselib.ssh_run_command(
                "serverb",
                "grep 'PasswordAuthentication no' /etc/ssh/sshd_config",
            )
```

**Test command**: `lab grade <exercise-name>`

---

## QA Testing Approach for Labs

**For ALL Labs (Regardless of Technology)**:

### Pass 1 - Student Execution (from EPUB)
1. `lab start <exercise-name>`
2. Follow steps in EPUB/student guide
3. Complete all requirements

### Pass 2 - Solution Validation
4. Test solution files from lesson repository
5. Verify solutions produce correct end state

### Pass 3 - Automated Grading
6. **Run `lab grade <exercise-name>`** ← CRITICAL
7. Verify all grading checks pass (100%)
8. Check for false positives/negatives

### Pass 4 - Cleanup
9. `lab finish <exercise-name>`
10. Verify environment resets properly

---

## Testing Grading Scripts

### Test Scenario 1: Solution Applied (Should PASS)

```bash
# 1. Start lab
ssh workstation "lab start <exercise-name>"

# 2. Apply solution files
# - For Ansible: ansible-navigator run solutions/*.sol
# - For OpenShift: oc apply -f solutions/*.yaml
# - For RHEL: Copy configs, run commands from solution

# 3. Run grading
ssh workstation "lab grade <exercise-name>"

# Expected: ✅ All checks PASS
```

### Test Scenario 2: No Solution (Should FAIL)

```bash
# 1. Start lab
ssh workstation "lab start <exercise-name>"

# 2. DO NOT apply solutions

# 3. Run grading
ssh workstation "lab grade <exercise-name>"

# Expected: ❌ Grading checks FAIL appropriately
```

### Test Scenario 3: Partial Solution (Should FAIL Gracefully)

```bash
# 1. Start lab
ssh workstation "lab start <exercise-name>"

# 2. Complete only some steps

# 3. Run grading
ssh workstation "lab grade <exercise-name>"

# Expected: Some ✅ PASS, some ❌ FAIL with clear messages
```

---

## Grading Script Validation Checklist

**For ALL Technologies**:

✅ **Accuracy**
- [ ] Tests actual lab requirements (not unrelated items)
- [ ] Each check maps to a specific lab objective
- [ ] No redundant checks

✅ **Reliability**
- [ ] No false positives (passes when shouldn't)
- [ ] No false negatives (fails when shouldn't)
- [ ] Idempotent (same result on repeated runs)

✅ **Clarity**
- [ ] Error messages clearly indicate what's wrong
- [ ] Success messages confirm what's correct
- [ ] Step messages match lab instructions

✅ **Coverage**
- [ ] All major lab objectives tested
- [ ] Critical configurations verified
- [ ] End-state validation included

---

## Summary

**Key Takeaway**: Grading scripts work the SAME WAY across ALL course types.

| Course Type | Grading Command | Technology Used in grade() |
|-------------|----------------|----------------------------|
| **Ansible** | `lab grade <exercise-name>` | Ansible playbooks via ansible module |
| **OpenShift** | `lab grade <exercise-name>` | Kubernetes API via kubernetes client |
| **RHEL** | `lab grade <exercise-name>` | SSH commands via courselib |
| **Satellite** | `lab grade <exercise-name>` | Satellite API via hammer CLI |

**What changes**: Technology/tools used inside `grade()` method
**What stays the same**: `lab grade <exercise-name>` command, start/finish/grade pattern

---

## For QA Engineers

**When testing LABS (any course type)**:

1. ✅ ALWAYS run `lab grade <exercise-name>`
2. ✅ Test with solution (should PASS)
3. ✅ Test without solution (should FAIL)
4. ✅ Test with partial solution (should FAIL gracefully)
5. ✅ Verify grading messages are clear
6. ✅ Check for false positives/negatives

**This applies to ALL courses** - Ansible, OpenShift, RHEL, Satellite, etc.
