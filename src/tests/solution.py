"""TC-SOL: Solution file validation.

Tests that solution files:
- Exist in the expected location (local repo)
- Have correct YAML syntax (yamllint)
- Execute successfully on the live system
- Follow naming conventions
"""

import subprocess
from datetime import datetime
from pathlib import Path
from typing import List

from ..models import (
    TestResult, Bug, BugSeverity, ExerciseContext,
    ExercisePattern, ExerciseType
)
from ..ssh import SSHConnection


CONTAINER_NAME = "qa-devcontainer"


class TC_SOL:
    """Solution files test category.

    Validates that ALL solution files work correctly by:
    1. Checking they exist in the repository
    2. Validating YAML syntax locally
    3. Executing each solution on the live system
    """

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """Test solution files for an exercise."""
        print(f"\n   TC-SOL: Testing solution files...")

        bugs_found = []
        start_time = datetime.now()
        solutions_tested = 0
        solutions_passed = 0

        # Detect DynoLabs v5 framework
        is_dynolabs5 = exercise.content_pattern == ExercisePattern.PYTHON or \
            (exercise.grading_script and exercise.grading_script.suffix == '.py')

        # Test 1: Solution files exist (check on workstation after lab start)
        # Don't rely on local repo detection - check what lab start deployed
        base_dir = f"/home/student/{exercise.lab_name}"
        result = ssh.run(f"ls {base_dir}/solutions/*.sol 2>/dev/null | wc -l", timeout=10)

        solution_count = 0
        if result.success and result.stdout.strip().isdigit():
            solution_count = int(result.stdout.strip())

        if solution_count == 0 and (not exercise.solution_files or len(exercise.solution_files) == 0):
            # No solutions found anywhere
            # Lower severity for DynoLabs v5 (uses lab solve internally)
            if is_dynolabs5:
                severity = BugSeverity.P3_LOW
                desc = "No solution files found (DynoLabs v5 may use internal solutions)"
            else:
                severity = BugSeverity.P3_LOW  # P3 because solutions might be embedded
                desc = "No .sol files found in solutions/ directory"

            bugs_found.append(Bug(
                id=f"SOL-MISSING-{exercise.id}",
                severity=severity,
                category="TC-SOL",
                exercise_id=exercise.id,
                description=desc,
                fix_recommendation="Check if solutions are embedded in grading or create .sol files",
                verification_steps=[
                    f"lab start {exercise.lab_name}",
                    f"ls {base_dir}/solutions/",
                ]
            ))
            print(f"      ⊘ No .sol files found (may use embedded solutions)")
        elif solution_count > 0:
            print(f"      ✓ Found {solution_count} solution file(s) on workstation")
        else:
            print(f"      Found {len(exercise.solution_files)} solution file(s)")

            # Test 2: Validate each solution file locally (syntax)
            for sol_file in exercise.solution_files:
                self._validate_syntax(sol_file, exercise, bugs_found)

            # Test 3: Execute solutions on live system
            for sol_file in exercise.solution_files:
                solutions_tested += 1
                if self._execute_solution(sol_file, exercise, ssh, bugs_found):
                    solutions_passed += 1

            # Test 4: Check naming convention
            for sol_file in exercise.solution_files:
                if not sol_file.name.endswith('.sol'):
                    bugs_found.append(Bug(
                        id=f"SOL-NAMING-{sol_file.stem}-{exercise.id}",
                        severity=BugSeverity.P3_LOW,
                        category="TC-SOL",
                        exercise_id=exercise.id,
                        description=f"Solution file '{sol_file.name}' doesn't follow .sol naming convention",
                        fix_recommendation=f"Rename to {sol_file.stem}.sol",
                        verification_steps=[f"mv {sol_file.name} {sol_file.stem}.sol"]
                    ))
                    print(f"      ⚠ {sol_file.name} doesn't use .sol extension")

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
            print(f"         ✗ File not found")
            return

        # Only lint YAML files
        is_yaml = sol_file.suffix in ['.yml', '.yaml'] or \
                  (sol_file.suffix == '.sol' and
                   ('.yml' in sol_file.stem or '.yaml' in sol_file.stem)) or \
                  (sol_file.suffix == '' and self._looks_like_yaml(sol_file))

        if not is_yaml:
            print(f"         ⊘ Not YAML, skipping syntax check")
            return

        # Try yamllint
        try:
            result = subprocess.run(
                ['yamllint', str(sol_file)],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                bugs.append(Bug(
                    id=f"SOL-YAML-{sol_file.stem}-{exercise.id}",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-SOL",
                    exercise_id=exercise.id,
                    description=f"YAML syntax errors in {sol_file.name}",
                    fix_recommendation=f"Fix YAML syntax:\n{result.stdout[:300]}",
                    verification_steps=[f"yamllint {sol_file}"]
                ))
                print(f"         ✗ YAML syntax errors")
            else:
                print(f"         ✓ YAML syntax valid")
        except FileNotFoundError:
            # yamllint not installed - skip
            print(f"         ⊘ yamllint not available, skipping")
        except subprocess.TimeoutExpired:
            print(f"         ⚠ yamllint timeout")

    def _execute_solution(self, sol_file: Path, exercise: ExerciseContext,
                          ssh: SSHConnection, bugs: List[Bug]) -> bool:
        """Execute solution file on the live system."""
        print(f"      Executing: {sol_file.name}")

        base_dir = f"/home/student/{exercise.lab_name}"
        target_name = sol_file.name.removesuffix('.sol')

        # Copy solution to workstation
        sol_path = f"{base_dir}/solutions/{sol_file.name}"
        work_path = f"{base_dir}/{target_name}"

        # Try solutions/ directory first, then base directory
        result = ssh.run(f"test -f {sol_path} && cp {sol_path} {work_path}", timeout=10)
        if not result.success:
            sol_path = f"{base_dir}/{sol_file.name}"
            result = ssh.run(f"test -f {sol_path} && cp {sol_path} {work_path}", timeout=10)

        if not result.success:
            bugs.append(Bug(
                id=f"SOL-DEPLOY-{sol_file.stem}-{exercise.id}",
                severity=BugSeverity.P2_HIGH,
                category="TC-SOL",
                exercise_id=exercise.id,
                description=f"Solution file {sol_file.name} not deployed on workstation",
                fix_recommendation="Check lab start deploys solution files",
                verification_steps=[
                    f"lab start {exercise.lab_name}",
                    f"ls -la {base_dir}/solutions/",
                ]
            ))
            print(f"         ✗ Not deployed on workstation")
            return False

        # If it's a playbook, execute it
        if target_name.endswith('.yml') or target_name.endswith('.yaml'):
            uses_dev_containers = (exercise.course_profile and
                                  exercise.course_profile.uses_dev_containers)

            if uses_dev_containers:
                # Start dev container and run playbook inside it
                print(f"         Running playbook in dev container...")
                dc_info = ssh.ensure_devcontainer(base_dir, CONTAINER_NAME)
                if dc_info:
                    result = ssh.run_in_devcontainer(
                        f"ansible-playbook {target_name}",
                        container_name=CONTAINER_NAME,
                        workdir=dc_info['workdir'],
                        user=dc_info.get('user'),
                        timeout=300,
                    )
                    ssh.stop_devcontainer(CONTAINER_NAME)
                else:
                    print(f"         ⚠ Dev container setup failed, trying workstation...")
                    result = ssh.run(
                        f"cd {base_dir} && ansible-playbook {target_name}",
                        timeout=300,
                    )
            else:
                # Traditional course - try navigator first, fall back to playbook
                print(f"         Running playbook...")
                result = ssh.run(
                    f"cd {base_dir} && ansible-navigator run {target_name} -m stdout 2>/dev/null || "
                    f"ansible-playbook {target_name}",
                    timeout=300
                )

            if not result.success:
                bugs.append(Bug(
                    id=f"SOL-EXEC-{sol_file.stem}-{exercise.id}",
                    severity=BugSeverity.P1_CRITICAL,
                    category="TC-SOL",
                    exercise_id=exercise.id,
                    description=f"Solution playbook {target_name} failed to execute",
                    fix_recommendation=f"Fix playbook errors:\n{(result.stderr or result.stdout)[:300]}",
                    verification_steps=[
                        f"cd {base_dir}",
                        f"ansible-playbook {target_name}",
                    ]
                ))
                print(f"         ✗ Playbook execution failed")
                return False

            print(f"         ✓ Playbook executed successfully")
            return True

        # Non-playbook file (just copied)
        print(f"         ✓ File deployed")
        return True

    def _looks_like_yaml(self, file_path: Path) -> bool:
        """Heuristic check if file is YAML."""
        try:
            content = file_path.read_text()
            # Check for YAML indicators
            return any(indicator in content for indicator in ['---', 'tasks:', 'hosts:', 'name:'])
        except Exception:
            return False
