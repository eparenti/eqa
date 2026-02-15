"""TC-PERF: Performance validation.

Tests exercise performance:
- Lab start/finish within time budgets
- Solution execution time
- Grading time
- Identifies slow operations
"""

from datetime import datetime
from typing import List, Dict, Optional
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext, ExerciseType
from ..clients.ssh import SSHConnection


class TC_PERF:
    """Performance validation test category."""

    # Time budgets in seconds
    TIME_BUDGETS = {
        'lab_start': 60,       # 1 minute for lab start
        'lab_finish': 60,      # 1 minute for lab finish
        'lab_grade': 30,       # 30 seconds for grading
        'solution_apply': 120, # 2 minutes for solution
        'playbook_run': 180,   # 3 minutes for playbook
    }

    # Warning thresholds (percentage of budget)
    WARNING_THRESHOLD = 0.75  # Warn at 75% of budget

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test exercise performance against time budgets.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-PERF: Testing performance...")

        bugs_found = []
        start_time = datetime.now()
        timings = {}

        # Test lab start performance
        print("   → Testing lab start performance...")
        start_timing = self._time_command(
            f"lab start {exercise.lab_name}",
            ssh,
            timeout=self.TIME_BUDGETS['lab_start'] + 30
        )
        timings['lab_start'] = start_timing

        if start_timing['success']:
            budget = self.TIME_BUDGETS['lab_start']
            duration = start_timing['duration']

            if duration > budget:
                bugs_found.append(Bug(
                    id=f"PERF-START-SLOW-{exercise.id}",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-PERF",
                    exercise_id=exercise.id,
                    description=f"Lab start exceeded time budget: {duration:.1f}s > {budget}s",
                    fix_recommendation="Optimize lab start script - reduce setup operations",
                    verification_steps=[
                        f"Profile: time lab start {exercise.lab_name}",
                        "Identify slow operations"
                    ]
                ))
            elif duration > budget * self.WARNING_THRESHOLD:
                bugs_found.append(Bug(
                    id=f"PERF-START-WARN-{exercise.id}",
                    severity=BugSeverity.P3_LOW,
                    category="TC-PERF",
                    exercise_id=exercise.id,
                    description=f"Lab start approaching time budget: {duration:.1f}s (budget: {budget}s)",
                    fix_recommendation="Consider optimizing lab start script",
                    verification_steps=[
                        f"Profile: time lab start {exercise.lab_name}",
                        "Look for optimization opportunities"
                    ]
                ))
            else:
                print(f"      ✓ Lab start: {duration:.1f}s (budget: {budget}s)")

        # Test solution/playbook performance (if applicable)
        if exercise.solution_files and exercise.type == ExerciseType.LAB:
            print("   → Testing solution performance...")

            for sol_file in exercise.solution_files:
                if sol_file.suffix in ['.yml', '.yaml']:
                    sol_timing = self._time_playbook(sol_file, exercise, ssh)
                    timings[f'solution_{sol_file.stem}'] = sol_timing

                    if sol_timing['success']:
                        budget = self.TIME_BUDGETS['playbook_run']
                        duration = sol_timing['duration']

                        if duration > budget:
                            bugs_found.append(Bug(
                                id=f"PERF-SOL-SLOW-{sol_file.stem}-{exercise.id}",
                                severity=BugSeverity.P2_HIGH,
                                category="TC-PERF",
                                exercise_id=exercise.id,
                                description=f"Solution playbook exceeded time budget: {duration:.1f}s > {budget}s",
                                fix_recommendation="Optimize playbook - use async, reduce loops",
                                verification_steps=[
                                    f"Profile: time ansible-playbook {sol_file.name}",
                                    "Use callback plugins for task timing"
                                ]
                            ))
                        else:
                            print(f"      ✓ Solution {sol_file.stem}: {duration:.1f}s (budget: {budget}s)")

        # Test grading performance (if applicable)
        if exercise.type == ExerciseType.LAB and exercise.grading_script:
            print("   → Testing grading performance...")
            grade_timing = self._time_command(
                f"lab grade {exercise.lab_name}",
                ssh,
                timeout=self.TIME_BUDGETS['lab_grade'] + 30
            )
            timings['lab_grade'] = grade_timing

            if grade_timing['success']:
                budget = self.TIME_BUDGETS['lab_grade']
                duration = grade_timing['duration']

                if duration > budget:
                    bugs_found.append(Bug(
                        id=f"PERF-GRADE-SLOW-{exercise.id}",
                        severity=BugSeverity.P2_HIGH,
                        category="TC-PERF",
                        exercise_id=exercise.id,
                        description=f"Grading exceeded time budget: {duration:.1f}s > {budget}s",
                        fix_recommendation="Optimize grading script - reduce checks or parallelize",
                        verification_steps=[
                            f"Profile: time lab grade {exercise.lab_name}",
                            "Identify slow grading checks"
                        ]
                    ))
                else:
                    print(f"      ✓ Grading: {duration:.1f}s (budget: {budget}s)")

        # Test lab finish performance
        print("   → Testing lab finish performance...")
        finish_timing = self._time_command(
            f"lab finish {exercise.lab_name}",
            ssh,
            timeout=self.TIME_BUDGETS['lab_finish'] + 30
        )
        timings['lab_finish'] = finish_timing

        if finish_timing['success']:
            budget = self.TIME_BUDGETS['lab_finish']
            duration = finish_timing['duration']

            if duration > budget:
                bugs_found.append(Bug(
                    id=f"PERF-FINISH-SLOW-{exercise.id}",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-PERF",
                    exercise_id=exercise.id,
                    description=f"Lab finish exceeded time budget: {duration:.1f}s > {budget}s",
                    fix_recommendation="Optimize lab finish script - reduce cleanup operations",
                    verification_steps=[
                        f"Profile: time lab finish {exercise.lab_name}",
                        "Identify slow cleanup operations"
                    ]
                ))
            else:
                print(f"      ✓ Lab finish: {duration:.1f}s (budget: {budget}s)")

        # Calculate total time
        total_time = sum(t.get('duration', 0) for t in timings.values() if t.get('success'))

        if len(bugs_found) == 0:
            print(f"      ✓ All operations within budget (total: {total_time:.1f}s)")

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-PERF",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'timings': {k: {'duration': v.get('duration', 0), 'success': v.get('success', False)}
                           for k, v in timings.items()},
                'total_time': total_time,
                'budgets': self.TIME_BUDGETS
            }
        )

    def _time_command(self, command: str, ssh: SSHConnection, timeout: int) -> Dict:
        """Time a command execution.

        Returns:
            Dict with 'success', 'duration', 'output'
        """
        start = datetime.now()
        result = ssh.run(command, timeout=timeout)
        duration = (datetime.now() - start).total_seconds()

        return {
            'success': result.success,
            'duration': duration,
            'output': result.stdout[:500] if result.stdout else '',
            'error': result.stderr[:200] if result.stderr else ''
        }

    def _time_playbook(self, playbook_path, exercise: ExerciseContext,
                       ssh: SSHConnection) -> Dict:
        """Time a playbook execution.

        Returns:
            Dict with 'success', 'duration', 'output'
        """
        base_id = exercise.id.removesuffix('-ge').removesuffix('-lab')

        # Build playbook command
        if exercise.materials_dir:
            work_dir = f"/home/student/{base_id}"
            playbook_name = playbook_path.name

            # Check if playbook exists on remote
            check = ssh.run(f"test -f {work_dir}/{playbook_name}", timeout=5)
            if not check.success:
                # Try to copy solution
                sol_path = exercise.materials_dir / "solutions" / playbook_name
                if sol_path.exists():
                    ssh.run(f"cp {sol_path} {work_dir}/", timeout=10)

            command = f"cd {work_dir} && ansible-playbook {playbook_name}"
        else:
            command = f"ansible-playbook {playbook_path}"

        return self._time_command(command, ssh, timeout=self.TIME_BUDGETS['playbook_run'] + 60)
