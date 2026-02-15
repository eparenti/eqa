# Test Results

**Auto-generated directory** - The QA skill writes test results here.

⚠️ **Don't edit these files manually** - they are generated automatically during testing.

---

## 📁 Directory Structure

**QA test reports** saved directly in `results/` directory:

```
results/
├── QA-REPORT-<ANSIBLE-COURSE>-FULL-2026-01-06-1548.md
├── QA-REPORT-<ANSIBLE-COURSE>-install-config-2026-01-06-1550.md
├── QA-REPORT-<ANSIBLE-COURSE>-<exercise-name>-2026-01-06-1505.md
├── QA-REPORT-<RHEL-COURSE>-CHAPTER2-2026-01-06-1612.md
└── README.md  (this file)
```

**Format:** `QA-REPORT-{NAME}-{DATE}-{TIME}.md`
- **{NAME}:** Course code, exercise name, or "FULL" for full course tests
- **{DATE}:** YYYY-MM-DD format
- **{TIME}:** HHMM format (24-hour, local time)

**Examples:**
- Full course test: `QA-REPORT-<ANSIBLE-COURSE>-FULL-2026-01-06-1548.md`
- Single exercise: `QA-REPORT-<ANSIBLE-COURSE>-install-config-2026-01-06-1550.md`
- Chapter test: `QA-REPORT-<ANSIBLE-COURSE>-CHAPTER2-2026-01-06-1552.md`

### logs/

**Detailed test execution logs** for debugging.

```
logs/
├── 2026-01-06/
│   ├── <exercise-name>-143022.log
│   ├── <exercise-name>-150145.log
│   └── <chapter>-review-161203.log
└── latest.log → 2026-01-06/<exercise-name>-150145.log
```

**Organization:** By date, then by exercise
**Latest:** Symlink to most recent log

### known-issues/

**Documented bugs and issues** found during testing.

```
known-issues/
├── <ANSIBLE-COURSE>-P0-BLOCKERS.md
├── <ANSIBLE-COURSE>-P1-CRITICAL.md
├── <RHEL-COURSE>-ch1-issues.md
└── RESOLVED/
    └── <ANSIBLE-COURSE>-<exercise-name>-P1-001.md
```

**Active issues:** In root of known-issues/
**Resolved:** Moved to RESOLVED/ subfolder

---

## Test Reports

### What's in a Report

Each test report includes:

1. **Executive Summary**
   - Test date/time
   - Exercise tested
   - Overall pass/fail status
   - Bug counts by severity

2. **Test Results**
   - TC-PREREQ: Prerequisites (SSH, tools, managed hosts, network devices, execution environments)
   - TC-INSTRUCT: Instructions
   - TC-EXEC: Exercise execution
   - TC-SOL: Solutions
   - TC-SOLVE: Solve playbooks (comprehensive reviews)
   - TC-GRADE: Grading (labs only)
   - TC-VERIFY: Verification (GEs only)
   - TC-AAP: AAP Controller resources (<AAP-COURSE>, <NETWORK-COURSE>)
   - TC-WORKFLOW: Workflow automation
   - TC-WEB: WebApp testing
   - TC-CLEAN: Cleanup
   - TC-IDEM: Idempotency
   - TC-E2E-*: End-to-end testing suite

3. **Bugs Found**
   - Bug ID, severity, description
   - Steps to reproduce
   - Suggested fixes

4. **Quality Gates**
   - Critical gates status
   - Important gates status
   - Release readiness decision

### Example Report

**File:** `reports/<ANSIBLE-COURSE>-<exercise-name>-2026-01-06-143022.md`

```markdown
# QA Report: <ANSIBLE-COURSE> - <exercise-name>

**Date:** 2026-01-06 14:30:22
**Exercise:** <exercise-name> (Guided Exercise)
**Tester:** QA Skill (Automated)

---

## Executive Summary

**Status:** ✅ PASS (8/8 tests, 100%)
**Bugs:** 0 (P0: 0, P1: 0, P2: 0)
**Ready for Release:** ✅ YES

---

## Test Results

### TC-PREREQ: Prerequisites
✅ TC-PREREQ-01: Environment ready (Ansible 2.16.14, SSH ok)

### TC-EXEC: Exercise Execution
✅ TC-EXEC-01: Steps 1-9 executed successfully

### TC-SOL: Solutions
✅ TC-SOL-01: myvhost.yml.sol runs (ok=9, changed=8, failed=0)

### TC-VERIFY: Verification
✅ TC-VERIFY-01: verify_srv.yml passes
✅ TC-VERIFY-02: verify_conf.yml passes
✅ TC-VERIFY-03: verify_cont.yml passes

### TC-CLEAN: Cleanup
✅ TC-CLEAN-01: Cleanup successful

---

## Quality Gates

### Critical (MUST Pass)
✅ TC-PREREQ: 100%
✅ TC-EXEC: 100%
✅ TC-SOL: 100%
✅ TC-VERIFY: 100%
✅ TC-CLEAN: 100%
✅ P0 Bugs: 0

**Decision:** ✅ READY FOR RELEASE
```

---

## Test Logs

### What's in a Log

Detailed execution output:

- Commands executed
- Output from each command
- Timing information
- Debug information
- Error traces

### Example Log Entry

