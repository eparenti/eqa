# Exercise QA Framework - Comprehensive Guide

**Version:** 2.0.0 | [Changelog](../CHANGELOG.md)
**Last Updated:** 2026-01-10

Complete reference for Red Hat Training course exercise quality assurance testing.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Test Categories Reference](#test-categories-reference)
3. [Technology-Specific Testing](#technology-specific-testing)
4. [Quality Metrics & Performance](#quality-metrics--performance)
5. [Advanced Features](#advanced-features)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)

---

## Quick Start

### Running Full Course QA

```bash
# Auto-detect course and run all tests
exercise-qa

# Specify course code
exercise-qa --course DO288

# Test specific exercises
exercise-qa --exercise deploy-app --exercise configure-db

# Watch mode - re-run on file changes
exercise-qa <lesson-code> <exercise-name> --watch

# Disable colors (for CI/CD or piping)
exercise-qa <lesson-code> <exercise-name> --no-color
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--e2e` | Enable end-to-end testing |
| `--full-course` | Test all exercises in course |
| `--mode` | Testing mode: `sequential`, `parallel`, `smart` |
| `--watch` | Re-run tests when files change |
| `--no-color` | Disable colorized terminal output |
| `--no-cache` | Disable caching |
| `--output-dir` | Custom output directory for reports |
| `--verbose` | Enable verbose output (default) |
| `--quiet` | Disable verbose output |

### What Gets Tested

The framework automatically tests **all 15 test categories**:

| Category | What It Tests | Duration |
|----------|---------------|----------|
| **TC-PREREQ** | Lab start prerequisites | <30s |
| **TC-EXEC** | Command syntax validation (pre-flight) | <30s |
| **TC-SOL** | Solution files | <5min |
| **TC-GRADE** | Grading scripts | <2min |
| **TC-IDEM** | Idempotency (multi-cycle) | <10min |
| **TC-CLEAN** | Cleanup validation | <1min |
| **TC-E2E** | End-to-end independence | <30min |
| **TC-WORKFLOW** | Workflow validation | <3min |
| **TC-INSTRUCT** | Instruction quality | <1min |
| **TC-VERIFY** | Verification steps | <2min |
| **TC-SOLVE** | Solve scripts | <5min |
| **TC-AAP** | AAP Controller ops | <10min |
| **TC-SECURITY** | Security best practices | <2min |
| **TC-ACCESSIBILITY** | WCAG 2.2 compliance | <1min |
| **TC-CONTRACT** | Component alignment | <2min |

### Reading Results

Results are generated in `results/`:

```
results/
├── QA-REPORT-DO288-FULL-20260110-1430.md    # Markdown report
├── QA-REPORT-DO288-FULL-20260110-1430.json  # JSON results
└── QA-REPORT-DO288-FULL-20260110-1430-metrics.json  # Quality metrics
```

**Key sections in report:**
- **Executive Summary**: Pass/fail status, bug counts
- **Quality Metrics Dashboard**: Coverage, defect density, ROI
- **Performance Budget Compliance**: Timeout adherence
- **Release Readiness Assessment**: Ship/no-ship decision

---

## Test Categories Reference

### Core Functional Categories

#### TC-PREREQ: Prerequisites Validation
**Purpose:** Verify `lab start` creates correct initial state

**Checks:**
- Files created in correct locations
- Services started/stopped as specified
- Network connectivity established
- Dependencies installed

**Pass Criteria:**
- All prerequisite conditions met
- No errors in lab script output

---

#### TC-EXEC: Command Syntax Validation
**Purpose:** Pre-flight validation of EPUB commands before execution

**Process:**
1. Parse EPUB content for command blocks
2. Validate command syntax (quoting, escaping)
3. Check for dangerous patterns (rm -rf /, chmod 777)
4. Verify command structure without executing

**Checks Performed:**
- Unquoted variable expansions
- Dangerous file operations
- Insecure permission changes
- Syntax errors in command structure

**Pass Criteria:**
- No critical syntax issues
- No dangerous command patterns
- Commands properly structured

---

#### TC-WORKFLOW: EPUB Workflow Execution
**Purpose:** Execute EPUB instructions step-by-step on live systems

**Process:**
1. Parse EPUB content for procedural steps
2. Extract commands from each step
3. Execute commands via SSH
4. Verify expected outcomes

**Technology-Specific Execution:**
- **Ansible**: `ansible-navigator run playbook.yml`
- **OpenShift**: `oc apply -f manifest.yaml`
- **RHEL**: `ssh servera "systemctl start httpd"`

**Pass Criteria:**
- All steps execute successfully
- No command failures
- Expected state achieved

---

#### TC-SOL: Solution File Testing
**Purpose:** Validate solution files produce correct results

**Process:**
1. Find solution files (`*.sol` extension)
2. Copy to exercise directory, removing `.sol`
3. Execute using appropriate tool
4. Verify outcome matches EPUB verification section

**Solution File Formats by Technology:**

| Technology | Format | Execution |
|-----------|--------|-----------|
| Ansible | `*.yml.sol` | `ansible-navigator run playbook.yml` |
| OpenShift | `*.yaml.sol` | `oc apply -f deployment.yaml` |
| RHEL | `*.sh.sol`, `*.conf.sol` | `bash script.sh` or config copy |

**Pass Criteria:**
- Solution achieves expected outcome
- Grading passes (if lab exercise)
- No errors during execution

---

#### TC-GRADE: Grading Script Validation
**Purpose:** Verify grading scripts correctly validate exercise completion

**For Labs Only** (not Guided Exercises)

**Process:**
1. Complete exercise (via solutions or EPUB)
2. Run: `lab grade <exercise-id>`
3. Parse grading output
4. Verify all checks pass

**Pass Criteria:**
- Grading script exits 0 (success)
- All grading checks pass
- No false positives/negatives

---

#### TC-IDEM: Idempotency Testing
**Purpose:** Verify lab scripts are idempotent (can run multiple times)

**Process:**
1. Run: `lab start <exercise-id>`
2. Capture state (files, services, config)
3. Run: `lab start <exercise-id>` again
4. Capture state again
5. Compare states - must be identical

**Common Idempotency Violations:**
- Creating users/files without existence check
- Appending to files repeatedly
- Incrementing counters
- Timestamps in generated files

**Pass Criteria:**
- Second run produces identical state
- No errors on repeated execution
- Lab script is truly idempotent

---

#### TC-CLEAN: Cleanup Validation
**Purpose:** Verify `lab finish` restores clean state

**Process:**
1. Complete exercise
2. Run: `lab finish <exercise-id>`
3. Verify all exercise artifacts removed
4. Verify services restored to pre-exercise state

**Pass Criteria:**
- All exercise files removed
- Services stopped/disabled
- Configuration changes reverted
- System ready for next exercise

---

#### TC-E2E: End-to-End Independence
**Purpose:** Verify exercise works in isolation (no dependencies on previous exercises)

**Process:**
1. Start from clean lab environment
2. Run only this exercise (skip all previous)
3. Verify completes successfully

**Pass Criteria:**
- Exercise completes without prior exercises
- No missing dependencies
- No assumptions about previous state

---

### Quality & Analysis Categories

#### TC-WORKFLOW: Workflow Validation
**Purpose:** Verify exercise workflow is logical and complete

**Checks:**
- Prerequisites clearly documented
- Steps in logical order
- No missing steps
- Verification instructions provided

**Pass Criteria:**
- Workflow is complete and coherent
- Student can follow without confusion

---

#### TC-INSTRUCT: Instruction Quality
**Purpose:** Analyze instruction quality and clarity

**Checks:**
- Commands are accurate and complete
- File paths are correct
- Technology-appropriate tools used
- Clear success/failure indicators

**Pass Criteria:**
- Instructions are clear and accurate
- No ambiguous or missing details

---

#### TC-VERIFY: Verification Steps
**Purpose:** Validate verification steps work correctly

**Process:**
1. Complete exercise
2. Execute verification steps from EPUB
3. Confirm expected results appear

**Pass Criteria:**
- Verification steps produce expected output
- Success indicators work correctly

---

#### TC-SOLVE: Solve Script Testing
**Purpose:** Test solve scripts (auto-complete scripts)

**Process:**
1. Start clean environment
2. Run: `lab solve <exercise-id>`
3. Verify exercise is completed
4. Run grading to confirm

**Pass Criteria:**
- Solve script completes exercise correctly
- Grading passes after solve

---

### Technology-Specific Categories

#### TC-AAP: Automation Controller Testing
**Purpose:** Validate AAP Controller operations

**For Automation Controller (AAP) Courses**

**Checks:**
- Controller API connectivity
- Job template execution
- Workflow execution
- Inventory sync
- Credential validation

**Pass Criteria:**
- Controller operations complete successfully
- Jobs finish with success status

---

### Security & Compliance Categories

#### TC-SECURITY: Security Best Practices
**Purpose:** Detect security anti-patterns (P2/P3 suggestions)

**Checks:**
- Hardcoded credentials (use Ansible Vault instead)
- Insecure file permissions (777, 666)
- Passwordless sudo configurations
- Secrets in files

**Severity:** P2_HIGH or P3_LOW (improvement suggestions, not blockers)

**Pass Criteria:**
- No security anti-patterns found
- Best practices followed

---

#### TC-ACCESSIBILITY: WCAG 2.2 Compliance
**Purpose:** Validate accessibility compliance (P2/P3 suggestions)

**Standards:** WCAG 2.2, EN 301 549

**Checks:**
- Images have alt text
- Proper heading hierarchy (h1→h2→h3)
- Keyboard navigation instructions
- Screen reader compatibility (table headers, etc.)

**Severity:** P2_HIGH or P3_LOW (improvement suggestions, not blockers)

**Pass Criteria:**
- No accessibility issues found
- Meets WCAG 2.2 Level A

---

#### TC-CONTRACT: Component Contract Validation
**Purpose:** Verify EPUB ↔ Solutions ↔ Grading alignment

**Checks:**
- Files mentioned in EPUB exist in solutions
- Resources described in EPUB are created by solutions
- Grading validates what solutions create
- Component complexity alignment

**Pass Criteria:**
- All components aligned
- No mismatches between EPUB, solutions, grading

---

## Technology-Specific Testing

### Ansible Courses (AU*)

**Solution Format:** `*.yml.sol` (playbooks)
**Execution:** `ansible-navigator run playbook.yml -m stdout`

**Verification:**
- Option 1: Run verify playbooks (`verify_*.yml`)
- Option 2: Follow EPUB verification steps

**Grading:** `lab grade <exercise-name>`

**Common Issues:**
- Missing collections (`ansible.posix`, `community.*`)
- YAML syntax errors
- Inventory configuration
- Privilege escalation (`become: true`)

---

### OpenShift/Kubernetes (DO*)

**Solution Format:** `*.yaml.sol` (manifests)
**Execution:** `oc apply -f deployment.yaml`

**Verification:**
```bash
oc get pods -n namespace
oc get svc -n namespace
curl http://route-url
```

**Grading:** `lab grade <exercise-name>`

**Common Issues:**
- Resource not found (wrong namespace)
- RBAC permissions (user can't create resource)
- Image pull errors
- Routes not accessible (DNS, firewall)

---

### RHEL System Administration (RH*)

**Solution Format:** Scripts (`.sh.sol`), configs (`.conf.sol`)
**Execution:** Via SSH

```bash
cp solutions/script.sh.sol script.sh
ssh servera "bash ~/exercise-directory/script.sh"
```

**Verification:**
```bash
ssh servera "systemctl status httpd"
ssh servera "cat /etc/myapp.conf"
ssh servera "firewall-cmd --list-services"
```

**Grading:** `lab grade <exercise-name>`

**Common Issues:**
- Service not found (package not installed)
- Permission denied (need sudo)
- SELinux context issues
- Firewall blocking

---

### Satellite Courses

**Solution Format:** `hammer` CLI commands, API calls
**Execution:**
```bash
hammer content-view create --name "myCV" --organization "MyOrg"
hammer content-view publish --name "myCV" --organization "MyOrg"
```

**Verification:**
```bash
hammer content-view list --organization "MyOrg"
```

**Common Issues:**
- hammer CLI not configured
- Authentication failures
- Organization/location context wrong

---

## Quality Metrics & Performance

### Industry-Standard Metrics

#### Coverage Metrics
- **Exercise Coverage**: % of exercises tested
- **Solution File Coverage**: % of solution files tested
- **Target**: 100% for both

#### Defect Metrics
- **Defect Density**: Bugs per exercise (target: <0.5)
- **Critical Defect Ratio**: % of P0/P1 bugs (target: <20%)
- **Defect Breakdown**: P0, P1, P2, P3 counts

#### Performance Metrics
- **Total Execution Time**: Full course test duration
- **Avg Time per Exercise**: Mean execution time
- **Category Times**: Time per test category
- **Budget Compliance**: % within performance budgets

#### Quality Score
**0-100 score** based on:
- Coverage: 30%
- Test Pass Rate: 30%
- Defect Quality: 30%
- Performance: 10%

#### Automation ROI
- Manual testing time: ~30 min/exercise
- Automated testing time: ~5 min/exercise
- Time saved: 25 min/exercise
- Efficiency gain: 83%
- Speed multiplier: 6x faster

---

### Performance Budgets

Each test category has a maximum execution time budget:

| Category | Budget | Warning | Critical | Blocker |
|----------|--------|---------|----------|---------|
| TC-PREREQ | 30s | >30s | >45s | >60s |
| TC-EXEC | 10min | >10min | >15min | >20min |
| TC-SOL | 5min | >5min | >7.5min | >10min |
| TC-GRADE | 2min | >2min | >3min | >4min |
| TC-IDEM | 10min | >10min | >15min | >20min |
| TC-E2E | 30min | >30min | >45min | >60min |

**Budget Violations:**
- **WARNING**: 100-150% of budget
- **CRITICAL**: 150-200% of budget
- **BLOCKER**: >200% of budget

---

## Advanced Features

### Comprehensive Review Exercise Handling

**Auto-Detection:** Exercises with "comprehensive review", "cumulative review", "capstone" in title/ID

**Special Handling:**
- **Extended Timeouts**: 2-3x normal timeouts
- **Dependency Tracking**: Step dependencies analyzed
- **Multi-Technology Support**: Handles Ansible + OpenShift + RHEL in single exercise
- **Critical Path Analysis**: Identifies longest dependency chain

**Complexity Levels:**
- **SIMPLE**: <10 steps, 1 technology
- **MODERATE**: 10-20 steps, 2 technologies
- **COMPLEX**: 20-30 steps, 3+ technologies
- **COMPREHENSIVE**: >30 steps, full course integration

---

### Failure Diagnostics

**Automatic Error Analysis** with actionable fix recommendations:

**Error Categories Detected:**
- File not found
- Permission denied
- Command not found
- Service failed
- Network error
- Syntax error
- Timeout
- Resource not found (OpenShift)
- Authentication failed
- Idempotency violation
- Missing dependency

**For Each Error:**
- Root cause analysis
- Exact fix commands
- Verification steps
- Related documentation links

**Example:**
```
Error: "No such file or directory: /home/student/playbook.yml"

Root Cause: File does not exist or path is incorrect

Fix Commands:
  # Check if file exists
  ls -la /home/student/playbook.yml

  # For solution files, copy and remove .sol:
  cd ~/materials/labs/example-ex
  cp solutions/playbook.yml.sol playbook.yml
```

---

### AI-Powered Test Case Generation

**Automatic Generation** of comprehensive test cases including edge cases not in EPUB:

**Test Case Types Generated:**
- **Happy Path**: Normal execution
- **Boundary**: Edge values (0, -1, max, etc.)
- **Error Handling**: Error scenarios
- **Edge Cases**: Special characters, long inputs, etc.
- **Negative**: Invalid inputs
- **Security**: Injection attacks, weak passwords
- **Performance**: Load testing
- **Idempotency**: Multi-run validation
- **Concurrency**: Parallel execution

**Example Generated Tests:**
```
TC-001: Execute exercise following EPUB exactly (CRITICAL)
TC-002: Test port boundary conditions: 0, -1, 65536 (HIGH)
TC-003: Test file operations with spaces in filenames (MEDIUM)
TC-004: Test weak password rejection (HIGH)
TC-005: Test concurrent user creation (LOW)
```

---

### Visual Regression Testing (Web UI)

**For Exercises with Web Consoles**

**Capabilities:**
- Screenshot capture
- Baseline comparison
- Visual diff detection
- Responsive design testing (mobile, tablet, desktop)
- Accessibility checks (integration with WCAG)

**Comparison Results:**
- **IDENTICAL**: 0% difference
- **MINOR_DIFF**: <5% difference (pass)
- **MODERATE_DIFF**: 5-15% difference (warning)
- **MAJOR_DIFF**: >15% difference (fail)

---

## Troubleshooting

### Common Problems & Solutions

#### 1. SSH Connection Failures

**Symptom:** "Connection refused" or "timeout"

**Solutions:**
```bash
# Check SSH service
sudo systemctl status sshd

# Check firewall
sudo firewall-cmd --list-services | grep ssh

# Verify SSH keys
chmod 600 ~/.ssh/id_rsa
ssh-copy-id servera
```

---

#### 2. Ansible Execution Failures

**Symptom:** "ansible-navigator: command not found"

**Solutions:**
```bash
# Install ansible-navigator
sudo dnf install -y ansible-navigator

# Check PATH
which ansible-navigator

# Verify collections
ansible-galaxy collection list
```

---

#### 3. OpenShift Resource Not Found

**Symptom:** "Error from server (NotFound)"

**Solutions:**
```bash
# Check namespace
oc project

# List all resources
oc get all

# Check in all namespaces
oc get all --all-namespaces

# Verify login
oc whoami
```

---

#### 4. Service Failed to Start

**Symptom:** "Job for httpd.service failed"

**Solutions:**
```bash
# Check status
systemctl status httpd

# View logs
journalctl -u httpd -n 50

# Check configuration
httpd -t  # or nginx -t

# Check SELinux
getenforce
ausearch -m avc -ts recent
```

---

#### 5. Permission Denied

**Symptom:** "Permission denied" when running commands

**Solutions:**
```bash
# Add execute permission
chmod +x script.sh

# Use sudo for privileged operations
sudo systemctl start httpd

# Check ownership
ls -la <file>
sudo chown $USER:$USER <file>
```

---

#### 6. Idempotency Failures

**Symptom:** "State changed on second run"

**Solutions:**
```
Review lab script for:
- Creating files/users without checking existence
- Appending to files repeatedly
- Incrementing counters
- Timestamps in generated files

Fix: Add idempotency checks:
if ! id username &>/dev/null; then
    useradd username
fi
```

---

#### 7. Grading Script False Negatives

**Symptom:** Grading fails but exercise appears correct

**Solutions:**
```bash
# Run grading in verbose mode (if available)
lab grade <exercise-id> -v

# Check grading script logic
cat /path/to/grading/script.py

# Verify exact requirements
# (grading may check specific file paths, ownership, permissions)
```

---

#### 8. Performance Budget Violations

**Symptom:** "CRITICAL: TC-SOL exceeds budget"

**Solutions:**
```
Investigate slow operations:
- Check network latency
- Review Ansible playbook for inefficient tasks
- Check for hanging processes
- Verify system resources (CPU, memory)

Consider:
- Optimizing slow playbooks
- Increasing timeout for legitimate slow operations
- Checking for environment issues
```

---

## Best Practices

### 1. Always Test All Exercises

**Thoroughness Guideline**: Never skip exercises

- Coverage must be 100%
- Partial testing violates QA standards
- Use `exercise-qa` (no args) to test full course

---

### 2. Review Quality Metrics

**After Each Test Run:**
- Check **Quality Score** (target: >90/100)
- Review **Defect Density** (target: <0.5 bugs/exercise)
- Verify **Budget Compliance** (target: >90%)
- Assess **Automation ROI**

---

### 3. Fix P0/P1 Bugs First

**Priority Order:**
1. **P0 (Blocker)**: Blocks release - fix immediately
2. **P1 (Critical)**: Major functionality broken - fix before release
3. **P2 (High)**: Important but not blocking - fix if time allows
4. **P3 (Low)**: Minor issues - document for future

**Never ship with P0 bugs**

---

### 4. Validate Idempotency

**For Every Exercise:**
- Run `lab start` twice
- Verify state unchanged
- Fix any idempotency violations

---

### 5. Test Independence (E2E)

**For Each Exercise:**
- Verify works without previous exercises
- Check no implicit dependencies
- Validate prerequisites are documented

---

### 6. Use Failure Diagnostics

**When Tests Fail:**
1. Review failure diagnostic report
2. Apply recommended fixes
3. Re-run specific test category
4. Verify fix works

---

### 7. Monitor Performance Budgets

**Track Execution Times:**
- Identify slow test categories
- Optimize inefficient operations
- Report persistent budget violations

---

### 8. Leverage AI Test Generation

**Before Release:**
- Generate additional test cases
- Run high-priority generated tests
- Add edge cases to test suite

---

### 9. Security & Accessibility

**Always Review:**
- TC-SECURITY findings (even P3)
- TC-ACCESSIBILITY suggestions
- Implement improvements when feasible

---

### 10. Document Everything

**Maintain:**
- Test results (JSON + markdown)
- Quality metrics (metrics.json)
- Bug fix history
- Release readiness decisions

---

## Additional Resources

### Related Documentation

- `TECHNOLOGY-GUIDE.md`: Technology-specific testing details
- `COMMON-PROBLEMS-AND-SOLUTIONS.md`: Detailed troubleshooting
- `COURSE-TECHNOLOGIES.md`: Course technology reference
- `GRADING-SCRIPTS-ALL-COURSES.md`: Grading script documentation

### Support

For issues or questions:
1. Check this guide
2. Review troubleshooting section
3. Check related documentation
4. Report issues with full test results

---

**End of Comprehensive Guide**

*Exercise QA Framework v2.0*
*Red Hat Training Quality Assurance*
