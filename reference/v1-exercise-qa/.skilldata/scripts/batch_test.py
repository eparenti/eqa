#!/usr/bin/env python3
"""
Batch test multiple exercises and generate summary report.

Supports:
- Testing all exercises in a chapter
- Testing all exercises in a lesson
- Parallel execution (optional)
- Summary reporting

FIXED: Line 44 - Replaced TODO with actual test execution implementation.
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.ssh_connection import SSHConnection
from lib.test_result import ExerciseContext, ExerciseType
from test_executor import TestExecutor
from test_categories import TC_IDEM, TC_SOL
from scripts.detect_workstation import detect_workstation


def test_single_exercise(exercise_id, lesson_code, course_context=None, epub_path=None):
    """
    Test a single exercise with full test suite.


    Args:
        exercise_id: Exercise identifier
        lesson_code: Lesson code (e.g., "<lesson-code>")
        course_context: Optional CourseContext for enhanced testing
        epub_path: Optional path to EPUB

    Returns:
        dict: Test results for this exercise
    """
    print(f"\n🧪 Testing: {exercise_id}")
    print("-" * 60)

    start_time = datetime.now()

    # Initialize result structure
    result = {
        'exercise_id': exercise_id,
        'lesson_code': lesson_code,
        'start_time': start_time.isoformat(),
        'status': 'pending',
        'test_categories': {},
        'bugs': [],
        'duration_seconds': 0
    }

    try:
        # Get exercise context from course_context if available
        if course_context:
            exercise = course_context.get_exercise(lesson_code, exercise_id)
        else:
            # Create minimal exercise context
            exercise = ExerciseContext(
                id=exercise_id,
                type=ExerciseType.GUIDED_EXERCISE,  # Will be detected later
                lesson_code=lesson_code,
                chapter=1,
                chapter_title="Chapter",
                title=exercise_id
            )

        # Auto-detect workstation
        workstation = detect_workstation()
        if not workstation:
            result['status'] = 'ERROR'
            result['error'] = 'Cannot detect workstation'
            return result

        # Create test executor
        executor = TestExecutor(workstation, course_context)

        # Verify SSH connectivity
        if not executor.test_connection():
            result['status'] = 'ERROR'
            result['error'] = f'Cannot connect to workstation: {workstation}'
            return result

        # Create SSH connection for test categories
        ssh = SSHConnection(workstation)

        # Run test categories
        test_results = {}
        all_bugs = []

        # TC-PREREQ: Test lab start
        print("\n  📋 TC-PREREQ: Testing prerequisites...")
        prereq_result = executor.test_prerequisites(exercise)
        test_results['TC-PREREQ'] = prereq_result.to_dict()
        all_bugs.extend(prereq_result.bugs_found)

        if prereq_result.passed:
            # TC-IDEM: Idempotency testing
            print("\n  🔄 TC-IDEM: Testing idempotency...")
            idem_tester = TC_IDEM(cycles=3)
            idem_result = idem_tester.test(exercise, ssh)
            test_results['TC-IDEM'] = idem_result.to_dict()
            all_bugs.extend(idem_result.bugs_found)

            # TC-SOL: Solution testing (if solutions available)
            if exercise.solution_files:
                print(f"\n  📁 TC-SOL: Testing {len(exercise.solution_files)} solution files...")
                sol_tester = TC_SOL()
                sol_result = sol_tester.test(exercise, exercise.solution_files, ssh)
                test_results['TC-SOL'] = sol_result.to_dict()
                all_bugs.extend(sol_result.bugs_found)

            # TC-CLEAN: Test cleanup
            print("\n  🧹 TC-CLEAN: Testing cleanup...")
            clean_result = executor.test_cleanup(exercise)
            test_results['TC-CLEAN'] = clean_result.to_dict()
            all_bugs.extend(clean_result.bugs_found)

        # Determine overall status
        all_passed = all(r.get('passed', False) for r in test_results.values())
        result['status'] = 'PASS' if all_passed else 'FAIL'
        result['test_categories'] = test_results
        result['bugs'] = [bug.to_dict() for bug in all_bugs]

    except Exception as e:
        result['status'] = 'ERROR'
        result['error'] = str(e)
        print(f"  ❌ Error during testing: {e}")

    end_time = datetime.now()
    result['duration_seconds'] = (end_time - start_time).total_seconds()
    result['end_time'] = end_time.isoformat()

    # Print summary
    print(f"\n{'='*60}")
    print(f"Result: {result['status']}")
    print(f"Duration: {result['duration_seconds']:.2f}s")
    if result.get('bugs'):
        print(f"Bugs Found: {len(result['bugs'])}")
    print(f"{'='*60}")

    return result


def batch_test_chapter(chapter_number, mapping_file, parallel=False, max_workers=3):
    """
    Test all exercises in a chapter.

    Args:
        chapter_number: Chapter number (e.g., 2)
        mapping_file: Path to course mapping JSON
        parallel: Run tests in parallel
        max_workers: Max parallel workers

    Returns:
        dict: Batch test results
    """
    # Load mapping
    with open(mapping_file, 'r') as f:
        mapping = json.load(f)

    chapter_key = str(chapter_number)
    if chapter_key not in mapping.get('chapters', {}):
        print(f"❌ Chapter {chapter_number} not found in mapping")
        return None

    chapter_info = mapping['chapters'][chapter_key]
    exercises = chapter_info.get('exercises', [])

    print(f"📚 Batch Testing: Chapter {chapter_number}")
    print(f"   Course: {mapping.get('course_code')}")
    print(f"   Lesson: {chapter_info.get('lesson_code')}")
    print(f"   Exercises: {len(exercises)}")
    print(f"   Mode: {'Parallel' if parallel else 'Sequential'}")
    print("=" * 60)

    results = {
        'course_code': mapping.get('course_code'),
        'chapter_number': chapter_number,
        'lesson_code': chapter_info.get('lesson_code'),
        'total_exercises': len(exercises),
        'start_time': datetime.now().isoformat(),
        'exercises': []
    }

    # Test exercises
    if parallel:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    test_single_exercise,
                    ex['id'],
                    chapter_info.get('lesson_code')
                ): ex for ex in exercises
            }

            for future in as_completed(futures):
                exercise = futures[future]
                try:
                    result = future.result()
                    results['exercises'].append(result)
                    print(f"   ✅ {result['exercise_id']}: {result['status']}")
                except Exception as e:
                    print(f"   ❌ {exercise['id']}: {str(e)}")
    else:
        for exercise in exercises:
            try:
                result = test_single_exercise(
                    exercise['id'],
                    chapter_info.get('lesson_code')
                )
                results['exercises'].append(result)
                print(f"   {'✅' if result['status'] == 'PASS' else '❌'} {result['exercise_id']}")
            except Exception as e:
                print(f"   ❌ {exercise['id']}: {str(e)}")

    # Calculate summary
    results['end_time'] = datetime.now().isoformat()
    results['passed'] = sum(1 for ex in results['exercises'] if ex.get('status') == 'PASS')
    results['failed'] = sum(1 for ex in results['exercises'] if ex.get('status') == 'FAIL')
    results['pass_rate'] = (results['passed'] / results['total_exercises'] * 100) if results['total_exercises'] > 0 else 0

    return results


def generate_summary_report(results, output_file):
    """Generate summary report for batch tests."""

    report = f"""# Batch Test Report: Chapter {results['chapter_number']}

