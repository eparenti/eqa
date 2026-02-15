"""JUnit XML report generator for Jenkins integration."""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..core.models import CourseTestResults, ExerciseTestResults, TestResult, Bug


class JUnitReportGenerator:
    """Generates JUnit XML reports for Jenkins integration."""

    def __init__(self, results: CourseTestResults):
        """Initialize with test results."""
        self.results = results

    def generate(self, output_path: Optional[Path] = None) -> str:
        """
        Generate JUnit XML report.

        Args:
            output_path: Optional path to write XML file

        Returns:
            XML string
        """
        # Create root testsuites element
        testsuites = ET.Element('testsuites')
        testsuites.set('name', f"exercise-qa-{self.results.course_code}")
        testsuites.set('tests', str(self._count_total_tests()))
        testsuites.set('failures', str(self._count_failures()))
        testsuites.set('errors', '0')
        testsuites.set('time', f"{self.results.total_duration_seconds:.3f}")

        # Create a testsuite for each exercise
        for exercise_result in self.results.exercise_results:
            testsuite = self._create_testsuite(exercise_result)
            testsuites.append(testsuite)

        # Convert to pretty XML string
        xml_str = self._prettify(testsuites)

        # Write to file if path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_str)

        return xml_str

    def _create_testsuite(self, exercise_result: ExerciseTestResults) -> ET.Element:
        """Create a testsuite element for an exercise."""
        testsuite = ET.Element('testsuite')
        testsuite.set('name', exercise_result.exercise_id)
        testsuite.set('tests', str(len(exercise_result.test_categories)))
        testsuite.set('failures', str(self._count_category_failures(exercise_result)))
        testsuite.set('errors', '0')
        testsuite.set('time', f"{exercise_result.duration_seconds:.3f}")
        testsuite.set('timestamp', exercise_result.start_time)

        # Add properties
        properties = ET.SubElement(testsuite, 'properties')
        self._add_property(properties, 'lesson_code', exercise_result.lesson_code)
        self._add_property(properties, 'status', exercise_result.status)

        # Create testcase for each test category
        for category_name, test_result in exercise_result.test_categories.items():
            testcase = self._create_testcase(test_result)
            testsuite.append(testcase)

        return testsuite

    def _create_testcase(self, test_result: TestResult) -> ET.Element:
        """Create a testcase element for a test category."""
        testcase = ET.Element('testcase')
        testcase.set('name', test_result.category)
        testcase.set('classname', f"{test_result.exercise_id}.{test_result.category}")
        testcase.set('time', f"{test_result.duration_seconds:.3f}")

        if not test_result.passed:
            # Add failure element with bug details
            failure = ET.SubElement(testcase, 'failure')
            failure.set('message', f"{len(test_result.bugs_found)} issue(s) found")
            failure.set('type', 'AssertionError')

            # Build failure text from bugs
            failure_text = []
            for bug in test_result.bugs_found:
                failure_text.append(f"[{bug.severity.value}] {bug.description}")
                failure_text.append(f"  Fix: {bug.fix_recommendation}")
                failure_text.append("")

            failure.text = "\n".join(failure_text)

        # Add system-out with test details
        system_out = ET.SubElement(testcase, 'system-out')
        details_text = []
        for key, value in test_result.details.items():
            details_text.append(f"{key}: {value}")
        system_out.text = "\n".join(details_text) if details_text else ""

        return testcase

    def _add_property(self, properties: ET.Element, name: str, value: str):
        """Add a property element."""
        prop = ET.SubElement(properties, 'property')
        prop.set('name', name)
        prop.set('value', str(value))

    def _count_total_tests(self) -> int:
        """Count total test cases across all exercises."""
        return sum(
            len(ex.test_categories)
            for ex in self.results.exercise_results
        )

    def _count_failures(self) -> int:
        """Count total failures across all exercises."""
        return sum(
            self._count_category_failures(ex)
            for ex in self.results.exercise_results
        )

    def _count_category_failures(self, exercise_result: ExerciseTestResults) -> int:
        """Count failures in an exercise's test categories."""
        return sum(
            1 for tc in exercise_result.test_categories.values()
            if not tc.passed
        )

    def _prettify(self, elem: ET.Element) -> str:
        """Return a pretty-printed XML string."""
        rough_string = ET.tostring(elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")


class CSVReportGenerator:
    """Generates CSV reports compatible with existing Jenkins format."""

    def __init__(self, results: CourseTestResults):
        """Initialize with test results."""
        self.results = results

    def generate(self, output_path: Optional[Path] = None) -> str:
        """
        Generate CSV report in Jenkins-compatible format.

        Args:
            output_path: Optional path to write CSV file

        Returns:
            CSV string
        """
        lines = []

        # Header matching existing format
        lines.append("tbl,index,exercise_id,category,passed,bugs,duration,severity")

        index = 1
        for exercise_result in self.results.exercise_results:
            for category_name, test_result in exercise_result.test_categories.items():
                # Determine highest severity bug
                max_severity = "none"
                if test_result.bugs_found:
                    severities = [b.severity.value for b in test_result.bugs_found]
                    max_severity = min(severities)  # P0 < P1 < P2 < P3

                line = ",".join([
                    "tbl",
                    str(index),
                    exercise_result.exercise_id,
                    category_name,
                    "1" if test_result.passed else "0",
                    str(len(test_result.bugs_found)),
                    f"{test_result.duration_seconds:.3f}",
                    max_severity
                ])
                lines.append(line)
                index += 1

        csv_content = "\n".join(lines)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(csv_content)

        return csv_content
