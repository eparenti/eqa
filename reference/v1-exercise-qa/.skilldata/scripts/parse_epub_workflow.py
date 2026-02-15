#!/usr/bin/env python3
"""
Parse EPUB guided exercise workflow and extract executable steps.

This script extracts:
- Numbered steps from the procedure section
- Commands from each step (code blocks, terminal output)
- Expected results/output
- Verification points

Output: JSON workflow file for automated execution
"""

import re
import sys
import json
from html.parser import HTMLParser
from pathlib import Path


class WorkflowParser(HTMLParser):
    """Parse EPUB HTML to extract exercise workflow."""

    def __init__(self, exercise_id):
        super().__init__()
        self.exercise_id = exercise_id
        self.in_ge = False
        self.in_procedure = False
        self.in_step = False
        self.in_code = False
        self.in_strong = False

        self.current_step = None
        self.steps = []
        self.step_number = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        # Find GE section
        if tag == "h2" and f"{self.exercise_id}-ge" in attrs_dict.get("id", ""):
            self.in_ge = True

        # Find procedure section
        elif self.in_ge and tag == "section" and "procedure" in attrs_dict.get("class", ""):
            self.in_procedure = True

        # Find step (ordered list item)
        elif self.in_procedure and tag == "li":
            self.step_number += 1
            self.current_step = {
                "step_number": self.step_number,
                "description": "",
                "commands": [],
                "expected_output": "",
                "verification": []
            }
            self.in_step = True

        # Find code blocks
        elif self.in_step and tag == "pre":
            self.in_code = True

        # Find command within code block (usually in <strong>)
        elif self.in_code and tag == "strong":
            self.in_strong = True

    def handle_endtag(self, tag):
        if tag == "li" and self.in_step:
            self.in_step = False
            if self.current_step:
                self.steps.append(self.current_step)
                self.current_step = None

        elif tag == "pre":
            self.in_code = False

        elif tag == "strong":
            self.in_strong = False

        elif tag == "section" and self.in_procedure:
            self.in_procedure = False

    def handle_data(self, data):
        if self.in_step and not self.in_code:
            # Step description text
            clean = data.strip().replace("\xa0", " ")
            if clean and self.current_step:
                self.current_step["description"] += " " + clean

        elif self.in_strong and self.current_step:
            # Command to execute
            cmd = data.strip()
            if cmd and not cmd.startswith("[") and not cmd.startswith("..."):
                self.current_step["commands"].append(cmd)

    def get_workflow(self):
        """Return parsed workflow."""
        return {
            "exercise_id": self.exercise_id,
            "total_steps": len(self.steps),
            "steps": self.steps
        }


def extract_workflow(epub_path, exercise_id, output_file=None):
    """
    Extract executable workflow from EPUB.

    Args:
        epub_path: Path to EPUB file
        exercise_id: Exercise identifier (e.g., '<exercise-name>')
        output_file: Optional JSON output file path

    Returns:
        dict: Workflow structure
    """
    import zipfile
    import tempfile

    # Extract EPUB
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(epub_path, 'r') as epub:
            epub.extractall(tmpdir)

        # Find chapter XHTML file
        chapter_file = None
        for xhtml in Path(tmpdir).glob("EPUB/*.xhtml"):
            if exercise_id.split("-")[0] in xhtml.stem:
                chapter_file = xhtml
                break

        if not chapter_file:
            print(f"❌ Could not find chapter file for {exercise_id}")
            return None

        # Parse HTML
        with open(chapter_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        parser = WorkflowParser(exercise_id)
        parser.feed(html_content)
        workflow = parser.get_workflow()

        # Save to file if requested
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(workflow, f, indent=2)
            print(f"✅ Workflow saved to: {output_file}")

        return workflow


def main():
    """CLI interface."""
    if len(sys.argv) < 3:
        print("Usage: parse_epub_workflow.py <epub_file> <exercise_id> [output.json]")
        print("\nExample:")
        print("  parse_epub_workflow.py AU0022L.epub <exercise-name> workflow.json")
        sys.exit(1)

    epub_path = sys.argv[1]
    exercise_id = sys.argv[2]
    output_file = sys.argv[3] if len(sys.argv) > 3 else None

    if not Path(epub_path).exists():
        print(f"❌ EPUB file not found: {epub_path}")
        sys.exit(1)

    workflow = extract_workflow(epub_path, exercise_id, output_file)

    if workflow:
        print(f"\n📋 Extracted Workflow:")
        print(f"   Exercise: {workflow['exercise_id']}")
        print(f"   Total Steps: {workflow['total_steps']}")
        print(f"\n   Steps:")
        for step in workflow['steps'][:5]:  # Show first 5
            print(f"   {step['step_number']}. {step['description'][:60]}...")
            if step['commands']:
                print(f"      Commands: {len(step['commands'])}")
                for cmd in step['commands'][:2]:
                    print(f"        • {cmd}")


if __name__ == "__main__":
    main()
