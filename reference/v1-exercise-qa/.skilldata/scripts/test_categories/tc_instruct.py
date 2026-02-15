#!/usr/bin/env python3
"""
TC-INSTRUCT: Instruction Quality Analysis

Implements Guideline #3: Quality Focus
Analyzes instruction quality and suggests improvements (not just bugs).
"""

import sys
import re
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.test_result import TestResult, ExerciseContext, QualityIssue


class TC_INSTRUCT:
    """
    Test Category: Instruction Quality Analysis

    Analyzes clarity, completeness, progression, and formatting of instructions.
    Provides actionable suggestions for improvement.
    """

    def test(self, exercise: ExerciseContext, epub_content: str) -> TestResult:
        """
        Analyze instruction quality for exercise.

        Args:
            exercise: Exercise context
            epub_content: EPUB content text

        Returns:
            TestResult with quality analysis
        """
        start_time = datetime.now()

        print(f"\n📊 Analyzing instruction quality for {exercise.id}")

        issues = []
        score = 1.0  # Start at perfect score

        # Clarity analysis
        clarity_issues, clarity_penalty = self._analyze_clarity(exercise.id, epub_content)
        issues.extend(clarity_issues)
        score -= clarity_penalty

        # Completeness analysis
        completeness_issues, completeness_penalty = self._analyze_completeness(exercise.id, epub_content)
        issues.extend(completeness_issues)
        score -= completeness_penalty

        # Progression analysis
        progression_issues, progression_penalty = self._analyze_progression(exercise.id, epub_content)
        issues.extend(progression_issues)
        score -= progression_penalty

        # Formatting analysis
        formatting_issues, formatting_penalty = self._analyze_formatting(exercise.id, epub_content)
        issues.extend(formatting_issues)
        score -= formatting_penalty

        # Ensure score doesn't go negative
        score = max(0.0, min(1.0, score))

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        passed = (score >= 0.8)  # 80% quality threshold

        if passed:
            print(f"  ✅ Quality score: {score:.2f} ({len(issues)} suggestions)")
        else:
            print(f"  ⚠️  Quality score: {score:.2f} ({len(issues)} issues found)")

        return TestResult(
            category="TC-INSTRUCT",
            exercise_id=exercise.id,
            passed=passed,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            details={
                'quality_score': score,
                'total_issues': len(issues),
                'issues_by_type': self._count_issues_by_type(issues),
                'issues': [self._quality_issue_to_dict(issue) for issue in issues]
            }
        )

    def _analyze_clarity(self, exercise_id: str, content: str) -> Tuple[List[QualityIssue], float]:
        """Analyze clarity of instructions."""
        issues = []
        penalty = 0.0

        # Check average sentence length
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if s.strip()]

        if sentences:
            avg_words = sum(len(s.split()) for s in sentences) / len(sentences)

            if avg_words > 30:
                issues.append(QualityIssue(
                    exercise_id=exercise_id,
                    issue_type='clarity',
                    description=f'Average sentence length is {avg_words:.1f} words (>30)',
                    suggestion='Break long sentences into shorter ones for better readability',
                    severity='minor'
                ))
                penalty += 0.05

        # Check for unexplained technical terms
        technical_terms = ['ansible', 'playbook', 'yaml', 'inventory', 'variable', 'module']
        content_lower = content.lower()

        for term in technical_terms:
            if term in content_lower:
                # Check if term is explained (appears near words like "is", "means", "refers to")
                explanation_pattern = rf'{term}\s+(is|means|refers to|represents)'
                if not re.search(explanation_pattern, content_lower):
                    # Only flag if it's early in content (first 500 chars)
                    if content_lower.find(term) < 500:
                        issues.append(QualityIssue(
                            exercise_id=exercise_id,
                            issue_type='clarity',
                            description=f'Technical term "{term}" may need explanation',
                            suggestion=f'Consider briefly explaining "{term}" on first use',
                            severity='minor'
                        ))
                        penalty += 0.02
                        break  # Only flag once

        return issues, penalty

    def _analyze_completeness(self, exercise_id: str, content: str) -> Tuple[List[QualityIssue], float]:
        """Analyze completeness of instructions."""
        issues = []
        penalty = 0.0

        # Check for objectives
        has_objectives = bool(re.search(r'(objective|goal|purpose|you will|in this)', content, re.I))

        if not has_objectives and len(content) > 1000:
            issues.append(QualityIssue(
                exercise_id=exercise_id,
                issue_type='completeness',
                description='No clear learning objectives stated',
                suggestion='Add learning objectives at the beginning (e.g., "In this exercise, you will...")',
                severity='moderate'
            ))
            penalty += 0.15

        # Check for verification steps
        has_verification = bool(re.search(r'(verify|check|confirm|ensure|validate)', content, re.I))

        if not has_verification:
            issues.append(QualityIssue(
                exercise_id=exercise_id,
                issue_type='completeness',
                description='No verification steps detected',
                suggestion='Add steps to verify exercise completion',
                severity='moderate'
            ))
            penalty += 0.15

        # Check for examples
        has_examples = bool(re.search(r'(example|for instance|such as)', content, re.I))
        has_code = bool(re.search(r'```|`|\$|#', content))

        if not has_examples and not has_code and len(content) > 1500:
            issues.append(QualityIssue(
                exercise_id=exercise_id,
                issue_type='completeness',
                description='No examples or code blocks detected',
                suggestion='Add examples or code blocks to illustrate concepts',
                severity='minor'
            ))
            penalty += 0.10

        return issues, penalty

    def _analyze_progression(self, exercise_id: str, content: str) -> Tuple[List[QualityIssue], float]:
        """Analyze logical progression of instructions."""
        issues = []
        penalty = 0.0

        # Check for numbered steps
        numbered_steps = re.findall(r'^\s*(\d+)\.', content, re.MULTILINE)

        if not numbered_steps and len(content) > 800:
            issues.append(QualityIssue(
                exercise_id=exercise_id,
                issue_type='progression',
                description='No numbered steps detected',
                suggestion='Use numbered steps for clear progression (1. First step, 2. Second step, etc.)',
                severity='moderate'
            ))
            penalty += 0.15
        elif numbered_steps:
            # Check for sequential numbering
            numbers = [int(n) for n in numbered_steps]
            expected = list(range(1, len(numbers) + 1))

            if numbers != expected:
                issues.append(QualityIssue(
                    exercise_id=exercise_id,
                    issue_type='progression',
                    description='Steps are not numbered sequentially',
                    suggestion='Ensure steps are numbered 1, 2, 3, etc. without gaps',
                    severity='minor'
                ))
                penalty += 0.05

        return issues, penalty

    def _analyze_formatting(self, exercise_id: str, content: str) -> Tuple[List[QualityIssue], float]:
        """Analyze formatting consistency."""
        issues = []
        penalty = 0.0

        # Check for inconsistent command formatting
        # Look for commands that should be in code blocks but aren't
        command_patterns = [
            r'run\s+([a-z\-]+)',
            r'execute\s+([a-z\-]+)',
            r'type\s+([a-z\-]+)'
        ]

        unformatted_commands = 0
        for pattern in command_patterns:
            matches = re.findall(pattern, content, re.I)
            for match in matches:
                # Check if the command appears in a code block
                if not re.search(rf'`{match}`|```.*{match}', content):
                    unformatted_commands += 1

        if unformatted_commands > 2:
            issues.append(QualityIssue(
                exercise_id=exercise_id,
                issue_type='formatting',
                description=f'{unformatted_commands} commands may need formatting',
                suggestion='Format commands in code blocks or backticks for clarity',
                severity='minor'
            ))
            penalty += 0.05

        return issues, penalty

    def _count_issues_by_type(self, issues: List[QualityIssue]) -> dict:
        """Count issues by type."""
        counts = {}
        for issue in issues:
            counts[issue.issue_type] = counts.get(issue.issue_type, 0) + 1
        return counts

    def _quality_issue_to_dict(self, issue: QualityIssue) -> dict:
        """Convert QualityIssue to dictionary."""
        return {
            'exercise_id': issue.exercise_id,
            'issue_type': issue.issue_type,
            'description': issue.description,
            'suggestion': issue.suggestion,
            'severity': issue.severity
        }


def main():
    """Test TC_INSTRUCT functionality."""
    import argparse
    from lib.test_result import ExerciseType

    parser = argparse.ArgumentParser(description="Analyze instruction quality")
    parser.add_argument("exercise_id", help="Exercise ID")
    parser.add_argument("--content", "-c", required=True, help="Path to EPUB content file")

    args = parser.parse_args()

    # Load content
    with open(args.content, 'r') as f:
        content = f.read()

    # Create exercise context
    exercise = ExerciseContext(
        id=args.exercise_id,
        type=ExerciseType.GUIDED_EXERCISE,
        lesson_code="<lesson-code>",
        chapter=1,
        chapter_title="Test",
        title=args.exercise_id
    )

    # Run test
    tester = TC_INSTRUCT()
    result = tester.test(exercise, content)

    print("\n" + "=" * 60)
    print(f"Quality Score: {result.details['quality_score']:.2f}")
    print(f"Result: {'PASS' if result.passed else 'NEEDS IMPROVEMENT'}")
    print(f"Issues Found: {result.details['total_issues']}")

    if result.details['issues']:
        print("\nSuggestions:")
        for issue in result.details['issues']:
            print(f"\n• {issue['description']}")
            print(f"  → {issue['suggestion']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
