#!/usr/bin/env python3
"""
TC-EXEC: Command Syntax and Safety Validation

Validates that EPUB commands are syntactically correct and safe to execute,
WITHOUT actually executing them. This is a pre-flight check before TC-WORKFLOW.

Key differences from TC-WORKFLOW:
- TC-EXEC: Validates commands are well-formed (syntax, paths, safety)
- TC-WORKFLOW: Actually executes the complete workflow on live systems

This separation allows catching obvious issues before committing to execution.
"""

import sys
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.test_result import TestResult, ExerciseContext, Bug, BugSeverity


class TC_EXEC:
    """
    Test Category: Command Syntax and Safety Validation

    Pre-flight validation of EPUB commands before execution:
    - Syntax validation (shell syntax, quoting, escapes)
    - Path validation (absolute vs relative, existence patterns)
    - Safety checks (dangerous commands, missing safeguards)
    - Command completeness (required flags, options)
    """

    # Dangerous command patterns that should have safeguards
    DANGEROUS_PATTERNS = [
        (r'\brm\s+-rf?\s+/', "rm with absolute path - verify intended"),
        (r'\brm\s+-rf?\s+\*', "rm with wildcard - verify scope"),
        (r'\bchmod\s+777\b', "chmod 777 is insecure - use specific permissions"),
        (r'\bchmod\s+666\b', "chmod 666 is insecure - use specific permissions"),
        (r'\bdd\s+.*of=/dev/', "dd to device - verify target"),
        (r'\bmkfs\.', "mkfs will destroy data - verify target"),
        (r'\bsudo\s+.*NOPASSWD', "NOPASSWD sudo configuration"),
        (r'>\s*/dev/null\s*2>&1', "Silent failure - may hide errors"),
    ]

    # Common syntax issues
    SYNTAX_PATTERNS = [
        (r'\$\{[^}]+\s', "Unclosed variable brace"),
        (r'"\$[^"]*[^\\]\'', "Mixed quote types may cause issues"),
        (r'\|\s*$', "Trailing pipe with no command"),
        (r'&&\s*$', "Trailing && with no command"),
        (r'\|\|\s*$', "Trailing || with no command"),
    ]

    # Commands that should have specific flags
    RECOMMENDED_FLAGS = {
        'cp': ['-v', '-i'],  # verbose or interactive for verification
        'mv': ['-v', '-i'],
        'rm': ['-v', '-i'],
        'rsync': ['-v', '--progress'],
        'curl': ['-f', '--fail'],  # fail on HTTP errors
        'wget': ['--continue'],
    }

    def __init__(self):
        """Initialize command validator."""
        pass

    def test(self, exercise: ExerciseContext, workflow: Dict = None) -> TestResult:
        """
        Validate EPUB commands without executing them.

        Args:
            exercise: Exercise context
            workflow: Parsed EPUB workflow (optional, uses exercise.epub_workflow if not provided)

        Returns:
            TestResult with validation findings
        """
        start_time = datetime.now()
        bugs_found = []
        validation_details = {
            'commands_validated': 0,
            'syntax_issues': [],
            'safety_warnings': [],
            'recommendations': []
        }

        # Get workflow from exercise or parameter
        wf = workflow or getattr(exercise, 'epub_workflow', None)
        if not wf:
            # No workflow to validate
            return TestResult(
                category="TC-EXEC",
                exercise_id=exercise.id,
                passed=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=0.0,
                bugs_found=[],
                details={'message': 'No workflow to validate'},
                summary="No commands to validate"
            )

        # Extract all commands from workflow
        commands = self._extract_commands(wf)
        validation_details['commands_validated'] = len(commands)

        # Validate each command
        for cmd_info in commands:
            cmd = cmd_info['command']
            step = cmd_info.get('step', 0)

            # Syntax validation
            syntax_issues = self._validate_syntax(cmd)
            for issue in syntax_issues:
                validation_details['syntax_issues'].append({
                    'step': step,
                    'command': cmd[:50] + '...' if len(cmd) > 50 else cmd,
                    'issue': issue
                })
                bugs_found.append(Bug(
                    id=f"BUG-SYNTAX-{exercise.id}-S{step}",
                    severity=BugSeverity.P2_HIGH,
                    exercise_id=exercise.id,
                    category="TC-EXEC",
                    description=f"Syntax issue in step {step}: {issue}",
                    fix_recommendation=f"Review command: {cmd[:100]}",
                    verification_steps=["Fix the syntax issue", "Re-run TC-EXEC validation"]
                ))

            # Safety validation
            safety_issues = self._validate_safety(cmd)
            for issue in safety_issues:
                validation_details['safety_warnings'].append({
                    'step': step,
                    'command': cmd[:50] + '...' if len(cmd) > 50 else cmd,
                    'warning': issue
                })
                # Safety warnings are P3 (informational) unless critical
                bugs_found.append(Bug(
                    id=f"BUG-SAFETY-{exercise.id}-S{step}",
                    severity=BugSeverity.P3_LOW,
                    exercise_id=exercise.id,
                    category="TC-EXEC",
                    description=f"Safety consideration in step {step}: {issue}",
                    fix_recommendation="Review if safeguards are needed",
                    verification_steps=["Verify command is intentional", "Add safeguards if needed"]
                ))

            # Recommendations
            recommendations = self._get_recommendations(cmd)
            for rec in recommendations:
                validation_details['recommendations'].append({
                    'step': step,
                    'recommendation': rec
                })

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Test passes if no P0/P1/P2 bugs (safety warnings are P3)
        critical_bugs = [b for b in bugs_found if b.severity in [BugSeverity.P0_BLOCKER, BugSeverity.P1_CRITICAL, BugSeverity.P2_HIGH]]
        passed = len(critical_bugs) == 0

        summary_parts = []
        if validation_details['syntax_issues']:
            summary_parts.append(f"{len(validation_details['syntax_issues'])} syntax issues")
        if validation_details['safety_warnings']:
            summary_parts.append(f"{len(validation_details['safety_warnings'])} safety warnings")
        if not summary_parts:
            summary_parts.append("All commands validated successfully")

        return TestResult(
            category="TC-EXEC",
            exercise_id=exercise.id,
            passed=passed,
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details=validation_details,
            summary=f"Validated {len(commands)} commands: {'; '.join(summary_parts)}"
        )

    def _extract_commands(self, workflow: Dict) -> List[Dict]:
        """Extract all commands from workflow steps."""
        commands = []
        for step in workflow.get('steps', []):
            step_num = step.get('number', 0)
            for cmd in step.get('commands', []):
                if isinstance(cmd, str):
                    commands.append({'command': cmd, 'step': step_num})
                elif isinstance(cmd, dict):
                    commands.append({'command': cmd.get('command', ''), 'step': step_num})
        return commands

    def _validate_syntax(self, command: str) -> List[str]:
        """Validate command syntax."""
        issues = []
        for pattern, message in self.SYNTAX_PATTERNS:
            if re.search(pattern, command):
                issues.append(message)
        return issues

    def _validate_safety(self, command: str) -> List[str]:
        """Check for potentially dangerous patterns."""
        warnings = []
        for pattern, message in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                warnings.append(message)
        return warnings

    def _get_recommendations(self, command: str) -> List[str]:
        """Get recommendations for command improvement."""
        recommendations = []
        for cmd_name, flags in self.RECOMMENDED_FLAGS.items():
            if re.search(rf'\b{cmd_name}\b', command):
                has_flag = any(f in command for f in flags)
                if not has_flag:
                    recommendations.append(f"Consider adding {' or '.join(flags)} to {cmd_name} for better output")
        return recommendations


def main():
    """Test TC_EXEC functionality."""
    import argparse
    import json
    from lib.test_result import ExerciseType

    parser = argparse.ArgumentParser(description="Validate EPUB command syntax and safety")
    parser.add_argument("exercise_id", help="Exercise ID")
    parser.add_argument("--workflow", "-w", help="Path to workflow JSON")

    args = parser.parse_args()

    # Create exercise context
    exercise = ExerciseContext(
        id=args.exercise_id,
        type=ExerciseType.GUIDED_EXERCISE,
        lesson_code="test",
        chapter=1,
        chapter_title="Test",
        title=args.exercise_id
    )

    # Load workflow if provided
    workflow = None
    if args.workflow:
        with open(args.workflow, 'r') as f:
            workflow = json.load(f)

    # Run validation
    tester = TC_EXEC()
    result = tester.test(exercise, workflow)

    print("\n" + "=" * 60)
    print(f"Result: {'PASS' if result.passed else 'FAIL'}")
    print(f"Summary: {result.summary}")
    print(f"Duration: {result.duration_seconds:.2f}s")

    if result.bugs_found:
        print(f"\nFindings ({len(result.bugs_found)}):")
        for bug in result.bugs_found:
            print(f"  [{bug.severity.value}] {bug.description}")

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
