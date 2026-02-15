# Enhanced User Messages

## Overview

Enhanced user messages provide a professional, informative testing experience. Instead of terse technical output, clear, descriptive messages explain what's being tested and why.

## Implementation Pattern

### Grading Script Example
```python
step_message="Waiting up to 15 minutes for lab systems to be available"
step_message="Downloading the automation execution environment"
step_message="The 'ansible-navigator.yml' file is configured correctly"
step_message="Installing required software"
```

### Testing Framework Pattern

```python
from ux_enhanced_progress import EnhancedProgressReporter

reporter = EnhancedProgressReporter()

# Print banner with context
reporter.print_banner(
    "TC-PREREQ: Prerequisites Testing",
    subtitle="Validating lab environment is ready"
)

# Detailed step messages
reporter.print_step(
    "Waiting for lab systems to be available",
    status="in_progress",
    details="This may take up to 15 minutes for large environments"
)

# Success/failure with context
reporter.print_step(
    "Lab systems are ready",
    status="success",
    duration=45.2
)
```

## Key Principles

1. **Descriptive**: Explain WHAT is being tested
2. **Contextual**: Explain WHY it matters
3. **Informative**: Show progress and timing
4. **Professional**: Match <NETWORK-COURSE>'s grading quality

## Implementation

### Basic Usage

```python
from ux_enhanced_progress import EnhancedProgressReporter

def test(self, exercise, ssh):
    reporter = EnhancedProgressReporter()

    # Clear banner
    reporter.print_banner(
        "TC-GRADE: Grading Testing",
        subtitle=f"Validating grading for {exercise.id}"
    )

    # Step 1 with description
    reporter.print_section_header("Step 1: Testing WITH solution")
    print("  Deploying solution files...")
    # ... do work ...
    print("  ✅ Solution deployed successfully")

    # Step 2 with timing
    start = time.time()
    reporter.print_section_header("Step 2: Running grading")
    print("  This validates the grading script works correctly")
    # ... do work ...
    duration = time.time() - start
    print(f"  ✅ Grading passed (took {duration:.1f}s)")
```

### Advanced: Progress Bars

```python
from ux_enhanced_progress import EnhancedProgressReporter

reporter = EnhancedProgressReporter()

# For operations with multiple steps
with reporter.create_progress("Testing solution files") as progress:
    task = progress.add_task("Processing", total=len(solution_files))

    for sol_file in solution_files:
        # Process file...
        progress.update(task, advance=1, description=f"Testing {sol_file.name}")
```

### Real Example from TC-AAP

```python
def test(self, exercise, ssh):
    print(f"\n🔧 TC-AAP: AAP Controller Testing")
    print("=" * 60)
    print(f"  AAP Controller URL: {self.aap_url}")

    # Test connection with clear message
    print("\n  Testing AAP Controller connection...")
    client = AAPControllerClient(self.aap_url)

    if not client.test_connection():
        print("    ❌ AAP Controller unreachable")
        # ... return with bug ...
    else:
        print("    ✅ AAP Controller is reachable")

    # Grade with verbose messages
    print(f"\n  Grading {len(expected_credentials)} credentials...")
    success, message = grade_credentials(
        expected_credentials,
        base_url=self.aap_url,
        verbose=True  # Enables detailed output
    )

    if success:
        print("    ✅ All credentials configured correctly")
    else:
        print(f"    ❌ Credential issues found")
        print(f"       {message}")
```

## Message Components

### 1. Banners
```python
print(f"\n🔧 TC-AAP: AAP Controller Testing")
print("=" * 60)
```

### 2. Section Headers
```python
print("\n  1. Testing SSH connection...")
print("\n  2. Checking required tools...")
```

### 3. Status Messages
```python
# Success
print("    ✅ SSH connection OK")

# Failure
print("    ❌ SSH connection failed")

# Warning
print("    ⚠️  No solution files found (may be intentional)")

# Info
print("    ℹ️  Using ansible-navigator with execution environment")

# In Progress
print("    🔄 Downloading execution environment...")
```

