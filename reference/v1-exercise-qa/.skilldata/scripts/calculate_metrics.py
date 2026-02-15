#!/usr/bin/env python3
"""
Calculate QA Metrics

Analyzes TEST-EXECUTION-TRACKING.csv and generates quality metrics.

Usage:
    python scripts/calculate_metrics.py <tracking-csv-path> [--html output.html] [--json output.json]

Options:
    --html FILE    Generate HTML dashboard
    --json FILE    Generate JSON output
    --exit-code    Exit with non-zero code if quality gates fail
"""

import sys
import csv
import json
from pathlib import Path
from collections import Counter
from datetime import datetime

def validate_csv_structure(tests):
    """Validate that CSV has required columns."""
    required_columns = ['Test Case ID', 'Status', 'Result', 'Priority', 'Bug ID']

    if not tests:
        return False, "CSV file is empty or has no data rows"

    first_row = tests[0]
    missing_columns = [col for col in required_columns if col not in first_row]

    if missing_columns:
        return False, f"Missing required columns: {', '.join(missing_columns)}"

    return True, "CSV structure valid"

def calculate_metrics(csv_path, options=None):
    """Calculate comprehensive QA metrics from tracking CSV."""
    options = options or {}

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            tests = list(reader)
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        sys.exit(1)

    # Validate CSV structure
    valid, message = validate_csv_structure(tests)
    if not valid:
        print(f"❌ Validation Error: {message}")
        sys.exit(1)

    # Filter out header rows and empty rows
    tests = [t for t in tests if t.get('Test Case ID', '').strip() and
             t.get('Test Case ID') != 'Test Case ID']

    # Calculate all metrics in a single pass
    total = len(tests)
    executed = passed = failed = blocked = 0
    bug_ids = []
    bugs_by_severity = Counter()
    priority_counts = Counter()
    category_counts = Counter()

    for t in tests:
        status = t.get('Status', '').strip()
        result = t.get('Result', '')
        priority = t.get('Priority', '').strip()
        bug_id = t.get('Bug ID', '').strip()
        category = t.get('Category', 'Unknown').strip()

        # Count execution status
        if status == 'Completed':
            executed += 1
        if 'BLOCKED' in status.upper():
            blocked += 1

        # Count pass/fail
        if '✅' in result or 'PASS' in result.upper():
            passed += 1
        if '❌' in result or 'FAIL' in result.upper():
            failed += 1

        # Collect bug data
        if bug_id and bug_id != '':
            bug_ids.append(bug_id)
            if bug_id.startswith('BUG') and priority:
                bugs_by_severity[priority] += 1

        # Count priorities and categories
        if priority:
            priority_counts[priority] += 1
        if category:
            category_counts[category] += 1

    unique_bugs = len(set(bug_ids))
    pass_rate = (passed / executed * 100) if executed > 0 else 0
    execution_rate = (executed / total * 100) if total > 0 else 0

    # Print dashboard
    print(f"\n{'='*60}")
    print(f"QA METRICS DASHBOARD")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    print(f"📊 TEST EXECUTION")
    print(f"   Total Tests:     {total}")
    print(f"   Executed:        {executed} ({execution_rate:.1f}%)")
    print(f"   Not Started:     {total - executed}")
    print(f"   Blocked:         {blocked}\n")

    print(f"✅ TEST RESULTS")
    print(f"   Passed:          {passed}")
    print(f"   Failed:          {failed}")
    print(f"   Pass Rate:       {pass_rate:.1f}%\n")

    print(f"🐛 BUG ANALYSIS")
    print(f"   Unique Bugs:     {unique_bugs}")
    print(f"   Total Failures:  {failed}")
    if bugs_by_severity:
        print(f"\n   By Severity:")
        for priority in ['P0', 'P1', 'P2', 'P3', 'P4']:
            count = bugs_by_severity.get(priority, 0)
            if count > 0:
                print(f"      {priority}: {count} bugs")
    print()

    print(f"⭐ TEST PRIORITY BREAKDOWN")
    for priority in ['P0', 'P1', 'P2', 'P3', 'P4']:
        count = priority_counts.get(priority, 0)
        if count > 0:
            print(f"   {priority}:              {count} tests")
    print()

    if category_counts:
        print(f"📁 TEST CATEGORY BREAKDOWN")
        for category, count in category_counts.most_common():
            print(f"   {category:15} {count} tests")
        print()

    # Quality gates with proper P0 bug detection
    p0_bugs = len([t for t in tests
                   if t.get('Bug ID', '').strip().startswith('BUG')
                   and t.get('Priority', '').strip() == 'P0'])

    p1_bugs = len([t for t in tests
                   if t.get('Bug ID', '').strip().startswith('BUG')
                   and t.get('Priority', '').strip() == 'P1'])

    gates = {
        "Test Execution = 100%": execution_rate >= 100,
        "Pass Rate ≥80%": pass_rate >= 80,
        "P0 Bugs = 0": p0_bugs == 0,
        "P1 Bugs ≤5": p1_bugs <= 5,
    }

    print(f"🎯 QUALITY GATES")
    gates_passed = 0
    gates_total = len(gates)

    for gate, status in gates.items():
        symbol = "✅" if status else "❌"
        print(f"   {symbol} {gate}")
        if status:
            gates_passed += 1

    print(f"\n   Overall: {gates_passed}/{gates_total} gates passing")
    print(f"\n{'='*60}\n")

    # Prepare results dictionary
    results = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total': total,
            'executed': executed,
            'passed': passed,
            'failed': failed,
            'blocked': blocked,
            'pass_rate': round(pass_rate, 2),
            'execution_rate': round(execution_rate, 2),
            'unique_bugs': unique_bugs
        },
        'bugs': {
            'total': unique_bugs,
            'by_severity': dict(bugs_by_severity)
        },
        'priorities': dict(priority_counts),
        'categories': dict(category_counts),
        'quality_gates': {
            'passed': gates_passed,
            'total': gates_total,
            'gates': {k: v for k, v in gates.items()}
        }
    }

    # Generate HTML output if requested
    if options.get('html'):
        generate_html_report(results, options['html'])
        print(f"✅ HTML report generated: {options['html']}")

    # Generate JSON output if requested
    if options.get('json'):
        with open(options['json'], 'w') as f:
            json.dump(results, f, indent=2)
        print(f"✅ JSON report generated: {options['json']}")

    # Exit with error code if quality gates fail and --exit-code is set
    if options.get('exit_code') and gates_passed < gates_total:
        sys.exit(1)

    return results

