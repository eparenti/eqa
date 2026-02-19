# Lab CLI Reference (DynoLabs 5)

The `lab` command is a Rust binary at `/usr/local/bin/lab`. It wraps Python grading packages managed via `uv`.

## Package Management

| Command | Description |
|---------|-------------|
| `lab install <sku>` | Install course package (respects manifest constraints) |
| `lab force <sku>` | Install package bypassing all constraints (for dev/QA) |
| `lab force <sku>=<version>` | Force-install exact version |
| `lab activate <sku>` | Switch active course without reinstalling |
| `lab list` | List installed courses |
| `lab version` | Show active course library and version |
| `lab release` | Show lab CLI version |
| `lab clean` | Remove course history and grading config |
| `lab clean --labs` | Remove UV cache + course history + grading config |
| `lab clean --all` | Remove everything except manifest |

## Lab Operations

| Command | Description |
|---------|-------------|
| `lab start <exercise>` | Start exercise (creates resources, copies files) |
| `lab finish <exercise>` | Clean up exercise (removes resources) |
| `lab grade <exercise>` | Grade exercise (Labs only) |
| `lab solve <exercise>` | Auto-solve exercise (if supported) |
| `lab status` | Show active lab state |
| `lab status <exercise> --reset` | Reset stuck lab state |
| `lab start <sku>::<exercise>` | Run exercise from specific course (namespace syntax) |

## Testing (Hidden Features)

| Command | Description |
|---------|-------------|
| `lab autotest` | Run all lab scripts in random order |
| `lab autotest --ignore-errors` | Continue testing after failures |
| `lab coursetest <scripts.yml>` | Sequential course workflow testing |

## Key Files

| Path | Description |
|------|-------------|
| `~/.grading/lab_manifest.json` | Maps exercise names to course SKUs and versions |
| `~/.grading/lab_state.json` | Tracks active lab state |
| `~/.grading/config.yaml` | Grading configuration |
| `/etc/rht` | Workstation course info (`RHT_COURSE`, `RHT_VMTREE`, `VERSION_LOCK`) |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `PYPI_URL` | Custom PyPI URL (highest priority) |
| `PKG_ENV` | Environment: `prod`, `stage`, `factory` |
| `UV_PYTHON_VERSION` | Override Python version for uv |

## References

- [Lab CLI (Rust)](https://github.com/RedHatTraining/classroom-api) — DynoLabs 5 Rust CLI source, manifest management, autotest
- [rht-labs-core](https://github.com/RedHatTraining/rht-labs-core) — DynoLabs grading framework (Python), lab script development guides
