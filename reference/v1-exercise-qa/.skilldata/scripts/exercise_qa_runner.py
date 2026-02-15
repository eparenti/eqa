#!/usr/bin/env python3
"""
Exercise QA Runner - Main entry point for the exercise-qa skill.

This is the unified workflow orchestrator that:
1. Parses user input (exercise ID, course, EPUB path)
2. Analyzes course context
3. Executes all test categories
4. Generates comprehensive report
5. Provides real-time progress feedback

Usage:
    python3 exercise_qa_runner.py <course-or-lesson-code> <exercise-name>
    python3 exercise_qa_runner.py <epub-path> <exercise-name>
    python3 exercise_qa_runner.py <epub-path>  # Test all exercises
"""

import sys
import os
import argparse
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, List

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from lib.test_result import (
    CourseContext, ExerciseContext, ExerciseType,
    TestResult, Bug, BugSeverity
)
from lib.ssh_connection import SSHConnection

# Import testing components
from course_analyzer import CourseAnalyzer
from test_executor import TestExecutor
from test_orchestrator import TestOrchestrator
from report_generator import ReportGenerator
from webapp_integrator import WebAppIntegrator

# Import test categories
from test_categories import (
    TC_IDEM, TC_SOL, TC_EXEC, TC_E2E,
    TC_WORKFLOW, TC_INSTRUCT,
    # v2.0 test categories
    TC_SECURITY, TC_ACCESSIBILITY, TC_CONTRACT
)

# Import utilities
from detect_workstation import detect_workstation
from find_exercise import find_exercise_path
from extract_epub_chapter import extract_from_epub
from lib.terminal_colors import (
    fmt, configure_colors,
    success, error, warning, info, dim,
    passed, failed, category, bug_severity,
    duration, percentage, header, bold
)


class ProgressReporter:
    """Real-time progress reporting with colorized visual feedback."""

    def __init__(self, verbose: bool = True, use_colors: bool = True):
        self.verbose = verbose
        self.current_phase = None
        self.phase_start_time = None
        self.total_phases = 0
        self.completed_phases = 0

        # Configure colors based on preference
        if not use_colors:
            configure_colors(enabled=False)

    def start_phase(self, phase_name: str, total: Optional[int] = None):
        """Start a new phase."""
        self.current_phase = phase_name
        self.phase_start_time = time.time()
        if total:
            self.total_phases = total

        if self.verbose:
            print(f"\n{bold('='*70)}")
            print(f"🔄 {bold(phase_name)}")
            if total and self.completed_phases > 0:
                progress_pct = (self.completed_phases / total) * 100
                print(f"   Progress: {self.completed_phases}/{total} ({percentage(progress_pct)})")
            print(f"{bold('='*70)}")

    def update(self, message: str, status: str = "info"):
        """Update progress with a message."""
        if not self.verbose:
            return

        # Apply color based on status
        if status == "success":
            colored_msg = success(message)
            icon = "✅"
        elif status == "error":
            colored_msg = error(message)
            icon = "❌"
        elif status == "warning":
            colored_msg = warning(message)
            icon = "⚠️"
        elif status == "running":
            colored_msg = info(message)
            icon = "🔄"
        else:
            colored_msg = message
            icon = "ℹ️"

        print(f"  {icon} {colored_msg}")

    def complete_phase(self, phase_success: bool = True):
        """Complete current phase."""
        if self.phase_start_time:
            elapsed = time.time() - self.phase_start_time
            if self.verbose:
                if phase_success:
                    status_msg = success(f"Completed in {duration(elapsed)}")
                    icon = "✅"
                else:
                    status_msg = error(f"Failed after {duration(elapsed)}")
                    icon = "❌"
                print(f"  {icon} {status_msg}")

        self.completed_phases += 1
        self.current_phase = None
        self.phase_start_time = None

    def print_summary(self, results: dict):
        """Print final summary with colors."""
        if not self.verbose:
            return

        print(f"\n{bold('='*70)}")
        print(f"📊 {bold('TESTING SUMMARY')}")
        print(f"{bold('='*70)}")

        total_tests = results.get('total_tests', 0)
        passed_count = results.get('passed', 0)
        failed_count = results.get('failed', 0)

        print(f"  Total Tests: {bold(str(total_tests))}")

        if total_tests > 0:
            pass_pct = passed_count / total_tests * 100
            fail_pct = failed_count / total_tests * 100
            print(f"  ✅ Passed: {success(str(passed_count))} ({percentage(pass_pct)})")
            print(f"  ❌ Failed: {error(str(failed_count)) if failed_count > 0 else dim('0')} ({percentage(100 - pass_pct, good_threshold=100, warn_threshold=80) if failed_count > 0 else dim('0.0%')})")
        else:
            print(f"  ✅ Passed: {dim('0')}")
            print(f"  ❌ Failed: {dim('0')}")

        if results.get('bugs'):
            bug_list = results['bugs']
            print(f"\n  🐛 Bugs Found: {bold(str(len(bug_list)))}")
            severity_counts = {}
            for bug in bug_list:
                sev = bug.get('severity', 'Unknown')
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

            for sev in ['P0', 'P1', 'P2', 'P3']:
                if sev in severity_counts:
                    print(f"     {bug_severity(sev)}: {severity_counts[sev]}")

        print(f"{bold('='*70)}\n")


