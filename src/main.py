"""eqa: Student simulation testing for Red Hat Training exercises.

Usage:
    python3 -m src.main <input> [exercise]
    python3 -m src.main /path/to/COURSE.epub exercise-name
    python3 -m src.main /path/to/COURSE.epub                   # all exercises
    python3 -m src.main /path/to/lesson-dir exercise-name
    python3 -m src.main AU0024L scale-files                    # lesson code
    python3 -m src.main AU294 --chapter 4                      # test chapter 4

Options:
    --chapter N                        Test only chapter N (requires course code input)
    --format markdown|json|junit|all   Report format (default: markdown)
    -o/--output <path>                 Output directory
    --quiet                            Suppress console output
    --no-color                         Disable ANSI colors
    --rebuild-epub                     Force EPUB rebuild
    --timeout-lab <seconds>            Lab command timeout (default: 300)
    --timeout-command <seconds>        Command timeout (default: 120)
    --timeout-build <seconds>          EPUB build timeout (default: 600)
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import yaml

from .colors import disable_colors
from .course import detect_course
from .epub import EPUBBuilder, EPUBParser
from .models import CourseResults, ExerciseType, SimulationResult
from .report import (
    generate_course_report,
    generate_report,
    write_course_report,
    write_report,
)
from .runner import StudentSimulator


DEFAULT_OUTPUT_DIR = Path(os.environ.get("EQA_CALLER_DIR", ".")) / "eqa-results"


def main(args: Optional[List[str]] = None):
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="eqa",
        description="Student simulation testing for Red Hat Training exercises",
    )
    parser.add_argument("input", help="EPUB path, lesson directory, or lesson code")
    parser.add_argument("exercise", nargs="?", help="Exercise ID (optional, tests all if omitted)")
    parser.add_argument("--format", default="markdown", choices=["markdown", "json", "junit", "all"])
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--rebuild-epub", action="store_true")
    parser.add_argument("--timeout-lab", type=int, default=300)
    parser.add_argument("--timeout-command", type=int, default=120)
    parser.add_argument("--timeout-build", type=int, default=600)
    parser.add_argument("--chapter", type=int, help="Test only chapter N (requires course code input)")
    parser.add_argument("--lesson-code", help="Lesson code for multi-repo courses (e.g., au0020l)")
    parser.add_argument("--test-solutions", action="store_true", help="Test solution files instead of student simulation")
    parser.add_argument("--cycles", type=int, default=1, help="Number of cycles for idempotency testing (default: 1)")

    parsed = parser.parse_args(args)

    if parsed.no_color:
        disable_colors()

    # If --chapter is used, resolve course code to the specific lesson
    if parsed.chapter:
        resolved = resolve_chapter(parsed.input, parsed.chapter)
        if not resolved:
            return 1
        epub_path, lesson_path, lesson_code_override = resolved
        if not parsed.lesson_code:
            parsed.lesson_code = lesson_code_override
    else:
        # Resolve input to an EPUB path and lesson path
        epub_path, lesson_path = resolve_input(
            parsed.input, rebuild=parsed.rebuild_epub, build_timeout=parsed.timeout_build,
        )

    if not epub_path:
        print(f"ERROR: Could not find or build EPUB from: {parsed.input}")
        return 1

    # Parse EPUB to get exercise list
    epub_parser = EPUBParser(epub_path, lesson_path)
    try:
        course = epub_parser.parse()
    finally:
        epub_parser.cleanup()

    # Determine which exercises to test
    if parsed.exercise:
        exercise_ids = [parsed.exercise]
        # Validate exercise exists
        matching = [e for e in course.exercises if e.id == parsed.exercise]
        if not matching:
            # Try fuzzy match
            candidates = [e.id for e in course.exercises
                          if parsed.exercise in e.id or e.id in parsed.exercise]
            if candidates:
                print(f"Exercise '{parsed.exercise}' not found. Did you mean:")
                for c in candidates:
                    print(f"  - {c}")
            else:
                print(f"Exercise '{parsed.exercise}' not found in EPUB.")
                print(f"Available exercises:")
                for e in course.exercises:
                    print(f"  - {e.id} ({e.type.value})")
            return 1
    else:
        exercise_ids = [e.id for e in course.exercises]

    print(f"\nCourse: {course.course_code} ({course.course_title})")
    print(f"Testing {len(exercise_ids)} exercise(s)")

    # Run simulations
    results: List[SimulationResult] = []
    start_time = datetime.now()

    for i, exercise_id in enumerate(exercise_ids, 1):
        print(f"\n[{i}/{len(exercise_ids)}] {exercise_id}")

        # Detect lesson code: explicit flag, or from course context
        lesson_code = parsed.lesson_code
        if not lesson_code:
            # For lesson-based inputs (e.g., AU0020L dir), use the dir name
            if lesson_path and lesson_path.name.upper().startswith('AU') and lesson_path.name.upper().endswith('L'):
                lesson_code = lesson_path.name.lower()

        # Look up exercise type from parsed course data
        ex_ctx = next((e for e in course.exercises if e.id == exercise_id), None)
        ex_type = ex_ctx.type if ex_ctx else None

        simulator = StudentSimulator(
            epub_path,
            timeout_lab=parsed.timeout_lab,
            timeout_command=parsed.timeout_command,
            lesson_code=lesson_code,
        )

        if parsed.test_solutions:
            result = simulator.test_solutions(exercise_id, exercise_type=ex_type)
            results.append(result)
            # Write report
            formats = ["markdown", "json", "junit"] if parsed.format == "all" else [parsed.format]
            paths = write_report(result, parsed.output, formats=formats)
            for p in paths:
                print(f"   Report: {p}")
        elif parsed.cycles > 1:
            # Idempotency testing: run multiple cycles
            cycle_results = simulator.run_idempotency(exercise_id, exercise_type=ex_type, cycles=parsed.cycles)
            results.extend(cycle_results)
            # Write reports for each cycle
            formats = ["markdown", "json", "junit"] if parsed.format == "all" else [parsed.format]
            for cycle_result in cycle_results:
                paths = write_report(cycle_result, parsed.output, formats=formats)
                for p in paths:
                    print(f"   Cycle {cycle_result.cycle} Report: {p}")
        else:
            result = simulator.run(exercise_id, exercise_type=ex_type)
            results.append(result)
            # Write report
            formats = ["markdown", "json", "junit"] if parsed.format == "all" else [parsed.format]
            paths = write_report(result, parsed.output, formats=formats)
            for p in paths:
                print(f"   Report: {p}")

    # Print summary
    total_duration = (datetime.now() - start_time).total_seconds()
    passed = sum(1 for r in results if r.success)
    failed = len(results) - passed

    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed}/{len(results)} exercises passed")
    print(f"Duration: {total_duration:.1f}s")
    print(f"{'='*60}")

    for r in results:
        status = "PASS" if r.success else "FAIL"
        print(f"  [{status}] {r.exercise_id} ({r.phase})")

    if failed > 0:
        print(f"\nFailed exercises:")
        for r in results:
            if not r.success:
                print(f"  {r.exercise_id}: {r.error_message or r.phase}")

    # Write course-level report if multiple exercises
    if len(results) > 1:
        course_results = CourseResults(
            course_code=course.course_code,
            test_date=datetime.now().isoformat(),
            total_exercises=len(course.exercises),
            exercises_tested=len(results),
            exercises_passed=passed,
            exercises_failed=failed,
            total_duration_seconds=total_duration,
            results=results,
            all_bugs=[b for r in results for b in r.bugs],
        )
        # Write course reports (markdown + json with quality metrics)
        formats = ["markdown", "json"] if parsed.format in ["all", "json"] else ["markdown"]
        course_report_paths = write_course_report(course_results, parsed.output, formats=formats)
        print(f"\nCourse reports:")
        for path in course_report_paths:
            print(f"  {path}")

    print(f"\nReports written to: {parsed.output}")
    return 0 if failed == 0 else 1


def resolve_chapter(input_str: str, chapter_num: int) -> Optional[Tuple[Path, Path, str]]:
    """Resolve a course code + chapter number to (epub_path, lesson_path, lesson_code).

    Reads the course-level outline.yml to find the lesson code for the given
    chapter number, then resolves that lesson to its EPUB.

    Returns None on failure (prints error message).
    """
    # Find the course directory
    course_dir = _find_course_dir(input_str)
    if not course_dir:
        print(f"ERROR: Could not find course directory for: {input_str}")
        print(f"  Searched in ~/git-repos/active/ and current directory")
        return None

    # Read the course outline to get chapter→lesson mapping
    outline_path = course_dir / "outline.yml"
    if not outline_path.exists():
        print(f"ERROR: No outline.yml in {course_dir}")
        return None

    try:
        with open(outline_path) as f:
            outline = yaml.safe_load(f)
    except Exception as e:
        print(f"ERROR: Failed to parse {outline_path}: {e}")
        return None

    # Extract chapters list
    root = outline.get('course', outline.get('lesson', {}))
    chapters = root.get('chapters', [])

    # Detect if this is a multi-repo (lesson-based) or single-repo (chapter-based) course
    is_multi_repo = any(ch.get('repository') for ch in chapters)
    unit_label = "lesson" if is_multi_repo else "chapter"

    if chapter_num < 1 or chapter_num > len(chapters):
        print(f"ERROR: {unit_label.title()} {chapter_num} not found. "
              f"Course has {len(chapters)} {unit_label}s:")
        for i, ch in enumerate(chapters, 1):
            keyword = ch.get('keyword', ch.get('remoteChapter', '?'))
            repo = ch.get('repository', '')
            lesson = re.search(r'/([A-Z]{2}\d{3,4}[A-Z]?)\.git', repo)
            lesson_str = f" ({lesson.group(1)})" if lesson else ""
            print(f"  {i}. {keyword}{lesson_str}")
        return None

    chapter = chapters[chapter_num - 1]
    keyword = chapter.get('keyword', chapter.get('remoteChapter', ''))

    # Extract lesson code from repository URL
    repo_url = chapter.get('repository', '')
    lesson_match = re.search(r'/([A-Z]{2}\d{3,4}[A-Z]?)\.git', repo_url)

    if lesson_match:
        lesson_code = lesson_match.group(1)
    else:
        # No remote repo — chapter is local to the course
        lesson_code = None

    if is_multi_repo:
        print(f"Lesson {chapter_num}: {keyword} ({lesson_code})")
    else:
        print(f"Chapter {chapter_num}: {keyword}")

    # Find the lesson directory and its EPUB
    if lesson_code:
        # Look for lesson directory in *-lessons/ pattern
        lesson_dir = _find_lesson_dir(course_dir, lesson_code)
        if not lesson_dir:
            print(f"ERROR: Lesson directory not found for {lesson_code}")
            print(f"  Expected at: {course_dir.parent}/{course_dir.name.replace(course_dir.name, '')}*-lessons/{lesson_code}")
            return None

        epub = _find_epub_in_dir(lesson_dir)
        if not epub:
            # Try building
            builder = EPUBBuilder()
            if builder.sk_path and (lesson_dir / "outline.yml").exists():
                print(f"Building EPUB for {lesson_code}...")
                result = builder.build_epub(lesson_dir, force_rebuild=False)
                if result.success and result.epub_path:
                    epub = result.epub_path

        if not epub:
            print(f"ERROR: No EPUB found for {lesson_code} in {lesson_dir}")
            return None

        return epub, lesson_dir, lesson_code.lower()
    else:
        # Local chapter — use the course EPUB
        epub = _find_epub_in_dir(course_dir)
        if not epub:
            print(f"ERROR: No EPUB found in {course_dir}")
            return None
        return epub, course_dir, input_str.lower()


def _find_course_dir(input_str: str) -> Optional[Path]:
    """Find the course directory for a course code like AU294."""
    input_path = Path(input_str).expanduser().resolve()
    if input_path.is_dir() and (input_path / "outline.yml").exists():
        return input_path

    search_dirs = [
        Path.cwd(),
        Path.home() / "git-repos" / "active",
    ]

    for base in search_dirs:
        if not base.exists():
            continue
        candidate = base / input_str
        if candidate.is_dir() and (candidate / "outline.yml").exists():
            return candidate

    return None


def _find_lesson_dir(course_dir: Path, lesson_code: str) -> Optional[Path]:
    """Find the lesson directory for a given lesson code.

    Searches for patterns like AU294-lessons/AU0022L relative to the course dir.
    """
    parent = course_dir.parent

    # Pattern: <course>-lessons/<lesson_code>
    for d in parent.glob(f"*-lessons/{lesson_code}"):
        if d.is_dir():
            return d

    # Direct sibling
    sibling = parent / lesson_code
    if sibling.is_dir():
        return sibling

    return None


def resolve_input(input_str: str, rebuild: bool = False,
                  build_timeout: int = 600) -> tuple:
    """Resolve input to (epub_path, lesson_path).

    Input can be:
    - Path to .epub file
    - Path to lesson directory (with outline.yml)
    - Lesson code (e.g., AU0024L) — looks in common locations
    """
    input_path = Path(input_str).expanduser().resolve()

    # Direct EPUB path
    if input_path.suffix == '.epub' and input_path.exists():
        return input_path, input_path.parent

    # Directory with EPUB
    if input_path.is_dir():
        # Find or build EPUB
        epub = _find_epub_in_dir(input_path)
        if epub and not rebuild:
            return epub, input_path

        # Try building EPUB
        builder = EPUBBuilder()
        if builder.sk_path and (input_path / "outline.yml").exists():
            print(f"Building EPUB for {input_path.name}...")
            result = builder.build_epub(input_path, force_rebuild=rebuild,
                                        timeout=build_timeout)
            if result.success and result.epub_path:
                return result.epub_path, input_path

        # Check if there's already a built EPUB
        if epub:
            return epub, input_path

        return None, input_path

    # Lesson code — search common locations
    search_dirs = [
        Path.cwd(),
        Path.home() / "git-repos" / "active",
    ]

    # Also check for lesson-specific paths (e.g., AU294-lessons/AU0024L)
    for base in search_dirs:
        if not base.exists():
            continue

        # Direct match
        candidate = base / input_str
        if candidate.is_dir():
            epub = _find_epub_in_dir(candidate)
            if epub:
                return epub, candidate

        # Pattern: *-lessons/input_str
        for lesson_dir in base.glob(f"*-lessons/{input_str}"):
            if lesson_dir.is_dir():
                epub = _find_epub_in_dir(lesson_dir)
                if epub:
                    return epub, lesson_dir

    return None, None


def _find_epub_in_dir(directory: Path) -> Optional[Path]:
    """Find the most recent EPUB in a directory."""
    for location in [directory, directory / ".cache" / "generated" / "en-US"]:
        if location.exists():
            epubs = list(location.glob("*.epub"))
            if epubs:
                return max(epubs, key=lambda p: p.stat().st_mtime)
    return None


if __name__ == "__main__":
    sys.exit(main())
