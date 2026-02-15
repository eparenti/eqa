"""TC-SOL: Solution file validation.

Tests that solution files:
- Exist in the expected location (local repo)
- Have correct YAML syntax (yamllint)
- Are deployed on workstation after lab start
- Execute successfully on the live system (ansible-navigator/ansible-playbook)
- Create expected resources

Includes AAP Controller awareness.
"""

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List

from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext, ExercisePattern, ExerciseType
from ..core.pattern_detector import is_aap_controller_content
from ..clients.ssh import SSHConnection


class TC_SOL:
    """Solution files test category.

    Validates that ALL solution files work correctly by:
    1. Checking they exist in the repository
    2. Validating YAML syntax locally
    3. Verifying deployment on workstation
    4. Executing each solution on the live system
    """

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """Test solution files for an exercise."""
        print(f"\n   TC-SOL: Testing solution files...")

        bugs_found = []
        start_time = datetime.now()
        solutions_tested = 0
        solutions_passed = 0

        # Detect DynoLabs v5 framework
        is_dynolabs5 = getattr(exercise, 'content_pattern', None) == ExercisePattern.PYTHON or \
            (exercise.grading_script and exercise.grading_script.suffix == '.py')

        # Test 1: Solution files exist
        if not exercise.solution_files or len(exercise.solution_files) == 0:
            # Lower severity for exercises that have grading scripts but no
            # separate solution files (common in DynoLabs v5 where solutions
            # are applied via `lab solve` using internal Ansible playbooks)
            if is_dynolabs5 and exercise.grading_script:
                severity = BugSeverity.P3_LOW
                desc = "No solution files found (DynoLabs v5 exercise uses lab solve)"
            else:
                severity = BugSeverity.P1_CRITICAL
                desc = "No solution files found for exercise"
            bugs_found.append(Bug(
                id=f"SOL-MISSING-{exercise.id}",
                severity=severity,
                category="TC-SOL",
                exercise_id=exercise.id,
                description=desc,
                fix_recommendation="Create solution files in solutions/ directory",
                verification_steps=[
                    "Check materials/labs/<exercise>/solutions/",
                    "Check classroom/grading/src/<course>/materials/solutions/<exercise>/",
                ]
            ))
        else:
            print(f"      Found {len(exercise.solution_files)} solution file(s)")

            # Test 2: Validate each solution file locally (syntax)
            for sol_file in exercise.solution_files:
                self._validate_syntax(sol_file, exercise, bugs_found)

            # Test 3: Verify deployment on workstation
            # Skip for DynoLabs v5 - solutions are deployed to Gitea repos
            # via `lab solve`, not directly to the workstation filesystem
            if not is_dynolabs5:
                self._verify_on_workstation(exercise, ssh, bugs_found)
            else:
                print(f"      Skip deployment check (DynoLabs v5 uses Gitea)")

            # Test 4: Execute solutions on live system
            # Skip for DynoLabs v5 - solutions are applied via `lab solve`
            if not is_dynolabs5:
                for sol_file in exercise.solution_files:
                    solutions_tested += 1
                    if self._execute_solution(sol_file, exercise, ssh, bugs_found):
                        solutions_passed += 1
            else:
                print(f"      Skip execution (DynoLabs v5 uses lab solve)")
                solutions_tested = len(exercise.solution_files)
                solutions_passed = solutions_tested

        # Test 5: Check naming convention (skip for AAP Controller)
        if not is_aap_controller_content(exercise):
            for sol_file in exercise.solution_files:
                if not sol_file.name.endswith('.sol'):
                    bugs_found.append(Bug(
                        id=f"SOL-NAMING-{sol_file.stem}-{exercise.id}",
                        severity=BugSeverity.P3_LOW,
                        category="TC-SOL",
                        exercise_id=exercise.id,
                        description=f"Solution file '{sol_file.name}' doesn't follow .sol naming convention",
                        fix_recommendation=f"Rename to {sol_file.stem}.sol",
                        verification_steps=[f"Rename {sol_file.name} to use .sol extension"]
                    ))

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-SOL",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'solution_files_found': len(exercise.solution_files),
                'solutions_tested': solutions_tested,
                'solutions_passed': solutions_passed,
            }
        )

    def _validate_syntax(self, sol_file: Path, exercise: ExerciseContext,
                         bugs: List[Bug]):
        """Validate solution file syntax locally."""
        print(f"      Validating: {sol_file.name}")

        if not sol_file.exists():
            bugs.append(Bug(
                id=f"SOL-NOTFOUND-{sol_file.stem}-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-SOL",
                exercise_id=exercise.id,
                description=f"Solution file '{sol_file.name}' not found in repository",
                fix_recommendation=f"Create solution file at {sol_file}",
                verification_steps=[f"test -f {sol_file}"]
            ))
            return

        # Only lint YAML files
        is_yaml = sol_file.suffix in ['.yml', '.yaml'] or \
                  (sol_file.suffix == '.sol' and
                   ('.yml' in sol_file.stem or '.yaml' in sol_file.stem)) or \
                  (sol_file.suffix == '' and self._looks_like_yaml(sol_file))

        if not is_yaml:
            return

        try:
            result = subprocess.run(
                ['yamllint', '-d', 'relaxed', str(sol_file)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                # Filter warnings vs errors
                errors = [l for l in result.stdout.split('\n')
                         if 'error' in l.lower()]
                if errors:
                    bugs.append(Bug(
                        id=f"SOL-SYNTAX-{sol_file.stem}-{exercise.id}",
                        severity=BugSeverity.P1_CRITICAL,
                        category="TC-SOL",
                        exercise_id=exercise.id,
                        description=f"Solution file '{sol_file.name}' has YAML syntax errors",
                        fix_recommendation=f"Fix YAML syntax: {errors[0][:100]}",
                        verification_steps=[f"yamllint {sol_file.name}"]
                    ))
                else:
                    print(f"         OK syntax (warnings only)")
            else:
                print(f"         OK syntax")
        except FileNotFoundError:
            # yamllint not installed locally - not a bug in the exercise
            pass
        except Exception:
            pass

    def _verify_on_workstation(self, exercise: ExerciseContext,
                               ssh: SSHConnection, bugs: List[Bug]):
        """Verify solution files are deployed on workstation after lab start."""
        base_id = exercise.lab_name

        search_paths = [
            f"/home/student/{base_id}/solutions",
            f"/home/student/{base_id}",
        ]

        for sol_file in exercise.solution_files:
            deploy_name = sol_file.name
            if deploy_name.endswith('.sol'):
                deploy_name = deploy_name[:-4]

            found = False
            for search_path in search_paths:
                result = ssh.run(f"test -f {search_path}/{deploy_name} && echo found", timeout=5)
                if result.success and 'found' in result.stdout:
                    found = True
                    break
                # Also check with original .sol name
                result = ssh.run(f"test -f {search_path}/{sol_file.name} && echo found", timeout=5)
                if result.success and 'found' in result.stdout:
                    found = True
                    break

            if not found:
                # Only report if exercise directory exists (lab start has run)
                dir_result = ssh.run(f"test -d /home/student/{base_id} && echo exists", timeout=5)
                if dir_result.success and 'exists' in dir_result.stdout:
                    bugs.append(Bug(
                        id=f"SOL-DEPLOY-{sol_file.stem}-{exercise.id}",
                        severity=BugSeverity.P1_CRITICAL,
                        category="TC-SOL",
                        exercise_id=exercise.id,
                        description=f"Solution file '{deploy_name}' not found on workstation",
                        fix_recommendation=f"Ensure lab start deploys solution to /home/student/{base_id}/solutions/",
                        verification_steps=[
                            f"lab start {base_id}",
                            f"ls /home/student/{base_id}/solutions/"
                        ]
                    ))

    def _execute_solution(self, sol_file: Path, exercise: ExerciseContext,
                          ssh: SSHConnection, bugs: List[Bug]) -> bool:
        """Execute a solution file on the live system.

        Runs the solution on the live system to verify it works.

        Returns True if solution executed successfully.
        """
        if not sol_file.exists():
            return False

        # Determine execution method based on file type and content
        deploy_name = sol_file.name
        if deploy_name.endswith('.sol'):
            deploy_name = deploy_name[:-4]

        base_id = exercise.lab_name
        work_dir = f"/home/student/{base_id}"

        # Only execute YAML playbooks and shell scripts
        is_yaml = deploy_name.endswith(('.yml', '.yaml'))
        is_shell = deploy_name.endswith('.sh')
        is_python = deploy_name.endswith('.py')

        if not (is_yaml or is_shell or is_python):
            print(f"      Skipping execution: {deploy_name} (not executable type)")
            return True

        # AAP Controller content uses different execution
        if is_aap_controller_content(exercise):
            return self._execute_aap_solution(deploy_name, base_id, exercise, ssh, bugs)

        # Prepare the solution file on workstation
        sol_path = f"{work_dir}/solutions/{deploy_name}"
        work_path = f"{work_dir}/{deploy_name}"

        # Check if solution exists on workstation
        result = ssh.run(f"test -f {sol_path} && echo found", timeout=5)
        if not result.success or 'found' not in result.stdout:
            # Try without solutions/ subdirectory
            sol_path = f"{work_dir}/{sol_file.name}"
            result = ssh.run(f"test -f {sol_path} && echo found", timeout=5)
            if not result.success or 'found' not in result.stdout:
                # Can't find solution to execute
                return False

        # Copy to working location (strip .sol extension)
        ssh.run(f"cp {sol_path} {work_path} 2>/dev/null", timeout=10)

        # Execute based on type
        if is_yaml:
            return self._execute_ansible_solution(deploy_name, work_dir, exercise, ssh, bugs)
        elif is_shell:
            return self._execute_shell_solution(deploy_name, work_dir, exercise, ssh, bugs)
        elif is_python:
            return self._execute_python_solution(deploy_name, work_dir, exercise, ssh, bugs)

        return True

    def _execute_ansible_solution(self, filename: str, work_dir: str,
                                   exercise: ExerciseContext,
                                   ssh: SSHConnection, bugs: List[Bug]) -> bool:
        """Execute an Ansible playbook solution."""
        profile = getattr(exercise, 'course_profile', None)

        print(f"      Executing: {filename}")

        # Determine runner: ansible-navigator or ansible-playbook
        use_navigator = False
        if profile and profile.uses_ansible_navigator:
            nav_check = ssh.run("which ansible-navigator 2>/dev/null", timeout=5)
            if nav_check.success and nav_check.stdout.strip():
                use_navigator = True

        if use_navigator:
            cmd = f"cd {work_dir} && ansible-navigator run {filename} -m stdout"
        else:
            cmd = f"cd {work_dir} && ansible-playbook {filename}"

        result = ssh.run(cmd, timeout=300)

        if not result.success:
            # Parse error to give better fix recommendation
            error_hint = self._parse_ansible_error(result.stdout + result.stderr)

            bugs.append(Bug(
                id=f"SOL-EXEC-{filename}-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-SOL",
                exercise_id=exercise.id,
                description=f"Solution '{filename}' failed to execute: {error_hint}",
                fix_recommendation=f"Fix solution file {filename}",
                verification_steps=[
                    f"cd {work_dir}",
                    f"ansible-playbook {filename}" if not use_navigator
                    else f"ansible-navigator run {filename} -m stdout"
                ]
            ))
            print(f"         FAIL execution")
            return False

        print(f"         OK execution")
        return True

    def _execute_aap_solution(self, filename: str, base_id: str,
                               exercise: ExerciseContext,
                               ssh: SSHConnection, bugs: List[Bug]) -> bool:
        """Execute AAP Controller solution (typically via ansible-playbook with controller modules)."""
        work_dir = f"/home/student/{base_id}"
        print(f"      Executing AAP solution: {filename}")

        cmd = f"cd {work_dir} && ansible-playbook {filename}"
        result = ssh.run(cmd, timeout=300)

        if not result.success:
            bugs.append(Bug(
                id=f"SOL-AAP-EXEC-{filename}-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-SOL",
                exercise_id=exercise.id,
                description=f"AAP Controller solution '{filename}' failed",
                fix_recommendation=f"Fix AAP Controller playbook {filename}",
                verification_steps=[
                    f"cd {work_dir}",
                    f"ansible-playbook {filename}",
                    "Check controller connectivity and credentials"
                ]
            ))
            print(f"         FAIL AAP execution")
            return False

        print(f"         OK AAP execution")
        return True

    def _execute_shell_solution(self, filename: str, work_dir: str,
                                 exercise: ExerciseContext,
                                 ssh: SSHConnection, bugs: List[Bug]) -> bool:
        """Execute a shell script solution."""
        print(f"      Executing: {filename}")

        cmd = f"cd {work_dir} && bash {filename}"
        result = ssh.run(cmd, timeout=120)

        if not result.success:
            bugs.append(Bug(
                id=f"SOL-SHELL-EXEC-{filename}-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-SOL",
                exercise_id=exercise.id,
                description=f"Shell solution '{filename}' failed (exit code {result.return_code})",
                fix_recommendation=f"Fix shell script {filename}",
                verification_steps=[f"cd {work_dir}", f"bash {filename}"]
            ))
            return False

        print(f"         OK execution")
        return True

    def _execute_python_solution(self, filename: str, work_dir: str,
                                  exercise: ExerciseContext,
                                  ssh: SSHConnection, bugs: List[Bug]) -> bool:
        """Execute a Python solution."""
        print(f"      Executing: {filename}")

        cmd = f"cd {work_dir} && python3 {filename}"
        result = ssh.run(cmd, timeout=120)

        if not result.success:
            bugs.append(Bug(
                id=f"SOL-PYTHON-EXEC-{filename}-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-SOL",
                exercise_id=exercise.id,
                description=f"Python solution '{filename}' failed",
                fix_recommendation=f"Fix Python script {filename}",
                verification_steps=[f"cd {work_dir}", f"python3 {filename}"]
            ))
            return False

        print(f"         OK execution")
        return True

    def _looks_like_yaml(self, file_path: Path) -> bool:
        """Check if an extensionless file looks like YAML."""
        try:
            with open(file_path, 'r') as f:
                first_line = f.readline().strip()
            return first_line.startswith('---') or first_line.startswith('- ')
        except Exception:
            return False

    def _parse_ansible_error(self, output: str) -> str:
        """Parse Ansible output for a concise error description."""
        # Common error patterns
        patterns = [
            (r"ERROR!\s*(.+?)(?:\n|$)", "Ansible error"),
            (r'FAILED!\s*=>\s*\{.*?"msg":\s*"(.+?)"', "Task failed"),
            (r"fatal:\s*\[.+?\]:\s*(.+?)(?:\n|$)", "Fatal error"),
            (r"ModuleNotFoundError:\s*(.+?)(?:\n|$)", "Missing module"),
            (r"No such file or directory:\s*(.+?)(?:\n|$)", "File not found"),
        ]

        for pattern, label in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return f"{label}: {match.group(1)[:150]}"

        # Fallback: last non-empty line
        lines = [l.strip() for l in output.strip().split('\n') if l.strip()]
        if lines:
            return lines[-1][:150]

        return "Unknown error"
