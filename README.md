# eqa: Exercise QA for Red Hat Training

A Claude Code skill (v2.0.0) that automates quality assurance testing for Red Hat Training course exercises.

## What It Does

- Tests exercises on live lab systems by simulating student workflows
- Validates solution files, grading scripts, and cleanup
- Diffs EPUB instructions against solution files (static and live)
- Detects bugs and classifies by severity (P0-P3) and type (TECH, PEDAGOGY, SEQUENCE, COMPLEXITY, GUIDANCE)
- Distinguishes intentional errors (troubleshooting exercises) from real bugs
- Handles dev containers, multi-repo courses, network devices, AAP Controller
- Generates detailed QA reports with quality scores

## Usage

This is a Claude Code skill. Invoke it with:

```bash
# Test a single exercise
/eqa DO457 manage-facts

# Test a full chapter
/eqa DO457 --chapter 5

# Test all exercises in a lesson (multi-repo)
/eqa AU294 --chapter 6

# End-to-end testing (exercise independence)
/eqa AU294 --chapter 4 --e2e
```

## Requirements

- Claude Code CLI
- Python 3.8+ with `beautifulsoup4`, `lxml`, `pyyaml`, `pexpect`
- SSH access to Red Hat Training workstation (`~/.ssh/config` with `workstation` host)
- Course EPUB file in `~/git-repos/active/<COURSE>/`

## Architecture

Claude orchestrates the testing workflow, calling Python utilities for mechanical tasks:

```
eqa/
├── SKILL.md                         # Skill manifest (v2.0.0)
├── .skilldata/
│   ├── scripts/
│   │   ├── ssh_tool.py              # SSH, lab commands, file transfer, VM access
│   │   ├── epub_tool.py             # EPUB extraction + instruction parsing
│   │   ├── course_tool.py           # Course detection + input resolution
│   │   ├── profile_tool.py          # Course profile from EPUB content
│   │   ├── web_tool.py              # Playwright browser automation
│   │   ├── diagnose_tool.py         # Error diagnosis
│   │   ├── report_tool.py           # Report generation + quality scoring
│   │   └── eqa_common.py            # Shared utilities
│   ├── config/
│   │   └── errors.yaml              # Error pattern database
│   └── docs/
│       ├── tools-reference.md       # Full tool documentation
│       ├── lab-cli.md               # DynoLabs 4/5 reference
│       ├── dynolabs-grading.md      # Grading behavior reference
│       └── ocp-recipes.md           # OpenShift/VM recipes
├── results/                         # QA reports written here
└── reference/                       # Historical skill versions
```

**Python utilities** handle SSH connections, EPUB parsing, course detection, profile building, web testing, and report generation. All output JSON to stdout.

**Claude** handles orchestration: test sequencing, interpreting results, understanding teaching intent, retry/skip decisions, grading analysis, and report generation.

## Testing Phases

| Phase | What | When |
|-------|------|------|
| **0: Static** | TC-EXEC, TC-INSTRUCT, TC-SECURITY, TC-STATICDIFF | Always |
| **1: Simulate** | TC-PREREQ, TC-GRADE, TC-STUDENTSIM, TC-LIVEDIFF, TC-WEB, TC-CLEAN | Always |
| **2: Solutions** | TC-SOL, TC-SOLVE | If solutions exist |
| **3: Idempotency** | TC-IDEM | If Phase 1 passed |

## Test Categories

| Category | Phase | What It Tests |
|----------|-------|---------------|
| TC-EXEC | 0 | Command syntax, safety, dependencies, anti-patterns |
| TC-INSTRUCT | 0 | Instruction completeness, accuracy, clarity |
| TC-SECURITY | 0 | Hardcoded credentials, insecure patterns, permissions |
| TC-STATICDIFF | 0 | EPUB file content vs solution files, complexity alignment, grading coverage |
| TC-PREREQ | 1 | Lab start works, environment ready |
| TC-GRADE | 1 | Grading validates correctly (Labs only) |
| TC-STUDENTSIM | 1 | EPUB instructions execute correctly (incl. verification steps) |
| TC-LIVEDIFF | 1 | Student-created files vs solution files (live comparison) |
| TC-WEB | 1 | Web app/console accessibility |
| TC-CLEAN | 1 | Cleanup complete, re-start works, rollback resilience |
| TC-SOL | 2 | Solution files produce correct state |
| TC-SOLVE | 2 | `lab solve` produces correct state |
| TC-IDEM | 3 | Consistent results across cycles |

## Bug Classification

### Severity

| Level | Description | Action |
|-------|-------------|--------|
| P0 | Exercise unusable (lab start fails, missing files) | Stop, report immediately |
| P1 | Validation broken (grading false pos/neg, cleanup incomplete) | Must fix before release |
| P2 | Quality issue (instruction step fails, unclear errors) | Should fix |
| P3 | Polish (typos, style, naming) | Optional |
| LAB | Lab infrastructure (slow start, transient failures) | Report to lab team |
| ENV | Environment (version mismatch, cluster not ready) | Report to operations |

### Type

| Type | Description |
|------|-------------|
| TECH | Technical failure (file not found, syntax error, service fails) |
| PEDAGOGY | Solution contradicts what the course teaches |
| SEQUENCE | Exercise uses concepts not yet taught |
| COMPLEXITY | Exercise scope exceeds stated objective |
| GUIDANCE | Intentional error lacks sufficient hints for students |

## Supported Course Types

- **Network Automation** (DO457) — Cisco IOS, Juniper JunOS, Arista EOS via SSH/NETCONF
- **OpenShift** (DO316, DO280, etc.) — VMs, storage, web console
- **Ansible Automation** (RH294, DO374, etc.) — Playbooks, roles, collections
- **AAP Controller** (DO457, DO374) — Workflow templates, REST API
- **RHEL** (RH124, RH134, etc.) — System administration
- **Dev containers** — VS Code remote containers with EE images

## License

Internal Red Hat Training tool.
