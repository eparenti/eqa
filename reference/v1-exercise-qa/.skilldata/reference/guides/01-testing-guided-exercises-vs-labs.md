# Quick Reference: Guided Exercise vs Lab Testing

## Summary Table

| Aspect | Guided Exercise (GE) | Lab |
|--------|---------------------|-----|
| **Purpose** | Step-by-step learning | Performance-based assessment |
| **Student Guidance** | Detailed instructions | High-level requirements |
| **Grading Script** | `start()` + `finish()` only | `start()` + `finish()` + **`grade()`** |
| **Validation** | Manual (verify_*.yml playbooks) | **Automated (`lab grade`)** |
| **Test Passes** | 2-pass (Exercise + Solution) | **3-pass (Execution + Solution + Grading)** |
| **Test Categories** | TC-PREREQ, TC-INSTRUCT, TC-EXEC, TC-SOL, **TC-VERIFY**, TC-CLEAN | TC-PREREQ, TC-INSTRUCT, TC-EXEC, TC-SOL, **TC-GRADE**, TC-CLEAN |
| **Examples** | <exercise-name>, roles-collections | <exercise-name>, develop-review |

---

## Detection Method

```bash
# Check grading script
cat classroom/grading/src/au0025l/<exercise-name>.py | grep "def grade"
# No output → Guided Exercise

cat classroom/grading/src/au0025l/<exercise-name>.py | grep "def grade"
# Output found → Lab
```

---

## Testing Workflow Comparison

### Guided Exercise (GE)

```
1. lab start <exercise-name>
   ↓
2. Execute steps 1-9 from ge.adoc (manual)
   ↓
3. Test solutions/myvhost.yml.sol
   ↓
4. Run verify_srv.yml
   Run verify_conf.yml
   Run verify_cont.yml
   ↓
5. lab finish <exercise-name>
   ↓
RESULT: Pass/Fail based on verify playbooks
```

### Lab

```
1. lab start <exercise-name>
   ↓
2. Complete lab requirements (steps 1-11)
   ↓
3. Test solutions/web_dev_server.yml.sol
   ↓
4. ⭐ lab grade <exercise-name> ⭐
   ↓
5. Verify all grading checks pass
   ↓
6. Test without solution (should fail)
   ↓
7. lab finish <exercise-name>
   ↓
RESULT: Pass/Fail based on automated grading
```

---

## Critical Testing Differences

### Guided Exercise
✅ **Must verify**:
- All verify_*.yml playbooks run successfully
- Solutions match expected output in instructions
- Step-by-step execution produces documented results

❌ **Do NOT need**:
- Automated grading script
- Grade without solution scenario

---

### Lab
✅ **Must verify**:
- `lab grade` passes 100% with solution applied
- `lab grade` fails appropriately WITHOUT solution
- Grading checks map to actual lab requirements
- No false positives (passes incorrectly)
- No false negatives (fails incorrectly)

✅ **Grading Script Validation**:
```bash
# Scenario 1: WITH solution (should PASS)
ssh workstation "cd ~/<exercise-name> && \
  ansible-navigator run solutions/web_dev_server.yml.sol -m stdout"
ssh workstation "lab grade <exercise-name>"
# Expected: ✅ All checks PASS

# Scenario 2: WITHOUT solution (should FAIL)
ssh workstation "lab finish <exercise-name> && lab start <exercise-name>"
ssh workstation "lab grade <exercise-name>"
# Expected: ❌ Checks FAIL with clear messages

# Scenario 3: PARTIAL completion (should FAIL gracefully)
ssh workstation "cd ~/<exercise-name> && \
  ansible-galaxy collection install ..."
ssh workstation "lab grade <exercise-name>"
# Expected: ⚠️ Some PASS, some FAIL
```

---

## Bug Severity - Lab Specific

### P0 Blocker (Lab)
- ❌ Grading script fails when solution is correct
- ❌ Grading script doesn't execute at all
- ❌ Lab cannot be completed due to broken prerequisites

### P1 Critical (Lab)
- ❌ Grading script passes when solution is wrong (false positive)
- ❌ Grading check doesn't test the actual requirement
- ❌ Grading messages are misleading

### P2 High (Lab)
- ⚠️ Grading messages could be clearer
- ⚠️ Grading check tests requirement but in wrong way

---

## QA Checklist

### For Guided Exercises
- [ ] All verify_*.yml playbooks exist in ansible/<exercise-name>/
- [ ] Each verify playbook tests specific learning objective
- [ ] Solutions produce output matching instructions
- [ ] Instructions include expected outputs
- [ ] Step-by-step execution is clear and unambiguous

### For Labs
- [ ] `lab grade <exercise-name>` command exists
- [ ] Grading script has all 3 methods: start(), grade(), finish()
- [ ] All grading checks pass with solution applied
- [ ] All grading checks fail without solution
- [ ] Partial completion fails gracefully
- [ ] Each grading check maps to lab requirement
- [ ] Grading messages are clear and actionable
- [ ] No false positives detected
- [ ] No false negatives detected
- [ ] Grading is idempotent (consistent results)

---

## Example Test Reports

### GE Test Report
```
Exercise: <exercise-name> (Guided Exercise)
✅ TC-PREREQ-01: Environment ready
✅ TC-INSTRUCT-01: 9 steps documented
✅ TC-EXEC-01: All steps executable
✅ TC-SOL-01: myvhost.yml.sol works
✅ TC-VERIFY-01: verify_srv.yml passes
✅ TC-VERIFY-02: verify_conf.yml passes
✅ TC-VERIFY-03: verify_cont.yml passes
✅ TC-CLEAN-01: Cleanup successful

Result: 8/8 PASS (100%)
Status: ✅ READY FOR RELEASE
```

### Lab Test Report
```
Exercise: <exercise-name> (Lab)
✅ TC-PREREQ-01: Environment ready
✅ TC-INSTRUCT-01: Requirements clear
✅ TC-EXEC-01: Lab completable
✅ TC-SOL-01: web_dev_server.yml.sol works
✅ TC-GRADE-01: lab grade passes WITH solution
✅ TC-GRADE-02: httpd service check - PASS
✅ TC-GRADE-03: firewalld service check - PASS
✅ TC-GRADE-04: Web content check - PASS
✅ TC-GRADE-05: User jdoe check - PASS
✅ TC-GRADE-06: User jdoe2 check - PASS
❌ TC-GRADE-07: lab grade PASSES without solution (FALSE POSITIVE!)
✅ TC-CLEAN-01: Cleanup successful

Result: 10/11 PASS (91%)
Status: ❌ BLOCKED - Fix grading script
Bug: BUG-001 (P0): Grading passes without completing lab
```

---

## Key Takeaways

### Guided Exercises
- **Testing Focus**: Manual step execution + verify playbooks
- **Success Criteria**: All steps work, verify playbooks pass
- **Main Risk**: Instructions unclear or verify playbooks incomplete

### Labs
- **Testing Focus**: Automated grading validation
- **Success Criteria**: Grading script accurately validates all requirements
- **Main Risk**: False positives/negatives in grading script

### Both
- **Common Testing**: Prerequisites, cleanup, solution files
- **Quality Standard**: 100% pass rate required for release
- **Test Location**: Lesson repo materials directory
- **Execution**: ansible-navigator (not ansible-playbook)

---

**Remember**: The key difference is **how correctness is validated**:
- GE: Manual verification via verify playbooks
- Lab: **Automated grading via `lab grade` command**
