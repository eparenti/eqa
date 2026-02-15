# Exercise QA - Architecture Overview

**For developers working on the skill**

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXERCISE QA RUNNER                                 │
│                        (exercise_qa_runner.py)                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   CLI Args  │→ │   Course    │→ │    Test     │→ │      Report         │ │
│  │   Parser    │  │  Analyzer   │  │ Orchestrator│  │    Generator        │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
        ┌───────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐
        │   TEST EXECUTOR   │ │  WEBAPP TESTER  │ │    QUALITY METRICS      │
        │ (test_executor.py)│ │(chrome_webapp..)│ │  (quality_metrics.py)   │
        └───────────────────┘ └─────────────────┘ └─────────────────────────┘
                    │
    ┌───────────────┴───────────────────────────────────────────┐
    ▼                   ▼                   ▼                   ▼
┌────────┐        ┌────────┐        ┌────────┐        ┌────────────────┐
│TC-PREREQ│       │TC-EXEC │        │TC-SOL  │        │  TC-WORKFLOW   │
├────────┤        ├────────┤        ├────────┤        ├────────────────┤
│TC-GRADE│        │TC-VERIFY│       │TC-SOLVE│        │   TC-IDEM      │
├────────┤        ├────────┤        ├────────┤        ├────────────────┤
│TC-CLEAN│        │TC-AAP  │        │TC-E2E  │        │  TC-INSTRUCT   │
├────────┤        ├────────┤        ├────────┤        ├────────────────┤
│TC-SECURITY│     │TC-ACCESS│       │TC-CONTRACT│     │   TC-WEB       │
└────────┘        └────────┘        └────────┘        └────────────────┘
    │                   │                   │                   │
    └───────────────────┴───────────────────┴───────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
        ┌─────────────────────┐   ┌─────────────────────────┐
        │   CORE LIBRARIES    │   │   DATA STRUCTURES       │
        │  (lib/)             │   │  (lib/test_result.py)   │
        ├─────────────────────┤   ├─────────────────────────┤
        │ • ssh_connection.py │   │ • Bug, BugSeverity      │
        │ • aap_client.py     │   │ • TestResult            │
        │ • ansible_executor  │   │ • ExerciseContext       │
        │ • failure_diagnostics│  │ • CourseContext         │
        │ • quality_metrics   │   │ • ExerciseTestResults   │
        │ • performance_budgets│  │ • CourseTestResults     │
        └─────────────────────┘   └─────────────────────────┘
                    │
                    ▼
        ┌─────────────────────────────────────┐
        │         LIVE LAB ENVIRONMENT        │
        ├─────────────────────────────────────┤
        │  workstation ──► managed hosts      │
        │       │                             │
        │       ├──► servera, serverb, ...    │
        │       ├──► iosxe1, junos1, arista1  │
        │       └──► AAP Controller API       │
        └─────────────────────────────────────┘
```

### Data Flow

```
┌──────────┐     ┌───────────────┐     ┌──────────────┐     ┌────────────┐
│  EPUB /  │ ──► │    Course     │ ──► │    Test      │ ──► │   Test     │
│  Course  │     │   Analyzer    │     │  Categories  │     │  Results   │
│  Input   │     │               │     │              │     │            │
└──────────┘     └───────────────┘     └──────────────┘     └────────────┘
                        │                      │                   │
                        ▼                      ▼                   ▼
                 ┌─────────────┐        ┌────────────┐      ┌────────────┐
                 │CourseContext│        │  SSH/API   │      │    Bug     │
                 │ (exercises, │        │ Connections│      │ Collection │
                 │  patterns)  │        │            │      │            │
                 └─────────────┘        └────────────┘      └────────────┘
                                                                   │
                                                                   ▼
                                                            ┌────────────┐
                                                            │   Report   │
                                                            │ Generator  │
                                                            │            │
                                                            └────────────┘
                                                                   │
                                                                   ▼
                                                            ┌────────────┐
                                                            │  QA Report │
                                                            │  (markdown)│
                                                            └────────────┘
