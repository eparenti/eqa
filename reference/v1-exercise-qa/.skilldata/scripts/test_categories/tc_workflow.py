#!/usr/bin/env python3
"""
TC-WORKFLOW: Automated EPUB Workflow Execution

Executes complete EPUB workflows automatically on live systems and validates
each step succeeds. This is the primary execution test that simulates the
student experience.

Key differences from TC-EXEC:
- TC-EXEC: Pre-flight validation (syntax, safety) - does NOT execute
- TC-WORKFLOW: Full workflow execution on live systems

This test category:
1. Runs all EPUB steps in sequence on the lab environment
2. Validates each step completes successfully
3. Captures state changes and outputs
4. Reports execution failures with context
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.test_result import TestResult, ExerciseContext, Bug, BugSeverity
from lib.ssh_connection import SSHConnection
from test_executor import TestExecutor


class TC_WORKFLOW:
    """
    Test Category: Automated Workflow Execution

    Executes ALL EPUB steps automatically on live systems and validates
    each step succeeds. This simulates the complete student experience.
    """

    def __init__(self):
        """Initialize workflow tester."""
        pass

    def test(
        self,
        exercise: ExerciseContext,
        ssh_or_executor,
        epub_workflow: Dict = None
    ) -> TestResult:
        """
        Execute complete EPUB workflow automatically.

        Args:
            exercise: Exercise context
            ssh_or_executor: Either SSHConnection or TestExecutor instance
            epub_workflow: Parsed EPUB workflow (optional, uses exercise.epub_workflow)

        Returns:
            TestResult with workflow execution results
        """
        start_time = datetime.now()

        # Get executor - accept both SSH connection and TestExecutor for flexibility
        if isinstance(ssh_or_executor, TestExecutor):
            executor = ssh_or_executor
        elif isinstance(ssh_or_executor, SSHConnection):
            executor = TestExecutor(ssh_or_executor.hostname)
        else:
            # Assume it's a hostname string
            executor = TestExecutor(str(ssh_or_executor))

        # Get workflow from parameter or exercise context
        workflow = epub_workflow or getattr(exercise, 'epub_workflow', None)

        if not workflow:
            # No workflow to execute
            return TestResult(
                category="TC-WORKFLOW",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=0.0,
                bugs_found=[],
                details={'message': 'No workflow to execute'},
                summary="No workflow available for execution"
            )

        # Execute the workflow using TestExecutor
        try:
            result = executor.execute_workflow(exercise.id, workflow)

            # Enhance result with TC-WORKFLOW category
            result.category = "TC-WORKFLOW"

            return result

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return TestResult(
                category="TC-WORKFLOW",
                exercise_id=exercise.id,
                passed=False,
                timestamp=datetime.now().isoformat(),
                duration_seconds=duration,
                bugs_found=[
                    Bug(
                        id=f"BUG-WORKFLOW-{exercise.id}-EXEC-FAIL",
                        severity=BugSeverity.P0_BLOCKER,
                        exercise_id=exercise.id,
                        category="TC-WORKFLOW",
                        description=f"Workflow execution failed: {str(e)}",
                        fix_recommendation="Review exercise configuration and lab connectivity",
                        verification_steps=[
                            "Verify SSH connectivity to workstation",
                            "Check lab environment is running",
                            "Review workflow JSON structure"
                        ]
                    )
                ],
                details={
                    'error': str(e),
                    'error_type': type(e).__name__
                },
                summary=f"Workflow execution failed: {str(e)[:50]}"
            )


def main():
    """Test TC_WORKFLOW functionality."""
    import argparse
    import json
    from lib.test_result import ExerciseType

    parser = argparse.ArgumentParser(description="Test automated workflow execution")
    parser.add_argument("exercise_id", help="Exercise ID")
    parser.add_argument("--workflow", "-w", required=True, help="Path to workflow JSON")
    parser.add_argument("--workstation", default="workstation", help="Workstation hostname")

    args = parser.parse_args()

    # Load workflow
    with open(args.workflow, 'r') as f:
        workflow = json.load(f)

    # Create exercise context
    exercise = ExerciseContext(
        id=args.exercise_id,
        type=ExerciseType.GUIDED_EXERCISE,
        lesson_code="test",
        chapter=1,
        chapter_title="Test",
        title=args.exercise_id
    )

    # Create executor
    executor = TestExecutor(args.workstation)

    if not executor.test_connection():
        print("Cannot connect to workstation")
        return 1

    # Run test
    tester = TC_WORKFLOW()
    result = tester.test(exercise, executor, workflow)

    print("\n" + "=" * 60)
    print(f"Result: {'PASS' if result.passed else 'FAIL'}")
    print(f"Summary: {result.summary}")
    print(f"Duration: {result.duration_seconds:.2f}s")

    if result.details.get('steps_passed') is not None:
        print(f"Steps: {result.details.get('steps_passed', 0)}/{result.details.get('total_steps', 0)} passed")

    if result.bugs_found:
        print(f"\nBugs Found ({len(result.bugs_found)}):")
        for bug in result.bugs_found:
            print(f"  [{bug.severity.value}] {bug.description}")

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
