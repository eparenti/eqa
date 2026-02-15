---
name: exercise-qa
version: 2.0.1
description: Automated quality assurance for Red Hat Training course exercises and labs
authors:
  - Ed Parenti <eparenti@redhat.com>
  - Claude Code
---

# Exercise QA - Automated Red Hat Training Course Testing

**Fully automated quality assurance for ANY Red Hat Training course**

Works with any course through auto-detection: Ansible, OpenShift, RHEL, Satellite, AAP Controller, Network Automation.

---

## Quick Start

```bash
# Test single exercise
/exercise-qa <lesson-code> <exercise-name>

# Test from EPUB
/exercise-qa /path/to/COURSE.epub <exercise-name>

# Test entire course
/exercise-qa /path/to/COURSE.epub

# End-to-end testing
/exercise-qa <course-code> <chapter-name> --e2e
```

**What happens automatically:**
- Detects workstation from `~/.ssh/config`
- Detects technology (Ansible, OpenShift, AAP, Network Devices)
- Detects exercise type (GE vs Lab)
- Tests on live systems using actual `lab` commands
- Generates comprehensive QA report

**Zero manual configuration required.**

---

## Capabilities

### Core Testing
- **Student Experience** - Executes EPUB steps exactly as documented
- **Solution Validation** - Tests ALL solution files on live systems
- **Grading Validation** - Validates `lab grade` (WITH/WITHOUT solution)
- **Cleanup Validation** - Ensures `lab finish` removes all artifacts
- **Idempotency** - Multi-cycle testing with state comparison
- **End-to-End** - Validates exercise independence

### Advanced Features
- **AAP Controller** - Python-based API validation
- **Network Devices** - Cisco, Juniper, Arista with auto-timeouts
- **Execution Environments** - ansible-navigator, EE image validation
- **Quality Metrics** - Coverage, defect density, ROI calculation
- **Performance Budgets** - Time tracking with violation detection
- **Failure Diagnostics** - AI-powered error analysis with fix commands
- **Security Testing** - Detects anti-patterns (P2/P3)
- **Accessibility** - WCAG 2.2 compliance (P2/P3)
- **Contract Validation** - EPUB ↔ Solutions ↔ Grading alignment

### Technology Support
- **Ansible** - ansible-navigator, EE, network automation
- **AAP Controller** - API testing (66+ methods)
- **Network Devices** - Cisco IOS, Juniper Junos, Arista EOS
- **OpenShift** - oc/kubectl, manifests, web console
- **RHEL** - SSH, services, multi-host
- **Web UIs** - Chrome/Selenium testing

---

## Testing Methodology

### Two-Pass Approach

**Pass 1: Student Simulation**
- Execute EPUB steps on live systems
- Test solution files
- Follow verification steps

**Pass 2: QA Validation**
- Test ALL solutions comprehensively
- Validate grading WITH/WITHOUT solution
- Test idempotency (3+ cycles)
- Validate cleanup completeness

### Automated Workflow

1. **Setup** - Auto-detect workstation, technology, exercise type
2. **Testing** - Run `lab start`, execute steps, test solutions, validate grading
3. **Reporting** - Generate report with bugs classified by severity

---

## Test Categories

| Category | What It Tests |
|----------|---------------|
| **TC-PREREQ** | SSH, tools, hosts, network devices, EE |
| **TC-EXEC** | Command syntax and safety validation |
| **TC-WORKFLOW** | EPUB workflow execution on live systems |
| **TC-SOL** | ALL solution files work |
| **TC-SOLVE** | Solve playbooks work |
| **TC-VERIFY** | Verification passes (GE) |
| **TC-GRADE** | Grading works correctly (Labs) |
| **TC-AAP** | AAP Controller resources |
| **TC-SECURITY** | Security best practices (P2/P3) |
| **TC-ACCESSIBILITY** | WCAG 2.2 compliance (P2/P3) |
| **TC-CONTRACT** | Component alignment |
| **TC-CLEAN** | Cleanup complete |
| **TC-IDEM** | Idempotency (multi-cycle) |
| **TC-E2E-*** | Exercise independence |
| **TC-INSTRUCT** | Instruction quality |
| **TC-WEB** | WebApp testing |

