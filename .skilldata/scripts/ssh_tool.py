#!/usr/bin/env python3
"""SSH ControlMaster management and remote command execution.

All output is JSON to stdout, diagnostics to stderr.
State persists across invocations via ~/.cache/eqa/ssh-state.json.

Usage:
    python3 ssh_tool.py connect [--host workstation]
    python3 ssh_tool.py run <command> [--timeout 120]
    python3 ssh_tool.py lab <action> <exercise> [--timeout 300]
    python3 ssh_tool.py write-file <remote_path> --content <base64>
    python3 ssh_tool.py read-file <remote_path>
    python3 ssh_tool.py interactive <command> --prompts '<json_array>'
    python3 ssh_tool.py devcontainer-start <project_dir>
    python3 ssh_tool.py devcontainer-run <command> [--workdir DIR] [--user USER]
    python3 ssh_tool.py devcontainer-stop
    python3 ssh_tool.py disconnect
"""

import argparse
import functools
import json
import os
import re
import shlex
import subprocess
import sys
import time
import uuid

from eqa_common import _output, _err, get_cache_dir, get_state_path, load_state, save_state, json_safe, debug_log


STATE_FILE = get_state_path("ssh")


def _strip_ansi(text: str, strip_spinners: bool = True) -> str:
    """Strip ANSI escape codes and control characters from output.

    Args:
        text: Raw text with potential ANSI codes.
        strip_spinners: If True, also remove DynoLabs spinner progress lines
            and collapse empty lines. Set to False for VM command output
            where all content should be preserved.
    """
    text = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)  # ECMA-48 Fe + CSI sequences
    text = re.sub(r'\x1b\][^\x07]*\x07', '', text)       # OSC sequences
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)  # control chars
    text = text.replace('\r\n', '\n').replace('\r', '\n')  # normalize line endings

    if not strip_spinners:
        return text

    # Collapse DynoLabs progress/spinner lines. These repeat the same
    # message with different leading indicator characters (e.g., - \ / |)
    # before a final result line (SUCCESS/FAIL/WARNING + same message).
    #
    # Instead of matching specific spinner chars (brittle — breaks if
    # DynoLabs changes), we deduplicate by message content: strip the
    # leading indicator prefix and any result keyword to get the core
    # message, then keep only the LAST line in each consecutive run
    # of identical messages. This naturally keeps the SUCCESS/FAIL line
    # and drops all the spinner repetitions before it.
    _RESULT_PREFIX = re.compile(r'^(?:SUCCESS|FAIL|WARNING)\s+', re.IGNORECASE)

    lines = text.split('\n')
    filtered = []
    prev_core = None
    prev_line = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Extract core message: strip leading non-alnum (spinner char),
        # then strip result prefix (SUCCESS/FAIL/WARNING)
        msg = re.sub(r'^[^a-zA-Z0-9]*', '', stripped)
        core = _RESULT_PREFIX.sub('', msg)
        if core == prev_core and prev_core:
            # Same core message — replace with this line (keep last)
            prev_line = line
        else:
            if prev_line is not None:
                filtered.append(prev_line)
            prev_core = core
            prev_line = line
    if prev_line is not None:
        filtered.append(prev_line)
    return '\n'.join(filtered)


def _ssh_opts(state: dict) -> list:
    """Common SSH options."""
    return [
        '-o', f'ControlPath={state["control_path"]}',
        '-o', 'ConnectTimeout=10',
        '-o', 'ServerAliveInterval=30',
        '-o', 'ServerAliveCountMax=3',
    ]


def _ssh_exec(state, cmd, timeout=120, input_data=None):
    """Run command over SSH. Returns (success, stdout, stderr, rc, duration)."""
    debug_log(f"exec cmd={cmd!r} timeout={timeout}", caller="ssh")
    start_time = time.time()
    try:
        result = subprocess.run(
            ['ssh'] + _ssh_opts(state) + [state["host"], cmd],
            capture_output=True, text=True, timeout=timeout,
            input=input_data,
        )
        duration = time.time() - start_time
        stdout_clean = _strip_ansi(result.stdout)
        stderr_clean = _strip_ansi(result.stderr)
        debug_log(
            f"exec rc={result.returncode} duration={duration:.2f}s"
            f" stdout={stdout_clean[:500]!r}"
            f" stderr={stderr_clean[:200]!r}",
            caller="ssh",
        )
        return (
            result.returncode == 0,
            stdout_clean,
            stderr_clean,
            result.returncode,
            round(duration, 2),
        )
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        debug_log(f"exec TIMEOUT after {timeout}s cmd={cmd!r}", caller="ssh",
                  level=40)  # WARNING
        return (False, "", f"Command timed out after {timeout}s", -1, round(duration, 2))
    except Exception as e:
        duration = time.time() - start_time
        debug_log(f"exec ERROR {e} cmd={cmd!r}", caller="ssh", level=40)
        return (False, "", f"Execution error: {e}", -1, round(duration, 2))


def requires_connection(func):
    """Decorator: load state and verify connection before running command."""
    @functools.wraps(func)
    def wrapper(args):
        state = load_state(STATE_FILE)
        if not state:
            _output({"success": False, "error": "Not connected. Run 'connect' first."})
            return
        return func(args, state)
    return wrapper


def _resolve_ssh_config_files(config_path: str) -> list:
    """Resolve SSH config files, following Include directives.

    Returns a list of file paths to parse, in order. Handles glob
    patterns in Include directives (e.g., Include config.d/*).
    """
    import glob as globmod

    config_path = os.path.expanduser(config_path)
    if not os.path.exists(config_path):
        return []

    files = [config_path]
    try:
        with open(config_path) as f:
            for line in f:
                stripped = line.strip()
                if stripped.lower().startswith('include '):
                    pattern = stripped.split(None, 1)[1].strip()
                    # Relative paths are relative to ~/.ssh/
                    if not os.path.isabs(pattern):
                        pattern = os.path.join(os.path.dirname(config_path), pattern)
                    pattern = os.path.expanduser(pattern)
                    for match in sorted(globmod.glob(pattern)):
                        if os.path.isfile(match) and match not in files:
                            files.append(match)
    except Exception:
        pass

    return files


def _detect_workstation() -> str:
    """Auto-detect workstation hostname from ~/.ssh/config.

    Looks for hosts named 'workstation', or containing 'workstation' in
    their hostname. Follows Include directives to find hosts defined in
    included config files. Falls back to 'workstation' if not found.
    """
    config_path = os.path.expanduser("~/.ssh/config")
    config_files = _resolve_ssh_config_files(config_path)
    if not config_files:
        return "workstation"

    try:
        current_host = None
        current_hostname = None
        candidates = []

        for path in config_files:
            try:
                with open(path) as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if line.lower().startswith('host '):
                            if current_host and 'workstation' in current_host.lower():
                                candidates.append((current_host, current_hostname or current_host))
                            current_host = line.split(None, 1)[1].split()[0]
                            current_hostname = None
                        elif line.lower().startswith('hostname '):
                            current_hostname = line.split(None, 1)[1]
                    # Handle last entry in this file
                    if current_host and 'workstation' in current_host.lower():
                        candidates.append((current_host, current_hostname or current_host))
                        current_host = None
                        current_hostname = None
            except (IOError, OSError):
                continue

        if candidates:
            # Prefer exact match "workstation" over partial matches
            for alias, hostname in candidates:
                if alias.lower() == 'workstation':
                    return alias
            return candidates[0][0]
    except Exception:
        pass

    return "workstation"


