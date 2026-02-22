---
name: eqa
version: 7.4.0
description: Automated exercise QA for Red Hat Training courses
authors:
  - Ed Parenti <eparenti@redhat.com>
  - Claude Code
---

# eqa - Exercise QA for Red Hat Training

Fully automated quality assurance for ANY Red Hat Training course. Auto-detects course structure, technology stack, and exercise type.

## Quick Start

```bash
/eqa AU0024L scale-files        # Single exercise
/eqa AU294 --chapter 6          # Full chapter
/eqa AU0024L                    # All exercises in a lesson
/eqa AU294 --chapter 4 --e2e    # End-to-end (exercise independence)
```

## Critical Rules

1. **Absolute paths** — `devcontainer-start` does not expand `~`. Always use `/home/student/<exercise>`.
2. **write-file = base64** — Write locally first, encode with `base64 -w0`, then upload via `--content`.
3. **devops for sudo** — `student` hangs on sudo. Use `ssh devops@<host> 'sudo <cmd>'`.
4. **ansible-navigator: `-m stdout`** — Without it the TUI hangs. (Not needed if `ansible-navigator.yml` already has `mode: stdout`.)
5. **EPUB is truth** — Never assume URLs, hostnames, or ports from prior exercises. Always extract from current exercise instructions.
6. **epub_tool commands are dicts** — Access with `.get("text")`, not string slicing. File actions may be in `sub_steps[].file_actions[]`.
7. **Parser limitations** — `epub_tool.py` may not capture all content from `<ul>`-based sub-items or single code blocks shared across multiple files. Always cross-reference with solution files when available.

All example values in this document are **illustrative** — extract real values from the EPUB, course profile, and live environment.

## Setup

Run these steps in order when invoked.

### 1. Resolve → 2. Parse → 3. Connect → 4. Profile

```bash
# 1. Resolve course input
course_tool.py resolve <input> [--chapter N]
# Returns: {epub_path, lesson_path, lesson_code, lab_framework}

# 2. Parse EPUB
epub_tool.py parse <epub_path> --lesson-path <lesson_path>
# Returns: {exercises, extract_dir, ...}

# 3. Connect SSH
ssh_tool.py connect --host workstation
# Returns: {framework, capabilities, lab_cli_version, ...}

# 4. Build course profile (use extract_dir from step 2, NOT the repo directory)
profile_tool.py build <extract_dir>
# Returns: {uses_dev_containers, uses_ansible_navigator, real_hosts, ...}
```

All tool paths are relative to `~/git-repos/eqa/.skilldata/scripts/`.

### 5. Lab Package

Ensure the installed grading package matches the EPUB version.

```bash
# Check version
ssh_tool.py run "lab version"   # DynoLabs 5
ssh_tool.py run "lab -v"        # DynoLabs 4

# Install/switch
ssh_tool.py lab install <lesson_code>

# If blocked (DynoLabs 5 only):
ssh_tool.py run "lab force <lesson_code>"
```

The `ssh_tool.py lab` command abstracts DynoLabs version differences: `solve` maps to `fix` on DL4, `force` falls back to `install`, etc. Check `capabilities` from connect output.

### 6. HLD Document (Optional)

Ask if the user has an HLD (`.docx`). If provided, extract text with `zipfile` + `ElementTree` and use for context during TC-STUDENTSIM and TC-INSTRUCT.

### 7. Network Tunnel (Optional, for web UI testing)

```bash
ssh_tool.py status              # Get subnets
# User runs: sudo sshuttle --dns -r workstation <subnets> -D
```

## Execution Flow

### Phase Overview

| Phase | What | Applies to |
|-------|------|-----------|
| **0: Static** | TC-EXEC, TC-INSTRUCT, TC-SECURITY, TC-STATICDIFF | All (STATICDIFF: if solutions exist) |
| **1: Simulate** | TC-PREREQ → TC-GRADE pre → TC-STUDENTSIM → TC-GRADE post → TC-WEB → TC-LIVEDIFF → TC-CLEAN | All |
| **2: Solutions** | TC-SOL and/or TC-SOLVE | If solution files or solve cmd exist |
| **3: Idempotency** | TC-IDEM | If Phase 1 passed |

### GE Checklist
```
Phase 0: TC-EXEC → TC-INSTRUCT → TC-SECURITY → TC-STATICDIFF (if solutions)
Phase 1: lab start → student sim (incl. verification) → live diff → lab finish → re-start → lab finish
Phase 2: lab start → apply solutions → run playbooks → verify → lab finish
Phase 3: compare Phase 1 vs Phase 2 (or repeat Phase 1)
```

