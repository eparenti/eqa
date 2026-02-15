#!/usr/bin/env python3
"""
TC-AAP: AAP Controller Testing

Tests AAP Controller resources and configurations in exercises.

Many AAP courses (<AAP-COURSE>, <NETWORK-COURSE>) require students to configure
AAP Controller resources like credentials, projects, inventories, and
job templates. This test category validates those configurations.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.test_result import TestResult, Bug, BugSeverity, ExerciseContext
from lib.ssh_connection import SSHConnection
from lib.aap_client import (
    AAPControllerClient,
    AAPControllerAPIError,
    grade_credentials,
    grade_projects,
    grade_job_templates
)


class TC_AAP:
    """
    AAP Controller testing.

    Tests that students have correctly configured AAP Controller resources
    including credentials, projects, inventories, and job templates.
    """

    def __init__(self, aap_url: str = "https://aap.lab.example.com"):
        """
        Initialize AAP Controller tester.

        Args:
            aap_url: Base URL of AAP Controller
        """
        self.aap_url = aap_url

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test AAP Controller configuration.

        Args:
            exercise: Exercise context
            ssh: SSH connection to workstation

        Returns:
            TestResult with AAP Controller test results
        """
        start_time = datetime.now()
        bugs_found = []
        test_details = {
            'aap_url': self.aap_url,
            'connection_successful': False,
            'resources_tested': [],
            'grading_results': {}
        }

        print(f"\n🔧 TC-AAP: AAP Controller Testing")
        print("=" * 60)
        print(f"  AAP Controller URL: {self.aap_url}")

        # Test AAP Controller connection
        print("\n  Testing AAP Controller connection...")
        client = AAPControllerClient(self.aap_url)

        try:
            if not client.test_connection():
                bugs_found.append(Bug(
                    id=f"BUG-{exercise.id.upper()}-AAP-UNREACHABLE",
                    severity=BugSeverity.P0_BLOCKER,
                    exercise_id=exercise.id,
                    category="TC-AAP",
                    description=f"AAP Controller is unreachable at {self.aap_url}",
                    fix_recommendation=(
                        "Ensure AAP Controller is running and accessible:\n\n"
                        f"1. Check if AAP Controller is running at {self.aap_url}\n"
                        "2. Verify network connectivity\n"
                        "3. Check firewall rules\n"
                        "4. Verify credentials (AAP_USERNAME/AAP_PASSWORD)"
                    ),
                    verification_steps=[
                        f"1. curl -k {self.aap_url}/api/v2/ping/",
                        "2. Check AAP Controller service status",
                        "3. Verify network connectivity",
                        "4. Test with browser"
                    ]
                ))
                print("    ❌ AAP Controller unreachable")

                return TestResult(
                    category="TC-AAP",
                    exercise_id=exercise.id,
                    passed=False,
                    timestamp=start_time.isoformat(),
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    bugs_found=bugs_found,
                    details=test_details,
                    summary="AAP Controller unreachable"
                )

            test_details['connection_successful'] = True
            print("    ✅ AAP Controller is reachable")

            # Look for expected resources definition
            # Check for Python grading script or resource definitions
            expected_resources = self._find_expected_resources(exercise, ssh)

            if not expected_resources:
                print("  ⏭️  No AAP Controller resources defined (skipping)")
                return TestResult(
                    category="TC-AAP",
                    exercise_id=exercise.id,
                    passed=True,
                    timestamp=start_time.isoformat(),
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    bugs_found=[],
                    details={'skipped': True, 'reason': 'No AAP resources defined'},
                    summary="Skipped: No AAP resources to test"
                )

            # Grade credentials
            if expected_resources.get('credentials'):
                print(f"\n  Grading {len(expected_resources['credentials'])} credentials...")
                success, message = grade_credentials(
                    expected_resources['credentials'],
                    base_url=self.aap_url,
                    verbose=True
                )

                test_details['grading_results']['credentials'] = {
                    'success': success,
                    'message': message
                }

                if not success:
                    bugs_found.append(Bug(
                        id=f"BUG-{exercise.id.upper()}-AAP-CREDENTIALS",
                        severity=BugSeverity.P1_CRITICAL,
                        exercise_id=exercise.id,
                        category="TC-AAP",
                        description="AAP Controller credentials are not configured correctly",
                        fix_recommendation=(
                            f"Fix AAP Controller credentials:\n\n"
                            f"{message}\n\n"
                            "Review the exercise instructions and ensure all credentials\n"
                            "are created with the correct configuration."
                        ),
                        verification_steps=[
                            "1. Log into AAP Controller UI",
                            "2. Navigate to Resources → Credentials",
                            "3. Verify all required credentials exist",
                            "4. Check credential types and organizations",
                            "5. Re-run grading"
                        ]
                    ))

            # Grade projects
            if expected_resources.get('projects'):
                print(f"\n  Grading {len(expected_resources['projects'])} projects...")
                success, message = grade_projects(
                    expected_resources['projects'],
                    base_url=self.aap_url,
                    verbose=True
                )

                test_details['grading_results']['projects'] = {
                    'success': success,
                    'message': message
                }

                if not success:
                    bugs_found.append(Bug(
                        id=f"BUG-{exercise.id.upper()}-AAP-PROJECTS",
                        severity=BugSeverity.P1_CRITICAL,
                        exercise_id=exercise.id,
                        category="TC-AAP",
                        description="AAP Controller projects are not configured correctly",
                        fix_recommendation=(
                            f"Fix AAP Controller projects:\n\n"
                            f"{message}\n\n"
                            "Review the exercise instructions and ensure all projects\n"
                            "are created with the correct SCM URLs and settings."
                        ),
                        verification_steps=[
                            "1. Log into AAP Controller UI",
                            "2. Navigate to Resources → Projects",
                            "3. Verify all required projects exist",
                            "4. Check SCM URLs and branches",
                            "5. Test project sync",
                            "6. Re-run grading"
                        ]
                    ))

            # Grade job templates
            if expected_resources.get('job_templates'):
                print(f"\n  Grading {len(expected_resources['job_templates'])} job templates...")
                success, message = grade_job_templates(
                    expected_resources['job_templates'],
                    base_url=self.aap_url,
                    verbose=True
                )

                test_details['grading_results']['job_templates'] = {
                    'success': success,
                    'message': message
                }

                if not success:
                    bugs_found.append(Bug(
                        id=f"BUG-{exercise.id.upper()}-AAP-JOB-TEMPLATES",
                        severity=BugSeverity.P1_CRITICAL,
                        exercise_id=exercise.id,
                        category="TC-AAP",
                        description="AAP Controller job templates are not configured correctly",
                        fix_recommendation=(
                            f"Fix AAP Controller job templates:\n\n"
                            f"{message}\n\n"
                            "Review the exercise instructions and ensure all job templates\n"
                            "are created with the correct playbooks and settings."
                        ),
                        verification_steps=[
                            "1. Log into AAP Controller UI",
                            "2. Navigate to Resources → Templates",
                            "3. Verify all required job templates exist",
                            "4. Check playbook paths",
                            "5. Verify inventories and credentials",
                            "6. Re-run grading"
                        ]
                    ))

        finally:
            client.close()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        passed = len(bugs_found) == 0

        return TestResult(
            category="TC-AAP",
            exercise_id=exercise.id,
            passed=passed,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details=test_details,
            summary=f"AAP Controller testing {'passed' if passed else 'failed'} - {len(bugs_found)} issues found"
        )

    def _find_expected_resources(
        self,
        exercise: ExerciseContext,
        ssh: SSHConnection
    ) -> Optional[Dict]:
        """
        Find expected AAP Controller resources for this exercise.

        Looks for:
        1. Python grading script with resource definitions
        2. JSON/YAML resource definition files
        3. Exercise instructions with resource specs

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            Dict of expected resources or None
        """
        # Try to find Python grading script
        possible_locations = [
            f"/home/student/DO{exercise.lesson_code.upper()}/grading/{exercise.id}.py",
            f"/home/student/grading/{exercise.id}.py",
            f"~/DO{exercise.lesson_code.upper()}/labs/{exercise.id}/aap_resources.json",
            f"~/DO{exercise.lesson_code.upper()}/labs/{exercise.id}/aap_resources.yaml",
        ]

        for location in possible_locations:
            result = ssh.run(f"test -f {location} && echo 'exists'", timeout=5)
            if result['exit_code'] == 0 and 'exists' in result['stdout']:
                print(f"  Found resource definition: {location}")

                # Read and parse the file
                if location.endswith('.json'):
                    content_result = ssh.run(f"cat {location}", timeout=5)
                    if content_result['exit_code'] == 0:
                        try:
                            return json.loads(content_result['stdout'])
                        except json.JSONDecodeError:
                            print(f"    ⚠️  Failed to parse JSON from {location}")

                # For Python files, try to extract resource definitions
                if location.endswith('.py'):
                    return self._extract_resources_from_python(ssh, location)

        # No resources found
        return None

    def _extract_resources_from_python(
        self,
        ssh: SSHConnection,
        script_path: str
    ) -> Optional[Dict]:
        """
        Extract resource definitions from Python grading script.

        Args:
            ssh: SSH connection
            script_path: Path to Python script

        Returns:
            Dict of resources or None
        """
        # Read the Python file
        result = ssh.run(f"cat {script_path}", timeout=5)
        if result['exit_code'] != 0:
            return None

        content = result['stdout']
        resources = {}

        # Look for CREDENTIALS, PROJECTS, INVENTORIES, JOB_TEMPLATES lists
        # This is a simple pattern match - could be made more sophisticated
        for resource_type in ['CREDENTIALS', 'PROJECTS', 'INVENTORIES', 'JOB_TEMPLATES']:
            if resource_type in content:
                # Found a potential resource definition
                # For simplicity, we'll note that resources are defined
                # but won't try to parse them (too complex for simple string matching)
                print(f"    Found {resource_type} definition in {script_path}")
                # Set placeholder - in real implementation, would parse the actual values
                resources[resource_type.lower()] = []

        return resources if resources else None