```
[2026-01-06 14:30:22] INFO: Starting test: <ANSIBLE-COURSE> <exercise-name>
[2026-01-06 14:30:23] INFO: TC-PREREQ-01: Checking environment
[2026-01-06 14:30:23] CMD: ssh workstation "ansible --version"
[2026-01-06 14:30:24] OUT: ansible 2.16.14
[2026-01-06 14:30:24] PASS: TC-PREREQ-01
[2026-01-06 14:30:25] INFO: TC-EXEC-01: Executing exercise steps
[2026-01-06 14:30:25] CMD: ssh workstation "cd ~/<exercise-name> && ansible-galaxy role init roles/myvhost"
[2026-01-06 14:30:26] OUT: - Role roles/myvhost was created successfully
[2026-01-06 14:30:26] PASS: TC-EXEC-01
...
```

**Use logs when:**
- Investigating test failures
- Debugging issues
- Understanding what commands were run
- Reproducing problems manually

---

## Known Issues

### Creating Issue Reports

When tests fail, document in `known-issues/`:

**File:** `known-issues/<ANSIBLE-COURSE>-P1-001.md`

```markdown
# BUG-<ANSIBLE-COURSE>-001 (P1): Missing ansible.posix Collection

**Discovered:** 2026-01-06
**Exercise:** <ANSIBLE-COURSE> - <exercise-name>
**Test Case:** TC-SOL-01
**Severity:** P1 (Critical)
**Status:** Open

## Problem

Solution playbook fails with:
```
ERROR! couldn't resolve module/action 'ansible.posix.firewalld'
```

## Impact

- Exercise steps work (students can complete manually)
- Solution file is broken
- Automated testing fails

## Root Cause

`ansible.posix` collection not in requirements.yml

## Reproduction Steps

1. `lab start <exercise-name>`
2. `cd ~/<exercise-name>`
3. `ansible-navigator run solutions/myvhost.yml.sol -m stdout`
4. Observe error

## Suggested Fix

Add to `requirements.yml`:
```yaml
collections:
  - name: ansible.posix
    version: ">=1.5.0"
```

## Workaround

Manual installation:
```bash
ansible-galaxy collection install ansible.posix
```

## Resolution

- [ ] Update requirements.yml
- [ ] Test fix
- [ ] Verify lab start installs collection
- [ ] Move to RESOLVED/
```

### Organizing Issues

**By severity:**
```
known-issues/
├── <ANSIBLE-COURSE>-P0-BLOCKERS.md     # All P0 bugs for <ANSIBLE-COURSE>
├── <ANSIBLE-COURSE>-P1-CRITICAL.md     # All P1 bugs for <ANSIBLE-COURSE>
└── <ANSIBLE-COURSE>-P2-P3.md           # Lower priority issues
```

**By exercise:**
```
known-issues/
├── <ANSIBLE-COURSE>-<exercise-name>-issues.md
├── <ANSIBLE-COURSE>-<exercise-name>-issues.md
└── <RHEL-COURSE>-ch1-servicemgmt-issues.md
```

**Recommendation:** Use by-severity for tracking what needs fixing urgently.

---

## Using Test Results

### 1. Review Latest Report

```bash
# View latest test report
cat results/reports/latest.md

# Or open in editor
vim results/reports/latest.md
```

### 2. Check Specific Exercise

```bash
# Find reports for specific exercise
ls results/reports/ | grep <exercise-name>

# View specific report
cat results/reports/<ANSIBLE-COURSE>-<exercise-name>-2026-01-06-143022.md
```

### 3. Track Bugs

```bash
# List open issues
ls results/known-issues/*.md

# View P0 blockers
cat results/known-issues/*-P0-*.md

# Check resolved issues
ls results/known-issues/RESOLVED/
```

### 4. Debug Failures

```bash
# View latest log
cat results/logs/latest.log

# Search for specific error
grep -i "error\|fail" results/logs/latest.log

# Find when command was run
grep "TC-SOL-01" results/logs/latest.log
```

---

## Maintenance

### Archive Old Reports

```bash
# Keep last 30 days, archive older
find results/reports/ -mtime +30 -exec mv {} results/reports/archive/ \;
```

### Clean Up Logs

```bash
# Keep last 7 days of logs
find results/logs/ -mtime +7 -type f -delete
```

### Update Known Issues

After fixing bugs:

```bash
# Move resolved issue
mv results/known-issues/<ANSIBLE-COURSE>-P1-001.md \
   results/known-issues/RESOLVED/
```

---

## Integration with Bug Tracking

### Export to CSV

```bash
# Generate bug summary
python .skilldata/scripts/calculate_metrics.py \
  results/reports/latest.md \
  --json results/bug-summary.json
```

### Link to Issue Tracker

In known-issues file, add:

```markdown
## External References

- JIRA: TRAIN-1234
- GitHub: RedHatTraining/<ANSIBLE-COURSE>#56
- Support Ticket: #98765
```

---

## Tips

✅ **DO:**
- Review reports after each test run
- Document bugs immediately when found
- Update known-issues when bugs are fixed
- Keep reports for historical comparison
- Use logs to debug failures

❌ **DON'T:**
- Edit generated reports manually
- Delete logs before debugging
- Ignore P0/P1 bugs
- Forget to archive old results
- Commit large log files to git

---

## Git Ignore Recommendations

Add to `.gitignore`:

```gitignore
# Ignore auto-generated results (logs can be large)
results/logs/
results/reports/*.md
!results/reports/README.md

# Keep known issues (important to track)
# results/known-issues/   # DON'T ignore these!
```

Or if you want to track recent results:

```gitignore
# Ignore old logs
results/logs/*
!results/logs/latest.log

# Keep recent reports (last 7 days)
results/reports/*.md
!results/reports/*-$(date -d '7 days ago' +%Y-%m-%d)*.md
!results/reports/latest.md
```

---

**Remember:** This directory is for automated results. For your own test documentation, use `test-cases/custom/`.
