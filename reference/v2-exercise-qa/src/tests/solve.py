"""TC-SOLVE: Solve playbook testing.

Tests that solve.yml playbooks automatically complete exercises correctly:
- Solve playbook exists
- Executes without errors
- Results in passing grade (100/100)
- Properly applies solution
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext, ExerciseType
from ..clients.ssh import SSHConnection


class TC_SOLVE:
    """Solve playbook test category."""

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test solve playbook functionality.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-SOLVE: Testing solve playbook...")

        bugs_found = []
        start_time = datetime.now()

        # Only test Labs (GEs don't have grading)
        if exercise.type != ExerciseType.LAB:
            print(f"   ⏭  Skipping (not a Lab)")
            duration = (datetime.now() - start_time).total_seconds()
            return TestResult(
                category="TC-SOLVE",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=duration,
                bugs_found=[],
                details={'status': 'skipped', 'reason': 'not_a_lab'}
            )

        # Find solve playbook
        solve_playbook = self._find_solve_playbook(exercise)
        if not solve_playbook:
            # Only flag as bug if the instructions reference a solve playbook
            if self._instructions_mention_solve(exercise):
                bugs_found.append(Bug(
                    id=f"SOLVE-MISSING-001-{exercise.id}",
                    severity=BugSeverity.P1_CRITICAL,
                    category="TC-SOLVE",
                    exercise_id=exercise.id,
                    description="Instructions reference a solve playbook but none exists",
                    fix_recommendation="Create solve.yml in materials directory"
                ))
                print(f"   ✗ Instructions mention solve playbook but it doesn't exist")
            else:
                print(f"   ⏭  No solve playbook (not referenced in instructions)")
        else:
            print(f"   Found solve playbook: {solve_playbook.name}")

            # Test solve playbook execution
            self._test_solve_execution(exercise, solve_playbook, ssh, bugs_found)

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-SOLVE",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'solve_playbook': str(solve_playbook) if solve_playbook else None
            }
        )

    def _instructions_mention_solve(self, exercise: ExerciseContext) -> bool:
        """Check if exercise instructions reference a solve playbook."""
        import re

        # Check EPUB instructions content
        instructions = getattr(exercise, 'instructions', None) or ''
        if not instructions and hasattr(exercise, 'epub_content'):
            instructions = exercise.epub_content or ''

        instructions_lower = instructions.lower()
        solve_patterns = [
            r'lab\s+solve',
            r'run\s+the\s+solve',
            r'solve\s+playbook',
            r'solve\.yml',
            r'solve\.yaml',
        ]

        for pattern in solve_patterns:
            if re.search(pattern, instructions_lower):
                return True

        return False

    def _find_solve_playbook(self, exercise: ExerciseContext) -> Optional[Path]:
        """Find solve playbook for exercise."""
        if not exercise.materials_dir:
            return None

        # Common solve playbook names
        candidates = [
            exercise.materials_dir / "solve.yml",
            exercise.materials_dir / "solve.yaml",
            exercise.materials_dir / "playbook-solve.yml",
            exercise.materials_dir / "playbook-solve.yaml",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None

    def _test_solve_execution(self, exercise: ExerciseContext,
                             solve_playbook: Path, ssh: SSHConnection,
                             bugs_found: List[Bug]):
        """Test solve playbook execution."""

        # Step 1: Run lab start to prepare environment
        print(f"   → Running lab start...")
        result = ssh.run(f"lab start {exercise.lab_name}")
        if result.exit_code != 0:
            bugs_found.append(Bug(
                id=f"SOLVE-START-FAIL-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-SOLVE",
                exercise_id=exercise.id,
                description="Lab start failed before solve playbook test",
                fix_recommendation=f"Fix lab start script for {exercise.id}"
            ))
            return

        # Step 2: Execute solve playbook
        print(f"   → Executing solve playbook...")
        solve_cmd = f"cd {exercise.materials_dir} && ansible-navigator run {solve_playbook.name} -m stdout"
        result = ssh.run(solve_cmd, timeout=300)

        if result.exit_code != 0:
            bugs_found.append(Bug(
                id=f"SOLVE-EXEC-FAIL-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-SOLVE",
                exercise_id=exercise.id,
                description="Solve playbook execution failed",
                fix_recommendation=f"Fix solve playbook syntax/logic: {result.stderr[:200]}"
            ))
            return

        # Step 3: Run grading to verify solve worked
        print(f"   → Verifying with lab grade...")
        result = ssh.run(f"lab grade {exercise.lab_name}")

        if result.exit_code != 0:
            bugs_found.append(Bug(
                id=f"SOLVE-GRADE-FAIL-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-SOLVE",
                exercise_id=exercise.id,
                description="Grading failed after solve playbook execution",
                fix_recommendation="Check that solve playbook correctly implements all requirements"
            ))
            return

        # Parse score
        score = self._parse_grade_score(result.stdout)
        if score != 100:
            bugs_found.append(Bug(
                id=f"SOLVE-INCOMPLETE-001-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-SOLVE",
                exercise_id=exercise.id,
                description=f"Solve playbook resulted in {score}/100 (expected 100/100)",
                fix_recommendation="Solve playbook does not fully complete the exercise requirements"
            ))
        else:
            print(f"   ✓ Solve playbook completed successfully (100/100)")

    def _parse_grade_score(self, output: str) -> int:
        """Parse score from grading output."""
        import re

        # Look for "Score: X/100" or similar patterns
        patterns = [
            r'Score:\s*(\d+)/100',
            r'SCORE:\s*(\d+)/100',
            r'Grade:\s*(\d+)/100',
            r'GRADE:\s*(\d+)/100',
            r'(\d+)/100',
        ]

        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                return int(match.group(1))

        return 0
