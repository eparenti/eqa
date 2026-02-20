#!/usr/bin/env python3
"""Report generator — creates QA reports from structured test results.

Generates exercise reports, chapter summaries, and quality scores.
All output is the report markdown to stdout, diagnostics to stderr.

Usage:
    # Generate exercise report from JSON test data
    python3 report_tool.py exercise --data '{"exercise_id": "...", ...}'

    # Generate chapter summary from multiple exercise results
    python3 report_tool.py chapter --data '[{...}, {...}]'

    # Calculate quality score
    python3 report_tool.py score --data '[{...}, {...}]'
"""

import argparse
import json
from datetime import datetime
from collections import defaultdict

from eqa_common import _err, json_safe


# Performance budget thresholds (seconds)
PERF_BUDGETS = {
    "lab_start": 60,       # Flag if > 60s
    "lab_finish": 60,      # Flag if > 60s
    "student_sim": 600,    # Flag if > 10 min
    "total": 900,          # Flag if > 15 min total
}


def calculate_quality_score(results: list) -> dict:
    """Calculate a 0-100 quality score from exercise results.

    Components:
    - Coverage (30%): exercises tested / total
    - Defects (40%): penalty for bugs (P0=-40, P1=-20, P2=-5, P3=-1)
    - Reliability (30%): cleanup + idempotency pass rate
    """
    if not results:
        return {"score": 0, "breakdown": {}}

    total = len(results)
    tested = sum(1 for r in results if r.get("result") not in ("BLOCKED", "ENV", "SKIPPED"))

    # Coverage (0-30)
    coverage_pct = tested / total if total > 0 else 0
    coverage_score = round(coverage_pct * 30)

    # Defects (0-40, penalty-based)
    bug_penalties = {"P0": 40, "P1": 20, "P2": 5, "P3": 1, "ENV": 0}
    total_penalty = 0
    bug_counts = defaultdict(int)
    for r in results:
        for bug in r.get("bugs", []):
            sev = bug.get("severity", "P3")
            bug_counts[sev] += 1
            total_penalty += bug_penalties.get(sev, 0)
    defect_score = max(0, 40 - total_penalty)

    # Reliability (0-30)
    clean_pass = sum(1 for r in results if r.get("tc_clean") == "PASS")
    idem_pass = sum(1 for r in results if r.get("tc_idem") == "PASS")
    reliability_denom = tested * 2 if tested > 0 else 1
    reliability_score = round(((clean_pass + idem_pass) / reliability_denom) * 30)

    score = coverage_score + defect_score + reliability_score

    return {
        "score": min(100, score),
        "coverage_score": coverage_score,
        "defect_score": defect_score,
        "reliability_score": reliability_score,
        "coverage_pct": round(coverage_pct * 100),
        "bug_counts": dict(bug_counts),
        "total_bugs": sum(bug_counts.values()),
        "defect_density": round(sum(bug_counts.values()) / tested, 2) if tested > 0 else 0,
    }


def check_perf_budgets(results: list) -> list:
    """Check performance budgets and return violations."""
    violations = []
    for r in results:
        eid = r.get("exercise_id", "unknown")
        perf = r.get("performance", {})
        for phase, threshold in PERF_BUDGETS.items():
            actual = perf.get(phase, 0)
            if actual > threshold:
                violations.append({
                    "exercise": eid,
                    "phase": phase,
                    "actual": actual,
                    "budget": threshold,
                    "over_by": round(actual - threshold, 1),
                })
    return violations


def generate_exercise_report(data: dict) -> str:
    """Generate markdown report for a single exercise."""
    eid = data.get("exercise_id", "unknown")
    course = data.get("course_code", "")
    title = data.get("title", "")
    etype = data.get("type", "GE")
    result = data.get("result", "UNKNOWN")
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    summary = data.get("summary", "")
    bugs = data.get("bugs", [])
    perf = data.get("performance", {})
    tc = data.get("test_categories", {})

    lines = [
        f"# Exercise QA Report: {eid}",
        "",
        f"**Course:** {course}",
        f"**Exercise:** {eid} ({etype})",
        f"**Date:** {date}",
        f"**Result:** {result}",
        "",
        "## Summary",
        summary or "No summary provided.",
        "",
        "## Test Results",
        "",
    ]

    for cat_name, cat_result in tc.items():
        lines.append(f"### {cat_name}")
        if isinstance(cat_result, dict):
            for k, v in cat_result.items():
                lines.append(f"- {k}: {v}")
        else:
            lines.append(f"- Result: {cat_result}")
        lines.append("")

    if bugs:
        lines.append("## Bugs Found")
        lines.append("| ID | Severity | Category | Description | Fix | Component |")
        lines.append("|----|----------|----------|-------------|-----|-----------|")
        for i, bug in enumerate(bugs, 1):
            lines.append(
                f"| {bug.get('id', f'B{i}')} | {bug.get('severity', 'P3')} | "
                f"{bug.get('category', '')} | {bug.get('description', '')} | "
                f"{bug.get('fix', '')} | {bug.get('component', '')} |"
            )
        lines.append("")

    if perf:
        lines.append("## Performance")
        lines.append("| Phase | Duration | Budget |")
        lines.append("|-------|----------|--------|")
        for phase, duration in perf.items():
            budget = PERF_BUDGETS.get(phase, "—")
            flag = " **SLOW**" if isinstance(budget, (int, float)) and duration > budget else ""
            lines.append(f"| {phase} | {duration}s | {budget}s{flag} |")
        lines.append("")

    return "\n".join(lines)


