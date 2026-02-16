# Interactive Mode - Lab Environment Setup

EQA supports interactive mode for testing, which prompts you when it can't connect to the lab environment, giving you time to set up the environment before continuing.

## Overview

When EQA can't connect to the workstation, it will:

1. **Display clear instructions** on what's needed to test the exercise
2. **Prompt you for action** with three options:
   - **Retry** - Try connecting again (while you set up the environment)
   - **Skip** - Skip this exercise and continue with the next one
   - **Abort** - Stop all testing

This is especially useful when:
- You're testing multiple exercises and need to start lab environments
- You're working with ephemeral lab environments (classroom, ROL, etc.)
- You want to verify specific exercises while setting up infrastructure

## Usage

### Interactive Mode (Default)

By default, EQA runs in interactive mode:

```bash
# Interactive mode - will prompt on connection failure
python3 -m src.main course.epub

# Explicit interactive mode
python3 -m src.main course.epub --mode categories
```

### Non-Interactive Mode

For automated testing (CI/CD, scripts), use `--non-interactive`:

```bash
# Non-interactive - skips exercises on connection failure
python3 -m src.main course.epub --non-interactive
```

## Interactive Prompt

When connection fails, you'll see:

```
============================================================
⚠️  Cannot connect to workstation: workstation
============================================================

To test this exercise, you need:
  1. A running lab environment for control-review
  2. SSH access configured to 'workstation'
  3. Lab framework installed (DynoLabs v5)

Commands to verify:
  $ ssh workstation hostname
  $ ssh workstation 'lab --version'
  $ ssh workstation 'lab list | grep control-review'

Options:
  [R] Retry - Try connecting again (I'm setting up the environment)
  [S] Skip  - Skip this exercise and continue with the next one
  [A] Abort - Stop all testing

Your choice [R/s/a]:
```

### Option Details

#### [R] Retry

Use this when you're setting up the lab environment:

1. EQA prompts you
2. You open another terminal and start the lab environment
3. Verify SSH access: `ssh workstation hostname`
4. Return to EQA and press **R**
5. EQA retries the connection

**Example workflow:**

```bash
# Terminal 1: Running EQA
$ python3 -m src.main AU294.epub control-review
...
⚠️  Cannot connect to workstation
Your choice [R/s/a]: _

# Terminal 2: Start lab environment
$ lab start control-review
$ ssh workstation hostname
workstation.example.com

# Back to Terminal 1
Your choice [R/s/a]: R
Retrying connection to workstation...
✓ Connected to workstation
```

#### [S] Skip

Use this to skip exercises you don't want to test:

- EQA marks the exercise as **SKIP**
- Continues with the next exercise
- No bug reported (intentional skip)

**Example:**

```
Your choice [R/s/a]: s
⊘ Skipping control-review
```

#### [A] Abort

Use this to stop all testing:

- EQA stops immediately
- No further exercises tested
- Exits with status code 1

**Example:**

```
Your choice [R/s/a]: a

❌ Testing aborted by user
```

## Use Cases

### Use Case 1: Testing Multiple Exercises

You're testing a course with 10 exercises, but only want to test 3 specific ones:

```bash
python3 -m src.main course.epub
# Retry for exercises you want to test
# Skip for exercises you don't want to test
```

### Use Case 2: Classroom Testing

You're in a classroom with ephemeral lab environments:

```bash
# Start testing
python3 -m src.main course.epub

# For each exercise:
# 1. EQA prompts
# 2. You start the lab environment
# 3. Press R to retry
# 4. EQA tests the exercise
# 5. Move to next exercise
```

### Use Case 3: CI/CD Pipeline

For automated testing, use non-interactive mode:

```bash
# CI/CD script
#!/bin/bash
# Start lab environments first
start-all-labs.sh

# Run EQA in non-interactive mode
python3 -m src.main course.epub --non-interactive

# All exercises will be skipped if connection fails
# No prompts, suitable for automation
```

### Use Case 4: Partial Course Testing

You're developing grading scripts and want to test only exercises with new changes:

```bash
# Test specific exercises
python3 -m src.main course.epub intro-lab setup-lab final-lab

# For each exercise:
# - Retry if you want to test it
# - Skip if it's unchanged
```

