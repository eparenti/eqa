---
name: eqa
version: 7.1.0
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

## Critical Rules

These seven rules prevent the most common time-wasting mistakes. Internalize them before testing.

1. **Paths must be absolute** — `devcontainer-start` does not expand `~`. Always use `/home/student/<exercise>`.
2. **write-file requires base64** — Encode content with `base64 -w0 /tmp/file.yml`, then pass via `--content`. Write locally first, encode, then upload.
3. **devops user for sudo** — `student` requires a password and will hang. `devops` has NOPASSWD sudo. Use `ssh devops@<host> 'sudo <cmd>'` for privileged operations on managed hosts.
4. **Dev container podman variant** — The tool checks `.devcontainer/podman/devcontainer.json` first (uses local registry, works). The default `devcontainer.json` may reference `registry.redhat.io` (fails without auth).
5. **ansible-navigator: always `-m stdout`** — Without it the interactive TUI hangs. Every `ansible-navigator run` command must include `-m stdout`.
6. **epub_tool commands are dicts** — Parsed commands from instructions JSON are `{"text": "...", ...}` dicts. Access with `.get("text")`, not string slicing. File actions are nested in `sub_steps[].file_actions[]`.
7. **URLs and hostnames come from the EPUB** — Never assume, carry over, or hardcode URLs, hostnames, or ports from prior exercises or session context. Always extract them from the current exercise's parsed instructions. The EPUB is the single source of truth for what URLs the student uses (e.g., `aap.lab.example.com` vs `controller.lab.example.com`, port 443 vs 8443). If a URL works in one exercise, that does not mean the same hostname/port applies to a different exercise.

### A Note on Examples

All hostnames, URLs, credentials, port numbers, and course-specific values in the recipes and examples below are **illustrative patterns** — they show the shape of the command, not the actual values to use. Always extract real values from:

1. **The EPUB** (parsed via `epub_tool.py`) — URLs, hostnames, ports, credentials, file content
2. **The course profile** (from `profile_tool.py`) — managed hosts, technology stack, dev container config
3. **The live environment** (via `ssh_tool.py`) — dynamic resource IDs, API-discovered values

Never copy an example value from this document into a live command.

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

Establishes ControlMaster connection, detects lab framework. State persists in `~/.cache/eqa/ssh-state.json`.

### 4. Build Course Profile

```bash
python3 ~/git-repos/eqa/.skilldata/scripts/profile_tool.py build <extract_dir>
```

Analyzes EPUB content to detect: technology stack, dev containers, tool locations, teaching patterns, ansible collections, real hosts, network devices.

### 4.5. Load HLD Document (Optional)

Ask the user: "Do you have an HLD (High-Level Design) document for this course? Loading it gives context about exercise intent, scenarios, and developer notes."

If the user provides an HLD path (`.docx` format):

1. Extract text from the docx using Python's `zipfile` and `xml.etree.ElementTree`:
   ```python
   import zipfile
   from xml.etree import ElementTree as ET
   docx = zipfile.ZipFile('<path-to-hld.docx>')
   xml = docx.read('word/document.xml')
   tree = ET.fromstring(xml)
   lines = []
   for p in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
       texts = [t.text for t in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if t.text]
       line = ''.join(texts).strip()
       if line:
           lines.append(line)
   ```

2. Parse the HLD for key information per lesson/section:
   - **Lesson goals** — what each chapter/lesson teaches
   - **Section types** — lecture, GE, quiz, lab
   - **Section objectives** — what each exercise should accomplish
   - **Scenarios/use cases** — the real-world context for the exercise
   - **Notes to developer** — design intent, known constraints, references to prior course sections
   - **Lesson status** — New, Existing, Major Update
   - **Complexity** — Low/Med/Hi

3. Store HLD context in session memory. Use it during:
   - **TC-STUDENTSIM**: Understanding teaching intent (step 2 of pre-execution checklist) — the HLD's "Notes to Developer" may explain why an exercise is designed a certain way
   - **TC-INSTRUCT**: Validating that exercise instructions achieve the stated objective from the HLD
   - **TC-CONTRACT**: Checking if grading aligns with the HLD's stated objectives
   - **Report writing**: Include the HLD objective in the exercise report summary for traceability

If the user declines or no HLD exists, skip this step — all other functionality works without it.

### 5. Ensure Correct Lab Package

The grading package on the workstation **must match** the EPUB being tested. A version mismatch means grading checks, VM names, and exercise logic may differ from the EPUB instructions — causing false test failures.

#### How lab packages work

The DynoLabs 5 Rust CLI (`/usr/local/bin/lab`) manages Python grading packages via `uv`. Key concepts:

- **Lab manifest** (`~/.grading/lab_manifest.json`): Maps exercise names to course SKUs and versions
- **Course packages** (e.g., `rht-labs-do316`, `rht-labs-au0022l`): Python packages containing grading scripts, Ansible playbooks, and lab materials
- **Active course**: Only one course is "active" at a time (`lab version` shows it)
- **PyPI mirror**: Packages are fetched from the Red Hat internal PyPI mirror (typically `pypi.apps.tools-na.prod.nextcle.com`, but may vary by environment)

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

## Testing Methodology

### Phased Approach

All applicable test categories run automatically for every exercise. The skill determines which TCs apply based on exercise type (GE vs Lab), available artifacts (solution files, solve scripts), and mode (`--e2e`).

**Phase 0: Static Analysis** (no live execution)
- TC-EXEC — command pre-flight validation (always)
- TC-INSTRUCT — instruction quality (always)
- TC-SECURITY — security review (always)
- TC-CONTRACT — contract validation (Labs with solution files)

**Phase 1: Student Simulation**
- TC-PREREQ — lab start (always)
- TC-GRADE pre-check — grade without solution, expect FAIL (Labs only)
- TC-STUDENTSIM — execute exercise (always)
- TC-VERIFY — verification steps (GEs only)
- TC-GRADE post-check — grade after simulation, expect PASS (Labs only)
- TC-WEB — web verification (if exercise deploys web apps or uses web consoles)
- TC-CLEAN — lab finish + re-start verification (always)

**Phase 2: Solution Validation** (separate cycle)
- TC-SOL — fresh start → apply solutions → grade/verify → finish (if solution files exist)
- TC-SOLVE — fresh start → lab solve → grade/verify → finish (if lab solve available)
- Run whichever applies; if both exist, run both as separate cycles

