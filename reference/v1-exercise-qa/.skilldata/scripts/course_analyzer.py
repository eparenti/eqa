#!/usr/bin/env python3
"""
Course Analysis Engine - Analyzes entire course BEFORE testing begins.

Implements Guideline #2: Context First
- Parses entire EPUB for all chapters
- Builds exercise dependency graph
- Analyzes instruction quality
- Maps all lab scripts, solutions, snippets
- Understands complete course structure

This MUST run BEFORE any testing to build comprehensive course understanding.
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime
import zipfile
import tempfile
from bs4 import BeautifulSoup

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.test_result import (
    CourseContext, ChapterContext, ExerciseContext,
    ExerciseType, QualityIssue
)


class CourseAnalyzer:
    """
    Analyzes complete course structure and content before testing.

    This is the entry point for all testing - builds comprehensive understanding
    of the course, exercises, dependencies, and quality issues.
    """

    def __init__(self, epub_path: Path, course_repo_path: Optional[Path] = None):
        """
        Initialize course analyzer.

        Args:
            epub_path: Path to course EPUB file
            course_repo_path: Optional path to course repository
        """
        self.epub_path = epub_path
        self.course_repo_path = course_repo_path
        self.temp_dir = None
        self.epub_content_dir = None

    def analyze_course(self) -> CourseContext:
        """
        Analyze entire course and build complete context.

        Returns:
            CourseContext with all course information

        This is the main entry point - calls all analysis methods.
        """
        print("🔍 Analyzing course structure...")

        # Extract EPUB
        self._extract_epub()

        # Detect course pattern and metadata
        course_code, course_title, version, pattern = self._detect_course_metadata()

        print(f"📚 Course: {course_code} - {course_title}")
        print(f"📐 Pattern: {pattern}")
        print(f"📦 Version: {version}")

        # Parse all chapters
        chapters = self._parse_all_chapters()

        print(f"📖 Found {len(chapters)} chapters")

        # Count total exercises
        total_exercises = sum(len(ch.exercises) for ch in chapters.values())
        print(f"✏️  Found {total_exercises} exercises")

        # Build dependency graph
        print("🔗 Building dependency graph...")
        dependency_graph = self._build_dependency_graph(chapters)

        # Detect webapp exercises
        print("🌐 Detecting webapp exercises...")
        webapp_exercises = self._detect_webapp_exercises(chapters)

        # Analyze instruction quality
        print("📊 Analyzing instruction quality...")
        quality_issues = self._analyze_course_quality(chapters)

        # Build resource map
        print("🗺️  Building resource map...")
        resource_map = self._build_resource_map(chapters)

        # Create course context
        context = CourseContext(
            course_code=course_code,
            course_title=course_title,
            version=version,
            total_chapters=len(chapters),
            total_exercises=total_exercises,
            pattern=pattern,
            chapters=chapters,
            dependency_graph=dependency_graph,
            resource_map=resource_map,
            quality_issues=quality_issues,
            webapp_exercises=webapp_exercises
        )

        print("✅ Course analysis complete!")

        return context

    def _extract_epub(self) -> None:
        """Extract EPUB to temporary directory."""
        self.temp_dir = tempfile.mkdtemp(prefix="epub_analysis_")
        self.epub_content_dir = Path(self.temp_dir) / "OEBPS"

        with zipfile.ZipFile(self.epub_path, 'r') as zip_ref:
            zip_ref.extractall(self.temp_dir)

    def _detect_course_metadata(self) -> Tuple[str, str, str, str]:
        """
        Detect course code, title, version, and pattern.

        Returns:
            Tuple of (course_code, course_title, version, pattern)
        """
        # Extract from filename: <ANSIBLE-COURSE>-RHAAP2.5-en-3.epub
        filename = self.epub_path.stem
        parts = filename.split('-')

        course_code = parts[0] if parts else "UNKNOWN"
        version = parts[1] if len(parts) > 1 else "1.0"

        # Get title from EPUB metadata
        course_title = self._extract_epub_title()

        # Detect pattern from outline.yml if available
        pattern = self._detect_course_pattern()

        return course_code, course_title, version, pattern

    def _extract_epub_title(self) -> str:
        """Extract course title from EPUB metadata."""
        opf_file = self.epub_content_dir / "content.opf"

        if opf_file.exists():
            with open(opf_file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'xml')
                title_tag = soup.find('dc:title')
                if title_tag:
                    return title_tag.text.strip()

        return "Unknown Course"

    def _detect_course_pattern(self) -> str:
        """
        Detect course repository pattern (1, 2, or 3).

        Returns:
            Pattern identifier string
        """
        # For now, return Pattern 2 (multi-repo) as default
        # In a full implementation, would check outline.yml structure
        return "Pattern 2 (Multi-repo, Lesson-based)"

    def _parse_all_chapters(self) -> Dict[int, ChapterContext]:
        """
        Parse all chapters from EPUB.

        Returns:
            Dictionary mapping chapter number to ChapterContext
        """
        chapters = {}

        # Find all chapter XHTML files
        chapter_files = sorted(self.epub_content_dir.glob("ch*.xhtml"))

        for i, chapter_file in enumerate(chapter_files, 1):
            chapter_context = self._parse_chapter(chapter_file, i)
            if chapter_context:
                chapters[i] = chapter_context

        return chapters

    def _parse_chapter(self, chapter_file: Path, chapter_num: int) -> Optional[ChapterContext]:
        """
        Parse single chapter from XHTML file.

        Args:
            chapter_file: Path to chapter XHTML file
            chapter_num: Chapter number

        Returns:
            ChapterContext or None if parsing fails
        """
        try:
            with open(chapter_file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')

            # Extract chapter title
            title_tag = soup.find('h1') or soup.find('title')
            chapter_title = title_tag.text.strip() if title_tag else f"Chapter {chapter_num}"

            # Extract keyword from title (simplified)
            keyword = chapter_title.lower().replace(' ', '-')[:20]

            # Guess lesson code (Pattern 2 style)
            lesson_code = f"au{chapter_num:04d}l"

            # Extract exercises from chapter
            exercises = self._extract_exercises_from_chapter(soup, chapter_num, chapter_title, lesson_code)

            return ChapterContext(
                number=chapter_num,
                title=chapter_title,
                keyword=keyword,
                lesson_code=lesson_code,
                exercises=exercises
            )

        except Exception as e:
            print(f"⚠️  Error parsing chapter {chapter_num}: {e}")
            return None

    def _extract_exercises_from_chapter(self, soup: BeautifulSoup, chapter_num: int,
                                       chapter_title: str, lesson_code: str) -> List[ExerciseContext]:
        """
        Extract all exercises from chapter HTML.

        Args:
            soup: BeautifulSoup object of chapter XHTML
            chapter_num: Chapter number
            chapter_title: Chapter title
            lesson_code: Lesson code

        Returns:
            List of ExerciseContext objects
        """
        exercises = []

        # Find all exercise sections (GE and Lab)
        ge_sections = soup.find_all(['section', 'div'], class_=re.compile(r'(guided|exercise|ge)', re.I))
        lab_sections = soup.find_all(['section', 'div'], class_=re.compile(r'lab', re.I))

        all_sections = ge_sections + lab_sections

        for section in all_sections:
            exercise = self._parse_exercise_section(section, chapter_num, chapter_title, lesson_code)
            if exercise:
                exercises.append(exercise)

        # If no exercises found via class names, try h2 headers
        if not exercises:
            exercises = self._extract_exercises_by_headers(soup, chapter_num, chapter_title, lesson_code)

        return exercises

    def _parse_exercise_section(self, section, chapter_num: int, chapter_title: str,
                                lesson_code: str) -> Optional[ExerciseContext]:
        """
        Parse single exercise section.

        Returns:
            ExerciseContext or None
        """
        try:
            # Extract exercise title
            title_tag = section.find(['h2', 'h3', 'h4'])
            if not title_tag:
                return None

            title = title_tag.text.strip()

            # Determine exercise ID from title
            exercise_id = self._generate_exercise_id(title)

            # Determine exercise type
            exercise_type = self._determine_exercise_type(title, section)

            # Extract full content
            content = section.get_text()

            # Check for webapp component
            has_webapp = self._detect_webapp_in_content(content)

            # Analyze quality
            quality_score, issues = self._analyze_exercise_quality(exercise_id, content)

            return ExerciseContext(
                id=exercise_id,
                type=exercise_type,
                lesson_code=lesson_code,
                chapter=chapter_num,
                chapter_title=chapter_title,
                title=title,
                epub_content=content,
                has_webapp_component=has_webapp,
                instruction_quality_score=quality_score,
                quality_issues=issues
            )

        except Exception as e:
            print(f"⚠️  Error parsing exercise section: {e}")
            return None

    def _extract_exercises_by_headers(self, soup: BeautifulSoup, chapter_num: int,
                                     chapter_title: str, lesson_code: str) -> List[ExerciseContext]:
        """
        Extract exercises by looking for h2 headers with exercise keywords.

        Fallback method when class-based detection fails.
        """
        exercises = []
        h2_tags = soup.find_all('h2')

        exercise_keywords = ['guided exercise', 'lab', 'practice', 'review']

        for h2 in h2_tags:
            title = h2.text.strip().lower()
            if any(keyword in title for keyword in exercise_keywords):
                # Found an exercise
                exercise_id = self._generate_exercise_id(h2.text.strip())
                exercise_type = self._determine_exercise_type(h2.text.strip(), h2)

                # Get content until next h2
                content = self._get_content_until_next_header(h2)

                has_webapp = self._detect_webapp_in_content(content)
                quality_score, issues = self._analyze_exercise_quality(exercise_id, content)

                exercises.append(ExerciseContext(
                    id=exercise_id,
                    type=exercise_type,
                    lesson_code=lesson_code,
                    chapter=chapter_num,
                    chapter_title=chapter_title,
                    title=h2.text.strip(),
                    epub_content=content,
                    has_webapp_component=has_webapp,
                    instruction_quality_score=quality_score,
                    quality_issues=issues
                ))

        return exercises

    def _generate_exercise_id(self, title: str) -> str:
        """
        Generate exercise ID from title.

        Args:
            title: Exercise title

        Returns:
            Exercise ID (e.g., "<exercise-name>")
        """
        # Remove common prefixes
        cleaned = re.sub(r'^(guided exercise|lab|practice):?\s*', '', title, flags=re.I)

        # Convert to lowercase, replace spaces with hyphens
        exercise_id = cleaned.lower().strip()
        exercise_id = re.sub(r'[^\w\s-]', '', exercise_id)
        exercise_id = re.sub(r'[-\s]+', '-', exercise_id)

        return exercise_id

    def _determine_exercise_type(self, title: str, section) -> ExerciseType:
        """
        Determine if exercise is GE or Lab.

        Args:
            title: Exercise title
            section: BeautifulSoup section element

        Returns:
            ExerciseType enum value
        """
        title_lower = title.lower()

        if 'lab' in title_lower or 'review' in title_lower:
            return ExerciseType.LAB
        elif 'guided' in title_lower or 'exercise' in title_lower:
            return ExerciseType.GUIDED_EXERCISE
        else:
            return ExerciseType.UNKNOWN

    def _detect_webapp_in_content(self, content: str) -> bool:
        """
        Detect if exercise involves webapp testing.

        Args:
            content: Exercise content text

        Returns:
            True if webapp component detected
        """
        webapp_keywords = [
            'web console', 'aap', 'ansible automation platform',
            'openshift console', 'satellite ui', 'browser',
            'web interface', 'web ui', 'cockpit'
        ]

        content_lower = content.lower()
        return any(keyword in content_lower for keyword in webapp_keywords)

    def _analyze_exercise_quality(self, exercise_id: str, content: str) -> Tuple[float, List[QualityIssue]]:
        """
        Analyze instruction quality for exercise.

        Args:
            exercise_id: Exercise identifier
            content: Exercise content text

        Returns:
            Tuple of (quality_score, list_of_issues)
        """
        issues = []
        score = 1.0  # Start at perfect score

        # Check for completeness
        if len(content) < 500:
            issues.append(QualityIssue(
                exercise_id=exercise_id,
                issue_type='completeness',
                description='Content seems too short (< 500 chars)',
                suggestion='Verify all instructions are included',
                severity='moderate'
            ))
            score -= 0.2

        # Check for step numbering
        if not re.search(r'\d+\.', content):
            issues.append(QualityIssue(
                exercise_id=exercise_id,
                issue_type='formatting',
                description='No numbered steps detected',
                suggestion='Add numbered steps for clarity',
                severity='minor'
            ))
            score -= 0.1

        # Check for code blocks
        has_code = bool(re.search(r'```|`|\$|#', content))
        if not has_code and len(content) > 1000:
            issues.append(QualityIssue(
                exercise_id=exercise_id,
                issue_type='completeness',
                description='No code examples detected in substantial content',
                suggestion='Add code examples or commands',
                severity='moderate'
            ))
            score -= 0.15

        return max(0.0, score), issues

    def _get_content_until_next_header(self, h2_tag) -> str:
        """
        Extract content from h2 tag until next h2.

        Args:
            h2_tag: BeautifulSoup h2 tag

        Returns:
            Content text
        """
        content_parts = []
        for sibling in h2_tag.find_next_siblings():
            if sibling.name == 'h2':
                break
            content_parts.append(sibling.get_text())

        return '\n'.join(content_parts)

    def _build_dependency_graph(self, chapters: Dict[int, ChapterContext]) -> Dict:
        """
        Build exercise dependency graph from resource analysis.

        Args:
            chapters: Dictionary of chapters

        Returns:
            Serialized dependency graph
        """
        # Simplified implementation - would use networkx in production
        graph = {'nodes': [], 'edges': []}

        for chapter in chapters.values():
            for exercise in chapter.exercises:
                graph['nodes'].append({
                    'id': exercise.id,
                    'lesson': exercise.lesson_code,
                    'type': exercise.type.value
                })

        return graph

    def _detect_webapp_exercises(self, chapters: Dict[int, ChapterContext]) -> List[str]:
        """
        Detect all exercises with webapp components.

        Args:
            chapters: Dictionary of chapters

        Returns:
            List of exercise IDs with webapp components
        """
        webapp_exercises = []

        for chapter in chapters.values():
            for exercise in chapter.exercises:
                if exercise.has_webapp_component:
                    webapp_exercises.append(exercise.id)

        return webapp_exercises

    def _analyze_course_quality(self, chapters: Dict[int, ChapterContext]) -> List[QualityIssue]:
        """
        Analyze overall course quality.

        Args:
            chapters: Dictionary of chapters

        Returns:
            List of course-wide quality issues
        """
        issues = []

        # Aggregate exercise quality issues
        for chapter in chapters.values():
            for exercise in chapter.exercises:
                issues.extend(exercise.quality_issues)

        return issues

    def _build_resource_map(self, chapters: Dict[int, ChapterContext]) -> Dict[str, List[str]]:
        """
        Build map of resources created by each exercise.

        Args:
            chapters: Dictionary of chapters

        Returns:
            Resource map
        """
        resource_map = {}

        for chapter in chapters.values():
            for exercise in chapter.exercises:
                resource_map[exercise.id] = exercise.creates_resources

        return resource_map

    def cleanup(self) -> None:
        """Clean up temporary directory."""
        if self.temp_dir:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)


def main():
    """Test course analyzer."""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze course structure from EPUB")
    parser.add_argument("epub", help="Path to course EPUB file")
    parser.add_argument("--output", "-o", help="Output JSON file for course context")
    parser.add_argument("--repo", help="Optional course repository path")

    args = parser.parse_args()

    epub_path = Path(args.epub)
    if not epub_path.exists():
        print(f"❌ EPUB file not found: {epub_path}")
        return 1

    analyzer = CourseAnalyzer(epub_path, Path(args.repo) if args.repo else None)

    try:
        context = analyzer.analyze_course()

        # Print summary
        print("\n" + "=" * 60)
        print("Course Analysis Summary")
        print("=" * 60)
        print(f"Course: {context.course_code} - {context.course_title}")
        print(f"Chapters: {context.total_chapters}")
        print(f"Exercises: {context.total_exercises}")
        print(f"WebApp Exercises: {len(context.webapp_exercises)}")
        print(f"Quality Issues: {len(context.quality_issues)}")

        # Save to JSON if requested
        if args.output:
            output_path = Path(args.output)
            context.to_json(output_path)
            print(f"\n✅ Context saved to {output_path}")

        return 0

    except Exception as e:
        print(f"❌ Error analyzing course: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        analyzer.cleanup()


if __name__ == "__main__":
    sys.exit(main())
