#!/usr/bin/env python3
"""
Validate Lab grading scripts for accuracy.

Tests three critical scenarios:
1. WITH solution applied → grading MUST pass (100%)
2. WITHOUT solution → grading MUST fail
3. WITH partial solution → grading MUST fail gracefully with clear messages

This catches:
- False positives (grading passes when it shouldn't)
- False negatives (grading fails when it shouldn't)
- Unclear error messages
- Missing grading checks
"""

import subprocess
import json
import sys
from pathlib import Path


def run_grading(exercise_name, workstation="workstation"):
    """
    Run lab grade and parse results.

    Returns:
        dict: {
            'passed': bool,
            'total_checks': int,
            'passed_checks': int,
            'failed_checks': int,
            'messages': list
        }
    """
    cmd = f'ssh {workstation} "lab grade {exercise_name}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    output = result.stdout + result.stderr

    # Parse grading output
    passed = result.returncode == 0
    checks_passed = output.count("SUCCESS")
    checks_failed = output.count("FAIL")
    total_checks = checks_passed + checks_failed

    # Extract messages
    messages = []
    for line in output.split('\n'):
        if "SUCCESS" in line or "FAIL" in line:
            messages.append(line.strip())

    return {
        'passed': passed,
        'total_checks': total_checks,
        'passed_checks': checks_passed,
        'failed_checks': checks_failed,
        'messages': messages,
        'raw_output': output
    }


def test_grading_with_solution(exercise_name, solution_file, workstation="workstation"):
    """
    Scenario 1: Test grading WITH solution applied.
    Expected: 100% pass rate
    """
    print(f"\n🧪 Scenario 1: Testing grading WITH solution...")

    # Apply solution
    cmd = f'ssh {workstation} "cd ~/{exercise_name} && cp {solution_file} $(basename {solution_file} .sol) && ansible-navigator run $(basename {solution_file} .sol) -m stdout"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"   ❌ Solution failed to execute")
        return {'error': 'Solution execution failed', 'details': result.stderr}

    # Run grading
    grading = run_grading(exercise_name, workstation)

    # Validate
    if grading['passed'] and grading['failed_checks'] == 0:
        print(f"   ✅ PASS: Grading passed with solution ({grading['passed_checks']}/{grading['total_checks']})")
        return {'status': 'PASS', 'grading': grading}
    else:
        print(f"   ❌ FAIL: Grading should pass with solution but got {grading['passed_checks']}/{grading['total_checks']}")
        print(f"   🐛 FALSE NEGATIVE detected!")
        return {'status': 'FAIL', 'issue': 'false_negative', 'grading': grading}


def test_grading_without_solution(exercise_name, workstation="workstation"):
    """
    Scenario 2: Test grading WITHOUT solution.
    Expected: Should fail with clear messages
    """
    print(f"\n🧪 Scenario 2: Testing grading WITHOUT solution...")

    # Reset lab
    subprocess.run(f'ssh {workstation} "lab finish {exercise_name} && lab start {exercise_name}"',
                   shell=True, capture_output=True)

    # Run grading
    grading = run_grading(exercise_name, workstation)

    # Validate
    if not grading['passed'] and grading['failed_checks'] > 0:
        print(f"   ✅ PASS: Grading correctly failed ({grading['failed_checks']} checks failed)")
        return {'status': 'PASS', 'grading': grading}
    else:
        print(f"   ❌ FAIL: Grading should fail without solution but passed!")
        print(f"   🐛 FALSE POSITIVE detected!")
        return {'status': 'FAIL', 'issue': 'false_positive', 'grading': grading}


def test_grading_messages(exercise_name, workstation="workstation"):
    """
    Scenario 3: Test grading message clarity.
    Expected: Clear, actionable error messages
    """
    print(f"\n🧪 Scenario 3: Testing grading message clarity...")

    # Run grading without solution
    grading = run_grading(exercise_name, workstation)

    # Analyze messages
    issues = []
    for msg in grading['messages']:
        if "FAIL" in msg:
            # Check if message is actionable
            if not any(word in msg.lower() for word in ['not', 'missing', 'incorrect', 'should', 'must']):
                issues.append(f"Unclear message: {msg}")

    if not issues:
        print(f"   ✅ PASS: All grading messages are clear")
        return {'status': 'PASS', 'messages': grading['messages']}
    else:
        print(f"   ⚠️  WARNING: Some messages could be clearer")
        for issue in issues:
            print(f"      • {issue}")
        return {'status': 'WARNING', 'issues': issues, 'messages': grading['messages']}


def validate_lab_grading(exercise_name, solution_file, workstation="workstation", output_file=None):
    """
    Complete grading validation workflow.

    Args:
        exercise_name: Lab name (e.g., '<exercise-name>')
        solution_file: Path to solution file (e.g., 'solutions/web_dev_server.yml.sol')
        workstation: SSH host
        output_file: Optional JSON output file

    Returns:
        dict: Validation results
    """
    print(f"🔍 Validating Lab Grading: {exercise_name}")
    print("=" * 60)

    results = {
        'exercise': exercise_name,
        'scenarios': {}
    }

    # Scenario 1: With solution
    results['scenarios']['with_solution'] = test_grading_with_solution(
        exercise_name, solution_file, workstation
    )

    # Scenario 2: Without solution
    results['scenarios']['without_solution'] = test_grading_without_solution(
        exercise_name, workstation
    )

    # Scenario 3: Message clarity
    results['scenarios']['message_clarity'] = test_grading_messages(
        exercise_name, workstation
    )

    # Overall assessment
    critical_pass = (
        results['scenarios']['with_solution']['status'] == 'PASS' and
        results['scenarios']['without_solution']['status'] == 'PASS'
    )

    results['overall_status'] = 'PASS' if critical_pass else 'FAIL'

    # Report
    print("\n" + "=" * 60)
    print("📊 Grading Validation Summary")
    print("=" * 60)

    if results['overall_status'] == 'PASS':
        print("✅ GRADING SCRIPT VALIDATED")
        print("   • No false positives detected")
        print("   • No false negatives detected")
    else:
        print("❌ GRADING SCRIPT HAS ISSUES")
        if results['scenarios']['with_solution'].get('issue') == 'false_negative':
            print("   🐛 FALSE NEGATIVE: Grading fails with correct solution")
        if results['scenarios']['without_solution'].get('issue') == 'false_positive':
            print("   🐛 FALSE POSITIVE: Grading passes without solution")

    # Save results
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to: {output_file}")

    return results


def main():
    """CLI interface."""
    if len(sys.argv) < 3:
        print("Usage: validate_grading.py <exercise_name> <solution_file> [workstation] [output.json]")
        print("\nExample:")
        print("  validate_grading.py <exercise-name> solutions/web_dev_server.yml.sol workstation results.json")
        sys.exit(1)

    exercise_name = sys.argv[1]
    solution_file = sys.argv[2]
    workstation = sys.argv[3] if len(sys.argv) > 3 else "workstation"
    output_file = sys.argv[4] if len(sys.argv) > 4 else None

    results = validate_lab_grading(exercise_name, solution_file, workstation, output_file)

    sys.exit(0 if results['overall_status'] == 'PASS' else 1)


if __name__ == "__main__":
    main()
