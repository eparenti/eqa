#!/usr/bin/env python3
"""
Enhanced Reporting and Analytics

Generates comprehensive QA reports in multiple formats:
- Markdown (existing)
- HTML (interactive)
- JSON (machine-readable)
- CSV (for spreadsheets)
- Trend analysis across multiple runs
- Advanced metrics and visualizations
"""

import sys
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.test_result import Bug, TestResult, ExerciseTestResults, CourseTestResults


class ReportExporter:
    """
    Export test results to multiple formats.
    """

    def __init__(self, output_dir: Path):
        """
        Initialize exporter.

        Args:
            output_dir: Output directory for reports
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_json(self, results: Dict[str, Any], filename: str) -> Path:
        """
        Export results to JSON.

        Args:
            results: Test results
            filename: Output filename

        Returns:
            Path to exported file
        """
        output_path = self.output_dir / f"{filename}.json"

        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        return output_path

    def export_csv(self, results: Dict[str, Any], filename: str) -> Path:
        """
        Export results to CSV.

        Args:
            results: Test results
            filename: Output filename

        Returns:
            Path to exported file
        """
        output_path = self.output_dir / f"{filename}.csv"

        # Flatten results for CSV
        rows = []

        if 'test_results' in results:
            # Single exercise results
            for category, test_result in results['test_results'].items():
                rows.append({
                    'exercise_id': results['exercise_id'],
                    'category': category,
                    'passed': test_result.get('passed', False),
                    'duration': test_result.get('duration_seconds', 0),
                    'bugs': len(test_result.get('bugs_found', []))
                })

        elif 'exercise_results' in results:
            # Multiple exercise results
            for exercise in results['exercise_results']:
                rows.append({
                    'exercise_id': exercise['exercise_id'],
                    'lesson_code': exercise.get('lesson_code', ''),
                    'status': exercise['status'],
                    'duration': exercise['duration_seconds']
                })

        # Write CSV
        if rows:
            with open(output_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

        return output_path

    def export_html(self, results: Dict[str, Any], filename: str) -> Path:
        """
        Export results to HTML.

        Args:
            results: Test results
            filename: Output filename

        Returns:
            Path to exported file
        """
        output_path = self.output_dir / f"{filename}.html"

        html_content = self._generate_html(results)

        with open(output_path, 'w') as f:
            f.write(html_content)

        return output_path

    def _generate_html(self, results: Dict[str, Any]) -> str:
        """
        Generate HTML report.

        Args:
            results: Test results

        Returns:
            HTML content
        """
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Exercise QA Report - {results.get('exercise_id', results.get('course_code', 'Unknown'))}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .card h3 {{
            margin-top: 0;
            color: #333;
        }}
        .metric {{
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }}
        .pass {{ color: #10b981; }}
        .fail {{ color: #ef4444; }}
        table {{
            width: 100%;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-collapse: collapse;
        }}
        th {{
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid #eee;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        .bug {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            border-left: 4px solid #ef4444;
        }}
        .severity-p0 {{ border-left-color: #dc2626; }}
        .severity-p1 {{ border-left-color: #f59e0b; }}
        .severity-p2 {{ border-left-color: #3b82f6; }}
        .severity-p3 {{ border-left-color: #10b981; }}
        .timestamp {{
            color: #6b7280;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Exercise QA Report</h1>
        <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Exercise: {results.get('exercise_id', results.get('course_code', 'Unknown'))}</p>
    </div>

    <div class="summary">
        <div class="card">
            <h3>Total Tests</h3>
            <div class="metric">{results.get('total_tests', 0)}</div>
        </div>
        <div class="card">
            <h3>Passed</h3>
            <div class="metric pass">{results.get('passed', 0)}</div>
        </div>
        <div class="card">
            <h3>Failed</h3>
            <div class="metric fail">{results.get('failed', 0)}</div>
        </div>
        <div class="card">
            <h3>Duration</h3>
            <div class="metric">{results.get('duration_seconds', 0):.1f}s</div>
        </div>
    </div>
"""

        # Test Results Table
        if 'test_results' in results:
            html += """
    <h2>Test Results</h2>
    <table>
        <thead>
            <tr>
                <th>Category</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Bugs</th>
            </tr>
        </thead>
        <tbody>
"""
            for category, test_result in results['test_results'].items():
                status = "✅ PASS" if test_result.get('passed') else "❌ FAIL"
                status_class = "pass" if test_result.get('passed') else "fail"

                html += f"""
            <tr>
                <td>{category}</td>
                <td class="{status_class}">{status}</td>
                <td>{test_result.get('duration_seconds', 0):.2f}s</td>
                <td>{len(test_result.get('bugs_found', []))}</td>
            </tr>
"""

            html += """
        </tbody>
    </table>
"""

        # Bugs Section
        if results.get('bugs'):
            html += "<h2>Bugs Found</h2>"

            for bug in results['bugs']:
                severity = bug.get('severity', 'Unknown')
                severity_class = f"severity-{severity.lower()}"

                html += f"""
    <div class="bug {severity_class}">
        <h3>{bug.get('id', 'Unknown')}</h3>
        <p><strong>Severity:</strong> {severity} | <strong>Category:</strong> {bug.get('category', 'Unknown')}</p>
        <p><strong>Description:</strong> {bug.get('description', 'No description')}</p>
        <p><strong>Fix Recommendation:</strong></p>
        <pre style="background: #f5f5f5; padding: 10px; border-radius: 4px;">{bug.get('fix_recommendation', 'No recommendation')}</pre>
    </div>
"""

        html += """
</body>
</html>
"""

        return html


