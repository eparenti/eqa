"""Report generation for exercise QA results.

Generates Markdown, JSON, and JUnit XML reports from simulation results.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import SimulationResult, ExecutedStep, StepResult, CourseResults, Bug
from .metrics import calculate_metrics, format_metrics_report
from .diagnostics import ErrorAnalyzer, generate_diagnostics_report


# ---------------------------------------------------------------------------
# Markdown report (single exercise)
# ---------------------------------------------------------------------------

def generate_report(result: SimulationResult) -> str:
    """Generate a Markdown report from a simulation result with AI diagnostics."""
    # Run AI diagnostics on this result
    analyzer = ErrorAnalyzer()
    diagnostic_issues = analyzer.analyze_result(result)

    sections = [
        _header(result),
        _executive_summary(result),
        _diagnostics_summary(diagnostic_issues),
        _grading_validation_section(result),
        _step_breakdown(result),
        _bugs_section(result),
        _detailed_diagnostics(diagnostic_issues),
        _recommendations(result),
    ]
    return "\n\n".join(filter(None, sections))


def _header(result: SimulationResult) -> str:
    status_icon = "✅" if result.success else "❌"
    status = "PASSED" if result.success else "FAILED"
    cycle_info = f" (Cycle {result.cycle})" if result.cycle > 1 else ""
    return f"""# Student Simulation Report: {result.exercise_id}{cycle_info}

{status_icon} **Status**: {status}

**Type**: {result.exercise_type.value}
**Phase**: {result.phase}
**Duration**: {result.total_duration_seconds:.1f}s
**Cycle**: {result.cycle}"""


def _executive_summary(result: SimulationResult) -> str:
    total = len(result.steps_executed)
    passed, failed = result.steps_passed, result.steps_failed
    skipped = total - passed - failed

    if result.success:
        verdict = "✅ The student simulation completed successfully."
    else:
        verdict = f"❌ The simulation failed at phase: **{result.phase}**"
        if result.error_message:
            verdict += f"\n\n**Error Message**:\n```\n{result.error_message}\n```"

    return f"""## Executive Summary

{verdict}

