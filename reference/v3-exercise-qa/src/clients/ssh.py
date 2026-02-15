"""SSH client for remote command execution.

Uses system ssh command with ControlMaster multiplexing for fast
repeated connections through ProxyJump.
"""

import atexit
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pexpect


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

        # ControlMaster socket path
        self._control_dir = tempfile.mkdtemp(prefix="exercise-qa-ssh-")
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
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
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
                    capture_output=True,
                    timeout=5,
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
                    capture_output=True,
                    text=True,
                    timeout=10,
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

    def _verify_lab_tools(self) -> Tuple[bool, List[str]]:
        """
        Verify that essential lab tools are available on the remote system.

        Returns:
            Tuple of (all_present, list_of_missing_tools)
        """
        essential_tools = ['lab']
        optional_tools = ['oc', 'ansible-navigator', 'podman']

        missing = []

        for tool in essential_tools:
            result = self.run(f"which {tool} 2>/dev/null", timeout=10)
            if not result.success or not result.stdout.strip():
                missing.append(tool)

        # Check optional tools but don't require them
        available_optional = []
        for tool in optional_tools:
            result = self.run(f"which {tool} 2>/dev/null", timeout=10)
            if result.success and result.stdout.strip():
                available_optional.append(tool)

        return len(missing) == 0, missing

    def detect_lab_framework(self) -> Tuple[str, str]:
        """
        Detect which lab framework is available.

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
                        return ('dynolabs5-rust', 'lab')

            if 'script' in file_type or 'text' in file_type:
                # Shell script - likely Factory wrapper
                return ('wrapper', 'lab')

            # Default to legacy dynolabs for other executables
            return ('dynolabs', 'lab')

        # Check for DynoLabs 5 Python grading (uv-based)
        result = self.run("which uv 2>/dev/null", timeout=10)
        has_uv = result.success and result.stdout.strip()

        result = self.run("test -f ~/grading/pyproject.toml && echo 'exists'", timeout=10)
        has_grading_pyproject = result.success and 'exists' in result.stdout

        if has_uv and has_grading_pyproject:
            return ('dynolabs5-python', 'cd ~/grading && uv run lab')

        return ('unknown', 'lab')

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

        # Strip common suffixes from exercise name for lab command
        lab_name = exercise_name.replace('-ge', '').replace('-lab', '')

        cmd = f"{prefix} {action} {lab_name}"
        print(f"   Running: {cmd} (framework: {framework})")

        result = self.run(cmd, timeout=timeout)

        # If lab start fails because another lab is running, the lab CLI
        # names the blocking lab in its output. Finish it and retry.
        if not result.success and action == 'start':
            import re
            output = result.stdout + result.stderr
            match = re.search(r'lab finish\s+(\S+)', output)
            if match:
                blocking_lab = match.group(1)
                print(f"   Finishing blocking lab: {blocking_lab}")
                self.run(f"{prefix} finish {blocking_lab}", timeout=120)
                print(f"   Retrying: {cmd}")
                result = self.run(cmd, timeout=timeout)

        return result

    def test_connection(self) -> bool:
        """Test if SSH connection is working."""
        result = self.run("echo 'connection_test'", timeout=10)
        return result.success and "connection_test" in result.stdout

    def run(self, command: str, timeout: int = 30) -> CommandResult:
        """
        Execute command via SSH using the ControlMaster socket.

        Args:
            command: Shell command to execute
            timeout: Command timeout in seconds

        Returns:
            CommandResult with execution details
        """
        start_time = time.time()

        try:
            # Use system ssh with ControlMaster socket for instant reuse
            result = subprocess.run(
                ['ssh'] + self._ssh_opts() + [self.host, command],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            duration = time.time() - start_time

            return CommandResult(
                command=command,
                success=(result.returncode == 0),
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_seconds=duration
            )

        except subprocess.TimeoutExpired:
            return CommandResult(
                command=command,
                success=False,
                return_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                duration_seconds=timeout
            )
        except Exception as e:
            return CommandResult(
                command=command,
                success=False,
                return_code=-1,
                stdout="",
                stderr=f"Execution error: {str(e)}",
                duration_seconds=time.time() - start_time
            )

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

    def run_interactive(self, command: str, prompts: List[Tuple[str, str]],
                        timeout: int = 120) -> CommandResult:
        """
        Execute an interactive command via SSH using pexpect.

        Args:
            command: Shell command to execute
            prompts: List of (prompt_pattern, response) tuples
            timeout: Command timeout in seconds

        Returns:
            CommandResult with execution details
        """
        start_time = time.time()
        output_buffer = []

        try:
            # Spawn SSH with the command (include username)
            ssh_cmd = f"ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no {self.username}@{self.host} {command}"
            child = pexpect.spawn(ssh_cmd, timeout=timeout, encoding='utf-8')

            # Handle each prompt in order
            for prompt_pattern, response in prompts:
                child.expect(prompt_pattern)
                output_buffer.append(child.before or "")
                output_buffer.append(child.after or "")
                child.sendline(response)

            # Wait for command to complete and capture remaining output
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
                duration_seconds=duration
            )

        except pexpect.TIMEOUT:
            return CommandResult(
                command=command,
                success=False,
                return_code=-1,
                stdout="".join(output_buffer),
                stderr=f"Interactive command timed out after {timeout}s",
                duration_seconds=timeout
            )
        except pexpect.EOF:
            # Command ended before all prompts were handled
            duration = time.time() - start_time
            return CommandResult(
                command=command,
                success=False,
                return_code=-1,
                stdout="".join(output_buffer),
                stderr="Command ended unexpectedly before all prompts were handled",
                duration_seconds=duration
            )
        except Exception as e:
            return CommandResult(
                command=command,
                success=False,
                return_code=-1,
                stdout="".join(output_buffer),
                stderr=f"Interactive execution error: {str(e)}",
                duration_seconds=time.time() - start_time
            )

    # --- Dev Container Support ---

    def start_devcontainer(self, image: str, run_args: list,
                           project_dir: str, container_name: str = "qa-devcontainer",
                           timeout: int = 120) -> CommandResult:
        """
        Start a dev container on the workstation.

        Args:
            image: Container image (e.g., registry.../ansible-dev-tools-rhel8:latest)
            run_args: podman run arguments from devcontainer.json
            project_dir: Exercise project directory on workstation (e.g., /home/student/develop-inventory)
            container_name: Name for the container
            timeout: Timeout in seconds

        Returns:
            CommandResult
        """
        # Remove any existing container with the same name
        self.run(f"podman rm -f {container_name} 2>/dev/null", timeout=15)

        # Build podman run command
        # Mount the exercise project into the container workspace
        project_name = project_dir.rstrip('/').split('/')[-1]
        workspace_dir = f"/workspaces/{project_name}"

        args = [
            "podman", "run", "-d",
            "--name", container_name,
            "-v", f"{project_dir}:{workspace_dir}:Z",
            "-w", workspace_dir,
        ]

        # Add runArgs from devcontainer.json
        for arg in run_args:
            args.append(arg)

        args.extend([image, "sleep", "infinity"])

        cmd = " ".join(args)
        print(f"   Starting dev container: {container_name}")
        print(f"   Image: {image}")
        print(f"   Project: {project_dir} -> {workspace_dir}")

        result = self.run(cmd, timeout=timeout)
        if result.success:
            print(f"   ✓ Dev container started")
            return result

        # Image pull likely failed - try with a fallback image already on workstation
        print(f"   ⚠ Container start failed (image pull issue), trying fallback...")
        fallback_image = self._find_fallback_image()
        if fallback_image:
            print(f"   Using fallback image: {fallback_image}")
            # Rebuild command with fallback image
            args_fallback = [
                "podman", "run", "-d",
                "--name", container_name,
                "-v", f"{project_dir}:{workspace_dir}:Z",
                "-w", workspace_dir,
            ]
            for arg in run_args:
                if arg != "--tls-verify=false":
                    args_fallback.append(arg)
            args_fallback.extend([fallback_image, "sleep", "infinity"])
            cmd_fallback = " ".join(args_fallback)
            result = self.run(cmd_fallback, timeout=timeout)
            if result.success:
                print(f"   ✓ Dev container started (fallback image)")
                return result

        print(f"   ✗ Dev container failed: {(result.stderr or result.stdout)[:200]}")
        return result

    def _find_fallback_image(self) -> Optional[str]:
        """Find a compatible container image already on the workstation."""
        # Look for ansible dev tools or EE images already pulled
        result = self.run("podman images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null", timeout=10)
        if not result.success:
            return None

        # Priority order for fallback images
        fallback_preferences = [
            'ansible-dev-tools',
            'ee-supported',
            'ee-29',
            'ee-minimal',
        ]

        images = result.stdout.strip().split('\n')
        for pref in fallback_preferences:
            for img in images:
                if pref in img and '<none>' not in img:
                    return img.strip()

        return None

    def run_in_devcontainer(self, command: str, container_name: str = "qa-devcontainer",
                            workdir: Optional[str] = None,
                            timeout: int = 120) -> CommandResult:
        """
        Execute a command inside the dev container.

        Args:
            command: Shell command to execute
            container_name: Name of the running container
            workdir: Working directory override inside the container
            timeout: Timeout in seconds

        Returns:
            CommandResult
        """
        exec_cmd = f"podman exec"
        if workdir:
            exec_cmd += f" -w {workdir}"
        exec_cmd += f" {container_name} bash -c {self._shell_quote(command)}"

        return self.run(exec_cmd, timeout=timeout)

    def stop_devcontainer(self, container_name: str = "qa-devcontainer",
                          timeout: int = 30) -> CommandResult:
        """
        Stop and remove the dev container.

        Args:
            container_name: Name of the container to stop
            timeout: Timeout in seconds

        Returns:
            CommandResult
        """
        print(f"   Stopping dev container: {container_name}")
        result = self.run(f"podman rm -f {container_name}", timeout=timeout)
        if result.success:
            print(f"   ✓ Dev container removed")
        return result

    @staticmethod
    def _shell_quote(s: str) -> str:
        """Quote a string for safe shell use."""
        return "'" + s.replace("'", "'\\''") + "'"

    def close(self):
        """Close SSH ControlMaster connection."""
        self._cleanup_master()
        self._connected = False
