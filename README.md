# eqa: Exercise QA for Red Hat Training

A Claude Code skill that automates quality assurance testing for Red Hat Training course exercises.

## What It Does

- Tests exercises on live lab systems by simulating student workflows
- Validates solution files, grading scripts, and cleanup
- Detects bugs and classifies by severity (P0-P3)
- Handles dev containers, multi-repo courses, interactive commands
- Generates detailed QA reports

## Usage

This is a Claude Code skill. Invoke it with:

```bash
# Test a single exercise
/eqa AU0024L scale-files

# Test a chapter (multi-repo course)
/eqa AU294 --chapter 6

# Test all exercises in a lesson
/eqa AU0024L
```

## Requirements

- Claude Code CLI
- Python 3.8+ with `beautifulsoup4`, `lxml`, `pyyaml`
- SSH access to Red Hat Training workstation (`~/.ssh/config` with `workstation` host)
- `pexpect` for interactive commands

## Architecture

Claude orchestrates the testing workflow, calling Python utilities for mechanical tasks:

```
eqa/
├── SKILL.md                         # Skill manifest + instructions
├── .skilldata/
│   ├── scripts/
│   │   ├── ssh_tool.py              # SSH ControlMaster + command execution
│   │   ├── epub_tool.py             # EPUB extraction + instruction parsing
│   │   ├── course_tool.py           # Course detection + input resolution
│   │   └── profile_tool.py          # Course profile from EPUB content
│   └── docs/
│       └── dynolabs-grading.md      # DynoLabs grading behavior reference
├── results/                         # QA reports written here
├── reference/                       # Historical skill versions
└── docs/                            # Additional documentation
```

**Python utilities** handle SSH connections, EPUB parsing, course detection, and profile building. All output JSON to stdout.

**Claude** handles orchestration: test sequencing, interpreting results, retry/skip decisions, grading analysis, and report generation.

## Test Categories

| Category | What It Tests |
|----------|---------------|
| TC-PREREQ | Lab start works, environment ready |
| TC-STUDENTSIM | EPUB instructions execute correctly |
| TC-SOL | Solution files work |
| TC-GRADE | Grading validates correctly (Labs) |
| TC-CLEAN | Cleanup is complete |
| TC-IDEM | Idempotency across cycles |

## Bug Severity

| Level | Description |
|-------|-------------|
| P0 | Exercise unusable (lab start crashes, SSH broken) |
| P1 | Validation broken (grading false positive/negative) |
| P2 | Quality issue (instruction steps fail) |
| P3 | Polish (typos, style) |

## License

Internal Red Hat Training tool.
