"""
Course Auto-Detection Module

Automatically detects course metadata, version, structure, and exercises
from the course repository without requiring manual configuration.

Thinks like a course developer, understands the curriculum structure.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import yaml


class CourseType(Enum):
    """Course type classification."""
    SCAFFOLDING = "scaffolding"      # Uses scaffolding (sk) build system
    TRADITIONAL = "traditional"       # Legacy build system
    UNKNOWN = "unknown"


class LabFramework(Enum):
    """Lab framework classification."""
    DYNOLABS_5 = "dynolabs5"          # Modern Python-based labs (uv, rht-labs-core)
    DYNOLABS_4 = "dynolabs4"          # Older Python labs
    SHELL_SCRIPTS = "shell"           # Traditional shell grading scripts
    AAP_API = "aap_api"               # Uses aap_api library
    NONE = "none"                     # No lab scripts
    UNKNOWN = "unknown"


@dataclass
class VersionInfo:
    """Aggregated version information from multiple sources."""
    metadata_version: Optional[str] = None      # From metadata.yml
    about_version: Optional[str] = None         # From __about__.py
    pyproject_version: Optional[str] = None     # From pyproject.toml (if static)
    git_tag: Optional[str] = None               # Latest git tag
    outline_edition: Optional[str] = None       # From outline.yml

    @property
    def canonical(self) -> str:
        """Get the canonical version (prefer metadata.yml)."""
        return (self.metadata_version or
                self.about_version or
                self.pyproject_version or
                "unknown")

    @property
    def is_consistent(self) -> bool:
        """Check if versions are consistent across sources."""
        versions = [v for v in [self.metadata_version, self.about_version] if v]
        if len(versions) <= 1:
            return True
        # Compare major.minor (ignore patch)
        def major_minor(v):
            match = re.match(r'(\d+\.\d+)', str(v))
            return match.group(1) if match else v
        return len(set(major_minor(v) for v in versions)) == 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            'canonical': self.canonical,
            'metadata_version': self.metadata_version,
            'about_version': self.about_version,
            'pyproject_version': self.pyproject_version,
            'git_tag': self.git_tag,
            'outline_edition': self.outline_edition,
            'is_consistent': self.is_consistent
        }


@dataclass
class ExerciseInfo:
    """Exercise information from outline.yml."""
    id: str                          # e.g., "install-config"
    type: str                        # "ge", "lab", "lecture", "multichoice"
    chapter_keyword: str             # e.g., "install"
    topic_keyword: str               # e.g., "config"
    title: Optional[str] = None
    time_minutes: Optional[int] = None
    objectives: List[str] = field(default_factory=list)

    @property
    def full_id(self) -> str:
        """Full exercise ID with type suffix."""
        if self.type in ('ge', 'lab'):
            return f"{self.chapter_keyword}-{self.topic_keyword}-{self.type}"
        return f"{self.chapter_keyword}-{self.topic_keyword}"

    @property
    def lab_name(self) -> str:
        """Name used with 'lab' command."""
        return f"{self.chapter_keyword}-{self.topic_keyword}"


@dataclass
class CourseInfo:
    """Complete auto-detected course information."""
    # Basic identification
    course_code: str
    course_title: Optional[str] = None
    sku: Optional[str] = None

    # Version information
    version: VersionInfo = field(default_factory=VersionInfo)

    # Course type and framework
    course_type: CourseType = CourseType.UNKNOWN
    lab_framework: LabFramework = LabFramework.UNKNOWN
    lab_framework_version: Optional[str] = None  # e.g., "4.45.0" for rht-labs-core

    # Paths
    repo_path: Optional[Path] = None
    classroom_path: Optional[Path] = None
    content_path: Optional[Path] = None

    # Exercises
    exercises: List[ExerciseInfo] = field(default_factory=list)
    chapters: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    product_name: Optional[str] = None
    product_version: Optional[str] = None
    architects: List[str] = field(default_factory=list)
    authors: List[str] = field(default_factory=list)
    status: Optional[str] = None

    # Detection confidence
    detection_confidence: float = 0.0  # 0-1
    detection_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'course_code': self.course_code,
            'course_title': self.course_title,
            'sku': self.sku,
            'version': self.version.to_dict(),
            'course_type': self.course_type.value,
            'lab_framework': self.lab_framework.value,
            'lab_framework_version': self.lab_framework_version,
            'repo_path': str(self.repo_path) if self.repo_path else None,
            'exercises_count': len(self.exercises),
            'chapters_count': len(self.chapters),
            'product_name': self.product_name,
            'product_version': self.product_version,
            'status': self.status,
            'detection_confidence': self.detection_confidence,
            'detection_notes': self.detection_notes
        }


class CourseDetector:
    """
    Auto-detects course metadata and structure from a repository.

    Usage:
        detector = CourseDetector("/path/to/AU467")
        course_info = detector.detect()

        print(f"Course: {course_info.course_code}")
        print(f"Version: {course_info.version.canonical}")
        print(f"Type: {course_info.course_type.value}")
        print(f"Exercises: {len(course_info.exercises)}")
    """

    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path).expanduser().resolve()
        self._notes: List[str] = []

    def detect(self) -> CourseInfo:
        """Run full auto-detection and return CourseInfo."""
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {self.repo_path}")

        # Start with basic info
        course_code = self._detect_course_code()
        info = CourseInfo(
            course_code=course_code,
            repo_path=self.repo_path
        )

        # Detect each aspect
        info.version = self._detect_version()
        info.course_type = self._detect_course_type()
        info.lab_framework, info.lab_framework_version = self._detect_lab_framework()

        # Detect paths
        info.classroom_path = self._find_classroom_path()
        info.content_path = self._find_content_path()

        # Parse metadata and outline
        self._parse_metadata(info)
        self._parse_outline(info)

        # Calculate detection confidence
        info.detection_confidence = self._calculate_confidence(info)
        info.detection_notes = self._notes.copy()

        return info

    def _detect_course_code(self) -> str:
        """Detect course code from metadata.yml or directory name."""
        # Try metadata.yml first
        metadata_path = self.repo_path / "metadata.yml"
        if metadata_path.exists():
            try:
                with open(metadata_path) as f:
                    metadata = yaml.safe_load(f)
                    if metadata and 'code' in metadata:
                        self._notes.append("Course code from metadata.yml")
                        return metadata['code']
            except Exception:
                pass

        # Fall back to directory name
        dir_name = self.repo_path.name
        # Extract course code pattern (e.g., AU467, DO374, RH294)
        match = re.match(r'^([A-Z]{2}\d{3,4}[A-Z]?)', dir_name)
        if match:
            self._notes.append("Course code from directory name")
            return match.group(1)

        self._notes.append("Could not detect course code, using directory name")
        return dir_name

    def _detect_version(self) -> VersionInfo:
        """Detect version from multiple sources."""
        version = VersionInfo()

        # 1. metadata.yml
        metadata_path = self.repo_path / "metadata.yml"
        if metadata_path.exists():
            try:
                with open(metadata_path) as f:
                    metadata = yaml.safe_load(f)
                    if metadata and 'version' in metadata:
                        version.metadata_version = str(metadata['version'])
            except Exception:
                pass

        # 2. __about__.py (in classroom/grading/src/<pkg>/)
        about_paths = list(self.repo_path.glob("classroom/grading/src/*/__about__.py"))
        if about_paths:
            try:
                content = about_paths[0].read_text()
                match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    version.about_version = match.group(1)
            except Exception:
                pass

        # 3. pyproject.toml (check if version is static)
        pyproject_path = self.repo_path / "classroom" / "grading" / "pyproject.toml"
        if pyproject_path.exists():
            try:
                content = pyproject_path.read_text()
                # Check for static version
                match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
                if match:
                    version.pyproject_version = match.group(1)
            except Exception:
                pass

        # 4. outline.yml edition
        outline_path = self.repo_path / "outline.yml"
        if outline_path.exists():
            try:
                with open(outline_path) as f:
                    outline = yaml.safe_load(f)
                    if outline and 'course' in outline:
                        courseinfo = outline['course'].get('courseinfo', {})
                        if 'edition' in courseinfo:
                            version.outline_edition = str(courseinfo['edition'])
            except Exception:
                pass

        # 5. Git tag (latest)
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'describe', '--tags', '--abbrev=0'],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                version.git_tag = result.stdout.strip()
        except Exception:
            pass

        return version

    def _detect_course_type(self) -> CourseType:
        """Detect if course uses scaffolding or traditional build."""
        # Check for scaffolding indicators
        outline_path = self.repo_path / "outline.yml"
        if outline_path.exists():
            try:
                with open(outline_path) as f:
                    outline = yaml.safe_load(f)
                    if outline and 'skeleton' in outline:
                        self._notes.append("Scaffolding detected via outline.yml skeleton reference")
                        return CourseType.SCAFFOLDING
            except Exception:
                pass

        # Check for content/ directory structure (scaffolding)
        content_dir = self.repo_path / "content"
        if content_dir.exists() and (content_dir / "introduction").exists():
            self._notes.append("Scaffolding detected via content/ structure")
            return CourseType.SCAFFOLDING

        # Check for guides/ directory (traditional)
        guides_dir = self.repo_path / "guides"
        if guides_dir.exists():
            self._notes.append("Traditional structure detected via guides/ directory")
            return CourseType.TRADITIONAL

        self._notes.append("Could not determine course type")
        return CourseType.UNKNOWN

    def _detect_lab_framework(self) -> Tuple[LabFramework, Optional[str]]:
        """Detect lab framework and version."""
        pyproject_path = self.repo_path / "classroom" / "grading" / "pyproject.toml"

        if not pyproject_path.exists():
            # Check for shell scripts
            grading_dir = self.repo_path / "classroom" / "grading"
            if grading_dir.exists():
                shell_scripts = list(grading_dir.glob("**/*.sh"))
                if shell_scripts:
                    self._notes.append("Shell-based grading detected")
                    return LabFramework.SHELL_SCRIPTS, None

            self._notes.append("No lab framework detected")
            return LabFramework.NONE, None

        try:
            content = pyproject_path.read_text()

            # Check for rht-labs-core (Dynolabs 5)
            match = re.search(r'rht-labs-core[=<>~]+([0-9.]+)', content)
            if match:
                version = match.group(1)
                major = int(version.split('.')[0])
                if major >= 4:
                    self._notes.append(f"Dynolabs 5 detected (rht-labs-core {version})")
                    return LabFramework.DYNOLABS_5, version
                else:
                    self._notes.append(f"Dynolabs 4 detected (rht-labs-core {version})")
                    return LabFramework.DYNOLABS_4, version

            # Check for aap_api
            if 'aap_api' in content or 'aap-api' in content:
                self._notes.append("AAP API lab framework detected")
                return LabFramework.AAP_API, None

            # Generic Python project
            self._notes.append("Python-based labs detected (unknown framework)")
            return LabFramework.UNKNOWN, None

        except Exception:
            return LabFramework.UNKNOWN, None

    def _find_classroom_path(self) -> Optional[Path]:
        """Find the classroom/grading directory."""
        paths_to_try = [
            self.repo_path / "classroom" / "grading",
            self.repo_path / "grading",
            self.repo_path / "labs"
        ]
        for path in paths_to_try:
            if path.exists():
                return path
        return None

    def _find_content_path(self) -> Optional[Path]:
        """Find the content directory."""
        paths_to_try = [
            self.repo_path / "content",
            self.repo_path / "guides"
        ]
        for path in paths_to_try:
            if path.exists():
                return path
        return None

    def _parse_metadata(self, info: CourseInfo):
        """Parse metadata.yml for additional info."""
        metadata_path = self.repo_path / "metadata.yml"
        if not metadata_path.exists():
            return

        try:
            with open(metadata_path) as f:
                metadata = yaml.safe_load(f)
                if not metadata:
                    return

                info.sku = metadata.get('code')

        except Exception as e:
            self._notes.append(f"Error parsing metadata.yml: {e}")

    def _parse_outline(self, info: CourseInfo):
        """Parse outline.yml for course structure and exercises."""
        outline_path = self.repo_path / "outline.yml"
        if not outline_path.exists():
            self._notes.append("No outline.yml found")
            return

        try:
            with open(outline_path) as f:
                outline = yaml.safe_load(f)
                if not outline:
                    return

                # Handle both 'course' and 'lesson' structures
                if 'course' in outline:
                    root = outline['course']
                    info_key = 'courseinfo'
                elif 'lesson' in outline:
                    root = outline['lesson']
                    info_key = 'lessoninfo'
                else:
                    self._notes.append("outline.yml has unknown structure (no 'course' or 'lesson' key)")
                    return

                # Course/lesson info
                courseinfo = root.get(info_key, {})
                info.course_title = courseinfo.get('title') or courseinfo.get('goal')
                info.sku = courseinfo.get('sku')
                info.product_name = courseinfo.get('product_name')
                info.product_version = courseinfo.get('product_number')
                info.architects = courseinfo.get('architects', [])
                info.authors = courseinfo.get('authors', [])
                info.status = courseinfo.get('status')

                # Parse chapters and exercises
                chapters = root.get('chapters', [])
                for chapter in chapters:
                    chapter_keyword = chapter.get('keyword', '')
                    chapter_title = chapter.get('title', '')

                    info.chapters.append({
                        'keyword': chapter_keyword,
                        'title': chapter_title,
                        'goal': chapter.get('goal', '')
                    })

                    # Parse topics within chapter
                    topics = chapter.get('topics', [])
                    for topic in topics:
                        topic_keyword = topic.get('keyword', '')
                        topic_title = topic.get('title', '')

                        # Parse sections (exercises) within topic
                        sections = topic.get('sections', [])
                        for section in sections:
                            section_type = section.get('type', '')

                            # Only track GEs and Labs as exercises
                            if section_type in ('ge', 'lab'):
                                exercise = ExerciseInfo(
                                    id=f"{chapter_keyword}-{topic_keyword}",
                                    type=section_type,
                                    chapter_keyword=chapter_keyword,
                                    topic_keyword=topic_keyword,
                                    title=topic_title,
                                    time_minutes=section.get('time'),
                                    objectives=section.get('objectives', [])
                                )
                                info.exercises.append(exercise)

                self._notes.append(f"Parsed {len(info.chapters)} chapters, {len(info.exercises)} exercises from outline.yml")

        except Exception as e:
            self._notes.append(f"Error parsing outline.yml: {e}")

    def _calculate_confidence(self, info: CourseInfo) -> float:
        """Calculate detection confidence score (0-1)."""
        score = 0.0
        max_score = 0.0

        # Course code detection
        max_score += 1.0
        if info.course_code and info.course_code != self.repo_path.name:
            score += 1.0  # Detected from metadata
        elif info.course_code:
            score += 0.5  # From directory name

        # Version detection
        max_score += 1.0
        if info.version.metadata_version:
            score += 0.5
        if info.version.is_consistent:
            score += 0.5

        # Course type detection
        max_score += 1.0
        if info.course_type != CourseType.UNKNOWN:
            score += 1.0

        # Lab framework detection
        max_score += 1.0
        if info.lab_framework != LabFramework.UNKNOWN:
            score += 1.0

        # Exercises detection
        max_score += 1.0
        if len(info.exercises) > 0:
            score += 1.0

        return score / max_score if max_score > 0 else 0.0


def detect_course(repo_path: str | Path) -> CourseInfo:
    """
    Convenience function to detect course information.

    Args:
        repo_path: Path to course repository

    Returns:
        CourseInfo with detected information
    """
    detector = CourseDetector(repo_path)
    return detector.detect()
