#!/usr/bin/env python3
"""
TC-GRADE: Grading Validation (Labs Only)

Thoroughly validates automated grading for Labs:

Scenario 1: WITH solution applied
- Copy solution files
- Apply solution
- Run `lab grade <exercise>`
- Must PASS with 100/100 score

Scenario 2: WITHOUT solution (clean start)
- Reset lab (finish + start)
- Run `lab grade <exercise>`
- Must FAIL with 0/100 score and clear error messages

Scenario 3: Message clarity
- Error messages must be actionable
- Must indicate what's wrong
- Must avoid cryptic jargon

This prevents false positives and false negatives in grading.
"""

import sys
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.test_result import TestResult, Bug, BugSeverity, ExerciseContext, ExerciseType
from lib.ssh_connection import SSHConnection


class TC_GRADE:
    """
    Grading validation for Labs.

    Tests grading accuracy and message clarity.
    """

    def __init__(self):
        """Initialize grading tester."""
        pass

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test grading validation.

        Args:
            exercise: Exercise context
            ssh: SSH connection to workstation

        Returns:
            TestResult with grading validation results
        """
        start_time = datetime.now()
        bugs_found = []
        test_details = {
            'scenario_1_passed': False,
            'scenario_1_score': None,
            'scenario_2_failed': False,
            'scenario_2_score': None,
            'messages_clear': False,
            'grading_output': {}
        }

        print(f"\n📝 TC-GRADE: Grading Validation")
        print("=" * 60)

        # Only test Labs
        if exercise.type != ExerciseType.LAB:
            print("  ⏭️  Skipping: Not a Lab")
            return TestResult(
                category="TC-GRADE",
                exercise_id=exercise.id,
                passed=True,
                timestamp=start_time.isoformat(),
                duration_seconds=0,
                bugs_found=[],
                details={'skipped': True, 'reason': 'Not a Lab'},
                summary="Skipped: Not a Lab"
            )

        print("\n  Testing grading script with 3 scenarios...\n")

        # SCENARIO 1: WITH solution (must PASS)
        print("  📋 Scenario 1: WITH solution applied")
        print("  " + "-" * 56)

        # Get solution files
        solutions_dir = f"~/DO{exercise.lesson_code.upper()}/solutions/{exercise.id}/"
        exercise_dir = f"~/DO{exercise.lesson_code.upper()}/labs/{exercise.id}/"

        # Find solution files
        find_result = ssh.run(f"find {solutions_dir} -name '*.sol' 2>/dev/null", timeout=10)

        if find_result['exit_code'] != 0 or not find_result['stdout'].strip():
            bugs_found.append(Bug(
                id=f"BUG-{exercise.id.upper()}-NO-SOLUTION",
                severity=BugSeverity.P0_BLOCKER,
                exercise_id=exercise.id,
                category="TC-GRADE",
                description="No solution files found for Lab",
                fix_recommendation=(
                    f"Create solution files in: {solutions_dir}\n\n"
                    "Labs require solution files for testing.\n"
                    "Create solution files that achieve 100% on grading."
                ),
                verification_steps=[
                    "1. Create solution files",
                    f"2. Place in {solutions_dir}",
                    "3. Test solution achieves 100%",
                    "4. Re-run test"
                ]
            ))
            print("    ❌ No solution files found")

            return self._build_result(start_time, exercise, bugs_found, test_details)

        solution_files = [f.strip() for f in find_result['stdout'].strip().split('\n')]
        print(f"    Found {len(solution_files)} solution files")

        # Copy and apply solutions
        for sol_file in solution_files:
            # Get filename without .sol extension
            filename = Path(sol_file).name.replace('.sol', '')

            # Copy to exercise directory
            copy_cmd = f"cp {sol_file} {exercise_dir}{filename}"
            ssh.run(copy_cmd, timeout=5)
            print(f"      Copied: {filename}")

        # Determine how to apply solution based on file types
        apply_success = self._apply_solutions(exercise, ssh, solution_files)

        if not apply_success:
            print("    ⚠️  Could not auto-apply solutions, proceeding to grading...")

        # Run grading WITH solution
        print("\n    Running: lab grade...")
        grade_result = ssh.run(f"cd ~ && lab grade {exercise.id}", timeout=300)

        test_details['grading_output']['scenario_1'] = grade_result['stdout']

        # Parse grading output
        score_with = self._parse_grade_score(grade_result['stdout'])
        test_details['scenario_1_score'] = score_with

        if score_with is None:
            bugs_found.append(Bug(
                id=f"BUG-{exercise.id.upper()}-GRADE-NO-SCORE",
                severity=BugSeverity.P1_CRITICAL,
                exercise_id=exercise.id,
                category="TC-GRADE",
                description="Cannot parse grading score from output",
                fix_recommendation=(
                    "Fix grading script output:\n\n"
                    "Grading must output score in recognizable format:\n"
                    "  - 'Overall result: PASS' or 'FAIL'\n"
                    "  - 'Score: X/Y'\n"
                    "  - Or similar standard format"
                ),
                verification_steps=[
                    "1. Review grading script output format",
                    "2. Ensure score is clearly indicated",
                    "3. Re-run grading",
                    "4. Verify score is parseable"
                ]
            ))
            print(f"    ❌ Cannot parse score from output")
        elif score_with < 100:
            bugs_found.append(Bug(
                id=f"BUG-{exercise.id.upper()}-GRADE-WITH-FAIL",
                severity=BugSeverity.P1_CRITICAL,
                exercise_id=exercise.id,
                category="TC-GRADE",
                description=f"Grading failed WITH solution applied (score: {score_with}/100)",
                fix_recommendation=(
                    f"Fix solution or grading script:\n\n"
                    f"Score WITH solution: {score_with}/100 (expected: 100/100)\n\n"
                    "Options:\n"
                    "1. Fix solution files to complete all tasks\n"
                    "2. Fix grading script if checking incorrectly\n"
                    "3. Review grading output for specific failures\n\n"
                    f"Grading output:\n{grade_result['stdout'][:500]}"
                ),
                verification_steps=[
                    "1. Review grading output",
                    "2. Fix solution or grading script",
                    "3. Apply solution",
                    "4. Run: lab grade",
                    "5. Verify 100/100"
                ]
            ))
            print(f"    ❌ Failed: {score_with}/100 (expected: 100/100)")
        else:
            test_details['scenario_1_passed'] = True
            print(f"    ✅ Passed: {score_with}/100")

        # SCENARIO 2: WITHOUT solution (must FAIL)
        print("\n  📋 Scenario 2: WITHOUT solution (clean start)")
        print("  " + "-" * 56)

        # Reset environment
        print("    Resetting environment...")
        ssh.run(f"cd ~ && lab finish {exercise.id}", timeout=300)
        ssh.run(f"cd ~ && lab start {exercise.id}", timeout=600)

        # Run grading WITHOUT solution
        print("    Running: lab grade...")
        grade_result = ssh.run(f"cd ~ && lab grade {exercise.id}", timeout=300)

        test_details['grading_output']['scenario_2'] = grade_result['stdout']

        score_without = self._parse_grade_score(grade_result['stdout'])
        test_details['scenario_2_score'] = score_without

        if score_without is None:
            print(f"    ⚠️  Cannot parse score")
        elif score_without > 0:
            bugs_found.append(Bug(
                id=f"BUG-{exercise.id.upper()}-GRADE-WITHOUT-PASS",
                severity=BugSeverity.P1_CRITICAL,
                exercise_id=exercise.id,
                category="TC-GRADE",
                description=f"Grading passed WITHOUT solution (false positive: {score_without}/100)",
                fix_recommendation=(
                    f"Fix grading script - false positive detected:\n\n"
                    f"Score WITHOUT solution: {score_without}/100 (expected: 0/100)\n\n"
                    "Grading script is passing when it should fail.\n"
                    "Review grading checks and ensure they verify actual work."
                ),
                verification_steps=[
                    "1. Review grading script checks",
                    "2. Ensure checks validate actual work",
                    "3. Run: lab start (fresh)",
                    "4. Run: lab grade",
                    "5. Verify 0/100 without solution"
                ]
            ))
            print(f"    ❌ False positive: {score_without}/100 (expected: 0/100)")
        else:
            test_details['scenario_2_failed'] = True
            print(f"    ✅ Failed as expected: {score_without}/100")

        # SCENARIO 3: Message clarity
        print("\n  📋 Scenario 3: Message clarity")
        print("  " + "-" * 56)

        messages_clear = self._check_message_clarity(grade_result['stdout'])
        test_details['messages_clear'] = messages_clear

        if not messages_clear:
            bugs_found.append(Bug(
                id=f"BUG-{exercise.id.upper()}-GRADE-MESSAGES",
                severity=BugSeverity.P2_HIGH,
                exercise_id=exercise.id,
                category="TC-GRADE",
                description="Grading messages are unclear or not actionable",
                fix_recommendation=(
                    "Improve grading messages:\n\n"
                    "Good message:\n"
                    "  ❌ User 'webadmin' not found on servera\n"
                    "  → Create user 'webadmin' on servera\n\n"
                    "Bad message:\n"
                    "  ❌ Check failed\n"
                    "  → (too vague)\n\n"
                    "Update grading script to provide specific, actionable feedback."
                ),
                verification_steps=[
                    "1. Review current grading messages",
                    "2. Make messages specific and actionable",
                    "3. Test grading without solution",
                    "4. Verify messages are helpful"
                ]
            ))
            print("    ❌ Messages unclear")
        else:
            print("    ✅ Messages are clear and actionable")

        return self._build_result(start_time, exercise, bugs_found, test_details)

    def _apply_solutions(self, exercise: ExerciseContext, ssh: SSHConnection,
                        solution_files: List[str]) -> bool:
        """
        Try to automatically apply solution files.

        Returns:
            True if solutions were applied, False otherwise
        """
        exercise_dir = f"~/DO{exercise.lesson_code.upper()}/labs/{exercise.id}/"

        applied_any = False

        for sol_file in solution_files:
            filename = Path(sol_file).name.replace('.sol', '')

            # Determine how to apply based on file extension
            if filename.endswith('.yml') or filename.endswith('.yaml'):
                # Ansible playbook
                cmd = f"cd {exercise_dir} && ansible-navigator run {filename} -m stdout"
                result = ssh.run(cmd, timeout=300)
                if result['exit_code'] == 0:
                    applied_any = True

            elif filename.endswith('.sh'):
                # Shell script
                cmd = f"cd {exercise_dir} && bash {filename}"
                result = ssh.run(cmd, timeout=120)
                if result['exit_code'] == 0:
                    applied_any = True

            # For other file types (.conf, .txt, etc.), just copying is enough

        return applied_any

    def _parse_grade_score(self, output: str) -> int:
        """
        Parse grade score from output.

        Returns:
            Score as integer (0-100), or None if cannot parse
        """
        # Look for "Overall result: PASS" or "FAIL"
        if re.search(r'Overall result:\s*PASS', output, re.IGNORECASE):
            return 100
        elif re.search(r'Overall result:\s*FAIL', output, re.IGNORECASE):
            return 0

        # Look for "Score: X/Y" pattern
        score_match = re.search(r'Score:\s*(\d+)/(\d+)', output)
        if score_match:
            score = int(score_match.group(1))
            total = int(score_match.group(2))
            return int((score / total) * 100)

        # Look for "X/Y" pattern
        fraction_match = re.search(r'(\d+)/(\d+)', output)
        if fraction_match:
            score = int(fraction_match.group(1))
            total = int(fraction_match.group(2))
            return int((score / total) * 100)

        return None

    def _check_message_clarity(self, output: str) -> bool:
        """
        Check if grading messages are clear and actionable.

        Returns:
            True if messages are clear, False otherwise
        """
        # Extract individual check messages
        check_pattern = r'·\s*(.+?)\s+(PASS|FAIL)'
        checks = re.finditer(check_pattern, output, re.MULTILINE)

        clear_count = 0
        unclear_count = 0

        for check in checks:
            message = check.group(1).strip()

            # Good messages are specific (mention resources, commands, files, etc.)
            is_clear = (
                len(message) > 20 and  # Not too short
                not message.lower().startswith('check') and  # Not generic "Check..."
                not message.lower().startswith('verify') and  # Not generic "Verify..."
                any(word in message.lower() for word in ['user', 'file', 'service', 'port', 'package', 'directory'])
            )

            if is_clear:
                clear_count += 1
            else:
                unclear_count += 1

        # If majority of messages are clear, consider it good
        if clear_count + unclear_count == 0:
            return True  # No checks found, skip this validation

        return clear_count > unclear_count

    def _build_result(self, start_time: datetime, exercise: ExerciseContext,
                     bugs_found: List[Bug], test_details: Dict) -> TestResult:
        """Build test result."""
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        passed = len(bugs_found) == 0

        return TestResult(
            category="TC-GRADE",
            exercise_id=exercise.id,
            passed=passed,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details=test_details,
            summary=f"Grading validation {'passed' if passed else 'failed'} - {len(bugs_found)} issues found"
        )


def main():
    """Test TC_GRADE functionality."""
    import argparse

    parser = argparse.ArgumentParser(description="Test TC-GRADE category")
    parser.add_argument("exercise_id", help="Exercise ID to test")
    parser.add_argument("--workstation", default="workstation", help="Workstation hostname")
    parser.add_argument("--lesson-code", help="Lesson code")

    args = parser.parse_args()

    # Create exercise context (must be a Lab)
    from lib.test_result import ExerciseContext, ExerciseType
    exercise = ExerciseContext(
        id=args.exercise_id,
        type=ExerciseType.LAB,
        lesson_code=args.lesson_code or "",
        chapter=1,
        chapter_title="Chapter",
        title=args.exercise_id
    )

    # Create SSH connection
    ssh = SSHConnection(args.workstation)

    if not ssh.test_connection():
        print(f"Cannot connect to {args.workstation}")
        return 1

    # Run test
    tester = TC_GRADE()
    result = tester.test(exercise, ssh)

    # Print results
    print("\n" + "=" * 60)
    print(f"Result: {'PASS' if result.passed else 'FAIL'}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Bugs Found: {len(result.bugs_found)}")
    print("=" * 60)

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
