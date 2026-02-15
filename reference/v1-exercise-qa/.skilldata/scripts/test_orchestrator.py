#!/usr/bin/env python3
"""
Test Orchestrator - Master coordinator ensuring ALL exercises tested (Guideline #6).

Coordinates all testing to ensure:
- ALL exercises are tested (no skipping)
- Tests run in optimal order
- Results are aggregated properly
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.test_result import CourseContext, CourseTestResults, ExerciseTestResults
from scripts.batch_test import test_single_exercise


class TestOrchestrator:
    """
    Master test coordinator.

    Ensures ALL exercises are tested with no skipping (guideline #6).
    """

    def __init__(self, course_context: CourseContext):
        """
        Initialize test orchestrator.

        Args:
            course_context: Course context from course_analyzer
        """
        self.context = course_context

    def run_full_course_test(self, mode: str = 'sequential') -> CourseTestResults:
        """
        Test ALL exercises in course (guideline #6 - no skipping).

        Args:
            mode: Testing mode ('sequential', 'parallel', 'smart')

        Returns:
            CourseTestResults with all exercise results
        """
        print("=" * 60)
        print(f"📚 Full Course Testing: {self.context.course_code}")
        print(f"📐 Pattern: {self.context.pattern}")
        print(f"📖 Chapters: {self.context.total_chapters}")
        print(f"✏️  Exercises: {self.context.total_exercises}")
        print(f"⚙️  Mode: {mode}")
        print("=" * 60)

        start_time = datetime.now()

        # Get ALL exercises
        all_exercises = self.context.get_all_exercises()

        print(f"\n🔍 Testing ALL {len(all_exercises)} exercises (no skipping)\n")

        # Create test plan based on mode
        if mode == 'smart':
            test_plan = self._create_smart_test_plan(all_exercises)
        else:
            test_plan = all_exercises  # Sequential

        # Execute tests
        exercise_results = []
        passed = 0
        failed = 0
        skipped = 0

        for i, exercise in enumerate(test_plan, 1):
            print(f"\n[{i}/{len(test_plan)}] {exercise.id} ({exercise.lesson_code})")
            print("-" * 60)

            try:
                # Test exercise
                result_dict = test_single_exercise(
                    exercise.id,
                    exercise.lesson_code,
                    self.context
                )

                # Convert to ExerciseTestResults
                exercise_result = ExerciseTestResults(
                    exercise_id=exercise.id,
                    lesson_code=exercise.lesson_code,
                    start_time=result_dict['start_time'],
                    end_time=result_dict.get('end_time', datetime.now().isoformat()),
                    duration_seconds=result_dict['duration_seconds'],
                    status=result_dict['status']
                )

                exercise_results.append(exercise_result)

                if result_dict['status'] == 'PASS':
                    passed += 1
                elif result_dict['status'] == 'FAIL':
                    failed += 1
                else:
                    skipped += 1

            except Exception as e:
                print(f"❌ Error testing {exercise.id}: {e}")
                failed += 1

        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()

        # Create results
        results = CourseTestResults(
            course_code=self.context.course_code,
            test_date=start_time.strftime('%Y-%m-%d'),
            total_exercises=len(all_exercises),
            exercises_tested=len(exercise_results),
            exercises_passed=passed,
            exercises_failed=failed,
            exercises_skipped=skipped,
            total_duration_seconds=total_duration,
            exercise_results=exercise_results,
            summary={
                'pass_rate': (passed / len(exercise_results) * 100) if exercise_results else 0,
                'mode': mode,
                'all_exercises_tested': (len(exercise_results) == len(all_exercises))
            }
        )

        # Print summary
        self._print_summary(results)

        return results

    def _create_smart_test_plan(self, exercises: List) -> List:
        """
        Create optimal test plan using dependency graph.

        Args:
            exercises: List of exercises

        Returns:
            Optimally ordered list of exercises
        """
        # For now, use sequential order
        # In future, use dependency graph for optimal ordering
        return exercises

    def _print_summary(self, results: CourseTestResults) -> None:
        """Print test summary."""
        print("\n" + "=" * 60)
        print("📊 Test Summary")
        print("=" * 60)
        print(f"Course: {results.course_code}")
        print(f"Date: {results.test_date}")
        print(f"Duration: {results.total_duration_seconds:.2f}s")
        print()
        print(f"Total Exercises: {results.total_exercises}")
        print(f"Exercises Tested: {results.exercises_tested}")
        print(f"✅ Passed: {results.exercises_passed}")
        print(f"❌ Failed: {results.exercises_failed}")
        print(f"⏭️  Skipped: {results.exercises_skipped}")
        print()
        print(f"Pass Rate: {results.summary['pass_rate']:.1f}%")
        print(f"All Exercises Tested: {'Yes ✅' if results.summary['all_exercises_tested'] else 'No ❌'}")
        print("=" * 60)

        if not results.summary['all_exercises_tested']:
            print("⚠️  WARNING: Not all exercises were tested (violates guideline #6)")
            print(f"   Expected: {results.total_exercises}")
            print(f"   Tested: {results.exercises_tested}")


def main():
    """Test orchestrator functionality."""
    import argparse

    parser = argparse.ArgumentParser(description="Orchestrate full course testing")
    parser.add_argument("course_context", help="Path to course_context.json")
    parser.add_argument("--mode", choices=['sequential', 'parallel', 'smart'],
                       default='sequential', help="Testing mode")

    args = parser.parse_args()

    # Load course context
    from lib.test_result import CourseContext
    course_context = CourseContext.from_json(Path(args.course_context))

    # Run full course test
    orchestrator = TestOrchestrator(course_context)
    results = orchestrator.run_full_course_test(mode=args.mode)

    # Save results
    output_file = Path(f"test_results_{course_context.course_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    results.to_json(output_file)
    print(f"\n💾 Results saved to: {output_file}")

    return 0 if results.exercises_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