class TrendAnalyzer:
    """
    Analyze trends across multiple test runs.
    """

    def __init__(self, results_dir: Path):
        """
        Initialize trend analyzer.

        Args:
            results_dir: Directory containing historical test results
        """
        self.results_dir = results_dir

    def load_historical_results(self, exercise_id: Optional[str] = None) -> List[Dict]:
        """
        Load historical test results.

        Args:
            exercise_id: Optional filter by exercise

        Returns:
            List of historical results
        """
        results = []

        # Load all JSON result files
        for result_file in self.results_dir.glob('**/*.json'):
            try:
                with open(result_file, 'r') as f:
                    data = json.load(f)

                # Filter by exercise if specified
                if exercise_id and data.get('exercise_id') != exercise_id:
                    continue

                results.append(data)

            except Exception as e:
                print(f"Error loading {result_file}: {e}")

        # Sort by timestamp
        results.sort(key=lambda x: x.get('start_time', ''), reverse=True)

        return results

    def calculate_trends(self, results: List[Dict]) -> Dict[str, Any]:
        """
        Calculate trend metrics.

        Args:
            results: List of historical results

        Returns:
            Trend metrics
        """
        if not results:
            return {}

        trends = {
            'total_runs': len(results),
            'pass_rate_trend': [],
            'duration_trend': [],
            'bug_count_trend': [],
            'common_bugs': defaultdict(int),
            'improvement_rate': 0
        }

        for result in results:
            # Pass rate
            total = result.get('total_tests', 0)
            passed = result.get('passed', 0)
            pass_rate = (passed / total * 100) if total > 0 else 0

            trends['pass_rate_trend'].append({
                'timestamp': result.get('start_time', ''),
                'pass_rate': pass_rate
            })

            # Duration
            trends['duration_trend'].append({
                'timestamp': result.get('start_time', ''),
                'duration': result.get('duration_seconds', 0)
            })

            # Bug count
            bug_count = len(result.get('bugs', []))
            trends['bug_count_trend'].append({
                'timestamp': result.get('start_time', ''),
                'count': bug_count
            })

            # Common bugs
            for bug in result.get('bugs', []):
                bug_type = f"{bug.get('severity', 'Unknown')}-{bug.get('category', 'Unknown')}"
                trends['common_bugs'][bug_type] += 1

        # Calculate improvement rate
        if len(trends['pass_rate_trend']) >= 2:
            first_pass_rate = trends['pass_rate_trend'][-1]['pass_rate']
            last_pass_rate = trends['pass_rate_trend'][0]['pass_rate']
            trends['improvement_rate'] = last_pass_rate - first_pass_rate

        return trends

    def generate_trend_report(self, exercise_id: str) -> Dict[str, Any]:
        """
        Generate trend report for an exercise.

        Args:
            exercise_id: Exercise ID

        Returns:
            Trend report
        """
        results = self.load_historical_results(exercise_id)
        trends = self.calculate_trends(results)

        return {
            'exercise_id': exercise_id,
            'analysis_date': datetime.now().isoformat(),
            'trends': trends,
            'latest_result': results[0] if results else None,
            'historical_results': results
        }