class ExerciseQARunner:
    """Main orchestrator for exercise QA testing."""

    def __init__(self, verbose: bool = True, cache_enabled: bool = True, use_colors: bool = True):
        """
        Initialize runner.

        Args:
            verbose: Enable detailed progress output
            cache_enabled: Enable caching for performance
            use_colors: Enable colorized terminal output
        """
        self.verbose = verbose
        self.cache_enabled = cache_enabled
        self.use_colors = use_colors
        self.progress = ProgressReporter(verbose, use_colors)
        self.workstation = None
        self.ssh = None
        self.course_context = None

    def detect_input_type(self, input_path: str) -> tuple[str, Optional[Path]]:
        """
        Detect whether input is course code, lesson code, or EPUB path.

        Returns:
            (input_type, epub_path) where input_type is 'course', 'lesson', or 'epub'
        """
        # Check if it's a file path
        path = Path(input_path).expanduser()
        if path.exists() and path.is_file() and path.suffix == '.epub':
            return ('epub', path)

        # Check if it's a course/lesson code pattern
        if input_path.lower().startswith(('au', 'do', 'rh', 'cl', 'ad')):
            # Lesson codes have numbers after letters (<lesson-code>, do316)
            # Course codes are just letters+numbers (au294, rh124)
            if input_path[-1].lower() == 'l' and any(c.isdigit() for c in input_path):
                return ('lesson', None)
            return ('course', None)

        # Default to course code
        return ('course', None)

    def setup_environment(self) -> bool:
        """
        Setup testing environment.

        Returns:
            True if setup successful, False otherwise
        """
        self.progress.start_phase("Environment Setup")

        # Detect workstation
        self.progress.update("Detecting workstation from ~/.ssh/config", "running")
        self.workstation = detect_workstation()

        if not self.workstation:
            self.progress.update("Cannot detect workstation", "error")
            self.progress.complete_phase(success=False)
            return False

        self.progress.update(f"Workstation: {self.workstation}", "success")

        # Test SSH connection
        self.progress.update("Testing SSH connectivity", "running")
        self.ssh = SSHConnection(self.workstation, username="student")

        if not self.ssh.test_connection():
            self.progress.update(f"Cannot connect to {self.workstation}", "error")
            self.progress.complete_phase(success=False)
            return False

        self.progress.update("SSH connection verified", "success")
        self.progress.complete_phase(success=True)
        return True

    def analyze_course(self, input_path: str, epub_path: Optional[Path] = None) -> bool:
        """
        Analyze course to build context.

        Args:
            input_path: Course/lesson code or EPUB path
            epub_path: Optional EPUB path if already detected

        Returns:
            True if analysis successful, False otherwise
        """
        self.progress.start_phase("Course Analysis")

        try:
            analyzer = CourseAnalyzer(input_path, epub_path)
            self.course_context = analyzer.analyze()

            self.progress.update(f"Course: {self.course_context.course_code}", "info")
            self.progress.update(f"Pattern: {self.course_context.pattern}", "info")
            self.progress.update(f"Exercises: {self.course_context.total_exercises}", "info")

            self.progress.complete_phase(success=True)
            return True

        except Exception as e:
            self.progress.update(f"Analysis failed: {e}", "error")
            self.progress.complete_phase(success=False)
            return False

    def run_single_exercise(self, exercise_id: str, lesson_code: Optional[str] = None) -> dict:
        """
        Run all test categories on a single exercise.

        Args:
            exercise_id: Exercise identifier
            lesson_code: Optional lesson code

        Returns:
            dict with test results
        """
        self.progress.start_phase(f"Testing Exercise: {exercise_id}")

        start_time = datetime.now()

        # Get exercise context
        if self.course_context:
            exercise = self.course_context.get_exercise(lesson_code, exercise_id)
        else:
            # Create minimal context
            exercise = ExerciseContext(
                id=exercise_id,
                type=ExerciseType.UNKNOWN,
                lesson_code=lesson_code or "",
                chapter=1,
                chapter_title="Chapter",
                title=exercise_id
            )

        # Initialize test executor
        executor = TestExecutor(self.workstation, self.course_context)

        # Initialize webapp integrator if needed
        webapp = WebAppIntegrator() if exercise.has_webapp_component else None

        # Run test categories
        test_results = {}
        all_bugs = []

        # TC-PREREQ
        self.progress.update("TC-PREREQ: Prerequisites", "running")
        prereq_result = executor.test_prerequisites(exercise)
        test_results['TC-PREREQ'] = prereq_result
        all_bugs.extend(prereq_result.bugs_found)

        if not prereq_result.passed:
            self.progress.update("Prerequisites failed, skipping remaining tests", "warning")
            self.progress.complete_phase(success=False)
            return self._build_results(exercise, test_results, all_bugs, start_time)

        # TC-INSTRUCT (if EPUB content available)
        if exercise.epub_content:
            self.progress.update("TC-INSTRUCT: Instruction Quality", "running")
            instruct_tester = TC_INSTRUCT()
            instruct_result = instruct_tester.test(exercise)
            test_results['TC-INSTRUCT'] = instruct_result
            all_bugs.extend(instruct_result.bugs_found)

        # TC-EXEC (pre-flight command validation - syntax, safety checks)
        # This runs BEFORE workflow execution to catch issues early
        if exercise.epub_workflow:
            self.progress.update("TC-EXEC: Command Syntax Validation", "running")
            exec_tester = TC_EXEC()
            exec_result = exec_tester.test(exercise, exercise.epub_workflow)
            test_results['TC-EXEC'] = exec_result
            all_bugs.extend(exec_result.bugs_found)

            # If critical syntax issues found, warn but continue
            if not exec_result.passed:
                self.progress.update("TC-EXEC found issues - proceeding with caution", "warning")

        # TC-WORKFLOW (automated EPUB execution on live systems)
        if exercise.epub_workflow:
            self.progress.update("TC-WORKFLOW: EPUB Workflow Execution", "running")
            workflow_tester = TC_WORKFLOW()
            workflow_result = workflow_tester.test(exercise, self.ssh, exercise.epub_workflow)
            test_results['TC-WORKFLOW'] = workflow_result
            all_bugs.extend(workflow_result.bugs_found)

        # TC-SOL (solution file testing)
        if exercise.solution_files:
            self.progress.update(f"TC-SOL: Testing {len(exercise.solution_files)} solutions", "running")
            sol_tester = TC_SOL()
            sol_result = sol_tester.test(exercise, exercise.solution_files, self.ssh)
            test_results['TC-SOL'] = sol_result
            all_bugs.extend(sol_result.bugs_found)

        # TC-SECURITY (v2.0 - security best practices analysis)
        self.progress.update("TC-SECURITY: Security Best Practices", "running")
        security_tester = TC_SECURITY()
        security_result = security_tester.test(exercise, self.ssh)
        test_results['TC-SECURITY'] = security_result
        all_bugs.extend(security_result.bugs_found)

        # TC-ACCESSIBILITY (v2.0 - WCAG 2.2 compliance)
        if exercise.epub_content:
            self.progress.update("TC-ACCESSIBILITY: Accessibility Compliance", "running")
            accessibility_tester = TC_ACCESSIBILITY()
            accessibility_result = accessibility_tester.test(exercise, exercise.epub_content)
            test_results['TC-ACCESSIBILITY'] = accessibility_result
            all_bugs.extend(accessibility_result.bugs_found)

        # TC-GRADE (grading validation for Labs)
        if exercise.type == ExerciseType.LAB:
            self.progress.update("TC-GRADE: Grading Validation", "running")
            grade_result = executor.test_grading(exercise)
            test_results['TC-GRADE'] = grade_result
            all_bugs.extend(grade_result.bugs_found)

        # TC-CONTRACT (v2.0 - component alignment validation)
        self.progress.update("TC-CONTRACT: Component Alignment", "running")
        contract_tester = TC_CONTRACT()
        contract_result = contract_tester.test(
            exercise,
            self.ssh,
            epub_content=exercise.epub_content if hasattr(exercise, 'epub_content') else None,
            grading_script_path=exercise.grading_script if hasattr(exercise, 'grading_script') else None
        )
        test_results['TC-CONTRACT'] = contract_result
        all_bugs.extend(contract_result.bugs_found)

        # TC-WEB (webapp testing if applicable)
        if webapp and exercise.has_webapp_component:
            self.progress.update("TC-WEB: WebApp Testing", "running")
            web_result = webapp.test_exercise(exercise)
            test_results['TC-WEB'] = web_result
            all_bugs.extend(web_result.bugs_found)

        # TC-IDEM (idempotency testing)
        self.progress.update("TC-IDEM: Idempotency (3 cycles)", "running")
        idem_tester = TC_IDEM(cycles=3)
        idem_result = idem_tester.test(exercise, self.ssh)
        test_results['TC-IDEM'] = idem_result
        all_bugs.extend(idem_result.bugs_found)

        # TC-CLEAN (cleanup verification)
        self.progress.update("TC-CLEAN: Cleanup Verification", "running")
        clean_result = executor.test_cleanup(exercise)
        test_results['TC-CLEAN'] = clean_result
        all_bugs.extend(clean_result.bugs_found)

        self.progress.complete_phase(success=True)
        return self._build_results(exercise, test_results, all_bugs, start_time)

    def run_e2e_testing(self, exercises: List[ExerciseContext]) -> dict:
        """
        Run end-to-end testing on multiple exercises.

        Args:
            exercises: List of exercises to test sequentially

        Returns:
            dict with E2E test results
        """
        self.progress.start_phase(f"E2E Testing: {len(exercises)} exercises")

        start_time = datetime.now()

        e2e_tester = TC_E2E()
        e2e_result = e2e_tester.test_sequence(exercises, self.ssh)

        self.progress.complete_phase(success=e2e_result.passed)

        return {
            'type': 'e2e',
            'exercises': [ex.id for ex in exercises],
            'results': e2e_result.to_dict(),
            'bugs': [bug.to_dict() for bug in e2e_result.bugs_found],
            'duration_seconds': (datetime.now() - start_time).total_seconds()
        }

    def run_full_course(self, mode: str = 'sequential') -> dict:
        """
        Run all exercises in course.

        Args:
            mode: Testing mode ('sequential', 'parallel', 'smart')

        Returns:
            dict with full course results
        """
        if not self.course_context:
            raise ValueError("Course context not available. Run analyze_course() first.")

        orchestrator = TestOrchestrator(self.course_context)
        results = orchestrator.run_full_course_test(mode=mode)

        return results.to_dict()

    def generate_report(self, results: dict, output_dir: Optional[Path] = None) -> Path:
        """
        Generate comprehensive QA report.

        Args:
            results: Test results
            output_dir: Optional output directory (defaults to skill results/)

        Returns:
            Path to generated report
        """
        self.progress.start_phase("Generating Report")

        if output_dir is None:
            output_dir = Path(__file__).parent.parent.parent / "results"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate report
        generator = ReportGenerator()
        report_path = generator.generate(results, output_dir)

        self.progress.update(f"Report saved to: {report_path}", "success")
        self.progress.complete_phase(success=True)

        return report_path

    def _build_results(self, exercise: ExerciseContext, test_results: dict,
                      bugs: List[Bug], start_time: datetime) -> dict:
        """Build results dictionary."""
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        total_tests = len(test_results)
        passed = sum(1 for r in test_results.values() if r.passed)
        failed = total_tests - passed

        return {
            'exercise_id': exercise.id,
            'lesson_code': exercise.lesson_code,
            'type': exercise.type.value,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration,
            'total_tests': total_tests,
            'passed': passed,
            'failed': failed,
            'test_results': {k: v.to_dict() for k, v in test_results.items()},
            'bugs': [bug.to_dict() for bug in bugs],
            'status': 'PASS' if passed == total_tests else 'FAIL'
        }


