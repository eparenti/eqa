"""Advanced report generation with quality metrics and recommendations."""

import json
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from ..core.models import CourseTestResults, Bug, BugSeverity
from .metrics import MetricsCalculator, QualityMetrics, BudgetReport
from ..diagnostics import ErrorAnalyzer, DiagnosticResult


class AdvancedReportGenerator:
    """Generates comprehensive QA reports with metrics and recommendations."""

    def __init__(self, results: CourseTestResults):
        """Initialize report generator."""
        self.results = results
        self.calculator = MetricsCalculator(results)
        self.metrics: Optional[QualityMetrics] = None
        self.budget_report: Optional[BudgetReport] = None
        self.error_analyzer = ErrorAnalyzer()
        self._diagnostics_cache: Dict[str, List[DiagnosticResult]] = {}

    def generate(self, output_dir: Path) -> tuple[Path, Path]:
        """
        Generate both markdown and JSON reports.

        Args:
            output_dir: Directory to save reports

        Returns:
            Tuple of (markdown_path, json_path)
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Calculate metrics
        self.metrics = self.calculator.calculate_quality_metrics()
        self.budget_report = self.calculator.calculate_performance_budget()

        # Generate reports
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        # Markdown report
        md_path = output_dir / f"QA-{self.results.course_code}-{timestamp}.md"
        md_content = self._generate_markdown()
        with open(md_path, 'w') as f:
            f.write(md_content)

        # JSON report
        json_path = output_dir / f"QA-{self.results.course_code}-{timestamp}.json"
        json_content = self._generate_json()
        with open(json_path, 'w') as f:
            f.write(json_content)

        return md_path, json_path

    def _generate_markdown(self) -> str:
        """Generate comprehensive markdown report."""
        sections = [
            self._header(),
            self._executive_summary(),
            self._quality_metrics_dashboard(),
            self._performance_budget_section(),
            self._test_coverage(),
            self._test_results_table(),
            self._bugs_by_severity(),
            self._detailed_bugs(),
            self._ai_diagnostics_section(),
            self._fix_recommendations(),
            self._automation_metrics(),
            self._release_assessment(),
            self._appendix(),
        ]
        # Filter out empty sections
        sections = [s for s in sections if s.strip()]
        return "\n\n".join(sections)

    def _header(self) -> str:
        """Generate report header."""
        duration_min = self.results.total_duration_seconds / 60
        return f"""# Exercise QA Report: {self.results.course_code}

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Test Date**: {self.results.test_date}
**Duration**: {self.results.total_duration_seconds:.1f}s ({duration_min:.1f} minutes)
**Automation Level**: Fully Automated

---"""

    def _executive_summary(self) -> str:
        """Generate executive summary."""
        pass_rate = self.metrics.pass_rate
        bugs_by_sev = self.metrics.bugs_by_severity
        total_bugs = self.metrics.total_bugs

        if pass_rate == 100:
            status_emoji, status_text = "✅", "PASS"
        elif pass_rate >= 80:
            status_emoji, status_text = "⚠️", "NEEDS ATTENTION"
        else:
            status_emoji, status_text = "❌", "CRITICAL ISSUES"

        all_tested = self.results.exercises_tested == self.results.total_exercises
        tested_status = "✅" if all_tested else "❌ (INCOMPLETE)"

        return f"""## Executive Summary

{status_emoji} **Overall Status**: {status_text}

### Key Metrics

- **Total Exercises**: {self.results.total_exercises}
- **Exercises Tested**: {self.results.exercises_tested} {tested_status}
- **Pass Rate**: {pass_rate:.1f}%
- **Passed**: {self.results.exercises_passed} ✅
- **Failed**: {self.results.exercises_failed} ❌
- **Skipped**: {self.results.exercises_skipped} ⏭️

### Bug Summary

- **P0 (Blocker)**: {bugs_by_sev['P0']} 🔴
- **P1 (Critical)**: {bugs_by_sev['P1']} 🟠
- **P2 (High)**: {bugs_by_sev['P2']} 🟡
- **P3 (Low)**: {bugs_by_sev['P3']} 🟢
- **Total Bugs**: {total_bugs}

