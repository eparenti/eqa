"""SSH client for remote command execution.

Uses system ssh with ControlMaster multiplexing for fast
repeated connections through ProxyJump.
"""

import atexit
import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pexpect


def _strip_ansi(text: str) -> str:
    """Strip ANSI escape codes and spinner characters from output."""
    text = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)
    text = re.sub(r'\x1b\][^\x07]*\x07', '', text)  # OSC sequences
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)  # control chars (keep \n \r \t)
    return text


@dataclass
class CommandResult:
    """Result from SSH command execution."""
    command: str
    success: bool
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float


class SSHConnection:
    """Manages SSH connection to lab workstation using system ssh.

    Uses ControlMaster multiplexing so the ProxyJump tunnel is established
    once and all subsequent commands reuse it instantly.
    """

    def __init__(self, host: str, username: str = "student",
                 max_retries: int = 3, retry_delay: float = 2.0):
        """
        Initialize SSH connection.

        Args:
            host: Hostname (e.g., 'workstation')
            username: SSH username
            max_retries: Number of connection retry attempts
            retry_delay: Seconds between retries (exponential backoff)
        """
        self.host = host
        self.username = username
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._connected = False
        self._framework_cache = None

        # ControlMaster socket path
        self._control_dir = tempfile.mkdtemp(prefix="eqa-ssh-")
        self._control_path = os.path.join(self._control_dir, f"{host}.sock")
        self._master_process = None

        # Clean up on exit
        atexit.register(self._cleanup_master)

    def _ssh_opts(self) -> List[str]:
        """Common SSH options for all commands."""
        return [
            '-o', f'ControlPath={self._control_path}',
            '-o', 'ConnectTimeout=10',
            '-o', 'ServerAliveInterval=30',
            '-o', 'ServerAliveCountMax=3',
        ]

    def _start_master(self) -> bool:
        """Start a ControlMaster background connection."""
        try:
            cmd = [
                'ssh',
                '-o', f'ControlPath={self._control_path}',
                '-o', 'ControlMaster=yes',
                '-o', 'ControlPersist=600',
                '-o', 'ConnectTimeout=15',
                '-o', 'ServerAliveInterval=30',
                '-o', 'ServerAliveCountMax=3',
                '-N', '-f',
                self.host,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, Exception):
            return False

    def _cleanup_master(self):
        """Tear down the ControlMaster connection."""
        try:
            if os.path.exists(self._control_path):
                subprocess.run(
                    ['ssh', '-o', f'ControlPath={self._control_path}',
                     '-O', 'exit', self.host],
                    capture_output=True, timeout=5,
                )
        except Exception:
            pass
        try:
            if os.path.exists(self._control_path):
                os.unlink(self._control_path)
            if os.path.exists(self._control_dir):
                os.rmdir(self._control_dir)
        except Exception:
            pass

    def connect(self, verify_lab_tools: bool = True) -> bool:
        """
        Establish SSH ControlMaster connection with retry logic.

        Args:
            verify_lab_tools: If True, verify that 'lab' command exists on remote
        """
        for attempt in range(self.max_retries):
            # Start ControlMaster
            if self._start_master():
                # Verify it works with a quick command
                result = subprocess.run(
                    ['ssh'] + self._ssh_opts() + [self.host, 'echo', 'connected'],
                    capture_output=True, text=True, timeout=10,
                )

                if result.returncode == 0 and 'connected' in result.stdout:
                    self._connected = True

                    # Verify lab tools are available
                    if verify_lab_tools:
                        tools_ok, missing = self._verify_lab_tools()
                        if not tools_ok:
                            print(f"⚠️  Missing tools on {self.host}: {', '.join(missing)}")

                    return True

            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2 ** attempt)
                print(f"⚠️  Connection attempt {attempt + 1} failed, retrying in {delay}s...")
                time.sleep(delay)

        print(f"❌ SSH connection failed after {self.max_retries} attempts")
        return False

    def is_connected(self) -> bool:
        """Check if SSH connection is established."""
        return self._connected

    def _verify_lab_tools(self) -> Tuple[bool, List[str]]:
        """
        Verify that essential lab tools are available on the remote system.

        Returns:
            Tuple of (all_present, list_of_missing_tools)
        """
        essential_tools = ['lab']
        missing = []

        for tool in essential_tools:
            result = self.run(f"which {tool} 2>/dev/null", timeout=10)
            if not result.success or not result.stdout.strip():
                missing.append(tool)

        return len(missing) == 0, missing

    def detect_lab_framework(self) -> Tuple[str, str]:
        """
        Detect which lab framework is available (cached after first call).

        DynoLabs 5 variants:
        - Rust CLI: 'lab' binary (from classroom-api/rust)
        - Python grading: 'uv run lab' from grading directory

        Earlier versions:
        - Factory wrapper: 'lab' shell script
        - Legacy DynoLabs: Python 'lab' command

        Returns:
            Tuple of (framework_type, command_prefix)
            - ('dynolabs5-rust', 'lab') for Rust CLI (classroom-api)
            - ('dynolabs5-python', 'cd ~/grading && uv run lab') for Python grading
            - ('wrapper', 'lab') for Factory wrapper script
            - ('dynolabs', 'lab') for legacy DynoLabs
        """
        if self._framework_cache is not None:
            return self._framework_cache

        # Check for standard lab command first
        result = self.run("which lab 2>/dev/null", timeout=10)
        has_lab = result.success and result.stdout.strip()

        if has_lab:
            lab_path = result.stdout.strip()

            # Check if it's Rust CLI (DynoLabs 5)
            # Rust binaries are ELF executables, not scripts
            result = self.run(f"file {lab_path} 2>/dev/null", timeout=10)
            file_type = result.stdout.lower() if result.success else ""

            if 'elf' in file_type or 'executable' in file_type:
                # Could be Rust CLI - check for version with specific format
                result = self.run("lab --version 2>/dev/null", timeout=10)
                if result.success and 'lab' in result.stdout.lower():
                    # Rust CLI has features like autotest
                    result = self.run("lab --help 2>/dev/null | grep -q autotest && echo 'rust'", timeout=10)
                    if result.success and 'rust' in result.stdout:
                        self._framework_cache = ('dynolabs5-rust', 'lab')
                        return self._framework_cache

            if 'script' in file_type or 'text' in file_type:
                # Shell script - likely Factory wrapper
                self._framework_cache = ('wrapper', 'lab')
                return self._framework_cache

            # Default to legacy dynolabs for other executables
            self._framework_cache = ('dynolabs', 'lab')
            return self._framework_cache

        # Check for DynoLabs 5 Python grading (uv-based)
        result = self.run("which uv 2>/dev/null", timeout=10)
        has_uv = result.success and result.stdout.strip()

        result = self.run("test -f ~/grading/pyproject.toml && echo 'exists'", timeout=10)
        has_grading_pyproject = result.success and 'exists' in result.stdout

        if has_uv and has_grading_pyproject:
            self._framework_cache = ('dynolabs5-python', 'cd ~/grading && uv run lab')
            return self._framework_cache

        self._framework_cache = ('unknown', 'lab')
        return self._framework_cache

    def run_autotest(self, ignore_errors: bool = False, timeout: int = 1800) -> CommandResult:
        """
        Run DynoLabs 5 autotest command (Rust CLI feature).

        Executes randomized comprehensive lab validation.

        Args:
            ignore_errors: Continue testing even if some labs fail
            timeout: Timeout in seconds (default: 30 minutes)

        Returns:
            CommandResult
        """
        framework, _ = self.detect_lab_framework()

        if framework != 'dynolabs5-rust':
            return CommandResult(
                command="lab autotest",
                success=False,
                return_code=-1,
                stdout="",
                stderr=f"autotest requires DynoLabs 5 Rust CLI (detected: {framework})",
                duration_seconds=0
            )

        cmd = "lab autotest"
        if ignore_errors:
            cmd += " --ignore-errors"

        print(f"   Running: {cmd}")
        return self.run(cmd, timeout=timeout)

    def run_coursetest(self, scripts_file: str = "scripts.yml",
                       dry_run: bool = False, timeout: int = 3600) -> CommandResult:
        """
        Run DynoLabs 5 coursetest command (Rust CLI feature).

        Executes sequential course workflow testing.

        Args:
            scripts_file: Path to scripts.yml file
            dry_run: Show what would be run without executing
            timeout: Timeout in seconds (default: 60 minutes)

        Returns:
            CommandResult
        """
        framework, _ = self.detect_lab_framework()

        if framework != 'dynolabs5-rust':
            return CommandResult(
                command="lab coursetest",
                success=False,
                return_code=-1,
                stdout="",
                stderr=f"coursetest requires DynoLabs 5 Rust CLI (detected: {framework})",
                duration_seconds=0
            )

        cmd = f"lab coursetest {scripts_file}"
        if dry_run:
            cmd += " --dry-run"

        print(f"   Running: {cmd}")
        return self.run(cmd, timeout=timeout)

    def run(self, command: str, timeout: int = 30) -> CommandResult:
        """Execute command via SSH using the ControlMaster socket."""
        start_time = time.time()

        try:
            result = subprocess.run(
                ['ssh'] + self._ssh_opts() + [self.host, command],
                capture_output=True, text=True, timeout=timeout,
            )
            duration = time.time() - start_time

            return CommandResult(
                command=command,
                success=(result.returncode == 0),
                return_code=result.returncode,
                stdout=_strip_ansi(result.stdout),
                stderr=_strip_ansi(result.stderr),
                duration_seconds=duration,
            )

        except subprocess.TimeoutExpired:
            return CommandResult(
                command=command, success=False, return_code=-1,
                stdout="", stderr=f"Command timed out after {timeout}s",
                duration_seconds=timeout,
            )
        except Exception as e:
            return CommandResult(
                command=command, success=False, return_code=-1,
                stdout="", stderr=f"Execution error: {str(e)}",
                duration_seconds=time.time() - start_time,
            )

    def run_lab_command(self, action: str, exercise_name: str,
                        timeout: int = 300) -> CommandResult:
        """
        Run a lab command with automatic framework detection.

        Args:
            action: Lab action (start, finish, grade)
            exercise_name: Exercise name/slug
            timeout: Timeout in seconds

        Returns:
            CommandResult
        """
        framework, prefix = self.detect_lab_framework()

        # Strip -ge/-lab suffix only from end of name (not mid-word)
        lab_name = exercise_name.removesuffix('-ge').removesuffix('-lab')

        cmd = f"{prefix} {action} {lab_name}"
        print(f"   Running: {cmd} (framework: {framework})")

        result = self.run(cmd, timeout=timeout)

        # If lab start fails because another lab is running, the lab CLI
        # names the blocking lab in its output. Finish it and retry.
        if not result.success and action == 'start':
            output = result.stdout + result.stderr
            match = re.search(r'lab finish\s+(\S+)', output)
            if match:
                blocking_lab = match.group(1)
                print(f"   Finishing blocking lab: {blocking_lab}")
                self.run(f"{prefix} finish {blocking_lab}", timeout=120)
                print(f"   Retrying: {cmd}")
                result = self.run(cmd, timeout=timeout)

        # Check stdout for failure indicators (DynoLabs v4/v5 format).
        # For start/finish, any FAIL step means the operation failed.
        # For grade, FAIL steps are expected (grading check results).
        if result.success and action in ('start', 'finish'):
            if re.search(r'\bFAIL\b', result.stdout):
                result = CommandResult(
                    command=result.command,
                    success=False,
                    return_code=1,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    duration_seconds=result.duration_seconds,
                )

        return result

    def force_lesson(self, lesson_code: str, timeout: int = 120) -> CommandResult:
        """Run lab install to activate a lesson package.

        For multi-repo courses, each lesson must be installed before its
        exercises can be tested.
        """
        return self.run(f"lab install {lesson_code.lower()}", timeout=timeout)

    def run_interactive(self, command: str, prompts: List[Tuple[str, str]],
                        timeout: int = 120) -> CommandResult:
        """Execute an interactive command via SSH using pexpect.

        Args:
            command: Shell command to execute
            prompts: List of (prompt_pattern, response) tuples
            timeout: Command timeout in seconds
        """
        start_time = time.time()
        output_buffer = []

        try:
            ssh_cmd = (f"ssh -o ControlPath={self._control_path} "
                       f"-o ConnectTimeout=10 "
                       f"{self.host} {command}")
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

            return CommandResult(
                command=command,
                success=(exit_code == 0),
                return_code=exit_code,
                stdout="".join(output_buffer),
                stderr="",
                duration_seconds=duration,
            )

        except pexpect.TIMEOUT:
            return CommandResult(
                command=command, success=False, return_code=-1,
                stdout="".join(output_buffer),
                stderr=f"Interactive command timed out after {timeout}s",
                duration_seconds=timeout,
            )
        except pexpect.EOF:
            duration = time.time() - start_time
            return CommandResult(
                command=command, success=False, return_code=-1,
                stdout="".join(output_buffer),
                stderr="Command ended unexpectedly before all prompts were handled",
                duration_seconds=duration,
            )
        except Exception as e:
            return CommandResult(
                command=command, success=False, return_code=-1,
                stdout="".join(output_buffer),
                stderr=f"Interactive execution error: {str(e)}",
                duration_seconds=time.time() - start_time,
            )

    def test_connection(self) -> bool:
        """Test if SSH connection is working."""
        result = self.run("echo 'connection_test'", timeout=10)
        return result.success and "connection_test" in result.stdout

    def file_exists(self, path: str) -> bool:
        """Check if file exists on remote system."""
        result = self.run(f"test -f {path} && echo 'exists'")
        return result.success and "exists" in result.stdout

    def directory_exists(self, path: str) -> bool:
        """Check if directory exists on remote system."""
        result = self.run(f"test -d {path} && echo 'exists'")
        return result.success and "exists" in result.stdout

    def read_file(self, path: str) -> Optional[str]:
        """Read file contents from remote system."""
        result = self.run(f"cat {path}")
        return result.stdout if result.success else None

    def write_file(self, path: str, content: str, timeout: int = 30) -> CommandResult:
        """Write file content to remote system using base64 encoding."""
        import base64
        encoded = base64.b64encode(content.encode()).decode()
        cmd = f"mkdir -p \"$(dirname '{path}')\" && echo '{encoded}' | base64 -d > '{path}'"
        return self.run(cmd, timeout=timeout)

    def write_file_in_devcontainer(self, path: str, content: str,
                                    container_name: str = "qa-devcontainer",
                                    workdir: Optional[str] = None,
                                    user: Optional[str] = None,
                                    timeout: int = 30) -> CommandResult:
        """Write file content inside a dev container using base64 encoding."""
        import base64
        encoded = base64.b64encode(content.encode()).decode()
        cmd = f"mkdir -p \"$(dirname '{path}')\" && echo '{encoded}' | base64 -d > '{path}'"
        return self.run_in_devcontainer(cmd, container_name=container_name,
                                         workdir=workdir, user=user, timeout=timeout)

    def start_devcontainer(self, image: str, run_args: List[str],
                           project_dir: str,
                           container_name: str = "qa-devcontainer",
                           container_user: Optional[str] = None,
                           timeout: int = 120) -> CommandResult:
        """Start a dev container on the workstation.

        Replicates what VS Code does when opening a dev container:
        - Mounts the project directory
        - Mounts SSH keys so the container can reach managed hosts
        """
        # Stop any existing container with this name
        self.run(f"podman rm -f {container_name} 2>/dev/null", timeout=10)

        # Determine where to mount SSH keys inside the container.
        # VS Code mounts ~/.ssh into the container user's home.
        home_dir = "/home/student"
        if container_user == "root":
            container_ssh_dir = "/root/.ssh"
        else:
            container_ssh_dir = f"/home/{container_user or 'student'}/.ssh"

        # Build podman run command
        args_str = " ".join(run_args)
        cmd = (f"podman run -d --name {container_name} "
               f"{args_str} "
               f"-v {project_dir}:/workspaces/{project_dir.split('/')[-1]}:Z "
               f"-v {home_dir}/.ssh:{container_ssh_dir}:Z "
               f"{image} sleep infinity")

        result = self.run(cmd, timeout=timeout)
        if result.success:
            # Verify container is running
            check = self.run(
                f"podman exec {container_name} echo 'ready'", timeout=15)
            if check.success and 'ready' in check.stdout:
                return result

        return result

    def run_in_devcontainer(self, command: str,
                            container_name: str = "qa-devcontainer",
                            workdir: Optional[str] = None,
                            user: Optional[str] = None,
                            timeout: int = 120) -> CommandResult:
        """Run a command inside a dev container."""
        workdir_flag = f"-w {workdir}" if workdir else ""
        user_flag = f"--user {user}" if user else ""
        escaped_cmd = self._shell_quote(command)
        return self.run(
            f"podman exec {user_flag} {workdir_flag} {container_name} bash -c {escaped_cmd}",
            timeout=timeout,
        )

    def stop_devcontainer(self, container_name: str = "qa-devcontainer"):
        """Stop and remove the dev container."""
        self.run(f"podman rm -f {container_name} 2>/dev/null", timeout=15)

    def parse_devcontainer_json(self, exercise_dir: str) -> Optional[dict]:
        """Read and parse devcontainer.json from the exercise directory on the workstation.

        Checks both .devcontainer/podman/ and .devcontainer/ paths.

        Returns:
            Parsed JSON config dict, or None if not found.
        """
        for dc_path in [
            f"{exercise_dir}/.devcontainer/podman/devcontainer.json",
            f"{exercise_dir}/.devcontainer/devcontainer.json",
        ]:
            content = self.read_file(dc_path)
            if content:
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    continue
        return None

    def ensure_devcontainer(self, exercise_dir: str,
                            container_name: str = "qa-devcontainer") -> Optional[dict]:
        """Parse devcontainer.json and start the container if not running.

        Returns:
            Dict with 'workdir', 'user', 'image' on success, None on failure.
        """
        config = self.parse_devcontainer_json(exercise_dir)
        if not config:
            return None

        image = config.get("image", "")
        run_args = config.get("runArgs", [])
        container_user = config.get("containerUser")
        if not image:
            return None

        exercise_name = exercise_dir.rstrip('/').split('/')[-1]

        result = self.start_devcontainer(
            image=image, run_args=run_args,
            project_dir=exercise_dir,
            container_name=container_name,
            container_user=container_user,
        )

        if result.success:
            return {
                'workdir': f"/workspaces/{exercise_name}",
                'user': container_user,
                'image': image,
            }
        return None

    @staticmethod
    def _shell_quote(s: str) -> str:
        """Quote a string for safe shell use."""
        return "'" + s.replace("'", "'\\''") + "'"

    def close(self):
        """Close SSH ControlMaster connection."""
        self._cleanup_master()
        self._connected = False
