# Exercise QA 2

Professional automated testing for Red Hat Training course exercises.

## Features

✅ **Two-Phase Testing** - Student simulation followed by QA validation
✅ **Automatic EPUB Building** - Detects missing EPUBs and builds them with `sk`
✅ **Multi-Repo Support** - Handles both single-repo and multi-repo courses
✅ **Auto Lab Package Detection** - Detects lesson SKU and installs lab packages automatically
✅ **22 Test Categories** - Comprehensive validation (prerequisites, solutions, grading, cleanup, idempotency, web UI, EE, etc.)
✅ **SSH Automation** - Tests exercises on live lab systems
✅ **Browser Automation** - Playwright-based UI testing for web console exercises
✅ **DynoLabs v5 Support** - Auto-detects and uses `uv run lab` when appropriate
✅ **AAP Controller** - Validates AAP workflows and resources
✅ **Quality Metrics** - Defect density, coverage, performance budgets
✅ **Smart Caching** - Skip already-passed tests (JSON with atomic writes)
✅ **Parallel Execution** - Test multiple exercises concurrently
✅ **Colorized Output** - ANSI colors with TTY detection and `--no-color` flag
✅ **AI Diagnostics** - Pattern-based error analysis with fix recommendations
✅ **Network Device Support** - Auto-detects Cisco/Juniper/Arista with adjusted timeouts
✅ **E2E Mode** - Focused test set for live lab validation (`--e2e`)
✅ **Quick/Full/CI Modes** - Fast iteration, comprehensive validation, or CI/CD integration

## Quick Start

```bash
# Test single exercise (Quick mode - default)
/exercise-qa AU0024L scale-files

# Test entire lesson (Quick mode)
/exercise-qa ~/git-repos/active/AU294-lessons/AU0024L

# Full mode - comprehensive pre-production validation (22 tests)
/exercise-qa AU0024L scale-files --full

# Force EPUB rebuild
/exercise-qa AU0024L --rebuild-epub

# Skip student simulation (QA checks only)
/exercise-qa AU0024L --skip-student-sim

# Student simulation only (skip QA checks)
/exercise-qa AU0024L --student-only

# E2E mode (focused live lab testing)
/exercise-qa AU0024L --e2e

# CI mode with JUnit output
/exercise-qa AU0024L --ci -o results/

# Disable colors
/exercise-qa AU0024L --no-color

# Run specific test categories only
/exercise-qa AU0024L --tests TC-LINT,TC-VARS,TC-DEPS
```

## How It Works

1. **Detect Input** - Lesson directory, EPUB file, or lesson code
2. **Build EPUB** - Uses existing EPUB or builds with `sk build epub3` (use `--rebuild-epub` to force)
3. **Parse Course** - Extracts exercises, solutions, grading scripts
4. **Install Lab Package** - Auto-detects lesson SKU and installs with `lab force <lesson>` if needed
5. **Run Student Simulation** - lab start → exercise steps → lab grade → lab finish
6. **Run QA Checks** - Executes test categories on live lab (Quick: 4 tests, Full: 22 tests)
7. **Generate Report** - Comprehensive markdown + JSON results

## Architecture

Clean, modular structure:

```
src/
├── core/          # Data models
├── epub/          # EPUB building & parsing
├── tests/         # Test categories (one per file)
├── clients/       # SSH, AAP, Ansible
├── reporting/     # Report generation
└── utils/         # Helpers
```

## Test Categories

| Category | Description |
|----------|-------------|
| **TC-PREREQ** | Prerequisites (SSH, tools, hosts, devices) |
| **TC-EXEC** | EPUB execution validation |
| **TC-WORKFLOW** | Workflow playbook testing |
| **TC-SOL** | Solution file testing |
| **TC-SOLVE** | Solve playbook testing |
| **TC-VERIFY** | Verification testing (GE) |
| **TC-GRADE** | Grading script validation (Labs) |
| **TC-CLEAN** | Cleanup validation |
| **TC-IDEM** | Idempotency testing |
| **TC-AAP** | AAP Controller workflows |
| **TC-E2E** | End-to-end independence |
| **TC-SECURITY** | Security best practices |
| **TC-CONTRACT** | Component alignment |
| **TC-INSTRUCT** | Instruction quality |
| **TC-LINT** | Linting and static analysis |
| **TC-DEPS** | Dependency validation |
| **TC-PERF** | Performance budgets |
| **TC-VARS** | Variable validation |
| **TC-ROLLBACK** | Rollback testing |
| **TC-NETWORK** | Network device testing |
| **TC-WEB** | Web UI testing (Playwright) |
| **TC-EE** | Execution environment validation |
| **TC-DYNOLABS** | DynoLabs v5 support |

## Documentation

- [User Guide](docs/USER-GUIDE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Test Categories](docs/TEST-CATEGORIES.md)
- [Development](docs/DEVELOPMENT.md)

## DynoLabs Support

The skill auto-detects the lab framework and uses the appropriate command:

| Framework | Detection | Command |
|-----------|-----------|---------|
| DynoLabs 5 (Rust CLI) | ELF binary with `autotest` | `lab start` |
| DynoLabs 5 (Python) | `uv` + `~/grading/pyproject.toml` | `cd ~/grading && uv run lab start` |
| Factory Wrapper | `lab` shell script | `lab start` |
| DynoLabs (legacy) | `lab` Python binary | `lab start` |

### DynoLabs 5 Rust CLI Features

When the Rust CLI from [classroom-api](https://github.com/RedHatTraining/classroom-api) is detected, additional testing features are available:

```bash
# Run randomized comprehensive lab validation
ssh.run_autotest(ignore_errors=True)

# Run sequential course workflow testing
ssh.run_coursetest("scripts.yml", dry_run=True)
```

These leverage the built-in testing capabilities of the Rust CLI:
- `lab autotest` - Randomized order, comprehensive validation
- `lab coursetest` - Sequential workflow, follows scripts.yml

## Browser Automation (TC-WEB)

For exercises with web UI steps (OpenShift console, RHOAI dashboard, AAP Controller):

```bash
# Install Playwright
pip install playwright
playwright install chromium

# Run with web testing enabled
/exercise-qa ~/git-repos/active/DO380 auth-ldap-ge
```

The skill:
- Auto-detects exercises with web UI steps
- Launches headless browser
- Authenticates using lab credentials
- Captures screenshots at each step
- Validates UI elements are accessible

## Requirements

- Python 3.9+
- SSH access to workstation
- Scaffolding tools (`sk`) for EPUB building
- pexpect, pyyaml
- playwright (optional, for TC-WEB)

## License

Proprietary - Red Hat Training Internal Use
