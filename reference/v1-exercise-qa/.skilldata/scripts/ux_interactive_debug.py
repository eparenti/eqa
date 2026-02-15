#!/usr/bin/env python3
"""
Interactive Debugging Mode

Provides interactive debugging capabilities when tests fail:
- Pause on test failure
- Show detailed error context
- Offer debugging commands
- Allow re-running tests
- Inspect system state
"""

import sys
import cmd
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.ssh_connection import SSHConnection
from lib.test_result import Bug, TestResult


class InteractiveDebugger(cmd.Cmd):
    """
    Interactive debugger for test failures.

    Allows inspecting failures, running commands, and retrying tests.
    """

    intro = """
╔══════════════════════════════════════════════════════════════╗
║           Exercise QA - Interactive Debugger                 ║
╚══════════════════════════════════════════════════════════════╝

Test failed. You can now:
  - Inspect the failure with 'show'
  - Run commands with 'run <command>'
  - Check logs with 'logs'
  - Retry the test with 'retry'
  - Continue to next test with 'continue'
  - Exit with 'quit'

Type 'help' for all commands.
"""

    prompt = "(debug) "

    def __init__(self, test_result: TestResult, ssh: SSHConnection,
                 exercise_context: Any):
        """
        Initialize debugger.

        Args:
            test_result: Failed test result
            ssh: SSH connection
            exercise_context: Exercise context
        """
        super().__init__()
        self.test_result = test_result
        self.ssh = ssh
        self.exercise = exercise_context
        self.should_continue = False
        self.should_retry = False

    def do_show(self, arg):
        """Show test failure details: show [bugs|result|context]"""
        if not arg or arg == 'bugs':
            self._show_bugs()
        elif arg == 'result':
            self._show_result()
        elif arg == 'context':
            self._show_context()
        else:
            print(f"Unknown option: {arg}")
            print("Usage: show [bugs|result|context]")

    def do_run(self, command):
        """Run a shell command on the workstation: run <command>"""
        if not command:
            print("Usage: run <command>")
            return

        print(f"Running: {command}")
        result = self.ssh.run(command, timeout=60)

        print("\nOutput:")
        if result['stdout']:
            print(result['stdout'])

        if result['stderr']:
            print("\nErrors:")
            print(result['stderr'])

        print(f"\nExit code: {result['exit_code']}")

    def do_logs(self, arg):
        """View lab logs: logs [exercise-name]"""
        exercise_id = arg if arg else self.exercise.id

        print(f"Fetching logs for: {exercise_id}")
        result = self.ssh.run(f"lab logs {exercise_id}", timeout=30)

        if result['stdout']:
            print("\n" + "=" * 60)
            print(result['stdout'])
            print("=" * 60)
        else:
            print("No logs available or command not found")

    def do_state(self, arg):
        """Show system state: state [users|services|files]"""
        if not arg or arg == 'users':
            self._show_users()
        elif arg == 'services':
            self._show_services()
        elif arg == 'files':
            self._show_files()
        else:
            print(f"Unknown option: {arg}")
            print("Usage: state [users|services|files]")

    def do_fix(self, arg):
        """Show fix recommendations for bugs"""
        for bug in self.test_result.bugs_found:
            print(f"\n{'='*60}")
            print(f"Bug: {bug.id}")
            print(f"Severity: {bug.severity.value}")
            print(f"\nFix Recommendation:")
            print(bug.fix_recommendation)
            print(f"\nVerification Steps:")
            for i, step in enumerate(bug.verification_steps, 1):
                print(f"  {i}. {step}")
            print("=" * 60)

    def do_retry(self, arg):
        """Retry the failed test"""
        self.should_retry = True
        return True  # Exit cmd loop

    def do_continue(self, arg):
        """Continue to next test (alias: c)"""
        self.should_continue = True
        return True  # Exit cmd loop

    def do_c(self, arg):
        """Alias for continue"""
        return self.do_continue(arg)

    def do_quit(self, arg):
        """Exit interactive debugger (alias: q, exit)"""
        return True  # Exit cmd loop

    def do_q(self, arg):
        """Alias for quit"""
        return self.do_quit(arg)

    def do_exit(self, arg):
        """Alias for quit"""
        return self.do_quit(arg)

    def do_help(self, arg):
        """Show help message"""
        if arg:
            # Show help for specific command
            super().do_help(arg)
        else:
            # Show all commands
            print("\nAvailable commands:")
            print("=" * 60)
            print("  show [bugs|result|context] - Show test details")
            print("  run <command>              - Run shell command")
            print("  logs [exercise]            - View lab logs")
            print("  state [users|services|files] - Show system state")
            print("  fix                        - Show bug fix recommendations")
            print("  retry                      - Retry the failed test")
            print("  continue (c)               - Continue to next test")
            print("  quit (q, exit)             - Exit debugger")
            print("  help [command]             - Show this help")
            print("=" * 60)

    def _show_bugs(self):
        """Show bug details."""
        if not self.test_result.bugs_found:
            print("No bugs found in this test")
            return

        print(f"\n{'='*60}")
        print(f"Bugs Found: {len(self.test_result.bugs_found)}")
        print("=" * 60)

        for bug in self.test_result.bugs_found:
            print(f"\n{bug.id}")
            print(f"  Severity: {bug.severity.value}")
            print(f"  Category: {bug.category}")
            print(f"\n  Description:")
            print(f"    {bug.description}")
            print()

    def _show_result(self):
        """Show test result details."""
        print(f"\n{'='*60}")
        print(f"Test Result: {self.test_result.category}")
        print("=" * 60)
        print(f"  Exercise: {self.test_result.exercise_id}")
        print(f"  Passed: {self.test_result.passed}")
        print(f"  Duration: {self.test_result.duration_seconds:.2f}s")
        print(f"  Timestamp: {self.test_result.timestamp}")

        if self.test_result.error_message:
            print(f"\n  Error Message:")
            print(f"    {self.test_result.error_message}")

        if self.test_result.details:
            print(f"\n  Details:")
            for key, value in self.test_result.details.items():
                if isinstance(value, (list, dict)):
                    print(f"    {key}: {len(value)} items")
                else:
                    print(f"    {key}: {value}")

    def _show_context(self):
        """Show exercise context."""
        print(f"\n{'='*60}")
        print(f"Exercise Context: {self.exercise.id}")
        print("=" * 60)
        print(f"  Type: {self.exercise.type.value}")
        print(f"  Lesson Code: {self.exercise.lesson_code}")
        print(f"  Chapter: {self.exercise.chapter}")
        print(f"  Title: {self.exercise.title}")

        if hasattr(self.exercise, 'solution_files') and self.exercise.solution_files:
            print(f"\n  Solution Files: {len(self.exercise.solution_files)}")
            for sol in self.exercise.solution_files[:5]:
                print(f"    - {sol}")

    def _show_users(self):
        """Show system users."""
        print("\nSystem Users:")
        result = self.ssh.run("getent passwd | tail -20", timeout=10)
        if result['stdout']:
            print(result['stdout'])

    def _show_services(self):
        """Show running services."""
        print("\nRunning Services:")
        result = self.ssh.run("systemctl list-units --type=service --state=running | head -20", timeout=10)
        if result['stdout']:
            print(result['stdout'])

    def _show_files(self):
        """Show exercise files."""
        exercise_dir = f"~/DO{self.exercise.lesson_code.upper()}/labs/{self.exercise.id}/"
        print(f"\nExercise Files ({exercise_dir}):")
        result = self.ssh.run(f"ls -la {exercise_dir}", timeout=10)
        if result['stdout']:
            print(result['stdout'])
        else:
            print("  Directory not found or empty")


