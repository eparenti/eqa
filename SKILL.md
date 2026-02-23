---
name: eqa
version: 2.0.0
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

### 1. Resolve → 2. Parse + Connect (parallel) → 3. Profile

```bash
# 1. Resolve course input (sequential — outputs feed steps 2+3)
course_tool.py resolve <input> [--chapter N]
# Returns: {epub_path, lesson_path, lesson_code, lab_framework}

# 2a. Parse EPUB  } Run these two in parallel — they don't depend on each other
# 2b. Connect SSH }
epub_tool.py parse <epub_path> --lesson-path <lesson_path>
# Returns: {exercises, extract_dir, ...}
ssh_tool.py connect --host workstation
# Returns: {framework, capabilities, lab_cli_version, ...}

# 3. Build course profile (use extract_dir from step 2a, NOT the repo directory)
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

| Phase | What | Applies to | When |
|-------|------|-----------|------|
| **0: Static** | TC-EXEC, TC-INSTRUCT, TC-SECURITY, TC-STATICDIFF | All (STATICDIFF: if solutions exist) | Overlaps with lab start |
| **1: Simulate** | TC-PREREQ (finish+start) → TC-GRADE pre → TC-STUDENTSIM → TC-GRADE post → TC-WEB → TC-LIVEDIFF | All | After lab start completes |
| **2+CLEAN: Solutions** | TC-CLEAN + TC-SOL (merged) and/or TC-SOLVE | If solutions or solve exist | Immediately after Phase 1 |
| **3: Idempotency** | TC-IDEM | If Phase 1 passed | Satisfied by Phase 2 |

### GE Checklist
```
Setup:    resolve → (parse + connect in parallel) → profile → install lab package
          ↓ immediately kick off: lab finish (safety) + lab start [background if possible]
Phase 0:  TC-EXEC → TC-INSTRUCT → TC-SECURITY → TC-STATICDIFF   ← runs while lab starts
          ↓ wait for lab start; verify initial state
Phase 1:  student sim (incl. verification, parallel playbooks) → live diff
Phase 2+CLEAN: lab finish → lab start [clean-state check = TC-CLEAN; fresh env = TC-SOL]
               → verify initial state → apply solutions → run → verify → lab finish
Phase 3:  TC-IDEM satisfied (Phase 2 = cycle 2)
```

### Lab Checklist
```
Setup:    resolve → (parse + connect in parallel) → profile → install lab package
          ↓ immediately kick off: lab finish (safety) + lab start [background if possible]
Phase 0:  TC-EXEC → TC-INSTRUCT → TC-SECURITY → TC-STATICDIFF   ← runs while lab starts
          ↓ wait for lab start; verify initial state
Phase 1:  grade (expect FAIL) → student sim → grade (expect PASS) → live diff
Phase 2+CLEAN: lab finish → lab start [clean-state check = TC-CLEAN; fresh env = TC-SOL]
               → verify initial state → apply solutions → grade (expect PASS) → lab finish
