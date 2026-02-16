"""TC-GRADE: Grading validation.

Tests grading scripts for Lab exercises using 3 scenarios:
1. WITHOUT solution (fresh start) -> must have FAILed GradingSteps
2. WITH solution applied -> must have all PASSed GradingSteps
3. Error message quality -> must be clear and actionable

DynoLabs Grading Behavior:
- GradingSteps are non-fatal (grading=True, fatal=False)
- GradingStep failures don't affect exit codes
- Exit code 0 = script completed (even if all checks failed!)
- Exit code non-zero = script crashed (fatal error)
- To determine pass/fail, we parse output for ✓/✗ or PASS/FAIL

Catches:
- False positives (all checks pass when they shouldn't)
- False negatives (checks fail when they should pass)
- Unclear error messages
- Script crashes (exit code != 0)
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models import (
    TestResult, Bug, BugSeverity, ExerciseContext,
    ExerciseType
)
from ..ssh import SSHConnection


CONTAINER_NAME = "qa-devcontainer"


class TC_GRADE:
    """Grading validation test category.

    Uses the Error Summary Pattern: collects ALL bugs before returning,
    so developers see every grading issue at once.
    """

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """Test grading script for a Lab exercise."""
        print(f"\n   TC-GRADE: Testing grading...")

        bugs_found = []
        start_time = datetime.now()

        # Only test Labs (GEs don't have grading)
        if exercise.type != ExerciseType.LAB:
            print("      Skip (not a Lab)")
            return TestResult(
                category="TC-GRADE",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=0.0,
                details={'skipped': True, 'reason': 'Not a Lab exercise'}
            )

        # Scenario 1: Grade WITH solution first (leverages existing state
        # from student simulation, avoids unnecessary reset)
        print("      Scenario 1: WITH solution...")
        with_result = self._test_with_solution(exercise, ssh, bugs_found)

        # Scenario 2: Grade WITHOUT solution (should get 0/100 or fail)
        print("      Scenario 2: WITHOUT solution...")
        without_result = self._test_without_solution(exercise, ssh, bugs_found)

        # Scenario 3: Error message quality
        if without_result and without_result.get('output'):
            print("      Scenario 3: Error message quality...")
            self._test_message_quality(without_result['output'], exercise, bugs_found)

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-GRADE",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'without_solution': {
                    'passed': without_result.get('passed') if without_result else None,
                    'return_code': without_result.get('return_code') if without_result else None,
                    'pass_count': without_result.get('pass_count', 0) if without_result else 0,
                    'fail_count': without_result.get('fail_count', 0) if without_result else 0,
                    'crashed': without_result.get('crashed', False) if without_result else False,
                },
                'with_solution': {
                    'passed': with_result.get('passed') if with_result else None,
                    'return_code': with_result.get('return_code') if with_result else None,
                    'pass_count': with_result.get('pass_count', 0) if with_result else 0,
                    'fail_count': with_result.get('fail_count', 0) if with_result else 0,
                    'crashed': with_result.get('crashed', False) if with_result else False,
                },
                'scenarios_tested': 3
            }
        )

    def _test_without_solution(self, exercise: ExerciseContext,
                                ssh: SSHConnection, bugs: List[Bug]) -> dict:
        """Scenario 1: Grade without solution - must have FAILed checks."""
        # Reset exercise to fresh state
        ssh.run_lab_command('finish', exercise.id, timeout=120)
        ssh.run_lab_command('start', exercise.id, timeout=300)

        # Grade immediately (no solution applied)
        result = ssh.run_lab_command('grade', exercise.id, timeout=300)

        # Check if script crashed (fatal error)
        if not result.success or result.return_code != 0:
            bugs.append(Bug(
                id=f"GRADE-CRASH-NOSOL-{exercise.id}",
                severity=BugSeverity.P0_BLOCKER,
                category="TC-GRADE",
                exercise_id=exercise.id,
                description=f"Grading script crashed without solution (exit code: {result.return_code})",
                fix_recommendation="Fix fatal errors in grading script. Use GradingStep for checks (non-fatal).",
                verification_steps=[
                    f"lab start {exercise.lab_name}",
                    f"lab grade {exercise.lab_name}",
                    "Should complete with FAIL indicators, not crash"
                ]
            ))
            print(f"         ✗ SCRIPT CRASHED (exit code: {result.return_code})")
            return {
                'passed': False,
                'return_code': result.return_code,
                'output': result.stdout,
                'crashed': True
            }

        # Parse output for PASS/FAIL indicators with word boundaries
        pass_count = len(re.findall(r'(✓|\bPASS\b)', result.stdout))
        fail_count = len(re.findall(r'(✗|\bFAIL\b)', result.stdout))

        # If all checks passed, that's a FALSE POSITIVE
        if pass_count > 0 and fail_count == 0:
            bugs.append(Bug(
                id=f"GRADE-FALSE-POS-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-GRADE",
                exercise_id=exercise.id,
                description=f"Grading passed without solution ({pass_count}/{pass_count} checks passed)",
                fix_recommendation="Review grading script to ensure it validates student work, not just file existence",
                verification_steps=[
                    f"lab start {exercise.lab_name}",
                    f"lab grade {exercise.lab_name}",
                    "Should show FAILed checks"
                ]
            ))
            print(f"         ✗ FALSE POSITIVE ({pass_count}/{pass_count} passed)")
        elif fail_count > 0:
            print(f"         ✓ Correctly failed ({fail_count} checks failed)")
        else:
            # No clear PASS/FAIL indicators found
            print(f"         ⚠ No PASS/FAIL indicators in output (cannot validate)")

        return {
            'passed': (pass_count > 0 and fail_count == 0),
            'return_code': result.return_code,
            'output': result.stdout,
            'pass_count': pass_count,
            'fail_count': fail_count
        }

    def _test_with_solution(self, exercise: ExerciseContext,
                             ssh: SSHConnection, bugs: List[Bug]) -> dict:
        """Scenario 2: Grade with solution - must have all PASSed checks."""
        base_dir = f"/home/student/{exercise.lab_name}"

        # Reset and start fresh first
        ssh.run_lab_command('finish', exercise.id, timeout=120)
        ssh.run_lab_command('start', exercise.id, timeout=300)

        # Try lab solve first (preferred for DynoLabs v5)
        print(f"         Trying lab solve...")
        solve_result = ssh.run_lab_command('solve', exercise.id, timeout=300)

        used_lab_solve = False
        if solve_result.success and solve_result.return_code == 0:
            print(f"         ✓ lab solve completed")
            used_lab_solve = True
        else:
            # lab solve failed or not available, try manual solution application
            print(f"         lab solve not available, applying solutions manually...")

            # Discover solution files on workstation
            result = ssh.run(f"ls {base_dir}/solutions/*.sol 2>/dev/null", timeout=10)

            solution_files = []
            if result.success and result.stdout.strip():
                solution_files = [Path(line.strip()) for line in result.stdout.strip().split('\n') if line.strip()]

            if not solution_files:
                print(f"         ⊘ No solution files found and lab solve unavailable")
                return {'passed': False, 'return_code': -1, 'output': '', 'skipped': True}

            print(f"         Found {len(solution_files)} solution file(s)")

            uses_dev_containers = (exercise.course_profile and
                                  exercise.course_profile.uses_dev_containers)

            # Start dev container for playbook execution if needed
            dc_info = None
            if uses_dev_containers:
                print(f"         Starting dev container for solution execution...")
                dc_info = ssh.ensure_devcontainer(base_dir, CONTAINER_NAME)
                if dc_info:
                    print(f"         Dev container ready (workdir: {dc_info['workdir']})")
                else:
                    print(f"         ⚠ Dev container setup failed")

            try:
                for sol_file_path in solution_files:
                    filename = sol_file_path.name
                    target_name = filename.removesuffix('.sol')
                    sol_path = str(sol_file_path)
                    work_path = f"{base_dir}/{target_name}"

                    # Copy solution
                    print(f"         Copying {filename}...")
                    ssh.run(f"test -f {sol_path} && cp {sol_path} {work_path}", timeout=10)

                    # Execute if it's a playbook
                    if target_name.endswith('.yml') or target_name.endswith('.yaml'):
                        if uses_dev_containers and dc_info:
                            # Run inside the dev container
                            print(f"         Executing {target_name} in dev container...")
                            exec_result = ssh.run_in_devcontainer(
                                f"ansible-playbook {target_name}",
                                container_name=CONTAINER_NAME,
                                workdir=dc_info['workdir'],
                                user=dc_info.get('user'),
                                timeout=300,
                            )
                            if not exec_result.success:
                                print(f"         ⚠ Playbook failed in container (rc={exec_result.return_code})")
                        elif not uses_dev_containers:
                            # Traditional course - can execute on workstation
                            print(f"         Executing {target_name}...")
                            exec_result = ssh.run(
                                f"cd {base_dir} && ansible-playbook {target_name}",
                                timeout=300
                            )
                            if not exec_result.success:
                                print(f"         ⚠ Playbook failed (rc={exec_result.return_code})")
                        else:
                            # Dev container course but container setup failed
                            print(f"         ⚠ Cannot execute {target_name} (dev container not available)")
            finally:
                # Stop dev container before grading (grade runs on workstation)
                if dc_info:
                    ssh.stop_devcontainer(CONTAINER_NAME)

        # Grade with solution
        result = ssh.run_lab_command('grade', exercise.id, timeout=300)

        # Check if script crashed (fatal error)
        if not result.success or result.return_code != 0:
            bugs.append(Bug(
                id=f"GRADE-CRASH-WITHSOL-{exercise.id}",
                severity=BugSeverity.P0_BLOCKER,
                category="TC-GRADE",
                exercise_id=exercise.id,
                description=f"Grading script crashed with solution applied (exit code: {result.return_code})",
                fix_recommendation="Fix fatal errors in grading script. Solution should not cause crashes.",
                verification_steps=[
                    f"lab start {exercise.lab_name}",
                    "Apply solution files",
                    f"lab grade {exercise.lab_name}",
                    "Should complete with PASS indicators, not crash"
                ]
            ))
            print(f"         ✗ SCRIPT CRASHED (exit code: {result.return_code})")
            return {
                'passed': False,
                'return_code': result.return_code,
                'output': result.stdout,
                'crashed': True
            }

        # Parse output for PASS/FAIL indicators with word boundaries
        pass_count = len(re.findall(r'(✓|\bPASS\b)', result.stdout))
        fail_count = len(re.findall(r'(✗|\bFAIL\b)', result.stdout))

        # With solution, all checks should pass
        if fail_count > 0:
            # Some checks failed even with solution - FALSE NEGATIVE!
            bugs.append(Bug(
                id=f"GRADE-FALSE-NEG-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-GRADE",
                exercise_id=exercise.id,
                description=f"Grading failed with solution applied ({fail_count} checks failed)",
                fix_recommendation="Review grading script validation logic, compare with solution files",
                verification_steps=[
                    f"lab start {exercise.lab_name}",
                    "Apply solution files",
                    f"lab grade {exercise.lab_name}",
                    "Should show all PASSed checks"
                ]
            ))
            print(f"         ✗ FALSE NEGATIVE ({fail_count}/{pass_count + fail_count} failed)")
        elif pass_count > 0:
            print(f"         ✓ Correctly passed ({pass_count}/{pass_count} passed)")
        else:
            # No clear PASS/FAIL indicators found
            print(f"         ⚠ No PASS/FAIL indicators in output (cannot validate)")

        return {
            'passed': (pass_count > 0 and fail_count == 0),
            'return_code': result.return_code,
            'output': result.stdout,
            'pass_count': pass_count,
            'fail_count': fail_count
        }

    def _test_message_quality(self, output: str, exercise: ExerciseContext,
                               bugs: List[Bug]):
        """Scenario 3: Check error message quality.

        Good error messages:
        - Explain what's wrong (not just "FAIL")
        - Are actionable (tell student what to fix)
        - Are specific (reference exact resources, files, or settings)
        - Are reasonably detailed (>20 chars per message)
        """
        # Find individual grading check messages
        check_messages = self._extract_check_messages(output)

        if not check_messages:
            # Output exists but no parseable check messages
            if len(output.strip()) < 50:
                bugs.append(Bug(
                    id=f"GRADE-MSG-BRIEF-{exercise.id}",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-GRADE",
                    exercise_id=exercise.id,
                    description="Grading output is too brief - doesn't explain what's wrong",
                    fix_recommendation="Add descriptive error messages to each grading check",
                    verification_steps=[
                        f"lab grade {exercise.lab_name}",
                        "Each check should explain what needs to be fixed"
                    ]
                ))
                print(f"         ⚠ Output too brief")
            return

        # Check for raw Python tracebacks (should be caught and user-friendly)
        if 'Traceback' in output or 'File "' in output:
            bugs.append(Bug(
                id=f"GRADE-MSG-TRACEBACK-{exercise.id}",
                severity=BugSeverity.P3_LOW,
                category="TC-GRADE",
                exercise_id=exercise.id,
                description="Grading output contains raw Python traceback",
                fix_recommendation="Catch exceptions and provide user-friendly error messages",
                verification_steps=["Review grading output for stack traces"]
            ))
            print(f"         ⚠ Error messages contain tracebacks")

        # Check each message for quality
        # Actionable keywords indicate the message tells the student what to check/fix
        actionable_keywords = [
            # Obligation/requirement words
            'should', 'must', 'expected', 'required', 'need',
            # State words
            'found', 'missing', 'exists', 'exist', 'contains', 'contain',
            'not', 'incorrect', 'invalid', 'wrong',
            # Action words
            'check', 'verify', 'ensure', 'ensuring', 'confirm',
            'create', 'configure', 'install', 'enable', 'disable',
            'start', 'started', 'stop', 'stopped', 'running',
            # Status words
            'is', 'are', 'in', 'on',  # "is running", "are configured", "in group", "on host"
            'reachable', 'available', 'accessible', 'resolved',
        ]

        vague_messages = []
        for msg in check_messages:
            if len(msg) < 20:
                vague_messages.append(msg)
            elif not any(word in msg.lower() for word in actionable_keywords):
                vague_messages.append(msg)

        # If more than half the messages are vague, report it
        if vague_messages and len(vague_messages) > len(check_messages) / 2:
            bugs.append(Bug(
                id=f"GRADE-MSG-VAGUE-{exercise.id}",
                severity=BugSeverity.P2_HIGH,
                category="TC-GRADE",
                exercise_id=exercise.id,
                description=f"Grading messages are vague ({len(vague_messages)} of {len(check_messages)} checks)",
                fix_recommendation="Make error messages specific and actionable",
                verification_steps=[
                    "Review grading check messages",
                    "Each should explain what's expected vs what was found"
                ]
            ))
            print(f"         ⚠ {len(vague_messages)} vague messages")
        else:
            print(f"         ✓ Message quality OK ({len(check_messages)} checks)")

    def _parse_score(self, output: str) -> Optional[int]:
        """Parse grading score from output.

        Handles multiple output formats:
        - "Overall grade: 80 of 100"
        - "Score: 100/100"
        - "80 / 100"
        - "Grade: 100"
        - DynoLabs v5: count PASS/FAIL lines (each check is a line)

        Returns:
            Score as integer 0-100, or None if no score found
        """
        if not output:
            return None

        # Try standard score patterns first
        patterns = [
            r'Overall\s+grade:\s*(\d+)\s*(?:of|/)\s*100',
            r'Score:\s*(\d+)\s*/\s*100',
            r'(\d+)\s*/\s*100',
            r'Grade:\s*(\d+)',
            r'(\d+)\s+of\s+100',
        ]

        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return int(match.group(1))

        # DynoLabs v5 format: count PASS vs FAIL lines
        pass_count = len(re.findall(r'\bPASS\b\s+\S', output))
        fail_count = len(re.findall(r'\bFAIL\b\s+\S', output))
        total = pass_count + fail_count

        if total > 0:
            return round((pass_count / total) * 100)

        return None

    def _extract_check_messages(self, output: str) -> List[str]:
        """Extract individual grading check messages from output.

        Parses patterns like:
        - "FAIL: Service httpd is not running"
        - "PASS: File /etc/config exists"
        - "[ FAIL ] Service httpd is not running"
        - "✗ Service httpd is not running"
        - DynoLabs v5: "PASS    The 'operator_normal' user exists..."
        - DynoLabs v5: "FAIL    The 'operator_normal' user exists..."

        Returns:
            List of unique check messages (deduplicated, order preserved)
        """
        messages = []

        patterns = [
            # DynoLabs v5: PASS/FAIL followed by spaces then message
            r'(?:\bPASS\b|\bFAIL\b)\s{2,}(.+?)(?:\n|$)',
            # Standard patterns
            r'(?:\bFAIL\b|\bFAILED\b|ERROR|✗|✘|❌)[\s:]*(.+?)(?:\n|$)',
            r'\[\s*FAIL\s*\]\s*(.+?)(?:\n|$)',
            r'(?:\bPASS\b|\bPASSED\b|OK|✓|✔|✅)[\s:]*(.+?)(?:\n|$)',
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, output, re.IGNORECASE):
                msg = match.group(1).strip()
                if msg and len(msg) > 3:
                    messages.append(msg)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for msg in messages:
            if msg not in seen:
                seen.add(msg)
                unique.append(msg)

        return unique