def generate_chapter_summary(results: list, course_code: str = "", chapter: str = "") -> str:
    """Generate markdown chapter summary from multiple exercise results."""
    date = datetime.now().strftime("%Y-%m-%d")
    total = len(results)
    tested = sum(1 for r in results if r.get("result") not in ("BLOCKED", "ENV", "SKIPPED"))
    passed = sum(1 for r in results if r.get("result") == "PASS")

    quality = calculate_quality_score(results)
    violations = check_perf_budgets(results)

    # Determine overall result
    has_p0 = quality["bug_counts"].get("P0", 0) > 0
    has_p1 = quality["bug_counts"].get("P1", 0) > 0
    if has_p0:
        overall = "FAIL"
    elif has_p1 or tested < total:
        overall = "CONDITIONAL"
    else:
        overall = "PASS"

    lines = [
        f"# Chapter QA Summary: {course_code} Chapter {chapter}",
        "",
        f"**Course:** {course_code}",
        f"**Chapter:** {chapter}",
        f"**Date:** {date}",
        f"**Exercises tested:** {tested}/{total}",
        f"**Result:** {overall}",
        f"**Quality Score:** {quality['score']}/100",
        "",
        "## Exercise Results",
        "",
        "| Exercise | Type | Result | Bugs | Duration |",
        "|----------|------|--------|------|----------|",
    ]

    for r in results:
        eid = r.get("exercise_id", "?")
        etype = r.get("type", "?")
        result = r.get("result", "?")
        bug_count = len(r.get("bugs", []))
        total_time = r.get("performance", {}).get("total", "—")
        bug_str = f"{bug_count}" if bug_count else "0"
        lines.append(f"| {eid} | {etype} | {result} | {bug_str} | {total_time}s |")

    lines.extend([
        "",
        "## Quality Metrics",
        "",
        f"- Quality score: **{quality['score']}/100** (coverage={quality['coverage_score']}, defects={quality['defect_score']}, reliability={quality['reliability_score']})",
        f"- Total bugs: {quality['total_bugs']} ({', '.join(f'{k}: {v}' for k, v in sorted(quality['bug_counts'].items()))})" if quality['total_bugs'] else "- Total bugs: 0",
        f"- Defect density: {quality['defect_density']} bugs/exercise",
        f"- Coverage: {quality['coverage_pct']}%",
        "",
    ])

    if violations:
        lines.extend([
            "## Performance Budget Violations",
            "",
            "| Exercise | Phase | Actual | Budget | Over by |",
            "|----------|-------|--------|--------|---------|",
        ])
        for v in violations:
            lines.append(f"| {v['exercise']} | {v['phase']} | {v['actual']}s | {v['budget']}s | +{v['over_by']}s |")
        lines.append("")

    # Collect all bugs (copy to avoid mutating caller's data)
    all_bugs = []
    for r in results:
        for bug in r.get("bugs", []):
            all_bugs.append({**bug, "exercise": r.get("exercise_id", "?")})

    if all_bugs:
        lines.extend([
            "## All Bugs",
            "",
            "| Exercise | Severity | Description | Component |",
            "|----------|----------|-------------|-----------|",
        ])
        for bug in all_bugs:
            lines.append(f"| {bug['exercise']} | {bug.get('severity', '?')} | {bug.get('description', '')} | {bug.get('component', '')} |")
        lines.append("")

    return "\n".join(lines)


@json_safe
def cmd_exercise(args):
    data = json.loads(args.data)
    print(generate_exercise_report(data))


@json_safe
def cmd_chapter(args):
    data = json.loads(args.data)
    print(generate_chapter_summary(data, args.course, args.chapter))


@json_safe
def cmd_score(args):
    data = json.loads(args.data)
    result = calculate_quality_score(data)
    result["perf_violations"] = check_perf_budgets(data)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Report generator for eqa")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    p = subparsers.add_parser("exercise")
    p.add_argument("--data", required=True, help="JSON exercise result")
    p.set_defaults(func=cmd_exercise)

    p = subparsers.add_parser("chapter")
    p.add_argument("--data", required=True, help="JSON array of exercise results")
    p.add_argument("--course", default="")
    p.add_argument("--chapter", default="")
    p.set_defaults(func=cmd_chapter)

    p = subparsers.add_parser("score")
    p.add_argument("--data", required=True, help="JSON array of exercise results")
    p.set_defaults(func=cmd_score)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
