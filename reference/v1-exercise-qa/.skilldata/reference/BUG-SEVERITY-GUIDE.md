# Bug Severity Classification Guide

**Purpose:** Classify bugs consistently for Red Hat Training course exercises.

---

## Severity Levels

### P0 (Blocker) - Exercise Unusable

Students **cannot complete** the exercise.

**Criteria:**
- Commands fail
- Prerequisites missing
- Environment broken
- `lab start` fails

**Examples:**
- Missing package/collection
- SSH connectivity fails
- Command in EPUB returns error
- Required file doesn't exist

**Action:** STOP testing, report immediately

---

### P1 (Critical) - Validation Broken

Exercise works but **cannot verify** success or **breaks on repeat**.

**Criteria:**
- Incomplete cleanup (idempotency broken)
- Grading fails incorrectly
- Verification fails incorrectly
- Solution files don't work

**Examples:**
- `lab finish` doesn't remove all artifacts
- `lab grade` passes when it shouldn't (false positive)
- `lab grade` fails when it shouldn't (false negative)
- Verification playbook/script fails on correct solution
- Solution file has errors

**Action:** Continue testing, MUST FIX before release

**Why P1:** Students need to:
- Practice repeatedly (idempotency)
- Verify their work (validation)
- Use solutions as reference

---

### P2 (High) - Quality Issues

Exercise works, validation works, but **student experience** suffers.

**Criteria:**
- Instructions unclear
- Missing documentation
- Confusing messages
- Inconsistent style

**Examples:**
- Step says "configure the service" (which service?)
- Expected output not shown in EPUB
- Error message doesn't explain what's wrong
- Inconsistent terminology

**Action:** Document, SHOULD FIX

**Why P2:** Affects learning but not functionality

---

### P3 (Low) - Polish

Minor cosmetic issues, **no functional** impact.

**Criteria:**
- Typos
- Style inconsistencies
- Optional improvements

**Examples:**
- Typo in comment
- Variable name could be clearer
- Formatting inconsistency

**Action:** Optional fix

**Why P3:** Nice to have, not required

---

## Decision Tree

```
Can student complete exercise?
├─ NO → P0 (Exercise broken)
└─ YES → Can student verify correctness?
    ├─ NO → P1 (Validation broken)
    └─ YES → Can student practice repeatedly?
        ├─ NO → P1 (Idempotency broken)
        └─ YES → Is student experience good?
            ├─ NO → P2 (Quality issue)
            └─ YES → Any minor issues?
                ├─ NO → No bug!
                └─ YES → P3 (Polish)
```

---

## Special Cases

### Idempotency Issues

**Always P1 (Critical):**
- `lab finish` doesn't remove all artifacts
- Second run behaves differently than first
- Environment accumulates state

**Why:** Students MUST be able to practice repeatedly.

### Grading Issues (Labs)

**False Positive → P1:**
- Grade passes when student didn't meet requirements
- Students think they're done when they're not

**False Negative → P1:**
- Grade fails when student met requirements
- Correct work marked wrong

**Unclear Messages → P2:**
- Grade fails but message doesn't explain why
- Student doesn't know what to fix

---

## Examples from Real Testing

### Example 1: Missing Collection (P0)

```
Error: couldn't resolve module 'ansible.posix.firewalld'
Impact: Students cannot run playbook
Classification: P0
Reason: Exercise unusable
```

### Example 2: Incomplete Cleanup (P1)

```
Issue: lab finish doesn't remove mary/nick from serverb
Impact: Second run starts with artifacts present
Classification: P1
Reason: Idempotency broken, students can't practice repeatedly
```

### Example 3: Unclear Instruction (P2)

```
Issue: Step says "configure the web server" without specifying how
Impact: Students confused, waste time
Classification: P2
Reason: Exercise completable but experience poor
```

### Example 4: Typo in Comment (P3)

```
Issue: Comment says "teh user" instead of "the user"
Impact: None
Classification: P3
Reason: Cosmetic only
```

---

## Bug Report Template

```markdown
### P{0-3}-00{N}: [Short Title]

**Severity:** P{0-3} ({Blocker|Critical|High|Low})
**Impact:** [One sentence describing student impact]

**Issue:**
[Description of what's wrong]

**Evidence:**
```
[Command output or error message]
```

**Fix:**
```
[Exact code/commands to fix]
```

**Verification:**
1. [Step to test fix]
2. [Expected result]
```

---

## Summary Table

| Severity | Student Can Complete? | Student Can Verify? | Can Practice Repeatedly? | Action |
|----------|----------------------|---------------------|-------------------------|--------|
| **P0** | ❌ NO | - | - | STOP, fix now |
| **P1** | ✅ YES | ❌ NO or Can't Repeat | - | MUST FIX before release |
| **P2** | ✅ YES | ✅ YES | ✅ YES (but poor UX) | SHOULD FIX |
| **P3** | ✅ YES | ✅ YES | ✅ YES (minor issue) | OPTIONAL |

---

## When in Doubt

**Rule:** Classify higher rather than lower.

- Uncertain if P0 or P1? → P0
- Uncertain if P1 or P2? → P1
- Uncertain if P2 or P3? → P2

**Why:** Better to over-report than under-report critical issues.

---

**Remember:** Focus on student impact, not technical complexity.