| Metric | Count |
|--------|-------|
| Steps Executed | {total} |
| Passed ✓ | {passed} |
| Failed ✗ | {failed} |
| Skipped - | {skipped} |"""


def _diagnostics_summary(issues: list) -> Optional[str]:
    """Generate a quick summary of diagnostic issues found."""
    if not issues:
        return None

    from .diagnostics import BugSeverity

    lines = [
        "## 🔍 Issues Found",
        "",
        f"**Total Issues**: {len(issues)}",
        "",
        "| Severity | Issue | Category |",
        "|----------|-------|----------|",
    ]

    for issue in issues:
        severity_icon = {
            BugSeverity.P0_BLOCKER: "🔴",
            BugSeverity.P1_CRITICAL: "🟠",
            BugSeverity.P2_HIGH: "🟡",
            BugSeverity.P3_LOW: "🟢",
        }.get(issue.severity, "⚪")

        lines.append(f"| {severity_icon} {issue.severity.value} | {issue.title} | {issue.category.value.replace('_', ' ').title()} |")

    return "\n".join(lines)


def _detailed_diagnostics(issues: list) -> Optional[str]:
    """Generate detailed diagnostics section."""
    if not issues:
        return None

    lines = [
        "## 🔧 Detailed Diagnostics & Fix Suggestions",
        "",
        "AI-powered analysis of issues with root cause and actionable fixes:",
        "",
    ]

    for issue in issues:
        lines.append(issue.to_markdown())

    return "\n".join(lines)


def _grading_validation_section(result: SimulationResult) -> Optional[str]:
    """Generate grading validation section for Labs."""
    from .models import ExerciseType

    if result.exercise_type != ExerciseType.LAB:
        return None

    if result.grade_without_solution_passed is None and result.grade_with_solution_passed is None:
        return None

    lines = ["## Grading Validation", ""]

    # Test 1: Grading without solution
    if result.grade_without_solution_passed is not None:
        expected = "FAIL"
        actual = "PASS" if result.grade_without_solution_passed else "FAIL"
        status = "✓" if not result.grade_without_solution_passed else "✗"
        lines.append(f"**Without Solution**: Expected: {expected}, Actual: {actual} {status}")

    # Test 2: Grading with solution
    if result.grade_with_solution_passed is not None:
        expected = "PASS"
        actual = "PASS" if result.grade_with_solution_passed else "FAIL"
        status = "✓" if result.grade_with_solution_passed else "✗"
        lines.append(f"**With Solution**: Expected: {expected}, Actual: {actual} {status}")

    # Overall validation status
    validation_passed = (
        (result.grade_without_solution_passed is False or result.grade_without_solution_passed is None) and
        (result.grade_with_solution_passed is True or result.grade_with_solution_passed is None)
    )

    lines.append("")
    if validation_passed:
        lines.append("**Overall**: Grading validation PASSED ✓")
    else:
        lines.append("**Overall**: Grading validation FAILED ✗")

    return "\n".join(lines)


def _step_breakdown(result: SimulationResult) -> str:
    if not result.steps_executed:
        return "## Step Breakdown\n\nNo steps were executed."

    lines = [
        "## Step Breakdown",
        "",
        "| Step | Description | Command | Result | Duration | Error |",
        "|------|-------------|---------|--------|----------|-------|",
    ]

    for step in result.steps_executed:
        result_str = step.result.value.upper()
        desc = _truncate(step.text, 40)
        cmd = _truncate(step.command or "-", 30)
        error = _truncate(step.error or "-", 40)
        duration = f"{step.duration_seconds:.1f}s" if step.duration_seconds > 0 else "-"
        lines.append(f"| {step.number} | {desc} | `{cmd}` | {result_str} | {duration} | {error} |")

    return "\n".join(lines)


def _bugs_section(result: SimulationResult) -> Optional[str]:
    if not result.bugs:
        return None

    from .models import BugSeverity

    severity_icons = {
        BugSeverity.P0_BLOCKER: "🔴",
        BugSeverity.P1_CRITICAL: "🟠",
        BugSeverity.P2_HIGH: "🟡",
        BugSeverity.P3_LOW: "🟢",
    }

    lines = ["## 🐛 Bugs Found (Legacy)", ""]
    for bug in result.bugs:
        icon = severity_icons.get(bug.severity, "⚪")
        lines.append(f"### {icon} [{bug.severity.value}] {bug.description}")
        lines.append(f"\n**ID**: {bug.id}")
        lines.append(f"\n**Fix**: {bug.fix_recommendation}")
        if bug.verification_steps:
            lines.append("\n**Verification**:")
            for step in bug.verification_steps:
                lines.append(f"- {step}")
        lines.append("")

    return "\n".join(lines)


def _recommendations(result: SimulationResult) -> Optional[str]:
    failed_steps = [s for s in result.steps_executed if s.result == StepResult.FAIL]
    if not failed_steps:
        return None

    lines = ["## Recommendations", ""]
    for step in failed_steps:
        lines.append(f"### Step {step.number}: {_truncate(step.text, 60)}")
        lines.append(f"\n**Command**: `{step.command}`")
        if step.error:
            lines.append(f"\n**Error**: {step.error}")
        lines.append(f"\n**Suggested Action**: {_suggest_fix(step)}\n")

    return "\n".join(lines)


def _suggest_fix(step: ExecutedStep) -> str:
    error = (step.error or "").lower()
    fixes = [
        ("command not found", "Check that the required package is installed."),
        ("permission denied", "Verify file permissions or use elevated privileges."),
        ("no such file or directory", "Check that prerequisite files exist."),
        ("connection refused", "Verify the target service is running."),
        ("timeout", "Check for network issues or infinite loops."),
        ("syntax error", "Review the command syntax for typos."),
    ]
    for pattern, suggestion in fixes:
        if pattern in error:
            return suggestion
    return "Review the error message and verify the instruction step is correct."


# ---------------------------------------------------------------------------
# Course-level Markdown report
# ---------------------------------------------------------------------------

def generate_course_report(results: CourseResults) -> str:
    """Generate a Markdown report for an entire course run with quality metrics and AI diagnostics."""
    # Calculate quality metrics
    metrics = calculate_metrics(results.results, total_exercises=results.total_exercises)

    # Generate AI diagnostics
    diagnostics = generate_diagnostics_report(results.results)

    lines = [
        f"# Course QA Report: {results.course_code}",
        "",
        f"**Date**: {results.test_date}",
        f"**Exercises Tested**: {results.exercises_tested}/{results.total_exercises}",
        f"**Passed**: {results.exercises_passed}",
        f"**Failed**: {results.exercises_failed}",
        f"**Duration**: {results.total_duration_seconds:.1f}s",
        f"**Quality Score**: {metrics.quality_score:.1f}/100 (Grade: {metrics.quality_grade})",
        "",
    ]

    # Add executive summary with clear pass/fail indication
    if results.exercises_failed == 0:
        lines.extend([
            "## ✅ Executive Summary",
            "",
            f"All {results.exercises_tested} exercises passed successfully!",
            "",
        ])
    else:
        lines.extend([
            "## ⚠️ Executive Summary",
            "",
            f"**{results.exercises_failed} of {results.exercises_tested} exercises failed** - see diagnostics below for details.",
            "",
        ])

    lines.extend([
        "---",
        "",
        diagnostics,
        "",
        "---",
        "",
        format_metrics_report(metrics),
        "",
        "---",
        "",
        "## Results Summary",
        "",
        "| Exercise | Type | Status | Duration | Phase | Issues |",
        "|----------|------|--------|----------|-------|--------|",
    ])

    # Count issues per exercise
    analyzer = ErrorAnalyzer()
    for r in results.results:
        status_icon = "✅ PASS" if r.success else "❌ FAIL"
        issues = analyzer.analyze_result(r)
        issue_count = f"{len(issues)} issue(s)" if issues else "-"
        lines.append(
            f"| {r.exercise_id} | {r.exercise_type.value} | {status_icon} "
            f"| {r.total_duration_seconds:.1f}s | {r.phase} | {issue_count} |"
        )

    if results.all_bugs:
        lines.extend(["", "## All Bugs (Legacy)", ""])
        for bug in results.all_bugs:
            lines.append(f"- **[{bug.severity.value}]** {bug.exercise_id}: {bug.description}")

    # Individual exercise details
    failed = [r for r in results.results if not r.success]
    if failed:
        lines.extend(["", "## Failed Exercise Details", ""])
        for r in failed:
            lines.append(f"### {r.exercise_id}")
            lines.append(f"\n**Phase**: {r.phase}")
            if r.error_message:
                lines.append(f"\n**Error**: {r.error_message}")

            # Add diagnostic info
            issues = analyzer.analyze_result(r)
            if issues:
                lines.append(f"\n**Issues Found**: {len(issues)}")
                for issue in issues:
                    lines.append(f"- [{issue.severity.value}] {issue.title}")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------

def generate_json_report(result: SimulationResult) -> str:
    """Generate a JSON report from a simulation result."""
    return json.dumps(result.to_dict(), indent=2)


def generate_course_json_report(results: CourseResults) -> str:
    """Generate a JSON report for an entire course run with quality metrics."""
    metrics = calculate_metrics(results.results, total_exercises=results.total_exercises)
    data = results.to_dict()
    data['quality_metrics'] = metrics.to_dict()
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# JUnit XML report
# ---------------------------------------------------------------------------

def generate_junit_report(result: SimulationResult) -> str:
    """Generate a JUnit XML report from a simulation result."""
    total = len(result.steps_executed)
    failures = result.steps_failed
    skipped = total - result.steps_passed - failures

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<testsuite name="{result.exercise_id}" tests="{total}" '
        f'failures="{failures}" skipped="{skipped}" '
        f'time="{result.total_duration_seconds:.1f}">',
    ]

    for step in result.steps_executed:
        cmd = _xml_escape(step.command or "")
        name = _xml_escape(f"Step {step.number}: {step.text[:60]}")
        lines.append(f'  <testcase name="{name}" classname="{result.exercise_id}" '
                     f'time="{step.duration_seconds:.1f}">')

        if step.result == StepResult.FAIL:
            error = _xml_escape(step.error or "Unknown error")
            lines.append(f'    <failure message="{_xml_escape(cmd)}">{error}</failure>')
        elif step.result == StepResult.SKIP:
            lines.append(f'    <skipped/>')

        lines.append('  </testcase>')

    lines.append('</testsuite>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File writing
# ---------------------------------------------------------------------------

def write_report(result: SimulationResult, output_dir: Path,
                 formats: List[str] = None) -> List[Path]:
    """Write reports to files.

    Args:
        result: Simulation result
        output_dir: Directory to write reports to
        formats: List of formats ("markdown", "json", "junit"). Default: all.

    Returns:
        List of written file paths
    """
    if formats is None:
        formats = ["markdown"]

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    written = []

    # Include cycle number in filename for idempotency testing
    cycle_suffix = f"-cycle{result.cycle}" if result.cycle > 1 else ""

    if "markdown" in formats:
        path = output_dir / f"{result.exercise_id}{cycle_suffix}-{timestamp}.md"
        path.write_text(generate_report(result))
        written.append(path)

    if "json" in formats:
        path = output_dir / f"{result.exercise_id}{cycle_suffix}-{timestamp}.json"
        path.write_text(generate_json_report(result))
        written.append(path)

    if "junit" in formats:
        path = output_dir / f"{result.exercise_id}-{timestamp}.xml"
        path.write_text(generate_junit_report(result))
        written.append(path)

    return written


def write_course_report(results: CourseResults, output_dir: Path,
                        formats: List[str] = None, include_diagnostics: bool = True) -> List[Path]:
    """Write course-level reports to files.

    Args:
        results: Course results with all exercise results
        output_dir: Directory to write reports to
        formats: List of formats ("markdown", "json"). Default: both.
        include_diagnostics: Whether to write a separate diagnostics report. Default: True.

    Returns:
        List of written file paths
    """
    if formats is None:
        formats = ["markdown", "json"]

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    written = []

    if "markdown" in formats:
        path = output_dir / f"{results.course_code}-report-{timestamp}.md"
        path.write_text(generate_course_report(results))
        written.append(path)

    if "json" in formats:
        path = output_dir / f"{results.course_code}-report-{timestamp}.json"
        path.write_text(generate_course_json_report(results))
        written.append(path)

    # Write standalone diagnostics report if there are any issues
    if include_diagnostics:
        failed_results = [r for r in results.results if not r.success]
        if failed_results or any(r.bugs for r in results.results):
            diagnostics = generate_diagnostics_report(results.results)
            path = output_dir / f"{results.course_code}-diagnostics-{timestamp}.md"
            path.write_text(diagnostics)
            written.append(path)

    return written


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate(text: str, max_len: int) -> str:
    text = text.replace("\n", " ").strip()
    return text if len(text) <= max_len else text[:max_len - 3] + "..."


def _xml_escape(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))
