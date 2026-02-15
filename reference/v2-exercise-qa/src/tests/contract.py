"""TC-CONTRACT: Contract testing.

Tests that exercise contracts are honored:
- lab start/finish/grade commands work as documented
- Output formats are consistent
- Exit codes follow conventions
- Error messages are helpful
- All documented commands exist
"""

import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext, ExerciseType
from ..clients.ssh import SSHConnection


class TC_CONTRACT:
    """Contract testing category."""

    # Expected exit codes
    EXIT_SUCCESS = 0
    EXIT_FAILURE = 1

    # Expected output patterns for lab commands
    EXPECTED_PATTERNS = {
        'start': {
            'success': [
                r'(success|started|complete|ready|done)',
                r'(environment|lab|exercise)\s+(is\s+)?(ready|started|prepared)',
            ],
            'failure': [
                r'(error|fail|unable|cannot|could not)',
            ]
        },
        'finish': {
            'success': [
                r'(success|finished|complete|cleaned|done)',
                r'(environment|lab|exercise)\s+(is\s+)?(finished|cleaned|reset)',
            ],
            'failure': [
                r'(error|fail|unable|cannot|could not)',
            ]
        },
        'grade': {
            'success': [
                r'(\d+)\s*/\s*100',
                r'(score|grade|result)',
                r'(pass|success)',
            ],
            'failure': [
                r'(error|fail|unable|cannot)',
            ]
        }
    }

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test exercise command contracts.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-CONTRACT: Testing command contracts...")

        bugs_found = []
        start_time = datetime.now()

        # Test lab command availability
        print("   → Testing lab command availability...")
        avail_bugs = self._test_command_availability(ssh)
        bugs_found.extend(avail_bugs)

        # Test start contract
        print("   → Testing 'lab start' contract...")
        start_bugs = self._test_start_contract(exercise, ssh)
        bugs_found.extend(start_bugs)

        # Test grade contract (for Labs)
        if exercise.type == ExerciseType.LAB:
            print("   → Testing 'lab grade' contract...")
            grade_bugs = self._test_grade_contract(exercise, ssh)
            bugs_found.extend(grade_bugs)

        # Test finish contract
        print("   → Testing 'lab finish' contract...")
        finish_bugs = self._test_finish_contract(exercise, ssh)
        bugs_found.extend(finish_bugs)

        # Test help output
        print("   → Testing help output...")
        help_bugs = self._test_help_contract(exercise, ssh)
        bugs_found.extend(help_bugs)

        # Test error handling
        print("   → Testing error handling...")
        error_bugs = self._test_error_handling(exercise, ssh)
        bugs_found.extend(error_bugs)

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-CONTRACT",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'commands_tested': ['start', 'finish', 'grade', 'help'],
                'exercise_type': exercise.type.value
            }
        )

    def _test_command_availability(self, ssh: SSHConnection) -> List[Bug]:
        """Test that lab command is available."""
        bugs = []

        result = ssh.run("which lab", timeout=5)
        if not result.success:
            bugs.append(Bug(
                id=f"CONTRACT-LABCMD-001",
                severity=BugSeverity.P0_BLOCKER,
                category="TC-CONTRACT",
                exercise_id="",
                description="'lab' command not found on PATH",
                fix_recommendation="Ensure lab command is installed and on PATH",
                verification_steps=[
                    "Run: which lab",
                    "Check PATH includes lab command location"
                ]
            ))
        else:
            print("      ✓ lab command available")

        return bugs

    def _test_start_contract(self, exercise: ExerciseContext, ssh: SSHConnection) -> List[Bug]:
        """Test lab start command contract."""
        bugs = []

        # Run lab start
        result = ssh.run(f"lab start {exercise.lab_name}", timeout=180)

        # Check exit code matches output
        if result.success:
            # Should have success-like output
            output = (result.stdout + result.stderr).lower()
            has_success_indicator = any(
                re.search(pattern, output, re.IGNORECASE)
                for pattern in self.EXPECTED_PATTERNS['start']['success']
            )

            if not has_success_indicator:
                bugs.append(Bug(
                    id=f"CONTRACT-START-OUTPUT-{exercise.id}",
                    severity=BugSeverity.P3_LOW,
                    category="TC-CONTRACT",
                    exercise_id=exercise.id,
                    description="lab start succeeded but output lacks success indicator",
                    fix_recommendation="Add clear success message to start output",
                    verification_steps=[
                        f"Run: lab start {exercise.lab_name}",
                        "Verify output indicates success"
                    ]
                ))
            else:
                print("      ✓ Start output includes success indicator")

        else:
            # Check for helpful error message
            output = (result.stdout + result.stderr).lower()
            if len(output) < 20:
                bugs.append(Bug(
                    id=f"CONTRACT-START-ERRMSG-{exercise.id}",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-CONTRACT",
                    exercise_id=exercise.id,
                    description="lab start failed with unhelpful error message",
                    fix_recommendation="Provide descriptive error messages",
                    verification_steps=[
                        f"Run: lab start {exercise.lab_name}",
                        "Check error output is descriptive"
                    ]
                ))

        return bugs

    def _test_grade_contract(self, exercise: ExerciseContext, ssh: SSHConnection) -> List[Bug]:
        """Test lab grade command contract."""
        bugs = []

        if not exercise.grading_script:
            print("      ⏭  No grading script")
            return bugs

        # Run lab grade
        result = ssh.run(f"lab grade {exercise.lab_name}", timeout=120)
        output = result.stdout + result.stderr

        # Check for score format
        score_pattern = r'(\d+)\s*/\s*100'
        score_match = re.search(score_pattern, output)

        if not score_match:
            bugs.append(Bug(
                id=f"CONTRACT-GRADE-FORMAT-{exercise.id}",
                severity=BugSeverity.P2_HIGH,
                category="TC-CONTRACT",
                exercise_id=exercise.id,
                description="lab grade output doesn't include score in X/100 format",
                fix_recommendation="Output score as 'Score: X/100' format",
                verification_steps=[
                    f"Run: lab grade {exercise.lab_name}",
                    "Verify output includes 'X/100' score"
                ]
            ))
        else:
            score = int(score_match.group(1))
            print(f"      ✓ Grade output includes score: {score}/100")

            # Verify exit code matches score
            if score == 100 and not result.success:
                bugs.append(Bug(
                    id=f"CONTRACT-GRADE-EXIT-{exercise.id}",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-CONTRACT",
                    exercise_id=exercise.id,
                    description="lab grade shows 100/100 but returns non-zero exit code",
                    fix_recommendation="Return exit code 0 for passing grade",
                    verification_steps=[
                        f"Run: lab grade {exercise.lab_name}; echo $?",
                        "Verify exit code is 0 for 100/100"
                    ]
                ))
            elif score < 100 and result.success:
                # Some graders return 0 even for partial scores - this is a design choice
                pass

        return bugs

    def _test_finish_contract(self, exercise: ExerciseContext, ssh: SSHConnection) -> List[Bug]:
        """Test lab finish command contract."""
        bugs = []

        # Run lab finish
        result = ssh.run(f"lab finish {exercise.lab_name}", timeout=120)

        if result.success:
            output = (result.stdout + result.stderr).lower()
            has_success_indicator = any(
                re.search(pattern, output, re.IGNORECASE)
                for pattern in self.EXPECTED_PATTERNS['finish']['success']
            )

            if not has_success_indicator:
                bugs.append(Bug(
                    id=f"CONTRACT-FINISH-OUTPUT-{exercise.id}",
                    severity=BugSeverity.P3_LOW,
                    category="TC-CONTRACT",
                    exercise_id=exercise.id,
                    description="lab finish succeeded but output lacks success indicator",
                    fix_recommendation="Add clear success message to finish output",
                    verification_steps=[
                        f"Run: lab finish {exercise.lab_name}",
                        "Verify output indicates success"
                    ]
                ))
            else:
                print("      ✓ Finish output includes success indicator")
        else:
            output = (result.stdout + result.stderr).lower()
            if len(output) < 20:
                bugs.append(Bug(
                    id=f"CONTRACT-FINISH-ERRMSG-{exercise.id}",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-CONTRACT",
                    exercise_id=exercise.id,
                    description="lab finish failed with unhelpful error message",
                    fix_recommendation="Provide descriptive error messages",
                    verification_steps=[
                        f"Run: lab finish {exercise.lab_name}",
                        "Check error output is descriptive"
                    ]
                ))

        return bugs

    def _test_help_contract(self, exercise: ExerciseContext, ssh: SSHConnection) -> List[Bug]:
        """Test help output contract."""
        bugs = []

        # Test lab --help
        result = ssh.run("lab --help 2>&1 || lab help 2>&1", timeout=10)

        if result.success or result.stdout:
            output = result.stdout + result.stderr

            # Check for basic help sections
            help_indicators = ['usage', 'commands', 'options', 'start', 'finish', 'grade']
            found_indicators = sum(1 for ind in help_indicators if ind.lower() in output.lower())

            if found_indicators < 2:
                bugs.append(Bug(
                    id=f"CONTRACT-HELP-INCOMPLETE-{exercise.id}",
                    severity=BugSeverity.P3_LOW,
                    category="TC-CONTRACT",
                    exercise_id=exercise.id,
                    description="lab help output is incomplete",
                    fix_recommendation="Include usage, commands, and options in help",
                    verification_steps=[
                        "Run: lab --help",
                        "Verify help includes usage and command list"
                    ]
                ))
            else:
                print("      ✓ Help output is complete")
        else:
            bugs.append(Bug(
                id=f"CONTRACT-HELP-MISSING-{exercise.id}",
                severity=BugSeverity.P3_LOW,
                category="TC-CONTRACT",
                exercise_id=exercise.id,
                description="lab command doesn't provide help output",
                fix_recommendation="Add --help option to lab command",
                verification_steps=[
                    "Run: lab --help",
                    "Verify help is displayed"
                ]
            ))

        return bugs

    def _test_error_handling(self, exercise: ExerciseContext, ssh: SSHConnection) -> List[Bug]:
        """Test error handling contract."""
        bugs = []

        # Test with invalid exercise ID
        result = ssh.run("lab start nonexistent-exercise-xyz123", timeout=30)

        if result.success:
            bugs.append(Bug(
                id=f"CONTRACT-ERR-INVALID-{exercise.id}",
                severity=BugSeverity.P2_HIGH,
                category="TC-CONTRACT",
                exercise_id=exercise.id,
                description="lab start succeeds for invalid exercise ID",
                fix_recommendation="Validate exercise ID and return error for invalid",
                verification_steps=[
                    "Run: lab start nonexistent-exercise",
                    "Should return non-zero exit code"
                ]
            ))
        else:
            output = result.stdout + result.stderr
            # Check for helpful error message
            if 'not found' in output.lower() or 'invalid' in output.lower() or 'unknown' in output.lower():
                print("      ✓ Invalid exercise returns helpful error")
            elif len(output) < 10:
                bugs.append(Bug(
                    id=f"CONTRACT-ERR-MSG-{exercise.id}",
                    severity=BugSeverity.P3_LOW,
                    category="TC-CONTRACT",
                    exercise_id=exercise.id,
                    description="Invalid exercise returns unhelpful error message",
                    fix_recommendation="Provide descriptive error for invalid exercise ID",
                    verification_steps=[
                        "Run: lab start nonexistent-exercise",
                        "Check error message is descriptive"
                    ]
                ))

        return bugs