class DebugMode:
    """
    Debug mode controller.

    Manages when to enter debug mode and handles user interaction.
    """

    def __init__(self, enabled: bool = False, pause_on_error: bool = True):
        """
        Initialize debug mode.

        Args:
            enabled: Enable interactive debugging
            pause_on_error: Pause on test failures
        """
        self.enabled = enabled
        self.pause_on_error = pause_on_error

    def handle_failure(self, test_result: TestResult, ssh: SSHConnection,
                       exercise_context: Any) -> str:
        """
        Handle test failure.

        Args:
            test_result: Failed test result
            ssh: SSH connection
            exercise_context: Exercise context

        Returns:
            Action to take ('continue', 'retry', or 'quit')
        """
        if not self.enabled or not self.pause_on_error:
            return 'continue'

        # Print failure summary
        print("\n" + "!" * 70)
        print(f"  TEST FAILED: {test_result.category} - {test_result.exercise_id}")
        print("!" * 70)

        if test_result.bugs_found:
            print(f"\n  Bugs Found: {len(test_result.bugs_found)}")
            for bug in test_result.bugs_found[:3]:  # Show first 3
                print(f"    - [{bug.severity.value}] {bug.description[:60]}...")

        # Enter interactive debugger
        debugger = InteractiveDebugger(test_result, ssh, exercise_context)
        debugger.cmdloop()

        # Determine action
        if debugger.should_retry:
            return 'retry'
        elif debugger.should_continue:
            return 'continue'
        else:
            return 'quit'

    def quick_inspect(self, message: str, ssh: SSHConnection, command: Optional[str] = None):
        """
        Quick inspection point.

        Args:
            message: Inspection message
            ssh: SSH connection
            command: Optional command to run for inspection
        """
        if not self.enabled:
            return

        print(f"\n🔍 Inspection: {message}")

        if command:
            result = ssh.run(command, timeout=30)
            if result['stdout']:
                print(result['stdout'])


def example_usage():
    """Example of using debug mode."""
    from lib.test_result import TestResult, Bug, BugSeverity, ExerciseContext, ExerciseType

    # Create mock objects
    ssh = SSHConnection("workstation")

    exercise = ExerciseContext(
        id="<exercise-name>",
        type=ExerciseType.GUIDED_EXERCISE,
        lesson_code="<lesson-code>",
        chapter=2,
        chapter_title="Implementing Playbooks",
        title="Using Flow Control"
    )

    # Create mock failure
    test_result = TestResult(
        category="TC-IDEM",
        exercise_id="<exercise-name>",
        passed=False,
        timestamp="2026-01-10T15:30:00",
        duration_seconds=45.2,
        bugs_found=[
            Bug(
                id="BUG-CONTROL-FLOW-IDEM-001",
                severity=BugSeverity.P1_CRITICAL,
                exercise_id="<exercise-name>",
                category="TC-IDEM",
                description="Exercise directory not removed after lab finish",
                fix_recommendation="Update finish.yml to remove directory",
                verification_steps=[
                    "1. Edit finish.yml",
                    "2. Add directory removal task",
                    "3. Test lab finish"
                ]
            )
        ],
        error_message="Idempotency check failed",
        details={'cycles_tested': 3, 'failed_at_cycle': 2}
    )

    # Create debug mode
    debug = DebugMode(enabled=True)

    # Handle failure
    action = debug.handle_failure(test_result, ssh, exercise)
    print(f"\nAction selected: {action}")


if __name__ == "__main__":
    example_usage()