### 4. Details
```python
print(f"       Error: {error_msg[:200]}")
print(f"       Duration: {duration:.1f}s")
print(f"       Found {count} items")
```

### 5. Lists
```python
print(f"    ✅ Found {len(files)} solution files:")
for f in files[:5]:
    print(f"       - {f}")
if len(files) > 5:
    print(f"       ... and {len(files) - 5} more")
```

## Formatting Standards

### Indentation
- Main sections: No indent
- Subsections: 2 spaces
- Details: 4 spaces (using `print(f"    ...")`)
- Lists: 7 spaces for alignment

### Emojis
- ✅ Success
- ❌ Failure
- ⚠️  Warning
- ℹ️  Information
- 🔄 In progress
- 🔧 Testing/Tools
- 📁 Files
- 🚀 Starting/Launching
- 📊 Results/Statistics

### Colors (via rich library)
```python
from ux_enhanced_progress import EnhancedProgressReporter

reporter = EnhancedProgressReporter()

# If rich is available, automatically uses colors:
# - Green for success
# - Red for errors
# - Yellow for warnings
# - Blue for info
```

## Timeout Messages

Always show clear timeout information:

```python
print("\n  Waiting for lab systems (timeout: 15 minutes)...")
result = ssh.run(command, timeout=900)  # 15 * 60

print("\n  Running grading (timeout: 5 minutes)...")
result = ssh.run(command, timeout=300)  # 5 * 60
```

## Progress for Long Operations

```python
print("\n  Downloading execution environment...")
print("    This may take several minutes on first run")
print("    Subsequent runs will use cached image")

start = time.time()
result = executor.validate_ee_image(ee_image, timeout=600)
duration = time.time() - start

print(f"    ✅ Download completed in {duration:.1f}s")
```

## Implementation Checklist

All test categories should:

- [ ] Have clear banner with test category name
- [ ] Number or label each major step
- [ ] Show what's being tested and why
- [ ] Display clear success/failure with ✅/❌
- [ ] Include timing for operations >5 seconds
- [ ] Show timeout information for long operations
- [ ] Provide context for warnings
- [ ] Use consistent indentation (2/4 spaces)
- [ ] Limit output (truncate long lists/errors)

## Examples by Test Category

### TC-PREREQ
```
✅ TC-PREREQ: Prerequisites Testing
============================================================

  1. Testing SSH connection...
     ✅ SSH connection OK

  2. Checking required tools...
     ✅ ansible-navigator available
     ✅ ansible available
     ✅ python3 available

  3. Running: lab start <exercise-name> (timeout: 10 minutes)
     ✅ lab start succeeded (took 45.2s)

  4. Checking exercise directory...
     ✅ Directory exists: ~/<NETWORK-COURSE>/labs/<exercise-name>

  5. Checking solution files...
     ✅ Found 3 solution files:
        - playbook.yml.sol
        - inventory.sol
        - ansible.cfg.sol
```

### TC-GRADE
```
🔧 TC-GRADE: Grading Testing
============================================================

  Scenario 1: WITH solution (should pass 100%)
     Deploying solution files...
     ✅ Solutions deployed

     Running grading...
     ✅ Grading PASSED: 100/100 (took 12.5s)

  Scenario 2: WITHOUT solution (should fail 0%)
     Removing solution files...
     ✅ Solutions removed

     Running grading...
     ✅ Grading correctly FAILED: 0/100 (took 8.2s)

  Scenario 3: Message clarity
     ✅ Error messages are clear and actionable

✅ All grading scenarios PASSED
```

## Benefits

1. **Better UX**: Clear, professional output
2. **Easier debugging**: Know exactly what's being tested
3. **Context awareness**: Understand why tests take time
4. **Professional**: Matches Red Hat Training quality standards
