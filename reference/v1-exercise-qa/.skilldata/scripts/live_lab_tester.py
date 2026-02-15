#!/usr/bin/env python3
"""
Live Lab Environment Tester

Tests exercises in live lab environments by executing actual lab commands
and following student workflows.

This script tests exercises in live lab environments using real systems.

Workflow:
1. SSH to workstation
2. Run `lab start <exercise-name>` - auto-installs course if needed
3. Exercise files placed in ~/<COURSE-SKU>/labs/<exercise-name>/
4. Solutions in ~/<COURSE-SKU>/solutions/<exercise-name>/
5. Execute exercise steps from EPUB
6. For Labs: Run `lab grade <exercise-name>`
7. Run `lab finish <exercise-name>` to cleanup
8. Verify cleanup completed

Lab command behavior:
- Automatically installs course packages from PyPI
- Creates exercise directories under ~/DO<courseSKU>/labs/
- Cleanup via lab finish removes projects and files
- Must run from ~/ (home directory)
"""

import sys
import re
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.ssh_connection import SSHConnection
from lib.state_capture import capture_system_state, compare_states
from lib.test_result import TestResult, Bug, BugSeverity, ExerciseContext


class LiveLabTester:
    """
    Tests exercises in live lab environments using actual lab commands.

    Uses real lab environment exactly as students do.
    """

    def __init__(self, workstation: str = "workstation"):
        """
        Initialize live lab tester.

        Args:
            workstation: Hostname from ~/.ssh/config (default: workstation)
        """
        self.workstation = workstation
        self.ssh = SSHConnection(workstation, username="student")

    def test_exercise_live(self, exercise: ExerciseContext) -> TestResult:
        """
        Test exercise in live lab environment.

        This runs the exercise on real systems.

        Args:
            exercise: Exercise context with EPUB content

        Returns:
            TestResult with live test results
        """
        start_time = datetime.now()
        bugs_found = []

        print(f"\n🔴 LIVE LAB TEST: {exercise.id}")
        print("=" * 60)

        # Step 1: Verify SSH connectivity
        print("1. Testing SSH connection to workstation...")
        if not self.ssh.test_connection():
            return TestResult(
                category="TC-PREREQ",
                exercise_id=exercise.id,
                passed=False,
                timestamp=start_time.isoformat(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                error_message=f"Cannot connect to workstation: {self.workstation}"
            )
        print("   ✅ SSH connection OK")

        # Step 2: Capture initial state
        print("\n2. Capturing initial system state...")
        initial_state = capture_system_state(self.ssh, exercise.id)
        print("   ✅ Initial state captured")

        # Step 3: Run lab start
        print(f"\n3. Running: lab start {exercise.id}")
        start_result = self.ssh.run(
            f"cd ~ && lab start {exercise.id}",
            timeout=600  # 10 minutes for setup
        )

        if start_result.return_code != 0:
            bug = Bug(
                id=f"BUG-{exercise.id.upper()}-LABSTART",
                severity=BugSeverity.P0_BLOCKER,
                exercise_id=exercise.id,
                category="TC-PREREQ",
                description=f"lab start {exercise.id} failed",
                fix_recommendation=f"Check lab environment setup for {exercise.id}",
                verification_steps=[
                    "Check if OpenShift cluster is accessible",
                    "Verify all required VMs are running",
                    f"Run: lab status {exercise.id}"
                ]
            )
            bugs_found.append(bug)

            return TestResult(
                category="TC-PREREQ",
                exercise_id=exercise.id,
                passed=False,
                timestamp=start_time.isoformat(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                error_message=f"lab start failed: {start_result.stderr}",
                bugs_found=bugs_found
            )

        print("   ✅ Lab started successfully")

        # Step 4: Verify exercise files created
        print("\n4. Verifying exercise files created...")
        lab_dir_check = self.ssh.run(f"ls -la ~/DO*/labs/{exercise.id}/ 2>&1")
        if lab_dir_check.return_code == 0:
            print(f"   ✅ Exercise directory created:")
            print(f"      {lab_dir_check.stdout.strip()}")
        else:
            print(f"   ⚠️  No exercise directory (may be normal for some exercises)")

        # Step 5: Check for solution files
        print("\n5. Checking for solution files...")
        sol_check = self.ssh.run(f"find ~/DO*/solutions/{exercise.id}/ -name '*.sol' 2>&1")
        solution_files = []
        if sol_check.return_code == 0 and sol_check.stdout.strip():
            solution_files = sol_check.stdout.strip().split('\n')
            print(f"   ✅ Found {len(solution_files)} solution file(s):")
            for sol in solution_files:
                print(f"      - {sol}")
        else:
            print("   ℹ️  No solution files (Guided Exercise)")

        # Step 6: Execute EPUB steps (if provided)
        if exercise.epub_content:
            print("\n6. Executing EPUB workflow steps...")
            epub_result = self._execute_epub_steps(exercise)
            if not epub_result.passed:
                bugs_found.extend(epub_result.bugs_found)

        # Step 7: Test grading (for Labs)
        grade_passed = True
        if exercise.type.value == "lab":
            print(f"\n7. Testing lab grading: lab grade {exercise.id}")
            grade_result = self._test_grading(exercise, solution_files)
            grade_passed = grade_result.passed
            bugs_found.extend(grade_result.bugs_found)

        # Step 8: Capture state after exercise
        print("\n8. Capturing state after exercise...")
        after_state = capture_system_state(self.ssh, exercise.id)
        print("   ✅ After-exercise state captured")

        # Step 9: Run lab finish
        print(f"\n9. Running: lab finish {exercise.id}")
        finish_result = self.ssh.run(
            f"cd ~ && lab finish {exercise.id}",
            timeout=600
        )

        if finish_result.return_code != 0:
            bug = Bug(
                id=f"BUG-{exercise.id.upper()}-LABFINISH",
                severity=BugSeverity.P1_CRITICAL,
                exercise_id=exercise.id,
                category="TC-CLEAN",
                description=f"lab finish {exercise.id} failed: {finish_result.stderr}",
                fix_recommendation="Review lab finish script for errors",
                verification_steps=[f"Run: lab status {exercise.id}"]
            )
            bugs_found.append(bug)
        else:
            print("   ✅ Lab finished successfully")

        # Step 10: Verify cleanup
        print("\n10. Verifying cleanup completed...")
        final_state = capture_system_state(self.ssh, exercise.id)

        # Compare final state with initial state
        diff = compare_states(initial_state, final_state)
        if diff.users_added or diff.groups_added or diff.files_added or diff.services_added:
            print("   ⚠️  Cleanup incomplete - artifacts remain:")
            if diff.users_added:
                print(f"      Users: {', '.join(diff.users_added)}")
            if diff.files_added:
                print(f"      Files: {len(diff.files_added)} files remain")

            bug = Bug(
                id=f"BUG-{exercise.id.upper()}-CLEANUP",
                severity=BugSeverity.P1_CRITICAL,
                exercise_id=exercise.id,
                category="TC-CLEAN",
                description=f"Incomplete cleanup - artifacts remain after lab finish. Users: {diff.users_added}, Files: {len(diff.files_added)}",
                fix_recommendation="Update lab finish script to remove all created resources",
                verification_steps=[
                    f"Run: lab start {exercise.id}",
                    f"Run: lab finish {exercise.id}",
                    "Compare system state before/after"
                ]
            )
            bugs_found.append(bug)
        else:
            print("   ✅ Cleanup complete - no artifacts remain")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        overall_passed = (len(bugs_found) == 0) and grade_passed

        print("\n" + "=" * 60)
        print(f"LIVE TEST RESULT: {'✅ PASS' if overall_passed else '❌ FAIL'}")
        print(f"Duration: {duration:.1f}s")
        print(f"Bugs Found: {len(bugs_found)}")
        print("=" * 60)

        return TestResult(
            category="TC-LIVE",
            exercise_id=exercise.id,
            passed=overall_passed,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'workstation': self.workstation,
                'solution_files_found': len(solution_files),
                'cleanup_complete': (len(bugs_found) == 0)
            }
        )

    def _execute_epub_steps(self, exercise: ExerciseContext) -> TestResult:
        """
        Execute steps from EPUB content.

        Parses EPUB for commands and executes them.

        Args:
            exercise: Exercise context with EPUB content

        Returns:
            TestResult with execution results
        """
        start_time = datetime.now()
        bugs_found = []

        # Extract commands from EPUB (simple approach - look for command blocks)
        commands = self._extract_commands_from_epub(exercise.epub_content)

        if not commands:
            print("   ℹ️  No commands found in EPUB content")
            return TestResult(
                category="TC-EXEC",
                exercise_id=exercise.id,
                passed=True,
                timestamp=start_time.isoformat(),
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )

        print(f"   Found {len(commands)} command(s) to execute")

        passed_count = 0
        for i, cmd in enumerate(commands, 1):
            print(f"   Step {i}/{len(commands)}: {cmd[:60]}...")
            result = self.ssh.run(f"cd ~ && {cmd}", timeout=300)

            if result.return_code != 0:
                print(f"      ❌ Command failed")
                bug = Bug(
                    id=f"BUG-{exercise.id.upper()}-STEP{i}",
                    severity=BugSeverity.P0_BLOCKER,
                    exercise_id=exercise.id,
                    category="TC-EXEC",
                    description=f"EPUB step {i} failed: {cmd[:100]}. Error: {result.stderr[:200] if result.stderr else result.stdout[:200]}",
                    fix_recommendation="Review EPUB instructions for accuracy",
                    verification_steps=[f"Manually execute: {cmd}"]
                )
                bugs_found.append(bug)
            else:
                print(f"      ✅ Success")
                passed_count += 1

        print(f"   Results: {passed_count}/{len(commands)} steps passed")

        return TestResult(
            category="TC-EXEC",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=start_time.isoformat(),
            duration_seconds=(datetime.now() - start_time).total_seconds(),
            bugs_found=bugs_found
        )

    def _extract_commands_from_epub(self, epub_content: str) -> List[str]:
        """
        Extract executable commands from EPUB content.

        Looks for command blocks, code blocks, and shell commands.

        Args:
            epub_content: EPUB HTML/text content

        Returns:
            List of commands to execute
        """
        if not epub_content:
            return []

        commands = []

        # Look for command patterns:
        # 1. Lines starting with $
        # 2. Lines in <code> blocks
        # 3. Lines after "Run:" or "Execute:"

        lines = epub_content.split('\n')
        for line in lines:
            line = line.strip()

            # Shell prompt pattern: $ command
            if re.match(r'^\$\s+(.+)$', line):
                cmd = re.sub(r'^\$\s+', '', line)
                commands.append(cmd)

            # Command after "Run:"
            elif re.match(r'^Run:\s+(.+)$', line, re.I):
                cmd = re.sub(r'^Run:\s+', '', line, flags=re.I)
                commands.append(cmd)

        return commands

    def _test_grading(self, exercise: ExerciseContext, solution_files: List[str]) -> TestResult:
        """
        Test lab grading with and without solutions.

        Args:
            exercise: Exercise context
            solution_files: List of solution file paths

        Returns:
            TestResult with grading test results
        """
        start_time = datetime.now()
        bugs_found = []

        # Scenario 1: Grade WITH solutions applied
        if solution_files:
            print("   Scenario 1: WITH solutions")

            # Copy and apply solution files
            for sol_file in solution_files:
                base_name = sol_file.replace('.sol', '')
                print(f"      Applying: {Path(sol_file).name}")
                self.ssh.run(f"cp {sol_file} {base_name}")

            # Run grading
            grade_result = self.ssh.run(f"cd ~ && lab grade {exercise.id}", timeout=300)

            if grade_result.return_code != 0 or "FAIL" in grade_result.stdout:
                bug = Bug(
                    id=f"BUG-{exercise.id.upper()}-GRADE-WITH",
                    severity=BugSeverity.P1_CRITICAL,
                    exercise_id=exercise.id,
                    category="TC-GRADE",
                    description=f"Grading failed WITH solution applied (should PASS). Output: {grade_result.stdout[:200]}",
                    fix_recommendation="Review solution files and grading script",
                    verification_steps=[
                        "Apply solutions manually",
                        f"Run: lab grade {exercise.id}",
                        "Should show 100/100"
                    ]
                )
                bugs_found.append(bug)
                print("      ❌ Grading failed (SHOULD PASS)")
            else:
                print("      ✅ Grading passed")

        # Scenario 2: Grade WITHOUT solutions
        print("   Scenario 2: WITHOUT solutions")

        # Reset environment
        self.ssh.run(f"cd ~ && lab finish {exercise.id}", timeout=300)
        time.sleep(2)
        self.ssh.run(f"cd ~ && lab start {exercise.id}", timeout=600)

        # Grade without solutions
        grade_result = self.ssh.run(f"cd ~ && lab grade {exercise.id}", timeout=300)

        if "PASS" in grade_result.stdout or grade_result.return_code == 0:
            bug = Bug(
                id=f"BUG-{exercise.id.upper()}-GRADE-WITHOUT",
                severity=BugSeverity.P1_CRITICAL,
                exercise_id=exercise.id,
                category="TC-GRADE",
                description=f"Grading PASSED without solution (should FAIL). False positive - grading passes incorrectly. Output: {grade_result.stdout[:200]}",
                fix_recommendation="Review grading script - may have false positives",
                verification_steps=[
                    f"Run: lab start {exercise.id}",
                    f"Run: lab grade {exercise.id} (without applying solutions)",
                    "Should show FAIL"
                ]
            )
            bugs_found.append(bug)
            print("      ❌ Grading passed (SHOULD FAIL)")
        else:
            print("      ✅ Grading failed as expected")

        return TestResult(
            category="TC-GRADE",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=start_time.isoformat(),
            duration_seconds=(datetime.now() - start_time).total_seconds(),
            bugs_found=bugs_found
        )


def main():
    """Test live lab tester."""
    import argparse
    from lib.test_result import ExerciseType

    parser = argparse.ArgumentParser(description="Test exercise in live lab environment")
    parser.add_argument("exercise_id", help="Exercise ID (e.g., accessing-clicreate)")
    parser.add_argument("--workstation", default="workstation", help="Workstation hostname")
    parser.add_argument("--type", choices=['ge', 'lab'], default='ge', help="Exercise type")

    args = parser.parse_args()

    # Create exercise context
    exercise = ExerciseContext(
        id=args.exercise_id,
        type=ExerciseType.GUIDED_EXERCISE if args.type == 'ge' else ExerciseType.LAB,
        lesson_code="unknown",
        chapter=1,
        chapter_title="Test",
        title=args.exercise_id
    )

    # Run live test
    tester = LiveLabTester(workstation=args.workstation)
    result = tester.test_exercise_live(exercise)

    print("\n" + "=" * 60)
    print(f"FINAL RESULT: {'PASS' if result.passed else 'FAIL'}")
    print(f"Duration: {result.duration_seconds:.1f}s")
    print(f"Bugs: {len(result.bugs_found)}")
    print("=" * 60)

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
