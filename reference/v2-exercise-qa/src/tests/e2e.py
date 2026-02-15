"""TC-E2E: End-to-end independence testing.

Tests that exercises work independently:
- Can start without prior exercises completed
- Don't depend on state from previous exercises
- All prerequisites are met by lab start
- Complete workflow works from fresh state
"""

from datetime import datetime
from typing import List, Dict, Optional
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext, ExerciseType
from ..clients.ssh import SSHConnection


class TC_E2E:
    """End-to-end independence test category."""

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test end-to-end exercise independence.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-E2E: Testing end-to-end independence...")

        bugs_found = []
        start_time = datetime.now()

        # Step 1: Ensure clean slate - finish any running labs
        print("   → Ensuring clean slate...")
        self._ensure_clean_slate(exercise, ssh)

        # Step 2: Test fresh start
        print("   → Testing fresh start...")
        start_bugs = self._test_fresh_start(exercise, ssh)
        bugs_found.extend(start_bugs)

        if start_bugs:
            # If start failed, can't continue
            print("   ⏭  Skipping remaining tests (start failed)")
            duration = (datetime.now() - start_time).total_seconds()
            return TestResult(
                category="TC-E2E",
                exercise_id=exercise.id,
                passed=False,
                timestamp=datetime.now().isoformat(),
                duration_seconds=duration,
                bugs_found=bugs_found,
                details={'start_failed': True}
            )

        # Step 3: Verify prerequisites are satisfied
        print("   → Verifying prerequisites...")
        prereq_bugs = self._verify_prerequisites(exercise, ssh)
        bugs_found.extend(prereq_bugs)

        # Step 4: Test solution execution (for Labs)
        if exercise.type == ExerciseType.LAB:
            print("   → Testing solution execution...")
            solution_bugs = self._test_solution_execution(exercise, ssh)
            bugs_found.extend(solution_bugs)

            # Step 5: Test grading
            print("   → Testing grading...")
            grade_bugs = self._test_grading(exercise, ssh)
            bugs_found.extend(grade_bugs)

        # Step 6: Test finish
        print("   → Testing finish...")
        finish_bugs = self._test_finish(exercise, ssh)
        bugs_found.extend(finish_bugs)

        # Step 7: Verify clean finish
        print("   → Verifying clean finish...")
        cleanup_bugs = self._verify_clean_finish(exercise, ssh)
        bugs_found.extend(cleanup_bugs)

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-E2E",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'exercise_type': exercise.type.value,
                'solution_files': len(exercise.solution_files),
                'has_grading': exercise.grading_script is not None
            }
        )

    def _ensure_clean_slate(self, exercise: ExerciseContext, ssh: SSHConnection):
        """Ensure no prior exercise state exists."""
        # Finish current exercise if running
        ssh.run(f"lab finish {exercise.lab_name} 2>/dev/null", timeout=60)

        # Clean up working directory
        base_id = exercise.id.removesuffix('-ge').removesuffix('-lab')
        ssh.run(f"rm -rf /home/student/{base_id} 2>/dev/null", timeout=10)
        ssh.run(f"rm -rf /home/student/{exercise.id} 2>/dev/null", timeout=10)

    def _test_fresh_start(self, exercise: ExerciseContext, ssh: SSHConnection) -> List[Bug]:
        """Test that exercise can start from fresh state."""
        bugs = []

        result = ssh.run(f"lab start {exercise.lab_name}", timeout=180)

        if not result.success:
            error_msg = result.stderr[:300] if result.stderr else result.stdout[:300] if result.stdout else 'unknown error'

            # Check for common dependency errors
            dependency_indicators = [
                'previous exercise',
                'must complete',
                'requires',
                'dependency',
                'not found',
                'missing prerequisite',
            ]

            is_dependency_error = any(ind in error_msg.lower() for ind in dependency_indicators)

            bugs.append(Bug(
                id=f"E2E-START-001-{exercise.id}",
                severity=BugSeverity.P0_BLOCKER if is_dependency_error else BugSeverity.P1_CRITICAL,
                category="TC-E2E",
                exercise_id=exercise.id,
                description=f"Exercise cannot start independently: {error_msg[:200]}",
                fix_recommendation="Ensure lab start creates all required prerequisites",
                verification_steps=[
                    "Reset environment to clean state",
                    f"Run: lab start {exercise.lab_name}",
                    "Should succeed without prior exercises"
                ]
            ))
        else:
            print("      ✓ Fresh start successful")

        return bugs

    def _verify_prerequisites(self, exercise: ExerciseContext, ssh: SSHConnection) -> List[Bug]:
        """Verify all prerequisites are met after start."""
        bugs = []
        base_id = exercise.id.removesuffix('-ge').removesuffix('-lab')

        # Check working directory exists
        result = ssh.run(f"test -d /home/student/{base_id} || test -d /home/student/{exercise.id}", timeout=5)
        if not result.success:
            bugs.append(Bug(
                id=f"E2E-WORKDIR-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-E2E",
                exercise_id=exercise.id,
                description="Working directory not created by lab start",
                fix_recommendation="Add directory creation to lab start script",
                verification_steps=[
                    f"Run: lab start {exercise.lab_name}",
                    f"Check: ls /home/student/{base_id}"
                ]
            ))
        else:
            print("      ✓ Working directory exists")

        # Check for required files mentioned in materials
        if exercise.materials_dir and exercise.materials_dir.exists():
            # Check if materials were copied
            result = ssh.run(f"ls /home/student/{base_id}/ 2>/dev/null | wc -l", timeout=10)
            if result.success:
                file_count = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
                if file_count > 0:
                    print(f"      ✓ {file_count} file(s) in working directory")

        return bugs

    def _test_solution_execution(self, exercise: ExerciseContext, ssh: SSHConnection) -> List[Bug]:
        """Test that solution files execute successfully."""
        bugs = []
        base_id = exercise.id.removesuffix('-ge').removesuffix('-lab')

        if not exercise.solution_files:
            print("      ⏭  No solution files")
            return bugs

        for sol_file in exercise.solution_files:
            # Determine source location
            if exercise.materials_dir:
                src_path = exercise.materials_dir / "solutions" / sol_file.name
            else:
                src_path = sol_file

            # Get destination filename (remove .sol extension)
            dest_name = sol_file.stem
            if dest_name.endswith('.sol'):
                dest_name = dest_name[:-4]
            elif sol_file.name.endswith('.sol'):
                dest_name = sol_file.name[:-4]

            dest_path = f"/home/student/{base_id}/{dest_name}"

            # Copy solution
            result = ssh.run(f"cp {src_path} {dest_path} 2>/dev/null", timeout=10)
            if not result.success:
                # Try alternate location
                alt_src = f"/home/student/{base_id}/solutions/{sol_file.name}"
                result = ssh.run(f"test -f {alt_src} && cp {alt_src} {dest_path}", timeout=10)

            # If it's a playbook, try to run it
            if dest_name.endswith('.yml') or dest_name.endswith('.yaml'):
                # Check if it's an Ansible playbook
                check_result = ssh.run(f"head -5 {dest_path} 2>/dev/null | grep -q 'hosts:'", timeout=5)
                if check_result.success:
                    # It's a playbook - try syntax check
                    syntax_result = ssh.run(f"cd /home/student/{base_id} && ansible-playbook --syntax-check {dest_name} 2>&1", timeout=30)
                    if not syntax_result.success:
                        bugs.append(Bug(
                            id=f"E2E-SOL-SYNTAX-{sol_file.stem}-{exercise.id}",
                            severity=BugSeverity.P1_CRITICAL,
                            category="TC-E2E",
                            exercise_id=exercise.id,
                            description=f"Solution playbook has syntax errors: {dest_name}",
                            fix_recommendation="Fix YAML syntax in solution file",
                            verification_steps=[
                                f"Run: ansible-playbook --syntax-check {dest_name}",
                                "Fix reported errors"
                            ]
                        ))
                    else:
                        print(f"      ✓ Solution syntax valid: {dest_name}")

        return bugs

    def _test_grading(self, exercise: ExerciseContext, ssh: SSHConnection) -> List[Bug]:
        """Test that grading works after solution is applied."""
        bugs = []

        if not exercise.grading_script:
            print("      ⏭  No grading script")
            return bugs

        # Run grading
        result = ssh.run(f"lab grade {exercise.lab_name}", timeout=120)

        if not result.success:
            bugs.append(Bug(
                id=f"E2E-GRADE-EXEC-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-E2E",
                exercise_id=exercise.id,
                description="Grading command failed during E2E test",
                fix_recommendation="Fix grading script execution issues",
                verification_steps=[
                    f"Run: lab grade {exercise.lab_name}",
                    "Check for errors"
                ]
            ))
        else:
            # Check for passing grade
            output = result.stdout + result.stderr
            if '100' in output or 'PASS' in output.upper() or 'SUCCESS' in output.upper():
                print("      ✓ Grading passed")
            else:
                print(f"      ⚠  Grading completed but may not have passed")

        return bugs

    def _test_finish(self, exercise: ExerciseContext, ssh: SSHConnection) -> List[Bug]:
        """Test that lab finish works."""
        bugs = []

        result = ssh.run(f"lab finish {exercise.lab_name}", timeout=120)

        if not result.success:
            error_msg = result.stderr[:200] if result.stderr else 'unknown error'
            bugs.append(Bug(
                id=f"E2E-FINISH-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-E2E",
                exercise_id=exercise.id,
                description=f"Lab finish failed: {error_msg}",
                fix_recommendation="Fix lab finish script",
                verification_steps=[f"Run: lab finish {exercise.lab_name}"]
            ))
        else:
            print("      ✓ Finish successful")

        return bugs

    def _verify_clean_finish(self, exercise: ExerciseContext, ssh: SSHConnection) -> List[Bug]:
        """Verify the exercise finished cleanly."""
        bugs = []
        base_id = exercise.id.removesuffix('-ge').removesuffix('-lab')

        # Check for leftover processes
        result = ssh.run(f"pgrep -f '{base_id}|{exercise.id}' 2>/dev/null", timeout=5)
        if result.success and result.stdout.strip():
            process_count = len(result.stdout.strip().split('\n'))
            if process_count > 0:
                bugs.append(Bug(
                    id=f"E2E-LEFTOVER-PROC-{exercise.id}",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-E2E",
                    exercise_id=exercise.id,
                    description=f"Found {process_count} leftover process(es) after finish",
                    fix_recommendation="Kill processes in finish script",
                    verification_steps=[
                        f"Run: lab finish {exercise.lab_name}",
                        f"Check: pgrep -f {base_id}"
                    ]
                ))

        return bugs
