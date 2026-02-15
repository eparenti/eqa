# Course Book Student Workflow Testing

**Purpose**: Test exercises from the student perspective using course book instructions as the primary source of truth.

---

## ⚠️ CRITICAL REQUIREMENT ⚠️

**MANDATORY EXECUTION IN LAB ENVIRONMENT**

This testing methodology REQUIRES actual execution in the lab environment.

**YOU MUST**:
- ✅ Actually run `lab start` command
- ✅ Actually create files as instructed in course book
- ✅ Actually execute playbooks with ansible-navigator
- ✅ Actually verify results on managed hosts
- ✅ Actually run solution files
- ✅ Actually test idempotency
- ✅ Document ACTUAL results (not assumptions)

**YOU MUST NOT**:
- ❌ Do static analysis only (reading files without running them)
- ❌ Assume lab scripts work without testing
- ❌ Assume playbooks work because YAML looks correct
- ❌ Skip execution and assume "looks good"
- ❌ Report PASS without actually running tests

**If you cannot access the lab environment, STOP and request access.**
**If you skip execution, your QA report is INVALID.**

---

## Overview

Traditional QA testing focuses on solution files. This approach misses bugs in:
- Course book instructions (unclear, wrong, or missing steps)
- Lab script deployment (missing files, wrong permissions)
- Supporting files (configs, templates with errors)
- Mismatch between instructions and solutions

Test as a student would, following the course book exactly IN THE ACTUAL LAB.

---

## Testing Philosophy

### Student First Perspective

**Key Principle**: A student has ONLY:
1. The course book (EPUB) with instructions
2. Files deployed by `lab start` command to `~/exercise-name/`
3. Access to workstation and managed hosts

**What students DON'T have**:
- Direct access to solution files, except once they are downloaded to the local machine by the lab script
- Knowledge of git repo structure
- Understanding of lab script internals
- Ability to fix deployment issues

**Therefore**: QA must test from this limited perspective to find real student-facing bugs.

---

## Component Architecture

### 1. Course Book (EPUB)
**Location**: `/home/eparenti/git-repos/active/<ANSIBLE-COURSE>/<ANSIBLE-COURSE>-RHAAP2.5-en-2.epub`

**Contains**:
- Chapter content and theory
- Guided exercises with step-by-step instructions
- Lab exercises with objectives and outcomes
- Troubleshooting exercises (intentional errors)

**Example Structure**:
```
Chapter 2: Introduction to Developing Automation Content
  Section 2.1: Managing Ansible Configuration Files
  Section 2.2: Guided Exercise: <exercise-name>
    - Objectives
    - Instructions (Step 1, Step 2, Step 3...)
    - Evaluation criteria
  Section 2.3: Guided Exercise: develop-inventory
    ...
```

**How to Extract**:
```bash
# Use Python ebooklib or similar
# Parse HTML from EPUB
# Extract exercise section
# Identify step-by-step instructions
```

### 2. Lab Scripts
**Location**: `/home/eparenti/git-repos/active/AU00XXL/classroom/grading/src/au00xxl/`

**Files**:
- One Python file per exercise (e.g., `files-manage.py`)
- Uses lab framework for start/finish/grade functions

**Example Lab Script Structure**:
```python
#!/usr/bin/env python3

from labs.common import steps
from labs.grading import Default

# Exercise configuration
EXERCISE = "files-manage"
LESSON = "au0023l"

class FilesManage(Default):
    """Files Management Exercise"""

    __LAB__ = EXERCISE

    def start(self):
        """Setup exercise environment"""
        # Copy materials from repo to student directory
        self.copy_materials('ansible.cfg')
        self.copy_materials('ansible-navigator.yml')
        self.copy_materials('inventory')
        self.copy_materials('files/')
        # Maybe create /home/student/files-manage/

    def finish(self):
        """Cleanup exercise"""
        self.remove_materials()

    def grade(self):
        """Grade student solution"""
        # Check if tasks completed correctly
        pass
```

**Key Functions**:
- `start()`: Deploy files to `~/exercise-name/` (student home directory)
- `finish()`: Clean up deployed files
- `grade()`: Verify student solution (if implemented)

**What to Check**:
- Which files get deployed?
- Where do they come from? (materials/labs/exercise-name/)
- Where do they go? (~/exercise-name/ in student home)
- Any special permissions or ownership set?
- Any prerequisites created (users, directories)?

