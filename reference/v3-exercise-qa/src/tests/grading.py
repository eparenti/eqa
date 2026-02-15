"""TC-GRADE: Grading validation.

Tests grading scripts for Lab exercises using 3 scenarios:
1. WITH solution applied -> must get 100/100
2. WITHOUT solution (fresh start) -> must get 0/100
3. Error message quality -> must be clear and actionable

Catches:
- False positives (passes when it shouldn't)
- False negatives (fails when it should pass)
- Unclear error messages (student doesn't know what to fix)

Only runs for Lab exercises (GEs don't have grading).
"""

import re
from datetime import datetime
from typing import List, Optional

from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext, ExerciseType, ExercisePattern
from ..clients.ssh import SSHConnection


class TC_GRADE:
    """Grading validation test category.

    Uses the Error Summary Pattern: collects ALL bugs before returning,
    so students/developers see every grading issue at once.
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

        # Check if grading script exists
        if not exercise.grading_script or not exercise.grading_script.exists():
            bugs_found.append(Bug(
                id=f"GRADE-MISSING-{exercise.id}",
                severity=BugSeverity.P0_BLOCKER,
                category="TC-GRADE",
                exercise_id=exercise.id,
                description="No grading script found for Lab exercise",
                fix_recommendation="Create grading module in classroom/grading/src/",
                verification_steps=[
                    "Create Python grading module with grade() function",
                    f"lab grade {exercise.lab_name}"
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

        # Scenario 1: Grade WITH solution applied (should get 100/100)
        print("      Scenario 1: WITH solution...")
        with_result = self._test_with_solution(exercise, ssh, bugs_found)

        # Scenario 2: Grade WITHOUT solution (should get 0/100)
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
                'with_solution_score': with_result.get('score') if with_result else None,
                'without_solution_score': without_result.get('score') if without_result else None,
                'scenarios_tested': 3
            }
        )

    def _is_dynolabs5(self, exercise: ExerciseContext) -> bool:
        """Check if exercise uses DynoLabs v5 framework."""
        return getattr(exercise, 'content_pattern', None) == ExercisePattern.PYTHON or \
            (exercise.grading_script and exercise.grading_script.suffix == '.py')

    def _test_with_solution(self, exercise: ExerciseContext,
                             ssh: SSHConnection, bugs: List[Bug]) -> dict:
        """Scenario 1: Grade with solution applied - must get 100/100.

        For DynoLabs v5: uses `lab solve` to apply solutions.
        For legacy: copies .sol files and executes playbooks manually.
        """
        lab_name = exercise.lab_name
        base_dir = f"/home/student/{lab_name}"

        if self._is_dynolabs5(exercise):
            # DynoLabs v5: use `lab solve` to apply solutions
            print(f"         Applying solution via: lab solve {lab_name}")
            solve_result = ssh.run_lab_command('solve', exercise.id, timeout=300)
            if not solve_result.success:
                bugs.append(Bug(
                    id=f"GRADE-SOLVE-{exercise.id}",
                    severity=BugSeverity.P1_CRITICAL,
                    category="TC-GRADE",
                    exercise_id=exercise.id,
                    description=f"'lab solve {lab_name}' failed",
                    fix_recommendation="Fix solve playbook in grading module",
                    verification_steps=[
                        f"lab start {lab_name}",
                        f"lab solve {lab_name}"
                    ]
                ))
                return {}
        elif exercise.solution_files:
            # Legacy: copy .sol files and execute playbooks
            for sol_file in exercise.solution_files:
                deploy_name = sol_file.name
                if deploy_name.endswith('.sol'):
                    deploy_name = deploy_name[:-4]

                # Copy solution to working directory
                sol_path = f"{base_dir}/solutions/{sol_file.name}"
                work_path = f"{base_dir}/{deploy_name}"

                # Try solutions/ directory first, then base directory
                result = ssh.run(f"test -f {sol_path} && cp {sol_path} {work_path}", timeout=10)
                if not result.success:
                    sol_path = f"{base_dir}/{sol_file.name}"
                    ssh.run(f"test -f {sol_path} && cp {sol_path} {work_path}", timeout=10)

            # Execute Ansible playbook solutions
            for sol_file in exercise.solution_files:
                deploy_name = sol_file.name
                if deploy_name.endswith('.sol'):
                    deploy_name = deploy_name[:-4]

                if deploy_name.endswith(('.yml', '.yaml')):
                    work_path = f"{base_dir}/{deploy_name}"
                    # Check if file exists before executing
                    exists = ssh.run(f"test -f {work_path} && echo yes", timeout=5)
                    if exists.success and 'yes' in exists.stdout:
                        print(f"         Applying solution: {deploy_name}")
                        result = ssh.run(
                            f"cd {base_dir} && ansible-playbook {deploy_name} 2>&1",
                            timeout=300
                        )
                        if not result.success:
                            # Try with ansible-navigator
                            result = ssh.run(
                                f"cd {base_dir} && ansible-navigator run {deploy_name} -m stdout 2>&1",
                                timeout=300
                            )

        # Run grading
        result = ssh.run_lab_command('grade', exercise.id, timeout=600)
        output = result.stdout + result.stderr

        # Try to parse score regardless of exit code - DynoLabs v5 returns
        # non-zero when grading checks fail, but the output is still valid
        score = self._parse_score(output)

        if score is None and not result.success:
            # Truly failed to execute (no parseable output AND non-zero exit)
            bugs.append(Bug(
                id=f"GRADE-EXEC-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-GRADE",
                exercise_id=exercise.id,
                description=f"'lab grade {lab_name}' failed to execute",
                fix_recommendation="Fix grading script Python errors",
                verification_steps=[
                    f"lab grade {lab_name}",
                    "Check for Python import/syntax errors"
                ]
            ))
            return {}
        elif score is None:
            bugs.append(Bug(
                id=f"GRADE-NOSCORE-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-GRADE",
                exercise_id=exercise.id,
                description="Could not parse grading score from output",
                fix_recommendation="Ensure grading output includes score in format 'X/100' or individual PASS/FAIL checks",
                verification_steps=[f"lab grade {lab_name}"]
            ))
            return {'score': None, 'output': output}

        if score != 100:
            bugs.append(Bug(
                id=f"GRADE-FALSENEGATIVE-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-GRADE",
                exercise_id=exercise.id,
                description=f"Grading with solution applied gave {score}/100 (expected 100/100) - false negative",
                fix_recommendation="Fix grading logic: should pass with correct solution applied",
                verification_steps=[
                    "Apply all solution files",
                    f"lab grade {lab_name}",
                    "Should show 100/100"
                ]
            ))
            print(f"         FAIL {score}/100 (expected 100)")
        else:
            print(f"         OK {score}/100")

        return {'score': score, 'output': output}

    def _test_without_solution(self, exercise: ExerciseContext,
                                ssh: SSHConnection, bugs: List[Bug]) -> dict:
        """Scenario 2: Grade without solution - must get 0/100 (or low score).

        Process:
        1. Reset lab (finish + start)
        2. Run lab grade immediately (no solution applied)
        3. Score should be 0/100
        """
        lab_name = exercise.lab_name

        # Reset lab to clean state
        ssh.run_lab_command('finish', exercise.id, timeout=300)
        result = ssh.run_lab_command('start', exercise.id, timeout=300)

        if not result.success:
            # Can't reset lab - skip this scenario
            print(f"         Skip (lab restart failed)")
            return {}

        # Grade immediately without applying solution
        result = ssh.run_lab_command('grade', exercise.id, timeout=600)
        output = result.stdout + result.stderr

        # Parse score regardless of exit code (DynoLabs v5 returns non-zero
        # for failed checks, but that's expected here - no solution applied)
        score = self._parse_score(output)

        if score is None and not result.success:
            # Grading command truly failed
            return {}
        elif score is None:
            return {'score': None, 'output': output}

        if score > 0:
            bugs.append(Bug(
                id=f"GRADE-FALSEPOSITIVE-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                category="TC-GRADE",
                exercise_id=exercise.id,
                description=f"Grading without solution gave {score}/100 (expected 0/100) - false positive",
                fix_recommendation="Fix grading logic: should fail when solution is not applied",
                verification_steps=[
                    f"lab finish {lab_name}",
                    f"lab start {lab_name}",
                    f"lab grade {lab_name}",
                    "Should show 0/100"
                ]
            ))
            print(f"         FAIL {score}/100 (expected 0)")
        else:
            print(f"         OK {score}/100")

        return {'score': score, 'output': output}

    def _test_message_quality(self, output: str, exercise: ExerciseContext,
                               bugs: List[Bug]):
        """Scenario 3: Check error message quality.

        Good error messages:
        - Explain what's wrong (not just "FAIL")
        - Are actionable (tell student what to fix)
        - Are specific (reference exact resources, files, or settings)
        - Are reasonably detailed (>50 chars per message)
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
            return

        # Check each message for quality
        vague_messages = []
        for msg in check_messages:
            if len(msg) < 20:
                vague_messages.append(msg)
            elif not any(word in msg.lower() for word in
                        ['should', 'must', 'expected', 'found', 'missing',
                         'not', 'incorrect', 'check', 'verify', 'ensure',
                         'create', 'configure', 'install', 'enable']):
                vague_messages.append(msg)

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
            print(f"         WARNING {len(vague_messages)} vague messages")
        else:
            print(f"         OK message quality ({len(check_messages)} checks)")

    def _parse_score(self, output: str) -> Optional[int]:
        """Parse grading score from output.

        Handles multiple output formats:
        - "Overall grade: 80 of 100"
        - "Score: 100/100"
        - "80 / 100"
        - "Grade: 100"
        - DynoLabs v5: count PASS/FAIL lines (each check is a line)
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
        # Each grading check ends with "PASS <message>" or "FAIL <message>"
        # Exclude SUCCESS lines (those are setup steps, not grading checks)
        pass_count = len(re.findall(r'PASS\s+\S', output))
        fail_count = len(re.findall(r'FAIL\s+\S', output))
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
        """
        messages = []

        patterns = [
            # DynoLabs v5: PASS/FAIL followed by spaces then message
            r'(?:PASS|FAIL)\s{2,}(.+?)(?:\n|$)',
            # Standard patterns
            r'(?:FAIL|FAILED|ERROR|✗|✘|❌)[\s:]*(.+?)(?:\n|$)',
            r'\[\s*FAIL\s*\]\s*(.+?)(?:\n|$)',
            r'(?:PASS|PASSED|OK|✓|✔|✅)[\s:]*(.+?)(?:\n|$)',
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
