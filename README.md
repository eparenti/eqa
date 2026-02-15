# exercise-qa-4: Automated Red Hat Training Exercise Testing

Fully automated quality assurance testing for Red Hat Training exercises.

## Features

- **Student Simulation** - Executes EPUB instructions on live lab systems
- **Solution Testing** - Validates solution files work correctly
- **Enhanced Grading** - Tests grading without/with solution
- **Idempotency Testing** - Multi-cycle testing for reliability
- **Bug Detection** - Auto-classifies bugs by severity (P0-P3)
- **Dev Container Support** - Works with ansible-dev-tools containers
- **Multiple Report Formats** - Markdown, JSON, JUnit
- **Chapter-Level Testing** - Test by chapter number
- **Course-Wide Testing** - Test all exercises at once

## Installation

### Quick Install

```bash
cd /path/to/exercise-qa-4
./install.sh
```

This will:
1. Create a symlink in `~/.local/bin/eqa`
2. Make the `eqa` command available system-wide

### Manual Install

```bash
# Add to your PATH
export PATH="/path/to/exercise-qa-4:$PATH"

# Or create symlink manually
ln -s /path/to/exercise-qa-4/eqa ~/.local/bin/eqa
```

### Verify Installation

```bash
eqa --help
```

## Requirements

- Python 3.8+
- SSH access to Red Hat Training workstation
- SSH config with `workstation` host defined
- Required Python packages: `beautifulsoup4`, `lxml`, `pyyaml`

## Usage

### Basic Testing

```bash
# Test a single exercise
eqa AU0024L scale-files

# Test all exercises in a lesson
eqa AU0024L

# Test specific chapter
eqa AU294 --chapter 4
```

### Advanced Testing

```bash
# Idempotency testing (run 2 cycles)
eqa AU0022L control-review --cycles 2

# Solution file testing
eqa AU0024L scale-review --test-solutions

# Multiple report formats
eqa AU0024L scale-files --format all

# Custom output directory
eqa AU0024L scale-files --output /tmp/qa-reports
```

### Command-Line Options

```
positional arguments:
  input                 EPUB path, lesson directory, or lesson code
  exercise             Exercise ID (optional, tests all if omitted)

options:
  --format {markdown,json,junit,all}
                        Report format (default: markdown)
  -o, --output PATH    Output directory (default: ./eqa-results)
  --quiet              Suppress console output
  --no-color           Disable ANSI colors
  --cycles N           Number of cycles for idempotency testing (default: 1)
  --test-solutions     Test solution files instead of student simulation
  --chapter N          Test only chapter N (requires course code input)
  --lesson-code CODE   Lesson code for multi-repo courses (e.g., au0020l)
  --rebuild-epub       Force EPUB rebuild
  --timeout-lab SEC    Lab command timeout (default: 300)
  --timeout-command SEC Command timeout (default: 120)
  --timeout-build SEC  EPUB build timeout (default: 600)
```

## How It Works

### Student Simulation Flow

1. **Extract** - Parse EPUB to get exercise instructions
2. **Connect** - SSH to workstation
3. **Start** - Run `lab start <exercise>`
4. **Simulate** - Execute EPUB instructions step-by-step
5. **Grade** - Run `lab grade <exercise>` (for Labs)
6. **Finish** - Run `lab finish <exercise>`
7. **Verify** - Confirm cleanup worked (run `lab start` again)

### Enhanced Grading (Labs Only)

1. **Test WITHOUT solution** - Grading should fail
2. **Execute instructions** - Simulate student work
3. **Test WITH solution** - Grading should pass

Detects bugs when:
- Grading passes without solution (incorrect validation)
- Grading fails with solution (broken grading script)

### Idempotency Testing

Run the complete cycle multiple times:

```
Cycle 1: lab start → simulate → grade → finish
Cycle 2: lab start → simulate → grade → finish
...
Cycle N: lab start → simulate → grade → finish
```

Validates:
- Scripts are truly idempotent
- Cleanup is complete
- No state pollution between runs

## Reports

Reports are written to `./eqa-results/` (or custom path via `--output`):

### Single Exercise
- `<exercise>-<timestamp>.md` - Detailed Markdown report
- `<exercise>-<timestamp>.json` - JSON format
- `<exercise>-<timestamp>.xml` - JUnit XML

### Idempotency Testing
- `<exercise>-<timestamp>.md` - Cycle 1 report
- `<exercise>-cycle2-<timestamp>.md` - Cycle 2 report
- `<exercise>-cycle3-<timestamp>.md` - Cycle 3 report

### Multi-Exercise
- `<COURSE>-summary.md` - Course-level summary

## Bug Severity Levels

| Level | Description | Examples |
|-------|-------------|----------|
| **P0** | Blocker - Exercise unusable | SSH fails, lab command missing |
| **P1** | Critical - Validation broken | Grading fails, cleanup incomplete |
| **P2** | High - Quality issues | Instruction steps fail |
| **P3** | Low - Polish needed | Typos, style issues |

## Examples

### Test a GE (Guided Exercise)
```bash
eqa AU0022L control-flow
```

Output:
```
✓ Lab start successful
✓ Instructions executed (6/6 passed)
✓ Lab finish successful
✓ Cleanup verified
```

### Test a Lab with Enhanced Grading
```bash
eqa AU0022L control-review
```

Output:
```
✓ Lab start successful
✗ Grading WITHOUT solution: PASSED (expected FAIL) - BUG FOUND!
✓ Instructions executed (4/4 passed)
✓ Grading WITH solution: PASSED
✓ Lab finish successful

Bugs Found:
[P1] Grading passed without solution (should fail)
```

### Idempotency Testing
```bash
eqa AU0022L control-review --cycles 3
```

Output:
```
Cycle 1/3: ✓ PASSED
Cycle 2/3: ✓ PASSED
Cycle 3/3: ✓ PASSED

✓ IDEMPOTENT: All 3 cycles passed
Average per cycle: 215.2s
```

## Architecture

```
exercise-qa-4/
├── eqa                 # CLI entry point
├── install.sh          # Installation script
├── src/
│   ├── main.py        # Argument parsing, orchestration
│   ├── runner.py      # Student simulation engine
│   ├── epub.py        # EPUB parsing, instruction extraction
│   ├── ssh.py         # SSH connection, command execution
│   ├── models.py      # Data models
│   └── report.py      # Report generation
└── README.md          # This file
```

## Troubleshooting

### "Cannot connect to workstation"
- Check SSH config: `~/.ssh/config` should have a `workstation` host
- Test manually: `ssh workstation echo OK`

### "Exercise not found in EPUB"
- Verify EPUB exists and contains the exercise
- Try rebuilding: `--rebuild-epub`

### "Lab command not found"
- Install rht-labs-core on workstation
- Check: `ssh workstation which lab`

### Path not in PATH
Add to `~/.bashrc` or `~/.zshrc`:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Development

### Running Without Install
```bash
cd exercise-qa-4
python3 -m src.main AU0024L scale-files
```

### Running Tests
```bash
# Test on a known-good exercise
python3 -m src.main AU0022L control-flow --no-color

# Test with verbose output
python3 -u -m src.main AU0022L control-flow
```

## License

Internal Red Hat Training tool.

## Version

4.0 - Simplified architecture with enhanced features
