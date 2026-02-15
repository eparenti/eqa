"""Quality metrics and performance budget calculation."""

from dataclasses import dataclass, field
from typing import Dict, List
from ..core.models import CourseTestResults, BugSeverity


@dataclass
class QualityMetrics:
    """Quality metrics for course testing."""
    pass_rate: float  # Percentage of exercises passing
    total_bugs: int
    bugs_by_severity: Dict[str, int]
    defect_density: float  # Bugs per exercise
    critical_ratio: float  # Percentage of P0/P1 bugs
    test_coverage: float  # Percentage of test categories executed
    avg_duration: float  # Average test duration per exercise
    total_duration: float  # Total test time

    def to_dict(self) -> Dict:
        return {
            'pass_rate': round(self.pass_rate, 1),
            'total_bugs': self.total_bugs,
            'bugs_by_severity': self.bugs_by_severity,
            'defect_density': round(self.defect_density, 2),
            'critical_ratio': round(self.critical_ratio, 1),
            'test_coverage': round(self.test_coverage, 1),
            'avg_duration': round(self.avg_duration, 2),
            'total_duration': round(self.total_duration, 2)
        }


@dataclass
class PerformanceBudget:
    """Performance budget for test categories."""
    category: str
    budget_seconds: float
    actual_seconds: float
    over_budget: bool
    percentage: float  # Actual as % of budget

    def to_dict(self) -> Dict:
        return {
            'category': self.category,
            'budget_seconds': self.budget_seconds,
            'actual_seconds': round(self.actual_seconds, 2),
            'over_budget': self.over_budget,
            'percentage': round(self.percentage, 1)
        }


@dataclass
class BudgetReport:
    """Performance budget report."""
    budgets: List[PerformanceBudget] = field(default_factory=list)
    total_budget: float = 0.0
    total_actual: float = 0.0
    within_budget: bool = True

    def to_dict(self) -> Dict:
        return {
            'budgets': [b.to_dict() for b in self.budgets],
            'total_budget': round(self.total_budget, 2),
            'total_actual': round(self.total_actual, 2),
            'within_budget': self.within_budget
        }


class MetricsCalculator:
    """Calculates quality metrics from test results."""

    # Default performance budgets (seconds per test category)
    DEFAULT_BUDGETS = {
        'TC-PREREQ': 10.0,
        'TC-SOL': 10.0,
        'TC-GRADE': 60.0,
        'TC-SOLVE': 60.0,
        'TC-VERIFY': 30.0,
        'TC-WORKFLOW': 45.0,
        'TC-EXEC': 30.0,
        'TC-CLEAN': 120.0,
        'TC-IDEM': 300.0,
        'TC-E2E': 300.0,
        'TC-LINT': 30.0,
        'TC-VARS': 30.0,
        'TC-DEPS': 30.0,
        'TC-INSTRUCT': 30.0,
        'TC-SECURITY': 30.0,
        'TC-CONTRACT': 90.0,
        'TC-NETWORK': 60.0,
        'TC-EE': 30.0,
        'TC-AAP': 60.0,
        'TC-PERF': 60.0,
        'TC-ROLLBACK': 120.0,
        'TC-WEB': 60.0,
        'TC-DYNOLABS': 30.0,
    }

    def __init__(self, results: CourseTestResults):
        """Initialize metrics calculator."""
        self.results = results

    def calculate_quality_metrics(self) -> QualityMetrics:
        """Calculate quality metrics."""
        # Pass rate
        pass_rate = (self.results.exercises_passed / self.results.exercises_tested * 100) \
                    if self.results.exercises_tested > 0 else 0

        # Bugs by severity
        bugs_by_severity = {
            'P0': 0,
            'P1': 0,
            'P2': 0,
            'P3': 0
        }
        for bug in self.results.all_bugs:
            bugs_by_severity[bug.severity.value] += 1

        # Defect density (bugs per exercise)
        defect_density = len(self.results.all_bugs) / self.results.exercises_tested \
                        if self.results.exercises_tested > 0 else 0

        # Critical ratio (percentage of P0/P1 bugs)
        critical_bugs = bugs_by_severity['P0'] + bugs_by_severity['P1']
        critical_ratio = (critical_bugs / len(self.results.all_bugs) * 100) \
                        if len(self.results.all_bugs) > 0 else 0

        # Test coverage (percentage of test categories run out of 23 available)
        total_categories = 23
        categories_run = self._count_unique_categories()
        test_coverage = min(categories_run / total_categories * 100, 100) if total_categories > 0 else 0

        # Duration metrics
        avg_duration = self.results.total_duration_seconds / self.results.exercises_tested \
                      if self.results.exercises_tested > 0 else 0

        return QualityMetrics(
            pass_rate=pass_rate,
            total_bugs=len(self.results.all_bugs),
            bugs_by_severity=bugs_by_severity,
            defect_density=defect_density,
            critical_ratio=critical_ratio,
            test_coverage=test_coverage,
            avg_duration=avg_duration,
            total_duration=self.results.total_duration_seconds
        )

    def calculate_performance_budget(self) -> BudgetReport:
        """Calculate performance budget compliance."""
        budgets = []
        total_budget = 0.0
        total_actual = 0.0

        # Collect category times across all exercises
        category_times: Dict[str, float] = {}
        for ex_result in self.results.exercise_results:
            for category, test_result in ex_result.test_categories.items():
                if category not in category_times:
                    category_times[category] = 0.0
                category_times[category] += test_result.duration_seconds

        # Compare to budgets
        for category, actual_time in category_times.items():
            budget_time = self.DEFAULT_BUDGETS.get(category, 30.0)  # Default 30s
            over_budget = actual_time > budget_time
            percentage = (actual_time / budget_time * 100) if budget_time > 0 else 0

            budgets.append(PerformanceBudget(
                category=category,
                budget_seconds=budget_time,
                actual_seconds=actual_time,
                over_budget=over_budget,
                percentage=percentage
            ))

            total_budget += budget_time
            total_actual += actual_time

        return BudgetReport(
            budgets=budgets,
            total_budget=total_budget,
            total_actual=total_actual,
            within_budget=(total_actual <= total_budget)
        )

    def _count_unique_categories(self) -> int:
        """Count unique test categories executed."""
        categories = set()
        for ex_result in self.results.exercise_results:
            categories.update(ex_result.test_categories.keys())
        return len(categories)