**Phase 3: Idempotency** (if Phase 1 passed)
- TC-IDEM — repeat Phase 1, compare results

**E2E** — only in `--e2e` mode (cross-exercise, fundamentally different from per-exercise testing)

Use the **Recipes** section below to execute each step efficiently — the recipes eliminate the common trial-and-error that slows testing down.

### Quick-Reference Phase Checklists

**GE (Guided Exercise):**
```
Phase 0: TC-EXEC → TC-INSTRUCT → TC-SECURITY
Phase 1: lab start → student sim → verify → lab finish → re-start check → lab finish
Phase 2: lab start → apply solutions → run playbooks → verify → lab finish (if solution files exist)
Phase 3: compare Phase 1 vs Phase 2 results (or repeat Phase 1 if no solutions)
```

**Lab:**
```
Phase 0: TC-EXEC → TC-INSTRUCT → TC-SECURITY → TC-CONTRACT
Phase 1: lab start → grade (pre-check, expect mostly FAIL) → student sim → grade (post-check, expect PASS) → lab finish → re-start check → lab finish
Phase 2: lab start → apply solutions → run playbooks → grade (expect PASS) → lab finish (if solution files exist)
Phase 3: compare Phase 1 vs Phase 2 results (or repeat Phase 1 if no solutions)
```

### Batch Chapter Testing

When testing all exercises in a chapter:
1. Get the exercise list from `epub_tool.py parse` filtered by chapter
2. Test each exercise sequentially through all applicable phases (Phase 0 → 1 → 2 → 3)
3. Track results as JSON for each exercise
4. Use `report_tool.py chapter` to generate the summary report
5. Use `report_tool.py score` to calculate the quality score

### Error Summary Pattern

