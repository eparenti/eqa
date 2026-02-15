# Exercise QA 2 - Architecture

Clean, professional architecture built from the ground up.

## Design Principles

1. **Separation of Concerns** - Each module has a single, clear responsibility
2. **One File Per Feature** - Easy to find, easy to modify
3. **Test Category Isolation** - Each test category is completely independent
4. **No Hidden Dependencies** - All imports are explicit
5. **Professional Structure** - Industry-standard organization

## Directory Structure

```
exercise-qa-2/
├── src/
│   ├── main.py                 # Entry point & orchestration
│   ├── core/
│   │   └── models.py           # Data models (Bug, TestResult, etc.)
│   ├── epub/
│   │   ├── builder.py          # EPUB building with sk
│   │   └── parser.py           # EPUB parsing
│   ├── clients/
│   │   ├── ssh.py              # SSH connection
│   │   ├── aap.py              # AAP Controller client
│   │   └── ansible.py          # Ansible executor
│   ├── tests/
│   │   ├── prereq.py           # TC-PREREQ
│   │   ├── solution.py         # TC-SOL
│   │   ├── grading.py          # TC-GRADE
│   │   ├── cleanup.py          # TC-CLEAN
│   │   ├── idempotency.py      # TC-IDEM
│   │   ├── execution.py        # TC-EXEC
│   │   ├── workflow.py         # TC-WORKFLOW
│   │   ├── verification.py     # TC-VERIFY
│   │   ├── aap.py              # TC-AAP
│   │   └── e2e.py              # TC-E2E
│   ├── reporting/
│   │   ├── generator.py        # Report generation
│   │   └── metrics.py          # Quality metrics
│   └── utils/
│       ├── cache.py            # Result caching
│       └── parallel.py         # Parallel execution
├── tests/
│   └── test_*.py               # Unit tests
├── docs/
│   ├── ARCHITECTURE.md         # This file
│   ├── USER-GUIDE.md           # User documentation
│   ├── TEST-CATEGORIES.md      # Test category reference
│   └── DEVELOPMENT.md          # Developer guide
├── config/
│   └── test-budgets.yml        # Performance budgets
├── skill.json                   # Skill metadata
└── README.md                    # Quick start

## Execution Flow

```
1. Input Resolution
   ├─> Is it an EPUB? → Use directly
   ├─> Is it a directory? → Look for EPUB or build it
   └─> Is it a lesson code? → Find directory

2. EPUB Handling
   ├─> EPUB exists? → Parse it
   └─> EPUB missing? → Build with sk → Parse it

3. Course Structure Parsing
   ├─> Extract exercises from EPUB
   ├─> Find solution files
   ├─> Find grading scripts
   └─> Build exercise contexts

4. SSH Connection
   └─> Connect to workstation with retry logic

5. Test Execution (for each exercise)
   ├─> TC-PREREQ (prerequisites)
   ├─> TC-SOL (solution files)
   ├─> TC-GRADE (grading validation)
   ├─> TC-CLEAN (cleanup)
   ├─> TC-IDEM (idempotency)
   └─> ... (other categories)

6. Result Aggregation
   └─> Combine exercise results into course results

7. Report Generation
   └─> Generate markdown + JSON reports
```

## Key Components

### Core Models (`core/models.py`)

All data structures:
- `Bug` - Defect found during testing
- `TestResult` - Result from one test category
- `ExerciseContext` - Complete exercise metadata
- `ExerciseTestResults` - All test results for one exercise
- `CourseContext` - Complete course structure
- `CourseTestResults` - Aggregated results

### EPUB Builder (`epub/builder.py`)

- Auto-detects scaffolding location
- Runs `sk build epub3`
- Finds generated EPUB
- Validates sk availability

### EPUB Parser (`epub/parser.py`)

- Extracts EPUB to temp directory
- Parses metadata from content.opf
- Finds exercises by ID patterns (`-ge`, `-lab`)
- Builds exercise contexts

### SSH Client (`clients/ssh.py`)

- System SSH with pexpect for interactive commands
- Exponential backoff retry logic
- Command execution with timeout
- File existence checking
- Remote file reading

### Test Categories (`tests/*.py`)

Each test category:
- Implements `test(exercise, ssh)` method
- Returns `TestResult`
- Uses error summary pattern (collect all bugs)
- Independent from other categories

### Main Orchestrator (`main.py`)

- Resolves input (EPUB, directory, or code)
- Ensures EPUB exists (builds if needed)
- Parses course structure
- Connects to SSH
- Runs all test categories
- Aggregates results
- Generates reports

## Error Summary Pattern

All test categories use the error summary pattern:

```python
def test(self, exercise, ssh):
    bugs_found = []  # Collect ALL bugs

    # Test 1
    if not check_1():
        bugs_found.append(Bug(...))

    # Test 2 - STILL RUN even if Test 1 failed
    if not check_2():
        bugs_found.append(Bug(...))

    # Test 3 - STILL RUN
    if not check_3():
        bugs_found.append(Bug(...))

    return TestResult(
        passed=(len(bugs_found) == 0),
        bugs_found=bugs_found
    )
```

**Benefit**: Student sees ALL issues in one run, not one at a time.

## Adding New Test Categories

1. Create new file in `src/tests/`:
   ```python
   # src/tests/newtest.py
   from ..core.models import TestResult, Bug, BugSeverity

   class TC_NEWTEST:
       def test(self, exercise, ssh):
           bugs_found = []
           # ... test logic ...
           return TestResult(...)
   ```

2. Import in `src/tests/__init__.py`:
   ```python
   from .newtest import TC_NEWTEST
   ```

3. Add to test execution in `src/main.py`:
   ```python
   test_categories = [
       TC_PREREQ(),
       TC_SOL(),
       TC_GRADE(),
       TC_NEWTEST(),  # Add here
   ]
   ```

## Benefits of This Architecture

✅ **Easy to Find** - "Where's EPUB building?" → `src/epub/builder.py`
✅ **Easy to Modify** - Change TC-GRADE? Edit one file: `src/tests/grading.py`
✅ **Easy to Add** - New test category? Add one file
✅ **Nothing Gets Lost** - Each feature has its own file
✅ **Clear Dependencies** - All imports are explicit
✅ **Testable** - Each module can be unit tested independently
✅ **Professional** - Industry-standard structure

## Comparison to Old Skill

| Aspect | Old Skill | New Skill |
|--------|-----------|-----------|
| **Test Categories** | 5,600 lines in 1 file | 1 file per category (~100-200 lines) |
| **EPUB Building** | Referenced but not implemented | Fully implemented |
| **Organization** | 60+ files, confusing structure | 15-20 files, clear structure |
| **Finding Features** | Difficult | Easy (one file per feature) |
| **Modifying Code** | Risky (huge files) | Safe (isolated modules) |
| **Adding Features** | Complex | Simple (add one file) |
| **Documentation** | Scattered | Comprehensive |

## Authors

- Ed Parenti <eparenti@redhat.com>
- Claude Code

## Version

1.0.0 - Initial professional implementation
