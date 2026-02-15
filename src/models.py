"""Data models for eqa."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any
from pathlib import Path


class ExerciseType(Enum):
    """Exercise type classification."""
    LAB = "Lab"
    GUIDED_EXERCISE = "GE"
    UNKNOWN = "Unknown"


class BugSeverity(Enum):
    """Bug severity levels."""
    P0_BLOCKER = "P0"
    P1_CRITICAL = "P1"
    P2_HIGH = "P2"
    P3_LOW = "P3"


class StepResult(Enum):
    """Result of executing a step."""
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    WARN = "warn"


@dataclass
class Bug:
    """A defect found during testing."""
    id: str
    severity: BugSeverity
    exercise_id: str
    description: str
    fix_recommendation: str
    verification_steps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'severity': self.severity.value,
            'exercise_id': self.exercise_id,
            'description': self.description,
            'fix_recommendation': self.fix_recommendation,
            'verification_steps': self.verification_steps,
        }


@dataclass
class ExecutedStep:
    """Result of executing a single EPUB step."""
    number: str
    text: str
    result: StepResult
    command: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    is_file_action: bool = False


@dataclass
class SimulationResult:
    """Complete result of student simulation for one exercise."""
    exercise_id: str
    exercise_type: ExerciseType
    success: bool
    phase: str  # "start", "instructions", "grade", "finish"
    steps_executed: List[ExecutedStep] = field(default_factory=list)
    steps_passed: int = 0
    steps_failed: int = 0
    total_duration_seconds: float = 0.0
    error_message: Optional[str] = None
    lab_start_output: str = ""
    lab_grade_output: str = ""
    lab_finish_output: str = ""
    bugs: List[Bug] = field(default_factory=list)
    # Enhanced grading validation
    grade_without_solution_passed: Optional[bool] = None  # Should be False
    grade_with_solution_passed: Optional[bool] = None     # Should be True
    # Idempotency testing
    cycle: int = 1  # Which cycle this result is from (1, 2, 3, ...)

    @property
    def summary(self) -> str:
        """Human-readable summary."""
        if self.success:
            return f"PASS: {self.steps_passed}/{len(self.steps_executed)} steps completed"
        return f"FAIL at {self.phase}: {self.error_message or 'unknown error'}"

    def to_dict(self) -> Dict:
        return {
            'exercise_id': self.exercise_id,
            'exercise_type': self.exercise_type.value,
            'success': self.success,
            'phase': self.phase,
            'summary': self.summary,
            'steps_executed': len(self.steps_executed),
            'steps_passed': self.steps_passed,
            'steps_failed': self.steps_failed,
            'total_duration_seconds': self.total_duration_seconds,
            'error_message': self.error_message,
            'bugs': [b.to_dict() for b in self.bugs],
        }


@dataclass
class ExerciseContext:
    """Context for an exercise under test."""
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

    @property
    def lab_name(self) -> str:
        """Get the lab command name."""
        return self.id

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
        }


@dataclass
class CourseContext:
    """Course structure and metadata."""
    course_code: str
    course_title: str
    version: str
    pattern: str
    epub_path: Optional[Path] = None
    lesson_repos: Dict[str, Path] = field(default_factory=dict)
    exercises: List[ExerciseContext] = field(default_factory=list)

    def get_exercise(self, exercise_id: str) -> Optional[ExerciseContext]:
        """Find exercise by ID."""
        for ex in self.exercises:
            if ex.id == exercise_id:
                return ex
        return None


@dataclass
class CourseResults:
    """Aggregated results for an entire course run."""
    course_code: str
    test_date: str
    total_exercises: int
    exercises_tested: int
    exercises_passed: int
    exercises_failed: int
    total_duration_seconds: float
    results: List[SimulationResult] = field(default_factory=list)
    all_bugs: List[Bug] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'course_code': self.course_code,
            'test_date': self.test_date,
            'total_exercises': self.total_exercises,
            'exercises_tested': self.exercises_tested,
            'exercises_passed': self.exercises_passed,
            'exercises_failed': self.exercises_failed,
            'total_duration_seconds': self.total_duration_seconds,
            'results': [r.to_dict() for r in self.results],
            'all_bugs': [b.to_dict() for b in self.all_bugs],
        }
