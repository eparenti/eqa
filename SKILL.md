---
name: eqa
version: 5.4.0
description: Automated exercise QA for Red Hat Training courses
authors:
  - Ed Parenti <eparenti@redhat.com>
  - Claude Code
---

# eqa - Exercise QA for Red Hat Training

Fully automated quality assurance for ANY Red Hat Training course. Works with any course through auto-detection: Ansible, OpenShift, RHEL, Satellite, AAP Controller, Network Automation.

## Quick Start

```bash
# Test a single exercise
/eqa AU0024L scale-files

# Test a chapter (multi-repo course)
/eqa AU294 --chapter 6

# Test all exercises in a lesson
/eqa AU0024L

# Test from EPUB path
/eqa /path/to/COURSE.epub exercise-name

# End-to-end testing (exercise independence)
/eqa AU294 --chapter 4 --e2e
```

**What happens automatically:**
- Detects course structure (single-repo, multi-repo, chapter-based)
- Detects technology (Ansible, OpenShift, AAP, Network Devices)
- Detects exercise type (GE vs Lab)
- Tests on live systems using actual `lab` commands
- Generates comprehensive QA report with quality metrics

**Zero manual configuration required.**

## Setup Workflow

When invoked, follow these steps in order:

### 1. Resolve Input

```bash
python3 ~/git-repos/eqa/.skilldata/scripts/course_tool.py resolve <input> [--chapter N]
```

Returns `{epub_path, lesson_path, lesson_code}`. If chapter is specified, resolves course outline to the correct lesson.

### 2. Parse EPUB

```bash
python3 ~/git-repos/eqa/.skilldata/scripts/epub_tool.py parse <epub_path> --lesson-path <lesson_path>
```

Returns `{course_code, course_title, exercises: [{id, type, title, solution_files}], extract_dir}`.

### 3. Connect SSH

```bash
python3 ~/git-repos/eqa/.skilldata/scripts/ssh_tool.py connect --host workstation
```

Establishes ControlMaster connection, detects lab framework. State persists in `/tmp/eqa-ssh-state.json`.

### 4. Build Course Profile

```bash
python3 ~/git-repos/eqa/.skilldata/scripts/profile_tool.py build <extract_dir>
```

Analyzes EPUB content to detect: technology stack, dev containers, tool locations, teaching patterns, ansible collections, real hosts, network devices.

### 5. Ensure Correct Lab Package

The grading package on the workstation **must match** the EPUB being tested. A version mismatch means grading checks, VM names, and exercise logic may differ from the EPUB instructions — causing false test failures.

#### How lab packages work

The DynoLabs 5 Rust CLI (`/usr/local/bin/lab`) manages Python grading packages via `uv`. Key concepts:

- **Lab manifest** (`~/.grading/lab_manifest.json`): Maps exercise names to course SKUs and versions
- **Course packages** (e.g., `rht-labs-do316`, `rht-labs-au0022l`): Python packages containing grading scripts, Ansible playbooks, and lab materials
- **Active course**: Only one course is "active" at a time (`lab version` shows it)
- **PyPI mirror**: Packages are fetched from `pypi.apps.tools-na.prod.nextcle.com`

#### Package installation commands

| Command | Behavior | Use When |
|---------|----------|----------|
| `lab install <sku>` | Respects manifest constraints, blocks non-manifest packages | Normal student/instructor use |
| `lab force <sku>` | **Bypasses all constraints**, always updates manifest | Dev/testing, installing packages not in manifest |
| `lab force <sku>=<version>` | Force-installs exact version | Testing specific version |
| `lab activate <sku>` | Switches active course (no install) | Switching between already-installed courses |
| `lab list` | Shows installed courses and active status | Checking what's available |
| `lab version` | Shows active course library and version | Verifying active package |

#### Step 5 workflow

**a) Check what's installed:**
```bash
ssh_tool.py run "lab version"
ssh_tool.py run "lab list"
```

**b) Determine the correct package SKU.** The `course_tool.py resolve` output includes the `lesson_code`. For multi-repo courses, each chapter has its own SKU (e.g., `au0022l`). For single-repo courses, the SKU is the course code (e.g., `do316`).