Phase 3:  TC-IDEM satisfied (Phase 2 = cycle 2)
```

Collect ALL bugs before reporting (don't fail-fast). Exception: P0 blockers may stop testing early.

## Test Categories

### TC-EXEC (Phase 0, all)
Validate commands for syntax errors, dangerous operations, missing dependencies, and naming consistency. Report as P2/P3.

**Anti-patterns to flag** (P3):
- `ignore_errors: yes` — should be avoided or used sparingly
- `when: true` — redundant, remove the condition
- `when: false` — dead code, task never runs
- `command:.*sudo` — use `become: true` instead
- `shell:.*cd` — use `chdir` parameter instead

**Dependency skip-lists** (don't flag as missing):
- Course-internal collections: `lab.*`, `training.*`, `classroom.*`, `rht.*` — bundled with lab packages
- EE-included collections: `ansible.posix`, `ansible.netcommon`, `ansible.utils`, `ansible.controller`, `ansible.platform`, `awx.awx`, `community.general`, `community.mysql`, `community.postgresql`, `community.crypto`, `redhat.rhel_system_roles`, `containers.podman`, `kubernetes.core`

### TC-INSTRUCT (Phase 0, all)
Check instruction completeness, accuracy, clarity, ordering, consistency. `...output omitted...` is normal — only a bug if the omitted section contains content the student needs.

### TC-SECURITY (Phase 0, all)
Flag hardcoded credentials, `chmod 777`, insecure protocols, unnecessary root. Many exercises intentionally use simple credentials for teaching — only flag habits students might carry to production.

**Scan patterns** (check solution files, skip files with `key`/`cert` in the name):
- Credentials (P2): `password:\s*['"]`, `api[_-]?key:\s*['"]`, `token:\s*['"]`, `secret:\s*['"]`
- Permissions (P3): `mode:\s*0?777`, `mode:\s*0?666`, `chmod\s+777`
- Sudo (P3): `NOPASSWD:\s*ALL`
- Secrets (P2): `-----BEGIN.*PRIVATE KEY-----`, `aws_secret_access_key`

### TC-STATICDIFF (Phase 0, if solutions exist)
Static comparison of EPUB file content against solution files. Diff each file_action from the parsed instructions against its corresponding `.sol` file (strip `.sol` suffix to match). For Labs, also check grading alignment: grading checks something solutions don't provide = P1. Missing solution for an EPUB-created file = P2. Content mismatch = P3 (cosmetic) or P2 (behavioral).

**Additional static checks:**
- **Complexity alignment**: If EPUB has >10 steps but only 1 solution file, flag as P3 for review — may indicate missing solution files or overly detailed EPUB.
- **Grading coverage gaps** (Labs): Extract `dest`/`path` from solution copy/template/file tasks and `name` from service/systemd tasks. If the grading script doesn't verify a solution-created resource, flag as P3.

### TC-PREREQ (Phase 1, all)
Always run `lab finish` before `lab start` to guarantee a clean environment regardless of leftover state from prior testing:

```bash
ssh_tool.py lab finish <exercise>   # safe even if not started; clears any leftover state
ssh_tool.py lab start <exercise>    # fresh start
```

If `lab start` returns `success: false` → P0. After start, verify the exercise directory matches the expected initial state (spot-check a key file against the materials directory). If the state doesn't match what the instructions assume, record the discrepancy — it may indicate a bug in the start script. Verify SSH to managed hosts.

### TC-GRADE (Phase 1, Labs only)
**Exit codes don't indicate pass/fail** — read the `checks` array or `stdout` directly.
- **Pre-check** (before work): Most checks should FAIL. All PASS = P1 false positive.
- **Post-check** (after sim): All should PASS. Any FAIL = P1 false negative.

### TC-STUDENTSIM (Phase 1, all)
**Read ALL instructions first** before executing. Understand teaching intent — intentional errors, progressive disclosure, and troubleshooting exercises are not bugs.

**Intentional vs unintentional errors:** Before reporting a bug, determine if the error is deliberate:

| Signal | Intentional (not a bug) | Unintentional (real bug) |
|--------|------------------------|--------------------------|
| Course book | Says "troubleshoot", "debug", "fix the error" | Says "run this" / "this should work" |
| Objectives | Include "identify and correct" | No mention of troubleshooting |
| Guidance | Hints provided for resolution | No debugging path given |
| Student path | Can recover using provided hints | Stuck with no way forward |

If the exercise objective includes troubleshooting and the course book explicitly references the error, document it as INTENTIONAL and verify the hints are sufficient. Only report as a bug if the student has no reasonable path to resolution.

Execute step by step, translating each instruction:
- Commands → `ssh_tool.py run` or `devcontainer-run`
- File creation → `ssh_tool.py write-file` (base64 encoded)
- File edits → read, modify, write back
- Interactive prompts → rewrite non-interactively
- GUI steps → see programmatic equivalents table below

**Verification steps (GEs):** Steps marked `is_verification: true` are part of the exercise flow — execute them inline during simulation. Failure after correct preceding steps = P1. Report verification results as a subsection (e.g., "Verification: 4/4 checks passed").

**Parallel playbooks:** When playbooks target independent host groups (e.g., `ios` vs `junos`, or different managed hosts with no shared state), run them simultaneously using multiple Bash tool calls in the same message. This can cut playbook execution time by 50% or more. Limit to 4 concurrent SSH sessions — more than that saturates the SSH multiplexer and causes connection failures.

**Parallel verifications:** Run verification/auxiliary playbooks in a parallel batch the same way, respecting the 4-session limit.

**Parallel file uploads:** Use background shell (`&` + `wait`) to upload multiple files simultaneously. Keep batches to 4–6 files at a time to avoid saturating the SSH mux.

**Dev containers:** `devcontainer-start` → pre-pull EE → `devcontainer-run` for commands → `lab` commands on workstation → let `lab finish` handle cleanup.

**Network devices:** Apply 2x timeout multiplier. Expect 90-110s for lab start/finish.

**ansible-navigator noise:** Base64 UUID strings in output are metadata artifacts — ignore them, look for `PLAY RECAP`.

### TC-LIVEDIFF (Phase 1, if solutions exist)
After TC-STUDENTSIM completes, compare each student-created file against its corresponding solution file on the workstation. Use `ssh_tool.py diff <remote_path> --expected <base64>` or read both and compare. Mismatches that affect behavior = P2. Cosmetic-only differences (whitespace, trailing newline, comment ordering) = P3. This catches cases where EPUB instructions produce subtly different files than the solutions, or where solutions are stale.

### TC-WEB (Phase 1, if web apps/consoles)
Prefer `oc` CLI > `curl` > REST API > Playwright (in that order). Application not reachable = P1.

### TC-CLEAN + TC-SOL (merged, Phases 1+2)
**Run these together to avoid an extra lab start/finish cycle** — the re-start check that proves TC-CLEAN is the same fresh environment TC-SOL needs anyway.

```
lab finish          ← Phase 1 teardown; re-start check begins here
lab start           ← proves cleanup was complete (TC-CLEAN); also TC-SOL fresh env
verify initial state
apply solutions
run playbooks / grade
verify / grade
lab finish          ← TC-SOL teardown
```

Re-start failure = P1 incomplete cleanup. Solutions don't work = P1. 404 on deleting resources from other exercises is expected in progressive courses.

**Rollback resilience checks** (run if time permits, before applying solutions):
- **Double start**: `lab start` twice should handle gracefully — crash = P1, "already started" message = OK
- **Grade doesn't corrupt state**: After `lab grade`, `lab finish` and `lab start` should still work — failure = P1

### TC-SOLVE (Phase 2, if solve available — no separate TC-SOL)
Folded into the merged TC-CLEAN+TC-SOL cycle: after lab start, run `ssh_tool.py lab solve <exercise>` instead of copying solution files, then verify/grade → finish.

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

### Background Lab Start (TC-PREREQ)
Use `run_in_background: true` on the Bash tool to kick off the lab cycle while Phase 0 runs:
```bash
# Kick off in background — note the output file path returned in the tool result
python3 ssh_tool.py lab finish <exercise> && python3 ssh_tool.py lab start <exercise>
# [run Phase 0 static analysis here while this runs]
# Then read the result:
cat <output_file>   # or use the TaskOutput tool with the background task ID
```
Check `success` in the lab start JSON before proceeding. If the background task ID is lost, `ssh_tool.py run "lab -v"` confirms whether the lab is running.

### Applying Solutions (TC-SOL)
```bash
# Preferred: solutions/ subdirectory is always present inside the exercise dir after lab start
ssh_tool.py run "cp -r /home/student/<ex>/solutions/group_vars /home/student/<ex>/"
ssh_tool.py run "cp /home/student/<ex>/solutions/playbook.yml /home/student/<ex>/playbook.yml"
# Alternative: copy from grading package (use when solutions/ dir isn't available)
ssh_tool.py run "cp /path/to/grading/materials/labs/<ex>/solutions/playbook.yml /home/student/<ex>/"
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

### Bug Types

Bugs have both a severity (P0-P3) and a type. Include the type in bug IDs when applicable.

| Type | Description | Example |
|------|-------------|---------|
| **TECH** | Technical failure (default) | File not found, syntax error, service fails |
| **PEDAGOGY** | Solution contradicts teaching | Course teaches `copy` module, solution uses `template` |
| **SEQUENCE** | Exercise uses concepts not yet taught | Vault used in Ch.2 but taught in Ch.5 |
| **COMPLEXITY** | Exercise scope exceeds stated objective | Objective says "learn variables", exercise adds roles + vault + handlers |
| **GUIDANCE** | Intentional error lacks sufficient hints | "Fix the error" with no indication of where to look |

Format: `BUG-<TYPE>-NNN` (e.g., `BUG-PEDAGOGY-001`). Use `TECH` for standard technical bugs. Pedagogical types are typically P2 unless they block the student (then P0/P1).

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
- **Performance budgets** (use tool-reported `duration` values, not wall-clock time — wall clock includes LLM processing and will always be inflated when running interactively):
  - lab start > 120s → flag as LAB (normal: 60–110s; network device courses: up to 120s)
  - lab finish > 90s → flag as LAB (normal: 30–55s)
  - Total lab operation time (sum of all tool durations) > 10min → flag

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
- **SSH host key changed** → the environment was *reprovisioned*, not just a transient drop. Clear the stale entry (`ssh-keygen -R <host>`), reconnect, and flag any timing data collected before the reprovision as unreliable. This is an **ENV** issue.
- `lab finish` takes much longer than usual (e.g., 500s vs normal 40s) → VMs rebooted after a reprovision and are slow to respond; not a course bug. **ENV**.
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