def generate_html_report(results, output_path):
    """Generate HTML dashboard from metrics."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QA Metrics Dashboard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: #f9f9f9;
            border-left: 4px solid #4CAF50;
            padding: 15px;
            border-radius: 4px;
        }}
        .metric-card.warning {{
            border-left-color: #ff9800;
        }}
        .metric-card.danger {{
            border-left-color: #f44336;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }}
        .metric-label {{
            color: #666;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        .quality-gates {{
            margin: 30px 0;
        }}
        .gate {{
            padding: 10px;
            margin: 5px 0;
            border-radius: 4px;
            display: flex;
            align-items: center;
        }}
        .gate.pass {{
            background: #e8f5e9;
            border-left: 4px solid #4CAF50;
        }}
        .gate.fail {{
            background: #ffebee;
            border-left: 4px solid #f44336;
        }}
        .timestamp {{
            color: #999;
            font-size: 0.85em;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>QA Metrics Dashboard</h1>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">{results['summary']['total']}</div>
                <div class="metric-label">Total Tests</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{results['summary']['execution_rate']:.1f}%</div>
                <div class="metric-label">Execution Rate</div>
            </div>
            <div class="metric-card {'warning' if results['summary']['pass_rate'] < 80 else ''}">
                <div class="metric-value">{results['summary']['pass_rate']:.1f}%</div>
                <div class="metric-label">Pass Rate</div>
            </div>
            <div class="metric-card {'danger' if results['summary']['unique_bugs'] > 0 else ''}">
                <div class="metric-value">{results['summary']['unique_bugs']}</div>
                <div class="metric-label">Unique Bugs</div>
            </div>
        </div>

        <h2>Quality Gates</h2>
        <div class="quality-gates">
"""

    for gate, passed in results['quality_gates']['gates'].items():
        status = 'pass' if passed else 'fail'
        symbol = '✅' if passed else '❌'
        html += f'            <div class="gate {status}">{symbol} {gate}</div>\n'

    html += f"""        </div>

        <h2>Test Results</h2>
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">{results['summary']['passed']}</div>
                <div class="metric-label">✅ Passed</div>
            </div>
            <div class="metric-card warning">
                <div class="metric-value">{results['summary']['failed']}</div>
                <div class="metric-label">❌ Failed</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{results['summary']['blocked']}</div>
                <div class="metric-label">🚫 Blocked</div>
            </div>
        </div>

        <div class="timestamp">
            Generated: {results['timestamp']}
        </div>
    </div>
</body>
</html>"""

    with open(output_path, 'w') as f:
        f.write(html)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python calculate_metrics.py <tracking-csv-path> [--html output.html] [--json output.json] [--exit-code]")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"❌ Error: File not found: {csv_path}")
        sys.exit(1)

    # Parse options
    options = {}
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == '--html' and i + 1 < len(args):
            options['html'] = args[i + 1]
            i += 2
        elif args[i] == '--json' and i + 1 < len(args):
            options['json'] = args[i + 1]
            i += 2
        elif args[i] == '--exit-code':
            options['exit_code'] = True
            i += 1
        else:
            i += 1

    calculate_metrics(csv_path, options)
