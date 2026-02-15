"""
Student Simulation Report Generator

Generates clear, readable Markdown reports from student simulation results.
"""

from typing import Optional
from ..testing.student_simulator import SimulationResult, ExecutedStep, StepResult


def generate_report(result: SimulationResult) -> str:
    """Generate a Markdown report from simulation results."""
    sections = [
        _header(result),
        _executive_summary(result),
        _step_breakdown(result),
        _recommendations(result),
    ]
    return "\n\n".join(filter(None, sections))


def _header(result: SimulationResult) -> str:
    status = "PASSED" if result.success else "FAILED"
    return f"""# Student Simulation Report: {result.exercise_id}

**Status**: {status}
**Phase**: {result.phase}
**Duration**: {result.total_duration_seconds:.1f}s"""


def _executive_summary(result: SimulationResult) -> str:
    total = len(result.steps_executed)
    passed, failed = result.steps_passed, result.steps_failed
    skipped = total - passed - failed

    if result.success:
        verdict = "The student simulation completed successfully."
    else:
        verdict = f"The simulation failed at phase: **{result.phase}**"
        if result.error_message:
            verdict += f"\n\n**Error**: {result.error_message}"

    return f"""## Executive Summary

{verdict}

| Metric | Count |
|--------|-------|
| Steps Executed | {total} |
| Passed | {passed} |
| Failed | {failed} |
| Skipped | {skipped} |"""


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


def _truncate(text: str, max_len: int) -> str:
    text = text.replace("\n", " ").strip()
    return text if len(text) <= max_len else text[:max_len - 3] + "..."