def _check_connection(state: dict) -> bool:
    """Verify ControlMaster socket is still alive."""
    control_path = state.get("control_path", "")
    if not os.path.exists(control_path):
        return False
    try:
        result = subprocess.run(
            ['ssh', '-o', f'ControlPath={control_path}', '-O', 'check', state["host"]],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _get_subnets(state):
    """Detect classroom subnets via ip route on the remote host."""
    try:
        nets = subprocess.run(
            ['ssh'] + _ssh_opts(state) + [state["host"],
             "ip route | grep -v default | awk '{print $1}' | grep -v '^10\\.88\\.'"],
            capture_output=True, text=True, timeout=5,
        )
        if nets.returncode == 0:
            return [s.strip() for s in nets.stdout.strip().split('\n') if s.strip()]
    except Exception:
        pass
    return []


def _detect_framework(state: dict) -> dict:
    """Detect which lab framework is available and validate it works.

    Uses a series of probes to identify the framework.  Each probe is
    independent — if one detection method stops working, others still
    function.  The command prefix is always 'lab' unless the only
    grading mechanism found is a uv-based Python package.

    After detection, validates the CLI actually works by running a simple
    command.  Known issues (e.g., missing setuptools) are auto-fixed.

    Returns a dict with keys:
        framework: str — framework name (dynolabs5, dynolabs4, dynolabs5-python, etc.)
        prefix: str — command prefix to use
        validated: bool — whether the CLI was validated to work
        issues: list[str] — issues found during validation
        fixes_applied: list[str] — auto-fixes that were applied
        lab_cli_version: str|None — version string from `lab --version`
    """
    host = state["host"]
    opts = _ssh_opts(state)

    def ssh_run(command, timeout=10):
        try:
            result = subprocess.run(
                ['ssh'] + opts + [host, command],
                capture_output=True, text=True, timeout=timeout,
            )
            return result.returncode, _strip_ansi(result.stdout), _strip_ansi(result.stderr)
        except Exception:
            return -1, "", ""

    result = {
        "framework": "unknown",
        "prefix": "lab",
        "validated": False,
        "issues": [],
        "fixes_applied": [],
        "lab_cli_version": None,
    }

    # Probe 1: Is there a `lab` command in PATH?
    rc, stdout, _ = ssh_run("which lab 2>/dev/null")
    if rc == 0 and stdout.strip():
        lab_path = stdout.strip()

        # Get version info — this tells us the framework generation
        rc_ver, ver_out, ver_err = ssh_run("lab -v 2>&1")
        ver_combined = ver_out + ver_err
        ver_match = re.search(r'Lab framework version:\s*(\S+)', ver_combined)
        lib_match = re.search(r'Course library version:\s*(\S+)', ver_combined)

        if ver_match:
            fw_version = ver_match.group(1)
            result["lab_cli_version"] = fw_version
            _err(f"Lab framework version: {fw_version}")
            major = int(fw_version.split('.')[0])
        else:
            # Fallback: try `lab --version` (DynoLabs 5 style)
            rc_ver2, ver_out2, _ = ssh_run("lab --version 2>&1")
            if rc_ver2 == 0 and ver_out2.strip():
                fw_version = ver_out2.strip()
                result["lab_cli_version"] = fw_version
                _err(f"Lab CLI version: {fw_version}")
                try:
                    major = int(fw_version.split('.')[0])
                except ValueError:
                    major = None
            else:
                fw_version = None
                major = None

        if lib_match:
            result["course_lib_version"] = lib_match.group(1)
            _err(f"Course library version: {lib_match.group(1)}")

        # Detect framework generation by checking available commands.
        # DynoLabs 5 (Rust CLI) has: list, force, activate, status, solve
        # DynoLabs 4 (Python CLI) has: select, fix, upgrade, system-info
        rc_help, help_out, _ = ssh_run("lab --help 2>&1")
        has_list = 'list' in help_out
        has_force = 'force' in help_out
        has_select = 'select' in help_out
        has_status = 'status' in help_out
        has_fix = bool(re.search(r'\bfix\b', help_out))

        if has_list and has_force:
            framework_name = 'dynolabs5'
        elif has_select and not has_list:
            framework_name = 'dynolabs4'
        elif major and major >= 5:
            framework_name = 'dynolabs5'
        elif major and major < 5:
            framework_name = 'dynolabs4'
        else:
            framework_name = 'dynolabs'

        # Store capability flags so cmd_lab() can map commands correctly
        result["framework"] = framework_name
        result["prefix"] = "lab"
        result["capabilities"] = {
            "has_list": has_list,
            "has_force": has_force,
            "has_select": has_select,
            "has_status": has_status,
            "has_fix": has_fix,
            "solve_cmd": "solve" if not has_fix else "fix",
        }

        # Validate: actually try running the CLI
        result = _validate_and_fix_framework(result, ssh_run)
        return result

    # Probe 2: uv-based Python grading (no `lab` binary in PATH)
    rc_uv, _, _ = ssh_run("which uv 2>/dev/null")
    for grading_dir in ['~/grading', '~/.grading']:
        rc_g, g_out, _ = ssh_run(f"test -f {grading_dir}/pyproject.toml && echo 'exists'")
        if rc_uv == 0 and rc_g == 0 and 'exists' in g_out:
            result["framework"] = "dynolabs5-python"
            result["prefix"] = f"cd {grading_dir} && uv run lab"
            result = _validate_and_fix_framework(result, ssh_run)
            return result

    # Probe 3: nothing found
    result["issues"].append("No lab CLI found on workstation")
    return result


# Known error patterns and their auto-fix generators.
# Each entry: (error_pattern, fix_command_fn, fix_description)
# fix_command_fn receives the combined error output and returns (command, timeout).


def _fix_missing_pkg_resources(error_output: str):
    """Generate fix command for missing pkg_resources.

    pkg_resources was removed from setuptools >= 78.  We find the uv-managed
    venv from the traceback path and install setuptools<78 there.
    """
    # Extract the site-packages path from the traceback
    m = re.search(r'(/home/\S+/site-packages)/labs/', error_output)
    if m:
        sp = m.group(1)
        return (f"pip3 install --quiet 'setuptools<78' --target '{sp}' 2>&1", 60)
    # Fallback: install into all uv venvs that have the grading package
    return (
        "for SP in $(find /home/student/.cache/uv/archive-v0/ "
        "-path '*/site-packages/labs/grading.py' -printf '%h\\n' 2>/dev/null "
        "| sed 's|/labs$||'); do "
        "  pip3 install --quiet 'setuptools<78' --target \"$SP\" 2>&1; "
        "done",
        120,
    )


_KNOWN_FRAMEWORK_FIXES = [
    (r"No module named 'pkg_resources'", _fix_missing_pkg_resources,
     "Installed setuptools<78 (provides pkg_resources)"),
    (r"No module named 'setuptools'", _fix_missing_pkg_resources,
     "Installed setuptools<78"),
]


def _validate_and_fix_framework(result: dict, ssh_run) -> dict:
    """Validate that the lab CLI works by running `lab list`.

    If it fails with a known error, attempt auto-fix and retry.
    Updates the result dict in-place with validation status.
    """
    prefix = result["prefix"]

    # Try `lab --version` first (fast, informational) — only if not already set
    if not result.get("lab_cli_version"):
        rc, stdout, stderr = ssh_run(f"{prefix} --version 2>&1")
        combined = stdout + stderr
        if rc == 0 and stdout.strip():
            result["lab_cli_version"] = stdout.strip()
            _err(f"Lab CLI version: {stdout.strip()}")

    # Validate by running a non-destructive command that exercises the full
    # CLI stack including the Python grading package.
    #
    # Strategy varies by framework:
    # - DynoLabs 5: `lab list` (Rust-only) + Python grading import test
    # - DynoLabs 4: `lab -v` (already got version) + `lab select --help`
    #   (exercises the Python CLI without side effects)
    #
    # In both cases, a successful `lab -v` with parseable output means
    # the CLI binary works.  For DynoLabs 4, the binary IS the Python
    # package (PyInstaller-compiled), so if -v works, the whole stack works.

    framework_name = result["framework"]

    if framework_name == 'dynolabs4':
        # DynoLabs 4: the CLI is a compiled Python binary.
        # If `lab -v` produced a version, the binary is functional.
        if result.get("lab_cli_version"):
            result["validated"] = True
            _err(f"DynoLabs 4 CLI validated (v{result['lab_cli_version']})")
            return result
        # Try one more command
        rc_sel, stdout_sel, _ = ssh_run(f"{prefix} select --help 2>&1", timeout=10)
        if rc_sel == 0 and 'Usage' in stdout_sel:
            result["validated"] = True
            _err("DynoLabs 4 CLI validated via 'select --help'")
            return result
        rc = rc_sel
        combined = stdout_sel
    else:
        # DynoLabs 5: test both the Rust binary and Python grading
        rc_list, stdout_list, stderr_list = ssh_run(f"{prefix} list 2>&1", timeout=15)
        combined_list = stdout_list + stderr_list

        # Test the Python grading import chain (uv-managed venv)
        grading_test_cmd = (
            "GRADING_PY=$(find /home/student/.cache/uv/archive-v0/ "
            "-path '*/site-packages/labs/grading.py' -print -quit 2>/dev/null); "
            "if [ -z \"$GRADING_PY\" ]; then echo 'no_grading_venv'; exit 0; fi; "
            "VENV_DIR=$(echo \"$GRADING_PY\" | sed 's|/lib/.*||'); "
            "\"$VENV_DIR/bin/python3\" -c "
            "'from labs.grading import Default; print(\"grading_ok\")' 2>&1"
        )
        rc_grading, stdout_grading, _ = ssh_run(grading_test_cmd, timeout=15)
        combined_grading = stdout_grading

        if rc_list == 0 and 'Traceback' not in combined_list:
            if 'grading_ok' in combined_grading:
                result["validated"] = True
                return result
            elif 'no_grading_venv' in combined_grading:
                # No uv venvs — might be a fresh install or DL4 misdetected
                result["validated"] = True
                return result
            elif 'Traceback' in combined_grading:
                _err("Lab CLI (Rust) works but Python grading package is broken")
                combined = combined_grading
            else:
                result["validated"] = True
                return result
        else:
            rc = rc_list
            combined = combined_list + combined_grading

    # CLI failed — check for known fixable errors
    _err(f"Lab CLI validation failed. Checking for known issues...")
    debug_log(f"framework validation failed: {combined[:500]}", caller="ssh", level=30)

    for pattern, fix_fn, fix_desc in _KNOWN_FRAMEWORK_FIXES:
        if re.search(pattern, combined):
            _err(f"Detected: {fix_desc}. Attempting auto-fix...")
            fix_cmd, fix_timeout = fix_fn(combined)
            fix_rc, fix_out, fix_err = ssh_run(fix_cmd, timeout=fix_timeout)
            if fix_rc == 0:
                result["fixes_applied"].append(fix_desc)
                _err(f"Fix applied: {fix_desc}")
            else:
                result["issues"].append(f"Auto-fix failed for: {fix_desc}")
                _err(f"Auto-fix failed: {fix_desc} (rc={fix_rc})")
                debug_log(f"fix failed: {fix_out} {fix_err}", caller="ssh", level=30)

    # Retry validation after fixes
    if result["fixes_applied"]:
        rc, stdout, stderr = ssh_run(f"{prefix} list 2>&1", timeout=15)
        combined = stdout + stderr
        if rc == 0 and 'Traceback' not in combined:
            result["validated"] = True
            _err("Lab CLI now working after auto-fix")
            return result

    # Still broken — record the issue
    if not result["validated"]:
        # Extract the specific error for diagnostics
        tb_match = re.search(r'(\w+Error: .+)$', combined, re.MULTILINE)
        error_msg = tb_match.group(1) if tb_match else f"lab list failed (rc={rc})"
        result["issues"].append(error_msg)
        _err(f"Lab CLI broken: {error_msg}")

    return result


@json_safe
def cmd_connect(args):
    """Start ControlMaster, detect framework, persist state."""
    host = args.host or _detect_workstation()
    cache_dir = get_cache_dir()
    control_path = os.path.join(cache_dir, f"ssh-{host}.sock")

    # Clean up stale socket from a dead connection
    old_state = load_state(STATE_FILE)
    if old_state and not _check_connection(old_state):
        old_socket = old_state.get("control_path", "")
        if old_socket and os.path.exists(old_socket):
            os.unlink(old_socket)

    _err(f"Connecting to {host}...")
    debug_log(f"connect host={host} control_path={control_path}", caller="ssh")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            cmd = [
                'ssh',
                '-o', f'ControlPath={control_path}',
                '-o', 'ControlMaster=yes',
                '-o', 'ControlPersist=600',
                '-o', 'ConnectTimeout=15',
                '-o', 'ServerAliveInterval=30',
                '-o', 'ServerAliveCountMax=3',
                '-N', '-f',
                host,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                # Verify connection
                opts = [
                    '-o', f'ControlPath={control_path}',
                    '-o', 'ConnectTimeout=10',
                ]
                verify = subprocess.run(
                    ['ssh'] + opts + [host, 'echo', 'connected'],
                    capture_output=True, text=True, timeout=10,
                )
                if verify.returncode == 0 and 'connected' in verify.stdout:
                    break
        except (subprocess.TimeoutExpired, Exception) as e:
            _err(f"Attempt {attempt + 1} failed: {e}")

        if attempt < max_retries - 1:
            delay = 2.0 * (2 ** attempt)
            _err(f"Retrying in {delay}s...")
            time.sleep(delay)
    else:
        _output({"success": False, "error": f"Connection failed after {max_retries} attempts"})
        return

    # Save initial state
    state = {
        "control_path": control_path,
        "host": host,
        "framework": None,
        "framework_prefix": None,
    }

    # Detect and validate lab framework
    fw = _detect_framework(state)
    state["framework"] = fw["framework"]
    state["framework_prefix"] = fw["prefix"]
    state["framework_validated"] = fw["validated"]
    state["framework_capabilities"] = fw.get("capabilities", {})

    save_state(STATE_FILE, state)
    debug_log(f"connected host={host} framework={fw['framework']} "
              f"prefix={fw['prefix']!r} validated={fw['validated']}",
              caller="ssh")

    _output({
        "success": True,
        "host": host,
        "control_path": control_path,
        "framework": fw["framework"],
        "framework_prefix": fw["prefix"],
        "framework_validated": fw["validated"],
        "framework_issues": fw["issues"],
        "framework_fixes_applied": fw["fixes_applied"],
        "lab_cli_version": fw["lab_cli_version"],
        "capabilities": fw.get("capabilities", {}),
    })


@json_safe
def cmd_status(args):
    """Check connection status, framework info, and disk space."""
    state = load_state(STATE_FILE)
    if not state:
        _output({"success": True, "connected": False, "message": "No active connection"})
        return

    alive = _check_connection(state)

    result = {
        "success": True,
        "connected": alive,
        "host": state.get("host"),
        "framework": state.get("framework"),
        "framework_prefix": state.get("framework_prefix"),
        "control_path": state.get("control_path"),
        "devcontainer": state.get("devcontainer"),
    }

    if alive:
        # Check disk space
        try:
            disk = subprocess.run(
                ['ssh'] + _ssh_opts(state) + [state["host"], "df -h / --output=avail,pcent | tail -1"],
                capture_output=True, text=True, timeout=5,
            )
            if disk.returncode == 0:
                result["disk_free"] = disk.stdout.strip()
        except Exception:
            pass

        subnets = _get_subnets(state)
        if subnets:
            result["subnets"] = subnets

    _output(result)


@json_safe
@requires_connection
def cmd_tunnel(args, state):
    """Generate sshuttle command for classroom network tunnel."""
    if not _check_connection(state):
        _output({"success": False, "error": "Connection lost. Run 'connect' again."})
        return

    subnets = _get_subnets(state)
    if not subnets:
        _output({"success": False, "error": "Could not detect classroom subnets"})
        return

    host = state["host"]
    cmd = f"sudo sshuttle --dns -r {shlex.quote(host)} {' '.join(subnets)} -D"
    _output({
        "success": True,
        "subnets": subnets,
        "command": cmd,
        "instructions": f"Run this in a separate terminal: {cmd}",
    })


@json_safe
def cmd_run(args):
    """Execute command via ControlMaster."""
    state = load_state(STATE_FILE)
    if not state:
        _output({"success": False, "error": "Not connected. Run 'connect' first."})
        return

    # Check for stale socket
    if not _check_connection(state):
        _err("ControlMaster socket is stale, reconnecting...")
        # Attempt reconnect
        host = state["host"]
        cache_dir = get_cache_dir()
        control_path = os.path.join(cache_dir, f"ssh-{host}.sock")
        # Clean up old socket
        old_control_path = state.get("control_path", "")
        if old_control_path and os.path.exists(old_control_path):
            try:
                os.unlink(old_control_path)
            except OSError:
                pass
        try:
            cmd = [
                'ssh',
                '-o', f'ControlPath={control_path}',
                '-o', 'ControlMaster=yes',
                '-o', 'ControlPersist=600',
                '-o', 'ConnectTimeout=15',
                '-o', 'ServerAliveInterval=30',
                '-o', 'ServerAliveCountMax=3',
                '-N', '-f',
                host,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                state["control_path"] = control_path
                save_state(STATE_FILE, state)
                _err("Reconnected successfully")
            else:
                _output({"success": False, "error": "Connection lost and reconnect failed. Run 'connect' again."})
                return
        except Exception as e:
            _output({"success": False, "error": f"Reconnect failed: {e}"})
            return

    command = args.command
    timeout = args.timeout

    ok, stdout, stderr, rc, duration = _ssh_exec(state, command, timeout=timeout)
    _output({
        "success": ok,
        "return_code": rc,
        "stdout": stdout,
        "stderr": stderr,
        "duration": duration,
    })


def _detect_blocking_lab(output: str) -> tuple[bool, str | None]:
    """Try to extract a blocking exercise name from lab output.

    Uses multiple heuristics so that a single format change doesn't
    break auto-recovery.

    Returns (is_blocked, name):
        (False, None)  — no blocking detected
        (True, name)   — blocked by a specific exercise
        (True, None)   — blocked but name could not be extracted
    """
    # Heuristic 1: message says "lab finish <name>"
    m = re.search(r'lab finish\s+(\S+)', output)
    if m:
        return True, m.group(1)
    # Heuristic 2: message says "finish <name> first" or similar
    m = re.search(r'finish\s+["\']?(\S+?)["\']?\s+first', output, re.IGNORECASE)
    if m:
        return True, m.group(1)
    # Heuristic 3: any mention of "already running/active" + an exercise name
    if re.search(r'already\s+(running|active|in progress)', output, re.IGNORECASE):
        # Blocked but can't extract the name.
        # Caller can try `lab status --reset` or ask the user.
        return True, None
    return False, None


def _detect_failure(stdout: str) -> bool:
    """Check whether lab start/finish output indicates a failure.

    Uses multiple heuristics so the tool degrades gracefully if the
    output format changes.
    """
    for pattern in [
        r'\bFAIL\b',          # DynoLabs 5 current format
        r'\bFAILED\b',        # possible variant
        r'\bERROR\b',         # generic error keyword
        r'\u2718',            # ✘ cross mark
        r'\u274C',            # ❌ red X
    ]:
        if re.search(pattern, stdout):
            return True
    return False


def _parse_grade_checks(stdout: str) -> list:
    """Parse grade output into structured check results.

    Tries multiple output formats so that format changes don't silently
    break grading validation.  Always returns a list (possibly empty if
    no known format matched — caller should fall back to raw stdout).
    """
    checks = []

    # Format 1: "PASS  description" / "FAIL  description" (current DynoLabs)
    for line in stdout.split('\n'):
        m = re.match(r'\s*(PASS|FAIL)\s+(.+)', line)
        if m:
            checks.append({"result": m.group(1), "description": m.group(2).strip()})

    if checks:
        return checks

    # Format 2: checkmark/cross symbols — "✓ description" / "✗ description"
    for line in stdout.split('\n'):
        m = re.match(r'\s*([\u2713\u2714\u2705])\s+(.+)', line)
        if m:
            checks.append({"result": "PASS", "description": m.group(2).strip()})
            continue
        m = re.match(r'\s*([\u2717\u2718\u274C])\s+(.+)', line)
        if m:
            checks.append({"result": "FAIL", "description": m.group(2).strip()})

    if checks:
        return checks

    # Format 3: "[OK] description" / "[FAIL] description"
    for line in stdout.split('\n'):
        m = re.match(r'\s*\[(OK|PASS|FAIL|ERROR)\]\s+(.+)', line, re.IGNORECASE)
        if m:
            result = "PASS" if m.group(1).upper() in ("OK", "PASS") else "FAIL"
            checks.append({"result": result, "description": m.group(2).strip()})

    return checks


@json_safe
@requires_connection
def cmd_lab(args, state):
    """Run framework-aware lab command."""
    action = args.action
    exercise = args.exercise
    timeout = args.timeout
    prefix = state.get("framework_prefix", "lab")
    framework = state.get("framework", "unknown")

    caps = state.get("framework_capabilities", {})

    if not state.get("framework_validated", True) and framework != "unknown":
        _err(f"Warning: Lab CLI ({framework}) was not validated during connect. "
             "Commands may fail. Re-run 'connect' to re-validate.")

    # Map actions to actual CLI commands based on framework capabilities.
    # DynoLabs 4 uses 'fix' instead of 'solve', 'select' instead of
    # 'activate', and doesn't have 'force', 'list', or 'status'.
    actual_action = action
    if action == 'solve' and caps.get('has_fix') and not caps.get('has_list'):
        actual_action = 'fix'
        _err(f"Mapped 'solve' → 'fix' (DynoLabs 4 CLI)")
    elif action == 'force' and not caps.get('has_force'):
        # DynoLabs 4 doesn't have 'force' — use 'install' instead
        _err(f"'force' not available on {framework}, using 'install' instead")
        actual_action = 'install'

    # 'force' bypasses framework prefix, uses raw exercise as SKU (DynoLabs 5)
    if action == 'force' and caps.get('has_force'):
        cmd = f"lab force {shlex.quote(exercise)}"
    else:
        lab_name = exercise
        cmd = f"{prefix} {actual_action} {shlex.quote(lab_name)}"
    _err(f"Running: {cmd} (framework: {framework})")
    debug_log(f"lab {action} {exercise} framework={framework} cmd={cmd!r}",
              caller="ssh")

    ok, stdout, stderr, rc, duration = _ssh_exec(state, cmd, timeout=timeout)
    success = ok

    # If lab start fails or warns about a blocking lab, finish it and retry.
    if action == 'start':
        output = stdout + stderr
        is_blocked, blocking_name = _detect_blocking_lab(output)
        if is_blocked:
            if blocking_name:
                _err(f"Finishing blocking lab: {blocking_name}")
                _ssh_exec(state, f"{prefix} finish {shlex.quote(blocking_name)}", timeout=120)
            else:
                # Blocked but can't extract name
                if caps.get('has_status'):
                    _err("Blocked by another lab (name unknown), attempting status reset")
                    _ssh_exec(state, f"{prefix} status --reset", timeout=30)
                else:
                    _err("Blocked by another lab (name unknown). "
                         "DynoLabs 4 has no status reset — trying lab finish for this exercise.")
                    _ssh_exec(state, f"{prefix} finish {shlex.quote(exercise)}", timeout=120)
            _err(f"Retrying: {cmd}")
            ok, stdout, stderr, rc, duration = _ssh_exec(state, cmd, timeout=timeout)
            success = ok

    # Check stdout for failure indicators (start/finish only)
    if success and action in ('start', 'finish'):
        if _detect_failure(stdout):
            success = False

    output_data = {
        "success": success,
        "return_code": rc,
        "stdout": stdout,
        "stderr": stderr,
        "duration": duration,
        "framework": framework,
        "command": cmd,
    }

    # Parse grade check results for structured output.
    # Always includes raw stdout so the agent can interpret if parsing
    # finds nothing (e.g., if the output format changed).
    if action == 'grade':
        checks = _parse_grade_checks(stdout)
        output_data["checks"] = checks
        output_data["all_pass"] = all(c["result"] == "PASS" for c in checks) if checks else None
        output_data["all_fail"] = all(c["result"] == "FAIL" for c in checks) if checks else None
        debug_log(f"grade parsed {len(checks)} checks all_pass={output_data['all_pass']}",
                  caller="ssh")
        if not checks:
            _err("Warning: Could not parse grade output into structured checks. "
                 "The output format may have changed. Raw stdout is included.")
            debug_log(f"grade parse EMPTY — raw stdout: {stdout[:500]!r}",
                      caller="ssh", level=30)

    _output(output_data)


@json_safe
@requires_connection
def cmd_interactive(args, state):
    """Execute interactive command via pexpect.

    Prompts are matched in any order — the command watches for all
    prompt patterns simultaneously and responds to whichever appears.
    This handles dynamic ordering, optional prompts, and unexpected
    system messages that appear between prompts.
    """
    try:
        import pexpect
    except ImportError:
        _output({"success": False, "error": "pexpect not installed"})
        return

    command = args.command
    timeout = args.timeout
    prompts = json.loads(args.prompts)  # [[pattern, response], ...]

    debug_log(f"interactive cmd={command!r} prompts={len(prompts)} timeout={timeout}",
              caller="ssh")

    start_time = time.time()
    output_buffer = []
    matched_prompts = []

    try:
        ssh_cmd = (f"ssh -o ControlPath={state['control_path']} "
                   f"-o ConnectTimeout=10 "
                   f"{state['host']} {command}")
        child = pexpect.spawn(ssh_cmd, timeout=timeout, encoding='utf-8')

        # Build pattern list: all prompt patterns + EOF + TIMEOUT
        patterns = [p[0] for p in prompts]
        sentinel_eof = len(patterns)
        sentinel_timeout = len(patterns) + 1
        expect_list = patterns + [pexpect.EOF, pexpect.TIMEOUT]

        # Track which prompts have been answered (allow repeats for
        # prompts like "Confirm vault password" that appear twice)
        max_iterations = len(prompts) * 3  # safety cap
        iterations = 0

        while iterations < max_iterations:
            iterations += 1
            idx = child.expect(expect_list)

            output_buffer.append(child.before or "")

            if idx == sentinel_eof:
                debug_log("interactive: EOF reached", caller="ssh")
                break
            elif idx == sentinel_timeout:
                debug_log(
                    f"interactive TIMEOUT after {timeout}s."
                    f" before={child.before!r} matched_so_far={matched_prompts}",
                    caller="ssh", level=40,
                )
                _output({
                    "success": False,
                    "return_code": -1,
                    "stdout": "".join(output_buffer),
                    "stderr": f"Interactive command timed out after {timeout}s",
                    "duration": round(time.time() - start_time, 2),
                    "matched_prompts": matched_prompts,
                })
                return
            else:
                # Matched a prompt — send the corresponding response
                output_buffer.append(child.after or "")
                prompt_pattern = prompts[idx][0]
                response = prompts[idx][1]
                matched_prompts.append(prompt_pattern)
                debug_log(f"interactive: matched {prompt_pattern!r}, sending response",
                          caller="ssh")
                child.sendline(response)

        child.close()
        duration = time.time() - start_time
        exit_code = child.exitstatus or 0

        _output({
            "success": exit_code == 0,
            "return_code": exit_code,
            "stdout": "".join(output_buffer),
            "stderr": "",
            "duration": round(duration, 2),
            "matched_prompts": matched_prompts,
        })
    except pexpect.EOF:
        _output({
            "success": False,
            "return_code": -1,
            "stdout": "".join(output_buffer),
            "stderr": "Command ended unexpectedly",
            "duration": round(time.time() - start_time, 2),
            "matched_prompts": matched_prompts,
        })
    except Exception as e:
        _output({
            "success": False,
            "return_code": -1,
            "stdout": "".join(output_buffer),
            "stderr": f"Interactive execution error: {e}",
            "duration": round(time.time() - start_time, 2),
            "matched_prompts": matched_prompts,
        })


@json_safe
@requires_connection
def cmd_vm_disks(args, state):
    """List disks attached to a KubeVirt VM via virsh domblklist.

    Returns parsed disk info as JSON array.
    """
    vm_name = args.vm_name
    namespace = args.namespace
    timeout = args.timeout

    # Get the virt-launcher pod name
    pod_cmd = (
        f"oc get pods -n {shlex.quote(namespace)} -l vm.kubevirt.io/name={shlex.quote(vm_name)} "
        f"--no-headers -o custom-columns=':metadata.name' 2>&1"
    )
    ok, stdout, stderr, rc, duration = _ssh_exec(state, pod_cmd, timeout=30)
    pod_name = stdout.strip()
    if not pod_name or not ok:
        _output({
            "success": False,
            "error": f"No virt-launcher pod found for VM {vm_name} in {namespace}",
            "duration": duration,
        })
        return

    # Run virsh domblklist
    virsh_cmd = f"oc exec -n {shlex.quote(namespace)} {shlex.quote(pod_name)} -- virsh domblklist 1 2>&1"
    ok, stdout, stderr, rc, duration = _ssh_exec(state, virsh_cmd, timeout=timeout)

    # Parse the virsh output into structured data
    disks = []
    for line in stdout.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('Target') or line.startswith('---'):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            target, source = parts
            disk_type = "unknown"
            if '/hotplug-disks/' in source:
                disk_type = "hotplug"
            elif '/vmi-disks/' in source:
                disk_type = "persistent"
            elif source.startswith('/dev/'):
                disk_type = "block"
            elif 'cloud-init' in source or 'noCloud' in source:
                disk_type = "cloudinit"
            # Extract volume name from source path
            vol_name = source.rsplit('/', 1)[-1] if '/' in source else source
            if vol_name == 'disk.img':
                vol_name = source.rsplit('/', 2)[-2] if source.count('/') >= 2 else vol_name
            disks.append({
                "target": target,
                "source": source,
                "type": disk_type,
                "volume": vol_name,
            })

    _output({
        "success": rc == 0,
        "disks": disks,
        "raw": stdout,
        "duration": duration,
    })


@json_safe
@requires_connection
def cmd_vm_exec(args, state):
    """Execute a command inside a KubeVirt VM.

    Tries virtctl ssh first (fast, clean output). If that fails due to
    auth issues, falls back to serial console via pexpect.
    """
    vm_name = args.vm_name
    namespace = args.namespace
    command = args.command
    user = args.user
    password = args.password
    timeout = args.timeout

    debug_log(f"vm-exec vm={vm_name} ns={namespace} user={user} cmd={command!r}",
              caller="ssh")
    start_time = time.time()

    # Strategy 1: virtctl ssh (key-based auth)
    ssh_cmd = (
        f"virtctl ssh {shlex.quote(user)}@{shlex.quote(vm_name)} -n {shlex.quote(namespace)} "
        f"--command {shlex.quote(command)} -l {shlex.quote(user)} --known-hosts="
    )
    try:
        result = subprocess.run(
            ['ssh'] + _ssh_opts(state) + [state["host"], ssh_cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        stdout = _strip_ansi(result.stdout)
        stderr = _strip_ansi(result.stderr)
        combined = stdout + stderr
        auth_failures = ["Permission denied", "Please login as", "publickey,gssapi"]
        is_auth_fail = any(p in combined for p in auth_failures)
        if result.returncode == 0 or not is_auth_fail:
            _output({
                "success": result.returncode == 0,
                "return_code": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "method": "virtctl-ssh",
                "duration": round(time.time() - start_time, 2),
            })
            return
    except subprocess.TimeoutExpired:
        pass  # fall through to console

    _err(f"virtctl ssh failed for {vm_name}, falling back to serial console")

    # Strategy 2: Serial console via pexpect
    try:
        import pexpect
    except ImportError:
        _output({"success": False, "error": "pexpect not installed and virtctl ssh failed"})
        return

    console_cmd = (
        f"ssh -o ControlPath={state['control_path']} -o ConnectTimeout=10 "
        f"{state['host']} virtctl console {shlex.quote(vm_name)} -n {shlex.quote(namespace)}"
    )
    output_buffer = []
    try:
        child = pexpect.spawn(console_cmd, timeout=timeout, encoding='utf-8')
        # Wait for console to connect, then send Enter to trigger prompt
        child.expect(r'Successfully connected|escape sequence', timeout=30)
        time.sleep(2)
        child.sendline("")
        time.sleep(1)
        child.sendline("")

        # Match login prompt or shell prompt (ANSI-tolerant)
        idx = child.expect([r'ogin:', r'[\]#\$] *$', pexpect.TIMEOUT], timeout=15)
        if idx == 0:
            # Need to login
            child.sendline(user)
            child.expect(r'assword:', timeout=10)
            child.sendline(password)
            child.expect(r'[\]#\$]', timeout=15)
        elif idx == 2:
            # Timeout — try one more Enter
            child.sendline("")
            child.expect([r'ogin:', r'[\]#\$]'], timeout=10)
            if 'ogin:' in (child.after or ''):
                child.sendline(user)
                child.expect(r'assword:', timeout=10)
                child.sendline(password)
                child.expect(r'[\]#\$]', timeout=15)

        # At shell prompt — run the command with exit code marker
        marker = f"EQA_EXIT_{uuid.uuid4().hex}"
        child.sendline(f"{command}; echo; echo {marker}=$?")
        child.expect(f'{marker}=(\\d+)', timeout=timeout)
        output_buffer.append(child.before or "")
        exit_code = int(child.match.group(1))

        # Logout
        child.sendline("exit")
        try:
            child.expect(pexpect.EOF, timeout=5)
        except (pexpect.TIMEOUT, pexpect.EOF):
            pass
        child.close()

        raw_output = "".join(output_buffer)
        # Strip ANSI codes but preserve all content lines (no spinner filtering)
        clean_output = _strip_ansi(raw_output, strip_spinners=False)
        # Remove the echoed command from the output
        lines = clean_output.split('\n')
        filtered = [l for l in lines if command not in l and marker not in l]
        clean_output = '\n'.join(filtered).strip()

        _output({
            "success": exit_code == 0,
            "return_code": exit_code,
            "stdout": clean_output,
            "stderr": "",
            "method": "console",
            "duration": round(time.time() - start_time, 2),
        })
    except pexpect.TIMEOUT:
        _output({
            "success": False,
            "return_code": -1,
            "stdout": "".join(output_buffer),
            "stderr": f"VM console timed out after {timeout}s",
            "method": "console",
            "duration": round(time.time() - start_time, 2),
        })
    except Exception as e:
        _output({
            "success": False,
            "return_code": -1,
            "stdout": "".join(output_buffer),
            "stderr": f"VM exec error: {e}",
            "method": "console",
            "duration": round(time.time() - start_time, 2),
        })


@json_safe
@requires_connection
def cmd_write_file(args, state):
    """Write file to remote system via base64 encoding."""
    remote_path = args.remote_path
    content_b64 = args.content

    quoted_path = shlex.quote(remote_path)
    cmd = f"mkdir -p \"$(dirname {quoted_path})\" && base64 -d > {quoted_path}"

    ok, stdout, stderr, rc, duration = _ssh_exec(state, cmd, timeout=30, input_data=content_b64)
    _output({
        "success": ok,
        "return_code": rc,
        "stderr": stderr,
    })


@json_safe
@requires_connection
def cmd_read_file(args, state):
    """Read file from remote system."""
    remote_path = args.remote_path

    ok, stdout, stderr, rc, duration = _ssh_exec(
        state, f"cat {shlex.quote(remote_path)}", timeout=30,
    )
    _output({
        "success": ok,
        "content": stdout if ok else None,
        "error": stderr if not ok else None,
    })


@json_safe
@requires_connection
def cmd_devcontainer_start(args, state):
    """Parse devcontainer.json and start container on workstation."""
    project_dir = args.project_dir
    host = state["host"]
    opts = _ssh_opts(state)

    def ssh_run(command, timeout=30):
        result = subprocess.run(
            ['ssh'] + opts + [host, command],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.returncode == 0, _strip_ansi(result.stdout), _strip_ansi(result.stderr)

    # Find devcontainer.json
    config = None
    for dc_path in [
        f"{project_dir}/.devcontainer/podman/devcontainer.json",
        f"{project_dir}/.devcontainer/devcontainer.json",
    ]:
        ok, content, _ = ssh_run(f"cat {shlex.quote(dc_path)} 2>/dev/null")
        if ok and content.strip():
            try:
                config = json.loads(content)
                break
            except json.JSONDecodeError:
                continue

    if not config:
        _output({"success": False, "error": "No devcontainer.json found"})
        return

    image = config.get("image", "")
    run_args = config.get("runArgs", [])
    container_user = config.get("containerUser")
    container_name = "qa-devcontainer"

    if not image:
        _output({"success": False, "error": "No image specified in devcontainer.json"})
        return

    exercise_name = project_dir.rstrip('/').split('/')[-1]

    # Check disk space before starting (need ~2GB for container + EE image)
    ok_df, df_out, _ = ssh_run("df / --output=avail | tail -1")
    if ok_df:
        try:
            avail_kb = int(df_out.strip())
            avail_gb = avail_kb / (1024 * 1024)
            if avail_gb < 2.0:
                _err(f"WARNING: Only {avail_gb:.1f}GB free on workstation. Dev container + EE image needs ~2GB.")
                _err("Consider running: ssh workstation 'podman system prune -af && rm -rf ~/.cache/uv'")
        except (ValueError, TypeError):
            pass

    # Stop any existing container
    ssh_run(f"podman rm -f {shlex.quote(container_name)} 2>/dev/null", timeout=10)

    # Determine SSH mount paths
    home_dir = "/home/student"
    if container_user == "root":
        container_ssh_dir = "/root/.ssh"
    else:
        container_ssh_dir = f"/home/{container_user or 'student'}/.ssh"

    # Build podman run command
    # run_args are parsed from devcontainer.json (podman flags like --cap-add SYS_PTRACE),
    # treated as trusted project config, not raw user input
    args_str = " ".join(run_args)
    user_flag = f"--user {shlex.quote(container_user)}" if container_user else ""
    cmd = (f"podman run -d --name {shlex.quote(container_name)} "
           f"{user_flag} "
           f"{args_str} "
           f"-v {shlex.quote(project_dir)}:/workspaces/{shlex.quote(exercise_name)}:Z "
           f"-v {home_dir}/.ssh:{container_ssh_dir}:z "
           f"{shlex.quote(image)} sleep infinity")

    ok, stdout, stderr = ssh_run(cmd, timeout=120)
    if ok:
        # Verify container
        ok2, out2, _ = ssh_run(f"podman exec {shlex.quote(container_name)} echo 'ready'", timeout=15)
        if ok2 and 'ready' in out2:
            workdir = f"/workspaces/{exercise_name}"
            # Save devcontainer state
            state["devcontainer"] = {
                "name": container_name,
                "workdir": workdir,
                "user": container_user,
                "image": image,
            }
            save_state(STATE_FILE, state)

            _output({
                "success": True,
                "workdir": workdir,
                "user": container_user,
                "image": image,
                "container_name": container_name,
            })
            return

    _output({"success": False, "error": f"Failed to start container: {stderr}"})


@json_safe
@requires_connection
def cmd_devcontainer_run(args, state):
    """Execute command in dev container."""
    dc = state.get("devcontainer", {})
    container_name = dc.get("name", "qa-devcontainer")
    workdir = args.workdir or dc.get("workdir")
    user = args.user or dc.get("user")

    workdir_flag = f"-w {shlex.quote(workdir)}" if workdir else ""
    user_flag = f"--user {shlex.quote(user)}" if user else ""
    escaped_cmd = shlex.quote(args.command)

    full_cmd = f"podman exec {user_flag} {workdir_flag} {shlex.quote(container_name)} bash -c {escaped_cmd}"

    ok, stdout, stderr, rc, duration = _ssh_exec(state, full_cmd, timeout=args.timeout)
    _output({
        "success": ok,
        "return_code": rc,
        "stdout": stdout,
        "stderr": stderr,
        "duration": duration,
    })


@json_safe
@requires_connection
def cmd_devcontainer_stop(args, state):
    """Stop and remove dev container."""
    dc = state.get("devcontainer", {})
    container_name = dc.get("name", "qa-devcontainer")

    _ssh_exec(state, f"podman rm -f {shlex.quote(container_name)} 2>/dev/null", timeout=15)
    if "devcontainer" in state:
        del state["devcontainer"]
        save_state(STATE_FILE, state)

    _output({"success": True})


@json_safe
@requires_connection
def cmd_autotest(args, state):
    """Run DynoLabs 5 autotest (Rust CLI only)."""
    framework = state.get("framework", "unknown")
    if framework != 'dynolabs5':
        _output({
            "success": False,
            "error": f"autotest requires DynoLabs 5 Rust CLI (detected: {framework})",
        })
        return

    cmd = "lab autotest"
    if args.ignore_errors:
        cmd += " --ignore-errors"

    _err(f"Running: {cmd}")
    ok, stdout, stderr, rc, duration = _ssh_exec(state, cmd, timeout=args.timeout)
    _output({
        "success": ok,
        "return_code": rc,
        "stdout": stdout,
        "stderr": stderr,
        "duration": duration,
    })


@json_safe
@requires_connection
def cmd_coursetest(args, state):
    """Run DynoLabs 5 coursetest (Rust CLI only)."""
    framework = state.get("framework", "unknown")
    if framework != 'dynolabs5':
        _output({
            "success": False,
            "error": f"coursetest requires DynoLabs 5 Rust CLI (detected: {framework})",
        })
        return

    cmd = f"lab coursetest {shlex.quote(args.scripts_file)}"
    if args.dry_run:
        cmd += " --dry-run"

    _err(f"Running: {cmd}")
    ok, stdout, stderr, rc, duration = _ssh_exec(state, cmd, timeout=args.timeout)
    _output({
        "success": ok,
        "return_code": rc,
        "stdout": stdout,
        "stderr": stderr,
        "duration": duration,
    })


@json_safe
@requires_connection
def cmd_wait_for(args, state):
    """Poll until a condition is met on the remote host."""
    mode = args.mode
    target = args.target
    timeout = args.timeout
    interval = args.interval

    if mode == "tcp":
        parts = target.rsplit(":", 1)
        if len(parts) != 2:
            _output({"success": False, "error": "tcp mode requires --target host:port"})
            return
        host, port = parts[0], parts[1]
        check_cmd = f"nc -z -w1 {shlex.quote(host)} {shlex.quote(port)}"
    elif mode == "http":
        check_cmd = f"curl -sk -o /dev/null -w '%{{http_code}}' {shlex.quote(target)}"
    elif mode == "command":
        check_cmd = target
    elif mode == "file":
        check_cmd = f"test -f {shlex.quote(target)}"
    else:
        _output({"success": False, "error": f"Unknown mode: {mode}"})
        return

    start_time = time.time()
    attempts = 0

    while True:
        attempts += 1
        ok, stdout, stderr, rc, _ = _ssh_exec(state, check_cmd, timeout=30)

        if mode == "http":
            code = stdout.strip()
            ok = code.startswith("2") or code.startswith("3")

        if ok:
            elapsed = round(time.time() - start_time, 2)
            _output({"success": True, "elapsed": elapsed, "attempts": attempts})
            return

        elapsed = time.time() - start_time
        if elapsed + interval > timeout:
            _output({
                "success": False,
                "error": f"Timed out after {round(elapsed, 2)}s ({attempts} attempts)",
                "elapsed": round(elapsed, 2),
                "attempts": attempts,
            })
            return

        time.sleep(interval)


@json_safe
@requires_connection
def cmd_diff(args, state):
    """Compare remote file against expected content."""
    import base64
    import difflib

    remote_path = args.remote_path
    expected_b64 = args.expected

    try:
        expected_content = base64.b64decode(expected_b64).decode("utf-8")
    except Exception as e:
        _output({"success": False, "error": f"Failed to decode expected content: {e}"})
        return

    ok, stdout, stderr, rc, duration = _ssh_exec(
        state, f"cat {shlex.quote(remote_path)}", timeout=30,
    )
    if not ok:
        _output({
            "success": False,
            "error": f"Failed to read remote file: {stderr}",
            "return_code": rc,
        })
        return

    remote_content = stdout

    if remote_content == expected_content:
        _output({"success": True, "match": True})
        return

    diff_lines = list(difflib.unified_diff(
        expected_content.splitlines(keepends=True),
        remote_content.splitlines(keepends=True),
        fromfile="expected",
        tofile=remote_path,
    ))
    _output({
        "success": True,
        "match": False,
        "diff": "".join(diff_lines),
    })


@json_safe
def cmd_disconnect(args):
    """Tear down ControlMaster connection."""
    state = load_state(STATE_FILE)
    if not state:
        _output({"success": True, "message": "No active connection"})
        return

    control_path = state.get("control_path", "")
    host = state.get("host", "")

    try:
        if os.path.exists(control_path):
            subprocess.run(
                ['ssh', '-o', f'ControlPath={control_path}', '-O', 'exit', host],
                capture_output=True, timeout=5,
            )
    except Exception:
        pass

    try:
        if os.path.exists(control_path):
            os.unlink(control_path)
    except Exception:
        pass

    if os.path.exists(STATE_FILE):
        os.unlink(STATE_FILE)

    _output({"success": True})


def main():
    parser = argparse.ArgumentParser(description="SSH tool for eqa")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # connect
    p_connect = subparsers.add_parser("connect")
    p_connect.add_argument("--host", default=None, help="Workstation hostname (auto-detected from ~/.ssh/config if omitted)")
    p_connect.set_defaults(func=cmd_connect)

    # status
    p_status = subparsers.add_parser("status")
    p_status.set_defaults(func=cmd_status)

    # tunnel
    p_tunnel = subparsers.add_parser("tunnel")
    p_tunnel.set_defaults(func=cmd_tunnel)

    # run
    p_run = subparsers.add_parser("run")
    p_run.add_argument("command")
    p_run.add_argument("--timeout", type=int, default=120)
    p_run.set_defaults(func=cmd_run)

    # lab
    p_lab = subparsers.add_parser("lab")
    p_lab.add_argument("action", choices=["start", "finish", "grade", "install", "solve", "force"])
    p_lab.add_argument("exercise")
    p_lab.add_argument("--timeout", type=int, default=600)
    p_lab.set_defaults(func=cmd_lab)

    # vm-exec
    p_vm_exec = subparsers.add_parser("vm-exec")
    p_vm_exec.add_argument("vm_name")
    p_vm_exec.add_argument("--namespace", "-n", required=True)
    p_vm_exec.add_argument("--command", "-c", required=True)
    p_vm_exec.add_argument("--user", default="root")
    p_vm_exec.add_argument("--password", default="redhat")
    p_vm_exec.add_argument("--timeout", type=int, default=60)
    p_vm_exec.set_defaults(func=cmd_vm_exec)

    # vm-disks
    p_vm_disks = subparsers.add_parser("vm-disks")
    p_vm_disks.add_argument("vm_name")
    p_vm_disks.add_argument("--namespace", "-n", required=True)
    p_vm_disks.add_argument("--timeout", type=int, default=30)
    p_vm_disks.set_defaults(func=cmd_vm_disks)

    # interactive
    p_interactive = subparsers.add_parser("interactive")
    p_interactive.add_argument("command")
    p_interactive.add_argument("--prompts", required=True, help="JSON array of [pattern, response] pairs")
    p_interactive.add_argument("--timeout", type=int, default=120)
    p_interactive.set_defaults(func=cmd_interactive)

    # write-file
    p_write = subparsers.add_parser("write-file")
    p_write.add_argument("remote_path")
    p_write.add_argument("--content", required=True, help="Base64-encoded content")
    p_write.set_defaults(func=cmd_write_file)

    # read-file
    p_read = subparsers.add_parser("read-file")
    p_read.add_argument("remote_path")
    p_read.set_defaults(func=cmd_read_file)

    # devcontainer-start
    p_dc_start = subparsers.add_parser("devcontainer-start")
    p_dc_start.add_argument("project_dir")
    p_dc_start.set_defaults(func=cmd_devcontainer_start)

    # devcontainer-run
    p_dc_run = subparsers.add_parser("devcontainer-run")
    p_dc_run.add_argument("command")
    p_dc_run.add_argument("--workdir", default=None)
    p_dc_run.add_argument("--user", default=None)
    p_dc_run.add_argument("--timeout", type=int, default=120)
    p_dc_run.set_defaults(func=cmd_devcontainer_run)

    # devcontainer-stop
    p_dc_stop = subparsers.add_parser("devcontainer-stop")
    p_dc_stop.set_defaults(func=cmd_devcontainer_stop)

    # autotest
    p_autotest = subparsers.add_parser("autotest")
    p_autotest.add_argument("--ignore-errors", action="store_true")
    p_autotest.add_argument("--timeout", type=int, default=1800)
    p_autotest.set_defaults(func=cmd_autotest)

    # coursetest
    p_coursetest = subparsers.add_parser("coursetest")
    p_coursetest.add_argument("scripts_file", nargs="?", default="scripts.yml")
    p_coursetest.add_argument("--dry-run", action="store_true")
    p_coursetest.add_argument("--timeout", type=int, default=3600)
    p_coursetest.set_defaults(func=cmd_coursetest)

    # wait-for
    p_wait = subparsers.add_parser("wait-for")
    p_wait.add_argument("--mode", required=True, choices=["tcp", "http", "command", "file"])
    p_wait.add_argument("--target", required=True, help="host:port, URL, shell command, or file path")
    p_wait.add_argument("--timeout", type=int, default=120)
    p_wait.add_argument("--interval", type=int, default=5)
    p_wait.set_defaults(func=cmd_wait_for)

    # diff
    p_diff = subparsers.add_parser("diff")
    p_diff.add_argument("remote_path")
    p_diff.add_argument("--expected", required=True, help="Base64-encoded expected content")
    p_diff.set_defaults(func=cmd_diff)

    # disconnect
    p_disconnect = subparsers.add_parser("disconnect")
    p_disconnect.set_defaults(func=cmd_disconnect)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
