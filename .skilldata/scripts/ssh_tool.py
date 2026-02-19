#!/usr/bin/env python3
"""SSH ControlMaster management and remote command execution.

All output is JSON to stdout, diagnostics to stderr.
State persists across invocations via /tmp/eqa-ssh-state.json.

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
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time


STATE_FILE = "/tmp/eqa-ssh-state.json"


def _strip_ansi(text: str, strip_spinners: bool = True) -> str:
    """Strip ANSI escape codes and control characters from output.

    Args:
        text: Raw text with potential ANSI codes.
        strip_spinners: If True, also remove DynoLabs spinner progress lines
            and collapse empty lines. Set to False for VM command output
            where all content should be preserved.
    """
    text = re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', text)  # CSI sequences (including ?2004h/l)
    text = re.sub(r'\x1b\][^\x07]*\x07', '', text)       # OSC sequences
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)  # control chars
    text = text.replace('\r\n', '\n').replace('\r', '\n')  # normalize line endings

    if not strip_spinners:
        return text

    # Strip DynoLabs spinner lines (e.g., "   -    Checking lab systems")
    # These are progress indicator lines with a single spinner char (- \ /)
    # followed by 4+ spaces. Exclude | to avoid matching MySQL table output.
    lines = text.split('\n')
    filtered = []
    for line in lines:
        stripped = line.strip()
        # Skip spinner lines: single spinner char (not |) + 4 spaces + text
        if re.match(r'^[-\\/]\s{4}', stripped):
            continue
        # Skip empty lines that result from spinner removal
        if not stripped:
            continue
        filtered.append(line)
    return '\n'.join(filtered)


def _load_state() -> dict:
    """Load persisted SSH state."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_state(state: dict):
    """Persist SSH state."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)


def _ssh_opts(state: dict) -> list:
    """Common SSH options."""
    return [
        '-o', f'ControlPath={state["control_path"]}',
        '-o', 'ConnectTimeout=10',
        '-o', 'ServerAliveInterval=30',
        '-o', 'ServerAliveCountMax=3',
    ]


def _output(data: dict):
    """Print JSON to stdout."""
    print(json.dumps(data))


def _err(msg: str):
    """Print diagnostic to stderr."""
    print(msg, file=sys.stderr)


def _shell_quote(s: str) -> str:
    """Quote a string for safe shell use."""
    return "'" + s.replace("'", "'\\''") + "'"


def cmd_connect(args):
    """Start ControlMaster, detect framework, persist state."""
    host = args.host
    control_dir = tempfile.mkdtemp(prefix="eqa-ssh-")
    control_path = os.path.join(control_dir, f"{host}.sock")

    _err(f"Connecting to {host}...")

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
        "control_dir": control_dir,
        "host": host,
        "framework": None,
        "framework_prefix": None,
    }

    # Detect lab framework
    framework, prefix = _detect_framework(state)
    state["framework"] = framework
    state["framework_prefix"] = prefix

    _save_state(state)

    _output({
        "success": True,
        "host": host,
        "control_path": control_path,
        "framework": framework,
        "framework_prefix": prefix,
    })


def _detect_framework(state: dict) -> tuple:
    """Detect which lab framework is available."""
    host = state["host"]
    opts = _ssh_opts(state)

    def ssh_run(command, timeout=10):
        try:
            result = subprocess.run(
                ['ssh'] + opts + [host, command],
                capture_output=True, text=True, timeout=timeout,
            )
            return result.returncode == 0, _strip_ansi(result.stdout)
        except Exception:
            return False, ""

    # Check for standard lab command
    ok, stdout = ssh_run("which lab 2>/dev/null")
    if ok and stdout.strip():
        lab_path = stdout.strip()

        # Check if it's Rust CLI (ELF binary)
        ok, file_type = ssh_run(f"file {lab_path} 2>/dev/null")
        file_type_lower = file_type.lower() if ok else ""

        if 'elf' in file_type_lower or 'executable' in file_type_lower:
            ok, help_out = ssh_run("lab --help 2>/dev/null | grep -q autotest && echo 'rust'")
            if ok and 'rust' in help_out:
                return ('dynolabs5-rust', 'lab')

        if 'script' in file_type_lower or 'text' in file_type_lower:
            return ('wrapper', 'lab')

        return ('dynolabs', 'lab')

    # Check for DynoLabs 5 Python grading (uv-based)
    ok_uv, _ = ssh_run("which uv 2>/dev/null")
    ok_grading, grading_out = ssh_run("test -f ~/grading/pyproject.toml && echo 'exists'")
    if ok_uv and ok_grading and 'exists' in grading_out:
        return ('dynolabs5-python', 'cd ~/grading && uv run lab')

    return ('unknown', 'lab')


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


def cmd_status(args):
    """Check connection status, framework info, and disk space."""
    state = _load_state()
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

        # Get classroom subnets
        try:
            nets = subprocess.run(
                ['ssh'] + _ssh_opts(state) + [state["host"],
                 "ip route | grep -v default | awk '{print $1}' | grep -v '^10\\.88\\.'"],
                capture_output=True, text=True, timeout=5,
            )
            if nets.returncode == 0:
                result["subnets"] = [s.strip() for s in nets.stdout.strip().split('\n') if s.strip()]
        except Exception:
            pass

    _output(result)


def cmd_tunnel(args):
    """Generate sshuttle command for classroom network tunnel."""
    state = _load_state()
    if not state:
        _output({"success": False, "error": "Not connected. Run 'connect' first."})
        return

    if not _check_connection(state):
        _output({"success": False, "error": "Connection lost. Run 'connect' again."})
        return

    try:
        nets = subprocess.run(
            ['ssh'] + _ssh_opts(state) + [state["host"],
             "ip route | grep -v default | awk '{print $1}' | grep -v '^10\\.88\\.'"],
            capture_output=True, text=True, timeout=5,
        )
        subnets = [s.strip() for s in nets.stdout.strip().split('\n') if s.strip()]
    except Exception:
        subnets = []

    if not subnets:
        _output({"success": False, "error": "Could not detect classroom subnets"})
        return

    host = state["host"]
    cmd = f"sudo sshuttle --dns -r {host} {' '.join(subnets)} -D"
    _output({
        "success": True,
        "subnets": subnets,
        "command": cmd,
        "instructions": f"Run this in a separate terminal: {cmd}",
    })


def cmd_run(args):
    """Execute command via ControlMaster."""
    state = _load_state()
    if not state:
        _output({"success": False, "error": "Not connected. Run 'connect' first."})
        return

    # Check for stale socket
    if not _check_connection(state):
        _err("ControlMaster socket is stale, reconnecting...")
        # Attempt reconnect
        host = state["host"]
        control_dir = state.get("control_dir", tempfile.mkdtemp(prefix="eqa-ssh-"))
        control_path = os.path.join(control_dir, f"{host}.sock")
        try:
            cmd = [
                'ssh',
                '-o', f'ControlPath={control_path}',
                '-o', 'ControlMaster=yes',
                '-o', 'ControlPersist=600',
                '-o', 'ConnectTimeout=15',
                '-N', '-f',
                host,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                state["control_path"] = control_path
                state["control_dir"] = control_dir
                _save_state(state)
                _err("Reconnected successfully")
            else:
                _output({"success": False, "error": "Connection lost and reconnect failed. Run 'connect' again."})
                return
        except Exception as e:
            _output({"success": False, "error": f"Reconnect failed: {e}"})
            return

    command = args.command
    timeout = args.timeout
    start_time = time.time()

    try:
        result = subprocess.run(
            ['ssh'] + _ssh_opts(state) + [state["host"], command],
            capture_output=True, text=True, timeout=timeout,
        )
        duration = time.time() - start_time

        _output({
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": _strip_ansi(result.stdout),
            "stderr": _strip_ansi(result.stderr),
            "duration": round(duration, 2),
        })
    except subprocess.TimeoutExpired:
        _output({
            "success": False,
            "return_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "duration": timeout,
        })
    except Exception as e:
        _output({
            "success": False,
            "return_code": -1,
            "stdout": "",
            "stderr": f"Execution error: {e}",
            "duration": round(time.time() - start_time, 2),
        })


def cmd_lab(args):
    """Run framework-aware lab command."""
    state = _load_state()
    if not state:
        _output({"success": False, "error": "Not connected. Run 'connect' first."})
        return

    action = args.action
    exercise = args.exercise
    timeout = args.timeout
    prefix = state.get("framework_prefix", "lab")
    framework = state.get("framework", "unknown")

    # 'force' bypasses framework prefix, uses raw exercise as SKU
    if action == 'force':
        cmd = f"lab force {exercise}"
    else:
        # Strip -ge/-lab suffix
        lab_name = exercise.removesuffix('-ge').removesuffix('-lab')
        cmd = f"{prefix} {action} {lab_name}"
    _err(f"Running: {cmd} (framework: {framework})")

    start_time = time.time()
    try:
        result = subprocess.run(
            ['ssh'] + _ssh_opts(state) + [state["host"], cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        duration = time.time() - start_time
        stdout = _strip_ansi(result.stdout)
        stderr = _strip_ansi(result.stderr)
        success = result.returncode == 0

        # If lab start fails or warns about a blocking lab, finish it and retry.
        # Some frameworks return exit code 0 but print a warning with
        # "lab finish <name>" in stdout instead of failing outright.
        if action == 'start':
            output = stdout + stderr
            match = re.search(r'lab finish\s+(\S+)', output)
            if match:
                blocking_lab = match.group(1)
                _err(f"Finishing blocking lab: {blocking_lab}")
                subprocess.run(
                    ['ssh'] + _ssh_opts(state) + [state["host"], f"{prefix} finish {blocking_lab}"],
                    capture_output=True, text=True, timeout=120,
                )
                _err(f"Retrying: {cmd}")
                result = subprocess.run(
                    ['ssh'] + _ssh_opts(state) + [state["host"], cmd],
                    capture_output=True, text=True, timeout=timeout,
                )
                duration = time.time() - start_time
                stdout = _strip_ansi(result.stdout)
                stderr = _strip_ansi(result.stderr)
                success = result.returncode == 0

        # Check stdout for FAIL indicators (start/finish only)
        if success and action in ('start', 'finish'):
            if re.search(r'\bFAIL\b', stdout):
                success = False

        _output({
            "success": success,
            "return_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "duration": round(duration, 2),
            "framework": framework,
            "command": cmd,
        })
    except subprocess.TimeoutExpired:
        _output({
            "success": False,
            "return_code": -1,
            "stdout": "",
            "stderr": f"Lab command timed out after {timeout}s",
            "duration": timeout,
            "framework": framework,
            "command": cmd,
        })


def cmd_interactive(args):
    """Execute interactive command via pexpect."""
    state = _load_state()
    if not state:
        _output({"success": False, "error": "Not connected. Run 'connect' first."})
        return

    try:
        import pexpect
    except ImportError:
        _output({"success": False, "error": "pexpect not installed"})
        return

    command = args.command
    timeout = args.timeout
    prompts = json.loads(args.prompts)  # [[pattern, response], ...]

    start_time = time.time()
    output_buffer = []

    try:
        ssh_cmd = (f"ssh -o ControlPath={state['control_path']} "
                   f"-o ConnectTimeout=10 "
                   f"{state['host']} {command}")
        child = pexpect.spawn(ssh_cmd, timeout=timeout, encoding='utf-8')

        for prompt_pattern, response in prompts:
            child.expect(prompt_pattern)
            output_buffer.append(child.before or "")
            output_buffer.append(child.after or "")
            child.sendline(response)

        child.expect(pexpect.EOF)
        output_buffer.append(child.before or "")
        child.close()

        duration = time.time() - start_time
        exit_code = child.exitstatus or 0

        _output({
            "success": exit_code == 0,
            "return_code": exit_code,
            "stdout": "".join(output_buffer),
            "stderr": "",
            "duration": round(duration, 2),
        })
    except pexpect.TIMEOUT:
        _output({
            "success": False,
            "return_code": -1,
            "stdout": "".join(output_buffer),
            "stderr": f"Interactive command timed out after {timeout}s",
            "duration": timeout,
        })
    except pexpect.EOF:
        _output({
            "success": False,
            "return_code": -1,
            "stdout": "".join(output_buffer),
            "stderr": "Command ended before all prompts were handled",
            "duration": round(time.time() - start_time, 2),
        })
    except Exception as e:
        _output({
            "success": False,
            "return_code": -1,
            "stdout": "".join(output_buffer),
            "stderr": f"Interactive execution error: {e}",
            "duration": round(time.time() - start_time, 2),
        })


def cmd_vm_disks(args):
    """List disks attached to a KubeVirt VM via virsh domblklist.

    Returns parsed disk info as JSON array.
    """
    state = _load_state()
    if not state:
        _output({"success": False, "error": "Not connected. Run 'connect' first."})
        return

    vm_name = args.vm_name
    namespace = args.namespace
    timeout = args.timeout

    start_time = time.time()

    # Get the virt-launcher pod name
    pod_cmd = (
        f"oc get pods -n {namespace} -l vm.kubevirt.io/name={vm_name} "
        f"--no-headers -o custom-columns=':metadata.name' 2>&1"
    )
    try:
        result = subprocess.run(
            ['ssh'] + _ssh_opts(state) + [state["host"], pod_cmd],
            capture_output=True, text=True, timeout=30,
        )
        pod_name = result.stdout.strip()
        if not pod_name or result.returncode != 0:
            _output({
                "success": False,
                "error": f"No virt-launcher pod found for VM {vm_name} in {namespace}",
                "duration": round(time.time() - start_time, 2),
            })
            return

        # Run virsh domblklist
        virsh_cmd = f"oc exec -n {namespace} {pod_name} -- virsh domblklist 1 2>&1"
        result = subprocess.run(
            ['ssh'] + _ssh_opts(state) + [state["host"], virsh_cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        stdout = _strip_ansi(result.stdout)

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
            "success": result.returncode == 0,
            "disks": disks,
            "raw": stdout,
            "duration": round(time.time() - start_time, 2),
        })
    except subprocess.TimeoutExpired:
        _output({
            "success": False,
            "error": f"Timed out after {timeout}s",
            "duration": timeout,
        })
    except Exception as e:
        _output({
            "success": False,
            "error": str(e),
            "duration": round(time.time() - start_time, 2),
        })


def cmd_vm_exec(args):
    """Execute a command inside a KubeVirt VM.

    Tries virtctl ssh first (fast, clean output). If that fails due to
    auth issues, falls back to serial console via pexpect.
    """
    state = _load_state()
    if not state:
        _output({"success": False, "error": "Not connected. Run 'connect' first."})
        return

    vm_name = args.vm_name
    namespace = args.namespace
    command = args.command
    user = args.user
    password = args.password
    timeout = args.timeout

    start_time = time.time()

    # Strategy 1: virtctl ssh (key-based auth)
    ssh_cmd = (
        f"virtctl ssh {user}@{vm_name} -n {namespace} "
        f"--command {_shell_quote(command)} -l {user} --known-hosts="
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
        f"{state['host']} virtctl console {vm_name} -n {namespace}"
    )
    output_buffer = []
    try:
        child = pexpect.spawn(console_cmd, timeout=timeout, encoding='utf-8')
        # Wait for console to connect, then send Enter to trigger prompt
        child.expect(r'Successfully connected|escape sequence', timeout=30)
        import time as _time
        _time.sleep(2)
        child.sendline("")
        _time.sleep(1)
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
        marker = "__EQA_EXIT__"
        child.sendline(f"{command}; echo {marker}=$?")
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


def cmd_write_file(args):
    """Write file to remote system via base64 encoding."""
    state = _load_state()
    if not state:
        _output({"success": False, "error": "Not connected. Run 'connect' first."})
        return

    remote_path = args.remote_path
    content_b64 = args.content

    cmd = f"mkdir -p \"$(dirname '{remote_path}')\" && echo '{content_b64}' | base64 -d > '{remote_path}'"

    try:
        result = subprocess.run(
            ['ssh'] + _ssh_opts(state) + [state["host"], cmd],
            capture_output=True, text=True, timeout=30,
        )
        _output({
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stderr": _strip_ansi(result.stderr),
        })
    except Exception as e:
        _output({"success": False, "error": str(e)})


def cmd_read_file(args):
    """Read file from remote system."""
    state = _load_state()
    if not state:
        _output({"success": False, "error": "Not connected. Run 'connect' first."})
        return

    remote_path = args.remote_path

    try:
        result = subprocess.run(
            ['ssh'] + _ssh_opts(state) + [state["host"], f"cat {_shell_quote(remote_path)}"],
            capture_output=True, text=True, timeout=30,
        )
        _output({
            "success": result.returncode == 0,
            "content": result.stdout if result.returncode == 0 else None,
            "error": _strip_ansi(result.stderr) if result.returncode != 0 else None,
        })
    except Exception as e:
        _output({"success": False, "error": str(e)})


def cmd_devcontainer_start(args):
    """Parse devcontainer.json and start container on workstation."""
    state = _load_state()
    if not state:
        _output({"success": False, "error": "Not connected. Run 'connect' first."})
        return

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
        ok, content, _ = ssh_run(f"cat {_shell_quote(dc_path)} 2>/dev/null")
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
    ssh_run(f"podman rm -f {container_name} 2>/dev/null", timeout=10)

    # Determine SSH mount paths
    home_dir = "/home/student"
    if container_user == "root":
        container_ssh_dir = "/root/.ssh"
    else:
        container_ssh_dir = f"/home/{container_user or 'student'}/.ssh"

    # Build podman run command
    args_str = " ".join(run_args)
    cmd = (f"podman run -d --name {container_name} "
           f"{args_str} "
           f"-v {project_dir}:/workspaces/{exercise_name}:Z "
           f"-v {home_dir}/.ssh:{container_ssh_dir}:Z "
           f"{image} sleep infinity")

    ok, stdout, stderr = ssh_run(cmd, timeout=120)
    if ok:
        # Verify container
        ok2, out2, _ = ssh_run(f"podman exec {container_name} echo 'ready'", timeout=15)
        if ok2 and 'ready' in out2:
            workdir = f"/workspaces/{exercise_name}"
            # Save devcontainer state
            state["devcontainer"] = {
                "name": container_name,
                "workdir": workdir,
                "user": container_user,
                "image": image,
            }
            _save_state(state)

            _output({
                "success": True,
                "workdir": workdir,
                "user": container_user,
                "image": image,
                "container_name": container_name,
            })
            return

    _output({"success": False, "error": f"Failed to start container: {stderr}"})


def cmd_devcontainer_run(args):
    """Execute command in dev container."""
    state = _load_state()
    if not state:
        _output({"success": False, "error": "Not connected. Run 'connect' first."})
        return

    dc = state.get("devcontainer", {})
    container_name = dc.get("name", "qa-devcontainer")
    workdir = args.workdir or dc.get("workdir")
    user = args.user or dc.get("user")

    workdir_flag = f"-w {workdir}" if workdir else ""
    user_flag = f"--user {user}" if user else ""
    escaped_cmd = _shell_quote(args.command)

    full_cmd = f"podman exec {user_flag} {workdir_flag} {container_name} bash -c {escaped_cmd}"

    start_time = time.time()
    try:
        result = subprocess.run(
            ['ssh'] + _ssh_opts(state) + [state["host"], full_cmd],
            capture_output=True, text=True, timeout=args.timeout,
        )
        duration = time.time() - start_time

        _output({
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": _strip_ansi(result.stdout),
            "stderr": _strip_ansi(result.stderr),
            "duration": round(duration, 2),
        })
    except subprocess.TimeoutExpired:
        _output({
            "success": False,
            "return_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {args.timeout}s",
            "duration": args.timeout,
        })


def cmd_devcontainer_stop(args):
    """Stop and remove dev container."""
    state = _load_state()
    if not state:
        _output({"success": False, "error": "Not connected."})
        return

    dc = state.get("devcontainer", {})
    container_name = dc.get("name", "qa-devcontainer")

    try:
        result = subprocess.run(
            ['ssh'] + _ssh_opts(state) + [state["host"], f"podman rm -f {container_name} 2>/dev/null"],
            capture_output=True, text=True, timeout=15,
        )
        if "devcontainer" in state:
            del state["devcontainer"]
            _save_state(state)

        _output({"success": True})
    except Exception as e:
        _output({"success": False, "error": str(e)})


def cmd_autotest(args):
    """Run DynoLabs 5 autotest (Rust CLI only)."""
    state = _load_state()
    if not state:
        _output({"success": False, "error": "Not connected. Run 'connect' first."})
        return

    framework = state.get("framework", "unknown")
    if framework != 'dynolabs5-rust':
        _output({
            "success": False,
            "error": f"autotest requires DynoLabs 5 Rust CLI (detected: {framework})",
        })
        return

    cmd = "lab autotest"
    if args.ignore_errors:
        cmd += " --ignore-errors"

    _err(f"Running: {cmd}")
    start_time = time.time()
    try:
        result = subprocess.run(
            ['ssh'] + _ssh_opts(state) + [state["host"], cmd],
            capture_output=True, text=True, timeout=args.timeout,
        )
        duration = time.time() - start_time
        _output({
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": _strip_ansi(result.stdout),
            "stderr": _strip_ansi(result.stderr),
            "duration": round(duration, 2),
        })
    except subprocess.TimeoutExpired:
        _output({
            "success": False, "return_code": -1,
            "stdout": "", "stderr": f"autotest timed out after {args.timeout}s",
            "duration": args.timeout,
        })


def cmd_coursetest(args):
    """Run DynoLabs 5 coursetest (Rust CLI only)."""
    state = _load_state()
    if not state:
        _output({"success": False, "error": "Not connected. Run 'connect' first."})
        return

    framework = state.get("framework", "unknown")
    if framework != 'dynolabs5-rust':
        _output({
            "success": False,
            "error": f"coursetest requires DynoLabs 5 Rust CLI (detected: {framework})",
        })
        return

    cmd = f"lab coursetest {args.scripts_file}"
    if args.dry_run:
        cmd += " --dry-run"

    _err(f"Running: {cmd}")
    start_time = time.time()
    try:
        result = subprocess.run(
            ['ssh'] + _ssh_opts(state) + [state["host"], cmd],
            capture_output=True, text=True, timeout=args.timeout,
        )
        duration = time.time() - start_time
        _output({
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": _strip_ansi(result.stdout),
            "stderr": _strip_ansi(result.stderr),
            "duration": round(duration, 2),
        })
    except subprocess.TimeoutExpired:
        _output({
            "success": False, "return_code": -1,
            "stdout": "", "stderr": f"coursetest timed out after {args.timeout}s",
            "duration": args.timeout,
        })


def cmd_disconnect(args):
    """Tear down ControlMaster connection."""
    state = _load_state()
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
        control_dir = state.get("control_dir", "")
        if control_dir and os.path.exists(control_dir):
            os.rmdir(control_dir)
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
    p_connect.add_argument("--host", default="workstation")
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

    # disconnect
    p_disconnect = subparsers.add_parser("disconnect")
    p_disconnect.set_defaults(func=cmd_disconnect)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
