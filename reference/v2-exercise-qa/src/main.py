#!/usr/bin/env python3
"""
Exercise QA 2 - Main Entry Point

Professional automated testing for Red Hat Training exercises.
Built cleanly from the ground up with proper architecture.

Authors:
  - Ed Parenti <eparenti@redhat.com>
  - Claude Code
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Core imports
from src.core.models import CourseContext, ExerciseContext, ExerciseTestResults, CourseTestResults
from src.core.course_detector import CourseDetector, CourseInfo, detect_course
from src.core.course_profile import CourseProfileBuilder, CourseProfile
from src.epub.builder import EPUBBuilder
from src.epub.parser import EPUBParser
from src.clients.ssh import SSHConnection

# Test categories
from src.tests.prereq import TC_PREREQ
from src.tests.solution import TC_SOL
from src.tests.grading import TC_GRADE
from src.tests.solve import TC_SOLVE
from src.tests.verify import TC_VERIFY
from src.tests.workflow import TC_WORKFLOW
from src.tests.execution import TC_EXEC
from src.tests.cleanup import TC_CLEAN
from src.tests.idempotency import TC_IDEM
from src.tests.aap import TC_AAP
from src.tests.e2e import TC_E2E
from src.tests.security import TC_SECURITY
from src.tests.contract import TC_CONTRACT
from src.tests.instructions import TC_INSTRUCT
from src.tests.lint import TC_LINT
from src.tests.deps import TC_DEPS
from src.tests.perf import TC_PERF
from src.tests.vars import TC_VARS
from src.tests.rollback import TC_ROLLBACK
from src.tests.network import TC_NETWORK
from src.tests.webapp import TC_WEB
from src.tests.dynolabs import TC_DYNOLABS
from src.tests.ee import TC_EE

# Reporting
from src.reporting.generator import AdvancedReportGenerator
from src.reporting.junit import JUnitReportGenerator, CSVReportGenerator
from src.reporting.student_report import generate_report as generate_student_report

# Student simulation
from src.testing.student_simulator import StudentSimulator, SimulationResult

# Utils
from src.utils.parallel import ParallelExecutor
from src.utils.cache import ResultCache, EPUBCache
from src.utils.colors import get_formatter, disable_colors, ColorFormatter


class ExerciseQA:
    """Main orchestrator for exercise testing."""

    # All valid test categories
    VALID_CATEGORIES = {
        'TC-PREREQ', 'TC-EXEC', 'TC-WORKFLOW', 'TC-SOL', 'TC-SOLVE',
        'TC-VERIFY', 'TC-GRADE', 'TC-CLEAN', 'TC-IDEM', 'TC-AAP',
        'TC-E2E', 'TC-SECURITY', 'TC-CONTRACT', 'TC-INSTRUCT',
        'TC-LINT', 'TC-DEPS', 'TC-PERF', 'TC-VARS', 'TC-ROLLBACK',
        'TC-NETWORK', 'TC-WEB', 'TC-DYNOLABS', 'TC-EE'
    }

    def __init__(self, args):
        """Initialize QA orchestrator."""
        self.args = args
        self.ssh = None
        self.course_context = None
        self.course_info: CourseInfo = None  # Auto-detected course info
        self.course_profile: CourseProfile = None  # EPUB content analysis
        self.parallel_executor = None

        # Initialize color formatter
        self.colors = get_formatter()
        if getattr(args, 'no_color', False):
            disable_colors()

        # Apply CI mode settings
        if getattr(args, 'ci', False):
            # CI mode: JUnit output, quiet console (but run ALL tests - fresh lab handles determinism)
            if args.format == 'markdown':  # Only change if default
                args.format = 'junit'
            args.quiet = True
            disable_colors()  # No colors in CI

        self.quiet = getattr(args, 'quiet', False)

        # Initialize caches if enabled
        self.result_cache = ResultCache() if args.cache_results else None
        self.epub_cache = EPUBCache() if not getattr(args, 'no_cache', False) else None

    def _print(self, msg: str):
        """Print message if not in quiet mode."""
        if not self.quiet:
            print(msg)

    def _detect_course(self, path: Path) -> CourseInfo:
        """Auto-detect course information from repository."""
        try:
            return detect_course(path)
        except Exception as e:
            self._print(f"   Warning: Course detection failed: {e}")
            return None

    def _print_course_info(self):
        """Print auto-detected course information."""
        if not self.course_info:
            return

        info = self.course_info
        self._print(f"   Course:      {info.course_code}")
        self._print(f"   Version:     {info.version.canonical}")
        self._print(f"   Type:        {info.course_type.value}")
        framework_str = info.lab_framework.value
        if info.lab_framework_version:
            framework_str += f" ({info.lab_framework_version})"
        self._print(f"   Framework:   {framework_str}")
        self._print(f"   Exercises:   {len(info.exercises)}")
        self._print(f"   Confidence:  {info.detection_confidence:.0%}")

    def run(self):
        """Main execution flow."""
        self._print(self.colors.bold("=" * 70))
        self._print(self.colors.header("Exercise QA 2"))
        self._print(self.colors.bold("=" * 70))

        # Print mode indicators
        mode_indicators = []
        if getattr(self.args, 'e2e', False):
            mode_indicators.append(self.colors.info("[E2E MODE]"))
        if getattr(self.args, 'full', False):
            mode_indicators.append(self.colors.header("[FULL MODE]"))
        if getattr(self.args, 'full_course', False):
            mode_indicators.append(self.colors.info("[FULL COURSE]"))
        if getattr(self.args, 'ci', False):
            mode_indicators.append(self.colors.dim("[CI MODE]"))
        if mode_indicators:
            self._print(" ".join(mode_indicators))

        # Step 1: Resolve input (lesson dir, EPUB, or lesson code)
        input_path = self._resolve_input()
        if not input_path:
            self._print("Could not resolve input")
            return 1

        # Step 1.5: Auto-detect course information (if directory)
        if input_path.is_dir():
            self._print("\nAuto-detecting course information...")
            self.course_info = self._detect_course(input_path)
            if self.course_info:
                self._print_course_info()

                # If --detect flag, just print info and exit
                if getattr(self.args, 'detect', False):
                    return 0

        # Step 2: Ensure EPUB exists (build if needed)
        epub_path = self._ensure_epub(input_path)
        if not epub_path:
            self._print("EPUB not available")
            return 1

        # Step 3: Parse course structure
        self.course_context = self._parse_course(epub_path)
        if not self.course_context or len(self.course_context.exercises) == 0:
            self._print("No exercises found")
            return 1

        # Step 3.5: Analyze course content (read the book before testing)
        self._analyze_course_content(epub_path)

        # Step 3.6: Filter exercises if specific exercise requested
        # --e2e and --full-course both test all exercises
        if getattr(self.args, 'e2e', False):
            self._print(self.colors.info(
                f"\n[E2E MODE] Testing all {len(self.course_context.exercises)} exercises in order for independence"
            ))
        elif getattr(self.args, 'full_course', False):
            self._print(self.colors.info(
                f"\n[FULL COURSE] Testing all {len(self.course_context.exercises)} exercises"
            ))
        elif self.args.exercise:
            filtered = [ex for ex in self.course_context.exercises
                       if self.args.exercise in ex.id or self.args.exercise == str(self.course_context.exercises.index(ex) + 1)]
            if not filtered:
                self._print(self.colors.error(f"Exercise '{self.args.exercise}' not found"))
                self._print(f"   Available exercises:")
                for i, ex in enumerate(self.course_context.exercises, 1):
                    self._print(f"   {i}. {ex.id}")
                return 1
            self.course_context.exercises = filtered

        # Step 4: Connect to workstation
        self.ssh = self._connect_ssh()
        if not self.ssh:
            self._print("SSH connection failed")
            return 1

        # Step 4.5: Ensure lab package is installed
        if not self._ensure_lab_package():
            self._print(self.colors.warning("   Warning: Could not verify lab package installation"))
            self._print("   Continuing anyway - exercises may fail if package is not installed")

        # Step 6: Run student simulation (Phase 1)
        # This is essential testing: lab start -> exercise steps -> lab grade -> lab finish -> verify cleanup
        skip_sim = getattr(self.args, 'skip_student_sim', False)

        if not skip_sim:
            self._print(self.colors.header(f"\n{'='*70}"))
            self._print(self.colors.header("PHASE 1: Student Simulation"))
            self._print("lab start → exercise steps → lab grade (Labs) → lab finish → verify cleanup")
            self._print("="*70)

            simulation_results = self._run_student_simulations(epub_path)

            # Save student simulation report
            if simulation_results:
                self._save_student_reports(simulation_results)

            # Check if all simulations passed
            failed_sims = [r for r in simulation_results if not r.success]
            if failed_sims:
                self._print(self.colors.warning(f"\n⚠ {len(failed_sims)} exercise(s) failed student simulation"))
                self._print("   These issues will be included in QA report")
                self._print(self.colors.info("\n   Continuing with comprehensive QA checks..."))
            else:
                self._print(self.colors.success(f"\n✓ All {len(simulation_results)} exercise(s) passed student simulation"))

            # If --student-only, exit here
            if getattr(self.args, 'student_only', False):
                self._print("\n--student-only specified, skipping QA checks")
                return 0 if not failed_sims else 1

        # Step 7: Run QA tests (Phase 2)
        is_full_mode = getattr(self.args, 'full', False)
        is_e2e_mode = getattr(self.args, 'e2e', False)
        is_ci_mode = getattr(self.args, 'ci', False)

        self._print(self.colors.header(f"\n{'='*70}"))
        if is_full_mode:
            self._print(self.colors.header("QA CHECKS (Full Mode)"))
        elif is_e2e_mode:
            self._print(self.colors.info("QA CHECKS (E2E Mode - Exercise Independence)"))
        elif is_ci_mode:
            self._print(self.colors.dim("QA CHECKS (CI Mode)"))
        else:
            self._print(self.colors.header("QA CHECKS (Standard Mode)"))
        self._print(f"Testing {len(self.course_context.exercises)} exercise(s)...")
        self._print("="*70)

        # Check if parallel mode is enabled
        if self.args.mode == 'parallel' and len(self.course_context.exercises) > 1:
            exercise_results = self._run_tests_parallel()
        else:
            exercise_results = self._run_tests_sequential()

        # Step 8: Generate report
        course_results = self._aggregate_results(exercise_results)

        # Step 9: Save report
        self._print(f"\nGenerating report...")
        report_paths = self._save_report(course_results)
        for path in report_paths:
            self._print(f"Report saved: {path}")

        self._print("=" * 70)

        # Return exit code based on results
        return 0 if course_results.exercises_failed == 0 else 1

    def _resolve_input(self) -> Path:
        """Resolve input to a path."""
        input_str = self.args.input

        # Check if it's a path
        path = Path(input_str).expanduser()
        if path.exists():
            return path

        # Try to find lesson repo by code
        search_base = Path.home() / "git-repos" / "active"
        if search_base.exists():
            # Look for AU*L directories
            for lesson_dir in search_base.glob(f"*{input_str}*"):
                if lesson_dir.is_dir():
                    self._print(f"📁 Found lesson: {lesson_dir}")
                    return lesson_dir

        self._print(f"❌ Could not find: {input_str}")
        return None

    def _ensure_epub(self, input_path: Path) -> Path:
        """Ensure EPUB exists, build if necessary."""
        # If input is already an EPUB
        if input_path.suffix == '.epub':
            self._print(f"📖 Using EPUB: {input_path}")
            return input_path

        # If input is a directory, always build fresh EPUB
        if input_path.is_dir():
            # Check if this is a scaffolding course
            outline_path = input_path / "outline.yml"
            if not outline_path.exists():
                # Not a scaffolding course - look for existing EPUB
                for epub in input_path.glob("*.epub"):
                    self._print(f"📖 Found EPUB: {epub}")
                    return epub
                self._print(f"❌ Not a scaffolding course and no EPUB found")
                return None

            # Check for existing EPUB first (performance optimization)
            existing_epubs = list(input_path.glob("*.epub"))
            if existing_epubs and not getattr(self.args, 'rebuild_epub', False):
                # Use existing EPUB if available and --rebuild-epub not specified
                newest_epub = max(existing_epubs, key=lambda p: p.stat().st_mtime)

                # Calculate and display EPUB age
                from datetime import datetime
                mtime = datetime.fromtimestamp(newest_epub.stat().st_mtime)
                age = datetime.now() - mtime
                if age.days > 0:
                    age_str = f"{age.days}d ago"
                elif age.seconds >= 3600:
                    age_str = f"{age.seconds // 3600}h ago"
                else:
                    age_str = f"{age.seconds // 60}m ago"

                self._print(f"📖 Using EPUB: {newest_epub.name} (built {age_str})")
                self._print(self.colors.dim("   (use --rebuild-epub to force rebuild)"))
                return newest_epub

            # Build EPUB
            self._print(f"\n📦 Building EPUB...")
            builder = EPUBBuilder()

            # Check if sk is available
            available, msg = builder.validate_sk_available()
            if not available:
                self._print(f"❌ {msg}")
                self._print("   Install scaffolding: https://github.com/RedHatTraining/scaffolding")
                return None

            self._print(f"   {msg}")

            # Check SSH access for multi-repo courses
            course_info = builder.get_course_info(input_path)
            if course_info.get("has_remote_chapters"):
                self._print(f"   Course has remote chapters - checking SSH access...")
                ssh_ok, ssh_msg = builder.validate_ssh_access()
                if not ssh_ok:
                    self._print(f"   ⚠️  {ssh_msg}")
                    self._print(f"   EPUB build may fail if cache is outdated.")

            # Build EPUB (only force rebuild if requested)
            build_timeout = getattr(self.args, 'timeout_build', 600)
            force_rebuild = getattr(self.args, 'rebuild_epub', False)
            result = builder.build_epub(input_path, force_rebuild=force_rebuild, timeout=build_timeout)

            if result.success and result.epub_path:
                self._print(f"📖 EPUB ready: {result.epub_path}")
                return result.epub_path
            else:
                self._print(f"❌ EPUB build failed: {result.message}")
                if result.stderr:
                    # Show last few lines of error
                    error_lines = result.stderr.strip().split('\n')[-5:]
                    for line in error_lines:
                        self._print(f"   {line}")
                return None

        return None

    def _parse_course(self, epub_path: Path) -> CourseContext:
        """Parse EPUB to extract course structure."""
        self._print(f"\n📚 Parsing course structure...")

        # Try to get from cache
        if self.epub_cache:
            cached_context = self.epub_cache.get(epub_path)
            if cached_context:
                self._print(f"   ✓ Loaded from cache")
                return cached_context

        # Parse EPUB (keep extract dir for course profile analysis)
        self._epub_parser = EPUBParser(epub_path)
        context = self._epub_parser.parse()
        # Don't cleanup yet - we need the extracted content for course analysis

        # Cache the result
        if self.epub_cache:
            self.epub_cache.set(epub_path, context)

        return context

    def _analyze_course_content(self, epub_path: Path):
        """Analyze EPUB content to understand the course before testing."""
        self._print(f"\n📖 Analyzing course content...")

        try:
            builder = CourseProfileBuilder()

            # Use the extracted EPUB directory from parsing
            extract_dir = getattr(self._epub_parser, 'temp_dir', None)
            if extract_dir and Path(extract_dir).exists():
                self.course_profile = builder.build(
                    Path(extract_dir),
                    self.course_context.exercises
                )
            else:
                # Fall back to re-extracting
                import zipfile, tempfile
                temp_dir = tempfile.mkdtemp(prefix="exercise-qa-profile-")
                with zipfile.ZipFile(epub_path, 'r') as z:
                    z.extractall(temp_dir)
                self.course_profile = builder.build(Path(temp_dir), self.course_context.exercises)

            # Print what we learned
            p = self.course_profile
            tech = []
            if p.uses_ansible_navigator:
                tech.append("ansible-navigator")
            if p.uses_ansible_dev_tools:
                tech.append("ansible-dev-tools")
            if p.uses_ansible_playbook:
                tech.append("ansible-playbook")
            if p.uses_aap_controller:
                tech.append("AAP Controller")
            if p.uses_execution_environments:
                tech.append("Execution Environments")
            if p.uses_openshift:
                tech.append("OpenShift")

            if tech:
                self._print(f"   Technology: {', '.join(tech)}")
            if p.expected_tools:
                self._print(f"   Expected tools: {', '.join(sorted(p.expected_tools))}")
            if p.has_intentional_errors:
                self._print(self.colors.warning(f"   ⚠  Course uses intentional errors as teaching tools"))
            if p.exercises_with_deliberate_bugs:
                self._print(self.colors.warning(
                    f"   ⚠  Troubleshooting exercises: {', '.join(sorted(p.exercises_with_deliberate_bugs))}"
                ))
            if p.progressive_exercises:
                self._print(self.colors.info(f"   ℹ  Progressive exercises (may depend on each other)"))

        except Exception as e:
            self._print(f"   Warning: Course analysis failed: {e}")
            self.course_profile = CourseProfile()

        # Clean up EPUB parser now
        if hasattr(self, '_epub_parser'):
            self._epub_parser.cleanup()

    def _connect_ssh(self) -> SSHConnection:
        """Establish SSH connection to workstation."""
        self._print(f"\n🔌 Connecting to workstation...")
        ssh = SSHConnection("workstation", username="student")

        if ssh.connect():
            self._print("   ✓ SSH connected")
            return ssh
        else:
            self._print("   ❌ SSH connection failed")
            return None

    def _ensure_lab_package(self) -> bool:
        """
        Ensure the correct lab package is installed on workstation.

        For multi-repo lesson courses (like AU294-lessons), each lesson has its own
        lab package (e.g., rht-labs-au0018l) that must be installed before testing.

        Returns:
            True if lab package is available, False otherwise
        """
        if not self.course_info or not self.course_info.sku:
            self._print("   No lesson SKU detected, skipping package check")
            return True

        lesson_code = self.course_info.sku
        self._print(f"\n📦 Checking lab package for {lesson_code}...")

        # Check if package is installed
        is_installed, installed_packages = self.ssh.check_lab_package_installed(lesson_code)

        if is_installed:
            self._print(self.colors.success(f"   ✓ Lab package {lesson_code.lower()} is installed"))
            return True

        # Package not installed - try to install it
        self._print(self.colors.warning(f"   ⚠ Lab package {lesson_code.lower()} not found"))
        if installed_packages:
            self._print(f"   Installed packages: {', '.join(installed_packages[:5])}")

        self._print(f"\n📦 Installing lab package with 'lab force {lesson_code.lower()}'...")
        result = self.ssh.install_lab_package(lesson_code)

        if result.success:
            self._print(self.colors.success(f"   ✓ Lab package installed successfully"))
            return True
        else:
            self._print(self.colors.error(f"   ✗ Failed to install lab package"))
            if result.stderr:
                self._print(f"   Error: {result.stderr[:200]}")
            return False

    def _run_student_simulations(self, epub_path: Path) -> list:
        """Run student simulations for all exercises."""
        from src.testing.student_simulator import StudentSimulator

        results = []
        # Determine lesson path for devcontainer detection
        lesson_path = None
        if self.course_context and self.course_context.exercises:
            lesson_path = self.course_context.exercises[0].lesson_path
        if not lesson_path:
            # Fall back to input path if it's a directory
            input_path = self._resolve_input()
            if input_path and input_path.is_dir():
                lesson_path = input_path

        simulator = StudentSimulator(
            epub_path,
            workstation="workstation",
            timeout_lab=getattr(self.args, 'timeout_lab', 300),
            timeout_command=getattr(self.args, 'timeout_command', 120),
            lesson_path=lesson_path
        )
        simulator.verbose = not self.quiet

        for exercise in self.course_context.exercises:
            self._print(f"\n{'─'*60}")
            result = simulator.run(exercise.id)
            results.append(result)

            # Print summary
            status = "✓ PASS" if result.success else "✗ FAIL"
            self._print(f"\n{status}: {exercise.id}")
            if not result.success:
                self._print(f"   Phase: {result.phase}")
                if result.error_message:
                    self._print(f"   Error: {result.error_message[:100]}")

        return results

    def _save_student_reports(self, results: list):
        """Save student simulation reports."""
        output_dir = Path.home() / ".claude" / "skills" / "exercise-qa-2" / "results"
        output_dir.mkdir(parents=True, exist_ok=True)

        for result in results:
            report = generate_student_report(result)
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            report_path = output_dir / f"student-sim-{result.exercise_id}-{timestamp}.md"
            report_path.write_text(report)
            self._print(f"   Report: {report_path}")

    def _run_tests_sequential(self) -> list:
        """Run tests sequentially (one at a time)."""
        exercise_results = []

        for exercise in self.course_context.exercises:
            # Check cache first
            if self.result_cache:
                cached_result = self.result_cache.get(exercise.id, exercise.lesson_path)
                if cached_result:
                    self._print(f"\n{'=' * 70}")
                    self._print(f"📝 {exercise.id}: ✓ CACHED (skipping)")
                    exercise_results.append(cached_result)
                    continue

            # Attach course profile so test categories can use it
            exercise.course_profile = self.course_profile

            # Run test
            result = self._test_exercise(exercise)
            exercise_results.append(result)

            # Cache passing results
            if self.result_cache and result.status == "PASS":
                self.result_cache.set(exercise.id, exercise.lesson_path, result)

        return exercise_results

    def _run_tests_parallel(self) -> list:
        """Run tests in parallel using connection pool."""
        # Setup parallel executor with connection pool
        self.parallel_executor = ParallelExecutor(max_workers=3)

        if not self.parallel_executor.setup_connection_pool("workstation", "student"):
            self._print("   ⚠️  Failed to setup connection pool, falling back to sequential")
            return self._run_tests_sequential()

        try:
            # Filter out cached results
            exercises_to_test = []
            cached_results = []

            for exercise in self.course_context.exercises:
                if self.result_cache:
                    cached_result = self.result_cache.get(exercise.id, exercise.lesson_path)
                    if cached_result:
                        self._print(f"   ✓ {exercise.id}: cached")
                        cached_results.append(cached_result)
                        continue

                exercises_to_test.append(exercise)

            # Run parallel tests
            if exercises_to_test:
                self._print(f"   🚀 Running {len(exercises_to_test)} exercise(s) in parallel...")
                parallel_results = self.parallel_executor.execute_tests(
                    exercises_to_test,
                    lambda ex, ssh: self._test_exercise_with_ssh(ex, ssh)
                )

                # Cache passing results
                if self.result_cache:
                    for result in parallel_results:
                        if result.status == "PASS":
                            # Find corresponding exercise
                            exercise = next(ex for ex in exercises_to_test if ex.id == result.exercise_id)
                            self.result_cache.set(result.exercise_id, exercise.lesson_path, result)

                # Combine cached and new results
                return cached_results + parallel_results
            else:
                return cached_results

        finally:
            if self.parallel_executor:
                self.parallel_executor.cleanup()

    def _get_test_categories(self):
        """Get filtered list of test categories based on CLI args."""
        # E2E tests: run all exercises in order to check independence
        # Uses standard tests + TC-E2E, skips slow multi-cycle tests
        e2e_categories = [
            ('TC-PREREQ', TC_PREREQ()),
            ('TC-E2E', TC_E2E()),
            ('TC-SOL', TC_SOL()),
            ('TC-GRADE', TC_GRADE()),
            ('TC-WORKFLOW', TC_WORKFLOW()),
            ('TC-EXEC', TC_EXEC()),
            ('TC-CLEAN', TC_CLEAN()),
            ('TC-CONTRACT', TC_CONTRACT()),
            ('TC-DEPS', TC_DEPS()),
            ('TC-LINT', TC_LINT()),
            ('TC-INSTRUCT', TC_INSTRUCT()),
            ('TC-SECURITY', TC_SECURITY()),
        ]

        # STANDARD tests (default): single-pass lab validation
        # Skips only multi-cycle tests (TC-IDEM, TC-ROLLBACK, TC-E2E, TC-PERF)
        standard_categories = [
            ('TC-PREREQ', TC_PREREQ()),
            ('TC-SOL', TC_SOL()),
            ('TC-GRADE', TC_GRADE()),
            ('TC-SOLVE', TC_SOLVE()),
            ('TC-VERIFY', TC_VERIFY()),
            ('TC-WORKFLOW', TC_WORKFLOW()),
            ('TC-EXEC', TC_EXEC()),
            ('TC-CLEAN', TC_CLEAN()),
            ('TC-LINT', TC_LINT()),
            ('TC-VARS', TC_VARS()),
            ('TC-DEPS', TC_DEPS()),
            ('TC-INSTRUCT', TC_INSTRUCT()),
            ('TC-SECURITY', TC_SECURITY()),
            ('TC-CONTRACT', TC_CONTRACT()),
            ('TC-NETWORK', TC_NETWORK()),
            ('TC-EE', TC_EE()),
            ('TC-AAP', TC_AAP()),
            ('TC-DYNOLABS', TC_DYNOLABS()),
            ('TC-WEB', TC_WEB()),
        ]

        # FULL tests: comprehensive validation including multi-cycle tests
        full_categories = [
            ('TC-PREREQ', TC_PREREQ()),
            ('TC-SOL', TC_SOL()),
            ('TC-GRADE', TC_GRADE()),
            ('TC-SOLVE', TC_SOLVE()),
            ('TC-VERIFY', TC_VERIFY()),
            ('TC-WORKFLOW', TC_WORKFLOW()),
            ('TC-EXEC', TC_EXEC()),
            ('TC-CLEAN', TC_CLEAN()),
            ('TC-IDEM', TC_IDEM()),
            ('TC-E2E', TC_E2E()),
            ('TC-LINT', TC_LINT()),
            ('TC-VARS', TC_VARS()),
            ('TC-DEPS', TC_DEPS()),
            ('TC-INSTRUCT', TC_INSTRUCT()),
            ('TC-SECURITY', TC_SECURITY()),
            ('TC-CONTRACT', TC_CONTRACT()),
            ('TC-NETWORK', TC_NETWORK()),
            ('TC-EE', TC_EE()),
            ('TC-DYNOLABS', TC_DYNOLABS()),
            ('TC-AAP', TC_AAP()),
            ('TC-PERF', TC_PERF()),
            ('TC-ROLLBACK', TC_ROLLBACK()),
            ('TC-WEB', TC_WEB()),
        ]

        # Determine mode
        is_full = getattr(self.args, 'full', False)
        is_ci = getattr(self.args, 'ci', False)
        is_e2e = getattr(self.args, 'e2e', False)

        # Explicit test list overrides everything
        include_tests = None
        if hasattr(self.args, 'tests') and self.args.tests:
            include_tests = set(t.strip().upper() for t in self.args.tests.split(','))
            # Validate test category names
            invalid = include_tests - self.VALID_CATEGORIES
            if invalid:
                self._print(self.colors.error(f"❌ Invalid test categories: {', '.join(sorted(invalid))}"))
                self._print(f"   Valid categories: {', '.join(sorted(self.VALID_CATEGORIES))}")
                return []

        # Parse --skip flag
        skip_tests = set()
        if hasattr(self.args, 'skip') and self.args.skip:
            skip_tests = set(t.strip().upper() for t in self.args.skip.split(','))

        # Build category list based on mode
        if include_tests:
            # Explicit test list - run only those
            all_cats = full_categories
            categories = [(name, tc) for name, tc in all_cats if name in include_tests]
            self._print(self.colors.info(f"🎯 Running: {', '.join(sorted(include_tests))}"))
        elif is_e2e:
            # E2E mode - all exercises in order, testing independence
            categories = e2e_categories
            self._print(self.colors.info(f"🔗 E2E MODE: {len(categories)} test categories per exercise (includes TC-E2E independence checks)"))
        elif is_full:
            # Full mode - comprehensive pre-production validation (all 23 tests)
            categories = full_categories
            self._print(self.colors.header(f"🔬 FULL MODE: {len(categories)} test categories (includes multi-cycle tests)"))
        else:
            # Standard mode (default) - thorough single-pass validation
            categories = standard_categories
            if is_ci:
                self._print(self.colors.dim(f"🤖 CI mode: {len(categories)} tests"))
            else:
                self._print(self.colors.header(f"🔍 Standard mode: {len(categories)} tests (--quick for static only, --full for multi-cycle)"))

        # Apply skip filter
        if skip_tests:
            categories = [(name, tc) for name, tc in categories if name not in skip_tests]
            self._print(self.colors.dim(f"⏭  Skipping: {', '.join(sorted(skip_tests))}"))

        return [tc for name, tc in categories]

    def _test_exercise(self, exercise: ExerciseContext) -> ExerciseTestResults:
        """Test a single exercise."""
        self._print(self.colors.bold(f"\n{'=' * 70}"))
        self._print(self.colors.header(f"📝 Testing: {exercise.id}"))
        self._print(f"   Type: {self.colors.info(exercise.type.value)}")
        self._print(f"   Title: {exercise.title}")
        self._print(f"   Chapter: {exercise.chapter} - {exercise.chapter_title}")

        start_time = datetime.now()
        test_results = {}
        all_bugs = []

        # Run test categories (filtered based on CLI args)
        test_categories = self._get_test_categories()
        total_categories = len(test_categories)

        for i, tc in enumerate(test_categories, 1):
            category_name = tc.__class__.__name__.replace('TC_', 'TC-')
            self._print(self.colors.dim(f"\n   [{i}/{total_categories}] Running {category_name}..."))

            try:
                result = tc.test(exercise, self.ssh)
                test_results[result.category] = result
                all_bugs.extend(result.bugs_found)

                if result.passed:
                    status_str = self.colors.success(f"✓ PASS")
                else:
                    status_str = self.colors.error(f"✗ FAIL")
                duration_str = self.colors.dim(f"({result.duration_seconds:.1f}s)")
                self._print(f"   {status_str} {result.category} {duration_str}")

                if result.bugs_found:
                    for bug in result.bugs_found:
                        badge = self.colors.severity_badge(bug.severity.value)
                        self._print(f"      {badge} {bug.description[:70]}")

            except Exception as e:
                self._print(self.colors.error(f"   ❌ {tc.__class__.__name__} crashed: {e}"))

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Determine overall status
        passed_tests = sum(1 for r in test_results.values() if r.passed)
        total_tests = len(test_results)
        status = "PASS" if passed_tests == total_tests else "FAIL"

        if status == "PASS":
            overall_str = self.colors.success(f"✓ PASS")
        else:
            overall_str = self.colors.error(f"✗ FAIL")
        self._print(f"\n   Overall: {overall_str} ({passed_tests}/{total_tests} categories passed, {len(all_bugs)} bugs)")

        return ExerciseTestResults(
            exercise_id=exercise.id,
            lesson_code=exercise.lesson_code,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            status=status,
            test_categories=test_results,
            bugs=all_bugs,
            summary=f"{passed_tests}/{total_tests} test categories passed"
        )

    def _test_exercise_with_ssh(self, exercise: ExerciseContext, ssh: SSHConnection) -> ExerciseTestResults:
        """Test a single exercise with provided SSH connection (for parallel execution)."""
        self._print(self.colors.bold(f"\n{'=' * 70}"))
        self._print(self.colors.header(f"📝 Testing: {exercise.id}"))
        self._print(f"   Type: {self.colors.info(exercise.type.value)}")
        self._print(f"   Title: {exercise.title}")
        self._print(f"   Chapter: {exercise.chapter} - {exercise.chapter_title}")

        start_time = datetime.now()
        test_results = {}
        all_bugs = []

        # Run test categories (filtered based on CLI args)
        test_categories = self._get_test_categories()
        total_categories = len(test_categories)

        for i, tc in enumerate(test_categories, 1):
            category_name = tc.__class__.__name__.replace('TC_', 'TC-')
            self._print(self.colors.dim(f"\n   [{i}/{total_categories}] Running {category_name}..."))

            try:
                result = tc.test(exercise, ssh)
                test_results[result.category] = result
                all_bugs.extend(result.bugs_found)

                if result.passed:
                    status_str = self.colors.success(f"✓ PASS")
                else:
                    status_str = self.colors.error(f"✗ FAIL")
                duration_str = self.colors.dim(f"({result.duration_seconds:.1f}s)")
                self._print(f"   {status_str} {result.category} {duration_str}")

                if result.bugs_found:
                    for bug in result.bugs_found:
                        badge = self.colors.severity_badge(bug.severity.value)
                        self._print(f"      {badge} {bug.description[:70]}")

            except Exception as e:
                self._print(self.colors.error(f"   ❌ {tc.__class__.__name__} crashed: {e}"))

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Determine overall status
        passed_tests = sum(1 for r in test_results.values() if r.passed)
        total_tests = len(test_results)
        status = "PASS" if passed_tests == total_tests else "FAIL"

        if status == "PASS":
            overall_str = self.colors.success(f"✓ PASS")
        else:
            overall_str = self.colors.error(f"✗ FAIL")
        self._print(f"\n   Overall: {overall_str} ({passed_tests}/{total_tests} categories passed, {len(all_bugs)} bugs)")

        return ExerciseTestResults(
            exercise_id=exercise.id,
            lesson_code=exercise.lesson_code,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            status=status,
            test_categories=test_results,
            bugs=all_bugs,
            summary=f"{passed_tests}/{total_tests} test categories passed"
        )

    def _aggregate_results(self, exercise_results: list) -> CourseTestResults:
        """Aggregate exercise results into course results."""
        total = len(self.course_context.exercises)
        tested = len(exercise_results)
        passed = sum(1 for r in exercise_results if r.status == "PASS")
        failed = sum(1 for r in exercise_results if r.status == "FAIL")
        skipped = total - tested

        all_bugs = []
        for result in exercise_results:
            all_bugs.extend(result.bugs)

        total_duration = sum(r.duration_seconds for r in exercise_results)

        return CourseTestResults(
            course_code=self.course_context.course_code,
            test_date=datetime.now().isoformat(),
            total_exercises=total,
            exercises_tested=tested,
            exercises_passed=passed,
            exercises_failed=failed,
            exercises_skipped=skipped,
            total_duration_seconds=total_duration,
            exercise_results=exercise_results,
            all_bugs=all_bugs,
            summary={
                'pass_rate': (passed / tested * 100) if tested > 0 else 0,
                'total_bugs': len(all_bugs),
                'avg_duration': total_duration / tested if tested > 0 else 0
            }
        )

    def _save_report(self, results: CourseTestResults) -> list:
        """Save test results in requested format(s)."""
        # Determine output directory and base filename
        if self.args.output:
            output_path = Path(self.args.output)
            if output_path.suffix:
                # User provided full path with extension
                output_dir = output_path.parent
                base_name = output_path.stem
            else:
                # User provided directory
                output_dir = output_path
                base_name = f"QA-{results.course_code}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        else:
            output_dir = Path.home() / ".claude" / "skills" / "exercise-qa-2" / "results"
            base_name = f"QA-{results.course_code}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        output_dir.mkdir(parents=True, exist_ok=True)
        report_paths = []
        fmt = self.args.format

        # Generate requested format(s)
        if fmt in ('junit', 'all'):
            junit_path = output_dir / f"{base_name}.xml"
            junit_gen = JUnitReportGenerator(results)
            junit_gen.generate(junit_path)
            report_paths.append(junit_path)
            self._print(f"   JUnit XML: {junit_path}")

        if fmt in ('csv', 'all'):
            csv_path = output_dir / f"{base_name}.csv"
            csv_gen = CSVReportGenerator(results)
            csv_gen.generate(csv_path)
            report_paths.append(csv_path)
            self._print(f"   CSV: {csv_path}")

        if fmt in ('markdown', 'json', 'all'):
            # Use the advanced generator for markdown and JSON
            generator = AdvancedReportGenerator(results)
            md_path, json_path = generator.generate(output_dir)

            if fmt in ('markdown', 'all'):
                report_paths.append(md_path)
                self._print(f"   Markdown: {md_path}")

            if fmt in ('json', 'all'):
                report_paths.append(json_path)
                self._print(f"   JSON: {json_path}")

        return report_paths


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Exercise QA 2 - Professional course testing"
    )

    parser.add_argument(
        'input',
        help='Lesson code, lesson directory, or EPUB file path'
    )

    parser.add_argument(
        'exercise',
        nargs='?',
        help='Specific exercise to test (optional)'
    )

    parser.add_argument(
        '--cache-results',
        action='store_true',
        help='Cache passing test results'
    )

    parser.add_argument(
        '--mode',
        choices=['sequential', 'parallel'],
        default='sequential',
        help='Test execution mode'
    )

    parser.add_argument(
        '--tests',
        type=str,
        help='Comma-separated list of test categories to run (e.g., TC-LINT,TC-SECURITY)'
    )

    parser.add_argument(
        '--skip',
        type=str,
        help='Comma-separated list of test categories to skip (e.g., TC-IDEM,TC-ROLLBACK)'
    )

    parser.add_argument(
        '--full',
        action='store_true',
        help='Full mode: all 23 test categories including multi-cycle tests (TC-IDEM, TC-ROLLBACK, TC-E2E, TC-PERF)'
    )

    parser.add_argument(
        '--detect',
        action='store_true',
        help='Only detect and display course information, then exit (no testing)'
    )

    parser.add_argument(
        '--ci',
        action='store_true',
        help='CI mode: output JUnit XML, quiet console. Runs all tests (use --tests to limit)'
    )

    parser.add_argument(
        '--format',
        choices=['markdown', 'json', 'junit', 'csv', 'all'],
        default='markdown',
        help='Output format (default: markdown). Use "all" for all formats.'
    )

    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Output file path (default: auto-generated in ~/.claude/skills/exercise-qa-2/results/)'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress console output (useful for CI pipelines)'
    )

    parser.add_argument(
        '--skip-student-sim',
        action='store_true',
        help='Skip student simulation phase (run QA checks only)'
    )

    parser.add_argument(
        '--force-qa',
        action='store_true',
        help='Run QA checks even if student simulation fails'
    )

    parser.add_argument(
        '--student-only',
        action='store_true',
        help='Run only student simulation (skip QA checks)'
    )

    parser.add_argument(
        '--timeout-build',
        type=int,
        default=600,
        help='EPUB build timeout in seconds (default: 600)'
    )

    parser.add_argument(
        '--timeout-lab',
        type=int,
        default=300,
        help='Lab start/finish timeout in seconds (default: 300)'
    )

    parser.add_argument(
        '--timeout-command',
        type=int,
        default=120,
        help='Individual command timeout in seconds (default: 120)'
    )

    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable all caching'
    )

    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colorized output'
    )

    parser.add_argument(
        '--e2e',
        action='store_true',
        help='E2E mode: run focused test set (TC-PREREQ, TC-E2E, TC-WORKFLOW, TC-CLEAN)'
    )

    parser.add_argument(
        '--full-course',
        action='store_true',
        help='Test all exercises in course (ignore exercise filter)'
    )

    parser.add_argument(
        '--rebuild-epub',
        action='store_true',
        help='Force rebuild EPUB even if one exists (default: use existing EPUB)'
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    qa = ExerciseQA(args)
    exit_code = qa.run()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
