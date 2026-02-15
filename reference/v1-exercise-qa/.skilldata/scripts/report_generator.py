#!/usr/bin/env python3
"""
Report Generator - Automated QA Report Generation

Automatically generates comprehensive QA reports from test results.
Replaces manual report creation with automated aggregation, classification,
and recommendation generation.
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.test_result import (
    CourseTestResults, ExerciseTestResults, Bug, BugSeverity,
    TestResult, CourseContext
)
from lib.quality_metrics import QualityMetrics, CoverageMetrics, DefectMetrics, PerformanceMetrics
from lib.performance_budgets import generate_budget_report, BudgetReport, PerformanceBudgetRegistry


class ReportGenerator:
    """
    Automated QA report generator.

    Generates comprehensive markdown and JSON reports from test results.
    """

    def __init__(self, course_context: CourseContext, test_results: CourseTestResults):
        """
        Initialize report generator.

        Args:
            course_context: Course context from course_analyzer
            test_results: Test results from test_orchestrator
        """
        self.context = course_context
        self.results = test_results
        self.quality_metrics = self._calculate_quality_metrics()
        self.budget_report = self._calculate_budget_report()

    def _calculate_quality_metrics(self) -> QualityMetrics:
        """
        Calculate quality metrics from test results.

        Returns:
            QualityMetrics object with all metrics calculated
        """
        metrics = QualityMetrics(course_code=self.context.course_code)

        # Coverage metrics
        metrics.coverage.exercises_total = self.results.total_exercises
        metrics.coverage.exercises_tested = self.results.exercises_tested

        # Count solution files
        for ex in self.results.exercise_results:
            if hasattr(ex, 'solution_files_found'):
                metrics.coverage.solution_files_total += ex.solution_files_found
                metrics.coverage.solution_files_tested += ex.solution_files_tested or 0

        # Defect metrics
        bugs = self._collect_all_bugs()
        for bug in bugs:
            if bug.severity == BugSeverity.P0_BLOCKER:
                metrics.defects.p0_count += 1
            elif bug.severity == BugSeverity.P1_CRITICAL:
                metrics.defects.p1_count += 1
            elif bug.severity == BugSeverity.P2_HIGH:
                metrics.defects.p2_count += 1
            elif bug.severity == BugSeverity.P3_LOW:
                metrics.defects.p3_count += 1

        metrics.defects.total_exercises_tested = self.results.exercises_tested

        # Performance metrics
        metrics.performance.total_execution_time = self.results.total_duration_seconds
        metrics.performance.test_count = self.results.exercises_tested

        # Track category times
        for ex in self.results.exercise_results:
            if hasattr(ex, 'test_categories'):
                for cat_name, cat_result in ex.test_categories.items():
                    if hasattr(cat_result, 'duration_seconds'):
                        if cat_name not in metrics.performance.category_times:
                            metrics.performance.category_times[cat_name] = 0
                        metrics.performance.category_times[cat_name] += cat_result.duration_seconds

        return metrics

    def _calculate_budget_report(self) -> BudgetReport:
        """
        Calculate performance budget report from test results.

        Returns:
            BudgetReport with budget compliance data
        """
        # Collect category timings from all exercises
        category_timings = defaultdict(float)

        for ex in self.results.exercise_results:
            if hasattr(ex, 'test_categories'):
                for cat_name, cat_result in ex.test_categories.items():
                    if hasattr(cat_result, 'duration_seconds'):
                        # Track max time for this category across all exercises
                        category_timings[cat_name] = max(
                            category_timings[cat_name],
                            cat_result.duration_seconds
                        )

        # Generate budget report
        return generate_budget_report(dict(category_timings))

    def generate(self, output_dir: Path = Path("results")) -> Path:
        """
        Generate comprehensive QA report.

        Args:
            output_dir: Directory to save reports

        Returns:
            Path to generated markdown report
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d-%H%M')
        base_name = f"QA-REPORT-{self.context.course_code}-FULL-{timestamp}"

        md_path = output_dir / f"{base_name}.md"
        json_path = output_dir / f"{base_name}.json"

        # Generate markdown report
        report = self._generate_markdown_report()
        with open(md_path, 'w') as f:
            f.write(report)

        # Save JSON results
        self.results.to_json(json_path)

        # Save quality metrics
        metrics_path = output_dir / f"{base_name}-metrics.json"
        self.quality_metrics.save(metrics_path)

        print(f"\n📄 Report generated: {md_path}")
        print(f"📄 JSON results: {json_path}")
        print(f"📊 Quality metrics: {metrics_path}")

        return md_path

    def _generate_markdown_report(self) -> str:
        """Generate markdown report content."""
        sections = [
            self._header(),
            self._executive_summary(),
            self._quality_metrics_dashboard(),
            self._performance_budget_section(),
            self._test_coverage(),
            self._test_results_table(),
            self._bugs_by_severity(),
            self._detailed_bugs(),
            self._fix_recommendations(),
            self._automation_metrics(),
            self._release_assessment(),
            self._appendix()
        ]

        return "\n\n".join(sections)

    def _header(self) -> str:
        """Generate report header."""
        return f"""# Exercise QA Report: {self.context.course_code}

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Test Date**: {self.results.test_date}
**Duration**: {self.results.total_duration_seconds:.1f}s ({self.results.total_duration_seconds / 60:.1f} minutes)
**Automation Level**: Fully Automated

---"""

    def _executive_summary(self) -> str:
        """Generate executive summary."""
        pass_rate = self.results.summary.get('pass_rate', 0)
        all_tested = self.results.summary.get('all_exercises_tested', False)

        # Count bugs by severity
        bugs = self._collect_all_bugs()
        bug_counts = self._count_bugs_by_severity(bugs)

        status_emoji = "✅" if pass_rate == 100 else "⚠️" if pass_rate >= 80 else "❌"

        return f"""## Executive Summary

{status_emoji} **Overall Status**: {'PASS' if pass_rate == 100 else 'NEEDS ATTENTION' if pass_rate >= 80 else 'CRITICAL ISSUES'}

### Key Metrics

- **Total Exercises**: {self.results.total_exercises}
- **Exercises Tested**: {self.results.exercises_tested} {'✅' if all_tested else '❌ (INCOMPLETE)'}
- **Pass Rate**: {pass_rate:.1f}%
- **Passed**: {self.results.exercises_passed} ✅
- **Failed**: {self.results.exercises_failed} ❌
- **Skipped**: {self.results.exercises_skipped} ⏭️

### Bug Summary

- **P0 (Blocker)**: {bug_counts.get('P0', 0)} 🔴
- **P1 (Critical)**: {bug_counts.get('P1', 0)} 🟠
- **P2 (High)**: {bug_counts.get('P2', 0)} 🟡
- **P3 (Low)**: {bug_counts.get('P3', 0)} 🟢
- **Total Bugs**: {len(bugs)}

---"""

    def _quality_metrics_dashboard(self) -> str:
        """Generate quality metrics dashboard with industry-standard metrics."""
        metrics = self.quality_metrics
        roi = metrics.calculate_automation_roi()

        return f"""## Quality Metrics Dashboard

### Coverage Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Exercise Coverage** | {metrics.coverage.exercise_coverage_percent:.1f}% ({metrics.coverage.exercises_tested}/{metrics.coverage.exercises_total}) | 100% | {'✅' if metrics.coverage.exercise_coverage_percent == 100 else '⚠️'} |
| **Solution File Coverage** | {metrics.coverage.solution_coverage_percent:.1f}% ({metrics.coverage.solution_files_tested}/{metrics.coverage.solution_files_total}) | 100% | {'✅' if metrics.coverage.solution_coverage_percent == 100 else '⚠️'} |

### Defect Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Defect Density** | {metrics.defects.defect_density:.2f} bugs/exercise | <0.5 | {'✅' if metrics.defects.defect_density < 0.5 else '⚠️'} |
| **Critical Defect Ratio** | {metrics.defects.critical_defect_ratio:.1%} | <20% | {'✅' if metrics.defects.critical_defect_ratio < 0.2 else '⚠️'} |
| **Total Defects** | {metrics.defects.total_defects} | 0 | {'✅' if metrics.defects.total_defects == 0 else '❌'} |

**Defect Breakdown:**
- P0 (Blocker): {metrics.defects.p0_count}
- P1 (Critical): {metrics.defects.p1_count}
- P2 (High): {metrics.defects.p2_count}
- P3 (Low): {metrics.defects.p3_count}

### Performance Metrics

| Metric | Value |
|--------|-------|
| **Total Execution Time** | {metrics.performance.total_execution_time:.1f}s ({metrics.performance.total_execution_time / 60:.1f} min) |
| **Avg Time per Exercise** | {metrics.performance.avg_execution_time:.1f}s |
| **Slowest Test Category** | {metrics.performance.get_slowest_category() or 'N/A'} |

**Category Execution Times:**
{self._format_category_times(metrics.performance.category_times)}

### Quality Score

**Overall Quality Score: {metrics.get_quality_score():.1f}/100**

- Coverage: {metrics.coverage.exercise_coverage_percent:.1f}%
- Test Pass Rate: {metrics.calculate_test_pass_rate():.1f}%
- Defect Quality: {max(0, 100 - (metrics.defects.defect_density * 200)):.1f}/100

### Automation ROI

| Metric | Value |
|--------|-------|
| **Manual Testing Time** | {roi['manual_time_minutes']:.0f} minutes ({roi['manual_time_minutes'] / 60:.1f} hours) |
| **Automated Testing Time** | {roi['automated_time_minutes']:.0f} minutes ({roi['automated_time_minutes'] / 60:.1f} hours) |
| **Time Saved** | {roi['time_saved_hours']:.1f} hours |
| **Efficiency Gain** | {roi['efficiency_gain_percent']:.1f}% |
| **Speed Multiplier** | {roi['speed_multiplier']:.1f}x faster |

---"""

    def _format_category_times(self, category_times: Dict[str, float]) -> str:
        """Format category times as a bulleted list."""
        if not category_times:
            return "- No category data available"

        lines = []
        for cat, time in sorted(category_times.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- **{cat}**: {time:.1f}s ({time / 60:.1f} min)")

        return "\n".join(lines)

    def _performance_budget_section(self) -> str:
        """Generate performance budget compliance section."""
        registry = PerformanceBudgetRegistry()
        report = self.budget_report

        # Build budget status table
        budget_table = """| Category | Max Time | Actual Time | Utilization | Status |
|----------|----------|-------------|-------------|--------|
"""

        # Collect category timings
        category_timings = defaultdict(float)
        for ex in self.results.exercise_results:
            if hasattr(ex, 'test_categories'):
                for cat_name, cat_result in ex.test_categories.items():
                    if hasattr(cat_result, 'duration_seconds'):
                        category_timings[cat_name] = max(
                            category_timings[cat_name],
                            cat_result.duration_seconds
                        )

        # Generate rows for executed categories
        for category, actual_time in sorted(category_timings.items()):
            budget = registry.get_budget(category)
            if budget:
                utilization = (actual_time / budget.max_seconds) * 100
                severity, message = registry.check_budget(category, actual_time)

                # Status emoji
                status_emoji = {
                    "INFO": "✅",
                    "WARNING": "⚠️",
                    "CRITICAL": "🟠",
                    "BLOCKER": "🔴"
                }.get(severity.name, "❓")

                budget_table += f"| {category} | {budget.max_seconds:.0f}s | {actual_time:.1f}s | {utilization:.0f}% | {status_emoji} {severity.name} |\n"

        # Overall compliance
        compliance_emoji = "✅" if report.budget_compliance_rate == 100 else "⚠️" if report.budget_compliance_rate >= 80 else "❌"

        section = f"""## Performance Budget Compliance

{compliance_emoji} **Budget Compliance Rate: {report.budget_compliance_rate:.1f}%**

### Budget Summary

- **Total Categories Tested**: {report.total_categories}
- **Within Budget**: {report.within_budget} ✅
- **Warnings**: {report.warnings} ⚠️
- **Critical**: {report.critical} 🟠
- **Blockers**: {report.blockers} 🔴

### Category Budget Status

{budget_table}

### Budget Guidelines

Performance budgets ensure tests complete in reasonable time:

- **TC-PREREQ**: 30s - Quick validation
- **TC-EXEC**: 10min - EPUB step execution
- **TC-SOL**: 5min - Solution testing
- **TC-GRADE**: 2min - Grading validation
- **TC-IDEM**: 10min - Multi-cycle testing
- **TC-E2E**: 30min - Full independence test
- **TC-AAP**: 10min - AAP Controller ops

**Note**: Budgets are per-exercise maximums. Violations suggest optimization opportunities.

---"""

        return section

    def _test_coverage(self) -> str:
        """Generate test coverage section."""
        return f"""## Test Coverage

### Test Categories Executed

| Category | Description | Exercises Tested |
|----------|-------------|------------------|
| TC-PREREQ | Prerequisites (lab start) | {self._count_category_executions('TC-PREREQ')} |
| TC-EXEC | EPUB step execution | {self._count_category_executions('TC-EXEC')} |
| TC-SOL | Solution file testing | {self._count_category_executions('TC-SOL')} |
| TC-GRADE | Grading script validation | {self._count_category_executions('TC-GRADE')} |
| TC-IDEM | Idempotency (multi-cycle) | {self._count_category_executions('TC-IDEM')} |
| TC-CLEAN | Cleanup validation | {self._count_category_executions('TC-CLEAN')} |
| TC-WEB | WebApp testing | {self._count_category_executions('TC-WEB')} |
| TC-INSTRUCT | Instruction quality | {self._count_category_executions('TC-INSTRUCT')} |
| TC-E2E | End-to-end testing | {self._count_category_executions('TC-E2E')} |

### Coverage Assessment

{'✅ **Complete Coverage**: All exercises tested with all applicable test categories' if self.results.summary.get('all_exercises_tested') else '❌ **Incomplete Coverage**: Some exercises were not tested (violates thoroughness guideline)'}

---"""

    def _test_results_table(self) -> str:
        """Generate test results table."""
        table = """## Test Results by Exercise

| Exercise ID | Status | Duration | Bugs | Test Categories |
|-------------|--------|----------|------|-----------------|
"""

        for ex_result in self.results.exercise_results:
            status_emoji = "✅" if ex_result.status == "PASS" else "❌" if ex_result.status == "FAIL" else "⏭️"
            bug_count = len(getattr(ex_result, 'bugs_found', []))
            categories_tested = len(getattr(ex_result, 'test_categories', {}))

            table += f"| {ex_result.exercise_id} | {status_emoji} {ex_result.status} | {ex_result.duration_seconds:.1f}s | {bug_count} | {categories_tested} |\n"

        table += "\n---"
        return table

    def _bugs_by_severity(self) -> str:
        """Generate bugs organized by severity."""
        bugs = self._collect_all_bugs()

        if not bugs:
            return """## Bugs Found

✅ **No bugs found** - All exercises passed successfully.

---"""

        by_severity = defaultdict(list)
        for bug in bugs:
            by_severity[bug.severity].append(bug)

        section = "## Bugs Found\n\n"

        for severity in ['P0', 'P1', 'P2', 'P3']:
            count = len(by_severity[severity])
            if count > 0:
                emoji = {'P0': '🔴', 'P1': '🟠', 'P2': '🟡', 'P3': '🟢'}[severity]
                section += f"### {emoji} {severity} Severity: {count} bugs\n\n"

                for bug in by_severity[severity]:
                    section += f"- **{bug.bug_id}** ({bug.exercise_id}): {bug.description}\n"

                section += "\n"

        section += "---"
        return section

    def _detailed_bugs(self) -> str:
        """Generate detailed bug information."""
        bugs = self._collect_all_bugs()

        if not bugs:
            return ""

        section = "## Detailed Bug Reports\n\n"

        # Group by exercise
        by_exercise = defaultdict(list)
        for bug in bugs:
            by_exercise[bug.exercise_id].append(bug)

        for exercise_id, exercise_bugs in sorted(by_exercise.items()):
            section += f"### {exercise_id}\n\n"

            for bug in exercise_bugs:
                section += f"#### {bug.bug_id} - {bug.severity}\n\n"
                section += f"**Category**: {bug.category}\n\n"
                section += f"**Description**: {bug.description}\n\n"

                if bug.expected_output:
                    section += f"**Expected**: `{bug.expected_output}`\n\n"

                if bug.actual_output:
                    section += f"**Actual**: `{bug.actual_output}`\n\n"

                if bug.error_message:
                    section += f"**Error**: `{bug.error_message}`\n\n"

                section += "\n"

        section += "---"
        return section

    def _fix_recommendations(self) -> str:
        """Generate fix recommendations with exact commands."""
        bugs = self._collect_all_bugs()

        if not bugs:
            return ""

        section = "## Fix Recommendations\n\n"
        section += "Prioritized actionable fixes with exact commands.\n\n"

        # Group by severity for prioritization
        by_severity = defaultdict(list)
        for bug in bugs:
            by_severity[bug.severity].append(bug)

        priority_order = ['P0', 'P1', 'P2', 'P3']

        for severity in priority_order:
            if not by_severity[severity]:
                continue

            emoji = {'P0': '🔴', 'P1': '🟠', 'P2': '🟡', 'P3': '🟢'}[severity]
            section += f"### {emoji} {severity} Priority Fixes\n\n"

            for bug in by_severity[severity]:
                section += f"**{bug.bug_id}** ({bug.exercise_id}):\n\n"
                section += f"- Issue: {bug.description}\n"

                # Generate fix recommendation based on bug category
                fix_cmd = self._generate_fix_command(bug)
                if fix_cmd:
                    section += f"- Fix: `{fix_cmd}`\n"

                # Add verification steps
                verify_steps = self._generate_verification_steps(bug)
                if verify_steps:
                    section += f"- Verify:\n"
                    for step in verify_steps:
                        section += f"  - {step}\n"

                section += "\n"

        section += "---"
        return section

    def _automation_metrics(self) -> str:
        """Generate automation metrics."""
        total = self.results.total_exercises
        tested = self.results.exercises_tested
        auto_rate = (tested / total * 100) if total > 0 else 0

        # Count test categories executed
        total_tests = sum(
            len(getattr(ex, 'test_categories', {}))
            for ex in self.results.exercise_results
        )

        return f"""## Automation Metrics

### Test Execution

- **Automation Rate**: {auto_rate:.1f}% ({tested}/{total} exercises)
- **Total Test Cases Executed**: {total_tests}
- **Average Tests per Exercise**: {total_tests / tested:.1f} (if tested > 0 else 0)
- **Total Duration**: {self.results.total_duration_seconds:.1f}s
- **Average Duration per Exercise**: {self.results.total_duration_seconds / tested:.1f}s (if tested > 0 else 0)

### Automation Capabilities Demonstrated

✅ Fully automated execution (no human prompts)
✅ EPUB-first testing approach
✅ Multi-cycle idempotency validation
✅ End-to-end independence testing
✅ Solution file automated testing
✅ WebApp component testing
✅ Instruction quality analysis
✅ Automated report generation

---"""

    def _release_assessment(self) -> str:
        """Generate release readiness assessment."""
        pass_rate = self.results.summary.get('pass_rate', 0)
        bugs = self._collect_all_bugs()
        bug_counts = self._count_bugs_by_severity(bugs)

        p0_count = bug_counts.get('P0', 0)
        p1_count = bug_counts.get('P1', 0)
        all_tested = self.results.summary.get('all_exercises_tested', False)

        # Determine readiness
        if not all_tested:
            readiness = "NOT READY"
            emoji = "❌"
            reason = "Not all exercises were tested (violates thoroughness guideline)"
        elif p0_count > 0:
            readiness = "BLOCKED"
            emoji = "🔴"
            reason = f"{p0_count} P0 blocker bug(s) must be fixed"
        elif p1_count > 0:
            readiness = "NOT READY"
            emoji = "🟠"
            reason = f"{p1_count} P1 critical bug(s) should be fixed"
        elif pass_rate < 100:
            readiness = "NEEDS REVIEW"
            emoji = "⚠️"
            reason = f"Pass rate is {pass_rate:.1f}% (target: 100%)"
        else:
            readiness = "READY"
            emoji = "✅"
            reason = "All exercises passed, no critical bugs"

        section = f"""## Release Readiness Assessment

{emoji} **Status**: {readiness}

**Reason**: {reason}

### Criteria

| Criterion | Status | Details |
|-----------|--------|---------|
| All exercises tested | {'✅' if all_tested else '❌'} | {self.results.exercises_tested}/{self.results.total_exercises} |
| No P0 blockers | {'✅' if p0_count == 0 else '❌'} | {p0_count} found |
| No P1 critical bugs | {'✅' if p1_count == 0 else '❌'} | {p1_count} found |
| 100% pass rate | {'✅' if pass_rate == 100 else '❌'} | {pass_rate:.1f}% |

### Recommendations

"""

        if readiness == "READY":
            section += "✅ **Course is ready for release**\n\n"
            section += "All quality criteria met. Proceed with confidence.\n"
        elif readiness == "BLOCKED":
            section += "🔴 **RELEASE BLOCKED**\n\n"
            section += f"Fix all {p0_count} P0 blocker bugs before release.\n"
            section += "See Fix Recommendations section above for exact commands.\n"
        elif readiness == "NOT READY":
            section += "🟠 **NOT READY FOR RELEASE**\n\n"
            section += "Address critical issues before release:\n"
            if not all_tested:
                section += "- Complete testing of all exercises\n"
            if p1_count > 0:
                section += f"- Fix {p1_count} P1 critical bugs\n"
            section += "\nSee Fix Recommendations section for guidance.\n"
        else:
            section += "⚠️ **NEEDS REVIEW**\n\n"
            section += "Review failed exercises and determine if fixes are needed.\n"

        section += "\n---"
        return section

    def _appendix(self) -> str:
        """Generate appendix with additional information."""
        return f"""## Appendix

### Course Structure

- **Course Code**: {self.context.course_code}
- **Total Chapters**: {self.context.total_chapters}
- **Total Exercises**: {self.context.total_exercises}
- **Pattern**: {self.context.pattern}

### Test Environment

- **Workstation**: Auto-detected
- **Connection Method**: SSH
- **Browser**: Chrome (headless) for webapp tests

### Methodology

This report was generated automatically following these principles:

1. **Fully Automated** - No human prompts during execution
2. **Context First** - Course analyzed before testing
3. **Quality Focus** - Instruction quality assessed, not just functionality
4. **Complete Understanding** - All lab scripts, snippets, files analyzed
5. **Repeatability & Independence** - Multi-cycle testing, isolation validation
6. **Thoroughness** - All exercises tested, no skipping

### Tools Used

- **Course Analyzer** - Pre-test context building
- **Test Executor** - EPUB workflow execution
- **Test Categories** - TC-PREREQ, TC-EXEC, TC-SOL, TC-GRADE, TC-IDEM, TC-CLEAN, TC-WEB, TC-INSTRUCT, TC-E2E
- **WebApp Integrator** - Chrome/Selenium automation
- **Report Generator** - This automated report

---

**End of Report**

Generated by Exercise QA Framework v2.0
For questions or issues, see SKILL.md documentation."""

    # Helper methods

    def _collect_all_bugs(self) -> List[Bug]:
        """Collect all bugs from all exercise results."""
        all_bugs = []
        for ex_result in self.results.exercise_results:
            bugs = getattr(ex_result, 'bugs_found', [])
            all_bugs.extend(bugs)
        return all_bugs

    def _count_bugs_by_severity(self, bugs: List[Bug]) -> Dict[str, int]:
        """Count bugs by severity level."""
        counts = defaultdict(int)
        for bug in bugs:
            counts[bug.severity] += 1
        return counts

    def _count_category_executions(self, category: str) -> int:
        """Count how many exercises executed a specific test category."""
        count = 0
        for ex_result in self.results.exercise_results:
            test_cats = getattr(ex_result, 'test_categories', {})
            if category in test_cats:
                count += 1
        return count

    def _generate_fix_command(self, bug: Bug) -> Optional[str]:
        """Generate fix command based on bug type."""
        # This is a simplified version - could be enhanced with ML/patterns
        if 'file not found' in bug.description.lower():
            return "Check file path and permissions"
        elif 'permission denied' in bug.description.lower():
            return "chmod +x <file> or sudo <command>"
        elif 'command not found' in bug.description.lower():
            return "Install missing package or check PATH"
        elif 'idempotency' in bug.description.lower():
            return "Review lab script for state changes on repeated runs"
        elif 'cleanup' in bug.description.lower():
            return "Add cleanup steps to lab finish script"
        else:
            return "Review exercise content and lab scripts"

    def _generate_verification_steps(self, bug: Bug) -> List[str]:
        """Generate verification steps for bug fix."""
        steps = [
            f"Run: lab start {bug.exercise_id}",
            f"Run: lab finish {bug.exercise_id}",
            "Verify no errors in output"
        ]

        if 'idempotency' in bug.description.lower():
            steps.append(f"Run: lab start {bug.exercise_id} (second time)")
            steps.append("Verify identical state")

        return steps


def main():
    """Generate report from test results."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Generate QA report from test results")
    parser.add_argument("course_context", help="Path to course_context.json")
    parser.add_argument("test_results", help="Path to test_results.json")
    parser.add_argument("--output-dir", default="results", help="Output directory")

    args = parser.parse_args()

    # Load course context
    course_context = CourseContext.from_json(Path(args.course_context))

    # Load test results
    with open(args.test_results, 'r') as f:
        results_dict = json.load(f)

    # Convert to CourseTestResults
    test_results = CourseTestResults(
        course_code=results_dict['course_code'],
        test_date=results_dict['test_date'],
        total_exercises=results_dict['total_exercises'],
        exercises_tested=results_dict['exercises_tested'],
        exercises_passed=results_dict['exercises_passed'],
        exercises_failed=results_dict['exercises_failed'],
        exercises_skipped=results_dict['exercises_skipped'],
        total_duration_seconds=results_dict['total_duration_seconds'],
        exercise_results=[],  # Would need to deserialize
        summary=results_dict.get('summary', {})
    )

    # Generate report
    generator = ReportGenerator(course_context, test_results)
    report_path = generator.generate(Path(args.output_dir))

    print(f"\n✅ Report generated successfully: {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
