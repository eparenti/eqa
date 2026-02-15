"""TC-GRADE: Grading validation.

Tests that grading scripts:
- Grade correctly WITH solution applied (100/100)
- Grade correctly WITHOUT solution applied (0/100)
- Provide clear error messages
- Don't have false positives or negatives
"""

from datetime import datetime
from pathlib import Path
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext, ExerciseType
from ..clients.ssh import SSHConnection


class TC_GRADE:
    """Grading validation test category."""

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test grading script for a Lab exercise.

        Args:
            exercise: Exercise context
            ssh: SSH connection to workstation

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-GRADE: Testing grading...")

        bugs_found = []
        start_time = datetime.now()

        # Only test Labs (GEs don't have grading)
        if exercise.type != ExerciseType.LAB:
            print("   ⏭  Skipping (not a Lab)")
            return TestResult(
                category="TC-GRADE",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=0.0,
                details={'skipped': True, 'reason': 'Not a Lab exercise'}
            )

        # Check if grading script exists
        if not exercise.grading_script or not exercise.grading_script.exists():
            bugs_found.append(Bug(
                id=f"GRADE-MISSING-001-{exercise.id}",
                severity=BugSeverity.P0_BLOCKER,
                category="TC-GRADE",
                exercise_id=exercise.id,
                description="Grading script not found for Lab exercise",
                fix_recommendation=f"Create grading script for {exercise.id}",
                verification_steps=[
                    "Create Python grading module",
                    "Implement grade() function",
                    "Test with lab grade command"
                ]
            ))
            duration = (datetime.now() - start_time).total_seconds()
            return TestResult(
                category="TC-GRADE",
                exercise_id=exercise.id,
                passed=False,
                timestamp=datetime.now().isoformat(),
                duration_seconds=duration,
                bugs_found=bugs_found
            )

        # Test 1: Grade WITH solution (should get 100/100)
        print("   → Testing WITH solution...")
        with_solution_result = self._test_grade_with_solution(exercise, ssh, bugs_found)

        # Test 2: Grade WITHOUT solution (should get 0/100)
        print("   → Testing WITHOUT solution...")
        without_solution_result = self._test_grade_without_solution(exercise, ssh, bugs_found)

        # Test 3: Check error message quality
        if without_solution_result:
            self._check_error_messages(without_solution_result, exercise, bugs_found)

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-GRADE",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'with_solution_score': with_solution_result.get('score') if with_solution_result else None,
                'without_solution_score': without_solution_result.get('score') if without_solution_result else None
            }
        )

    def _test_grade_with_solution(self, exercise: ExerciseContext,
                                    ssh: SSHConnection, bugs_found: list) -> dict:
        """Test grading with solution applied."""
        # Apply solution first
        if exercise.solution_files:
            for sol_file in exercise.solution_files:
                # Copy .sol file to working file
                base_name = sol_file.stem.replace('.sol', '')
                result = ssh.run(f"cp {sol_file} {base_name}")
                if not result.success:
                    print(f"      ⚠  Could not apply solution: {sol_file.name}")

        # Run grading
        result = ssh.run(f"lab grade {exercise.lab_name}")

        if not result.success:
            bugs_found.append(Bug(
                id=f"GRADE-EXEC-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-GRADE",
                exercise_id=exercise.id,
                description="Grading command failed to execute",
                fix_recommendation="Fix grading script syntax/import errors",
                verification_steps=[
                    f"Run: lab grade {exercise.lab_name}",
                    "Check for Python errors"
                ]
            ))
            return {}

        # Parse score from output
        score = self._parse_grade_score(result.stdout)

        if score != 100:
            bugs_found.append(Bug(
                id=f"GRADE-WITH-SOL-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-GRADE",
                exercise_id=exercise.id,
                description=f"Grading with solution applied gave {score}/100 (expected 100/100)",
                fix_recommendation="Fix grading logic - should pass with solution",
                verification_steps=[
                    "Apply solution files",
                    f"Run: lab grade {exercise.lab_name}",
                    "Should show 100/100"
                ]
            ))
        else:
            print(f"      ✓ With solution: {score}/100")

        return {'score': score, 'output': result.stdout}

    def _test_grade_without_solution(self, exercise: ExerciseContext,
                                       ssh: SSHConnection, bugs_found: list) -> dict:
        """Test grading without solution applied."""
        # Reset the lab first
        ssh.run(f"lab finish {exercise.lab_name}")
        ssh.run(f"lab start {exercise.lab_name}")

        # Run grading
        result = ssh.run(f"lab grade {exercise.lab_name}")

        if not result.success:
            # Already reported in with_solution test
            return {}

        # Parse score
        score = self._parse_grade_score(result.stdout)

        if score != 0:
            bugs_found.append(Bug(
                id=f"GRADE-WITHOUT-SOL-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-GRADE",
                exercise_id=exercise.id,
                description=f"Grading without solution gave {score}/100 (expected 0/100)",
                fix_recommendation="Fix grading logic - should fail without solution (false positive)",
                verification_steps=[
                    f"Run: lab finish {exercise.lab_name}",
                    f"Run: lab start {exercise.lab_name}",
                    f"Run: lab grade {exercise.lab_name}",
                    "Should show 0/100"
                ]
            ))
        else:
            print(f"      ✓ Without solution: {score}/100")

        return {'score': score, 'output': result.stdout}

    def _parse_grade_score(self, output: str) -> int:
        """Parse score from grading output."""
        # Look for patterns like "Score: 100/100" or "100 / 100"
        import re
        patterns = [
            r'Score:\s*(\d+)\s*/\s*100',
            r'(\d+)\s*/\s*100',
            r'Grade:\s*(\d+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return 0  # Default if not found

    def _check_error_messages(self, result: dict, exercise: ExerciseContext, bugs_found: list):
        """Check quality of error messages."""
        output = result.get('output', '')

        # Check for vague error messages
        vague_patterns = [
            'fail', 'error', 'wrong', 'incorrect'
        ]

        if len(output) < 50:  # Very short output
            bugs_found.append(Bug(
                id=f"GRADE-MSG-SHORT-{exercise.id}",
                severity=BugSeverity.P2_HIGH,
                category="TC-GRADE",
                exercise_id=exercise.id,
                description="Grading error messages are too brief/vague",
                fix_recommendation="Add descriptive error messages explaining what's wrong",
                verification_steps=[
                    "Test grading without solution",
                    "Check that error messages explain what needs to be fixed"
                ]
            ))