### 3. Materials Directory
**Location**: `/home/eparenti/git-repos/active/AU00XXL/materials/labs/<exercise>/`

**Structure**:
```
files-manage/
├── ansible.cfg          # Deployed to /home/student/files-manage/
├── ansible-navigator.yml
├── inventory
├── files/               # Directory with supporting files
│   ├── index.html
│   └── config.conf
├── templates/           # Jinja2 templates (if any)
│   └── motd.j2
└── solutions/           # NOT deployed to student (reference only)
    ├── site.yml.sol
    ├── inventory.sol
    └── ansible.cfg.sol
```

**Deployed Files** (what students get):
- Configuration files (ansible.cfg, ansible-navigator.yml)
- Inventory files
- Supporting files (files/, templates/)
- Starter files (partially completed playbooks)

**NOT Deployed** (students don't see):
- solutions/ directory
- Development files (.git, README.md)

### 4. Student Environment
**Location**: `~/exercise-name/` (student home directory)

**Created by**:
1. First: `lab force <lesson-code>` - Installs lab scripts for chapter
2. Then: `lab start <exercise-name>` - Deploys exercise files

**Contains**:
- Files deployed by lab script (from materials/labs/exercise/)
- Student's work (files they create/modify following course book)

**Example**:
```
~/files-manage/
├── ansible.cfg              # Deployed by lab script
├── ansible-navigator.yml    # Deployed by lab script
├── inventory                # Deployed by lab script
├── files/                   # Deployed by lab script
│   └── index.html
└── site.yml                 # Created by student following course book
```

---

## Testing Process

### PHASE 1: Course Book Extraction

#### Step 1.1: Locate Exercise Section

**Example**: For "<exercise-name>" exercise:
```
Course: <ANSIBLE-COURSE>-RHAAP2.5-en-2.epub
Chapter: 2 - Introduction to Developing Automation Content
Section: Guided Exercise: <exercise-name>
```

**Tools**:
```bash
# Extract EPUB (it's a ZIP file)
unzip -d /tmp/epub <ANSIBLE-COURSE>-RHAAP2.5-en-2.epub

# Find exercise section
grep -r "<exercise-name>" /tmp/epub/

# Parse HTML to extract instructions
python3 parse_exercise.py --exercise <exercise-name>
```

#### Step 1.2: Parse Instructions

**Extract**:
1. Exercise title and objectives
2. Step-by-step instructions
3. Expected outcomes
4. Troubleshooting notes
5. Evaluation criteria

**Example Parsed Output**:
```yaml
exercise:
  name: <exercise-name>
  title: "Guided Exercise: Writing a Simple Playbook"
  objectives:
    - "Create a single-play Ansible playbook"
    - "Deploy a web page to managed hosts"

  instructions:
    - step: 1
      text: "Create a new playbook named site.yml"
      command: null
      expected: "Playbook file exists"

    - step: 2
      text: "Add a play targeting servera and serverb"
      command: null
      expected: "Play defined with hosts: web"

    - step: 3
      text: "Add a task to install httpd package"
      command: null
      expected: "Task uses ansible.builtin.package module"

    - step: 4
      text: "Add a task to copy index.html from files/ directory"
      command: null
      expected: "Task uses ansible.builtin.copy module"

    - step: 5
      text: "Run the playbook with ansible-navigator"
      command: "ansible-navigator run site.yml -m stdout"
      expected: "ok=3 changed=2 unreachable=0 failed=0"

  intentional_errors: []

  evaluation:
    - "Playbook runs without errors"
    - "Web page accessible on servera and serverb"
```

#### Step 1.3: Identify Intentional Errors

**Keywords to search for**:
- "intentional error"
- "troubleshoot"
- "fix the following"
- "debug this"
- "the file contains an error"

**Example**:
```markdown
### Guided Exercise: develop-troubleshoot

Step 3: The ansible.cfg file contains an intentional configuration error.
        Debug the configuration to find and fix the error.

NOTE: This is a troubleshooting exercise. The error is intentional.
```

**Action**: Document as INTENTIONAL-ERROR, not a bug.

---

### PHASE 2: Lab Script Analysis

#### Step 2.1: Locate Lab Script

**Pattern**: `/home/eparenti/git-repos/active/AU00XXL/classroom/grading/src/au00xxl/<exercise>.py`

**Example**:
```bash
# For files-manage exercise in AU0023L
cd /home/eparenti/git-repos/active/AU0023L
find . -name "files-manage.py"
# Result: ./classroom/grading/src/au0023l/files-manage.py
```

#### Step 2.2: Analyze start() Function

**Read the code**:
```python
def start(self):
    """Setup exercise environment"""
    # What gets deployed?
    self.copy_materials('ansible.cfg')
    self.copy_materials('ansible-navigator.yml')
    self.copy_materials('inventory')
    self.copy_materials('files/')
    self.copy_materials('templates/')  # Check if this exists
```

**Questions to Answer**:
1. What files are deployed?
2. Are directories copied (files/, templates/)?
3. Are there any prerequisites created (users, groups)?
4. Where do files come from? (materials/labs/<exercise>/)
5. Where do they go? (/home/student/<exercise>/)

**Create Deployment Map**:
```yaml
deployment:
  source: /home/eparenti/git-repos/active/AU0023L/materials/labs/files-manage/
  destination: /home/student/files-manage/

  files_deployed:
    - ansible.cfg
    - ansible-navigator.yml
    - inventory
    - files/index.html
    - files/config.conf
    - templates/motd.j2

  prerequisites:
    users: []
    groups: []
    directories: []
```

#### Step 2.3: Check for Deployment Issues

**Common Problems**:
1. Missing `copy_materials()` call for required files
2. Wrong source path
3. Missing directory creation
4. Wrong permissions on deployed files

**Example Bug**:
```python
# Lab script (WRONG):
def start(self):
    self.copy_materials('ansible.cfg')
    self.copy_materials('inventory')
    # Missing: self.copy_materials('templates/')
```

**Impact**: Course book step 5 says "use template templates/motd.j2" but file not deployed!

**Bug Report**:
```
BUG-LAB-001: templates/ directory not deployed
Component: Lab script (files-manage.py:25)
Severity: P0
Impact: Student cannot complete step 5
Fix: Add self.copy_materials('templates/')
```

---

### PHASE 3: Student Workflow Testing

**MANDATORY**: Execute EVERY step in the actual lab environment!

#### Step 3.1: Setup Environment (EXECUTE, don't skip!)

```bash
# 1. Install lab scripts for chapter - ACTUALLY DO THIS
ssh workstation "lab force <lesson-code>"
# Example: ssh workstation "lab force au0023l"

# 2. Start exercise - ACTUALLY DO THIS
ssh workstation "lab start <exercise-name>"
# Example: ssh workstation "lab start files-manage"

# 3. Verify deployment - ACTUALLY DO THIS
ssh workstation "ls -la ~/<exercise-name>/"
# Example: ssh workstation "ls -la ~/files-manage/"

# Expected output:
# ansible.cfg, ansible-navigator.yml, inventory, solutions/
# Any other files/directories specified in lab script
```

**VERIFY ACTUAL OUTPUT** - Check against lab script expectations.

**If output doesn't match expectations**: REPORT BUG-LAB (deployment issue)
**If files missing**: REPORT BUG-LAB (missing deployment)

#### Step 3.2: Follow Course Book Steps

**For EACH step in course book**:

1. Read the instruction
2. Execute EXACTLY as student would
3. Check result against expected outcome
4. Document: PASS / FAIL

**Example Test Execution**:

**Course Book Step 1**: "Create a new playbook named site.yml"
```bash
# Student action:
ssh workstation "cd /home/student/files-manage && touch site.yml"

# Test:
ssh workstation "ls /home/student/files-manage/site.yml"
# Result: ✅ PASS (file exists)
```

**Course Book Step 2**: "Add a play targeting web hosts"
```bash
# Student action: Edit site.yml
# Course book provides example YAML

# Test: Check if example YAML is valid
ssh workstation "cd /home/student/files-manage && ansible-navigator run site.yml --syntax-check -m stdout"
# Result: ✅ PASS / ❌ FAIL
```

**Course Book Step 3**: "Add a task to copy files/index.html"
```bash
# Student follows course book instruction

# Test: Does files/index.html exist?
ssh workstation "ls /home/student/files-manage/files/index.html"
# Result: ✅ PASS (file exists)

# Test: Can task reference it correctly?
# Course book might say: src: files/index.html
# OR: src: ../files/index.html
# This depends on where playbook is executed from
```

**Course Book Step 4**: "Run the playbook"
```bash
# Student action:
ssh workstation "cd /home/student/files-manage && ansible-navigator run site.yml -m stdout"

# Expected (from course book):
# ok=3 changed=2 unreachable=0 failed=0

# Actual result:
# Check output
```

#### Step 3.3: Document Results

**For Each Step**:
```yaml
step_results:
  - step: 1
    instruction: "Create a new playbook named site.yml"
    student_action: "touch site.yml"
    expected: "File exists"
    actual: "File created successfully"
    result: PASS

  - step: 2
    instruction: "Add a play targeting web hosts"
    student_action: "Edit site.yml with provided YAML"
    expected: "Valid YAML syntax"
    actual: "Syntax check passed"
    result: PASS

  - step: 3
    instruction: "Add a task to copy files/index.html"
    student_action: "Add copy task to playbook"
    expected: "Task added successfully"
    actual: "ERROR: files/index.html not found"
    result: FAIL
    bug: BUG-BOOK-001
```

#### Step 3.4: Classify Failures

**When step fails, determine WHY**:

**A. Course Book Issue**:
- Instruction is wrong or unclear
- Referenced file doesn't exist
- Command syntax is incorrect
- Steps are out of order

**B. Lab Script Issue**:
- Required file not deployed
- Wrong permissions on deployed files
- Directory structure wrong

**C. Supporting File Issue**:
- Deployed file has wrong content
- Configuration file has errors
- Template syntax broken

**D. Student Error (Not a Bug)**:
- Student might misread instruction
- Document as "requires careful reading"

**E. Intentional Error (Not a Bug)**:
- Course book explicitly mentions error
- Part of troubleshooting exercise

---

### PHASE 4: Solution Testing

**After** testing student workflow, test solutions.

#### Step 4.1: Locate Solutions

**Location**: `/home/eparenti/git-repos/active/AU00XXL/materials/labs/<exercise>/solutions/`

```bash
# List solutions
ls -la /home/eparenti/git-repos/active/AU0023L/materials/labs/files-manage/solutions/
# Output:
# file-operations.yml.sol
# vsftpd-server.yml.sol
```

#### Step 4.2: Deploy Solutions

```bash
# Copy to student environment
ssh workstation "cd /home/student/files-manage && cp /path/to/solutions/site.yml.sol site.yml"

# Or if testing locally:
cd /home/student/files-manage
for f in solutions/*.sol; do
    cp "$f" "${f%.sol}"
done
```

#### Step 4.3: Test Solutions

```bash
# Run solution
ssh workstation "cd /home/student/files-manage && ansible-navigator run site.yml -m stdout"

# Expected: Solution should work perfectly
# Actual: Check for errors
```

#### Step 4.4: Compare to Course Book

**Questions**:
1. Does solution match what course book teaches?
2. Does solution use same modules as course book examples?
3. Does solution follow same approach?

**Example Mismatch**:
```yaml
# Course book teaches:
- name: Copy file
  ansible.builtin.copy:
    src: files/index.html
    dest: /var/www/html/

# Solution uses:
- name: Copy file
  ansible.builtin.template:  # DIFFERENT MODULE
    src: templates/index.j2
    dest: /var/www/html/
```

**Classification**:
- If both work: Document as alternative approach
- If solution doesn't match teaching: BUG-SOL-XXX (P2 - pedagogical issue)

---

## Bug Classification Matrix

### Bug Type vs Component

| Bug Type | Component | Severity | Example |
|----------|-----------|----------|---------|
| Missing file referenced | Course Book | P0 | "Step 3: Use template.j2" but file not deployed |
| Unclear instruction | Course Book | P1-P2 | "Run the command" (which command?) |
| Wrong command syntax | Course Book | P0 | Command has typo or wrong options |
| File not deployed | Lab Script | P0 | start() missing copy_materials() |
| Wrong permissions | Lab Script | P0-P1 | File deployed as root, not student |
| Missing prerequisite | Lab Script | P0 | User must exist but not created |
| Config file error | Supporting File | P1 | ansible.cfg wrong inventory path |
| Template syntax error | Supporting File | P1 | Jinja2 template has {{variable} (missing }) |
| Solution doesn't work | Solution File | P1 | Solution fails when executed |
| Solution wrong approach | Solution File | P2 | Uses different method than taught |
| Intentional error | Any | TEACH | Documented in course book for learning |

### Severity Definitions

**P0 (Blocker)**: Student cannot proceed
- Course book step fails
- Required file missing
- Command doesn't work
- Environment broken

**P1 (Critical)**: Solution wrong or major confusion
- Solution file doesn't work
- Instruction very unclear
- Config file has error
- Wrong approach taught

**P2 (Minor)**: Cosmetic or minor issues
- Typo in course book
- Alternative approach used
- Inconsistent terminology
- Formatting issue

**TEACH (Intentional)**: Not a bug, teaching exercise
- Explicitly documented in course book
- Purpose: Teach troubleshooting
- Action: Document, don't fix

---

## Report Generation

### Comprehensive Report Structure

```markdown
# QA Report: <Exercise Name>

## Executive Summary
- **Exercise**: <exercise-name>
- **Lesson Code**: <lesson-code>
- **Lab Script**: AU0020L/classroom/grading/src/<lesson-code>/<exercise-name>.py
- **Course Book**: Chapter 2, Section 2.2
- **Test Date**: 2026-01-05
- **Status**: ✅ PASS / ⚠️ ISSUES / ❌ BLOCKED

## Component Testing

### 1. Course Book Instructions
- **Total Steps**: 8
- **Steps Passed**: 6
- **Steps Failed**: 2
- **Intentional Errors**: 0

| Step | Instruction | Result | Notes |
|------|-------------|--------|-------|
| 1 | Create playbook | ✅ PASS | Clear instruction |
| 2 | Define play | ✅ PASS | Example provided |
| 3 | Add package task | ✅ PASS | Works as written |
| 4 | Add copy task | ❌ FAIL | BUG-BOOK-001: Wrong file path |
| 5 | Run playbook | ❌ FAIL | Fails due to step 4 |
| 6 | Verify results | ⏭️ SKIP | Cannot test (step 5 failed) |

### 2. Lab Script Deployment
- **Script**: AU0020L/classroom/grading/src/<lesson-code>/<exercise-name>.py
- **Expected Files**: 5
- **Deployed Files**: 4
- **Issues**: 1

**Deployment Analysis**:
```python
def start(self):
    self.copy_materials('ansible.cfg')         # ✅ Deployed
    self.copy_materials('ansible-navigator.yml') # ✅ Deployed
    self.copy_materials('inventory')           # ✅ Deployed
    self.copy_materials('files/')              # ✅ Deployed
    # ❌ MISSING: self.copy_materials('solutions/')
```

**Bugs**:
- BUG-LAB-001: solutions/ directory not deployed (not a bug - intentional)
- All required files deployed correctly

### 3. Supporting Files
| File | Path | Status | Issues |
|------|------|--------|--------|
| ansible.cfg | /home/student/<exercise-name>/ | ✅ VALID | None |
| inventory | /home/student/<exercise-name>/ | ✅ VALID | None |
| files/index.html | /home/student/<exercise-name>/files/ | ✅ EXISTS | None |

### 4. Solution Files
| Solution | Status | Matches Book? | Issues |
|----------|--------|---------------|--------|
| site.yml.sol | ❌ FAILS | ❌ NO | BUG-SOL-001: Wrong file path |

**Solution Testing**:
```bash
# Test: ansible-navigator run site.yml -m stdout
# Expected: ok=3 changed=2 failed=0
# Actual: ok=1 changed=0 failed=1

# Error:
# fatal: [servera]: FAILED! => {
#   "msg": "Could not find or access 'files/index.html'"
# }
```

**Root Cause**: Solution references `files/index.html` but should be `../files/index.html`

## Bugs Found

### BUG-BOOK-001: File path instruction incorrect
- **Component**: Course book, Step 4
- **Severity**: P0 (Blocker)
- **Description**: Course book instructs "src: files/index.html" but from solutions/ subdirectory, path should be "../files/index.html"
- **Impact**: Student following instructions will get file not found error
- **Location**: Chapter 2, Section 2.2, Step 4
- **Fix**: Update course book to clarify: "src: ../files/index.html when playbook in subdirectory"

### BUG-SOL-001: Solution file path error
- **Component**: Solution file (site.yml.sol)
- **Severity**: P1 (Critical)
- **Description**: Solution uses wrong relative path for files/
- **Impact**: Solution doesn't work when tested
- **Location**: /materials/labs/<exercise-name>/solutions/site.yml.sol
- **Fix**: Change line 8 from `src: files/index.html` to `src: ../files/index.html`

## Intentional Errors
*None found in this exercise*

## Student Experience

### Can student complete exercise following course book?
**NO** - Step 4 instruction causes failure

### Are instructions clear?
**PARTIALLY** - Most steps clear, but file path instruction ambiguous

### Overall student experience
**POOR** - Student will be stuck at step 4

## Recommendations

### Immediate Fixes (P0)
1. **BUG-BOOK-001**: Update course book step 4 with correct file path instruction
2. Test update: Verify student can complete exercise after fix

### Important Fixes (P1)
1. **BUG-SOL-001**: Update solutions/site.yml.sol with correct path

### Course Improvements
1. Add note about relative paths when playbooks in subdirectories
2. Consider restructuring to avoid subdirectory confusion
3. Add troubleshooting tip for "file not found" errors

## Summary
- **Total Bugs**: 2 (P0: 1, P1: 1)
- **Intentional Errors**: 0
- **Student Experience**: POOR
- **Recommendation**: ❌ BLOCKED - Must fix BUG-BOOK-001 before release
```

---

## Best Practices

### DO:
- ✅ Always read course book first
- ✅ Parse ALL exercise instructions
- ✅ Examine lab script deployment
- ✅ Test as student would (no shortcuts)
- ✅ Test solutions separately
- ✅ Check for intentional errors
- ✅ Document all components tested
- ✅ Classify bugs by component
- ✅ Assess student experience

### DON'T:
- ❌ Skip to testing solutions only
- ❌ Assume deployment is correct
- ❌ Ignore course book instructions
- ❌ Report intentional errors as bugs
- ❌ Test from repo directory (use /home/student/)
- ❌ Mix student workflow and solution testing

---

## Common Patterns

### Pattern 1: File Path from Subdirectory
**Symptom**: Course book says `src: files/index.html` but student gets "file not found"

**Root Cause**: Playbook executed from subdirectory (e.g., solutions/)

**Classification**:
- If course book wrong: BUG-BOOK
- If solution wrong: BUG-SOL
- If both wrong: Both bugs

### Pattern 2: Missing Deployment
**Symptom**: Course book references file that doesn't exist

**Root Cause**: Lab script doesn't deploy the file

**Classification**: BUG-LAB (P0)

### Pattern 3: Config File Mismatch
**Symptom**: ansible.cfg has wrong inventory path

**Investigation**:
1. Check course book: Does it mention the error?
2. If YES → INTENTIONAL (troubleshooting exercise)
3. If NO → BUG-FILE (P1)

### Pattern 4: Solution Doesn't Match Teaching
**Symptom**: Solution uses different approach than course book

**Investigation**:
1. Does solution work? If NO → BUG-SOL (P1)
2. Does course book mention alternatives? If YES → Document
3. If NO → BUG-SOL (P2 - pedagogical issue)

---

## Testing Commands Reference

### Course Book Extraction
```bash
# Extract EPUB
unzip -d /tmp/epub /path/to/course.epub

# Find exercise
grep -r "exercise-name" /tmp/epub/

# Parse HTML (example)
python3 <<EOF
from bs4 import BeautifulSoup
with open('/tmp/epub/chapter2.html', 'r') as f:
    soup = BeautifulSoup(f, 'html.parser')
    exercise = soup.find('section', id='<exercise-name>')
    steps = exercise.find_all('div', class_='step')
    for i, step in enumerate(steps, 1):
        print(f"Step {i}: {step.get_text().strip()}")
EOF
```

### Lab Script Analysis
```bash
# Find lab script
find /home/eparenti/git-repos/active/AU00XXL -name "exercise-name.py"

# Read start() function
grep -A 20 "def start" /path/to/script.py

# Understand deployment
cat /path/to/script.py | grep "copy_materials"
```

### Student Environment Testing
```bash
# Start lab
ssh workstation "lab start au00xxl exercise-name"

# Verify deployment
ssh workstation "ls -laR /home/student/exercise-name/"

# Test as student
ssh workstation "cd /home/student/exercise-name && <command>"

# Clean up
ssh workstation "lab finish au00xxl exercise-name"
```

### Solution Testing
```bash
# Deploy solutions
ssh workstation "cd /home/student/exercise-name && for f in solutions/*.sol; do cp \"\$f\" \"\${f%.sol}\"; done"

# Test solution
ssh workstation "cd /home/student/exercise-name && ansible-navigator run playbook.yml -m stdout"
```

---

**Purpose**: Test exercises from student perspective, find bugs in all components
