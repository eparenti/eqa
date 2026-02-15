"""Core data models for exercise QA."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any
from pathlib import Path


class ExerciseType(Enum):
    """Exercise type classification."""
    LAB = "Lab"
    GUIDED_EXERCISE = "GE"
    UNKNOWN = "Unknown"


class CoursePattern(Enum):
    """Course structure pattern classification."""
    TRADITIONAL = "traditional"      # Standard .sol files, shell grading scripts
    AAP_CONTROLLER = "aap_controller"  # AAP Controller YAML exports
    HYBRID = "hybrid"                # Mix of traditional and Controller
    UNKNOWN = "unknown"


class ExercisePattern(Enum):
    """Exercise content pattern classification."""
    ANSIBLE_PLAYBOOK = "ansible_playbook"    # Traditional Ansible playbooks
    AAP_CONTROLLER = "aap_controller"        # AAP Controller config YAML
    SHELL_SCRIPT = "shell_script"            # Shell-based exercises
    PYTHON = "python"                        # Python-based exercises
    MIXED = "mixed"                          # Multiple patterns
    UNKNOWN = "unknown"


class BugSeverity(Enum):
    """Bug severity levels."""
    P0_BLOCKER = "P0"
    P1_CRITICAL = "P1"
    P2_HIGH = "P2"
    P3_LOW = "P3"


@dataclass
class Bug:
    """Represents a defect found during testing."""
    id: str
    severity: BugSeverity
    category: str
    exercise_id: str
    description: str
    fix_recommendation: str
    verification_steps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'severity': self.severity.value,
            'category': self.category,
            'exercise_id': self.exercise_id,
            'description': self.description,
            'fix_recommendation': self.fix_recommendation,
            'verification_steps': self.verification_steps
        }


@dataclass
class TestResult:
    """Result from a single test category."""
    category: str
    exercise_id: str
    passed: bool
    timestamp: str
    duration_seconds: float
    bugs_found: List[Bug] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'category': self.category,
            'exercise_id': self.exercise_id,
            'passed': self.passed,
            'timestamp': self.timestamp,
            'duration_seconds': self.duration_seconds,
            'bugs_found': [b.to_dict() for b in self.bugs_found],
            'details': self.details
        }


@dataclass
class ExerciseContext:
    """Complete context for an exercise."""
    id: str
    type: ExerciseType
    lesson_code: str
    chapter: int
    chapter_title: str
    title: str
    lesson_path: Optional[Path] = None
    solution_files: List[Path] = field(default_factory=list)
    grading_script: Optional[Path] = None
    materials_dir: Optional[Path] = None
    depends_on: List[str] = field(default_factory=list)
    content_pattern: ExercisePattern = ExercisePattern.UNKNOWN
    course_profile: Optional[Any] = field(default=None, repr=False)

    @property
    def lab_name(self) -> str:
        """Get the lab command name (id without -ge or -lab suffix)."""
        return self.id.removesuffix('-ge').removesuffix('-lab')

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'type': self.type.value,
            'lesson_code': self.lesson_code,
            'chapter': self.chapter,
            'chapter_title': self.chapter_title,
            'title': self.title,
            'lesson_path': str(self.lesson_path) if self.lesson_path else None,
            'solution_files': [str(f) for f in self.solution_files],
            'grading_script': str(self.grading_script) if self.grading_script else None,
            'materials_dir': str(self.materials_dir) if self.materials_dir else None,
            'depends_on': self.depends_on,
            'content_pattern': self.content_pattern.value
        }


@dataclass
class ExerciseTestResults:
    """Complete test results for one exercise."""
    exercise_id: str
    lesson_code: str
    start_time: str
    end_time: str
    duration_seconds: float
    status: str  # PASS, FAIL, SKIP, ERROR
    test_categories: Dict[str, TestResult] = field(default_factory=dict)
    bugs: List[Bug] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict:
        return {
            'exercise_id': self.exercise_id,
            'lesson_code': self.lesson_code,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_seconds': self.duration_seconds,
            'status': self.status,
            'test_categories': {k: v.to_dict() for k, v in self.test_categories.items()},
            'bugs': [b.to_dict() for b in self.bugs],
            'summary': self.summary
        }


@dataclass
class CourseContext:
    """Complete course structure and metadata."""
    course_code: str
    course_title: str
    version: str
    pattern: str
    epub_path: Optional[Path] = None
    lesson_repos: Dict[str, Path] = field(default_factory=dict)
    exercises: List[ExerciseContext] = field(default_factory=list)
    dependency_graph: Dict[str, List[str]] = field(default_factory=dict)
    course_pattern: CoursePattern = CoursePattern.UNKNOWN

    def get_exercise(self, exercise_id: str) -> Optional[ExerciseContext]:
        """Find exercise by ID."""
        for ex in self.exercises:
            if ex.id == exercise_id:
                return ex
        return None


@dataclass
class CourseTestResults:
    """Aggregated results for entire course."""
    course_code: str
    test_date: str
    total_exercises: int
    exercises_tested: int
    exercises_passed: int
    exercises_failed: int
    exercises_skipped: int
    total_duration_seconds: float
    exercise_results: List[ExerciseTestResults] = field(default_factory=list)
    all_bugs: List[Bug] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'course_code': self.course_code,
            'test_date': self.test_date,
            'total_exercises': self.total_exercises,
            'exercises_tested': self.exercises_tested,
            'exercises_passed': self.exercises_passed,
            'exercises_failed': self.exercises_failed,
            'exercises_skipped': self.exercises_skipped,
            'total_duration_seconds': self.total_duration_seconds,
            'exercise_results': [r.to_dict() for r in self.exercise_results],
            'all_bugs': [b.to_dict() for b in self.all_bugs],
            'summary': self.summary
        }