---

## Exercise Types

### Guided Exercise (GE)
- Step-by-step instructions, no automated grading
- Testing: TC-PREREQ → TC-EXEC → TC-SOL → TC-VERIFY → TC-CLEAN

### Lab
- Performance-based, automated grading via `lab grade`
- Testing: TC-PREREQ → TC-EXEC → TC-SOL → TC-GRADE → TC-CLEAN → TC-IDEM

### Comprehensive Review
- Auto-detected, extended timeouts (2.5x)
- Testing: All categories + TC-SOLVE + TC-E2E-*

---

## Bug Severity

| Severity | Description | Action |
|----------|-------------|--------|
| **P0** | Exercise unusable (commands fail, SSH broken) | STOP, report |
| **P1** | Validation broken (grading fails, cleanup incomplete) | MUST FIX |
| **P2** | Quality issues (unclear instructions) | SHOULD FIX |
| **P3** | Polish (typos, style) | Optional |

---

## Course Patterns

The skill auto-detects 3 patterns from `outline.yml`:

### Pattern 1: Single-Repo, Lesson-Based
```bash
/exercise-qa <lesson-code> <exercise-name>
```

### Pattern 2: Multi-Repo, Lesson-Based
**CRITICAL:** Run `lab force <lesson-code>` first!
```bash
ssh workstation "lab force <lesson-code>"
/exercise-qa <lesson-code> <exercise-name>
```

### Pattern 3: Single-Repo, Chapter-Based
```bash
/exercise-qa <course-code> <exercise-name>
```

---

## Key Patterns

### Error Summary Pattern
Collects ALL bugs before reporting (better UX than fail-fast):
- Students see all problems at once
- Fix multiple issues in one iteration
- Exception: P0 blockers may stop early

### Enhanced Messaging
Professional output with:
- Clear step descriptions
- Timeout information
- Emoji indicators (pass/fail/warning/info)
- Timing for long operations

---

## Reports

**Location:** `~/.claude/skills/exercise-qa/results/`

**Contents:**
- Executive summary (pass/fail, bug counts)
- Test results per category
- Quality metrics (coverage, defects, score)
- Performance budget compliance
- Bug details with fix recommendations
- Release readiness assessment

---

## Best Practices

1. **Test from EPUB** - Not .adoc source files
2. **Test on live systems** - Real VMs, clusters
3. **Test idempotency** - Students practice repeatedly
4. **Test as student first** - Then as QA engineer
5. **For Labs** - Always run `lab grade` WITH and WITHOUT solution

### Solution Files
```bash
# Correct: Copy and remove .sol extension
cp solutions/playbook.yml.sol playbook.yml
ansible-navigator run playbook.yml -m stdout

# Wrong: Never run directly from solutions/
ansible-navigator run solutions/playbook.yml.sol  # WRONG
```

---

## Quality Metrics

**Coverage:** Exercise coverage, solution file coverage (target: 100%)

**Defects:** Defect density <0.5, critical ratio <20%

**Performance:** ~5 min/exercise automated vs ~30 min manual (6x faster)

**Quality Score:** 0-100 based on coverage, defects, performance

---

## Additional Documentation

- **Complete Reference:** `config/COMPREHENSIVE-GUIDE.md`
- **Architecture:** `.skilldata/ARCHITECTURE.md`
- **Troubleshooting:** `config/COMMON-PROBLEMS-AND-SOLUTIONS.md`
- **Technology Guide:** `config/TECHNOLOGY-GUIDE.md`

---

## Status

**Production Ready - Version 2.0**

- 15+ test categories
- Industry-standard quality metrics
- Universal course support via auto-detection
- Fully automated with live environment validation
