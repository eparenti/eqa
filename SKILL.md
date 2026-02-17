---
name: eqa
version: 5.0.0
description: Automated exercise QA for Red Hat Training courses
authors:
  - Ed Parenti <eparenti@redhat.com>
  - Claude Code
---

# eqa - Exercise QA for Red Hat Training

Automated quality assurance testing for Red Hat Training course exercises. Tests exercises on live lab systems by simulating student workflows, validating solutions, grading, cleanup, and idempotency.

## Quick Start

```bash
# Test a single exercise in a lesson
/eqa AU0024L scale-files

# Test a chapter (multi-repo course)
/eqa AU294 --chapter 6

# Test all exercises in a lesson
/eqa AU0024L

# Test from EPUB path
/eqa /path/to/COURSE.epub exercise-name
```

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

Analyzes EPUB content to detect: technology stack, dev containers, tool locations, teaching patterns, ansible collections, real hosts.

### 5. For Multi-Repo Courses: Install Lesson

```bash
python3 ~/git-repos/eqa/.skilldata/scripts/ssh_tool.py lab install <lesson_code>
```

Required before exercises can be tested in multi-repo courses. Must be run each time you switch to a different lesson — installing a new lesson replaces the previous one.

## Test Categories

Execute these in order for each exercise. Use judgment to decide when to skip, retry, or adapt.

### TC-PREREQ: Prerequisites

1. Run `ssh_tool.py lab start <exercise>`
2. If start fails due to blocking lab, ssh_tool handles it automatically (finishes blocking lab, retries)
3. If start has FAIL in output, report as P0 bug

### TC-STUDENTSIM: Student Simulation

1. Run `epub_tool.py summary <epub> --lesson-path <path>` first to see which exercises have commands vs GUI-only steps
2. Get instructions: `epub_tool.py instructions <epub> <exercise_id>`
3. Execute each step's commands via `ssh_tool.py run <command>`
4. For file actions (type=create), write files via `ssh_tool.py write-file <path> --content <base64>`
5. For interactive commands, use `ssh_tool.py interactive <cmd> --prompts '<json>'`
6. Track which steps pass/fail

**ansible-navigator: always add `-m stdout`**. EPUB instructions often say `ansible-navigator run playbook.yml` without `-m stdout`. Without it, ansible-navigator launches an interactive TUI that hangs in non-interactive execution. Always append `-m stdout` when running ansible-navigator commands via ssh_tool.

**VS Code GUI steps are untestable.** Steps like "Click File > New Text File", "Reopen in Container", or "Click Open Folder" have no extractable commands. When an exercise is primarily GUI-based (summary shows `gui_only_steps > command_steps`), use the solution files instead of trying to simulate the GUI steps. The solution files represent the end state the GUI steps would produce.

**Dev container exercises:** If the course profile shows `uses_dev_containers`, check for `.devcontainer/` in the exercise directory on workstation. Use `ssh_tool.py devcontainer-start <project_dir>` and run commands via `ssh_tool.py devcontainer-run` instead of `ssh_tool.py run`. Before starting, run `ssh_tool.py status` to check available disk space — dev containers need ~2GB free for the container image + EE image.

**Interpreting failures:** Not all command failures are bugs. Consider:
- Verification steps (grep, test) may fail if prior steps had issues
- Commands that check state may legitimately return non-zero
- `ansible-navigator` commands may fail due to EE image issues (environment, not exercise bug)
- Troubleshooting exercises have *intentional* failures
- EE image pull failures with "no space left on device" are environment issues, not exercise bugs

### TC-SOL: Solution Files

If solution files exist (from EPUB parse):
1. Run `ssh_tool.py lab start <exercise>` (fresh start)
2. Copy each solution file to its correct location on workstation
3. For `.sol` extension files: copy without the `.sol` suffix
4. Verify the exercise works with solutions applied

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

### TC-CLEAN: Cleanup

1. Run `ssh_tool.py lab finish <exercise>`
2. If finish has FAIL in output: **P1 cleanup bug**
3. Verify cleanup: run `ssh_tool.py lab start <exercise>` again
4. If start fails after finish: **P1 incomplete cleanup**
5. Run `ssh_tool.py lab finish <exercise>` to clean up

### TC-IDEM: Idempotency (Optional, Labs)

Run the full cycle (start → simulate → grade → finish) twice. Compare results. If cycle 2 fails where cycle 1 passed, the exercise has state pollution.

## Bug Severity

| Severity | Description | Examples |
|----------|-------------|----------|
| **P0** | Exercise unusable | `lab start` crashes, SSH fails, missing lab command |
| **P1** | Validation broken | Grading false positive/negative, cleanup incomplete, solution files don't work |
| **P2** | Quality issue | Instruction step fails, unclear error messages, missing files |
| **P3** | Polish | Typos in output, minor style issues, slow timeouts |

## Report Format

Write reports to `~/git-repos/eqa/results/`. Use filename pattern: `<exercise-id>-<YYYYMMDD-HHMMSS>.md`

### Report Structure