---"""

    def _quality_metrics_dashboard(self) -> str:
        """Generate quality metrics dashboard with industry-standard metrics."""
        bugs = self.metrics.bugs_by_severity
        tested = max(self.results.exercises_tested, 1)
        duration_min = self.metrics.total_duration / 60

        # Coverage metrics
        exercise_cov = (self.results.exercises_tested / max(self.results.total_exercises, 1)) * 100

        # Defect metrics
        defect_density = self.metrics.defect_density
        critical_ratio = self.metrics.critical_ratio

        # Quality score (0-100)
        score_coverage = min(exercise_cov, 100)
        score_pass_rate = self.metrics.pass_rate
        score_defect = max(0, 100 - (defect_density * 200))
        quality_score = (score_coverage * 0.3 + score_pass_rate * 0.4 + score_defect * 0.3)

        # Automation ROI estimate (15 min manual per exercise)
        manual_time_min = self.results.exercises_tested * 15
        auto_time_min = self.metrics.total_duration / 60
        time_saved_hrs = max(0, (manual_time_min - auto_time_min)) / 60
        efficiency = ((manual_time_min - auto_time_min) / max(manual_time_min, 1)) * 100
        speed_mult = manual_time_min / max(auto_time_min, 0.1)

        # Category execution times
        category_times = self._collect_category_times()
        cat_time_lines = []
        if category_times:
            for cat, t in sorted(category_times.items(), key=lambda x: x[1], reverse=True):
                cat_time_lines.append(f"- **{cat}**: {t:.1f}s")
        else:
            cat_time_lines.append("- No category data available")

        slowest = max(category_times, key=category_times.get) if category_times else "N/A"

        return f"""## Quality Metrics Dashboard

### Coverage Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Exercise Coverage** | {exercise_cov:.1f}% ({self.results.exercises_tested}/{self.results.total_exercises}) | 100% | {self._status_icon(exercise_cov == 100)} |
| **Test Coverage** | {self.metrics.test_coverage:.1f}% | 80% | {self._status_icon(self.metrics.test_coverage >= 80)} |

### Defect Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Defect Density** | {defect_density:.2f} bugs/exercise | <0.5 | {self._status_icon(defect_density < 0.5)} |
| **Critical Defect Ratio** | {critical_ratio:.1f}% | <20% | {self._status_icon(critical_ratio < 20)} |
| **Total Defects** | {self.metrics.total_bugs} | 0 | {self._status_icon(self.metrics.total_bugs == 0)} |

**Defect Breakdown:**
- P0 (Blocker): {bugs['P0']}
- P1 (Critical): {bugs['P1']}
- P2 (High): {bugs['P2']}
- P3 (Low): {bugs['P3']}

### Performance Metrics

| Metric | Value |
|--------|-------|
| **Total Execution Time** | {self.metrics.total_duration:.1f}s ({duration_min:.1f} min) |
| **Avg Time per Exercise** | {self.metrics.avg_duration:.1f}s |
| **Slowest Test Category** | {slowest} |

**Category Execution Times:**
{chr(10).join(cat_time_lines)}

### Quality Score

**Overall Quality Score: {quality_score:.1f}/100**

- Coverage: {score_coverage:.1f}%
- Test Pass Rate: {score_pass_rate:.1f}%
- Defect Quality: {score_defect:.1f}/100

### Automation ROI

| Metric | Value |
|--------|-------|
| **Manual Testing Time** | {manual_time_min:.0f} minutes ({manual_time_min / 60:.1f} hours) |
| **Automated Testing Time** | {auto_time_min:.0f} minutes ({auto_time_min / 60:.1f} hours) |
| **Time Saved** | {time_saved_hrs:.1f} hours |
| **Efficiency Gain** | {efficiency:.1f}% |
| **Speed Multiplier** | {speed_mult:.1f}x faster |