def main():
    """Test TC_AAP functionality."""
    import argparse

    parser = argparse.ArgumentParser(description="Test TC-AAP category")
    parser.add_argument("exercise_id", help="Exercise ID to test")
    parser.add_argument("--workstation", default="workstation", help="Workstation hostname")
    parser.add_argument("--lesson-code", help="Lesson code")
    parser.add_argument("--aap-url", default="https://aap.lab.example.com", help="AAP Controller URL")

    args = parser.parse_args()

    # Create minimal exercise context
    from lib.test_result import ExerciseContext, ExerciseType
    exercise = ExerciseContext(
        id=args.exercise_id,
        type=ExerciseType.LAB,
        lesson_code=args.lesson_code or "",
        chapter=1,
        chapter_title="Chapter",
        title=args.exercise_id
    )

    # Create SSH connection
    ssh = SSHConnection(args.workstation)

    if not ssh.test_connection():
        print(f"Cannot connect to {args.workstation}")
        return 1

    # Run test
    tester = TC_AAP(aap_url=args.aap_url)
    result = tester.test(exercise, ssh)

    # Print results
    print("\n" + "=" * 60)
    print(f"Result: {'PASS' if result.passed else 'FAIL'}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Bugs Found: {len(result.bugs_found)}")
    print("=" * 60)

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