```markdown
# Exercise QA Report: <exercise-id>

**Course:** <course_code> - <course_title>
**Exercise:** <exercise_id> (<type>)
**Date:** <timestamp>
**Result:** PASS | FAIL

## Summary
<1-2 sentence overview>

## Test Results

### TC-PREREQ
- lab start: PASS/FAIL
- Duration: Xs

### TC-STUDENTSIM
- Steps executed: N/M
- Commands: passed/failed/skipped
- [Details of any failures]

### TC-GRADE (if Lab)
- Without solution: <expected FAIL, got ...>
- With solution: <expected PASS, got ...>

### TC-CLEAN
- lab finish: PASS/FAIL
- Re-start verification: PASS/FAIL

## Bugs Found
| ID | Severity | Category | Description | Fix Recommendation |
|----|----------|----------|-------------|-------------------|
| BUG-001 | P1 | TC-GRADE | Grading passes without solution | Add validation checks |

## Course Profile
<Key characteristics from profile_tool>
```

## Utility Reference

### ssh_tool.py

| Subcommand | Description | Key Options |
|------------|-------------|-------------|
| `connect` | Start ControlMaster | `--host workstation` |
| `status` | Check connection, framework, disk space | |
| `run <cmd>` | Execute command (auto-reconnects) | `--timeout 120` |
| `lab <action> <exercise>` | Framework-aware lab command | `--timeout 300` |
| `interactive <cmd>` | Interactive command via pexpect | `--prompts '[[pat,resp],...]'` |
| `write-file <path>` | Write file (base64) | `--content <b64>` |
| `read-file <path>` | Read remote file | |
| `devcontainer-start <dir>` | Parse devcontainer.json, start (checks disk) | |
| `devcontainer-run <cmd>` | Execute in container | `--workdir`, `--user` |
| `devcontainer-stop` | Stop container | |
| `autotest` | DynoLabs 5 autotest (Rust CLI) | `--ignore-errors`, `--timeout 1800` |
| `coursetest` | DynoLabs 5 coursetest (Rust CLI) | `--dry-run`, `--timeout 3600` |
| `disconnect` | Tear down connection | |

### epub_tool.py

| Subcommand | Description | Key Options |
|------------|-------------|-------------|
| `parse <epub>` | Extract course structure | `--lesson-path <path>` |
| `instructions <epub> <id>` | Get exercise steps | |
| `summary <epub>` | Testability overview per exercise | `--lesson-path <path>` |
| `build <course_path>` | Build EPUB via sk | `--force` |

### course_tool.py

| Subcommand | Description | Key Options |
|------------|-------------|-------------|
| `resolve <input>` | Resolve to epub+lesson path | `--chapter N` |
| `detect <repo_path>` | Auto-detect course metadata | |

### profile_tool.py

| Subcommand | Description |
|------------|-------------|
| `build <extract_dir>` | Build course profile from EPUB |

## Course Patterns

### Multi-Repo Courses (e.g., AU294)

Each chapter maps to a separate lesson repository. The course outline.yml has `repository` fields pointing to lesson repos.

1. Resolve with `--chapter N` to find the right lesson
2. Run `lab install <lesson_code>` before testing exercises
3. Lesson code comes from the repository URL in outline.yml

### Dev Container Exercises

Some courses run tools inside podman containers instead of directly on workstation.

1. Course profile will show `uses_dev_containers: true`
2. After `lab start`, check for `.devcontainer/` in exercise dir
3. Use `devcontainer-start` to spin up the container
4. Run exercise commands via `devcontainer-run`
5. `lab` commands still run on workstation (not in container)
6. Clean up with `devcontainer-stop` before `lab finish`

### ansible-navigator Commands

When running `ansible-navigator` via ssh_tool (non-interactively), **always append `-m stdout`** to prevent the interactive TUI from launching. The EPUB may or may not include this flag — add it regardless.

```bash
# EPUB says:          ansible-navigator run site.yml
# You should run:     ansible-navigator run site.yml -m stdout

# EPUB says:          ansible-navigator inventory -i inventory --list
# You should run:     ansible-navigator inventory -i inventory --list -m stdout
```

Do NOT translate `ansible-navigator` to `ansible-playbook`. The course profile tells you which tool the course expects.

## Decision Points

- **Lab start fails with "another lab is running"**: ssh_tool handles this automatically by finishing the blocking lab
- **Command times out**: Retry once with 2x timeout. If still fails, record as P2 and continue
- **SSH drops mid-test**: ssh_tool auto-reconnects on stale sockets. If that fails, run `ssh_tool.py connect` again
- **Exercise not found in EPUB**: Check for fuzzy matches (the exercise ID in instructions may differ from what was requested)
- **Grade passes without solution**: This is a P1 bug, not a false alarm. DynoLabs grading SHOULD fail when student hasn't done the work
- **All steps pass but grade fails**: Check if solution files need to be applied differently, or if grading checks something the instructions don't cover
- **EE image pull fails "no space left on device"**: Environment issue. Run `podman system prune -af` and `rm -rf ~/.cache/uv` on workstation. If still insufficient, note as environment blocker
- **Exercise is all GUI steps**: Use solution files to set up the expected state, then test the verification/command steps that follow
- **ansible-navigator hangs**: Missing `-m stdout` flag. Always append it for non-interactive execution
- **Switching lessons in multi-repo course**: Must run `lab install <new-lesson>` before testing exercises in a different lesson

## Cleanup

Always disconnect when done:
```bash
python3 ~/git-repos/eqa/.skilldata/scripts/ssh_tool.py disconnect
```
