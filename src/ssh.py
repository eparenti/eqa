"""SSH client for remote command execution.

Uses system ssh with ControlMaster multiplexing for fast
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

    def __init__(self, host: str, username: str = "student"):
        self.host = host
        self.username = username
        self._connected = False

        # ControlMaster socket path
        self._control_dir = tempfile.mkdtemp(prefix="exercise-qa-ssh-")
        self._control_path = os.path.join(self._control_dir, f"{host}.sock")

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

    def connect(self) -> bool:
        """Establish SSH ControlMaster connection with retry."""
        for attempt in range(3):
            if self._start_master():
                result = subprocess.run(
                    ['ssh'] + self._ssh_opts() + [self.host, 'echo', 'connected'],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0 and 'connected' in result.stdout:
                    self._connected = True
                    # Verify lab command exists
                    lab_check = self.run("which lab 2>/dev/null", timeout=10)
                    if not lab_check.success or not lab_check.stdout.strip():
                        print("WARNING: 'lab' command not found on remote system")
                    return True

            if attempt < 2:
                delay = 2.0 * (2 ** attempt)
                print(f"Connection attempt {attempt + 1} failed, retrying in {delay}s...")
                time.sleep(delay)

        print(f"SSH connection failed after 3 attempts")
        return False

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
                stdout=result.stdout,
                stderr=result.stderr,
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
        """Run a lab command (start, grade, finish).

        Handles the case where another lab is in progress by finishing
        the blocking lab first, exactly as a student would.
        """
        import re

        result = self.run(f"lab {action} {exercise_name}", timeout=timeout)

        # The lab CLI returns rc=0 even when blocked by another lab.
        # It prints "another lab is in progress" and tells the user
        # to run "lab finish <blocking-lab>". Do what the student would do.
        if action == 'start' and 'another lab is in progress' in result.stdout:
            match = re.search(r'lab finish\s+(\S+)', result.stdout)
            if match:
                blocking_lab = match.group(1)
                # Strip ANSI codes from the matched lab name
                blocking_lab = re.sub(r'\x1b\[[0-9;]*m', '', blocking_lab)
                print(f"   Finishing blocking lab: {blocking_lab}")
                finish_result = self.run(f"lab finish {blocking_lab}", timeout=120)
                # If finish fails, reset the blocking lab's state
                if not finish_result.success or 'error' in finish_result.stderr.lower():
                    print(f"   Finish failed, resetting: {blocking_lab}")
                    self.run(f"lab status {blocking_lab} --reset", timeout=30)
                result = self.run(f"lab {action} {exercise_name}", timeout=timeout)

        # The lab CLI sometimes returns rc=0 even when the action failed.
        # Check stdout for failure indicators.
        if result.success and ('lab start failed' in result.stdout.lower()
                               or 'lab finish failed' in result.stdout.lower()
                               or 'lab grade failed' in result.stdout.lower()
                               or 'cannot continue lab script' in result.stdout.lower()):
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
        """Run lab force to install a lesson package.

        For multi-repo courses, each lesson must be forced before its
        exercises can be tested.
        """
        return self.run(f"lab force {lesson_code.lower()}", timeout=timeout)

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
            ssh_cmd = (f"ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "
                       f"{self.username}@{self.host} {command}")
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

    @staticmethod
    def _shell_quote(s: str) -> str:
        """Quote a string for safe shell use."""
        return "'" + s.replace("'", "'\\''") + "'"

    def close(self):
        """Close SSH ControlMaster connection."""
        self._cleanup_master()
        self._connected = False
