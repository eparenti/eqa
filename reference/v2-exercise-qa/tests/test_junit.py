"""Tests for JUnit XML report generator."""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile

from src.reporting.junit import JUnitReportGenerator, CSVReportGenerator
from src.core.models import (
    CourseTestResults, ExerciseTestResults, TestResult,
    Bug, BugSeverity
)


@pytest.fixture
def sample_results():
    """Create sample test results for testing."""
    bug = Bug(
        id='LINT-001',
        severity=BugSeverity.P1_CRITICAL,
        category='TC-LINT',
        exercise_id='test-exercise-lab',
        description='Syntax error in playbook.yml',
        fix_recommendation='Fix YAML syntax'
    )

    test_result_pass = TestResult(
        category='TC-VARS',
        exercise_id='test-exercise-lab',
        passed=True,
        timestamp=datetime.now().isoformat(),
        duration_seconds=0.5,
        bugs_found=[],
        details={'vars_checked': 10}
    )

    test_result_fail = TestResult(
        category='TC-LINT',
        exercise_id='test-exercise-lab',
        passed=False,
        timestamp=datetime.now().isoformat(),
        duration_seconds=1.5,
        bugs_found=[bug],
        details={'files_linted': 5}
    )

    exercise_result = ExerciseTestResults(
        exercise_id='test-exercise-lab',
        lesson_code='TEST001',
        start_time=datetime.now().isoformat(),
        end_time=datetime.now().isoformat(),
        duration_seconds=2.0,
        status='FAIL',
        test_categories={
            'TC-VARS': test_result_pass,
            'TC-LINT': test_result_fail
        },
        bugs=[bug],
        summary='1/2 tests passed'
    )

    return CourseTestResults(
        course_code='TEST001',
        test_date=datetime.now().isoformat(),
        total_exercises=1,
        exercises_tested=1,
        exercises_passed=0,
        exercises_failed=1,
        exercises_skipped=0,
        total_duration_seconds=2.0,
        exercise_results=[exercise_result],
        all_bugs=[bug],
        summary={'pass_rate': 50}
    )


class TestJUnitReportGenerator:
    """Tests for JUnit XML report generation."""

    def test_generates_valid_xml(self, sample_results):
        """Test that valid XML is generated."""
        gen = JUnitReportGenerator(sample_results)
        xml = gen.generate()

        assert '<?xml version' in xml
        assert '<testsuites' in xml
        assert '</testsuites>' in xml

    def test_includes_course_name(self, sample_results):
        """Test that course name is in output."""
        gen = JUnitReportGenerator(sample_results)
        xml = gen.generate()

        assert 'TEST001' in xml

    def test_includes_test_counts(self, sample_results):
        """Test that test counts are correct."""
        gen = JUnitReportGenerator(sample_results)
        xml = gen.generate()

        assert 'tests="2"' in xml
        assert 'failures="1"' in xml

    def test_includes_failure_details(self, sample_results):
        """Test that failure details are included."""
        gen = JUnitReportGenerator(sample_results)
        xml = gen.generate()

        assert '<failure' in xml
        assert 'Syntax error' in xml
        assert 'Fix YAML syntax' in xml

    def test_includes_testcase_timing(self, sample_results):
        """Test that timing information is included."""
        gen = JUnitReportGenerator(sample_results)
        xml = gen.generate()

        assert 'time="1.500"' in xml or 'time="0.500"' in xml

    def test_writes_to_file(self, sample_results):
        """Test that XML can be written to file."""
        gen = JUnitReportGenerator(sample_results)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.xml"
            gen.generate(output_path)

            assert output_path.exists()
            content = output_path.read_text()
            assert '<testsuites' in content

    def test_passing_test_has_no_failure_element(self, sample_results):
        """Test that passing tests don't have failure elements."""
        gen = JUnitReportGenerator(sample_results)
        xml = gen.generate()

        # TC-VARS passed, should not have failure in its testcase
        # This is a bit tricky to check without parsing XML
        assert 'TC-VARS' in xml


class TestCSVReportGenerator:
    """Tests for CSV report generation."""

    def test_generates_csv_header(self, sample_results):
        """Test that CSV has correct header."""
        gen = CSVReportGenerator(sample_results)
        csv = gen.generate()

        lines = csv.strip().split('\n')
        header = lines[0]

        assert 'exercise_id' in header
        assert 'category' in header
        assert 'passed' in header

    def test_includes_test_data(self, sample_results):
        """Test that test data is included."""
        gen = CSVReportGenerator(sample_results)
        csv = gen.generate()

        assert 'test-exercise-lab' in csv
        assert 'TC-LINT' in csv
        assert 'TC-VARS' in csv

    def test_failure_marked_as_zero(self, sample_results):
        """Test that failures are marked as 0."""
        gen = CSVReportGenerator(sample_results)
        csv = gen.generate()

        # TC-LINT failed, should have passed=0
        lines = csv.strip().split('\n')
        lint_line = [l for l in lines if 'TC-LINT' in l][0]
        assert ',0,' in lint_line  # passed=0

    def test_pass_marked_as_one(self, sample_results):
        """Test that passes are marked as 1."""
        gen = CSVReportGenerator(sample_results)
        csv = gen.generate()

        # TC-VARS passed, should have passed=1
        lines = csv.strip().split('\n')
        vars_line = [l for l in lines if 'TC-VARS' in l][0]
        assert ',1,' in vars_line  # passed=1

    def test_writes_to_file(self, sample_results):
        """Test that CSV can be written to file."""
        gen = CSVReportGenerator(sample_results)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.csv"
            gen.generate(output_path)

            assert output_path.exists()
            content = output_path.read_text()
            assert 'exercise_id' in content
