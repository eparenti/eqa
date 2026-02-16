"""Test orchestration - runs test categories in the correct order."""

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import (
    ExerciseContext, ExerciseTestResults, TestResult,
    Bug, BugSeverity
)
from .ssh import SSHConnection
from .tests import (
    TC_PREREQ, TC_STUDENTSIM, TC_SOL, TC_GRADE, TC_IDEM, TC_CLEAN
)


class TestOrchestrator:
    """Orchestrates test category execution for exercises.

    Runs test categories in order:
    1. TC-PREREQ (if P0 fails, stop)
    2. TC-STUDENTSIM
    3. TC-SOL
    4. TC-GRADE (Labs only)
    5. TC-IDEM
    6. TC-CLEAN

    Reuses SSH connection and EPUB extraction across exercises.
    """

    def __init__(self, epub_path: Path,
                 workstation: str = "workstation",
                 timeout_lab: int = 300,
                 timeout_command: int = 120,
                 interactive: bool = True,
                 lesson_code: Optional[str] = None):
        self.epub_path = epub_path
        self.workstation = workstation
        self.timeout_lab = timeout_lab
        self.timeout_command = timeout_command
        self.interactive = interactive
        self.lesson_code = lesson_code
        self.ssh: Optional[SSHConnection] = None

        # Reuse TC_STUDENTSIM across exercises (shares EPUB extraction)
        self._studentsim = TC_STUDENTSIM(
            epub_path=self.epub_path,
            timeout_command=self.timeout_command,
        )

    def close(self):
        """Clean up shared resources."""
        if self.ssh:
            self.ssh.close()
            self.ssh = None
        self._studentsim.cleanup()

    def _ensure_connection(self, exercise: ExerciseContext) -> bool:
        """Ensure SSH connection is established, reusing existing if alive.

        Returns True if connected, False if user chose to skip/abort.
        """
        # Reuse existing connection if still alive
        if self.ssh and self.ssh.is_connected():
            if self.ssh.test_connection():
                return True
            # Connection died, clean up and reconnect
            self.ssh.close()
            self.ssh = None

        # Create new connection
        self.ssh = SSHConnection(self.workstation)
        max_connection_attempts = 5

        for attempt in range(max_connection_attempts):
            if self.ssh.connect():
                return True

            choice = self._prompt_connection_retry(exercise)
            if choice == 'retry':
                print(f"\nRetrying connection to {self.workstation}...")
                time.sleep(1)
                continue
            elif choice == 'abort':
                print("\n❌ Testing aborted by user")
                sys.exit(1)
            else:  # skip
                return False

        return False

    def _prompt_connection_retry(self, exercise: ExerciseContext) -> str:
        """Prompt user when SSH connection fails.

        Returns: 'retry', 'skip', or 'abort'
        """
        if not self.interactive:
            return 'skip'

        print(f"\n{'='*60}")
        print(f"⚠️  Cannot connect to workstation: {self.workstation}")
        print(f"{'='*60}")
        print("\nTo test this exercise, you need:")
        print(f"  1. A running lab environment for {exercise.id}")
        print(f"  2. SSH access configured to '{self.workstation}'")
        print(f"  3. Lab framework installed (DynoLabs v5)")
        print("\nCommands to verify:")
        print(f"  $ ssh {self.workstation} hostname")
        print(f"  $ ssh {self.workstation} 'lab --version'")
        print(f"  $ ssh {self.workstation} 'lab list | grep {exercise.id}'")
        print("\nOptions:")
        print("  [R] Retry - Try connecting again (I'm setting up the environment)")
        print("  [S] Skip  - Skip this exercise and continue with the next one")
        print("  [A] Abort - Stop all testing")

        while True:
            try:
                choice = input("\nYour choice [R/s/a]: ").strip().lower()
                if not choice or choice == 'r':
                    return 'retry'
                elif choice == 's':
                    return 'skip'
                elif choice == 'a':
                    return 'abort'
                else:
                    print(f"Invalid choice: '{choice}'. Please enter R, S, or A.")
            except (EOFError, KeyboardInterrupt):
                print("\n\nInterrupted by user.")
                return 'abort'

    def test_exercise(self, exercise: ExerciseContext) -> ExerciseTestResults:
        """Run all test categories for an exercise."""
        start_time = datetime.now()
        test_categories = {}
        all_bugs = []

        print(f"\n{'='*60}")
        print(f"TESTING: {exercise.id} ({exercise.type.value})")
        print(f"{'='*60}")

        # Connect to workstation (reusing existing connection if alive)
        if not self._ensure_connection(exercise):
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            if self.ssh and not self.ssh.is_connected():
                return ExerciseTestResults(
                    exercise_id=exercise.id,
                    lesson_code=exercise.lesson_code,
                    start_time=start_time.isoformat(),
                    end_time=end_time.isoformat(),
                    duration_seconds=duration,
                    status="ERROR",
                    test_categories={},
                    bugs=[Bug(
                        id=f"SSH-CONN-{exercise.id}",
                        severity=BugSeverity.P0_BLOCKER,
                        category="INFRASTRUCTURE",
                        exercise_id=exercise.id,
                        description=f"Cannot connect to {self.workstation}",
                        fix_recommendation="Check SSH configuration and network",
                        verification_steps=[f"ssh {self.workstation} hostname"]
                    )],
                    summary="Failed to connect to workstation"
                )

            return ExerciseTestResults(
                exercise_id=exercise.id,
                lesson_code=exercise.lesson_code,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                duration_seconds=duration,
                status="SKIP",
                test_categories={},
                bugs=[],
                summary="Skipped - no workstation connection"
            )

        try:
            # Install lesson for multi-repo courses
            if self.lesson_code:
                print(f"\n   Installing lesson: {self.lesson_code}")
                install_result = self.ssh.force_lesson(self.lesson_code, timeout=self.timeout_lab)
                if not install_result.success:
                    print(f"   Warning: lab install failed: {(install_result.stderr or install_result.stdout)[:200]}")

            # 1. TC-PREREQ (blocker if fails with P0)
            prereq = TC_PREREQ()
            prereq_result = prereq.test(exercise, self.ssh)
            test_categories['TC-PREREQ'] = prereq_result
            all_bugs.extend(prereq_result.bugs_found)

            # Check for P0 blocker
            has_p0 = any(b.severity == BugSeverity.P0_BLOCKER
                         for b in prereq_result.bugs_found)
            if has_p0:
                print(f"\n   P0 BLOCKER found in TC-PREREQ - stopping tests")
                status = "FAIL"
            else:
                # 2. TC-STUDENTSIM (reuses shared instance for EPUB caching)
                studentsim_result = self._studentsim.test(exercise, self.ssh)
                test_categories['TC-STUDENTSIM'] = studentsim_result
                all_bugs.extend(studentsim_result.bugs_found)

                # 3. TC-SOL
                sol = TC_SOL()
                sol_result = sol.test(exercise, self.ssh)
                test_categories['TC-SOL'] = sol_result
                all_bugs.extend(sol_result.bugs_found)

                # 4. TC-GRADE (Labs only)
                grade = TC_GRADE()
                grade_result = grade.test(exercise, self.ssh)
                test_categories['TC-GRADE'] = grade_result
                all_bugs.extend(grade_result.bugs_found)

                # 5. TC-IDEM
                idem = TC_IDEM()
                idem_result = idem.test(exercise, self.ssh, cycles=2)
                test_categories['TC-IDEM'] = idem_result
                all_bugs.extend(idem_result.bugs_found)

                # 6. TC-CLEAN
                clean = TC_CLEAN()
                clean_result = clean.test(exercise, self.ssh)
                test_categories['TC-CLEAN'] = clean_result
                all_bugs.extend(clean_result.bugs_found)

                # Determine overall status
                if all(tc.passed for tc in test_categories.values()):
                    status = "PASS"
                else:
                    status = "FAIL"

        except Exception as e:
            # Unexpected error during testing
            error_bug = Bug(
                id=f"ERROR-{exercise.id}",
                severity=BugSeverity.P0_BLOCKER,
                category="INFRASTRUCTURE",
                exercise_id=exercise.id,
                description=f"Unexpected error during testing: {str(e)}",
                fix_recommendation="Check test infrastructure",
                verification_steps=[]
            )
            all_bugs.append(error_bug)
            status = "ERROR"

        # NOTE: Don't close SSH here - it's reused across exercises.
        # Call self.close() after all exercises are tested.

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Generate summary
        passed = sum(1 for tc in test_categories.values() if tc.passed)
        total = len(test_categories)
        summary = f"{status}: {passed}/{total} test categories passed, {len(all_bugs)} bugs found"

        return ExerciseTestResults(
            exercise_id=exercise.id,
            lesson_code=exercise.lesson_code,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            status=status,
            test_categories=test_categories,
            bugs=all_bugs,
            summary=summary
        )
