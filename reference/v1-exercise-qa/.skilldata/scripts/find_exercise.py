#!/usr/bin/env python3
"""
Find Exercise in Lesson Repo

Locates exercise directories in the lesson repository structure and
provides paths for QA testing.

Usage:
    python scripts/find_exercise.py <lesson-code> <exercise-name>
    python scripts/find_exercise.py <lesson-code> <exercise-name>
"""

import os
import sys
from pathlib import Path


LESSON_REPO_BASE = Path("/home/developer/git-repos/active")


def find_lesson_repo(lesson_code):
    """
    Find the lesson repository directory.

    Args:
        lesson_code: Lesson code (e.g., <lesson-code>)

    Returns:
        Path object if found, None otherwise
    """
    # Convert <lesson-code> to AU0020L
    course_code = lesson_code.upper().rstrip('L') + 'L'

    repo_path = LESSON_REPO_BASE / course_code

    if repo_path.exists():
        return repo_path

    return None


def find_exercise_materials(lesson_code, exercise_name):
    """
    Find the exercise materials directory.

    Args:
        lesson_code: Lesson code (e.g., <lesson-code>)
        exercise_name: Exercise name (e.g., <exercise-name>)

    Returns:
        dict with paths if found, None otherwise
    """
    repo_path = find_lesson_repo(lesson_code)

    if not repo_path:
        return None

    # Path to materials
    materials_path = (
        repo_path /
        "classroom" /
        "grading" /
        "src" /
        lesson_code.lower() /
        "materials" /
        "labs" /
        exercise_name
    )

    if not materials_path.exists():
        return None

    # Check for required files
    solutions_path = materials_path / "solutions"
    ansible_cfg = materials_path / "ansible.cfg"
    inventory = materials_path / "inventory"
    ansible_navigator_yml = materials_path / "ansible-navigator.yml"

    result = {
        "materials_path": materials_path,
        "solutions_path": solutions_path if solutions_path.exists() else None,
        "ansible_cfg": ansible_cfg if ansible_cfg.exists() else None,
        "inventory": inventory if inventory.exists() else None,
        "ansible_navigator_yml": ansible_navigator_yml if ansible_navigator_yml.exists() else None,
    }

    # Find solution files
    if solutions_path and solutions_path.exists():
        solution_files = list(solutions_path.glob("*.sol"))
        result["solution_files"] = solution_files
    else:
        result["solution_files"] = []

    return result


def list_exercises(lesson_code):
    """
    List all exercises for a lesson.

    Args:
        lesson_code: Lesson code (e.g., <lesson-code>)

    Returns:
        list of exercise names
    """
    repo_path = find_lesson_repo(lesson_code)

    if not repo_path:
        return []

    materials_base = (
        repo_path /
        "classroom" /
        "grading" /
        "src" /
        lesson_code.lower() /
        "materials" /
        "labs"
    )

    if not materials_base.exists():
        return []

    # Get all directories
    exercises = [d.name for d in materials_base.iterdir() if d.is_dir()]

    return sorted(exercises)


def main():
    if len(sys.argv) < 2:
        print("❌ Error: Lesson code required")
        print("Usage: python find_exercise.py <lesson-code> [exercise-name]")
        print("\nExample:")
        print("  python find_exercise.py <lesson-code>")
        print("  python find_exercise.py <lesson-code> <exercise-name>")
        sys.exit(1)

    lesson_code = sys.argv[1].lower()

    # If no exercise name, list all exercises
    if len(sys.argv) == 2:
        print(f"🔍 Finding exercises for {lesson_code}...\n")

        repo_path = find_lesson_repo(lesson_code)
        if not repo_path:
            print(f"❌ Lesson repo not found: {lesson_code.upper()}")
            sys.exit(1)

        print(f"✅ Lesson repo: {repo_path}\n")

        exercises = list_exercises(lesson_code)

        if not exercises:
            print("❌ No exercises found")
            sys.exit(1)

        print(f"📚 Exercises found ({len(exercises)}):\n")
        for i, exercise in enumerate(exercises, 1):
            print(f"  {i}. {exercise}")

        print(f"\n💡 Usage:")
        print(f"   python find_exercise.py {lesson_code} <exercise-name>")

        return

    # Find specific exercise
    exercise_name = sys.argv[2]

    print(f"🔍 Finding exercise: {lesson_code} / {exercise_name}\n")

    result = find_exercise_materials(lesson_code, exercise_name)

    if not result:
        print(f"❌ Exercise not found: {exercise_name}")
        print(f"\n💡 List all exercises:")
        print(f"   python find_exercise.py {lesson_code}")
        sys.exit(1)

    print(f"✅ Exercise found!\n")
    print(f"📁 Materials path:")
    print(f"   {result['materials_path']}\n")

    print(f"📋 Configuration files:")
    if result['ansible_cfg']:
        print(f"   ✅ ansible.cfg")
    else:
        print(f"   ❌ ansible.cfg (missing)")

    if result['ansible_navigator_yml']:
        print(f"   ✅ ansible-navigator.yml")
    else:
        print(f"   ❌ ansible-navigator.yml (missing)")

    if result['inventory']:
        print(f"   ✅ inventory")
    else:
        print(f"   ❌ inventory (missing)")

    print(f"\n🎯 Solution files ({len(result['solution_files'])}):")
    if result['solution_files']:
        for sol_file in result['solution_files']:
            print(f"   • {sol_file.name}")
    else:
        print(f"   ❌ No solution files found")

    print(f"\n🚀 Test command:")
    print(f"   cd {result['materials_path']}")
    if result['solution_files']:
        sol_file = result['solution_files'][0].name
        print(f"   ansible-navigator run solutions/{sol_file} -m stdout")

    print(f"\n📊 QA command:")
    print(f"   /qa {lesson_code} {exercise_name}")


if __name__ == "__main__":
    main()
