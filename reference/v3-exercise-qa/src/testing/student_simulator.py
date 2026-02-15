"""
Student Simulator

Simulates a student following exercise instructions from the EPUB.
This is the primary test - if a student can't complete the exercise
by following the instructions, nothing else matters.

Design Philosophy:
- Simple and readable
- Fail fast with clear error messages
- Test exactly what students experience

Dev Container Support:
- Detects exercises that use VS Code dev containers
- Reads .devcontainer/podman/devcontainer.json for image and config
- Starts container on workstation, mounts exercise project
- Runs exercise commands inside the container via podman exec
- Cleans up container after exercise completes
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from enum import Enum

from ..epub.instruction_extractor import (
    InstructionExtractor,
    ExerciseInstructions,
    InstructionStep,
    Command
)
from ..clients.ssh import SSHConnection


class StepResult(Enum):
    """Result of executing a step."""
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    WARN = "warn"


@dataclass
class ExecutedStep:
    """Result of executing a single step."""
    number: str
    text: str
    result: StepResult
    command: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class SimulationResult:
    """Complete result of student simulation."""
    exercise_id: str
    success: bool
    phase: str  # "start", "instructions", "grade", "finish"
    steps_executed: List[ExecutedStep] = field(default_factory=list)
    steps_passed: int = 0
    steps_failed: int = 0
    total_duration_seconds: float = 0.0
    error_message: Optional[str] = None

    @property
    def summary(self) -> str:
        """Human-readable summary."""
        if self.success:
            return f"PASS: {self.steps_passed}/{len(self.steps_executed)} steps completed"
        else:
            return f"FAIL at {self.phase}: {self.error_message or 'See step details'}"


class StudentSimulator:
    """
    Simulates a student following exercise instructions.

    Usage:
        simulator = StudentSimulator(epub_path)
        result = simulator.run("install-config-ge")

        if result.success:
            print("Student can complete the exercise!")
        else:
            print(f"Failed: {result.summary}")
    """

    def __init__(self, epub_path: Path, workstation: str = "workstation",
                 timeout_lab: int = 300, timeout_command: int = 120,
                 lesson_path: Optional[Path] = None):
        """
        Initialize student simulator.

        Args:
            epub_path: Path to course EPUB
            workstation: SSH hostname for lab workstation
            timeout_lab: Timeout for lab start/finish commands (default: 300s)
            timeout_command: Timeout for individual commands (default: 120s)
            lesson_path: Path to lesson repo (for devcontainer detection)
        """
        self.epub_path = epub_path
        self.workstation = workstation
        self.ssh: Optional[SSHConnection] = None
        self.verbose = True
        self.timeout_lab = timeout_lab
        self.timeout_command = timeout_command
        self.lesson_path = lesson_path

        # Dev container state
        self._devcontainer_active = False
        self._devcontainer_name = "qa-devcontainer"
        self._devcontainer_workdir: Optional[str] = None

    def run(self, exercise_id: str) -> SimulationResult:
        """
        Simulate student completing an exercise.

        Args:
            exercise_id: Exercise ID (e.g., "install-config-ge")

        Returns:
            SimulationResult with pass/fail and details
        """
        start_time = datetime.now()

        self._log(f"\n{'='*60}")
        self._log(f"STUDENT SIMULATION: {exercise_id}")
        self._log(f"{'='*60}")

        # Step 1: Extract instructions from EPUB
        self._log("\n1. Extracting instructions from EPUB...")
        extractor = InstructionExtractor(self.epub_path)
        try:
            instructions = extractor.extract(exercise_id)
        finally:
            extractor.cleanup()

        if not instructions:
            return SimulationResult(
                exercise_id=exercise_id,
                success=False,
                phase="extract",
                error_message=f"Could not find exercise '{exercise_id}' in EPUB"
            )

        self._log(f"   Found {len(instructions.steps)} instruction steps")
        self._log(f"   Total commands: {instructions.total_commands}")

        # Step 2: Connect to workstation
        self._log("\n2. Connecting to workstation...")
        self.ssh = SSHConnection(self.workstation, username="student")
        if not self.ssh.connect():
            return SimulationResult(
                exercise_id=exercise_id,
                success=False,
                phase="connect",
                error_message=f"Cannot connect to {self.workstation}"
            )
        self._log("   Connected")

        # Step 3: Run lab start
        lab_name = exercise_id.replace("-ge", "").replace("-lab", "")
        start_cmd = instructions.prerequisites_command or f"lab start {lab_name}"
        self._log(f"\n3. Starting lab: {start_cmd}")
        start_result = self._run_lab_start(exercise_id, instructions)
        if not start_result.success:
            return start_result

        # Step 3.5: Detect and start dev container if exercise uses one
        dc_config = self._detect_devcontainer(exercise_id)
        if dc_config:
            self._log(f"\n3.5. Setting up dev container...")
            if self._start_devcontainer(exercise_id, dc_config):
                self._log(f"   ✓ Commands will run inside dev container")
            else:
                self._log(f"   ⚠ Dev container setup failed, running commands directly")

        # Step 4: Execute instructions
        self._log(f"\n4. Following instructions ({len(instructions.steps)} steps)...")
        instruction_result = self._execute_instructions(exercise_id, instructions)
        if not instruction_result.success:
            # Clean up: stop dev container and run lab finish
            self._stop_devcontainer()
            self._run_lab_finish(exercise_id)
            return instruction_result

        # Step 5: For Labs, run grading (runs on workstation, not in container)
        is_lab = exercise_id.endswith("-lab")
        if is_lab:
            self._log("\n5. Running grading...")
            # Stop dev container before grading (grading runs on workstation)
            self._stop_devcontainer()
            grade_result = self._run_grading(exercise_id)
            if not grade_result.success:
                self._run_lab_finish(exercise_id)
                return grade_result

        # Step 6: Run lab finish
        self._stop_devcontainer()  # Ensure container is stopped
        step_num = 6 if is_lab else 5
        self._log(f"\n{step_num}. Finishing lab...")
        finish_result = self._run_lab_finish(exercise_id)

        # Calculate totals
        duration = (datetime.now() - start_time).total_seconds()
        all_steps = instruction_result.steps_executed

        return SimulationResult(
            exercise_id=exercise_id,
            success=True,
            phase="complete",
            steps_executed=all_steps,
            steps_passed=sum(1 for s in all_steps if s.result == StepResult.PASS),
            steps_failed=sum(1 for s in all_steps if s.result == StepResult.FAIL),
            total_duration_seconds=duration
        )

    def _detect_devcontainer(self, exercise_id: str) -> Optional[dict]:
        """
        Detect if an exercise uses a dev container.

        Checks for .devcontainer/podman/devcontainer.json in exercise materials.

        Args:
            exercise_id: Exercise ID

        Returns:
            Parsed devcontainer.json dict, or None if not found
        """
        if not self.lesson_path:
            return None

        # Strip -ge/-lab suffix for directory lookup
        base_id = exercise_id.removesuffix('-ge').removesuffix('-lab')
        base_id_underscore = base_id.replace('-', '_')
        lesson_lower = self.lesson_path.name.lower()

        # Search for devcontainer.json in exercise materials
        search_paths = []
        for eid in [base_id, base_id_underscore]:
            search_paths.extend([
                self.lesson_path / "classroom" / "grading" / "src" / lesson_lower / "materials" / "labs" / eid / ".devcontainer" / "podman" / "devcontainer.json",
                self.lesson_path / "classroom" / "grading" / "src" / lesson_lower / "materials" / "labs" / eid / ".devcontainer" / "devcontainer.json",
                self.lesson_path / "materials" / "labs" / eid / ".devcontainer" / "podman" / "devcontainer.json",
            ])

        for dc_path in search_paths:
            if dc_path.exists():
                try:
                    with open(dc_path) as f:
                        config = json.load(f)
                    self._log(f"   Found devcontainer config: {dc_path.relative_to(self.lesson_path)}")
                    return config
                except (json.JSONDecodeError, OSError) as e:
                    self._log(f"   Warning: Could not parse {dc_path}: {e}")

        return None

    def _start_devcontainer(self, exercise_id: str, config: dict) -> bool:
        """
        Start the dev container on the workstation.

        Args:
            exercise_id: Exercise ID
            config: Parsed devcontainer.json

        Returns:
            True if container started successfully
        """
        image = config.get("image", "")
        run_args = config.get("runArgs", [])

        if not image:
            self._log("   Warning: No image specified in devcontainer.json")
            return False

        # The exercise project directory on the workstation
        base_id = exercise_id.removesuffix('-ge').removesuffix('-lab')
        project_dir = f"/home/student/{base_id}"

        # Verify the project directory exists on workstation
        check = self.ssh.run(f"test -d {project_dir} && echo 'exists'", timeout=10)
        if not check.success or 'exists' not in check.stdout:
            self._log(f"   Warning: Project directory {project_dir} not found on workstation")
            return False

        # Start the container
        result = self.ssh.start_devcontainer(
            image=image,
            run_args=run_args,
            project_dir=project_dir,
            container_name=self._devcontainer_name
        )

        if result.success:
            self._devcontainer_active = True
            project_name = base_id
            self._devcontainer_workdir = f"/workspaces/{project_name}"
            return True

        return False

    def _stop_devcontainer(self):
        """Stop and remove the dev container."""
        if self._devcontainer_active:
            self.ssh.stop_devcontainer(self._devcontainer_name)
            self._devcontainer_active = False

    def _run_command(self, command: str, timeout: int = 120) -> 'CommandResult':
        """
        Run a command, routing through dev container if active.

        Args:
            command: Shell command to execute
            timeout: Timeout in seconds

        Returns:
            CommandResult
        """
        if self._devcontainer_active:
            return self.ssh.run_in_devcontainer(
                command,
                container_name=self._devcontainer_name,
                timeout=timeout
            )
        else:
            return self.ssh.run(command, timeout=timeout)

    def _run_lab_start(self, exercise_id: str, instructions: ExerciseInstructions) -> SimulationResult:
        """Run lab start command.

        The lab CLI handles package installation and conflict resolution
        automatically. We pipe 'yes' via run_lab_command so its interactive
        prompts are answered non-interactively.
        """
        if instructions.prerequisites_command:
            result = self.ssh.run(instructions.prerequisites_command, timeout=self.timeout_lab)
        else:
            result = self.ssh.run_lab_command("start", exercise_id, timeout=self.timeout_lab)

        if not result.success:
            return SimulationResult(
                exercise_id=exercise_id,
                success=False,
                phase="start",
                error_message=f"lab start failed: {result.stderr or result.stdout}"
            )

        self._log("   Lab started successfully")
        return SimulationResult(exercise_id=exercise_id, success=True, phase="start")

    def _execute_instructions(self, exercise_id: str, instructions: ExerciseInstructions) -> SimulationResult:
        """Execute all instruction steps."""
        executed_steps = []
        # Track current working directory across commands (each SSH is a new shell)
        current_dir = None

        def execute_step(step: InstructionStep, depth: int = 0) -> bool:
            """Execute a step and its sub-steps. Returns True if all passed."""
            nonlocal current_dir
            indent = "   " + ("  " * depth)

            self._log(f"{indent}Step {step.number}: {step.text[:60]}...")

            # Execute commands in this step
            for cmd in step.commands:
                step_start = datetime.now()

                # First, translate for dev container if active (e.g., ansible-navigator -> ansible-playbook)
                translated_cmd = self._translate_for_devcontainer(cmd.text)

                # Then check for TTY-requiring commands (watch, top, less, etc.)
                actual_cmd, conversion_reason = self._convert_interactive_command(translated_cmd)

                if actual_cmd is None:
                    # Command cannot be automated - skip with warning
                    self._log(f"{indent}  [skip] {conversion_reason}: {cmd.text[:40]}...")
                    executed_steps.append(ExecutedStep(
                        number=step.number,
                        text=step.text,
                        result=StepResult.SKIP,
                        command=cmd.text
                    ))
                    continue

                if conversion_reason:
                    self._log(f"{indent}  $ {actual_cmd[:50]}... ({conversion_reason})")
                elif cmd.is_interactive and cmd.prompts:
                    # Handle authentication prompts
                    converted_cmd = self._convert_to_non_interactive(cmd)
                    if converted_cmd:
                        self._log(f"{indent}  $ {converted_cmd[:50]}... (auto-auth)")
                        actual_cmd = converted_cmd
                    else:
                        # Cannot convert - skip with warning
                        self._log(f"{indent}  [skip] Interactive command cannot be automated: {cmd.text[:40]}...")
                        executed_steps.append(ExecutedStep(
                            number=step.number,
                            text=step.text,
                            result=StepResult.SKIP,
                            command=cmd.text
                        ))
                        continue
                else:
                    self._log(f"{indent}  $ {cmd.text[:50]}...")

                # Handle cd commands - track directory for subsequent commands
                import re
                # Determine home directory based on execution context
                home_dir = self._devcontainer_workdir if self._devcontainer_active else "/home/student"

                cd_match = re.match(r'^cd\s+(.+)$', actual_cmd.strip())
                if cd_match:
                    new_dir = cd_match.group(1).strip()
                    # Expand ~ to appropriate home
                    new_dir = new_dir.replace('~', home_dir)
                    # Handle relative paths
                    if not new_dir.startswith('/'):
                        if current_dir:
                            new_dir = f"{current_dir}/{new_dir}"
                        else:
                            new_dir = f"{home_dir}/{new_dir}"
                    current_dir = new_dir
                    # Run the cd to verify it works
                    actual_cmd = f"cd {current_dir} && pwd"
                elif current_dir:
                    # Prepend cd to current directory for all other commands
                    actual_cmd = f"cd {current_dir} && {actual_cmd}"

                result = self._run_command(actual_cmd, timeout=self.timeout_command)
                duration = (datetime.now() - step_start).total_seconds()

                if result.success:
                    self._log(f"{indent}  ✓ OK ({duration:.1f}s)")
                    executed_steps.append(ExecutedStep(
                        number=step.number,
                        text=step.text,
                        result=StepResult.PASS,
                        command=cmd.text,
                        output=result.stdout[:500] if result.stdout else None,
                        duration_seconds=duration
                    ))
                else:
                    self._log(f"{indent}  ✗ FAILED")
                    self._log(f"{indent}    Error: {(result.stderr or result.stdout or 'unknown')[:100]}")
                    executed_steps.append(ExecutedStep(
                        number=step.number,
                        text=step.text,
                        result=StepResult.FAIL,
                        command=cmd.text,
                        error=result.stderr or result.stdout,
                        duration_seconds=duration
                    ))
                    return False

            # Execute sub-steps
            for sub_step in step.sub_steps:
                if not execute_step(sub_step, depth + 1):
                    return False

            return True

        # Execute all top-level steps
        all_passed = True
        for step in instructions.steps:
            if not execute_step(step):
                all_passed = False
                break

        passed_count = sum(1 for s in executed_steps if s.result == StepResult.PASS)
        failed_count = sum(1 for s in executed_steps if s.result == StepResult.FAIL)

        self._log(f"\n   Results: {passed_count} passed, {failed_count} failed")

        return SimulationResult(
            exercise_id=exercise_id,
            success=all_passed,
            phase="instructions",
            steps_executed=executed_steps,
            steps_passed=passed_count,
            steps_failed=failed_count,
            error_message=None if all_passed else "Instruction step failed"
        )

    def _translate_for_devcontainer(self, cmd_text: str) -> str:
        """
        Translate commands for dev container execution.

        When running inside an EE container, ansible-navigator commands
        need to be converted to direct ansible commands, since
        ansible-navigator is a wrapper that runs commands inside EE
        containers - and we're already inside one.

        Args:
            cmd_text: Original command

        Returns:
            Translated command
        """
        import re

        if not self._devcontainer_active:
            return cmd_text

        cmd = cmd_text.strip()

        # ansible-navigator run -> ansible-playbook
        match = re.match(r'^ansible-navigator\s+run\s+(.+)', cmd)
        if match:
            rest = match.group(1)
            # Strip ansible-navigator specific flags
            rest = re.sub(r'--mode\s+\S+', '', rest)
            rest = re.sub(r'-m\s+\S+', '', rest)
            rest = re.sub(r'--eei\s+\S+', '', rest)
            rest = re.sub(r'--ee\s+\S+', '', rest)
            rest = re.sub(r'--pull-policy\s+\S+', '', rest)
            return f"ansible-playbook {rest.strip()}"

        # ansible-navigator inventory -> ansible-inventory
        match = re.match(r'^ansible-navigator\s+inventory\s+(.+)', cmd)
        if match:
            rest = match.group(1)
            rest = re.sub(r'--mode\s+\S+', '', rest)
            rest = re.sub(r'-m\s+\S+', '', rest)
            rest = re.sub(r'--eei\s+\S+', '', rest)
            rest = re.sub(r'--ee\s+\S+', '', rest)
            return f"ansible-inventory {rest.strip()}"

        # ansible-navigator doc -> ansible-doc
        match = re.match(r'^ansible-navigator\s+doc\s+(.+)', cmd)
        if match:
            return f"ansible-doc {match.group(1).strip()}"

        # ansible-navigator config -> ansible-config
        match = re.match(r'^ansible-navigator\s+config\s*(.*)', cmd)
        if match:
            return f"ansible-config {match.group(1).strip()}"

        # Generic ansible-navigator -> try ansible directly
        if cmd.startswith('ansible-navigator '):
            subcmd = cmd[len('ansible-navigator '):]
            return f"ansible {subcmd}"

        return cmd_text

    def _convert_interactive_command(self, cmd_text: str) -> Tuple[Optional[str], str]:
        """
        Convert interactive/TTY-requiring commands to non-interactive form.

        Args:
            cmd_text: The command string

        Returns:
            Tuple of (converted_command, reason)
            - If converted_command is not None, use it instead
            - If converted_command is None, the command should be skipped
            - reason explains what was done
        """
        import re

        cmd_stripped = cmd_text.strip()

        # Handle 'watch' command - run the underlying command once
        if cmd_stripped.startswith('watch '):
            # Extract the command after 'watch' and any flags
            # watch [-n seconds] [-d] command
            match = re.match(r'watch\s+(?:-[nd]\s+\d*\s*)*(.+)$', cmd_stripped)
            if match:
                underlying_cmd = match.group(1).strip()
                return underlying_cmd, "converted 'watch' to single execution"
            # Simple case: watch command
            underlying_cmd = cmd_stripped[6:].strip()
            return underlying_cmd, "converted 'watch' to single execution"

        # Handle 'top' - run once with batch mode
        if cmd_stripped == 'top' or cmd_stripped.startswith('top '):
            return "top -b -n 1 | head -20", "converted 'top' to batch mode"

        # Handle 'htop' - skip (no good batch mode)
        if cmd_stripped == 'htop' or cmd_stripped.startswith('htop '):
            return None, "skipped 'htop' (requires TTY)"

        # Handle 'less', 'more' - convert to cat
        if cmd_stripped.startswith('less ') or cmd_stripped.startswith('more '):
            file_arg = cmd_stripped.split(None, 1)[1] if ' ' in cmd_stripped else ''
            if file_arg:
                return f"cat {file_arg}", "converted pager to 'cat'"
            return None, "skipped pager (no file argument)"

        # Handle 'vim', 'vi', 'nano' - skip (editors)
        for editor in ['vim ', 'vi ', 'nano ', 'emacs ']:
            if cmd_stripped.startswith(editor) or cmd_stripped == editor.strip():
                return None, f"skipped '{editor.strip()}' (editor requires TTY)"

        # Handle 'ssh' without command (interactive session)
        if re.match(r'^ssh\s+\S+$', cmd_stripped):
            return None, "skipped interactive SSH session"

        # Handle 'tail -f' - run without -f and limit output
        if ' -f ' in cmd_stripped or cmd_stripped.endswith(' -f'):
            converted = cmd_stripped.replace(' -f ', ' ').replace(' -f', '')
            return f"{converted} | head -50", "converted 'tail -f' to single read"

        # No conversion needed
        return cmd_text, ""

    def _convert_to_non_interactive(self, cmd: 'Command') -> Optional[str]:
        """
        Convert interactive commands to non-interactive form.

        Returns the converted command string, or None if conversion not possible.
        """
        import re

        # Extract username and password from prompts
        username = None
        password = None
        for prompt, response in cmd.prompts:
            if 'username' in prompt.lower():
                username = response
            elif 'password' in prompt.lower():
                password = response

        # podman login: add --username and --password flags
        if cmd.text.startswith('podman login') and username and password:
            # Extract the registry URL
            match = re.match(r'podman login\s+(\S+)', cmd.text)
            if match:
                registry = match.group(1)
                return f"podman login {registry} --username {username} --password {password}"

        # docker login: same pattern
        if cmd.text.startswith('docker login') and username and password:
            match = re.match(r'docker login\s+(\S+)', cmd.text)
            if match:
                registry = match.group(1)
                return f"docker login {registry} --username {username} --password {password}"

        # git credential prompts - could use GIT_ASKPASS or credential helper
        # For now, return None to skip

        # ssh with password - would need sshpass, skip for now

        return None  # Cannot convert

    def _run_grading(self, exercise_id: str) -> SimulationResult:
        """Run lab grade command with DynoLabs v5 support."""
        result = self.ssh.run_lab_command("grade", exercise_id, timeout=self.timeout_lab)

        # Primary check: exit code (most reliable indicator)
        # Exit code 0 = pass, non-zero = fail
        if result.success and result.return_code == 0:
            self._log("   Grading passed (exit code 0)")
            return SimulationResult(exercise_id=exercise_id, success=True, phase="grade")

        # Secondary check: look for explicit failure indicators in output
        output = (result.stdout or "") + (result.stderr or "")
        failure_indicators = ["FAIL", "failed", "error", "Error"]
        has_failure = any(ind.lower() in output.lower() for ind in failure_indicators)

        if has_failure or result.return_code != 0:
            return SimulationResult(
                exercise_id=exercise_id,
                success=False,
                phase="grade",
                error_message=f"Grading failed (exit code {result.return_code}). Output: {output[:200]}"
            )

        # If we get here, exit code was 0 but we're being extra cautious
        self._log("   Grading passed")
        return SimulationResult(exercise_id=exercise_id, success=True, phase="grade")

    def _run_lab_finish(self, exercise_id: str) -> SimulationResult:
        """Run lab finish command with DynoLabs v5 support."""
        result = self.ssh.run_lab_command("finish", exercise_id, timeout=self.timeout_lab)

        if not result.success:
            self._log(f"   Warning: lab finish returned non-zero exit code")
            # Don't fail the whole simulation for finish issues
            return SimulationResult(
                exercise_id=exercise_id,
                success=True,  # Still consider success
                phase="finish",
                error_message=f"lab finish had issues: {result.stderr or result.stdout}"
            )

        self._log("   Lab finished")
        return SimulationResult(exercise_id=exercise_id, success=True, phase="finish")

    def _log(self, message: str):
        """Log message if verbose mode."""
        if self.verbose:
            print(message)


def simulate_student(epub_path: Path, exercise_id: str, workstation: str = "workstation") -> SimulationResult:
    """
    Convenience function to run student simulation.

    Args:
        epub_path: Path to EPUB file
        exercise_id: Exercise ID
        workstation: SSH hostname

    Returns:
        SimulationResult
    """
    simulator = StudentSimulator(epub_path, workstation)
    return simulator.run(exercise_id)
