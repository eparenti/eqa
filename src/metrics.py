"""Quality metrics calculation for exercise testing.

Provides industry-standard quality metrics:
- Coverage: % of exercises tested
- Defect Density: Bugs per exercise
- Success Rate: % of exercises passed
- Quality Score: 0-100 overall quality rating
- Performance: Duration and timeout analysis
"""

from dataclasses import dataclass, field
from typing import List, Dict
from .models import SimulationResult, BugSeverity, ExerciseType


@dataclass
class QualityMetrics:
    """Quality metrics for a test run."""

    # Coverage metrics
    total_exercises: int = 0
    exercises_tested: int = 0
    coverage_percentage: float = 0.0

    # Success metrics
    exercises_passed: int = 0
    exercises_failed: int = 0
    success_rate: float = 0.0

    # Defect metrics
    total_bugs: int = 0
    p0_bugs: int = 0
    p1_bugs: int = 0
    p2_bugs: int = 0
    p3_bugs: int = 0
    defect_density: float = 0.0  # Bugs per exercise
    critical_ratio: float = 0.0  # P0+P1 / total bugs

    # Performance metrics
    total_duration: float = 0.0
    avg_duration_per_exercise: float = 0.0
    min_duration: float = 0.0
    max_duration: float = 0.0

    # Grading validation metrics (for Labs)
    labs_tested: int = 0
    labs_with_grading_bugs: int = 0
    grading_validation_pass_rate: float = 0.0

    # Idempotency metrics
    idempotency_tested: int = 0
    idempotent_exercises: int = 0
    idempotency_pass_rate: float = 0.0

    # Overall quality score (0-100)
    quality_score: float = 0.0
    quality_grade: str = "N/A"  # A, B, C, D, F

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'coverage': {
                'total_exercises': self.total_exercises,
                'exercises_tested': self.exercises_tested,
                'coverage_percentage': round(self.coverage_percentage, 1),
            },
            'success': {
                'exercises_passed': self.exercises_passed,
                'exercises_failed': self.exercises_failed,
                'success_rate': round(self.success_rate, 1),
            },
            'defects': {
                'total_bugs': self.total_bugs,
                'by_severity': {
                    'P0': self.p0_bugs,
                    'P1': self.p1_bugs,
                    'P2': self.p2_bugs,
                    'P3': self.p3_bugs,
                },
                'defect_density': round(self.defect_density, 2),
                'critical_ratio': round(self.critical_ratio, 1),
            },
            'performance': {
                'total_duration': round(self.total_duration, 1),
                'avg_duration_per_exercise': round(self.avg_duration_per_exercise, 1),
                'min_duration': round(self.min_duration, 1),
                'max_duration': round(self.max_duration, 1),
            },
            'grading_validation': {
                'labs_tested': self.labs_tested,
                'labs_with_grading_bugs': self.labs_with_grading_bugs,
                'pass_rate': round(self.grading_validation_pass_rate, 1),
            },
            'idempotency': {
                'tested': self.idempotency_tested,
                'idempotent': self.idempotent_exercises,
                'pass_rate': round(self.idempotency_pass_rate, 1),
            },
            'quality_score': {
                'score': round(self.quality_score, 1),
                'grade': self.quality_grade,
            },
        }


