#!/usr/bin/env python3
"""
Initialize QA Project Structure (Automated Testing Version)

Creates QA testing infrastructure for automated exercise/lab validation.
Focus on process steps, not time-based schedules.

Usage:
    python scripts/init_qa_project_v2.py <project-name> [output-dir]

Example:
    python scripts/init_qa_project_v2.py <ANSIBLE-COURSE> ./
"""

import os
import sys
import csv
from pathlib import Path
from datetime import datetime

def create_directory_structure(base_path):
    """Create QA project directory structure."""
    dirs = [
        "tests/docs",
        "tests/docs/templates",
        "tests/docs/reports",
        "tests/scripts"
    ]

    for dir_path in dirs:
        full_path = base_path / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created: {full_path}")

def create_test_execution_tracking(base_path, project_name):
    """Create TEST-EXECUTION-TRACKING.csv with headers."""
    csv_path = base_path / "tests/docs/templates/TEST-EXECUTION-TRACKING.csv"

    headers = [
        "Test Case ID", "Category", "Priority", "Test Name",
        "Prerequisites", "Status", "Result", "Bug ID",
        "Execution Date", "Executed By", "Notes", "Screenshot/Log"
    ]

    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerow([
            "TC-PREREQ-001", "Prerequisites", "P0", "Example: Environment Ready",
            "None", "Not Started", "", "", "", "",
            "Replace with actual test cases", ""
        ])

    print(f"✅ Created: {csv_path}")

def create_bug_tracking_template(base_path):
    """Create BUG-TRACKING-TEMPLATE.csv."""
    csv_path = base_path / "tests/docs/templates/BUG-TRACKING-TEMPLATE.csv"

    headers = [
        "Bug ID", "Title", "Severity", "Component", "Test Case ID",
        "Status", "Reported Date", "Reported By", "Assigned To",
        "Description", "Steps to Reproduce", "Expected Result",
        "Actual Result", "Environment", "Screenshots/Logs",
        "Resolution", "Resolved Date", "Verified By", "Verification Date"
    ]

    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

    print(f"✅ Created: {csv_path}")

def create_baseline_metrics(base_path, project_name):
    """Create BASELINE-METRICS.md template."""
    content = f"""# Baseline Metrics - {project_name}

**Date**: {datetime.now().strftime("%Y-%m-%d")}
**Purpose**: Pre-QA snapshot for comparison during testing

---

## Test Coverage (Current State)

### Unit Tests
- **Total Tests**: [NUMBER]
- **Passing**: [NUMBER] ([%]%)
- **Failing**: [NUMBER]
- **Coverage**: [%]% (statements/branches/functions)

### Integration Tests
- **Total Tests**: [NUMBER]
- **Status**: [Passing/Failing/Not Implemented]

---

## Known Issues (Pre-QA)

### Critical Issues
- [ ] Issue 1: Description
- [ ] Issue 2: Description

### Technical Debt
- [ ] Debt 1: Description
- [ ] Debt 2: Description

---

## Security Status

### OWASP Top 10 Coverage
- [ ] A01: Broken Access Control
- [ ] A02: Cryptographic Failures
- [ ] A03: Injection
- [ ] A04: Insecure Design
- [ ] A05: Security Misconfiguration
- [ ] A06: Vulnerable Components
- [ ] A07: Authentication Failures
- [ ] A08: Data Integrity Failures
- [ ] A09: Logging Failures
- [ ] A10: SSRF

**Current Coverage**: [X]/10 ([%]%)

---

## Code Quality

- **Linting Errors**: [NUMBER]
- **TypeScript Strict Mode**: [Yes/No]
- **Code Duplication**: [%]%
- **Cyclomatic Complexity**: [Average]

---

**Next Steps**: Begin automated testing with baseline established.
"""

    file_path = base_path / "tests/docs/BASELINE-METRICS.md"
    with open(file_path, 'w') as f:
        f.write(content)

    print(f"✅ Created: {file_path}")

