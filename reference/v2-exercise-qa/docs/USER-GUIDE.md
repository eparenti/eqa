# Exercise QA 2 - User Guide

Professional automated testing for Red Hat Training exercises.

## Quick Start

```bash
# Test a lesson by code
/exercise-qa AU0024L

# Test a specific exercise
/exercise-qa AU0024L scale-files

# Test from lesson directory
/exercise-qa ~/git-repos/active/AU294-lessons/AU0024L

# Test from EPUB
/exercise-qa ~/git-repos/active/AU294/AU294.epub
```

## How It Works

### 1. Input Resolution

The skill accepts three types of input:

**Lesson Code**: `AU0024L`
- Searches `~/git-repos/active/` for matching directory
- Example: `/exercise-qa AU0024L`

**Lesson Directory**: Full path to lesson repo
- Example: `/exercise-qa ~/git-repos/active/AU294-lessons/AU0024L`

**EPUB File**: Full path to course EPUB
- Example: `/exercise-qa ~/git-repos/active/AU294/AU294.epub`

### 2. Automatic EPUB Building

If no EPUB is found in the lesson directory:

1. Checks for existing EPUB in:
   - Lesson root directory
   - `.cache/generated/en-US/`

2. If not found, automatically builds it:
   ```bash
   sk build epub3 -r <lesson-path>
   ```

3. Uses the generated EPUB for testing

**Requirements:**
- Scaffolding tools installed at `~/git-repos/active/scaffolding`
- `sk` command available

### 3. Exercise Detection

Parses EPUB to find exercises:

- **Guided Exercises**: Sections ending with `-ge`
- **Labs**: Sections ending with `-lab`

For each exercise, locates:
- Solution files in `materials/labs/<exercise>/solutions/`
- Grading script in `classroom/grading/src/<lesson>/`
- Materials directory

### 4. Test Execution

Runs test categories in order:

#### TC-PREREQ: Prerequisites
- SSH connectivity to workstation
- Required tools (ansible, python3, git)
- Lab hosts reachable (servera, serverb, etc.)
- Execution environments available

#### TC-SOL: Solution Files
- Solution files exist
- Have correct syntax (.yml files)
- Follow naming conventions (.sol extension)

#### TC-GRADE: Grading Validation
- Grading works WITH solution (100/100)
- Grading works WITHOUT solution (0/100)
- Error messages are clear and actionable

#### Future Categories
- TC-CLEAN: Cleanup validation
- TC-IDEM: Idempotency testing
- TC-EXEC: EPUB execution
- TC-WORKFLOW: Automated workflows
- TC-VERIFY: Verification steps
- TC-AAP: AAP Controller testing
- TC-E2E: End-to-end testing

### 5. Report Generation

Generates comprehensive report:

**Location**: `~/.claude/skills/exercise-qa-2/results/`

**Format**: Markdown file with:
- Summary (pass rate, bugs found)
- Detailed bug list with severity
- Fix recommendations
- Verification steps

**Example**:
```
QA-AU0024L-20260203-120000.md
```

## Test Results

### Understanding Output

**Per-Test Category:**
```
✓ PASS TC-PREREQ (2.3s)
✗ FAIL TC-SOL (5.1s)
   [P1] Solution file 'playbook.yml.sol' has syntax errors
```

**Overall Status:**
```
Overall: PASS (3/3 categories passed)
```

### Bug Severity Levels

