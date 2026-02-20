# Utility Reference

## ssh_tool.py

| Subcommand | Description | Key Options |
|------------|-------------|-------------|
| `connect` | Start ControlMaster (auto-detects workstation from ~/.ssh/config) | `--host <hostname>` |
| `status` | Check connection, framework, disk space | |
| `run <cmd>` | Execute command (auto-reconnects) | `--timeout 120` |
| `lab <action> <exercise>` | Framework-aware lab command (start/finish/grade/install/solve/force) | `--timeout 600` |
| `vm-exec <vm>` | Run command inside a KubeVirt VM (tries SSH, falls back to console) | `-n <ns>`, `-c <cmd>`, `--user`, `--password` |
| `vm-disks <vm>` | List VM disk attachments via virsh (parsed JSON) | `-n <ns>` |
| `interactive <cmd>` | Interactive command via pexpect | `--prompts '[[pat,resp],...]'` |
| `write-file <path>` | Write file (base64) | `--content <b64>` |
| `read-file <path>` | Read remote file | |
| `devcontainer-start <dir>` | Parse devcontainer.json, start (checks disk) | |
| `devcontainer-run <cmd>` | Execute in container | `--workdir`, `--user` |
| `devcontainer-stop` | Stop container | |
| `autotest` | DynoLabs 5 autotest (Rust CLI) | `--ignore-errors`, `--timeout 1800` |
| `coursetest` | DynoLabs 5 coursetest (Rust CLI) | `--dry-run`, `--timeout 3600` |
| `tunnel` | Generate sshuttle command for classroom network | (no options) |
| `disconnect` | Tear down connection | |

## epub_tool.py

| Subcommand | Description | Key Options |
|------------|-------------|-------------|
| `parse <epub>` | Extract course structure | `--lesson-path <path>` |
| `instructions <epub> <id>` | Get exercise steps | |
| `summary <epub>` | Testability overview per exercise | `--lesson-path <path>` |
| `build <course_path>` | Build EPUB via sk | `--force` |

## course_tool.py

| Subcommand | Description | Key Options |
|------------|-------------|-------------|
| `resolve <input>` | Resolve to epub+lesson path | `--chapter N` |
| `detect <repo_path>` | Auto-detect course metadata | |

## profile_tool.py

| Subcommand | Description |
|------------|-------------|
| `build <extract_dir>` | Build course profile from EPUB |

## web_tool.py

| Subcommand | Description | Key Options |
|------------|-------------|-------------|
| `login <url>` | Login to web app (fill + submit in one session) | `--username`, `--password`, `--then <url>`, `--screenshot` |
| `navigate <url>` | Open URL in headless browser | `--screenshot <path>` |
| `click <selector>` | Click element | `--screenshot <path>` |
| `fill <selector> <value>` | Fill form field | |
| `text <selector>` | Get element text | |
| `screenshot <path>` | Capture current page | |
| `page-text` | Get full page text | |
| `wait <selector>` | Wait for element | `--timeout 10000` |
| `evaluate <js>` | Run JavaScript | |
| `api-get <url>` | HTTP GET request | `--headers <json>` |
| `api-post <url>` | HTTP POST request | `--data <json>`, `--headers <json>` |
| `close` | Clear browser state | |

Requires: `pip install playwright && playwright install chromium`
The `api-get` and `api-post` subcommands do NOT require Playwright (use urllib directly).

## diagnose_tool.py

| Subcommand | Description | Key Options |
|------------|-------------|-------------|
| `analyze <text>` | Diagnose error output, identify root cause, suggest fixes | `--file <path>` |

Returns JSON with `findings[]` — each finding has `id`, `title`, `severity`, `category`, `fix`, `matched_text`.

Recognizes: SSH errors, Ansible errors (missing collections, undefined vars, YAML syntax), OCP errors (NotFound, Forbidden, timeouts), DynoLabs errors (manifest, CatalogSource, lab state), environment issues (disk full, EE pull failures).

## report_tool.py

| Subcommand | Description | Key Options |
|------------|-------------|-------------|
| `exercise --data <json>` | Generate markdown exercise report | |
| `chapter --data <json>` | Generate chapter summary with quality score | `--course`, `--chapter` |
| `score --data <json>` | Calculate quality score (0-100) | |

Quality score components: Coverage (30pts), Defects (40pts), Reliability (30pts).

Performance budget thresholds: lab start >60s, lab finish >60s, student sim >600s, total >900s.

## AAP Controller CLI

For courses that use AAP Automation Controller, use the `rht-labs-aapcli` tool at `~/git-repos/active/rht-labs-aapcli` to interact with the Controller API programmatically (create job templates, launch jobs, manage inventories, etc.).