def create_progress_report_template(base_path):
    """Create PROGRESS-REPORT.md template."""
    content = """# QA Progress Report

**Date**: [Date]
**Project**: [Project Name]

---

## Executive Summary

**Status**: 🟢 On Track / 🟡 At Risk / 🔴 Blocked

### Key Metrics
- **Tests Executed**: X / Y ([Z]%)
- **Pass Rate**: [%]%
- **Bugs Filed**: [N] (P0: [a], P1: [b], P2: [c], P3: [d])
- **Code Coverage**: [%]%

---

## Test Execution Progress

| Category | Total | Executed | Pass | Fail | Pass Rate |
|----------|-------|----------|------|------|-----------|
| Prerequisites | X | Y | Z | W | [%]% |
| Instructions | X | Y | Z | W | [%]% |
| Execution | X | Y | Z | W | [%]% |
| Solutions | X | Y | Z | W | [%]% |
| Cleanup | X | Y | Z | W | [%]% |
| **TOTAL** | X | Y | Z | W | [%]% |

---

## Quality Gates Status

| Gate | Target | Current | Status |
|------|--------|---------|--------|
| Test Execution | 100% | [%]% | ✅/⚠️/❌ |
| Pass Rate | ≥100% | [%]% | ✅/⚠️/❌ |
| P0 Bugs | 0 | [N] | ✅/⚠️/❌ |

---

## Bugs Summary

### P0 Bugs (Blockers)
1. **BUG-001**: [Title]
   - Status: [Open/In Progress/Blocked]
   - Test Case: TC-XXX-YYY
   - Impact: [Description]

---

## Blockers & Risks

### Current Blockers
- [ ] Blocker 1: Description
- [ ] Blocker 2: Description

### Risks
- ⚠️ **Risk 1**: Description - Mitigation: [Action]

---

## Next Steps

### Upcoming Test Categories
- [Category]: [Description]
- Prerequisites: [List]

---

**Status**: [On Track / At Risk / Blocked]
"""

    file_path = base_path / "tests/docs/templates/PROGRESS-REPORT.md"
    with open(file_path, 'w') as f:
        f.write(content)

    print(f"✅ Created: {file_path}")

def create_test_case_template(base_path):
    """Create TEST-CASE-TEMPLATE.md."""
    content = """# Test Case Template

Use this template to create new test cases for exercises/labs.

---

## Template

```markdown
### TC-{CATEGORY}-{NUMBER}: {Descriptive Title}

**Priority**: P0/P1/P2/P3/P4
**Category**: Prerequisites/Instructions/Execution/Solution/Cleanup/Mistakes

**Prerequisites**:
- List what must be true before this test
- Be specific (e.g., "File x.yml exists")
- Can reference other test cases (e.g., "TC-PREREQ-001 passed")

**Test Steps**:
1. First action (with specific command if applicable)
2. Second action
3. Verification step

**Expected Result**:
✅ First thing that should be true
✅ Second thing that should be true
✅ Third thing that should be true

**Pass/Fail Criteria**:
- ✅ PASS: All expected results met
- ❌ FAIL: Any expected result not met

**Potential Bugs**:
- Common issue 1
- Common issue 2
```

---

## Example: Prerequisites Test

```markdown
### TC-PREREQ-301-001: Ansible Installed

**Priority**: P0
**Category**: Prerequisites

**Prerequisites**: None

**Test Steps**:
1. Run `ansible --version`
2. Check version output

**Expected Result**:
✅ Command succeeds (exit code 0)
✅ Version is 2.15.x or higher

**Pass/Fail Criteria**:
- ✅ PASS: Command succeeds and version ≥ 2.15
- ❌ FAIL: Command fails or version < 2.15

**Potential Bugs**:
- Ansible not in PATH
- Wrong version installed
```

---

## Example: Exercise Execution Test

```markdown
### TC-EXEC-301-003: Create Ansible Inventory

**Priority**: P0
**Category**: Execution

**Prerequisites**:
- Exercise environment ready
- TC-PREREQ-301-001 passed

**Test Steps**:
1. Execute Step 1 from exercise: `mkdir -p ~/ansible-lab/inventory`
2. Execute Step 2: Create hosts file with webservers group
3. Verify file created: `cat ~/ansible-lab/inventory/hosts`

**Expected Result**:
✅ Directory ~/ansible-lab/inventory exists
✅ File hosts contains [webservers] group
✅ File lists two web servers

**Pass/Fail Criteria**:
- ✅ PASS: All files created with correct content
- ❌ FAIL: Missing files or incorrect content

**Potential Bugs**:
- Directory creation fails (permissions)
- File content incorrect (syntax error)
```

---

## Test Categories

### TC-PREREQ: Prerequisites
Validate environment ready for exercise

### TC-INSTRUCT: Instructions
Validate exercise instructions are clear

### TC-EXEC: Execution
Validate exercise steps work correctly

### TC-SOL: Solution
Validate provided solution works

### TC-CLEAN: Cleanup
Validate cleanup script works

### TC-MISTAKE: Common Mistakes
Validate error handling for common mistakes

---

## Priority Levels

- **P0 (Blocker)**: Exercise completely broken, must fix
- **P1 (Critical)**: Major issue, should fix before release
- **P2 (High)**: Minor issue, good to fix
- **P3 (Low)**: Nice to have improvement

---

**Usage**: Copy template above and fill in for your exercise.
"""

    file_path = base_path / "tests/docs/TEST-CASE-TEMPLATE.md"
    with open(file_path, 'w') as f:
        f.write(content)

    print(f"✅ Created: {file_path}")