**c) Install or force-install the package:**

```bash
# If the package is in the manifest:
ssh_tool.py lab install <lesson_code>

# If blocked ("not part of this course curriculum"), use force:
ssh_tool.py run "lab force <lesson_code>"
```

`lab force` bypasses the manifest version lock and course validation. It is designed for developers and testers. It always updates the manifest to reflect the forced installation.

**d) Verify the active package matches:**
```bash
ssh_tool.py run "lab version"
```

**e) For multi-repo courses**, `lab install` or `lab force` must be run each time you switch to a different lesson — installing a new lesson replaces the previous one.

#### Namespace syntax for cross-course exercises

When multiple installed courses have exercises with the same name, use namespace syntax:
```bash
lab start <sku>::<exercise>
# e.g.: lab start do316::storage-review
```

#### Detecting version mismatches

After `lab start`, immediately run `lab grade` to compare grading checks against the EPUB:

```bash
# After lab start succeeds, run grade to see what the installed package checks
ssh_tool.py lab grade <exercise>
```

- Compare the grading check descriptions (VM names, project names, resource names) against the EPUB steps
- If they don't match, the installed package is a different version than the EPUB
- Use `lab version` to see the installed package version vs the EPUB's `pyproject.toml` version
- Use `lab force <sku>` to install the correct version matching the EPUB

### 6. Network Tunnel (for web UI testing)

To access classroom web UIs (OCP console, AAP Controller, Satellite, deployed web apps) from the local machine for Playwright testing or `curl` verification, set up a network tunnel via sshuttle.

**a) Get the classroom subnets:**
```bash
ssh_tool.py status
```
The `subnets` field in the output lists the classroom networks (e.g., `["172.25.250.0/24", "192.168.50.0/24"]`).

**b) Start sshuttle:**

`sshuttle` requires sudo. Ask the user to run the command in a separate terminal:
```bash
sudo sshuttle --dns -r workstation <subnet1> <subnet2> ... -D
```

**c) Verify connectivity:**
```bash
curl -sk -o /dev/null -w '%{http_code}' https://<any-classroom-url>/
```

This step is **optional** — only needed for TC-WEB testing with Playwright or direct `curl` from the local machine. If skipped, use `ssh_tool.py run "curl ..."` to access web services via the workstation instead.

## Test Categories