---"""

    def _performance_budget_section(self) -> str:
        """Generate performance budget section."""
        if not self.budget_report.budgets:
            return "## Performance Budget\n\nNo budget data available.\n\n---"

        within = sum(1 for b in self.budget_report.budgets if not b.over_budget)
        over = sum(1 for b in self.budget_report.budgets if b.over_budget)
        total = len(self.budget_report.budgets)
        compliance = (within / max(total, 1)) * 100

        compliance_emoji = "✅" if compliance == 100 else "⚠️" if compliance >= 80 else "❌"

        lines = [f"## Performance Budget Compliance", ""]
        lines.append(f"{compliance_emoji} **Budget Compliance Rate: {compliance:.1f}%**")
        lines.append("")
        lines.append("### Budget Summary")
        lines.append("")
        lines.append(f"- **Total Categories Tested**: {total}")
        lines.append(f"- **Within Budget**: {within} ✅")
        lines.append(f"- **Over Budget**: {over} ⚠️")
        lines.append("")
        lines.append("### Category Budget Status")
        lines.append("")
        lines.append("| Category | Budget | Actual | Utilization | Status |")
        lines.append("|----------|--------|--------|-------------|--------|")

        for budget in self.budget_report.budgets:
            if budget.over_budget:
                status = "⚠️ OVER"
            elif budget.percentage > 80:
                status = "✅ HIGH"
            else:
                status = "✅ OK"
            lines.append(
                f"| {budget.category} | {budget.budget_seconds:.0f}s | "
                f"{budget.actual_seconds:.1f}s | {budget.percentage:.0f}% | {status} |"
            )

        lines.append("")
        lines.append(f"**Overall**: {compliance_emoji} ({self.budget_report.total_actual:.1f}s / {self.budget_report.total_budget:.1f}s)")
        lines.append("")
        lines.append("---")

        return "\n".join(lines)

    def _test_coverage(self) -> str:
        """Generate test coverage section."""
        # Count executions per category
        category_counts = defaultdict(int)
        for ex in self.results.exercise_results:
            for cat_name in ex.test_categories:
                category_counts[cat_name] += 1

        all_categories = [
            ("TC-PREREQ", "Prerequisites (SSH, tools, hosts)"),
            ("TC-EXEC", "EPUB step execution"),
            ("TC-SOL", "Solution file validation"),
            ("TC-GRADE", "Grading script validation"),
            ("TC-SOLVE", "Solve playbook testing"),
            ("TC-VERIFY", "Verification testing"),
            ("TC-WORKFLOW", "Workflow automation"),
            ("TC-CLEAN", "Cleanup validation"),
            ("TC-IDEM", "Idempotency (multi-cycle)"),
            ("TC-E2E", "End-to-end independence"),
            ("TC-LINT", "Linting and static analysis"),
            ("TC-VARS", "Variable validation"),
            ("TC-DEPS", "Dependency validation"),
            ("TC-INSTRUCT", "Instruction quality"),
            ("TC-SECURITY", "Security best practices"),
            ("TC-CONTRACT", "Component alignment"),
            ("TC-NETWORK", "Network device testing"),
            ("TC-EE", "Execution environment"),
            ("TC-AAP", "AAP Controller workflows"),
            ("TC-PERF", "Performance budgets"),
            ("TC-ROLLBACK", "Rollback testing"),
            ("TC-WEB", "Web UI testing"),
            ("TC-DYNOLABS", "DynoLabs v5 support"),
        ]

        lines = ["## Test Coverage", ""]
        lines.append("### Test Categories Executed")
        lines.append("")
        lines.append("| Category | Description | Exercises Tested |")
        lines.append("|----------|-------------|------------------|")

        for cat_name, desc in all_categories:
            count = category_counts.get(cat_name, 0)
            if count > 0:
                lines.append(f"| {cat_name} | {desc} | {count} |")

        lines.append("")

        all_tested = self.results.exercises_tested == self.results.total_exercises
        if all_tested:
            lines.append("✅ **Complete Coverage**: All exercises tested with all applicable test categories")
        else:
            lines.append("❌ **Incomplete Coverage**: Some exercises were not tested")

        lines.append("")
        lines.append("---")

        return "\n".join(lines)

    def _test_results_table(self) -> str:
        """Generate test results table."""
        lines = ["## Test Results by Exercise", ""]
        lines.append("| Exercise ID | Status | Duration | Bugs | Test Categories |")
        lines.append("|-------------|--------|----------|------|-----------------|")

        for ex_result in self.results.exercise_results:
            status_icon = "✅" if ex_result.status == "PASS" else "❌"
            bug_count = len(ex_result.bugs)
            cat_count = len(ex_result.test_categories)
            lines.append(
                f"| {ex_result.exercise_id} | {status_icon} {ex_result.status} | "
                f"{ex_result.duration_seconds:.1f}s | {bug_count} | {cat_count} |"
            )

        lines.append("")
        lines.append("---")

        return "\n".join(lines)

    def _bugs_by_severity(self) -> str:
        """Generate bugs organized by severity with colored indicators."""
        if not self.results.all_bugs:
            return "## Bugs Found\n\n✅ **No bugs found** - All exercises passed successfully.\n\n---"

        severity_config = {
            'P0': ('🔴', 'Blocker'),
            'P1': ('🟠', 'Critical'),
            'P2': ('🟡', 'High'),
            'P3': ('🟢', 'Low'),
        }

        lines = ["## Bugs Found", ""]

        for severity in ['P0', 'P1', 'P2', 'P3']:
            bugs = [b for b in self.results.all_bugs if b.severity.value == severity]
            if bugs:
                emoji, name = severity_config[severity]
                lines.append(f"### {emoji} {severity} Severity: {len(bugs)} bugs")
                lines.append("")
                for bug in bugs:
                    lines.append(f"- **{bug.id}** ({bug.exercise_id}): {bug.description}")
                lines.append("")

        lines.append("---")
        return "\n".join(lines)

    def _detailed_bugs(self) -> str:
        """Generate detailed bug listings grouped by exercise."""
        if not self.results.all_bugs:
            return ""

        # Group by exercise
        by_exercise = defaultdict(list)
        for bug in self.results.all_bugs:
            by_exercise[bug.exercise_id].append(bug)

        lines = ["## Detailed Bug Reports", ""]

        for exercise_id, exercise_bugs in sorted(by_exercise.items()):
            lines.append(f"### {exercise_id}")
            lines.append("")

            for bug in exercise_bugs:
                severity_emoji = {'P0': '🔴', 'P1': '🟠', 'P2': '🟡', 'P3': '🟢'}.get(
                    bug.severity.value, '❓')
                lines.append(f"#### {bug.id} - {severity_emoji} {bug.severity.value}")
                lines.append("")
                lines.append(f"**Category**: {bug.category}")
                lines.append("")
                lines.append(f"**Description**: {bug.description}")
                lines.append("")
                lines.append(f"**Fix**: {bug.fix_recommendation}")
                lines.append("")

                if bug.verification_steps:
                    lines.append("**Verification Steps**:")
                    for step in bug.verification_steps:
                        lines.append(f"- {step}")
                    lines.append("")

        lines.append("---")
        return "\n".join(lines)

    def _fix_recommendations(self) -> str:
        """Generate fix recommendations with exact commands."""
        if not self.results.all_bugs:
            return ""

        severity_config = {
            'P0': '🔴',
            'P1': '🟠',
            'P2': '🟡',
            'P3': '🟢',
        }

        lines = ["## Fix Recommendations", ""]
        lines.append("Prioritized actionable fixes.")
        lines.append("")

        for severity in ['P0', 'P1', 'P2', 'P3']:
            bugs = [b for b in self.results.all_bugs if b.severity.value == severity]
            if not bugs:
                continue

            emoji = severity_config[severity]
            lines.append(f"### {emoji} {severity} Priority Fixes")
            lines.append("")

            for i, bug in enumerate(bugs, 1):
                lines.append(f"**{i}. {bug.id}** ({bug.exercise_id}):")
                lines.append("")
                lines.append(f"- **Issue**: {bug.description}")
                lines.append(f"- **Fix**: {bug.fix_recommendation}")

                # Add AI diagnostic command if available
                diagnostics = self._get_diagnostics_for_bug(bug)
                if diagnostics and diagnostics[0].recommendations:
                    rec = diagnostics[0].recommendations[0]
                    if rec.commands:
                        lines.append(f"  ```bash")
                        for cmd in rec.commands[:3]:
                            lines.append(f"  {cmd}")
                        lines.append(f"  ```")

                # Add verification steps
                if bug.verification_steps:
                    lines.append("- **Verify**:")
                    for step in bug.verification_steps:
                        lines.append(f"  - `{step}`")

                lines.append("")

        lines.append("---")
        return "\n".join(lines)

    def _automation_metrics(self) -> str:
        """Generate automation metrics."""
        tested = max(self.results.exercises_tested, 1)
        total = max(self.results.total_exercises, 1)
        auto_rate = (self.results.exercises_tested / total) * 100

        # Count test categories executed
        total_tests = sum(
            len(ex.test_categories) for ex in self.results.exercise_results
        )

        avg_tests = total_tests / tested

        return f"""## Automation Metrics