def create_readme(base_path, project_name):
    """Create README.md for QA docs."""
    content = f"""# QA Documentation - {project_name}

**Status**: 🟢 Ready for Execution
**Created**: {datetime.now().strftime("%Y-%m-%d")}
**Focus**: Automated Exercise & Lab Testing

---

## Quick Start

### Run QA on Exercise or Lab

```bash
# Test an exercise (ge.adoc file)
/qa /COURSE/content/keyword/topic/ge.adoc

# Test a lab (lab.adoc file)
/qa /COURSE/content/keyword/topic/lab.adoc
```

LLM will automatically:
1. Read exercise/lab content from ge.adoc or lab.adoc file
2. Read test cases from `tests/docs/TEST-CASES-{{topic-name}}.md` or auto-generate
3. Execute all test cases in sequence
4. Validate commands, files, solutions
5. Document failures
6. Generate report

---

## Test Execution Process

### Phase 1: Prerequisites Validation
- Validate environment ready
- Check packages installed
- Verify services running

### Phase 2: Instructions Validation
- Check exercise clarity
- Verify steps are complete
- Validate commands are correct

### Phase 3: Exercise Execution
- Execute each exercise step
- Validate outputs match expected
- Check files created correctly

### Phase 4: Solution Validation
- Run provided solution
- Verify solution completes successfully
- Validate final state correct

### Phase 5: Cleanup Validation
- Execute cleanup script
- Verify all artifacts removed
- Confirm system ready for next exercise

### Phase 6: Error Handling Validation
- Test common student mistakes
- Verify error messages are helpful
- Check recovery procedures work

---

## Quality Gates

All exercises must achieve:

| Gate | Target | Status |
|------|--------|--------|
| Prerequisites Pass | 100% | ⏳ Not Started |
| Instructions Pass | 100% | ⏳ Not Started |
| Execution Pass | 100% | ⏳ Not Started |
| Solution Pass | 100% | ⏳ Not Started |
| Cleanup Pass | 100% | ⏳ Not Started |
| P0 Bugs | 0 | ✅ No blockers |

---

## File Structure

```
tests/
├── docs/
│   ├── README.md                    # This file
│   ├── TEST-CASE-TEMPLATE.md        # Template for new test cases
│   ├── TEST-CASES-create-inventory.md   # Test cases for create-inventory exercise
│   ├── TEST-CASES-configure-haproxy.md  # Test cases for configure-haproxy lab
│   ├── BASELINE-METRICS.md          # Pre-QA baseline
│   ├── templates/
│   │   ├── TEST-EXECUTION-TRACKING.csv
│   │   ├── BUG-TRACKING-TEMPLATE.csv
│   │   └── PROGRESS-REPORT.md
│   └── reports/
│       └── {{topic-name}}-QA-REPORT-*.md  # Generated reports
└── scripts/
    ├── calculate_metrics.py         # Generate quality metrics
    ├── validate_qa_setup.py         # Validate QA infrastructure
    └── validate_test_ids.py         # Check test ID consistency
```

---

## Creating Test Cases

### Step 1: Copy Template

```bash
# For exercise at /COURSE/content/load-balancing/configure-haproxy/ge.adoc
cp tests/docs/TEST-CASE-TEMPLATE.md tests/docs/TEST-CASES-configure-haproxy.md
```

### Step 2: Add Test Cases

Edit the markdown file with your test cases following the template.

### Step 3: Run QA

```bash
# Test the exercise
/qa /COURSE/content/load-balancing/configure-haproxy/ge.adoc
```

### Step 4: Fix Issues

Update exercise or test cases until 100% pass rate achieved.

---

## Example Test Case

```markdown
### TC-EXEC-423-001: Install HAProxy

**Priority**: P0
**Category**: Execution

**Prerequisites**: Repository configured

**Test Steps**:
1. Install HAProxy: `sudo dnf install -y haproxy`
2. Verify installation: `rpm -q haproxy`

**Expected Result**:
✅ Installation succeeds
✅ Package haproxy installed

**Pass/Fail Criteria**:
- ✅ PASS: Both steps succeed
- ❌ FAIL: Either step fails
```

---

## Automated Process Flow

```
User runs: /qa /COURSE/content/keyword/topic/ge.adoc  (or lab.adoc)

↓

LLM reads exercise/lab content from ge.adoc or lab.adoc

↓

LLM discovers test cases in tests/docs/TEST-CASES-{{topic}}.md

↓

LLM executes tests in sequence:
1. TC-PREREQ-* (Prerequisites)
2. TC-INSTRUCT-* (Instructions)
3. TC-EXEC-* (Execution)
4. TC-SOL-* (Solution)
5. TC-CLEAN-* (Cleanup)
6. TC-MISTAKE-* (Error Handling)

↓

LLM documents results:
- PASS/FAIL for each test
- Failure details captured
- Screenshots/logs saved

↓

LLM generates report:
tests/docs/reports/EX*-QA-REPORT-{{date}}.md
```

---

**Status**: ✅ Ready for automated exercise & lab testing
**Contact**: QA Team
"""

    file_path = base_path / "tests/docs/README.md"
    with open(file_path, 'w') as f:
        f.write(content)

    print(f"✅ Created: {file_path}")

def main():
    if len(sys.argv) < 2:
        print("❌ Error: Project name required")
        print("Usage: python init_qa_project_v2.py <project-name> [output-dir]")
        sys.exit(1)

    project_name = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."

    base_path = Path(output_dir).resolve()

    print(f"\n🚀 Initializing QA Project: {project_name}")
    print(f"   Location: {base_path}\n")

    # Create directory structure
    create_directory_structure(base_path)

    # Create tracking files
    create_test_execution_tracking(base_path, project_name)
    create_bug_tracking_template(base_path)

    # Create documentation
    create_baseline_metrics(base_path, project_name)
    create_progress_report_template(base_path)
    create_test_case_template(base_path)
    create_readme(base_path, project_name)

    print(f"\n✅ QA Project '{project_name}' initialized successfully!")
    print(f"\n📝 Next Steps:")
    print(f"   1. Review {base_path}/tests/docs/README.md")
    print(f"   2. Fill in BASELINE-METRICS.md with current project state")
    print(f"   3. Create test cases for your exercises using TEST-CASE-TEMPLATE.md")
    print(f"   4. Run automated testing: /qa /path/to/exercise/")

if __name__ == "__main__":
    main()