```

---

## Design Principles

1. **Simple** - Clear abstractions, minimal dependencies
2. **Efficient** - Auto-detection, connection pooling, error summary pattern
3. **Maintainable** - Modular design, comprehensive documentation
4. **Quality First** - Never sacrifice features for simplicity

---

## Core Architecture

### Layer 1: Data Structures (`lib/test_result.py`)

Foundation for all testing:

```python
from lib import Bug, BugSeverity, TestResult, ExerciseContext, ExerciseType

# All test categories use these structures
bug = Bug(
    id="BUG-001",
    severity=BugSeverity.P1_CRITICAL,
    exercise_id="<exercise-name>",
    category="TC-GRADE",
    description="Grading fails without solution",
    fix_recommendation="Update grade.yml to check...",
    verification_steps=["1. Apply fix", "2. Test grading"]
)

result = TestResult(
    category="TC-GRADE",
    exercise_id="<exercise-name>",
    passed=False,
    bugs_found=[bug],
    details={...}
)
```

### Layer 2: Connection Management (`lib/ssh_connection.py`)

Unified SSH for Linux hosts and network devices:

```python
from lib import SSHConnection, SSHConnectionPool

# Single connection
ssh = SSHConnection("workstation", username="student")
result = ssh.run("ansible --version", timeout=30)

# Network device with auto-detection
device = SSHConnection("iosxe1", auto_detect_device=True)
# Automatically uses 2.0x timeout for Cisco

# Connection pool for multiple hosts/devices
pool = SSHConnectionPool()
pool.add_connection("workstation")
pool.add_connection("iosxe1", auto_detect=True)
pool.add_connection("junos1", auto_detect=True)

# Run commands on all
results = pool.run_on_all("show version")
```

### Layer 3: Technology Clients

**AAP Controller** (`lib/aap_client.py`):
```python
from lib import AAPControllerClient, grade_credentials

client = AAPControllerClient("https://aap.example.com")
credential = client.get_credential_by_name("Git-Cred")

# Python-based grading
success, message = grade_credentials([
    {'name': 'Git-Cred', 'credential_type': 'Source Control'}
], base_url="https://aap.example.com")
```

**Ansible Executor** (`lib/ansible_executor.py`):
```python
from lib import AnsibleExecutor

executor = AnsibleExecutor(ssh)

# Auto-detects navigator vs playbook
detection = executor.detect_execution_method("/path/to/playbook")
# Returns: {'method': 'navigator', 'ee_enabled': True, 'ee_image': '...'}

# Execute with auto-selection
result = executor.execute_playbook("/path/to/playbook.yml")
```

### Layer 4: Classification & Orchestration

**Exercise Classifier** (`lib/exercise_classifier.py`):
```python
from lib import ExerciseClassifier, ExercisePriority

# Classify exercise
priority = ExerciseClassifier.get_priority(exercise)
timeout_mult = ExerciseClassifier.get_timeout_multiplier(exercise)
should_test_solve = ExerciseClassifier.should_test_solve_playbook(exercise)
```

**Test Orchestrator** (`test_orchestrator.py`):
- Ensures ALL exercises tested (no skipping)
- Creates test plans (sequential, parallel, smart)
- Aggregates results
- Triggers report generation

**Course Analyzer** (`course_analyzer.py`):
- Analyzes course BEFORE testing
- Builds dependency graph
- Maps all resources
- Detects technology

---

## Test Categories (`test_categories/`)

All test categories follow:
1. **Error summary pattern** - collect all bugs before returning
2. **Enhanced messaging** - clear progress indicators
3. **Shared data structures** - Bug, TestResult

**Standard interface:**
```python
class TC_EXAMPLE:
    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        bugs_found = []

        # Test 1 - collect bugs
        if not check_1():
            bugs_found.append(Bug(...))

        # Test 2 - continue even if test 1 failed
        if not check_2():
            bugs_found.append(Bug(...))

        # Return all bugs
        return TestResult(
            category="TC-EXAMPLE",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            bugs_found=bugs_found
        )