- **P0 (Blocker)**: Prevents testing (SSH failure, missing exercise)
- **P1 (Critical)**: Core functionality broken (grading fails, solution doesn't work)
- **P2 (High)**: Important but not blocking (poor error messages, performance issues)
- **P3 (Low)**: Minor issues (naming conventions, cosmetic problems)

### Exit Codes

- `0`: All tests passed
- `1`: Some tests failed

## Common Scenarios

### Scenario 1: Test New Exercise

```bash
# After creating a new exercise
/exercise-qa AU0024L new-exercise-name

# Check report for issues
cat ~/.claude/skills/exercise-qa-2/results/QA-*.md
```

### Scenario 2: Validate Fixes

```bash
# After fixing bugs
/exercise-qa AU0024L problem-exercise

# Verify issues are resolved
```

### Scenario 3: Full Lesson QA

```bash
# Test all exercises in lesson
/exercise-qa ~/git-repos/active/AU294-lessons/AU0024L

# Review comprehensive report
```

### Scenario 4: EPUB-Only Testing

```bash
# Test from published EPUB
/exercise-qa ~/git-repos/active/AU294/AU294.epub

# Useful for final validation before release
```

## Prerequisites

### System Requirements

- **Python**: 3.9 or higher
- **SSH Access**: To `workstation` host
- **Scaffolding**: Installed at `~/git-repos/active/scaffolding`

### Python Packages

Install required packages:
```bash
pip install pexpect beautifulsoup4 lxml pyyaml
```

### SSH Configuration

Configure SSH access to workstation:

```bash
# ~/.ssh/config
Host workstation
    HostName workstation.lab.example.com
    User student
    IdentityFile ~/.ssh/id_rsa
```

Test connectivity:
```bash
ssh workstation
```

## Troubleshooting

### Issue: "sk tool not found"

**Solution**:
```bash
# Install scaffolding
cd ~/git-repos/active
git clone git@github.com:RedHatTraining/scaffolding.git
```

### Issue: "SSH connection failed"

**Solution**:
1. Check workstation is running
2. Verify SSH keys: `ssh student@workstation`
3. Check network connectivity

### Issue: "No exercises found"

**Solution**:
1. Check EPUB contains exercise sections
2. Verify sections have IDs ending in `-ge` or `-lab`
3. Try rebuilding EPUB: `sk build epub3`

### Issue: "Solution files not found"

**Solution**:
1. Check `materials/labs/<exercise>/solutions/` exists
2. Verify .sol files are present
3. Check file permissions

## Command-Line Options

### Testing Modes

| Flag | Description |
|------|-------------|
| `--e2e` | E2E mode: focused test set (TC-PREREQ, TC-E2E, TC-WORKFLOW, TC-CLEAN) |
| `--quick` | Skip expensive tests (TC-IDEM, TC-ROLLBACK, TC-E2E, TC-PERF) |
| `--full-course` | Test all exercises (ignore exercise filter) |
| `--tests TC-X,TC-Y` | Run only specified test categories |
| `--skip TC-X,TC-Y` | Skip specified test categories |

### Output Options

| Flag | Description |
|------|-------------|
| `--format markdown` | Markdown report (default) |
| `--format json` | JSON report |
| `--format junit` | JUnit XML (for CI) |
| `--format csv` | CSV format |
| `--format all` | All formats |
| `--no-color` | Disable colorized output |
| `--quiet` | Suppress console output |
| `-o PATH` | Specify output path |

### CI Integration

| Flag | Description |
|------|-------------|
| `--ci` | CI mode: JUnit output, quiet console, no colors |
| `--cache-results` | Cache passing test results |
| `--no-cache` | Disable all caching |

### Simulation Control

| Flag | Description |
|------|-------------|
| `--skip-student-sim` | Skip student simulation phase |
| `--force-qa` | Run QA even if simulation fails |
| `--student-only` | Run only student simulation |

### Timeouts

| Flag | Default | Description |
|------|---------|-------------|
| `--timeout-build` | 600s | EPUB build timeout |
| `--timeout-lab` | 300s | Lab start/finish timeout |
| `--timeout-command` | 120s | Individual command timeout |

## Live Lab Testing Workflow

### 1. Prepare Environment

```bash
# Ensure lab environment is accessible
ssh workstation

# Verify lab command works
lab status
```

### 2. Run E2E Tests

```bash
# Test single exercise with E2E mode
/exercise-qa AU0024L scale-files --e2e

# Test entire lesson with quick mode
/exercise-qa ~/git-repos/active/AU294-lessons/AU0024L --quick
```

### 3. Review Results

```bash
# Check the generated report
cat ~/.claude/skills/exercise-qa-2/results/QA-*.md

# Look for AI diagnostics section for automated fix suggestions
```

### 4. Fix Issues

Address bugs by priority:
1. **P0 (Blocker)** - Fix immediately
2. **P1 (Critical)** - Fix before release
3. **P2 (High)** - Should fix before release
4. **P3 (Low)** - Fix if time permits

### 5. Verify Fixes

```bash
# Re-run tests after fixing
/exercise-qa AU0024L scale-files --tests TC-SOL,TC-GRADE
```

## Technology-Specific Guidance

### Network Device Courses

For courses with Cisco, Juniper, or Arista devices:

```bash
# The tool auto-detects network devices and adjusts timeouts
/exercise-qa ~/git-repos/active/NET-lessons/lesson

# Device detection uses:
# - Inventory variables (ansible_network_os)
# - SSH banner analysis
# - Timeout multipliers: 2.0x-2.5x for network devices
```

### AAP Controller Courses

For AAP/Tower courses:

```bash
# TC-AAP validates controller configuration
/exercise-qa ~/git-repos/active/DO-lessons/lesson --tests TC-AAP

# Checks:
# - Controller connectivity
# - Credential configuration
# - Project/inventory setup
```

### Execution Environment Courses

For EE-based courses:

```bash
# TC-EE validates execution environment
/exercise-qa ~/git-repos/active/DO-lessons/lesson --tests TC-EE

# Checks:
# - ansible-navigator availability
# - Container runtime (podman/docker)
# - EE images availability
# - Registry connectivity
```

### DynoLabs v5 Courses

For courses using DynoLabs v5:

```bash
# Auto-detects Rust CLI or Python DynoLabs
/exercise-qa ~/git-repos/active/DO-lessons/lesson

# Detection:
# - Rust CLI: ELF binary with 'autotest' capability
# - Python: uv + ~/grading/pyproject.toml
```

## Best Practices

### 1. Test Early and Often

Run QA while developing:
```bash
# After creating solution
/exercise-qa AU0024L exercise-name

# After creating grading
/exercise-qa AU0024L exercise-name

# Before committing
/exercise-qa ~/git-repos/active/AU294-lessons/AU0024L
```

### 2. Fix High-Severity First

Address bugs in priority order:
1. P0 (Blocker) - Prevents any testing
2. P1 (Critical) - Core functionality broken
3. P2 (High) - Important quality issues
4. P3 (Low) - Minor polish

### 3. Verify Fixes

After fixing issues:
```bash
# Re-run tests
/exercise-qa AU0024L exercise-name

# Confirm bugs are resolved
```

### 4. Keep EPUBs Updated

Rebuild EPUB after content changes:
```bash
cd ~/git-repos/active/AU294-lessons/AU0024L
~/git-repos/active/scaffolding/sk build epub3
```

## Support

For issues or questions:
- Check [ARCHITECTURE.md](ARCHITECTURE.md) for technical details
- See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common problems and solutions
- See [TEST-CATEGORIES.md](TEST-CATEGORIES.md) for test category reference
- Review [DEVELOPMENT.md](DEVELOPMENT.md) for extending the skill

## License

Proprietary - Red Hat Training Internal Use