def calculate_metrics(results: List[SimulationResult],
                      total_exercises: int = None) -> QualityMetrics:
    """Calculate quality metrics from simulation results.

    Args:
        results: List of simulation results
        total_exercises: Total number of exercises in course (for coverage)

    Returns:
        QualityMetrics with calculated values
    """
    if not results:
        return QualityMetrics()

    metrics = QualityMetrics()

    # Coverage
    metrics.exercises_tested = len(results)
    if total_exercises:
        metrics.total_exercises = total_exercises
        metrics.coverage_percentage = (metrics.exercises_tested / total_exercises) * 100
    else:
        metrics.total_exercises = metrics.exercises_tested
        metrics.coverage_percentage = 100.0

    # Success rate
    metrics.exercises_passed = sum(1 for r in results if r.success)
    metrics.exercises_failed = len(results) - metrics.exercises_passed
    metrics.success_rate = (metrics.exercises_passed / len(results)) * 100

    # Defect metrics
    all_bugs = [bug for r in results for bug in r.bugs]
    metrics.total_bugs = len(all_bugs)
    metrics.p0_bugs = sum(1 for b in all_bugs if b.severity == BugSeverity.P0_BLOCKER)
    metrics.p1_bugs = sum(1 for b in all_bugs if b.severity == BugSeverity.P1_CRITICAL)
    metrics.p2_bugs = sum(1 for b in all_bugs if b.severity == BugSeverity.P2_HIGH)
    metrics.p3_bugs = sum(1 for b in all_bugs if b.severity == BugSeverity.P3_LOW)

    if metrics.exercises_tested > 0:
        metrics.defect_density = metrics.total_bugs / metrics.exercises_tested

    if metrics.total_bugs > 0:
        critical_bugs = metrics.p0_bugs + metrics.p1_bugs
        metrics.critical_ratio = (critical_bugs / metrics.total_bugs) * 100

    # Performance metrics
    durations = [r.total_duration_seconds for r in results if r.total_duration_seconds > 0]
    if durations:
        metrics.total_duration = sum(durations)
        metrics.avg_duration_per_exercise = metrics.total_duration / len(durations)
        metrics.min_duration = min(durations)
        metrics.max_duration = max(durations)

    # Grading validation metrics (for Labs)
    lab_results = [r for r in results if r.exercise_type == ExerciseType.LAB]
    metrics.labs_tested = len(lab_results)

    if metrics.labs_tested > 0:
        # Count labs with grading bugs
        labs_with_bugs = 0
        for r in lab_results:
            has_grading_bug = False
            # Grading passed without solution (should fail)
            if r.grade_without_solution_passed is True:
                has_grading_bug = True
            # Grading failed with solution (should pass)
            if r.grade_with_solution_passed is False:
                has_grading_bug = True
            if has_grading_bug:
                labs_with_bugs += 1

        metrics.labs_with_grading_bugs = labs_with_bugs
        metrics.grading_validation_pass_rate = ((metrics.labs_tested - labs_with_bugs) / metrics.labs_tested) * 100

    # Idempotency metrics
    # Group by exercise_id to find multi-cycle tests
    exercise_cycles = {}
    for r in results:
        if r.exercise_id not in exercise_cycles:
            exercise_cycles[r.exercise_id] = []
        exercise_cycles[r.exercise_id].append(r)

    # Find exercises tested with multiple cycles
    multi_cycle_exercises = {ex_id: cycles for ex_id, cycles in exercise_cycles.items() if len(cycles) > 1}
    metrics.idempotency_tested = len(multi_cycle_exercises)

    if metrics.idempotency_tested > 0:
        idempotent_count = 0
        for ex_id, cycles in multi_cycle_exercises.items():
            # Idempotent if all cycles passed
            if all(c.success for c in cycles):
                idempotent_count += 1
        metrics.idempotent_exercises = idempotent_count
        metrics.idempotency_pass_rate = (idempotent_count / metrics.idempotency_tested) * 100

    # Calculate overall quality score (0-100)
    metrics.quality_score = _calculate_quality_score(metrics)
    metrics.quality_grade = _score_to_grade(metrics.quality_score)

    return metrics


def _calculate_quality_score(metrics: QualityMetrics) -> float:
    """Calculate overall quality score (0-100).

    Weighted formula:
    - Coverage: 20%
    - Success Rate: 30%
    - Defect Severity: 30%
    - Grading Validation: 10%
    - Idempotency: 10%
    """
    score = 0.0

    # Coverage component (20 points max)
    coverage_score = (metrics.coverage_percentage / 100) * 20
    score += coverage_score

    # Success rate component (30 points max)
    success_score = (metrics.success_rate / 100) * 30
    score += success_score

    # Defect severity component (30 points max)
    # Deduct points based on defect density and critical ratio
    defect_score = 30

    # Deduct for defect density (target: < 0.5 bugs/exercise)
    if metrics.defect_density > 0:
        density_penalty = min(metrics.defect_density * 10, 15)  # Max 15 point penalty
        defect_score -= density_penalty

    # Deduct for high critical ratio (target: < 20%)
    if metrics.critical_ratio > 20:
        critical_penalty = ((metrics.critical_ratio - 20) / 80) * 15  # Max 15 point penalty
        defect_score -= critical_penalty

    score += max(0, defect_score)

    # Grading validation component (10 points max)
    if metrics.labs_tested > 0:
        grading_score = (metrics.grading_validation_pass_rate / 100) * 10
        score += grading_score
    else:
        # No labs tested, give full points
        score += 10

    # Idempotency component (10 points max)
    if metrics.idempotency_tested > 0:
        idem_score = (metrics.idempotency_pass_rate / 100) * 10
        score += idem_score
    else:
        # No idempotency tests, give full points
        score += 10

    return max(0, min(100, score))