```

**Implemented categories:**
- `tc_prereq.py` - Prerequisites (SSH, tools, hosts, network devices, EE)
- `tc_instruct.py` - Instruction quality
- `tc_exec.py` - EPUB execution
- `tc_sol.py` - Solution testing
- `tc_solve.py` - Solve playbook testing
- `tc_verify.py` - Verification
- `tc_grade.py` - Grading validation
- `tc_aap.py` - AAP Controller testing
- `tc_clean.py` - Cleanup validation
- `tc_idem.py` - Idempotency
- `tc_e2e.py` - End-to-end testing
- `tc_workflow.py` - Workflow automation

---

## Key Patterns

### Error Summary Pattern

**Problem:** Fail-fast frustrates students - find issue, fix, re-run, find next issue

**Solution:** Collect all bugs before returning

```python
def test(self, exercise, ssh):
    bugs_found = []  # Collect all

    # Test credentials - continue even if fails
    if not test_credentials():
        bugs_found.append(Bug(...))

    # Test projects - STILL RUN even if credentials failed
    if not test_projects():
        bugs_found.append(Bug(...))

    # Test templates - STILL RUN
    if not test_job_templates():
        bugs_found.append(Bug(...))

    # Return ALL bugs at once
    return TestResult(bugs_found=bugs_found, ...)
```

**Benefit:** Student sees all 3 issues in one test run instead of 3 test runs

**Exception:** P0 blockers may stop early (SSH failure, etc.)

### Enhanced Messaging

**Problem:** Terse output doesn't explain what's happening or why

**Solution:** Professional, clear messages with context

```python
print(f"\n✅ TC-PREREQ: Prerequisites Testing")
print("=" * 60)

print("\n  1. Testing SSH connection...")
print("     ✅ SSH connection OK")

print("\n  2. Checking required tools...")
print("     ✅ ansible-navigator available (v3.1.0)")
print("     ℹ️  Using ansible-navigator with EE: ee-supported-rhel8:latest")

print("\n  3. Testing network devices (timeout: 30s)...")
print("     ✅ iosxe1 reachable (cisco_iosxe)")
```

**Standards:**
- Emojis: ✅ ❌ ⚠️ ℹ️
- Indentation: main=0, details=2, items=4
- Timeouts shown for long operations
- Timing for operations >5 seconds

### Connection Pooling

**Problem:** Creating new SSH connections for each test is slow

**Solution:** SSHConnectionPool manages and reuses connections

```python
pool = SSHConnectionPool()

# Add once
pool.add_connection("workstation")
pool.add_connection("servera")
pool.add_connection("iosxe1", auto_detect=True)

# Reuse throughout testing
result1 = pool.get("workstation").run("command1")
result2 = pool.get("workstation").run("command2")  # Same connection
result3 = pool.get("iosxe1").run("show version", timeout=45)  # 2.0x timeout
```

### Auto-Detection

**Problem:** Manual configuration is error-prone and tedious

**Solution:** Auto-detect everything

```python
# Workstation from ~/.ssh/config
workstation = detect_workstation()

# Technology from course materials
tech = detect_technology(course_path)  # "ansible", "openshift", "rhel"

# Exercise type from grading script
ex_type = detect_exercise_type(script)  # "GE" or "Lab"

# Device type from hostname
device_type = SSHConnection.detect_device_type("iosxe1")  # "cisco_iosxe"

