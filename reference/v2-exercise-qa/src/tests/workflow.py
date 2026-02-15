"""TC-WORKFLOW: Workflow automation testing.

Tests that workflow playbooks automate the full student experience:
- Workflow playbook exists
- Executes start -> work -> verify -> cleanup cycle
- Properly simulates student workflow
- All steps execute successfully
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext
from ..clients.ssh import SSHConnection


class TC_WORKFLOW:
    """Workflow automation test category."""

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test workflow automation.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-WORKFLOW: Testing workflow automation...")

        bugs_found = []
        start_time = datetime.now()

        # Find workflow playbook
        workflow_playbook = self._find_workflow_playbook(exercise)
        if not workflow_playbook:
            # Workflow automation is optional - not finding one is not an error
            print(f"   ⏭  No workflow playbook found (optional)")
            duration = (datetime.now() - start_time).total_seconds()
            return TestResult(
                category="TC-WORKFLOW",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=duration,
                bugs_found=[],
                details={'status': 'skipped', 'reason': 'no_workflow_playbook'}
            )

        print(f"   Found workflow playbook: {workflow_playbook.name}")

        # Test workflow execution
        self._test_workflow_execution(exercise, workflow_playbook, ssh, bugs_found)

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-WORKFLOW",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'workflow_playbook': str(workflow_playbook) if workflow_playbook else None
            }
        )

    def _find_workflow_playbook(self, exercise: ExerciseContext) -> Optional[Path]:
        """Find workflow playbook for exercise."""
        if not exercise.materials_dir:
            return None

        # Common workflow playbook names
        candidates = [
            exercise.materials_dir / "workflow.yml",
            exercise.materials_dir / "workflow.yaml",
            exercise.materials_dir / "playbook-workflow.yml",
            exercise.materials_dir / "playbook-workflow.yaml",
            exercise.materials_dir / "test-workflow.yml",
            exercise.materials_dir / "test-workflow.yaml",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None

    def _test_workflow_execution(self, exercise: ExerciseContext,
                                 workflow_playbook: Path, ssh: SSHConnection,
                                 bugs_found: List[Bug]):
        """Test workflow playbook execution."""

        print(f"   → Executing workflow playbook...")

        # Run workflow playbook
        workflow_cmd = f"cd {exercise.materials_dir} && ansible-navigator run {workflow_playbook.name} -m stdout"
        result = ssh.run(workflow_cmd, timeout=600)  # Workflows can be long

        if result.exit_code != 0:
            bugs_found.append(Bug(
                id=f"WORKFLOW-EXEC-FAIL-001-{exercise.id}",
                severity=BugSeverity.P2_HIGH,
                category="TC-WORKFLOW",
                exercise_id=exercise.id,
                description="Workflow playbook execution failed",
                fix_recommendation=f"Fix workflow playbook: {result.stderr[:200]}"
            ))
            return

        # Check for common workflow markers in output
        workflow_steps = {
            'start': False,
            'solution': False,
            'verify': False,
            'cleanup': False
        }

        output_lower = result.stdout.lower()

        # Detect workflow steps
        if 'start' in output_lower or 'setup' in output_lower:
            workflow_steps['start'] = True

        if 'solution' in output_lower or 'solve' in output_lower:
            workflow_steps['solution'] = True

        if 'verify' in output_lower or 'check' in output_lower:
            workflow_steps['verify'] = True

        if 'cleanup' in output_lower or 'finish' in output_lower:
            workflow_steps['cleanup'] = True

        # Check if workflow seems complete
        complete_steps = sum(workflow_steps.values())

        if complete_steps >= 2:  # At least 2 workflow steps detected
            print(f"      ✓ Workflow executed successfully ({complete_steps}/4 steps detected)")
        else:
            bugs_found.append(Bug(
                id=f"WORKFLOW-INCOMPLETE-001-{exercise.id}",
                severity=BugSeverity.P3_LOW,
                category="TC-WORKFLOW",
                exercise_id=exercise.id,
                description=f"Workflow may be incomplete (only {complete_steps}/4 steps detected)",
                fix_recommendation="Verify workflow includes: start, solution, verify, cleanup steps"
            ))