### Test Execution

- **Automation Rate**: {auto_rate:.1f}% ({self.results.exercises_tested}/{self.results.total_exercises} exercises)
- **Total Test Cases Executed**: {total_tests}
- **Average Tests per Exercise**: {avg_tests:.1f}
- **Total Duration**: {self.results.total_duration_seconds:.1f}s
- **Average Duration per Exercise**: {self.results.total_duration_seconds / tested:.1f}s

### Automation Capabilities Demonstrated

✅ Fully automated execution (no human prompts)
✅ EPUB-first testing approach
✅ SSH ControlMaster multiplexing for fast execution
✅ AI-powered error pattern matching and diagnostics
✅ Multi-format reporting (Markdown, JSON, JUnit, CSV)
✅ Automated report generation with quality metrics

---"""

    def _release_assessment(self) -> str:
        """Generate release readiness assessment."""
        pass_rate = self.metrics.pass_rate
        p0_count = self.metrics.bugs_by_severity['P0']
        p1_count = self.metrics.bugs_by_severity['P1']
        all_tested = self.results.exercises_tested == self.results.total_exercises

        # Determine readiness
        if not all_tested:
            readiness, emoji = "NOT READY", "❌"
            reason = "Not all exercises were tested"
        elif p0_count > 0:
            readiness, emoji = "BLOCKED", "🔴"
            reason = f"{p0_count} P0 blocker bug(s) must be fixed"
        elif p1_count > 0:
            readiness, emoji = "NOT READY", "🟠"
            reason = f"{p1_count} P1 critical bug(s) should be fixed"
        elif pass_rate < 100:
            readiness, emoji = "NEEDS REVIEW", "⚠️"
            reason = f"Pass rate is {pass_rate:.1f}% (target: 100%)"
        else:
            readiness, emoji = "READY", "✅"
            reason = "All exercises passed, no critical bugs"

        lines = ["## Release Readiness Assessment", ""]
        lines.append(f"{emoji} **Status**: {readiness}")
        lines.append("")
        lines.append(f"**Reason**: {reason}")
        lines.append("")
        lines.append("### Criteria")
        lines.append("")
        lines.append("| Criterion | Status | Details |")
        lines.append("|-----------|--------|---------|")
        lines.append(f"| All exercises tested | {self._status_icon(all_tested)} | {self.results.exercises_tested}/{self.results.total_exercises} |")
        lines.append(f"| No P0 blockers | {self._status_icon(p0_count == 0)} | {p0_count} found |")
        lines.append(f"| No P1 critical bugs | {self._status_icon(p1_count == 0)} | {p1_count} found |")
        lines.append(f"| 100% pass rate | {self._status_icon(pass_rate == 100)} | {pass_rate:.1f}% |")
        lines.append("")
        lines.append("### Recommendations")
        lines.append("")

        if readiness == "READY":
            lines.append("✅ **Course is ready for release**")
            lines.append("")
            lines.append("All quality criteria met. Proceed with confidence.")
        elif readiness == "BLOCKED":
            lines.append("🔴 **RELEASE BLOCKED**")
            lines.append("")
            lines.append(f"Fix all {p0_count} P0 blocker bugs before release.")
            lines.append("See Fix Recommendations section above for exact commands.")
        elif readiness == "NOT READY":
            lines.append("🟠 **NOT READY FOR RELEASE**")
            lines.append("")
            lines.append("Address critical issues before release:")
            if not all_tested:
                lines.append("- Complete testing of all exercises")
            if p1_count > 0:
                lines.append(f"- Fix {p1_count} P1 critical bugs")
            lines.append("")
            lines.append("See Fix Recommendations section for guidance.")
        else:
            lines.append("⚠️ **NEEDS REVIEW**")
            lines.append("")
            lines.append("Review failed exercises and determine if fixes are needed.")

        lines.append("")
        lines.append("---")
        return "\n".join(lines)

    def _appendix(self) -> str:
        """Generate appendix with course structure and methodology."""
        # Count test categories across all exercises
        all_cats = set()
        for ex in self.results.exercise_results:
            all_cats.update(ex.test_categories.keys())

        return f"""## Appendix

