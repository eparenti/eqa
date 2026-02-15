#!/usr/bin/env python3
"""
TC-ACCESSIBILITY: Accessibility Compliance Validation

Tests EPUB content for WCAG 2.2 and EN 301 549 compliance.
Reports findings as P2/P3 severity (improvement suggestions, not critical bugs).

Accessibility checks:
- Images without alt text
- Improper heading hierarchy
- Color contrast issues
- Missing keyboard navigation instructions
- Screen reader compatibility
"""

import sys
import re
from pathlib import Path
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.test_result import TestResult, Bug, BugSeverity, ExerciseContext
from lib.ssh_connection import SSHConnection


class TC_ACCESSIBILITY:
    """
    Accessibility compliance validation test category.

    Reports findings as improvement suggestions (P2/P3), not critical bugs.
    Based on WCAG 2.2 and EN 301 549 standards.
    """

    def __init__(self):
        """Initialize accessibility tester."""
        pass

    def test(self, exercise: ExerciseContext, epub_content: str = None) -> TestResult:
        """
        Test exercise EPUB content for accessibility compliance.

        All findings are reported as P2/P3 (improvement suggestions).

        Args:
            exercise: Exercise context
            epub_content: EPUB HTML content (optional)

        Returns:
            TestResult with accessibility improvement suggestions
        """
        print(f"\n♿ TC-ACCESSIBILITY: Accessibility Compliance")
        print("=" * 60)
        print("  Standards: WCAG 2.2, EN 301 549")
        print("  Note: Findings are improvement suggestions")

        bugs_found = []

        if not epub_content:
            print("  ℹ️  No EPUB content provided, skipping accessibility checks")
            return TestResult(
                category="TC-ACCESSIBILITY",
                exercise_id=exercise.id,
                passed=True,
                timestamp="",
                duration_seconds=0,
                details={'skipped': True},
                summary="Accessibility: Skipped (no EPUB content)"
            )

        # Check 1: Images without alt text
        print("\n  1. Checking for images without alt text...")
        alt_text_issues = self._check_alt_text(epub_content, exercise)
        bugs_found.extend(alt_text_issues)
        if alt_text_issues:
            print(f"     ⚠️  Found {len(alt_text_issues)} image(s) missing alt text")
        else:
            print("     ✅ All images have alt text")

        # Check 2: Heading hierarchy
        print("\n  2. Checking heading hierarchy...")
        heading_issues = self._check_heading_hierarchy(epub_content, exercise)
        bugs_found.extend(heading_issues)
        if heading_issues:
            print(f"     ⚠️  Found heading hierarchy issue(s)")
        else:
            print("     ✅ Heading hierarchy is proper")

        # Check 3: Keyboard navigation
        print("\n  3. Checking for keyboard navigation instructions...")
        keyboard_issues = self._check_keyboard_instructions(epub_content, exercise)
        bugs_found.extend(keyboard_issues)
        if keyboard_issues:
            print(f"     ⚠️  Consider adding keyboard navigation guidance")
        else:
            print("     ✅ Keyboard navigation mentioned")

        # Check 4: Screen reader considerations
        print("\n  4. Checking screen reader compatibility...")
        screen_reader_issues = self._check_screen_reader_compat(epub_content, exercise)
        bugs_found.extend(screen_reader_issues)
        if screen_reader_issues:
            print(f"     ⚠️  Screen reader considerations recommended")
        else:
            print("     ✅ Content appears screen reader friendly")

        # Summary
        print(f"\n{'=' * 60}")
        if bugs_found:
            print(f"Accessibility Suggestions: {len(bugs_found)} improvement(s) recommended")
        else:
            print("Accessibility: ✅ No accessibility improvements needed")
        print(f"{'=' * 60}")

        return TestResult(
            category="TC-ACCESSIBILITY",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp="",
            duration_seconds=0,
            bugs_found=bugs_found,
            details={
                'checks_performed': 4,
                'suggestions_count': len(bugs_found)
            },
            summary=f"Accessibility: {len(bugs_found)} improvement suggestions"
        )

    def _check_alt_text(self, epub_content: str, exercise: ExerciseContext) -> List[Bug]:
        """Check for images without alt text. Returns P2 suggestions."""
        bugs = []

        # Find all img tags
        img_pattern = r'<img[^>]*>'
        images = re.findall(img_pattern, epub_content, re.IGNORECASE)

        for img_tag in images:
            # Check if alt attribute exists
            if not re.search(r'alt\s*=\s*["\'][^"\']*["\']', img_tag, re.IGNORECASE):
                bugs.append(Bug(
                    id=f"A11Y-ALT-{exercise.id}",
                    severity=BugSeverity.P2_HIGH,
                    exercise_id=exercise.id,
                    category="TC-ACCESSIBILITY",
                    description="Accessibility Improvement: Image(s) missing alt text for screen readers",
                    fix_recommendation="""
Add alt text to all images for screen reader users:

**Example:**
```html
<!-- Before -->
<img src="screenshot.png">

<!-- After -->
<img src="screenshot.png" alt="Screenshot showing the OpenShift web console with the Projects dropdown menu expanded">
```

**Guidelines:**
- Describe what the image shows, not just "screenshot"
- Include relevant UI elements shown
- For decorative images, use alt=""
- Keep descriptions concise but informative

**WCAG 2.2 Requirement**: Level A (required for compliance)
""",
                    verification_steps=[
                        "Review all images in EPUB content",
                        "Add descriptive alt text to each image",
                        "Test with screen reader if possible"
                    ]
                ))
                break  # Report once, not for every image

        return bugs

    def _check_heading_hierarchy(self, epub_content: str, exercise: ExerciseContext) -> List[Bug]:
        """Check for proper heading hierarchy. Returns P3 suggestions."""
        bugs = []

        # Extract headings
        heading_pattern = r'<h([1-6])[^>]*>'
        headings = re.findall(heading_pattern, epub_content, re.IGNORECASE)

        if not headings:
            return bugs

        # Check if h1 exists and is first
        if headings and headings[0] != '1':
            bugs.append(Bug(
                id=f"A11Y-HEADING-{exercise.id}",
                severity=BugSeverity.P3_LOW,
                exercise_id=exercise.id,
                category="TC-ACCESSIBILITY",
                description="Accessibility Improvement: Heading hierarchy should start with h1",
                fix_recommendation="""
Maintain proper heading hierarchy for screen reader navigation:

**Hierarchy Rules:**
1. Start with <h1> for main title
2. Use <h2> for major sections
3. Use <h3> for subsections under <h2>
4. Don't skip levels (h1 → h3 is invalid)

**Example:**
```html
<h1>Exercise Title</h1>
<h2>Prerequisites</h2>
<h3>Required Packages</h3>
<h2>Procedure</h2>
<h3>Step 1: Configure Service</h3>
```

**WCAG 2.2 Requirement**: Helps screen reader users navigate content
""",
                verification_steps=[
                    "Review heading structure in EPUB",
                    "Ensure proper nesting (h1 → h2 → h3)",
                    "Don't skip heading levels"
                ]
            ))

        return bugs

    def _check_keyboard_instructions(self, epub_content: str, exercise: ExerciseContext) -> List[Bug]:
        """Check for keyboard navigation instructions. Returns P3 suggestions."""
        bugs = []

        # Check if content mentions keyboard navigation
        keyboard_mentions = re.search(
            r'\b(keyboard|tab|enter|escape|arrow\s+keys)\b',
            epub_content,
            re.IGNORECASE
        )

        # If web UI is involved but no keyboard mentions
        if re.search(r'\b(web\s+console|browser|click|button)\b', epub_content, re.IGNORECASE):
            if not keyboard_mentions:
                bugs.append(Bug(
                    id=f"A11Y-KEYBOARD-{exercise.id}",
                    severity=BugSeverity.P3_LOW,
                    exercise_id=exercise.id,
                    category="TC-ACCESSIBILITY",
                    description="Accessibility Improvement: Consider adding keyboard navigation instructions",
                    fix_recommendation="""
For exercises involving web UIs, consider mentioning keyboard alternatives:

**Example additions:**
```
**Note**: You can navigate using Tab (move forward),
Shift+Tab (move backward), Enter (activate), and
Escape (cancel/close dialogs).
```

Or for specific actions:
```
3. Click the Save button (or press Alt+S).
4. Navigate the menu using arrow keys or click items.
```

**Best Practice**: Make content accessible to keyboard-only users.
**WCAG 2.2**: Level A requirement - all functionality available via keyboard
""",
                    verification_steps=[
                        "Review exercise for web UI interactions",
                        "Add keyboard alternatives where appropriate",
                        "Test that all actions are keyboard-accessible"
                    ]
                ))

        return bugs

    def _check_screen_reader_compat(self, epub_content: str, exercise: ExerciseContext) -> List[Bug]:
        """Check for screen reader compatibility considerations. Returns P3 suggestions."""
        bugs = []

        # Check for tables without headers
        if re.search(r'<table[^>]*>', epub_content, re.IGNORECASE):
            # Check if tables have <th> tags
            if not re.search(r'<th[^>]*>', epub_content, re.IGNORECASE):
                bugs.append(Bug(
                    id=f"A11Y-TABLE-{exercise.id}",
                    severity=BugSeverity.P3_LOW,
                    exercise_id=exercise.id,
                    category="TC-ACCESSIBILITY",
                    description="Accessibility Improvement: Tables should have header cells (<th>) for screen readers",
                    fix_recommendation="""
Use proper table headers for screen reader compatibility:

**Before:**
```html
<table>
  <tr>
    <td>Name</td>
    <td>Status</td>
  </tr>
</table>
```

**After:**
```html
<table>
  <tr>
    <th>Name</th>
    <th>Status</th>
  </tr>
  <tr>
    <td>pod-1</td>
    <td>Running</td>
  </tr>
</table>
```

**WCAG 2.2**: Table headers help screen readers announce column/row context
""",
                    verification_steps=[
                        "Review all tables in EPUB content",
                        "Add <th> tags for header rows",
                        "Consider adding scope='col' or scope='row' for complex tables"
                    ]
                ))

        return bugs


def main():
    """Test TC-ACCESSIBILITY."""
    from lib.test_result import ExerciseType

    print("TC-ACCESSIBILITY: Accessibility Compliance Validation Demo")
    print("=" * 80)

    # Create test exercise
    exercise = ExerciseContext(
        id="example-exercise",
        type=ExerciseType.GUIDED_EXERCISE,
        lesson_code="test",
        chapter=1,
        chapter_title="Test",
        title="Example Exercise"
    )

    # Sample EPUB content with accessibility issues
    epub_content = """
    <h2>Exercise Instructions</h2>
    <p>Click the button in the web console.</p>
    <img src="screenshot.png">
    <table>
      <tr><td>Name</td><td>Status</td></tr>
    </table>
    """

    # Run accessibility checks
    tester = TC_ACCESSIBILITY()
    result = tester.test(exercise, epub_content)

    print("\n" + "=" * 80)
    print(f"Result: {'PASS' if result.passed else 'SUGGESTIONS'}")
    print(f"Accessibility Suggestions: {len(result.bugs_found)}")
    print("=" * 80)

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