class MetricsCalculator:
    """
    Calculate advanced metrics from test results.
    """

    @staticmethod
    def calculate_quality_score(results: Dict[str, Any]) -> float:
        """
        Calculate overall quality score (0-100).

        Args:
            results: Test results

        Returns:
            Quality score
        """
        score = 100.0

        # Deduct points for failures
        failed = results.get('failed', 0)
        total = results.get('total_tests', 1)
        score -= (failed / total * 40)  # Max 40 points for test failures

        # Deduct points for bugs
        bugs = results.get('bugs', [])
        for bug in bugs:
            severity = bug.get('severity', 'P3')
            if severity == 'P0':
                score -= 15
            elif severity == 'P1':
                score -= 10
            elif severity == 'P2':
                score -= 5
            elif severity == 'P3':
                score -= 2

        return max(0, score)

    @staticmethod
    def calculate_readiness(results: Dict[str, Any]) -> str:
        """
        Calculate release readiness.

        Args:
            results: Test results

        Returns:
            Readiness level (READY, NEEDS_WORK, BLOCKED)
        """
        # Check for blockers
        bugs = results.get('bugs', [])
        p0_bugs = [b for b in bugs if b.get('severity') == 'P0']
        p1_bugs = [b for b in bugs if b.get('severity') == 'P1']

        if p0_bugs:
            return 'BLOCKED'
        elif p1_bugs:
            return 'NEEDS_WORK'

        # Check pass rate
        total = results.get('total_tests', 0)
        passed = results.get('passed', 0)
        pass_rate = (passed / total * 100) if total > 0 else 0

        if pass_rate >= 100:
            return 'READY'
        elif pass_rate >= 80:
            return 'NEEDS_WORK'
        else:
            return 'BLOCKED'

    @staticmethod
    def calculate_coverage(results: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate test coverage metrics.

        Args:
            results: Test results

        Returns:
            Coverage metrics
        """
        test_categories = results.get('test_results', {})

        all_categories = [
            'TC-PREREQ', 'TC-INSTRUCT', 'TC-EXEC', 'TC-SOL',
            'TC-VERIFY', 'TC-GRADE', 'TC-WORKFLOW', 'TC-WEB',
            'TC-CLEAN', 'TC-IDEM', 'TC-E2E-CLEAN', 'TC-E2E-ISOLATION',
            'TC-E2E-SEQUENCE', 'TC-E2E-LEAKAGE'
        ]

        tested_categories = list(test_categories.keys())
        coverage = (len(tested_categories) / len(all_categories) * 100)

        return {
            'coverage_percent': coverage,
            'categories_tested': len(tested_categories),
            'categories_total': len(all_categories),
            'missing_categories': [c for c in all_categories if c not in tested_categories]
        }


def demo():
    """Demo enhanced reporting."""
    # Create sample results
    sample_results = {
        'exercise_id': '<exercise-name>',
        'lesson_code': '<lesson-code>',
        'type': 'GE',
        'start_time': '2026-01-10T15:30:00',
        'end_time': '2026-01-10T15:32:15',
        'duration_seconds': 135.2,
        'total_tests': 5,
        'passed': 4,
        'failed': 1,
        'test_results': {
            'TC-PREREQ': {'passed': True, 'duration_seconds': 12.5, 'bugs_found': []},
            'TC-EXEC': {'passed': True, 'duration_seconds': 25.3, 'bugs_found': []},
            'TC-SOL': {'passed': True, 'duration_seconds': 30.1, 'bugs_found': []},
            'TC-IDEM': {'passed': False, 'duration_seconds': 45.8, 'bugs_found': [{}]},
            'TC-CLEAN': {'passed': True, 'duration_seconds': 21.5, 'bugs_found': []}
        },
        'bugs': [
            {
                'id': 'BUG-CONTROL-FLOW-IDEM',
                'severity': 'P1',
                'category': 'TC-IDEM',
                'description': 'Exercise directory not removed after lab finish',
                'fix_recommendation': 'Update finish.yml to remove directory',
                'verification_steps': [
                    '1. Edit finish.yml',
                    '2. Add directory removal task',
                    '3. Test lab finish'
                ]
            }
        ]
    }

    # Create exporter
    output_dir = Path('/tmp/exercise-qa-reports')
    exporter = ReportExporter(output_dir)

    # Export to multiple formats
    print("Exporting reports...")
    json_path = exporter.export_json(sample_results, 'test-report')
    print(f"  JSON: {json_path}")

    csv_path = exporter.export_csv(sample_results, 'test-report')
    print(f"  CSV: {csv_path}")

    html_path = exporter.export_html(sample_results, 'test-report')
    print(f"  HTML: {html_path}")

    # Calculate metrics
    print("\nCalculating metrics...")
    quality_score = MetricsCalculator.calculate_quality_score(sample_results)
    print(f"  Quality Score: {quality_score:.1f}/100")

    readiness = MetricsCalculator.calculate_readiness(sample_results)
    print(f"  Release Readiness: {readiness}")

    coverage = MetricsCalculator.calculate_coverage(sample_results)
    print(f"  Test Coverage: {coverage['coverage_percent']:.1f}%")


if __name__ == "__main__":
    demo()
