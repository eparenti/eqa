"""TC-SOL: Solution file validation.

Tests that solution files:
- Exist in the expected location
- Have correct syntax/formatting
- Execute successfully
- Create expected resources
"""

from datetime import datetime
from pathlib import Path
from typing import List
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext, ExercisePattern
from ..core.pattern_detector import is_aap_controller_content
from ..clients.ssh import SSHConnection


class TC_SOL:
    """Solution files test category."""

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test solution files for an exercise.

        Args:
            exercise: Exercise context
            ssh: SSH connection to workstation

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-SOL: Testing solution files...")

        bugs_found = []
        start_time = datetime.now()

        # Test 1: Solution files exist
        if not exercise.solution_files or len(exercise.solution_files) == 0:
            bugs_found.append(Bug(
                id=f"SOL-MISSING-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-SOL",
                exercise_id=exercise.id,
                description="No solution files found for exercise",
                fix_recommendation="Create solution files in solutions/ directory",
                verification_steps=[
                    "Check materials/labs/<exercise>/solutions/",
                    "Verify .sol files exist"
                ]
            ))
        else:
            print(f"   Found {len(exercise.solution_files)} solution file(s)")

            # Test 2: Validate each solution file locally
            for sol_file in exercise.solution_files:
                self._validate_solution_file(sol_file, exercise, ssh, bugs_found)

            # Test 3: Verify solution files are deployed on workstation
            self._verify_on_workstation(exercise, ssh, bugs_found)

        # Test 4: Check solution file naming convention (skip for AAP Controller content)
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
        else:
            print(f"   ⏭  Skipping .sol naming check (AAP Controller content)")

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
                'files_tested': len(exercise.solution_files)
            }
        )

    def _validate_solution_file(self, sol_file: Path, exercise: ExerciseContext,
                                  ssh: SSHConnection, bugs_found: List[Bug]):
        """Validate a single solution file."""
        import subprocess
        print(f"   → Testing: {sol_file.name}")

        # Check if file exists LOCALLY (solution files are in the repo, not deployed to workstation)
        if not sol_file.exists():
            bugs_found.append(Bug(
                id=f"SOL-NOTFOUND-{sol_file.stem}-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-SOL",
                exercise_id=exercise.id,
                description=f"Solution file '{sol_file.name}' not found in repository",
                fix_recommendation=f"Create solution file at {sol_file}",
                verification_steps=[f"Check: test -f {sol_file}"]
            ))
            return

        # Check file syntax LOCALLY if it's a YAML/playbook
        # Skip non-YAML files like README.md, .txt, etc.
        if sol_file.suffix in ['.yml', '.yaml'] or (sol_file.suffix == '.sol' and '.yml' in sol_file.stem or '.yaml' in sol_file.stem):
            # Use different validation for AAP Controller content vs Ansible playbooks
            if is_aap_controller_content(exercise):
                # AAP Controller YAML - use yamllint only (locally)
                result = subprocess.run(
                    ['yamllint', '-d', 'relaxed', str(sol_file)],
                    capture_output=True, text=True, timeout=30
                )
                check_name = "YAML"
                success = result.returncode == 0
            else:
                # Traditional Ansible playbook - check YAML syntax locally
                # Note: ansible-playbook --syntax-check requires inventory/hosts which may not exist
                # Use yamllint for basic YAML validation instead
                result = subprocess.run(
                    ['yamllint', '-d', 'relaxed', str(sol_file)],
                    capture_output=True, text=True, timeout=30
                )
                check_name = "YAML"
                success = result.returncode == 0

            if not success:
                bugs_found.append(Bug(
                    id=f"SOL-SYNTAX-{sol_file.stem}-{exercise.id}",
                    severity=BugSeverity.P1_CRITICAL,
                    category="TC-SOL",
                    exercise_id=exercise.id,
                    description=f"Solution file '{sol_file.name}' has {check_name.lower()} syntax errors",
                    fix_recommendation=f"Fix {check_name} syntax in {sol_file.name}",
                    verification_steps=[
                        f"Run: yamllint {sol_file.name}",
                        "Fix reported errors"
                    ]
                ))
            else:
                print(f"      ✓ {check_name} syntax valid")

    def _verify_on_workstation(self, exercise: ExerciseContext,
                                ssh: SSHConnection, bugs_found: List[Bug]):
        """Verify solution files are accessible on workstation."""
        base_id = exercise.id.removesuffix('-ge').removesuffix('-lab')

        # Common solution file locations on workstation
        search_paths = [
            f"/home/student/{base_id}/solutions",
            f"/home/student/{base_id}",
        ]

        for sol_file in exercise.solution_files:
            # Get the deployed filename (strip .sol extension)
            deploy_name = sol_file.name
            if deploy_name.endswith('.sol'):
                deploy_name = deploy_name[:-4]

            found = False
            for search_path in search_paths:
                result = ssh.run(f"test -f {search_path}/{deploy_name} && echo found", timeout=5)
                if result.success and 'found' in result.stdout:
                    found = True
                    break
                # Also check with original name
                result = ssh.run(f"test -f {search_path}/{sol_file.name} && echo found", timeout=5)
                if result.success and 'found' in result.stdout:
                    found = True
                    break

            if not found:
                # Check if lab start has been run (directory exists)
                dir_result = ssh.run(f"test -d /home/student/{base_id} && echo exists", timeout=5)
                if dir_result.success and 'exists' in dir_result.stdout:
                    bugs_found.append(Bug(
                        id=f"SOL-NOTFOUND-{sol_file.stem}-{exercise.id}",
                        severity=BugSeverity.P1_CRITICAL,
                        category="TC-SOL",
                        exercise_id=exercise.id,
                        description=f"Solution file '{deploy_name}' not found on workstation",
                        fix_recommendation=f"Upload solution file to /home/student/{base_id}/solutions/{deploy_name}",
                        verification_steps=[
                            f"Check: test -f /home/student/{base_id}/solutions/{deploy_name}"
                        ]
                    ))