### Lab Checklist
```
Phase 0: TC-EXEC → TC-INSTRUCT → TC-SECURITY → TC-STATICDIFF
Phase 1: lab start → grade (expect FAIL) → student sim → grade (expect PASS) → live diff → lab finish → re-start → lab finish
Phase 2: lab start → apply solutions → grade (expect PASS) → lab finish
Phase 3: compare Phase 1 vs Phase 2 (or repeat Phase 1)
```

Collect ALL bugs before reporting (don't fail-fast). Exception: P0 blockers may stop testing early.

## Test Categories

### TC-EXEC (Phase 0, all)
Validate commands for syntax errors, dangerous operations, missing dependencies, and naming consistency. Report as P2/P3.

### TC-INSTRUCT (Phase 0, all)
Check instruction completeness, accuracy, clarity, ordering, consistency. `...output omitted...` is normal — only a bug if the omitted section contains content the student needs.

### TC-SECURITY (Phase 0, all)
Flag hardcoded credentials, `chmod 777`, insecure protocols, unnecessary root. Many exercises intentionally use simple credentials for teaching — only flag habits students might carry to production.

### TC-STATICDIFF (Phase 0, if solutions exist)
Static comparison of EPUB file content against solution files. Diff each file_action from the parsed instructions against its corresponding `.sol` file (strip `.sol` suffix to match). For Labs, also check grading alignment: grading checks something solutions don't provide = P1. Missing solution for an EPUB-created file = P2. Content mismatch = P3 (cosmetic) or P2 (behavioral).

### TC-PREREQ (Phase 1, all)
Run `ssh_tool.py lab start <exercise>`. Auto-recovery handles blocking labs. If `success: false` → P0. Verify SSH to managed hosts.

### TC-GRADE (Phase 1, Labs only)
**Exit codes don't indicate pass/fail** — read the `checks` array or `stdout` directly.
- **Pre-check** (before work): Most checks should FAIL. All PASS = P1 false positive.
- **Post-check** (after sim): All should PASS. Any FAIL = P1 false negative.

### TC-STUDENTSIM (Phase 1, all)
**Read ALL instructions first** before executing. Understand teaching intent — intentional errors, progressive disclosure, and troubleshooting exercises are not bugs.

Execute step by step, translating each instruction:
- Commands → `ssh_tool.py run` or `devcontainer-run`
- File creation → `ssh_tool.py write-file` (base64 encoded)
- File edits → read, modify, write back
- Interactive prompts → rewrite non-interactively
- GUI steps → see programmatic equivalents table below

**Verification steps (GEs):** Steps marked `is_verification: true` are part of the exercise flow — execute them inline during simulation. Failure after correct preceding steps = P1. Report verification results as a subsection (e.g., "Verification: 4/4 checks passed").

**Dev containers:** `devcontainer-start` → pre-pull EE → `devcontainer-run` for commands → `lab` commands on workstation → let `lab finish` handle cleanup.

**Network devices:** Apply 2x timeout multiplier. Expect 90-110s for lab start/finish.

**ansible-navigator noise:** Base64 UUID strings in output are metadata artifacts — ignore them, look for `PLAY RECAP`.

### TC-LIVEDIFF (Phase 1, if solutions exist)
After TC-STUDENTSIM completes, compare each student-created file against its corresponding solution file on the workstation. Use `ssh_tool.py diff <remote_path> --expected <base64>` or read both and compare. Mismatches that affect behavior = P2. Cosmetic-only differences (whitespace, trailing newline, comment ordering) = P3. This catches cases where EPUB instructions produce subtly different files than the solutions, or where solutions are stale.

### TC-WEB (Phase 1, if web apps/consoles)
Prefer `oc` CLI > `curl` > REST API > Playwright (in that order). Application not reachable = P1.

### TC-CLEAN (Phase 1, all)
`lab finish` → `lab start` (re-start check) → `lab finish`. Re-start failure = P1 incomplete cleanup. 404 on deleting resources from other exercises is expected in progressive courses.

### TC-SOL (Phase 2, if solutions exist)
Fresh start → copy solutions → run playbooks → verify/grade → finish. Solutions don't work = P1.

### TC-SOLVE (Phase 2, if solve available)
Fresh start → `ssh_tool.py lab solve <exercise>` → verify/grade → finish.

### TC-IDEM (Phase 3, if Phase 1 passed)
**Shortcut:** If TC-SOL passed, it counts as cycle 2. Different results = P1 state pollution.

## GUI → Programmatic Equivalents

| GUI Step | Programmatic Equivalent |
|----------|------------------------|
| "Open folder in VS Code" | No-op |
| "Reopen in Container" | `ssh_tool.py devcontainer-start /home/student/<exercise>` |
| "Create/save file" | `ssh_tool.py write-file` |
| "Edit file" | Read, modify, write back |
| "Run in terminal" | `ssh_tool.py devcontainer-run <cmd>` |
| "Open browser" | `web_tool.py navigate <url>` or `curl` |
| "Log in to console" | `web_tool.py login <url> --username <u> --password <p> --then <url>` |
| AAP Controller UI | REST API via `curl` or `web_tool.py api-get/api-post` |
| "podman login/pull" | Add `--tls-verify=false` for lab registries |
| OCP console actions | `oc` CLI equivalents |

## Recipes

### Writing Files
```bash
# Write locally → encode → upload
# (Write tool) → /tmp/file.yml
ssh_tool.py write-file /home/student/<ex>/file.yml --content "$(base64 -w0 /tmp/file.yml)"
```

### Applying Solutions (TC-SOL)
```bash
ssh_tool.py run "cp /home/student/<ex>/solutions/playbook.yml.sol /home/student/<ex>/playbook.yml"
ssh_tool.py run "cp -r /home/student/<ex>/solutions/group_vars /home/student/<ex>/"
```

### Dev Container Lifecycle
```bash
ssh_tool.py devcontainer-start /home/student/<exercise>          # Absolute path required
ssh_tool.py devcontainer-run "cat /home/student/<ex>/ansible-navigator.yml"  # Get EE image
ssh_tool.py devcontainer-run "podman pull --tls-verify=false <registry>/<image>:<tag>"
ssh_tool.py devcontainer-run "cd /home/student/<ex> && ansible-navigator run playbook.yml -m stdout"
ssh_tool.py lab grade <exercise>                                 # Lab cmds on workstation
ssh_tool.py lab finish <exercise>                                # Handles container cleanup
```

### ansible-vault (Non-Interactive)
```bash
ssh_tool.py write-file /tmp/vault-pass --content "$(echo -n '<password>' | base64 -w0)"
ssh_tool.py run "ansible-vault encrypt --vault-password-file /tmp/vault-pass secrets.yml"
ssh_tool.py run "ansible-navigator run site.yml -m stdout --vault-password-file /tmp/vault-pass"
```

### Managed Host Commands
```bash
ssh_tool.py run "ssh devops@<host> 'sudo systemctl restart httpd'"   # Privileged (devops)
ssh_tool.py run "ssh student@<host> 'cat /etc/motd'"                 # Unprivileged (student)
# NEVER: ssh student@<host> 'sudo ...'  ← hangs waiting for password
```

### Git Clone with Special Characters
```bash
ssh_tool.py run "git clone http://student:Student%40123@utility.lab.example.com:3000/student/<repo>.git"
# @ → %40, # → %23, $ → %24
```

### Gitea API Authentication
```bash
# curl -u fails with @ in password. Use base64 Basic auth:
ssh_tool.py run "curl -sk -H 'Authorization: Basic <base64(user:pass)>' http://utility:3000/api/v1/..."
# Or create a token (requires scopes like write:repository)
```

### Podman in Lab Environments
```bash
ssh_tool.py run "podman login -u <user> -p <pass> <registry> --tls-verify=false"
ssh_tool.py run "podman pull --tls-verify=false <registry>/<image>:<tag>"
```

## Classification

### Bug Severity

| Severity | Meaning | Action |
|----------|---------|--------|
| **P0** | Exercise unusable (lab start fails, missing playbooks) | STOP, report immediately |
| **P1** | Validation broken (false grade, cleanup incomplete, solutions fail) | Must fix before release |
| **P2** | Quality issue (instruction fails, unclear errors, security anti-pattern) | Should fix |
| **P3** | Polish (typos, style, naming inconsistency) | Optional |
| **LAB** | Lab infrastructure (slow start, transient failures, 404 on cleanup) | Report to lab/platform team |
| **ENV** | Environment (version mismatch, disk full, cluster not ready) | Report to operations |

### Decision Tree
1. Student can't complete exercise? → **P0**
2. Student can't verify work? → **P1**
3. Exercise not repeatable (idempotency)? → **P1**
4. Bad student experience? → **P2**
5. Minor issues? → **P3**
6. Lab script misbehaving? → **LAB**
7. Test environment broken? → **ENV**

### Distinguishing Categories
- Same exercise works on fresh workstation but fails here → **ENV**
- ALL exercises fail at same step → **ENV**
- ONE exercise fails at unique step → exercise bug (P0-P3)
- `lab start` fails but `oc`/`virtctl` work → grading script issue

## Quality Metrics & Reporting

### Metrics
- **Coverage**: exercises tested / total
- **Defect density**: bugs per exercise (target: < 0.5)
- **Critical ratio**: P0+P1 as % of total (target: < 20%)
- **Performance budgets**: lab start > 60s, lab finish > 60s, total > 10min → flag

### Quality Score (0-100, via `report_tool.py score`)
| Score | Assessment |
|-------|------------|
| 90-100 | Ready for release |
| 70-89 | Conditional — fix P1+ |
| 50-69 | Needs work |
| <50 | Not ready |

### Release Readiness
- **Ready**: 0 P0, 0 P1, density < 0.5
- **Conditional**: 0 P0, ≤ 2 P1, density < 1.0
- **Not ready**: Any P0, or > 2 P1, or density ≥ 1.0

### Reports
Write to `~/git-repos/eqa/results/`:
- Exercise: `<exercise-id>-<YYYYMMDD-HHMMSS>.md`
- Chapter: `<course>-ch<N>-summary-<YYYYMMDD>.md`

Include: Summary, Quality Metrics, Test Results (by phase/TC), Bugs Found, Lab Issues, Findings, Performance, Course Profile. Only include TC sections that apply to the exercise type.

## Decision Points

**Lab operations:**
- Blocking lab → ssh_tool auto-recovers. If not, `ssh_tool.py lab finish <exercise>` manually.
- Command timeout → retry once with 2x timeout, then P2.
- SSH drops → ssh_tool auto-reconnects. If not, `ssh_tool.py connect` again.
- Grade passes without solution → P1 (grading SHOULD fail without student work).
- `lab install` blocked → use `lab force` (DL5) or check `lab select` (DL4).
- Multi-repo course → `lab install <new-lesson>` before switching lessons.

**EPUB interpretation:**
- Exercise not found → check fuzzy matches.
- `...output omitted...` in file content → read actual file, apply only the specific edit.
- Resource IDs in EPUB → they're examples; discover real IDs via API queries.
- Troubleshooting exercise → failures are intentional; only bug if still fails after documented fixes.

**AAP Controller:**
- Use Controller URL from EPUB (may differ between exercises).
- Expect 180-300s for lab start (provisioning).
- Transient 503/500 → retry once before classifying as bug.
- Team membership verification → check job output, not role assignment endpoints.

**OCP/VMs:**
- Storage → `oc get sc` first, never hardcode storage class.
- VM commands → `ssh_tool.py vm-exec` (auto-handles auth methods).
- VM disk not visible → restart VM after attach.
- Prefer `oc` CLI over web console for reliability.

**Gitea:**
- Webhook via API → set `branch_filter: "*"` explicitly (API defaults to empty, UI defaults to `*`).
- Password with `@` → use base64 Basic auth, not `curl -u`.

## Reference

### Tool Commands
```
ssh_tool.py connect --host workstation
ssh_tool.py run <cmd>
ssh_tool.py lab start|finish|grade|solve|force <exercise>
ssh_tool.py write-file <path> --content <base64>
ssh_tool.py devcontainer-start|devcontainer-run|devcontainer-stop
ssh_tool.py vm-exec <vm> -n <ns> -c <cmd>
ssh_tool.py vm-disks <vm> -n <ns>
ssh_tool.py wait-for --mode {tcp,http,command,file} --target <target>
ssh_tool.py diff <remote_path> --expected <base64>
ssh_tool.py status | tunnel | disconnect
web_tool.py login|navigate|click|fill|page-text|screenshot|api-get|api-post
diagnose_tool.py analyze <text>
report_tool.py exercise|chapter|score --data <json>
epub_tool.py parse|instructions <epub> <exercise>
course_tool.py resolve <input> [--chapter N]
profile_tool.py build <extract_dir>
```

Full docs: `.skilldata/docs/tools-reference.md`, `.skilldata/docs/lab-cli.md`, `.skilldata/docs/ocp-recipes.md`

### Course Patterns
1. **Single-repo, lesson-based**: `outline.yml` has `dco:` root, no `repository:` fields. Materials at `materials/labs/`.
2. **Multi-repo, lesson-based**: `outline.yml` has `dco:` with `repository:` fields. Each lesson cloned separately.
3. **Single-repo, chapter-based**: `outline.yml` has `course:` root. Materials at `content/{chapter}/`.

### DynoLabs Version Mapping

| Action | DynoLabs 5 (Rust) | DynoLabs 4 (Python) |
|--------|-------------------|---------------------|
| Install | `lab install <sku>` | `lab install <sku>` |
| Force install | `lab force <sku>` | N/A |
| Switch course | `lab activate <sku>` | `lab select <sku>` |
| Auto-solve | `lab solve <exercise>` | `lab fix <exercise>` |
| Show version | `lab version` | `lab -v` |
| Reset status | `lab status --reset` | N/A |

`ssh_tool.py lab` handles mapping automatically.

## Cleanup

```bash
ssh_tool.py disconnect
```
