# Exercise QA - Automated Course Testing

**Version 2.0.1** | [Changelog](./CHANGELOG.md)

**Automated quality assurance for ANY Red Hat Training course**

Auto-detects technology, exercise type, and course structure. Tests on live systems. Generates comprehensive QA reports.

---

## Quick Start

```bash
# Test single exercise
/exercise-qa <lesson-code> <exercise-name>

# Test from EPUB
/exercise-qa /path/to/COURSE.epub <exercise-name>

# Test entire course (all exercises)
/exercise-qa /path/to/COURSE.epub

# End-to-end testing
/exercise-qa <course-code> <chapter-name> --e2e

# Watch mode - re-run tests on file changes
/exercise-qa <lesson-code> <exercise-name> --watch

# Disable colorized output
/exercise-qa <lesson-code> <exercise-name> --no-color
```

**Zero configuration required** - fully automatic.

---

## What It Does

**Core Testing:**
- ✅ Student Experience - EPUB steps on live systems
- ✅ Solution Validation - ALL solution files tested
- ✅ Grading Validation - WITH/WITHOUT solution
- ✅ Cleanup & Idempotency - Multi-cycle testing
- ✅ End-to-End - Exercise independence validation
- ✅ Instruction Quality - Clarity and completeness

**Advanced Features (v2.0):**
- ✅ Quality Metrics - Industry-standard coverage, defects, ROI
- ✅ Performance Budgets - Time budgets with violation tracking
- ✅ Failure Diagnostics - AI-powered error analysis with exact fixes
- ✅ Security Testing - Detects anti-patterns (P2/P3 suggestions)
- ✅ Accessibility - WCAG 2.2 compliance validation
- ✅ Contract Validation - EPUB ↔ Solutions ↔ Grading alignment
- ✅ Comprehensive Reviews - Dependency tracking, extended timeouts
- ✅ Visual Regression - Screenshot comparison for web UIs
- ✅ AI Test Generation - Automatically generates edge case tests
- ✅ AAP Controller API Testing - Credentials, projects, templates
- ✅ Network Devices - Cisco IOS/IOS-XE, Juniper Junos, Arista EOS
- ✅ Execution Environments - ansible-navigator, EE validation
- ✅ Colorized Output - ANSI color support with auto-detection
- ✅ Watch Mode - Re-run tests automatically on file changes

**Technologies Supported:**
- Ansible Automation (ansible-navigator, EE, network automation)
- AAP Controller (API testing, resources validation)
- Network Devices (Cisco, Juniper, Arista)
- OpenShift (manifests, web console)
- RHEL & Linux (multi-host SSH)
- Web Interfaces (AAP, OpenShift Console, Satellite, Cockpit)

---

## Test Categories

| Category | What It Tests |
|----------|---------------|
| **TC-PREREQ** | SSH, tools, managed hosts, network devices, execution environments |
| **TC-EXEC** | Command syntax validation (pre-flight safety checks) |
| **TC-WORKFLOW** | EPUB workflow execution on live systems |
| **TC-SOL** | ALL solution files work |
| **TC-GRADE** | Grading works (WITH/WITHOUT solution) |
| **TC-AAP** | AAP Controller resources configured |
| **TC-SECURITY** | Security best practices (P2/P3 suggestions) |
| **TC-ACCESSIBILITY** | WCAG 2.2 accessibility (P2/P3 suggestions) |
| **TC-CONTRACT** | Component alignment (EPUB ↔ Solutions ↔ Grading) |
| **TC-CLEAN** | Cleanup complete |
| **TC-IDEM** | Idempotency (multi-cycle) |
| **TC-E2E-*** | Exercise independence and sequential workflows |

**Total:** 15+ test categories

---

## CLI Options

| Option | Description |
|--------|-------------|
| `--e2e` | Enable end-to-end testing |
| `--full-course` | Test all exercises in course |
| `--mode` | Testing mode: `sequential`, `parallel`, `smart` |
| `--watch` | Watch mode: re-run tests when files change |
| `--no-color` | Disable colorized terminal output |
| `--no-cache` | Disable caching |
| `--output-dir` | Custom output directory for reports |
| `--verbose` | Enable verbose output (default) |
| `--quiet` | Disable verbose output |

---

## Output

**Reports auto-saved to:** `~/.claude/skills/exercise-qa/results/`

**Format:** `QA-REPORT-<COURSE>-<exercise>-YYYY-MM-DD-HHMM.md`

**Contents:**
- Executive summary with pass/fail metrics
- Quality Metrics Dashboard (coverage, defects, ROI, quality score)
- Performance Budget Compliance (time budgets, violations)
- Bug classification (P0/P1/P2/P3)
- Fix recommendations with exact commands (from failure diagnostics)
- Security & accessibility findings (P2/P3 suggestions)
- Verification steps
- Automation metrics (6x faster, 83% efficiency gain)
- Release readiness assessment

---

## Documentation

**Quick Reference:** [COMPREHENSIVE-GUIDE.md](./config/COMPREHENSIVE-GUIDE.md) - Complete reference for all features
**Full Documentation:** [SKILL.md](./SKILL.md) - Technical implementation details

**Directory-specific:**
- [config/README.md](./config/README.md) - Course mappings and references
- [test-cases/README.md](./test-cases/README.md) - Custom test cases
- [results/README.md](./results/README.md) - Test results format

---

## Status

✅ **Production Ready - Version 2.0**

- **15+ Test Categories** - Comprehensive functional, quality, security, and accessibility testing
- **Industry-Standard Metrics** - Coverage, defect density, quality scores, ROI tracking
- **AI-Powered Diagnostics** - Automatic error analysis with exact fix commands
- **Performance Budgets** - Time tracking with violation alerts
- **Universal Support** - Works with ALL Red Hat Training courses via auto-detection

**Automation:** Fully automated with live environment validation