def _score_to_grade(score: float) -> str:
    """Convert numeric score to letter grade."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


def format_metrics_report(metrics: QualityMetrics) -> str:
    """Generate a formatted metrics report as markdown.

    Args:
        metrics: Quality metrics to report

    Returns:
        Markdown-formatted metrics report
    """
    lines = ["# Quality Metrics Report", ""]

    # Overall quality score (prominent at top)
    lines.append(f"## Overall Quality: {metrics.quality_score:.1f}/100 (Grade: {metrics.quality_grade})")
    lines.append("")

    # Coverage
    lines.append("## Coverage")
    lines.append("")
    lines.append(f"- **Exercises Tested**: {metrics.exercises_tested}/{metrics.total_exercises}")
    lines.append(f"- **Coverage**: {metrics.coverage_percentage:.1f}%")
    lines.append("")

    # Success Rate
    lines.append("## Success Rate")
    lines.append("")
    lines.append(f"- **Passed**: {metrics.exercises_passed}")
    lines.append(f"- **Failed**: {metrics.exercises_failed}")
    lines.append(f"- **Success Rate**: {metrics.success_rate:.1f}%")
    lines.append("")

    # Defects
    lines.append("## Defects")
    lines.append("")
    lines.append(f"- **Total Bugs**: {metrics.total_bugs}")
    lines.append(f"- **P0 (Blocker)**: {metrics.p0_bugs}")
    lines.append(f"- **P1 (Critical)**: {metrics.p1_bugs}")
    lines.append(f"- **P2 (High)**: {metrics.p2_bugs}")
    lines.append(f"- **P3 (Low)**: {metrics.p3_bugs}")
    lines.append(f"- **Defect Density**: {metrics.defect_density:.2f} bugs/exercise")
    lines.append(f"- **Critical Ratio**: {metrics.critical_ratio:.1f}% (P0+P1)")
    lines.append("")

    # Quality thresholds
    lines.append("### Quality Thresholds")
    lines.append("")
    density_status = "✓ Good" if metrics.defect_density < 0.5 else "✗ Needs Improvement"
    critical_status = "✓ Good" if metrics.critical_ratio < 20 else "✗ Needs Improvement"
    lines.append(f"- **Defect Density**: {density_status} (target: < 0.5)")
    lines.append(f"- **Critical Ratio**: {critical_status} (target: < 20%)")
    lines.append("")

    # Performance
    if metrics.total_duration > 0:
        lines.append("## Performance")
        lines.append("")
        lines.append(f"- **Total Duration**: {metrics.total_duration:.1f}s ({metrics.total_duration/60:.1f} min)")
        lines.append(f"- **Average per Exercise**: {metrics.avg_duration_per_exercise:.1f}s")
        lines.append(f"- **Min Duration**: {metrics.min_duration:.1f}s")
        lines.append(f"- **Max Duration**: {metrics.max_duration:.1f}s")
        lines.append("")

    # Grading Validation
    if metrics.labs_tested > 0:
        lines.append("## Grading Validation (Labs)")
        lines.append("")
        lines.append(f"- **Labs Tested**: {metrics.labs_tested}")
        lines.append(f"- **Labs with Grading Bugs**: {metrics.labs_with_grading_bugs}")
        lines.append(f"- **Validation Pass Rate**: {metrics.grading_validation_pass_rate:.1f}%")
        lines.append("")

    # Idempotency
    if metrics.idempotency_tested > 0:
        lines.append("## Idempotency")
        lines.append("")
        lines.append(f"- **Exercises Tested**: {metrics.idempotency_tested}")
        lines.append(f"- **Idempotent**: {metrics.idempotent_exercises}")
        lines.append(f"- **Pass Rate**: {metrics.idempotency_pass_rate:.1f}%")
        lines.append("")

    # Score breakdown
    lines.append("## Quality Score Breakdown")
    lines.append("")
    lines.append("The quality score (0-100) is calculated from:")
    lines.append("")
    lines.append(f"- **Coverage** (20%): {(metrics.coverage_percentage / 100) * 20:.1f}/20")
    lines.append(f"- **Success Rate** (30%): {(metrics.success_rate / 100) * 30:.1f}/30")
    lines.append("- **Defect Severity** (30%): Based on defect density and critical ratio")
    lines.append(f"- **Grading Validation** (10%): {(metrics.grading_validation_pass_rate / 100) * 10:.1f}/10" if metrics.labs_tested > 0 else "- **Grading Validation** (10%): 10.0/10 (no labs)")
    lines.append(f"- **Idempotency** (10%): {(metrics.idempotency_pass_rate / 100) * 10:.1f}/10" if metrics.idempotency_tested > 0 else "- **Idempotency** (10%): 10.0/10 (not tested)")
    lines.append("")

    return "\n".join(lines)