## Technical Details

### Retry Behavior

- **Max retries:** 5 user-initiated retries per exercise
- **Delay:** 1 second between retry attempts
- **Connection timeout:** Determined by SSH `ConnectTimeout` (default 10s)

### Non-Interactive Behavior

When `--non-interactive` is used:

1. Connection failure → Skip exercise immediately
2. No prompts displayed
3. Status: **SKIP**
4. Summary: "Skipped - no workstation connection"

### Connection Verification

Before prompting, EQA attempts to connect with:

1. **Initial attempt:** Standard SSH connection
2. **Retry logic:** 3 attempts with exponential backoff (2s, 4s)
3. **Prompt:** If all attempts fail

## Examples

### Example 1: Test All Exercises (Interactive)

```bash
$ python3 -m src.main AU294.epub

[1/32] control-flow
⚠️  Cannot connect to workstation
Your choice [R/s/a]: R
Retrying connection...
✓ Connected
✓ TC-PREREQ passed
✓ TC-STUDENTSIM passed
...

[2/32] control-handlers
⚠️  Cannot connect to workstation
Your choice [R/s/a]: S
⊘ Skipping control-handlers

[3/32] control-review
⚠️  Cannot connect to workstation
Your choice [R/s/a]: R
Retrying connection...
✓ Connected
...
```

### Example 2: Test Specific Exercises (Interactive)

```bash
$ python3 -m src.main AU294.epub control-review develop-review

[1/2] control-review
⚠️  Cannot connect to workstation
# In another terminal: lab start control-review
Your choice [R/s/a]: R
✓ Connected
✓ All tests passed

[2/2] develop-review
⚠️  Cannot connect to workstation
# In another terminal: lab start develop-review
Your choice [R/s/a]: R
✓ Connected
✓ All tests passed
```

### Example 3: CI/CD (Non-Interactive)

```bash
#!/bin/bash
# ci-test.sh

# Start all lab environments
for ex in control-review develop-review files-review; do
    lab start $ex &
done
wait

# Run EQA in non-interactive mode
python3 -m src.main AU294.epub \
    --non-interactive \
    --output ci-results/

# Check results
if [ $? -eq 0 ]; then
    echo "All tests passed"
else
    echo "Some tests failed"
    exit 1
fi
```

## Best Practices

1. **Use interactive mode during development**
   - Gives you control over which exercises to test
   - Allows time to start lab environments

2. **Use non-interactive mode in CI/CD**
   - No prompts means no blocking
   - Suitable for automation

3. **Verify SSH access first**
   ```bash
   # Before running EQA
   ssh workstation hostname
   ssh workstation 'lab --version'
   ```

4. **Keep another terminal open**
   - Use it to start lab environments
   - Verify connections manually
   - Monitor lab status

5. **Test in batches**
   - Don't try to test all 30+ exercises at once
   - Test related exercises together
   - Skip unrelated exercises

## Troubleshooting

### Prompt doesn't appear

**Problem:** EQA skips exercises without prompting

**Solution:** Make sure you're not using `--non-interactive`

```bash
# Check your command
python3 -m src.main course.epub  # Interactive (default)
```

### Can't input choice

**Problem:** Prompt appears but input doesn't work

**Solution:** Check if stdin is redirected or script is running in background

```bash
# Wrong - stdin redirected
python3 -m src.main course.epub < /dev/null

# Correct
python3 -m src.main course.epub
```

### Retry always fails

**Problem:** Pressing R always results in connection failure

**Solution:** Verify SSH connection manually first

```bash
# Test SSH connection
ssh workstation hostname

# Check lab environment
ssh workstation 'lab list'

# Check lab framework
ssh workstation 'lab --version'
```

### Abort doesn't work

**Problem:** Pressing A doesn't stop testing

**Solution:** Use Ctrl+C to force exit

```bash
# Graceful abort
Your choice [R/s/a]: a

# Force abort
Ctrl+C
```

## Related

- [SSH Configuration](ssh-config.md)
- [DynoLabs Framework](dynolabs-grading.md)
- [Test Categories](test-categories.md)