# Execution method from environment
method = executor.detect_execution_method(playbook_dir)
# Returns: navigator/playbook based on ansible-navigator.yml and binary
```

---

## File Organization

```
.skilldata/scripts/
├── lib/                          # Core libraries
│   ├── __init__.py              # Exports all lib classes
│   ├── test_result.py           # Data structures
│   ├── ssh_connection.py        # Connection management
│   ├── aap_client.py            # AAP Controller API
│   ├── ansible_executor.py      # Ansible execution
│   └── exercise_classifier.py   # Classification logic
├── test_categories/              # Test implementations
│   ├── __init__.py              # Exports all test categories
│   ├── tc_prereq.py
│   ├── tc_exec.py
│   ├── tc_sol.py
│   ├── tc_solve.py
│   ├── tc_grade.py
│   ├── tc_verify.py
│   ├── tc_aap.py
│   ├── tc_clean.py
│   ├── tc_idem.py
│   └── tc_e2e.py
├── course_analyzer.py            # Course analysis engine
├── test_executor.py              # Test execution engine
├── test_orchestrator.py          # Master coordinator
├── report_generator.py           # Report generation
├── chrome_webapp_tester.py       # WebApp testing
├── webapp_integrator.py          # WebApp integration
└── exercise_qa_runner.py         # Main entry point
```

---

## Adding New Test Categories

1. **Create test category file:**
```python
# test_categories/tc_new.py
from lib import Bug, BugSeverity, TestResult

class TC_NEW:
    def test(self, exercise, ssh):
        bugs_found = []

        # Implement tests using error summary pattern
        if not my_check():
            bugs_found.append(Bug(
                id=f"BUG-NEW-001",
                severity=BugSeverity.P1_CRITICAL,
                exercise_id=exercise.id,
                category="TC-NEW",
                description="Something failed",
                fix_recommendation="Fix with this command...",
                verification_steps=["1. Apply fix", "2. Verify"]
            ))

        return TestResult(
            category="TC-NEW",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            bugs_found=bugs_found,
            details={...}
        )
```

2. **Export from `__init__.py`:**
```python
from .tc_new import TC_NEW

__all__ = [
    # ... existing exports ...
    'TC_NEW'
]
```

3. **Add to orchestrator** (`test_orchestrator.py`)

---

## Adding New Technologies

1. **Add detection logic** (`course_analyzer.py` or `detect_technology()`)

2. **Add technology-specific client if needed** (like `aap_client.py`)

3. **Update test categories** to handle new technology:
```python
# In tc_prereq.py
def _detect_technology_prerequisites(self, exercise):
    if exercise.technology == "my-new-tech":
        return self._check_my_tech_prereqs()
```

4. **Update documentation** (SKILL.md)

---

## Performance Optimizations

1. **Connection pooling** - Reuse SSH connections
2. **EPUB caching** - Cache parsed EPUB content
3. **Parallel execution** - Run independent tests in parallel
4. **Auto-detection** - Skip unnecessary checks based on detected technology
5. **Error summary** - Reduce test iterations needed
6. **Smart timeouts** - Automatic multipliers for slow devices (network devices)

---

## Testing the Skill

```bash
# Run demo of exercise classifier
python3 lib/exercise_classifier.py

# Test SSH connection
python3 -c "from lib import SSHConnection; ssh = SSHConnection('workstation'); print(ssh.run('echo test'))"

# Test AAP client
python3 -c "from lib import AAPControllerClient; c = AAPControllerClient('https://aap.example.com'); c.test_connection()"
```

---

## Code Quality Standards

1. **Error summary pattern** - All test categories MUST collect bugs before returning
2. **Enhanced messaging** - Use clear, descriptive output with emojis and context
3. **Type hints** - All function signatures have type hints
4. **Docstrings** - All public functions documented
5. **Consistent naming** - Follow Python PEP 8
6. **Modularity** - Single responsibility per module
7. **No duplication** - Shared logic in lib/
8. **Auto-detection** - Prefer auto-detection over manual configuration

---

## Developer References

**Pattern Documentation:**
- `ERROR-SUMMARY-PATTERN.md` - Error collection pattern
- `ENHANCED-USER-MESSAGES.md` - Message formatting standards

**User Documentation:**
- `SKILL.md` - Complete user-facing documentation
- `README.md` - Quick start guide

**Testing Standards:**
- `.skilldata/reference/testing-standards/` - Industry testing standards
- `.skilldata/reference/BUG-SEVERITY-GUIDE.md` - Bug classification

---

**Maintained:** 2026-01-10
**Status:** Production Ready