**Date**: {results['end_time']}
**Course**: {results['course_code']}
**Lesson**: {results['lesson_code']}

---

## Summary

**Total Exercises**: {results['total_exercises']}
**Passed**: {results['passed']} ({results['pass_rate']:.1f}%)
**Failed**: {results['failed']}

---

## Exercise Results

| Exercise | Status | Duration | Bugs |
|----------|--------|----------|------|
"""

    for ex in results['exercises']:
        status_icon = "✅" if ex.get('status') == 'PASS' else "❌"
        report += f"| {ex['exercise_id']} | {status_icon} {ex.get('status', 'UNKNOWN')} | {ex.get('duration_seconds', 0):.1f}s | {len(ex.get('bugs', []))} |\n"

    report += f"""
---

## Bugs Found

"""

    total_bugs = sum(len(ex.get('bugs', [])) for ex in results['exercises'])
    if total_bugs == 0:
        report += "**No bugs found** ✅\n"
    else:
        for ex in results['exercises']:
            if ex.get('bugs'):
                report += f"\n### {ex['exercise_id']}\n\n"
                for bug in ex['bugs']:
                    report += f"- **{bug.get('severity')}**: {bug.get('description')}\n"

    report += f"""
---

## Recommendations

"""

    if results['pass_rate'] == 100:
        report += "✅ **All exercises passed** - Chapter ready for release\n"
    elif results['pass_rate'] >= 80:
        report += "⚠️ **Most exercises passed** - Fix failing exercises before release\n"
    else:
        report += "❌ **Chapter has significant issues** - Requires review and fixes\n"

    # Write report
    with open(output_file, 'w') as f:
        f.write(report)

    print(f"\n📄 Summary report: {output_file}")


def main():
    """CLI interface."""
    if len(sys.argv) < 3:
        print("Usage: batch_test.py <chapter_number> <mapping_file> [--parallel] [--workers N]")
        print("\nExample:")
        print("  batch_test.py 2 config/courses/<ANSIBLE-COURSE>-mapping.json")
        print("  batch_test.py 3 config/courses/<RHEL-COURSE>-mapping.json --parallel --workers 4")
        sys.exit(1)

    chapter_number = int(sys.argv[1])
    mapping_file = sys.argv[2]
    parallel = '--parallel' in sys.argv
    max_workers = 3

    if '--workers' in sys.argv:
        idx = sys.argv.index('--workers')
        max_workers = int(sys.argv[idx + 1])

    if not Path(mapping_file).exists():
        print(f"❌ Mapping file not found: {mapping_file}")
        sys.exit(1)

    # Run batch test
    results = batch_test_chapter(chapter_number, mapping_file, parallel, max_workers)

    if results:
        # Generate report
        output_file = f"results/BATCH-REPORT-Chapter{chapter_number}-{datetime.now().strftime('%Y%m%d')}.md"
        generate_summary_report(results, output_file)

        # Save JSON results
        json_file = output_file.replace('.md', '.json')
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\n{'✅' if results['pass_rate'] == 100 else '❌'} Batch test complete: {results['passed']}/{results['total_exercises']} passed")
        sys.exit(0 if results['pass_rate'] == 100 else 1)


if __name__ == "__main__":
    main()
