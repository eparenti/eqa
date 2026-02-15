#!/usr/bin/env python3
"""
TC-VERIFY: Verification Testing

Tests that students can verify their work after completing an exercise.

For Guided Exercises:
- Execute verification steps from EPUB
- Run verification scripts/playbooks if provided
- Validate expected outputs match actual state

This test category ensures students know when they've completed
the exercise correctly.
"""

import sys
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.test_result import TestResult, Bug, BugSeverity, ExerciseContext
from lib.ssh_connection import SSHConnection


class TC_VERIFY:
    """
    Verification testing for guided exercises.

    Tests that students can verify their completion.
    """

    def __init__(self):
        """Initialize verification tester."""
        pass

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test verification procedures.

        Args:
            exercise: Exercise context
            ssh: SSH connection to workstation

        Returns:
            TestResult with verification test results
        """
        start_time = datetime.now()
        bugs_found = []
        test_details = {
            'verification_steps': [],
            'scripts_found': [],
            'playbooks_found': []
        }

        print(f"\n🔍 TC-VERIFY: Verification Testing")
        print("=" * 60)

        # Check for verification in EPUB
        verification_steps = self._extract_verification_steps(exercise)
        test_details['verification_steps'] = verification_steps

        if verification_steps:
            print(f"  Found {len(verification_steps)} verification steps in EPUB")

            # Execute each verification step
            for i, step in enumerate(verification_steps, 1):
                print(f"\n  Step {i}: {step['description'][:60]}...")

                if step['commands']:
                    for cmd in step['commands']:
                        result = ssh.run(cmd, timeout=30)

                        if result['exit_code'] != 0:
                            bugs_found.append(Bug(
                                id=f"BUG-{exercise.id.upper()}-VERIFY-STEP{i}",
                                severity=BugSeverity.P2_HIGH,
                                exercise_id=exercise.id,
                                category="TC-VERIFY",
                                description=f"Verification step {i} failed: {cmd}",
                                fix_recommendation=(
                                    f"Review verification step {i} in EPUB:\n"
                                    f"Command: {cmd}\n"
                                    f"Error: {result['stderr']}\n\n"
                                    f"Either fix the exercise so verification passes, "
                                    f"or update verification steps in EPUB."
                                ),
                                verification_steps=[
                                    "1. Complete exercise solution",
                                    f"2. Run: {cmd}",
                                    "3. Verify command succeeds",
                                    "4. Update EPUB if needed"
                                ]
                            ))
                            print(f"    ❌ Failed: {cmd}")
                        else:
                            print(f"    ✅ Passed: {cmd}")

        # Check for verification scripts
        verify_scripts = self._find_verification_scripts(exercise)
        test_details['scripts_found'] = verify_scripts

        if verify_scripts:
            print(f"\n  Found {len(verify_scripts)} verification scripts")

            for script in verify_scripts:
                print(f"  Testing: {script}")

                # Determine how to run the script
                if script.endswith('.yml') or script.endswith('.yaml'):
                    # Ansible playbook
                    cmd = f"cd ~/DO{exercise.lesson_code.upper()}/labs/{exercise.id}/ && ansible-navigator run {script} -m stdout"
                elif script.endswith('.sh'):
                    # Shell script
                    cmd = f"cd ~/DO{exercise.lesson_code.upper()}/labs/{exercise.id}/ && bash {script}"
                else:
                    print(f"    ⚠️  Unknown script type: {script}")
                    continue

                result = ssh.run(cmd, timeout=120)

                if result['exit_code'] != 0:
                    bugs_found.append(Bug(
                        id=f"BUG-{exercise.id.upper()}-VERIFY-SCRIPT",
                        severity=BugSeverity.P1_CRITICAL,
                        exercise_id=exercise.id,
                        category="TC-VERIFY",
                        description=f"Verification script failed: {script}",
                        fix_recommendation=(
                            f"Fix verification script:\n"
                            f"Script: {script}\n"
                            f"Error: {result['stderr']}\n\n"
                            f"Ensure script correctly validates exercise completion."
                        ),
                        verification_steps=[
                            "1. Complete exercise solution",
                            f"2. Run: {cmd}",
                            "3. Fix script if incorrect",
                            "4. Verify script passes"
                        ]
                    ))
                    print(f"    ❌ Failed")
                else:
                    print(f"    ✅ Passed")

        # Check for playbook-based verification
        verify_playbooks = self._find_verification_playbooks(exercise)
        test_details['playbooks_found'] = verify_playbooks

        if verify_playbooks:
            print(f"\n  Found {len(verify_playbooks)} verification playbooks")

            for playbook in verify_playbooks:
                print(f"  Testing: {playbook}")

                cmd = f"ansible-navigator run {playbook} -m stdout"
                result = ssh.run(cmd, timeout=120)

                if result['exit_code'] != 0:
                    bugs_found.append(Bug(
                        id=f"BUG-{exercise.id.upper()}-VERIFY-PLAYBOOK",
                        severity=BugSeverity.P1_CRITICAL,
                        exercise_id=exercise.id,
                        category="TC-VERIFY",
                        description=f"Verification playbook failed: {playbook}",
                        fix_recommendation=(
                            f"Fix verification playbook:\n"
                            f"Playbook: {playbook}\n"
                            f"Error: {result['stderr']}\n\n"
                            f"Ensure playbook correctly validates exercise completion."
                        ),
                        verification_steps=[
                            "1. Complete exercise solution",
                            f"2. Run: {cmd}",
                            "3. Fix playbook if incorrect",
                            "4. Verify playbook passes"
                        ]
                    ))
                    print(f"    ❌ Failed")
                else:
                    print(f"    ✅ Passed")

        # Determine overall result
        total_verifications = len(verification_steps) + len(verify_scripts) + len(verify_playbooks)

        if total_verifications == 0:
            # No verification found - this is a P2 issue for GEs
            if exercise.type.value == "GE":
                bugs_found.append(Bug(
                    id=f"BUG-{exercise.id.upper()}-NO-VERIFY",
                    severity=BugSeverity.P2_HIGH,
                    exercise_id=exercise.id,
                    category="TC-VERIFY",
                    description="No verification mechanism found for Guided Exercise",
                    fix_recommendation=(
                        "Add verification steps or scripts:\n\n"
                        "Option 1: Add verification section to EPUB\n"
                        "Option 2: Create verify script/playbook\n"
                        "Option 3: Add verification steps to exercise instructions\n\n"
                        "Students need a way to confirm they completed the exercise correctly."
                    ),
                    verification_steps=[
                        "1. Choose verification approach (EPUB steps, script, or playbook)",
                        "2. Implement verification",
                        "3. Test verification with solution",
                        "4. Document in EPUB"
                    ]
                ))

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        passed = len(bugs_found) == 0

        return TestResult(
            category="TC-VERIFY",
            exercise_id=exercise.id,
            passed=passed,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details=test_details,
            summary=f"Tested {total_verifications} verification mechanisms, found {len(bugs_found)} issues"
        )

    def _extract_verification_steps(self, exercise: ExerciseContext) -> List[Dict]:
        """
        Extract verification steps from EPUB content.

        Returns:
            List of verification steps with commands
        """
        if not exercise.epub_content:
            return []

        steps = []

        # Look for "Verification" or "Verify" sections
        verification_patterns = [
            r'## Verification\s*\n(.*?)(?=\n##|\Z)',
            r'### Verify.*?\n(.*?)(?=\n##|\Z)',
            r'## Evaluation\s*\n(.*?)(?=\n##|\Z)',
            r'To verify.*?:(.*?)(?=\n##|\Z)'
        ]

        for pattern in verification_patterns:
            matches = re.finditer(pattern, exercise.epub_content, re.DOTALL | re.IGNORECASE)

            for match in matches:
                content = match.group(1)

                # Extract numbered steps
                step_pattern = r'(\d+)\.\s+(.+?)(?=\n\d+\.|\Z)'
                step_matches = re.finditer(step_pattern, content, re.DOTALL)

                for step_match in step_matches:
                    step_num = step_match.group(1)
                    step_text = step_match.group(2).strip()

                    # Extract commands from step
                    commands = self._extract_commands(step_text)

                    steps.append({
                        'number': int(step_num),
                        'description': step_text[:100],
                        'commands': commands
                    })

        return steps

    def _extract_commands(self, text: str) -> List[str]:
        """Extract command from text (look for code blocks or command markers)."""
        commands = []

        # Look for code blocks
        code_block_pattern = r'```(?:bash|shell)?\s*\n(.*?)\n```'
        code_blocks = re.finditer(code_block_pattern, text, re.DOTALL)

        for block in code_blocks:
            cmd = block.group(1).strip()
            if cmd and not cmd.startswith('#'):  # Skip comments
                commands.append(cmd)

        # Look for inline code with $ prefix
        inline_pattern = r'`\$\s*([^`]+)`'
        inline_commands = re.finditer(inline_pattern, text)

        for cmd_match in inline_commands:
            cmd = cmd_match.group(1).strip()
            if cmd:
                commands.append(cmd)

        return commands

    def _find_verification_scripts(self, exercise: ExerciseContext) -> List[str]:
        """Find verification scripts in exercise directory."""
        # Common verification script patterns
        patterns = [
            'verify.sh',
            'verify.yml',
            'verify.yaml',
            f'verify_{exercise.id}.sh',
            f'verify_{exercise.id}.yml'
        ]

        # In actual implementation, would check exercise directory
        # For now, return from exercise context if available
        return exercise.verification_scripts if hasattr(exercise, 'verification_scripts') else []

    def _find_verification_playbooks(self, exercise: ExerciseContext) -> List[str]:
        """Find verification playbooks in grading directory."""
        # In actual implementation, would look in grading/ansible directory
        # For now, return from exercise context if available
        return exercise.verification_playbooks if hasattr(exercise, 'verification_playbooks') else []


def main():
    """Test TC_VERIFY functionality."""
    import argparse

    parser = argparse.ArgumentParser(description="Test TC-VERIFY category")
    parser.add_argument("exercise_id", help="Exercise ID to test")
    parser.add_argument("--workstation", default="workstation", help="Workstation hostname")
    parser.add_argument("--lesson-code", help="Lesson code")

    args = parser.parse_args()

    # Create minimal exercise context
    from lib.test_result import ExerciseContext, ExerciseType
    exercise = ExerciseContext(
        id=args.exercise_id,
        type=ExerciseType.GUIDED_EXERCISE,
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
    tester = TC_VERIFY()
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
