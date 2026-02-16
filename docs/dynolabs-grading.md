# DynoLabs Grading Framework - Understanding for EQA

This document explains how DynoLabs grading works and how EQA validates it correctly.

## Core Concepts

### Step vs GradingStep

DynoLabs uses two main step types:

1. **Step** - General purpose step (default: fatal=True)
   - Used for setup, execution, cleanup
   - Failures raise `StepFatalError` by default
   - Fatal steps cause process exit

2. **GradingStep** - Special step for validation (grading=True, fatal=False)
   - Used for checking student work
   - Failures are NON-FATAL by default
   - Multiple GradingSteps can fail without stopping the script

### Step Results

Steps can have three results:
- `SUCCESS` - Step completed successfully (normal steps)
- `PASS` - Step completed successfully (grading steps)
- `FAIL` - Step failed

### Fatal vs Non-Fatal Behavior

```python
# Fatal step (default) - raises exception on failure
with Step("Deploy application") as step:
    deploy()  # If this fails, script stops

# Non-fatal step - continues even on failure
with Step("Check optional feature", fatal=False) as step:
    check()  # If this fails, script continues

# GradingStep - non-fatal by default
with GradingStep("Check database configured") as step:
    if not db_configured():
        step.add_error("Database not configured")
    # Script continues even if this fails
```

## Grading Exit Codes - THE KEY INSIGHT

**CRITICAL:** DynoLabs grading exit codes do NOT indicate pass/fail of checks!

### Exit Code Meanings

- **Exit code 0** = Grading script completed successfully (no fatal errors)
  - This does NOT mean all checks passed!
  - GradingSteps can fail and exit code is still 0
  - Just means the script didn't crash

- **Exit code non-zero** = Fatal error occurred (script crashed)
  - Could be unhandled exception
  - Could be a fatal Step failure
  - This is a BUG in the grading script

### Example

```python
def grade(self):
    with GradingStep("Check file exists") as step:
        if not file_exists():
            step.add_error("File missing")  # FAIL, but non-fatal

    with GradingStep("Check content correct") as step:
        if not content_valid():
            step.add_error("Content invalid")  # FAIL, but non-fatal

    # Script reaches here even if both checks failed
    # Exit code: 0 (success - script completed)
    # But output shows: ✗ FAIL for both checks
```

## How EQA Validates Grading

### What We Check

1. **Script Completion** (exit codes)
   - Exit code must be 0 (script didn't crash)
   - Non-zero exit = P0 BLOCKER bug

2. **Check Results** (output parsing)
   - Parse output for ✓/✗ or PASS/FAIL indicators
   - Count passed vs failed checks
   - Validate against expected results

### Scenarios

#### Scenario 1: WITHOUT Solution
```
lab start exercise
lab grade exercise
```

**Expected:**
- Exit code: 0 (script completes)
- Output: Contains ✗ FAIL indicators
- At least one check should fail

**If all checks pass:** FALSE POSITIVE bug (P1 Critical)

#### Scenario 2: WITH Solution
```
lab start exercise
# Apply solution files
lab grade exercise
```

**Expected:**
- Exit code: 0 (script completes)
- Output: Contains ✓ PASS indicators
- All checks should pass

**If any check fails:** FALSE NEGATIVE bug (P1 Critical)

#### Scenario 3: Message Quality
Check that error messages are:
- Clear and actionable
- Not raw Python tracebacks
- Provide specific guidance

## Common Mistakes (Avoided by EQA)

### ❌ WRONG: Using exit codes for pass/fail
```python
# WRONG - This misunderstands DynoLabs
result = ssh.run("lab grade exercise")
if result.return_code == 0:
    print("Grading passed")  # NO! Script just didn't crash
else:
    print("Grading failed")  # NO! Script crashed (different issue)
```

### ✅ CORRECT: Parsing output for results
```python
# CORRECT - Parse output for actual results
result = ssh.run("lab grade exercise")

# First check: did script crash?
if result.return_code != 0:
    # P0 BLOCKER - script crashed
    raise Bug("Grading script crashed")

# Then check: did validations pass?
pass_count = len(re.findall(r'(✓|PASS)', result.stdout))
fail_count = len(re.findall(r'(✗|FAIL)', result.stdout))

if fail_count > 0:
    print(f"Grading failed: {fail_count} checks failed")
```

## DynoLabs CLI Commands

### Framework Detection

DynoLabs v5 has multiple deployment styles:

1. **Rust CLI** (preferred)
   - Command: `lab grade exercise-name`
   - Location: `/usr/local/bin/lab`
   - Modern, fast

2. **Python CLI**
   - Command: `cd ~/grading && uv run lab grade exercise-name`
   - Uses `uv` package manager
   - Python-based

3. **Wrapper CLI**
   - Command: `lab grade exercise-name`
   - Wrapper around Python CLI

4. **Legacy**
   - Older DynoLabs versions
   - Various command formats

EQA's `detect_lab_framework()` automatically identifies the correct variant.

## References

- **rht-labs-core**: https://github.com/RedHatTraining/rht-labs-core
- **Step class**: `src/labs/core/steps/step.py`
- **CLI**: `src/labs/cli.py`
- **Lab base class**: `src/labs/core/lab.py`

## EQA Implementation

See `src/tests/grading.py` for TC-GRADE implementation that correctly:
1. Detects script crashes (exit code validation)
2. Parses PASS/FAIL indicators (output validation)
3. Identifies false positives and false negatives
4. Validates error message quality