Collect ALL bugs before reporting (don't fail-fast):
- Students see all problems at once
- Fix multiple issues in one iteration
- Exception: P0 blockers may stop testing early

When any command fails, run the output through `diagnose_tool.py analyze` for automatic root cause identification.

### Performance Budgets

Track execution times and flag slow exercises:

| Phase | Budget | Flag if exceeds |
|-------|--------|-----------------|
| `lab start` | 60s | Slow start — may frustrate students |
| `lab finish` | 60s | Slow cleanup |
| Student simulation | 600s (10 min) | Exercise may be too complex |
| Total exercise | 900s (15 min) | Total time excessive |

Use `report_tool.py score` to check performance budget violations across a chapter.

### Quality Score (0-100)

Calculated automatically by `report_tool.py score`:
- **Coverage** (30 pts): exercises tested / total
- **Defects** (40 pts): penalty per bug (P0=-40, P1=-20, P2=-5, P3=-1)
- **Reliability** (30 pts): cleanup + idempotency pass rate

| Score | Assessment |
|-------|------------|
| 90-100 | Ready for release |
| 70-89 | Conditional — fix P1+ bugs |
| 50-69 | Needs work — multiple issues |
| <50 | Not ready |

## Recipes

Copy-paste patterns for the most common operations. Use these during student simulation and QA validation to avoid trial-and-error.

### Recipe: Dev Container Lifecycle

Dev container exercises require specific ordering. All paths must be absolute.

```bash
# 1. Start the dev container (ABSOLUTE path — ~ does not expand)
ssh_tool.py devcontainer-start /home/student/<exercise>

# 2. Read ansible-navigator.yml for the EE image name
ssh_tool.py devcontainer-run "cat /home/student/<exercise>/ansible-navigator.yml"

# 3. Pre-pull the EE image inside the container (use --tls-verify=false for local registry)
ssh_tool.py devcontainer-run "podman pull --tls-verify=false utility.lab.example.com:5000/<ee-image>:<tag>"

# 4. Run exercise commands inside the container
ssh_tool.py devcontainer-run "cd /home/student/<exercise> && ansible-navigator run playbook.yml -m stdout"

# 5. lab commands run on workstation, NOT in the container
ssh_tool.py lab grade <exercise>

# 6. Let lab finish handle container cleanup — do NOT run devcontainer-stop before lab finish
ssh_tool.py lab finish <exercise>
```

Notes:
- The `.devcontainer/podman/devcontainer.json` variant uses the local registry and works without auth. The tool checks for it automatically.
- Files written to the project directory on the workstation appear inside the container automatically (bind mount).
- If the EE pull fails with "no space left on device", run `ssh_tool.py run "podman system prune -af"` on workstation first.
- **Container user matters for grading.** The `devcontainer-start` command reads `containerUser` from `devcontainer.json` and passes it as `--user` to `podman run`. This sets the container's default user, which grading scripts inherit when running `podman exec`. If the container user is wrong (e.g., image default instead of `root`), grading may fail with permission errors even though student simulation succeeded.

### Recipe: Writing Files

The `write-file` command requires base64-encoded content. Batch multiple files for efficiency.

```bash
# 1. Write file content locally using the Write tool
# (Write tool) → /tmp/playbook.yml

# 2. Encode to base64
base64 -w0 /tmp/playbook.yml
# Capture the output as $encoded

# 3. Upload to workstation
ssh_tool.py write-file /home/student/<exercise>/playbook.yml --content "$encoded"

# Batch pattern: write all files locally first, then upload all at once
ssh_tool.py write-file /home/student/<exercise>/file1.yml --content "$(base64 -w0 /tmp/file1.yml)" && \
ssh_tool.py write-file /home/student/<exercise>/file2.yml --content "$(base64 -w0 /tmp/file2.yml)"
```

### Recipe: Applying Solution Files

For TC-SOL testing (Phase 2). Start from a clean state.

```bash
# 1. List available solution files
ssh_tool.py run "ls /home/student/<exercise>/solutions/"

# 2. Copy each .sol file to its target location (strip the .sol suffix)
ssh_tool.py run "cp /home/student/<exercise>/solutions/playbook.yml.sol /home/student/<exercise>/playbook.yml"

# 3. For dev container exercises: copy into the project dir on workstation —
#    files appear in container automatically via bind mount

# 4. Run playbooks from solutions (check EPUB instructions for the exact commands)
ssh_tool.py run "cd /home/student/<exercise> && ansible-navigator run playbook.yml -m stdout"
# or inside dev container:
ssh_tool.py devcontainer-run "cd /home/student/<exercise> && ansible-navigator run playbook.yml -m stdout"
```

### Recipe: Git Clone with Credentials

Gitea credentials often contain special characters (e.g., `Student@123`). URL-encode them in clone URLs.

```bash
# The @ in the password must be encoded as %40
ssh_tool.py run "git clone http://student:Student%40123@utility.lab.example.com:3000/student/<repo>.git"

# Common URL encodings: @ → %40, # → %23, $ → %24, % → %25, & → %26, + → %2B
# Get credentials from the course profile (gitea_user, gitea_password) or EPUB instructions
```

### Recipe: Gitea API Authentication

When Gitea credentials contain `@` (e.g., `Student@123`), `curl -u` fails. Use base64 Basic auth or token auth:

```bash
# Option 1: Base64-encoded Basic auth header
# Encode "student:Student@123" → "c3R1ZGVudDpTdHVkZW50QDEyMw=="
ssh_tool.py run "curl -sk -H 'Authorization: Basic <base64(user:pass)>' http://utility.lab.example.com:3000/api/v1/repos/student/<repo>/hooks"

# Option 2: Create a token first, then use it
# Note: Gitea API tokens require explicit scopes (e.g., write:repository)
ssh_tool.py run "curl -sk -X POST -H 'Authorization: Basic <base64>' -H 'Content-Type: application/json' \
  -d '{\"name\": \"eqa-token\", \"scopes\": [\"write:repository\"]}' \
  http://utility.lab.example.com:3000/api/v1/users/student/tokens"
# Returns: {"sha1": "<token>", ...}

# Then use the token:
ssh_tool.py run "curl -sk -H 'Authorization: token <token>' http://utility.lab.example.com:3000/api/v1/..."
```

### Recipe: Podman in Lab Environments

Lab environments use self-signed certificates. Interactive `podman` commands prompt for TLS verification, but automation needs explicit flags.

```bash
# Login (non-interactive — add --tls-verify=false for self-signed certs)
ssh_tool.py run "podman login -u <user> -p <password> <registry-host> --tls-verify=false"

# Pull (same flag needed)
ssh_tool.py run "podman pull --tls-verify=false <registry-host>/<image>:<tag>"

# The EPUB may not include --tls-verify=false because the student runs interactively
# and podman prompts. In automation, always add it for lab registries.
```

### Recipe: Managed Host Commands

**Note:** Replace `<managed-host>` with actual hostnames from the course profile's `real_hosts` field or the EPUB instructions. Never assume hostnames — they vary by course.

```bash
# Privileged operations — use devops (has NOPASSWD sudo)
ssh_tool.py run "ssh devops@<managed-host> 'sudo systemctl restart httpd'"
ssh_tool.py run "ssh devops@<managed-host> 'sudo cat /etc/shadow'"

# Unprivileged operations — student is fine
ssh_tool.py run "ssh student@<managed-host> 'cat /etc/motd'"

# NEVER do this — hangs waiting for password:
# ssh_tool.py run "ssh student@<managed-host> 'sudo systemctl restart httpd'"
```

### Recipe: Parsing Instructions JSON

The `epub_tool.py instructions` output has a specific structure. Here's how to navigate it:

```python
# Structure overview:
# instructions = {
#   "steps": [
#     {
#       "title": "Step title",
#       "sub_steps": [
#         {
#           "text": "Instruction text",
#           "commands": [
#             {"text": "ansible-navigator run ...", "host": "workstation", ...}  # dicts, NOT strings
#           ],
#           "file_actions": [
#             {"path": "playbook.yml", "content": "---\n...", "action": "create"}
#           ],
#           "is_verification": false
#         }
#       ]
#     }
#   ]
# }

# Extracting commands — they are dicts, use .get("text")
for step in instructions["steps"]:
    for sub in step["sub_steps"]:
        for cmd in sub.get("commands", []):
            command_text = cmd.get("text")  # NOT cmd[:50] or str(cmd)

# Extracting file content for write-file
for step in instructions["steps"]:
    for sub in step["sub_steps"]:
        for fa in sub.get("file_actions", []):
            path = fa["path"]
            content = fa["content"]

# Finding verification steps (for GEs)
verification_steps = [
    sub for step in instructions["steps"]
    for sub in step["sub_steps"]
    if sub.get("is_verification")
]

# Handling "...output omitted..." in file_actions content
# The EPUB often truncates long files. If a file_action contains
# "...output omitted..." or similar, the content is INCOMPLETE.
# Read the actual file from the repo/workstation to get full content,
# then apply only the change the EPUB describes.
for step in instructions["steps"]:
    for sub in step["sub_steps"]:
        for fa in sub.get("file_actions", []):
            if "output omitted" in fa.get("content", ""):
                # Don't use this content as-is — read the real file first,
                # then apply the specific edit the EPUB describes
                pass
```

### Recipe: Grade Validation (Labs)

A single `lab start` covers both the without-solution and with-solution grade checks — no restart needed between them.

```bash
# 1. Start fresh
ssh_tool.py lab start <exercise>

# 2. Grade WITHOUT solution (expect most checks to FAIL)
ssh_tool.py lab grade <exercise>
# Analyze per-check: checks for student-created artifacts should FAIL
# Checks for lab-start-provisioned resources may legitimately PASS
# If ALL checks PASS → P1 FALSE POSITIVE bug

# 3. Apply solution files (see Recipe: Applying Solution Files)

# 4. Grade WITH solution (expect all PASS)
ssh_tool.py lab grade <exercise>
# If any check FAILS here → P1 FALSE NEGATIVE bug

# 5. Clean up
ssh_tool.py lab finish <exercise>
```

### Recipe: Verification (GEs)

```bash
# 1. After completing student simulation, find verification steps
# Look for sub_steps with is_verification: true in the instructions JSON

# 2. Run verification commands — common patterns (use actual hostnames from EPUB):
ssh_tool.py run "ssh devops@<managed-host> 'cat /etc/motd'"
ssh_tool.py run "ssh devops@<managed-host> 'sudo systemctl status httpd'"
ssh_tool.py run "curl -s http://<managed-host>.<domain>/"

# 3. Compare output with what the EPUB describes as expected
# If verification fails after correct steps → P1 bug
```

### Recipe: ansible-vault Non-Interactive

Interactive vault prompts hang in automation. Rewrite to non-interactive form:

```bash
# Write the vault password to a temp file (use the password from the EPUB instructions)
ssh_tool.py write-file /tmp/vault-pass --content "$(echo -n '<vault-password>' | base64 -w0)"

# Encrypt a file
ssh_tool.py run "ansible-vault encrypt --vault-password-file /tmp/vault-pass playbook.yml"

# Encrypt with vault-id
ssh_tool.py run "ansible-vault encrypt --vault-id myvault@/tmp/vault-pass secrets.yml"

# Run playbook with vault
ssh_tool.py run "ansible-navigator run site.yml -m stdout --vault-password-file /tmp/vault-pass"
# or: --extra-vars @vault.yml --vault-password-file /tmp/vault-pass

# ansible-vault create → create empty file + encrypt
ssh_tool.py write-file /home/student/<exercise>/secrets.yml --content "$(echo -n '---\nmy_secret: value' | base64 -w0)"
ssh_tool.py run "ansible-vault encrypt --vault-password-file /tmp/vault-pass /home/student/<exercise>/secrets.yml"
```

## Test Categories

Execute these for each exercise. Collect ALL bugs before reporting (error summary pattern — don't fail-fast). All applicable TCs run automatically — the skill determines applicability based on exercise type, available artifacts, and mode.

#### TC-EXEC: Command Pre-flight Validation

**Applies to:** All exercises. **Phase:** 0 (static analysis).

Before running commands on live systems, validate them:

1. Get instructions: `epub_tool.py instructions <epub> <exercise_id>`
2. Check each command for:
   - **Syntax errors** — missing quotes, unmatched braces, invalid YAML references
   - **Dangerous operations** — `rm -rf /`, unqualified `dd`, `mkfs` on wrong device
   - **Missing dependencies** — commands referencing files that don't exist yet and aren't created by prior steps
   - **Consistency** — filenames in commands match filenames in prose/file_actions
3. Report issues as P2 (syntax) or P3 (style) bugs WITHOUT executing them

#### TC-INSTRUCT: Instruction Quality

**Applies to:** All exercises. **Phase:** 0 (static analysis).

Analyze the quality of EPUB instructions:

1. **Completeness**: Every file the student needs to create should have clear content specified. Vague instructions like "add the appropriate content" without showing what: **P2 bug**
2. **Accuracy**: Commands in instructions should match the expected tool versions. e.g., `ansible-playbook` in a course that uses `ansible-navigator`: **P2 bug**
3. **Clarity**: Steps should be unambiguous. If a step could be interpreted multiple ways: **P3 bug**
4. **Ordering**: Steps should be in a logical order. If step N references something created in step N+2: **P2 bug**
5. **Consistency**: File names, variable names, and host names should be consistent throughout the exercise: **P3 bug**
6. **`...output omitted...` in file content**: EPUBs often truncate long file listings or playbook output with `...output omitted...`. This is normal rendering — evaluate whether the student has enough information to complete the step WITHOUT seeing the omitted content. If the omitted section contains content the student needs to type or understand: **P2 bug** (incomplete instructions). If the omitted section is unchanged boilerplate (e.g., a tasks section the student doesn't modify): **not a bug** — note it as a finding.

#### TC-SECURITY: Security Review

**Applies to:** All exercises. **Phase:** 0 (static analysis).

Check for security anti-patterns in exercise content:

1. **Hardcoded credentials**: Passwords in plain text in playbooks (other than vault-encrypted): **P2 bug**
2. **Overly permissive files**: `chmod 777`, world-readable credential files: **P2 bug**
3. **Insecure protocols**: HTTP where HTTPS should be used, telnet instead of SSH: **P3 bug**
4. **Root access**: Unnecessary use of `become: true` or running as root when not needed: **P3 bug**
5. **Missing validation**: Playbooks that don't validate input or use `unsafe`: **P3 bug**

Note: Many exercises intentionally use simple credentials for teaching purposes. Only flag security issues that teach bad habits students might carry to production.

#### TC-CONTRACT: Contract Validation

**Applies to:** Labs with solution files. **Phase:** 0 (static analysis).

Verify alignment between EPUB instructions, solution files, and grading scripts:

1. **EPUB → Solutions**: Every file the EPUB tells students to create should have a corresponding solution file. Missing solutions: **P2 bug**
2. **Solutions → Grading**: Every check in the grading script should be satisfiable by the solution files. If grading checks something the solutions don't provide: **P1 bug**
3. **EPUB → Grading**: Every outcome the EPUB claims should be validated by grading (for Labs). If the EPUB describes an outcome that grading doesn't check: **P2 bug**
4. **Naming consistency**: Exercise IDs, file paths, and variable names should be consistent across EPUB, solutions, and grading. Mismatches: **P3 bug**

#### TC-PREREQ: Prerequisites

**Applies to:** All exercises. **Phase:** 1.

1. Run `ssh_tool.py lab start <exercise>`
2. If start fails due to a blocking lab, ssh_tool auto-recovers (finishes blocking lab or resets status, then retries)
3. If `success` is false in the tool output, report as P0 bug (the tool detects failures using multiple heuristics — not tied to a single keyword)
4. Verify SSH connectivity to all managed hosts the exercise uses (check the course profile's `real_hosts`)

#### TC-GRADE: Grading (Labs Only)

**Applies to:** Labs only. **Phase:** 1 (integrated into student simulation cycle).

**Critical: Lab CLI exit codes do NOT indicate pass/fail of individual checks.** The exit code only tells you whether the grading script ran without crashing. To determine which checks passed or failed, you must examine the output.

The `ssh_tool.py lab grade` command attempts to parse the output into structured `checks` (each with `result` and `description`). It supports multiple output formats automatically. **If parsing finds no checks** (e.g., the output format changed), the raw `stdout` is always included — read it directly and interpret the results yourself.

**Pre-check** (after lab start, before any work):
```bash
ssh_tool.py lab grade <exercise>
```
- Check the `checks` array in the output for structured results
- If `checks` is empty, read `stdout` directly — the output format may have changed
- Analyze each check individually: most should fail, but some may legitimately pass if `lab start` pre-configures resources that grading also checks (e.g., installing packages, enabling services). This is a grading weakness, not a false positive.
- If ALL checks pass: **P1 FALSE POSITIVE bug** (grading doesn't validate anything)
- If checks pass that correspond to student-created artifacts (inventory files, playbook-applied config): **P1 FALSE POSITIVE bug** for those specific checks
- Document which checks pass pre-simulation and why — this informs whether grading adequately distinguishes student work from lab setup

**Post-check** (after student simulation completes):
```bash
ssh_tool.py lab grade <exercise>
```
- Non-zero exit code with no output = P0 script crash
- All checks SHOULD pass
- If any check fails: **P1 FALSE NEGATIVE bug** (grading rejects correct solution)

**Grade message quality**: Check that error messages are clear and actionable, not raw Python tracebacks or cryptic codes. Unclear messages are P2 bugs.

#### TC-STUDENTSIM: Student Simulation

**Applies to:** All exercises. **Phase:** 1.

**This is the core test.** Execute the exercise as a student would, step by step.

**Understand the exercise before executing anything.** This is the most important step. Before running a single command:

1. **Read the full instructions** with `epub_tool.py instructions` — read through ALL steps, not just the first few. Understand the complete arc: what gets created, what gets configured, what the expected outcome is.

2. **Understand the teaching intent.** Course developers design exercises to teach specific concepts. Sometimes this means:
   - **Intentional errors** — an exercise may deliberately introduce broken configs, wrong hostnames, or failing playbooks so the student learns to diagnose and fix them. These are NOT bugs. The EPUB will describe what's broken and guide the student to fix it.
   - **Progressive disclosure** — earlier steps may produce incomplete or failing results that later steps build on. A failure at step 3 is only a bug if the EPUB doesn't expect it.
   - **Implied knowledge** — chapter 8 assumes completion of chapters 1-7. Credentials, URLs, and conventions introduced in earlier chapters won't be re-explained. Check the course profile's `progressive_exercises` flag and the EPUB's lecture content for context.

3. **Extract all URLs, hostnames, and ports** from the instructions' commands and prose (e.g., `https://aap.lab.example.com`, `utility.lab.example.com:3000`). Use these exact values — never substitute hostnames or ports from prior exercises or session memory. The EPUB is the single source of truth.

4. **Identify the exercise pattern**: Is this a build-from-scratch exercise? A troubleshooting exercise with intentional failures? A review lab that combines skills from the whole chapter? This determines how to interpret failures during execution.

Then execute step by step:

1. For each step, translate the instruction into tool calls:
   - Commands in `<pre>` blocks → `ssh_tool.py run` or `devcontainer-run`
   - File creation instructions (prose like "Create a file X containing Y") → `ssh_tool.py write-file` (see **Recipe: Writing Files**)
   - File content from EPUB `file_actions` → `ssh_tool.py write-file`
   - Config file edits (prose like "Add this line to ansible.cfg") → read the file, modify it, write it back
   - Interactive commands (vault prompts, passwords) → rewrite to non-interactive form (see **Recipe: ansible-vault Non-Interactive**)
   - Verification steps → execute and interpret output
2. Track which steps pass/fail and why
3. Track execution time per step for performance metrics

**ansible-navigator: always add `-m stdout`** to prevent the interactive TUI from hanging.

**Dev container exercises:** If the course profile shows `uses_dev_containers`, follow the **Recipe: Dev Container Lifecycle** above. Key points:
1. After `lab start`, use `ssh_tool.py devcontainer-start /home/student/<exercise>` (absolute path)
2. Pre-pull the EE image inside the container (see recipe)
3. Run exercise commands via `ssh_tool.py devcontainer-run`
4. `lab` commands still run on workstation (not in container)
5. Let `lab finish` handle container cleanup (do NOT run `devcontainer-stop` before `lab finish`)

**GUI steps have programmatic equivalents:**

| GUI Step | Programmatic Equivalent |
|----------|------------------------|
| "Open folder in VS Code" | No-op (project dir already exists) |
| "Reopen in Container" | `ssh_tool.py devcontainer-start /home/student/<exercise>` |
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
| "Create credential" (AAP UI) | `curl -sk -u <user>:<pass> -X POST -H 'Content-Type: application/json' '<aap-url>/api/controller/v2/credentials/' -d '{"name":"...","credential_type":<id>,"organization":1,"inputs":{...}}'` |
| "Associate credential with JT" (AAP UI) | `curl -sk -u <user>:<pass> -X POST '<aap-url>/api/controller/v2/job_templates/<jt-id>/credentials/' -d '{"id":<cred-id>}'` |
| "Launch template" (AAP UI) | `curl -sk -u <user>:<pass> -X POST '<aap-url>/api/controller/v2/job_templates/<jt-id>/launch/'` — then poll job status until completed |
| "podman login" (interactive) | `ssh_tool.py run "podman login -u <user> -p <pass> <registry> --tls-verify=false"` |
| "podman pull" | `ssh_tool.py run "podman pull --tls-verify=false <registry>/<image>:<tag>"` |
| OCP web console: Add disk to VM | `oc` create PVC + `virtctl addvolume` + restart VM |
| OCP web console: Create project | `oc new-project <name>` |
| OCP web console: Check resource status | `oc get <resource> -n <project>` |

**ansible-vault commands:** See **Recipe: ansible-vault Non-Interactive**.

**Network device commands:** For courses with Cisco, Juniper, or Arista devices, use 2x timeout multipliers. Network device SSH sessions are slower and may need `pexpect` for interactive prompts.

**Interpreting failures — context is everything.** Not all command failures are bugs. Before classifying any failure, ask: "Does the EPUB expect this to fail?"
- **Intentional failures** — course developers deliberately introduce errors for teaching (wrong hostnames, broken configs, misconfigured services). The EPUB describes what's wrong and guides the student to fix it. These are the exercise working as designed, not bugs. Check `has_intentional_errors` and `exercises_with_deliberate_bugs` in the course profile, but also read the prose — not every intentional failure is flagged in the profile.
- **Progressive steps** — a command may fail at step 3 because the fix isn't applied until step 5. Read ahead before reporting.
- Verification steps may legitimately return non-zero
- EE image pull with "no space left on device" is an environment issue
- `ansible-navigator` returning non-zero with `PLAY RECAP` means the playbook ran but had Ansible errors — read the output to determine if it's an exercise bug or expected behavior

**Troubleshooting exercises:** These exercises have deliberately broken configurations. The student's task is to identify and fix problems. Strategy:
1. Read all instructions first to understand what's broken and what the fix should be
2. Run the initial commands — they WILL fail (this is intentional, not a bug)
3. Apply the fixes described in the EPUB instructions
4. Re-run the commands — they should now succeed
5. Only report a bug if the exercise fails AFTER applying the documented fixes

**ansible-navigator output noise:** `ansible-navigator` may emit base64-encoded UUID strings (e.g., `ZZZZZ...==`) interleaved with playbook output. These are metadata artifacts from the execution environment, not errors. Ignore them when parsing output — look for `PLAY RECAP` and task results to determine success/failure.

#### TC-VERIFY: Verification (GEs)

**Applies to:** GEs only. **Phase:** 1.

For Guided Exercises, after completing the student simulation (see **Recipe: Verification (GEs)**):

1. Re-run any steps marked `is_verification: true` in the instructions
2. Check that verification commands produce the expected output (compare with what the EPUB describes)
3. If a verification step fails after successfully completing all prior steps, it's a **P1 bug** — the instructions don't produce the outcome they claim
4. Common verification patterns: `curl`, `ssh host 'command'`, `ansible-navigator inventory --list`, `systemctl status`

#### TC-WEB: Web Application and Web Console Testing

**Applies to:** Exercises that deploy web apps or use web consoles. **Phase:** 1.

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
   # Login URL, credentials, and target URL come from the EPUB and course profile.
   # These are EXAMPLES — do not use these values directly.
   web_tool.py login "<console-url>" \
     --username <admin-user> --password <admin-password> \
     --then "<console-url>/k8s/ns/<ns>/kubevirt.io~v1~VirtualMachine" \
     --screenshot "/tmp/console.png"
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
- Or use `curl -sk -u <admin-user>:<admin-password>` via `ssh_tool.py run` for direct REST API calls (credentials from the EPUB instructions)
- **Always use the Controller URL from the EPUB instructions** — do not assume a hostname or port. Different exercises may use different URLs (e.g., `aap.lab.example.com` vs `controller.lab.example.com`, with or without non-standard ports). In AAP 2.5, `aap.lab.example.com` is typically the unified gateway that proxies to the controller backend.
- **Resource IDs in the EPUB are examples** — EPUB commands often contain hardcoded IDs like `job_templates/11/launch/`. These are example values from the author's environment. The actual IDs are dynamically assigned at `lab start` time and will differ. Always discover IDs by querying the API by name first (e.g., `GET /job_templates/?name=Refresh%20Fact%20Cache`), then use the returned ID in subsequent calls. The EPUB typically instructs the student to find the ID first, then use it — follow that flow.
- **AAP exercises are inherently slow** — `lab start` provisions many Controller resources (job templates, inventories, projects, credentials, teams, users, notifications) via the API. Expect 180-300s for start and 60-100s for finish. These are not bugs — they're the cost of Controller provisioning.
- **Transient AAP failures are common** — HTTP 503 during `lab start` (controller still initializing), MODULE FAILURE creating users (API gateway not ready), and HTTP 500 on role assignments after repeated start/finish cycles. Retry once before classifying as a bug. These are transient platform issues, not exercise bugs.

#### TC-CLEAN: Cleanup

**Applies to:** All exercises. **Phase:** 1.

1. Run `ssh_tool.py lab finish <exercise>`
2. If `success` is false: check the reason in the output before classifying.
   - **Resource not found (404)** on deletion — in progressive courses, finish scripts may try to clean up resources from other exercises in the same chapter (e.g., deleting a Gitea repo created in an earlier exercise). If the resource was never created in this exercise, a 404 on deletion is expected, not a P1 bug. Verify the re-start still works.
   - **Resource in use** (e.g., "being used by running jobs") — the finish script tried to delete a resource while a background job is still running. This IS a P1 bug — the finish script should cancel running jobs first.
   - **Actual failures** (playbook errors, connection issues) — **P1 cleanup bug**
3. Verify cleanup completeness: run `ssh_tool.py lab start <exercise>` again
4. If start fails after finish: **P1 incomplete cleanup**
5. Check that cleanup removes ALL artifacts:
   - Users, groups, files, directories created during the exercise
   - Services started/enabled
   - Configuration changes
   - Firewall rules
   - Containers, images
6. Run `ssh_tool.py lab finish <exercise>` to clean up after verification

#### TC-SOL: Solution Files

**Applies to:** Exercises with solution files. **Phase:** 2.

Tested SEPARATELY from student simulation — fresh start, apply solutions, verify. See **Recipe: Applying Solution Files** and **Recipe: Grade Validation (Labs)**.

1. Run `ssh_tool.py lab start <exercise>` (fresh start, clean state)
2. Copy each solution file to its correct location on workstation
3. For `.sol` extension files: copy without the `.sol` suffix
4. Run any playbooks the solutions provide (check EPUB instructions for the `ansible-navigator run` commands)
5. Verify the exercise works: for Labs, run `lab grade`; for GEs, run verification commands
6. If solution files don't produce the expected state: **P1 bug**
7. Run `ssh_tool.py lab finish <exercise>` to clean up

#### TC-SOLVE: Solve Scripts

**Applies to:** Exercises where `lab solve` is available. **Phase:** 2.

Some exercises have a `lab solve <exercise>` command that applies solutions automatically.

1. Run `ssh_tool.py lab start <exercise>` (fresh start)
2. Run `ssh_tool.py lab solve <exercise>` (if the framework supports it)
3. For Labs: run `lab grade` — should pass
4. For GEs: run verification commands — should pass
5. If solve doesn't produce a gradeable/verifiable state: **P1 bug**
6. Run `ssh_tool.py lab finish <exercise>` to clean up

#### TC-IDEM: Idempotency

**Applies to:** All exercises (skip if Phase 1 failed). **Phase:** 3.

Run the full cycle (start → simulate → grade → finish) at least twice. Compare results.

**Shortcut:** If TC-SOL ran successfully in Phase 2, it already constitutes a second full cycle (fresh start → apply solutions → grade → finish). Compare TC-SOL results against Phase 1 results — if both passed, idempotency is validated without a third cycle. Only run a dedicated TC-IDEM cycle when TC-SOL was not executed or when investigating a suspected cleanup issue.

1. **Cycle 1**: Normal execution (Phase 1)
2. **Cycle 2**: TC-SOL (if run) or repeat Phase 1
3. If cycle 2 fails where cycle 1 passed: **P1 state pollution bug**
4. Common idempotency issues:
   - Incomplete cleanup (not removing all artifacts)
   - Asymmetric operations (setup on host A, cleanup on host B)
   - Conditional artifacts (created based on conditions, cleanup unconditional)
   - Forgotten dependencies (groups, files, services not cleaned)

#### TC-E2E: Exercise Independence

**Applies to:** `--e2e` mode only.

Validate that exercises don't depend on state from previous exercises.

1. Run exercise B WITHOUT running exercise A first
2. If exercise B fails because it assumes state from exercise A: **P1 independence bug**
3. Exception: progressive exercises (check course profile for `progressive_exercises: true`) are allowed to depend on prior exercises, but must declare their dependencies

## Bug Severity

| Severity | Description | Examples | Action |
|----------|-------------|----------|--------|
| **P0** | Exercise unusable | `lab start` script logic error, missing playbooks, wrong targets | STOP testing, report immediately |
| **P1** | Validation broken | Grading false positive/negative, cleanup incomplete, solution files don't work, verification fails after correct steps | MUST FIX before release |
| **P2** | Quality issue | Instruction step fails, unclear error messages, missing files, security anti-patterns | SHOULD FIX |
| **P3** | Polish | Typos in output, minor style issues, naming inconsistencies | Optional fix |
| **LAB** | Lab infrastructure issue | Slow lab start/finish, transient API failures, service not ready after provisioning, cleanup tries to delete non-existent resources, platform instability after repeated cycles | Not an exercise bug — report to lab/platform team |
| **ENV** | Environment issue | Library version mismatch, wrong workstation image, cluster not ready, disk full | Not an exercise bug — report to operations/provisioning team |

### Exercise Bugs vs Lab Issues vs Environment Issues

These three categories are distinct and reported to different teams:

- **Exercise bugs (P0-P3)**: Problems in the EPUB instructions, solution files, or grading scripts. The exercise content is wrong. Report to the **course developer**.
- **Lab issues (LAB)**: Problems in the lab scripts (`start.yml`, `finish.yml`, `grade.py`) or lab infrastructure behavior that aren't content bugs but degrade the student experience. Examples:
  - `lab start` takes 300s (student waits 5 minutes before they can begin)
  - `lab finish` fails with 404 trying to delete resources from other exercises
  - `lab finish` fails because it doesn't cancel running jobs before deleting templates
  - `lab start` returns 503 on first attempt, succeeds on retry (service not ready)
  - `lab grade` launches jobs that interfere with `lab finish`
  - Grading checks pass trivially (5/13 checks pass before student does anything)
  - Platform becomes unstable after repeated start/finish cycles
  Report to the **lab script developer** or **platform team**.
- **Environment issues (ENV)**: Problems with the test environment itself — wrong workstation image, packages not matching the EPUB version, cluster not provisioned correctly, disk full. These block testing but aren't actionable by course or lab developers. Report to **operations/provisioning**.

**Severity Decision Tree:**
1. Can the student complete the exercise? NO → **P0**
2. Can the student verify their work? NO → **P1**
3. Can the student practice repeatedly (idempotency)? NO → **P1**
4. Is the student experience good? NO → **P2**
5. Any minor issues? YES → **P3**
6. Is the lab script misbehaving (slow, fragile, over-aggressive cleanup)? YES → **LAB**
7. Is the test environment itself broken? YES → **ENV**

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

Only include TC sections that apply to this exercise type. Omit sections for TCs that don't apply (e.g., TC-VERIFY for Labs, TC-GRADE for GEs).

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

### Phase 0: Static Analysis

### TC-EXEC
- Commands validated: N
- Issues found: [list]

### TC-INSTRUCT
- Instruction quality issues: [list]

### TC-SECURITY
- Security findings: [list]

### TC-CONTRACT (Lab only)
- EPUB ↔ Solutions alignment: PASS/FAIL
- Solutions ↔ Grading alignment: PASS/FAIL

### Phase 1: Student Simulation

### TC-PREREQ
- lab start: PASS/FAIL (Xs)

### TC-GRADE pre-check (Lab only)
- Without solution: <expected FAIL, got ...>

### TC-STUDENTSIM
- Steps executed: N/M
- Commands: passed/failed/skipped
- Files written: N
- Duration: Xs
- [Details of any failures with diagnostics]

### TC-VERIFY (GE only)
- Verification steps: passed/failed

### TC-GRADE post-check (Lab only)
- With solution: <expected PASS, got ...>
- Message quality: Good | Needs improvement

### TC-WEB
- Web verification: PASS/FAIL

### TC-CLEAN
- lab finish: PASS/FAIL (Xs)
- Re-start verification: PASS/FAIL

### Phase 2: Solution Validation

### TC-SOL
- Solution files applied: N/M
- Playbooks executed: [list]
- Result: PASS/FAIL

### TC-SOLVE
- lab solve: PASS/FAIL
- Grade/verify after solve: PASS/FAIL

### Phase 3: Idempotency

### TC-IDEM
- Cycle 1: PASS/FAIL
- Cycle 2: PASS/FAIL

## Bugs Found
| ID | Severity | Category | Description | Fix Recommendation | Component |
|----|----------|----------|-------------|-------------------|-----------|

## Lab Issues
| ID | Category | Description | Impact | Recommendation |
|----|----------|-------------|--------|----------------|

## Findings (non-bugs)
<Observations worth documenting but not actionable bugs — e.g., EPUB uses example IDs that differ from live environment, progressive exercise assumptions>

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

| Exercise | Type | Result | Bugs | Lab Issues | Duration |
|----------|------|--------|------|------------|----------|
| exercise-1 | GE | PASS | 0 | 1 | 45s |
| exercise-2 | GE | PASS | 1 P3 | 0 | 52s |
| exercise-3 | Lab | FAIL | 1 P1 | 2 | 68s |

## Aggregate Metrics

- Total bugs: N (P0: N, P1: N, P2: N, P3: N)
- Total lab issues: N
- Defect density: X.X bugs/exercise
- Critical ratio: X%
- Total test duration: Xs
- Release readiness: Ready | Conditional | Not ready

## All Bugs

| ID | Exercise | Severity | Description | Component |
|----|----------|----------|-------------|-----------|

## Lab Issues

| ID | Exercise | Category | Description | Impact |
|----|----------|----------|-------------|--------|

## Recommendations

<Prioritized list of fixes needed before release, organized by:
1. Exercise bugs (P0 first, then P1, P2, P3)
2. Lab issues (report to lab/platform team)
3. Environment issues (report to operations)>
```

## Utility Reference

See `.skilldata/docs/tools-reference.md` for full tool documentation.

Key commands:
- `ssh_tool.py connect` — connect to workstation (auto-detects from ~/.ssh/config)
- `ssh_tool.py run <cmd>` — execute command on workstation
- `ssh_tool.py lab <action> <exercise>` — lab start/finish/grade/force/solve
- `ssh_tool.py vm-exec <vm> -n <ns> -c <cmd>` — run command inside a VM
- `ssh_tool.py vm-disks <vm> -n <ns>` — list VM disk attachments as JSON
- `ssh_tool.py wait-for --mode {tcp,http,command,file} --target <target>` — poll until condition met
- `ssh_tool.py diff <remote_path> --expected <base64>` — compare remote file against expected content
- `ssh_tool.py tunnel` — generate sshuttle command for network tunnel
- `web_tool.py login <url> --username <u> --password <p> --then <url>` — web console login
- `diagnose_tool.py analyze <text>` — diagnose error output, suggest fixes
- `report_tool.py exercise --data <json>` — generate exercise report
- `report_tool.py chapter --data <json>` — generate chapter summary with quality score
- `report_tool.py score --data <json>` — calculate quality score (0-100)

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

### OpenShift / Kubernetes Courses

See `.skilldata/docs/ocp-recipes.md` for full OCP reference including VM disk operations, storage classes, web console testing with Playwright, dev container exercises, and ansible-navigator usage.

## Environment Issues vs Exercise Bugs

Not every failure is an exercise bug. Distinguish carefully:

**Environment issues** (report as ENV, not P0-P3):
- Python library version mismatches in the grading package (e.g., `ResourceList.__init__() got an unexpected keyword argument`)
- Workstation provisioned for a different course (wrong `RHT_COURSE`)
- OCP cluster not ready, operators degraded, or nodes not available
- Disk full, network unreachable, DNS resolution failures
- Package version on PyPI doesn't match the EPUB being tested

**Exercise bugs** (report as P0-P3):
- `lab start` script has wrong host targets, missing playbooks, or logic errors
- Grading checks wrong resources, false positives/negatives
- EPUB instructions don't match what the lab scripts set up
- Solution files don't produce the expected state
- Cleanup incomplete (artifacts left behind)

**How to tell the difference:**
1. If the same exercise works on a freshly provisioned classroom workstation but fails on your test workstation → environment issue
2. If `lab start` fails but `oc`/`virtctl` commands work fine for the same resources → grading script issue, not cluster issue
3. If ALL exercises fail at the same step (e.g., CatalogSource check) → likely environment, not exercise-specific
4. If ONE exercise fails at a unique step → likely an exercise bug

When blocked by an environment issue, report it as ENV in the summary and note that the exercises could not be validated. Do NOT classify environment issues as P0 exercise bugs.

## Decision Points

- **Lab start fails due to blocking lab**: ssh_tool detects this using multiple heuristics (not tied to a specific error message format) and auto-recovers by finishing the blocking lab or resetting lab status. If auto-recovery fails, run `ssh_tool.py lab finish <exercise>` manually
- **Command times out**: Retry once with 2x timeout. If still fails, record as P2 and continue
- **SSH drops mid-test**: ssh_tool auto-reconnects on stale sockets. If that fails, run `ssh_tool.py connect` again
- **Exercise not found in EPUB**: Check for fuzzy matches (the exercise ID in instructions may differ from what was requested)
- **Grade passes without solution**: This is a P1 bug, not a false alarm. Grading SHOULD fail when the student hasn't done the work
- **All steps pass but grade fails**: Check if solution files need to be applied differently, or if grading checks something the instructions don't cover
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
- **Gitea webhook via API vs UI**: The Gitea web UI defaults `branch_filter` to `*`, but the API defaults it to empty string `""`. If grading checks for `branch_filter: *`, set it explicitly when creating webhooks via API: `"branch_filter": "*"`. This is a known API/UI behavior difference, not an exercise bug.
- **Gitea API authentication**: If the Gitea password contains `@` (e.g., `Student@123`), `curl -u user:pass` fails because `@` breaks URL parsing. Use base64-encoded Basic auth instead: `curl -H 'Authorization: Basic <base64(user:pass)>'`. Alternatively, create a Gitea API token first (requires scope, e.g., `write:repository`) and use `curl -H 'Authorization: token <token>'`. The Gitea API base path is `/api/v1/`.
- **AAP team membership verification**: In AAP 2.5, verifying team member/admin role assignments via the REST API is not straightforward — `access_list`, `role_team_assignments`, and `role_user_assignments` endpoints may return empty results. Verify by checking the **job output** (`/api/controller/v2/jobs/<id>/stdout/?format=txt`) instead, which clearly shows role assignments. Alternatively, list users directly and check their team associations.
- **EPUB file content with `...output omitted...`**: When a `file_action` from the parsed EPUB contains `...output omitted...`, the content is truncated. Read the actual file from the workstation/repo first, then apply only the specific change the EPUB describes. The omitted content is typically unchanged boilerplate that the student doesn't need to modify.

## Lab CLI Reference

See `.skilldata/docs/lab-cli.md` for full DynoLabs 5 reference including package management, lab operations, testing features, key files, and environment variables.

Key commands: `lab start/finish/grade/solve <exercise>`, `lab force <sku>` (bypass manifest), `lab version`, `lab list`, `lab status --reset`.

References: [Lab CLI (Rust)](https://github.com/RedHatTraining/classroom-api), [rht-labs-core](https://github.com/RedHatTraining/rht-labs-core)

## Cleanup

Always disconnect when done:
```bash
python3 ~/git-repos/eqa/.skilldata/scripts/ssh_tool.py disconnect
```
