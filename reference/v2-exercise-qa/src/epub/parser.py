"""EPUB parsing and course structure extraction."""

import zipfile
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup
import yaml

from ..core.models import CourseContext, ExerciseContext, ExerciseType, CoursePattern
from ..core.pattern_detector import PatternDetector


class EPUBParser:
    """Parses EPUB files to extract course structure and exercises."""

    def __init__(self, epub_path: Path, lesson_path: Optional[Path] = None):
        """
        Initialize EPUB parser.

        Args:
            epub_path: Path to EPUB file
            lesson_path: Path to lesson directory (optional, defaults to EPUB parent)
        """
        self.epub_path = epub_path
        self.lesson_path = lesson_path or epub_path.parent
        self.temp_dir = None
        self.content_dir = None

    def parse(self) -> CourseContext:
        """
        Parse EPUB and extract course structure.

        Returns:
            CourseContext with all exercises and metadata
        """
        print(f"📖 Parsing EPUB: {self.epub_path.name}")

        # Extract EPUB
        self._extract_epub()

        # Get metadata
        course_code, course_title, version = self._extract_metadata()

        # Find exercises
        exercises = self._find_exercises()

        # Detect content patterns for each exercise
        pattern_detector = PatternDetector()
        for exercise in exercises:
            exercise.content_pattern = pattern_detector.detect_exercise_pattern(exercise)

        # Detect overall course pattern
        course_pattern = pattern_detector.detect_course_pattern(exercises)

        # Count patterns for logging
        pattern_counts = {}
        for ex in exercises:
            p = ex.content_pattern.value
            pattern_counts[p] = pattern_counts.get(p, 0) + 1

        print(f"   Found {len(exercises)} exercises")
        print(f"   Course pattern: {course_pattern.value}")
        if pattern_counts:
            print(f"   Exercise patterns: {pattern_counts}")

        return CourseContext(
            course_code=course_code,
            course_title=course_title,
            version=version,
            pattern="Pattern 1 (EPUB-based)",
            epub_path=self.epub_path,
            exercises=exercises,
            course_pattern=course_pattern
        )

    def _extract_epub(self):
        """Extract EPUB to temporary directory."""
        self.temp_dir = tempfile.mkdtemp(prefix="epub_qa_")
        self.content_dir = Path(self.temp_dir) / "EPUB"

        with zipfile.ZipFile(self.epub_path, 'r') as zip_ref:
            zip_ref.extractall(self.temp_dir)

    def _extract_metadata(self) -> Tuple[str, str, str]:
        """Extract course code, title, and version from EPUB."""
        # Try to get from filename first
        filename = self.epub_path.stem
        parts = filename.split('-')

        course_code = parts[0] if parts else "UNKNOWN"
        version = parts[1] if len(parts) > 1 else "1.0"
        course_title = f"{course_code} Course"

        # Try to get better title from content.opf
        opf_path = self.content_dir / "content.opf"
        if opf_path.exists():
            try:
                with open(opf_path, 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f, 'xml')
                    title_elem = soup.find('dc:title')
                    if title_elem:
                        course_title = title_elem.text.strip()
            except:
                pass

        return course_code, course_title, version

    def _find_exercises(self) -> List[ExerciseContext]:
        """Find all exercises in EPUB."""
        exercises = []

        if not self.content_dir.exists():
            return exercises

        # Find all XHTML/HTML files
        for html_file in self.content_dir.glob("*.xhtml"):
            exercises.extend(self._parse_chapter_file(html_file))

        for html_file in self.content_dir.glob("*.html"):
            exercises.extend(self._parse_chapter_file(html_file))

        return exercises

    def _parse_chapter_file(self, file_path: Path) -> List[ExerciseContext]:
        """Parse a chapter file to find exercises."""
        exercises = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')

            # Look for sections or headers with IDs ending in -ge or -lab
            # Some EPUBs use <section>, others use <h2> or <h3>
            elements = soup.find_all(['section', 'h2', 'h3'])
            for element in elements:
                section_id = element.get('id', '')

                if section_id.endswith('-ge'):
                    exercise = self._create_exercise_context(
                        section_id,
                        ExerciseType.GUIDED_EXERCISE,
                        element,
                        file_path
                    )
                    exercises.append(exercise)

                elif section_id.endswith('-lab'):
                    exercise = self._create_exercise_context(
                        section_id,
                        ExerciseType.LAB,
                        element,
                        file_path
                    )
                    exercises.append(exercise)

        except Exception as e:
            print(f"⚠️  Error parsing {file_path.name}: {e}")

        return exercises

    def _create_exercise_context(self, exercise_id: str, ex_type: ExerciseType,
                                  section, file_path: Path) -> ExerciseContext:
        """Create ExerciseContext from parsed HTML section."""
        # Get title
        title_elem = section.find(['h1', 'h2', 'h3'])
        title = title_elem.text.strip() if title_elem else exercise_id

        # Get chapter info from filename
        chapter_keyword = file_path.stem
        chapter = 1  # Default

        # Get lesson code from lesson path
        lesson_code = self.lesson_path.name if self.lesson_path else "unknown"

        # Find solution files and grading script
        solution_files = self._find_solution_files(exercise_id)
        grading_script = self._find_grading_script(exercise_id)
        materials_dir = self._find_materials_dir(exercise_id)

        return ExerciseContext(
            id=exercise_id,
            type=ex_type,
            lesson_code=lesson_code,
            chapter=chapter,
            chapter_title=chapter_keyword.title(),
            title=title,
            lesson_path=self.lesson_path,
            solution_files=solution_files,
            grading_script=grading_script,
            materials_dir=materials_dir
        )

    def _find_solution_files(self, exercise_id: str) -> List[Path]:
        """Find solution files for an exercise."""
        solution_files = []

        if not self.lesson_path:
            return solution_files

        # Strip -ge or -lab suffix for directory lookup
        base_id = exercise_id.removesuffix('-ge').removesuffix('-lab')
        # Also try with underscores instead of hyphens
        base_id_underscore = base_id.replace('-', '_')

        # Patterns to search for in each solutions directory
        def collect_solutions(solutions_dir: Path):
            if not solutions_dir.exists():
                return
            # .sol files (traditional pattern)
            solution_files.extend(solutions_dir.glob("*.sol"))
            solution_files.extend(solutions_dir.glob("**/*.sol"))
            # Regular yml/yaml files (newer pattern)
            solution_files.extend(solutions_dir.glob("*.yml"))
            solution_files.extend(solutions_dir.glob("*.yaml"))
            solution_files.extend(solutions_dir.glob("**/*.yml"))
            solution_files.extend(solutions_dir.glob("**/*.yaml"))

        # Pattern 1: materials/labs/<exercise>/solutions/
        for eid in [base_id, base_id_underscore]:
            solutions_dir = self.lesson_path / "materials" / "labs" / eid / "solutions"
            collect_solutions(solutions_dir)

        # Pattern 2: grading/src/<lesson>/materials/labs/<exercise>/solutions/
        lesson_lower = self.lesson_path.name.lower()
        for eid in [base_id, base_id_underscore]:
            grading_solutions = self.lesson_path / "classroom" / "grading" / "src" / lesson_lower / "materials" / "labs" / eid / "solutions"
            collect_solutions(grading_solutions)

        # Pattern 3: grading/src/<lesson>/materials/solutions/<exercise>/ (AU467 style)
        for eid in [base_id, base_id_underscore]:
            solutions_dir = self.lesson_path / "classroom" / "grading" / "src" / lesson_lower / "materials" / "solutions" / eid
            collect_solutions(solutions_dir)

        return sorted(set(solution_files))

    def _find_grading_script(self, exercise_id: str) -> Optional[Path]:
        """Find grading script for an exercise."""
        if not self.lesson_path:
            return None

        # Strip -ge or -lab suffix for directory lookup
        base_id = exercise_id.removesuffix('-ge').removesuffix('-lab')
        # Also try with underscores instead of hyphens
        base_id_underscore = base_id.replace('-', '_')

        # Look for grading script in classroom/grading/src/<lesson>/
        lesson_lower = self.lesson_path.name.lower()
        grading_dir = self.lesson_path / "classroom" / "grading" / "src" / lesson_lower

        if grading_dir.exists():
            # Look for grade script with various naming patterns
            for script_id in [exercise_id, base_id, base_id_underscore]:
                # Pattern 1: grade_<exercise>.sh or grade_<exercise>.py
                grade_script = grading_dir / f"grade_{script_id}.sh"
                if grade_script.exists():
                    return grade_script

                grade_py = grading_dir / f"grade_{script_id}.py"
                if grade_py.exists():
                    return grade_py

                # Pattern 2: <exercise>.py (Python module style - AU467)
                module_py = grading_dir / f"{script_id}.py"
                if module_py.exists():
                    # Verify it has a grade method
                    try:
                        content = module_py.read_text()
                        if 'def grade' in content or 'class ' in content:
                            return module_py
                    except:
                        pass

                # Pattern 3: <exercise>-review.py or <exercise>_review.py
                for suffix in ['-review', '_review']:
                    review_py = grading_dir / f"{script_id}{suffix}.py"
                    if review_py.exists():
                        return review_py

        return None

    def _find_materials_dir(self, exercise_id: str) -> Optional[Path]:
        """Find materials directory for an exercise."""
        if not self.lesson_path:
            return None

        # Strip -ge or -lab suffix for directory lookup
        base_id = exercise_id.removesuffix('-ge').removesuffix('-lab')
        base_id_underscore = base_id.replace('-', '_')

        lesson_lower = self.lesson_path.name.lower()

        # Check various locations
        for eid in [base_id, base_id_underscore]:
            # Pattern 1: materials/labs/<exercise>
            materials = self.lesson_path / "materials" / "labs" / eid
            if materials.exists():
                return materials

            # Pattern 2: grading/src/<lesson>/materials/labs/<exercise>
            materials = self.lesson_path / "classroom" / "grading" / "src" / lesson_lower / "materials" / "labs" / eid
            if materials.exists():
                return materials

            # Pattern 3: grading/src/<lesson>/materials/git_repos/<exercise>
            materials = self.lesson_path / "classroom" / "grading" / "src" / lesson_lower / "materials" / "git_repos" / eid
            if materials.exists():
                return materials

        return None

    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