def run_watch_mode(args):
    """
    Watch mode: monitor exercise files and re-run tests on changes.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    import hashlib
    from datetime import datetime

    print(f"\n{bold('='*70)}")
    print(f"👁️  {bold('WATCH MODE')} - Monitoring for file changes")
    print(f"{bold('='*70)}")
    print(f"  Press Ctrl+C to exit\n")

    # Determine paths to watch
    input_path = Path(args.input).expanduser()
    exercise_id = args.exercise

    if input_path.is_file() and input_path.suffix == '.epub':
        watch_paths = [input_path]
        print(f"  Watching: {input_path}")
    else:
        # Watch current directory for exercise-related files
        watch_dir = Path.cwd()
        watch_patterns = ['*.yml', '*.yaml', '*.py', '*.sh', '*.adoc']
        watch_paths = []
        for pattern in watch_patterns:
            watch_paths.extend(watch_dir.rglob(pattern))
        print(f"  Watching: {watch_dir} ({len(watch_paths)} files)")

    if exercise_id:
        print(f"  Exercise: {exercise_id}")

    def get_file_hash(filepath: Path) -> str:
        """Get MD5 hash of file contents."""
        try:
            return hashlib.md5(filepath.read_bytes()).hexdigest()
        except Exception:
            return ""

    def get_all_hashes() -> dict:
        """Get hashes of all watched files."""
        hashes = {}
        for p in watch_paths:
            if p.is_file():
                hashes[str(p)] = get_file_hash(p)
        return hashes

    def run_tests():
        """Run the tests."""
        print(f"\n{info(f'[{datetime.now().strftime('%H:%M:%S')}] Running tests...')}")
        print(f"{dim('-'*70)}")

        verbose = args.verbose and not args.quiet
        runner = ExerciseQARunner(
            verbose=verbose,
            cache_enabled=not args.no_cache,
            use_colors=not args.no_color
        )

        if not runner.setup_environment():
            return

        input_type, epub_path = runner.detect_input_type(args.input)

        if not runner.analyze_course(args.input, epub_path):
            return

        if args.exercise:
            results = runner.run_single_exercise(args.exercise)
        elif args.full_course or input_type == 'epub':
            results = runner.run_full_course(mode=args.mode)
        else:
            print(error("Exercise name required for watch mode"))
            return

        if results:
            runner.progress.print_summary(results)

    # Initial run
    run_tests()

    # Get initial file state
    last_hashes = get_all_hashes()

    # Watch loop
    poll_interval = 2  # seconds
    print(f"\n{dim(f'Polling every {poll_interval}s for changes...')}")

    try:
        while True:
            time.sleep(poll_interval)

            # Check for changes
            current_hashes = get_all_hashes()

            changed_files = []
            for filepath, current_hash in current_hashes.items():
                if filepath not in last_hashes or last_hashes[filepath] != current_hash:
                    changed_files.append(filepath)

            if changed_files:
                print(f"\n{warning('File changes detected:')}")
                for f in changed_files[:5]:
                    print(f"  {dim('•')} {Path(f).name}")
                if len(changed_files) > 5:
                    print(f"  {dim(f'... and {len(changed_files) - 5} more')}")

                last_hashes = current_hashes
                run_tests()
                print(f"\n{dim(f'Polling every {poll_interval}s for changes...')}")

    except KeyboardInterrupt:
        print(f"\n\n{info('Watch mode stopped.')}")
        return 0

    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Exercise QA - Automated Red Hat Training Course Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test single exercise
  %(prog)s <lesson-code> <exercise-name>
  %(prog)s do316 accessing-review

  # Test from EPUB
  %(prog)s ./<OPENSHIFT-COURSE>-RHOCPV4.18-en-0.epub accessing-clicreate

  # Test full course
  %(prog)s ./<OPENSHIFT-COURSE>-RHOCPV4.18-en-0.epub --full-course

  # E2E testing
  %(prog)s au294 chapter2 --e2e
  %(prog)s rh124 --e2e usergroup-create usergroup-manage
        """
    )

    parser.add_argument(
        'input',
        help='Course code, lesson code, or EPUB path'
    )
    parser.add_argument(
        'exercise',
        nargs='?',
        help='Exercise name (omit for full course testing)'
    )
    parser.add_argument(
        '--e2e',
        action='store_true',
        help='Enable end-to-end testing'
    )
    parser.add_argument(
        '--full-course',
        action='store_true',
        help='Test all exercises in course'
    )
    parser.add_argument(
        '--mode',
        choices=['sequential', 'parallel', 'smart'],
        default='sequential',
        help='Testing mode for full course (default: sequential)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        default=True,
        help='Enable verbose output (default: True)'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Disable verbose output'
    )
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable caching'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        help='Output directory for reports'
    )
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colorized output'
    )
    parser.add_argument(
        '--watch',
        action='store_true',
        help='Watch mode: re-run tests when exercise files change'
    )

    args = parser.parse_args()

    # Configure colors
    if args.no_color:
        configure_colors(enabled=False)

    # Handle watch mode
    if args.watch:
        return run_watch_mode(args)

    # Initialize runner
    verbose = args.verbose and not args.quiet
    runner = ExerciseQARunner(
        verbose=verbose,
        cache_enabled=not args.no_cache,
        use_colors=not args.no_color
    )

    # Setup environment
    if not runner.setup_environment():
        return 1

    # Detect input type
    input_type, epub_path = runner.detect_input_type(args.input)

    # Analyze course
    if not runner.analyze_course(args.input, epub_path):
        return 1

    # Execute tests based on mode
    results = None

    if args.full_course:
        # Test all exercises
        results = runner.run_full_course(mode=args.mode)

    elif args.e2e:
        # E2E testing
        if not args.exercise:
            print("Error: E2E testing requires exercise name(s)")
            return 1

        # Get exercises for E2E testing
        exercises = runner.course_context.get_chapter_exercises(args.exercise)
        results = runner.run_e2e_testing(exercises)

    elif args.exercise:
        # Single exercise testing
        results = runner.run_single_exercise(args.exercise)

    else:
        # Default: test all exercises when given EPUB
        if input_type == 'epub':
            results = runner.run_full_course(mode=args.mode)
        else:
            print("Error: Exercise name required (or use --full-course)")
            return 1

    # Print summary
    if results:
        runner.progress.print_summary(results)

        # Generate report
        report_path = runner.generate_report(results, args.output_dir)
        print(f"\n📄 Full report: {report_path}\n")

    # Return exit code based on results
    if results and results.get('status') == 'PASS':
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