Execute these for each exercise. Collect ALL bugs before reporting (error summary pattern — don't fail-fast). The order below is the recommended sequence, but use judgment to skip or adapt based on context.

### TC-PREREQ: Prerequisites

1. Run `ssh_tool.py lab start <exercise>`
2. If start fails due to blocking lab, ssh_tool handles it automatically (finishes blocking lab, retries)
3. If start has FAIL in output, report as P0 bug
4. Verify SSH connectivity to all managed hosts the exercise uses (check the course profile's `real_hosts`)

### TC-EXEC: Command Pre-flight Validation

Before running commands on live systems, validate them:

1. Get instructions: `epub_tool.py instructions <epub> <exercise_id>`
2. Check each command for:
   - **Syntax errors** — missing quotes, unmatched braces, invalid YAML references
   - **Dangerous operations** — `rm -rf /`, unqualified `dd`, `mkfs` on wrong device
   - **Missing dependencies** — commands referencing files that don't exist yet and aren't created by prior steps
   - **Consistency** — filenames in commands match filenames in prose/file_actions
3. Report issues as P2 (syntax) or P3 (style) bugs WITHOUT executing them

### TC-STUDENTSIM: Student Simulation

**Read the whole exercise first.** Before executing anything, get the full instructions with `epub_tool.py instructions` and read through all steps. Understand what files need to be created, what config needs to be edited, and what the exercise is trying to teach. This context is critical for making decisions during execution.

Then execute step by step:

1. For each step, translate the instruction into tool calls:
   - Commands in `<pre>` blocks → `ssh_tool.py run` or `devcontainer-run`
   - File creation instructions (prose like "Create a file X containing Y") → `ssh_tool.py write-file`
   - File content from EPUB `file_actions` → `ssh_tool.py write-file`
   - Config file edits (prose like "Add this line to ansible.cfg") → read the file, modify it, write it back
   - Interactive commands (vault prompts, passwords) → rewrite to non-interactive form or use `ssh_tool.py interactive`
   - Verification steps → execute and interpret output
2. Track which steps pass/fail and why
3. Track execution time per step for performance metrics

**ansible-navigator: always add `-m stdout`** to prevent the interactive TUI from hanging.

**Dev container exercises:** If the course profile shows `uses_dev_containers`:
1. After `lab start`, use `ssh_tool.py devcontainer-start <project_dir>`
2. Pre-pull the EE image: read `ansible-navigator.yml` for the image name, then `podman pull` it inside the container
3. Run exercise commands via `ssh_tool.py devcontainer-run`
4. `lab` commands still run on workstation (not in container)
5. Let `lab finish` handle container cleanup (do NOT run `devcontainer-stop` before `lab finish`)

**GUI steps have programmatic equivalents:**

| GUI Step | Programmatic Equivalent |
|----------|------------------------|
| "Open folder in VS Code" | No-op (project dir already exists) |
| "Reopen in Container" | `ssh_tool.py devcontainer-start <project_dir>` |
| "Create new file / save as X" | `ssh_tool.py write-file` with content from step context |
| "Edit file / add content" | Read file, modify, write back via `ssh_tool.py` |
| "Run in terminal" | `ssh_tool.py devcontainer-run <command>` |
| "Create .xxx_pass containing PASSWORD" | `ssh_tool.py write-file` + `chmod 600` |
| "Add line to ansible.cfg" | Read ansible.cfg, add line, write back |
| "Open browser to URL" | `web_tool.py navigate <url>` or `curl` |
| "Click button / fill form" | `web_tool.py click <selector>` / `web_tool.py fill <selector> <value>` |
| "Log in to the web console" | `web_tool.py login <console-url> --username <user> --password <pass> --then <target-url>` |
| "Verify page shows X" | `web_tool.py page-text` and check for expected content |
| "Take screenshot" | `web_tool.py screenshot /tmp/screenshot.png` |
| "Navigate to VM list" | `web_tool.py navigate "https://console.../k8s/ns/<project>/kubevirt.io~v1~VirtualMachine"` |
| AAP Controller UI actions | `rht-labs-aapcli` or Controller REST API via `web_tool.py api-get/api-post` |
| OCP web console: Add disk to VM | `oc` create PVC + `virtctl addvolume` + restart VM |
| OCP web console: Create project | `oc new-project <name>` |
| OCP web console: Check resource status | `oc get <resource> -n <project>` |

**ansible-vault commands:** Rewrite interactive vault commands to non-interactive form:
- `ansible-vault encrypt file` → `ansible-vault encrypt --vault-password-file /tmp/pass file` (write password to temp file first)
- `ansible-vault encrypt --vault-id name@prompt file` → `ansible-vault encrypt --vault-id name@/tmp/pass file`
- `--ask-vault-pass` → `--vault-password-file /tmp/pass`
- `ansible-vault create` → create empty file + `ansible-vault encrypt`

**Network device commands:** For courses with Cisco, Juniper, or Arista devices, use 2x timeout multipliers. Network device SSH sessions are slower and may need `pexpect` for interactive prompts.

**Interpreting failures:** Not all command failures are bugs:
- Verification steps may legitimately return non-zero
- Troubleshooting exercises have *intentional* failures (check course profile for `has_intentional_errors` and `exercises_with_deliberate_bugs`)
- EE image pull with "no space left on device" is an environment issue
- `ansible-navigator` returning non-zero with `PLAY RECAP` means the playbook ran but had Ansible errors — read the output to determine if it's an exercise bug or expected behavior

### TC-VERIFY: Verification (GEs)

For Guided Exercises, after completing the student simulation:

1. Re-run any steps marked `is_verification: true` in the instructions
2. Check that verification commands produce the expected output (compare with what the EPUB describes)
3. If a verification step fails after successfully completing all prior steps, it's a **P1 bug** — the instructions don't produce the outcome they claim
4. Common verification patterns: `curl`, `ssh host 'command'`, `ansible-navigator inventory --list`, `systemctl status`

### TC-SOL: Solution Files

Tested SEPARATELY from student simulation — fresh start, apply solutions, verify.

1. Run `ssh_tool.py lab start <exercise>` (fresh start, clean state)
2. Copy each solution file to its correct location on workstation
3. For `.sol` extension files: copy without the `.sol` suffix
4. Run any playbooks the solutions provide (check EPUB instructions for the `ansible-navigator run` commands)
5. Verify the exercise works: for Labs, run `lab grade`; for GEs, run verification commands
6. If solution files don't produce the expected state: **P1 bug**
7. Run `ssh_tool.py lab finish <exercise>` to clean up

### TC-SOLVE: Solve Scripts (if available)

Some exercises have a `lab solve <exercise>` command that applies solutions automatically.

1. Run `ssh_tool.py lab start <exercise>` (fresh start)
2. Run `ssh_tool.py lab solve <exercise>` (if the framework supports it)
3. For Labs: run `lab grade` — should pass
4. For GEs: run verification commands — should pass
5. If solve doesn't produce a gradeable/verifiable state: **P1 bug**
6. Run `ssh_tool.py lab finish <exercise>` to clean up

### TC-GRADE: Grading (Labs Only)

**Critical: DynoLabs grading exit codes do NOT indicate pass/fail of checks.** See `.skilldata/docs/dynolabs-grading.md`.

1. **Grade WITHOUT solution** (after lab start, before any work):
   ```bash
   ssh_tool.py lab grade <exercise>
   ```
   - Exit code 0 is normal (script completed)
   - Parse output for PASS/FAIL indicators
   - All checks SHOULD fail (student hasn't done anything)
   - If all checks pass: **P1 FALSE POSITIVE bug** (grading doesn't validate anything)

2. **Apply solution files** (or complete student simulation)

3. **Grade WITH solution**:
   ```bash
   ssh_tool.py lab grade <exercise>
   ```
   - Exit code must be 0 (non-zero = P0 script crash)
   - All checks SHOULD pass
   - If any check fails: **P1 FALSE NEGATIVE bug** (grading rejects correct solution)

4. **Grade message quality**: Check that error messages are clear and actionable, not raw Python tracebacks or cryptic codes. Unclear messages are P2 bugs.

### TC-CONTRACT: Contract Validation

Verify alignment between EPUB instructions, solution files, and grading scripts:

1. **EPUB → Solutions**: Every file the EPUB tells students to create should have a corresponding solution file. Missing solutions: **P2 bug**
2. **Solutions → Grading**: Every check in the grading script should be satisfiable by the solution files. If grading checks something the solutions don't provide: **P1 bug**
3. **EPUB → Grading**: Every outcome the EPUB claims should be validated by grading (for Labs). If the EPUB describes an outcome that grading doesn't check: **P2 bug**
4. **Naming consistency**: Exercise IDs, file paths, and variable names should be consistent across EPUB, solutions, and grading. Mismatches: **P3 bug**

### TC-CLEAN: Cleanup

1. Run `ssh_tool.py lab finish <exercise>`
2. If finish has FAIL in output: **P1 cleanup bug**
3. Verify cleanup completeness: run `ssh_tool.py lab start <exercise>` again
4. If start fails after finish: **P1 incomplete cleanup**
5. Check that cleanup removes ALL artifacts:
   - Users, groups, files, directories created during the exercise
   - Services started/enabled
   - Configuration changes
   - Firewall rules
   - Containers, images
6. Run `ssh_tool.py lab finish <exercise>` to clean up after verification

### TC-IDEM: Idempotency

Run the full cycle (start → simulate → grade → finish) at least twice. Compare results.

1. **Cycle 1**: Normal execution
2. **Cycle 2**: Should produce identical results
3. If cycle 2 fails where cycle 1 passed: **P1 state pollution bug**
4. Common idempotency issues:
   - Incomplete cleanup (not removing all artifacts)
   - Asymmetric operations (setup on host A, cleanup on host B)
   - Conditional artifacts (created based on conditions, cleanup unconditional)
   - Forgotten dependencies (groups, files, services not cleaned)

### TC-E2E: Exercise Independence

Validate that exercises don't depend on state from previous exercises.

1. Run exercise B WITHOUT running exercise A first
2. If exercise B fails because it assumes state from exercise A: **P1 independence bug**
3. Exception: progressive exercises (check course profile for `progressive_exercises: true`) are allowed to depend on prior exercises, but must declare their dependencies

### TC-INSTRUCT: Instruction Quality

Analyze the quality of EPUB instructions:

1. **Completeness**: Every file the student needs to create should have clear content specified. Vague instructions like "add the appropriate content" without showing what: **P2 bug**
2. **Accuracy**: Commands in instructions should match the expected tool versions. e.g., `ansible-playbook` in a course that uses `ansible-navigator`: **P2 bug**
3. **Clarity**: Steps should be unambiguous. If a step could be interpreted multiple ways: **P3 bug**
4. **Ordering**: Steps should be in a logical order. If step N references something created in step N+2: **P2 bug**
5. **Consistency**: File names, variable names, and host names should be consistent throughout the exercise: **P3 bug**

### TC-SECURITY: Security Review

Check for security anti-patterns in exercise content:

1. **Hardcoded credentials**: Passwords in plain text in playbooks (other than vault-encrypted): **P2 bug**
2. **Overly permissive files**: `chmod 777`, world-readable credential files: **P2 bug**
3. **Insecure protocols**: HTTP where HTTPS should be used, telnet instead of SSH: **P3 bug**
4. **Root access**: Unnecessary use of `become: true` or running as root when not needed: **P3 bug**
5. **Missing validation**: Playbooks that don't validate input or use `unsafe`: **P3 bug**

Note: Many exercises intentionally use simple credentials for teaching purposes. Only flag security issues that teach bad habits students might carry to production.

### TC-WEB: Web Application and Web Console Testing

For exercises that deploy web applications or use web consoles (OpenShift, AAP Controller, Satellite):

**Verification methods (in order of preference):**

1. **`oc` CLI** — fastest and most reliable for resource state verification:
   ```bash
   ssh_tool.py run "oc get vm -n <ns>"              # VM status
   ssh_tool.py run "oc get pvc -n <ns>"             # Storage state
   ssh_tool.py run "oc get route -n <ns>"           # Route/URL info
   ssh_tool.py run "oc get pods -n <ns>"            # Pod status
   ```

2. **`curl` from workstation** — verify web apps are reachable and return expected content:
   ```bash
   ssh_tool.py run "curl -sk https://<route-url>/"  # Check web app response
   ssh_tool.py run "curl -sk -o /dev/null -w '%{http_code}' https://<url>"  # Just status code
   ```

3. **`web_tool.py api-get/api-post`** — REST API verification (no Playwright needed):
   ```bash
   web_tool.py api-get "https://<url>/api/v1/..." --headers '{"Authorization": "Bearer <token>"}'
   ```

4. **`web_tool.py` with Playwright** — full browser testing (requires `pip install playwright && playwright install chromium` and sshuttle tunnel — see Setup Step 6).

   With the tunnel active, use web_tool.py locally:
   ```bash
   # Login and navigate to a page in one session (important: use the console URL, not the OAuth URL)
   web_tool.py login "https://console-openshift-console.apps.ocp4.example.com" \
     --username admin --password redhatocp \
     --then "https://console-openshift-console.apps.ocp4.example.com/k8s/ns/<ns>/kubevirt.io~v1~VirtualMachine" \
     --screenshot "/tmp/ocp.png"
   ```
   The `login` command handles the full OAuth redirect chain in a single browser session. **Always use the console URL** (not the OAuth authorize URL) — the console redirects to OAuth automatically and maintains proper state.

**When to use each method:**
- Resource existence and status → `oc` CLI (always available)
- Web app returns correct content → `curl` from workstation
- REST API responses → `web_tool.py api-get/api-post`
- Visual verification, form submissions, console-only workflows → Playwright (if available)
- Application not reachable after deployment: **P1 bug**
- Application shows wrong content: **P2 bug**

**AAP Controller:**
- Use `rht-labs-aapcli` at `~/git-repos/active/rht-labs-aapcli` for API operations
- Or use `web_tool.py api-get/api-post` for direct REST API calls
- Controller URL is typically `https://controller.example.com` or as specified in the exercise

## Bug Severity

| Severity | Description | Examples | Action |
|----------|-------------|----------|--------|
| **P0** | Exercise unusable | `lab start` crashes, SSH fails, missing lab command | STOP testing, report immediately |
| **P1** | Validation broken | Grading false positive/negative, cleanup incomplete, solution files don't work, verification fails after correct steps | MUST FIX before release |
| **P2** | Quality issue | Instruction step fails, unclear error messages, missing files, security anti-patterns | SHOULD FIX |
| **P3** | Polish | Typos in output, minor style issues, naming inconsistencies | Optional fix |

**Severity Decision Tree:**
1. Can the student complete the exercise? NO → **P0**
2. Can the student verify their work? NO → **P1**
3. Can the student practice repeatedly (idempotency)? NO → **P1**
4. Is the student experience good? NO → **P2**
5. Any minor issues? YES → **P3**

## Quality Metrics

Track these metrics across all exercises tested:

### Coverage
- **Exercise coverage**: % of exercises tested out of total in the chapter/course
- **Solution file coverage**: % of solution files that were tested and work correctly
- **Test category coverage**: Which TC-* categories were executed per exercise

### Defect Metrics
- **Total bugs found**: Count by severity (P0/P1/P2/P3)
- **Defect density**: Bugs per exercise (target: < 0.5)
- **Critical ratio**: P0+P1 bugs as % of total (target: < 20%)

### Performance
- **Execution time per exercise**: Track `lab start`, student sim, grading, and `lab finish` durations
- **Total chapter/course duration**: Sum of all exercise times
- **Slow exercises**: Flag any exercise where `lab start` or `lab finish` takes > 60s, or total exercise time exceeds 10 minutes. Slow exercises degrade the student experience.

### Release Readiness
Based on the metrics above, provide an assessment:
- **Ready**: 0 P0, 0 P1, defect density < 0.5
- **Conditional**: 0 P0, ≤ 2 P1, defect density < 1.0
- **Not ready**: Any P0, or > 2 P1, or defect density ≥ 1.0

## Failure Diagnostics

When a command or test fails, analyze the error and provide:

1. **Root cause**: What specifically went wrong (not just "command failed")
2. **Error category**: Classify into one of:
   - SSH/connectivity issue
   - Missing file/dependency
   - Permission error
   - Syntax error in playbook/config
   - Package not installed
   - Service not running
   - Grading logic error
   - EPUB instruction error
   - Environment issue (disk, memory, network)
   - Timeout
   - Vault/encryption issue
3. **Fix recommendation**: Specific action to resolve (not generic advice)
4. **Affected component**: EPUB, solution file, grading script, or lab script

## Report Format

Write individual exercise reports to `~/git-repos/eqa/results/`. Use filename pattern: `<exercise-id>-<YYYYMMDD-HHMMSS>.md`

When testing multiple exercises (chapter or course), also generate a **summary report** after all exercises are tested. Use filename pattern: `<course>-ch<N>-summary-<YYYYMMDD>.md`

### Report Structure

```markdown
# Exercise QA Report: <exercise-id>

**Course:** <course_code> - <course_title>
**Exercise:** <exercise_id> (<type>)
**Date:** <timestamp>
**Result:** PASS | FAIL

## Summary
<1-2 sentence overview>

## Quality Metrics
- Exercise coverage: N/M
- Defect density: X.X
- Critical ratio: X%
- Release readiness: Ready | Conditional | Not ready

## Test Results

### TC-PREREQ
- lab start: PASS/FAIL (Xs)

### TC-EXEC
- Commands validated: N
- Issues found: [list]

### TC-STUDENTSIM
- Steps executed: N/M
- Commands: passed/failed/skipped
- Files written: N
- Duration: Xs
- [Details of any failures with diagnostics]

### TC-VERIFY (GE only)
- Verification steps: passed/failed

### TC-SOL
- Solution files applied: N/M
- Playbooks executed: [list]
- Result: PASS/FAIL

### TC-GRADE (Lab only)
- Without solution: <expected FAIL, got ...>
- With solution: <expected PASS, got ...>
- Message quality: Good | Needs improvement

### TC-CONTRACT
- EPUB ↔ Solutions alignment: PASS/FAIL
- Solutions ↔ Grading alignment: PASS/FAIL

### TC-CLEAN
- lab finish: PASS/FAIL (Xs)
- Re-start verification: PASS/FAIL

### TC-IDEM (if run)
- Cycle 1: PASS/FAIL
- Cycle 2: PASS/FAIL

### TC-INSTRUCT
- Instruction quality issues: [list]

### TC-SECURITY
- Security findings: [list]

## Bugs Found
| ID | Severity | Category | Description | Fix Recommendation | Component |
|----|----------|----------|-------------|-------------------|-----------|

## Performance
| Phase | Duration |
|-------|----------|
| lab start | Xs |
| Student sim | Xs |
| Grading | Xs |
| lab finish | Xs |
| Total | Xs |

## Course Profile
<Key characteristics from profile_tool>
```

### Chapter Summary Report (for multi-exercise runs)

When testing a chapter or multiple exercises, generate a summary report after all individual reports:

```markdown
# Chapter QA Summary: <course> Chapter <N>

**Course:** <course_code> - <course_title>
**Chapter:** <N> (<keyword>)
**Date:** <timestamp>
**Exercises tested:** N/M
**Result:** PASS | CONDITIONAL | FAIL

## Exercise Results

| Exercise | Type | Result | Bugs | Duration |
|----------|------|--------|------|----------|
| exercise-1 | GE | PASS | 0 | 45s |
| exercise-2 | GE | PASS | 1 P3 | 52s |
| exercise-3 | Lab | FAIL | 1 P1 | 68s |

## Aggregate Metrics

- Total bugs: N (P0: N, P1: N, P2: N, P3: N)
- Defect density: X.X bugs/exercise
- Critical ratio: X%
- Total test duration: Xs
- Release readiness: Ready | Conditional | Not ready

## All Bugs

| ID | Exercise | Severity | Description | Component |
|----|----------|----------|-------------|-----------|

## Recommendations

<Prioritized list of fixes needed before release>
```

## Utility Reference

See `.skilldata/docs/tools-reference.md` for full tool documentation (ssh_tool.py, epub_tool.py, course_tool.py, profile_tool.py, web_tool.py).

Key commands used most often:
- `ssh_tool.py run <cmd>` — execute command on workstation
- `ssh_tool.py lab <action> <exercise>` — lab start/finish/grade/force/solve
- `ssh_tool.py vm-exec <vm> -n <ns> -c <cmd>` — run command inside a VM
- `ssh_tool.py vm-disks <vm> -n <ns>` — list VM disk attachments as JSON
- `ssh_tool.py tunnel` — generate sshuttle command for network tunnel
- `web_tool.py login <url> --username <u> --password <p> --then <url>` — web console login

## Course Patterns

The skill auto-detects 3 course patterns from `outline.yml`:

### Pattern 1: Single-Repo, Lesson-Based
- One repository with all lessons
- `outline.yml` has `dco:` root key, no `repository:` fields
- Materials at `materials/labs/{exercise-name}/`

### Pattern 2: Multi-Repo, Lesson-Based (e.g., AU294)
- Multiple repositories, one per chapter/lesson
- `outline.yml` has `dco:` root key WITH `repository:` fields pointing to lesson repos
- Each lesson cloned separately
- Requires `lab install <lesson_code>` before testing

### Pattern 3: Single-Repo, Chapter-Based
- One repository with chapter-based organization
- `outline.yml` has `course:` root key
- Materials at `content/{chapter-keyword}/`

### OpenShift / Kubernetes Courses (DO*)

See `.skilldata/docs/ocp-recipes.md` for full OCP reference including VM disk operations, storage classes, web console testing with Playwright, dev container exercises, and ansible-navigator usage.

Key points:
- Use `ssh_tool.py vm-exec <vm> -n <ns> -c <cmd>` to run commands inside VMs (auto-detects SSH vs console auth)
- Use `ssh_tool.py vm-disks <vm> -n <ns>` to verify disk attachments
- Use `virtctl addvolume --persist` for SCSI hot-plug, DataVolume + `oc patch` for virtio
- Use `web_tool.py login <console-url> --username admin --password redhatocp --then <target-url>` for web console
- Always append `-m stdout` to `ansible-navigator` commands
- For dev containers: `devcontainer-start` → `devcontainer-run` → let `lab finish` handle cleanup

## Decision Points

- **Lab start fails with "another lab is running"**: ssh_tool handles this automatically by finishing the blocking lab
- **Command times out**: Retry once with 2x timeout. If still fails, record as P2 and continue
- **SSH drops mid-test**: ssh_tool auto-reconnects on stale sockets. If that fails, run `ssh_tool.py connect` again
- **Exercise not found in EPUB**: Check for fuzzy matches (the exercise ID in instructions may differ from what was requested)
- **Grade passes without solution**: This is a P1 bug, not a false alarm. DynoLabs grading SHOULD fail when student hasn't done the work
- **All steps pass but grade fails**: Check if solution files need to be applied differently, or if grading checks something the instructions don't cover
- **EE image pull fails "no space left on device"**: Environment issue. Run `podman system prune -af` and `rm -rf ~/.cache/uv` on workstation
- **Exercise has GUI steps**: Translate to programmatic equivalents (see GUI translation table above)
- **ansible-navigator hangs**: Missing `-m stdout` flag. Always append it for non-interactive execution
- **AAP Controller web UI steps**: Use `rht-labs-aapcli` or Controller REST API via `web_tool.py api-get/api-post`
- **Switching lessons in multi-repo course**: Must run `lab install <new-lesson>` (or `lab force <new-lesson>`) before testing exercises in a different lesson
- **`lab install` fails "not part of this course curriculum"**: Use `lab force <sku>` to bypass manifest constraints. This is normal when the workstation is provisioned for a different course (e.g., workstation has DO981 but you're testing DO316 exercises). `lab force` always works and updates the manifest.
- **Version mismatch between EPUB and installed package**: The installed grading package may have different VM names, exercise logic, or grading checks than the EPUB. Use `lab force <sku>` to install the correct version matching the EPUB. Check `lab version` vs the git repo's `pyproject.toml`
- **OCP exercise needs storage**: Always run `oc get sc` first to find the right storage class. Don't hardcode storage class names
- **Running commands inside VMs**: Use `ssh_tool.py vm-exec <vm> -n <ns> -c <cmd>`. It tries `virtctl ssh` first (key auth), then falls back to serial console with login automation. Check `vm_auth` and `vm_default_password` in the course profile for auth method.
- **`virtctl console` hangs**: Use `ssh_tool.py vm-exec` instead, or `virtctl ssh --command` for non-interactive VM access
- **VM disk not visible after attach**: The VM needs a restart. Stop → add volume → start
- **OCP web console steps**: Prefer `oc` CLI equivalents for reliability. Use `web_tool.py` Playwright for visual verification and web-console-only workflows
- **Network device exercises**: Apply 2x timeout multiplier for all SSH/device commands
- **Troubleshooting exercise**: Check `exercises_with_deliberate_bugs` in profile — failures may be intentional

## Lab CLI Reference

See `.skilldata/docs/lab-cli.md` for full DynoLabs 5 reference including package management, lab operations, testing features, key files, and environment variables.

Key commands: `lab start/finish/grade/solve <exercise>`, `lab force <sku>` (bypass manifest), `lab version`, `lab list`, `lab status --reset`.

References: [Lab CLI (Rust)](https://github.com/RedHatTraining/classroom-api), [rht-labs-core](https://github.com/RedHatTraining/rht-labs-core)

## Cleanup

Always disconnect when done:
```bash
python3 ~/git-repos/eqa/.skilldata/scripts/ssh_tool.py disconnect
```