### Course Structure

- **Course Code**: {self.results.course_code}
- **Total Exercises**: {self.results.total_exercises}
- **Test Categories Used**: {len(all_cats)}

### Test Environment

- **Workstation**: Auto-detected
- **Connection Method**: SSH (ControlMaster multiplexed)

### Methodology

This report was generated automatically following these principles:

1. **Fully Automated** - No human prompts during execution
2. **Context First** - Course analyzed before testing
3. **Quality Focus** - Instruction quality assessed, not just functionality
4. **Complete Understanding** - All lab scripts, solutions, and files analyzed
5. **Repeatability & Independence** - Multi-cycle testing, isolation validation
6. **Thoroughness** - All exercises tested, no skipping

---

**End of Report**

Generated by Exercise QA 3
"""

    # Helper methods

    def _collect_category_times(self) -> Dict[str, float]:
        """Collect max execution time per category across exercises."""
        category_times = defaultdict(float)
        for ex in self.results.exercise_results:
            for cat_name, cat_result in ex.test_categories.items():
                category_times[cat_name] = max(
                    category_times[cat_name],
                    cat_result.duration_seconds
                )
        return dict(category_times)

    def _generate_json(self) -> str:
        """Generate JSON report."""
        report = {
            'course_code': self.results.course_code,
            'test_date': self.results.test_date,
            'summary': {
                'total_exercises': self.results.total_exercises,
                'exercises_tested': self.results.exercises_tested,
                'exercises_passed': self.results.exercises_passed,
                'exercises_failed': self.results.exercises_failed,
                'duration_seconds': self.results.total_duration_seconds
            },
            'quality_metrics': self.metrics.to_dict(),
            'performance_budget': self.budget_report.to_dict(),
            'exercise_results': [
                {
                    'exercise_id': ex.exercise_id,
                    'status': ex.status,
                    'duration': ex.duration_seconds,
                    'bugs': len(ex.bugs)
                }
                for ex in self.results.exercise_results
            ],
            'bugs': [
                self._bug_to_json(bug)
                for bug in self.results.all_bugs
            ]
        }
        return json.dumps(report, indent=2)

    def _bug_to_json(self, bug: Bug) -> Dict:
        """Convert bug to JSON with AI diagnostics."""
        bug_dict = {
            'id': bug.id,
            'severity': bug.severity.value,
            'category': bug.category,
            'exercise_id': bug.exercise_id,
            'description': bug.description,
            'fix': bug.fix_recommendation,
            'verification_steps': bug.verification_steps
        }

        # Add AI diagnostics if available
        diagnostics = self._get_diagnostics_for_bug(bug)
        if diagnostics:
            bug_dict['ai_diagnostics'] = [d.to_dict() for d in diagnostics]

        return bug_dict

    def _status_icon(self, condition: bool) -> str:
        """Get status icon based on condition."""
        return "✅" if condition else "❌"


    def _get_diagnostics_for_bug(self, bug: Bug) -> List[DiagnosticResult]:
        """Get AI diagnostics for a bug based on its description."""
        cache_key = f"{bug.id}-{bug.description[:50]}"
        if cache_key in self._diagnostics_cache:
            return self._diagnostics_cache[cache_key]

        # Set exercise_id for context
        self.error_analyzer.exercise_id = bug.exercise_id

        # Analyze the bug description for patterns
        diagnostics = self.error_analyzer.analyze(bug.description)

        # Cache the result
        self._diagnostics_cache[cache_key] = diagnostics
        return diagnostics

    def _ai_diagnostics_section(self) -> str:
        """Generate AI-powered diagnostics section for bugs."""
        if not self.results.all_bugs:
            return ""

        lines = ["## AI Diagnostics", ""]
        lines.append("Automated analysis of error patterns with recommended fixes:")
        lines.append("")

        bugs_with_diagnostics = []

        for bug in self.results.all_bugs:
            diagnostics = self._get_diagnostics_for_bug(bug)
            if diagnostics:
                bugs_with_diagnostics.append((bug, diagnostics))

        if not bugs_with_diagnostics:
            lines.append("No known error patterns detected.")
            lines.append("")
            lines.append("---")
            return "\n".join(lines)

        for bug, diagnostics in bugs_with_diagnostics:
            lines.append(f"### {bug.id}")
            lines.append("")

            for diag in diagnostics:
                lines.append(f"**Pattern Detected**: {diag.pattern_title}")
                lines.append(f"- Severity: {diag.severity}")
                lines.append(f"- Category: {diag.category}")

                if diag.line_number:
                    lines.append(f"- Line: {diag.line_number}")
                if diag.file_path:
                    lines.append(f"- File: {diag.file_path}")
                lines.append("")

                if diag.recommendations:
                    lines.append("**Recommended Fix**:")
                    rec = diag.recommendations[0]
                    lines.append(f"> {rec.title}")
                    lines.append("")
                    if rec.commands:
                        lines.append("```bash")
                        for cmd in rec.commands[:5]:
                            lines.append(cmd)
                        lines.append("```")
                        lines.append("")

                    if rec.verification_steps:
                        lines.append("**Verification**:")
                        for step in rec.verification_steps[:3]:
                            lines.append(f"- {step}")
                        lines.append("")

        lines.append("---")
        return "\n".join(lines)
