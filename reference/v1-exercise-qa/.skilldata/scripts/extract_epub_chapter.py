#!/usr/bin/env python3
"""
Extract Chapter Content from EPUB

Extracts specific chapter content from an EPUB file for QA testing.

Usage:
    python scripts/extract_epub_chapter.py <epub-path> <chapter-number> [mapping-file]

Example:
    python scripts/extract_epub_chapter.py <ANSIBLE-COURSE>.epub 2
    python scripts/extract_epub_chapter.py <ANSIBLE-COURSE>.epub 2 course-mapping.json
"""

import os
import sys
import json
import zipfile
import tempfile
from pathlib import Path
from html.parser import HTMLParser


class ExerciseHTMLParser(HTMLParser):
    """Parse HTML/XHTML to extract exercise sections."""

    def __init__(self):
        super().__init__()
        self.in_exercise = False
        self.in_lab = False
        self.current_exercise = None
        self.exercises = []
        self.current_section_id = None
        self.current_content = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        # Check for exercise or lab sections
        if tag == 'section':
            section_id = attrs_dict.get('id', '')
            class_attr = attrs_dict.get('class', '')

            # Guided Exercise
            if 'ge' in class_attr or 'guided-exercise' in class_attr:
                self.in_exercise = True
                self.current_section_id = section_id
                self.current_content = []

            # Lab
            elif 'lab' in class_attr:
                self.in_lab = True
                self.current_section_id = section_id
                self.current_content = []

    def handle_endtag(self, tag):
        if tag == 'section' and (self.in_exercise or self.in_lab):
            # Save the exercise/lab
            if self.current_content:
                content = ' '.join(self.current_content)
                exercise_type = 'lab' if self.in_lab else 'exercise'

                self.exercises.append({
                    'id': self.current_section_id,
                    'type': exercise_type,
                    'content': content
                })

            self.in_exercise = False
            self.in_lab = False
            self.current_section_id = None
            self.current_content = []

    def handle_data(self, data):
        if self.in_exercise or self.in_lab:
            clean_data = data.strip()
            if clean_data:
                self.current_content.append(clean_data)


def load_mapping_file(mapping_path):
    """Load chapter-to-lesson mapping from JSON file."""
    try:
        with open(mapping_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing mapping file: {e}")
        return None


def extract_epub(epub_path, output_dir):
    """Extract EPUB to temporary directory."""
    try:
        with zipfile.ZipFile(epub_path, 'r') as zip_ref:
            zip_ref.extractall(output_dir)
        return True
    except Exception as e:
        print(f"❌ Error extracting EPUB: {e}")
        return False


def find_chapter_file(mapping, chapter_num):
    """Find chapter file name from mapping."""
    chapter_key = str(chapter_num)

    if chapter_key in mapping.get('mapping', {}):
        return mapping['mapping'][chapter_key].get('chapter_file')

    return None


def extract_chapter_content(epub_dir, chapter_file):
    """Extract content from chapter XHTML file."""
    # Common EPUB structure
    possible_paths = [
        Path(epub_dir) / 'EPUB' / chapter_file,
        Path(epub_dir) / 'OPS' / chapter_file,
        Path(epub_dir) / chapter_file
    ]

    for path in possible_paths:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse exercises
            parser = ExerciseHTMLParser()
            parser.feed(content)

            return {
                'file_path': str(path),
                'full_content': content,
                'exercises': parser.exercises
            }

    return None


def main():
    if len(sys.argv) < 3:
        print("❌ Error: EPUB path and chapter number required")
        print("Usage: python extract_epub_chapter.py <epub-path> <chapter-number> [mapping-file]")
        sys.exit(1)

    epub_path = sys.argv[1]
    chapter_num = sys.argv[2]
    mapping_file = sys.argv[3] if len(sys.argv) > 3 else 'course-mapping.json'

    # Validate EPUB exists
    if not os.path.exists(epub_path):
        print(f"❌ EPUB file not found: {epub_path}")
        sys.exit(1)

    print(f"📚 Extracting Chapter {chapter_num} from: {epub_path}\n")

    # Load mapping
    mapping = load_mapping_file(mapping_file)
    if not mapping:
        print(f"⚠️  Mapping file not found: {mapping_file}")
        print("   Attempting to extract without mapping...")
        chapter_file = None
    else:
        chapter_file = find_chapter_file(mapping, chapter_num)
        if chapter_file:
            print(f"✅ Found chapter file from mapping: {chapter_file}")
        else:
            print(f"⚠️  Chapter {chapter_num} not found in mapping")

    # Extract EPUB to temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📂 Extracting EPUB to temporary directory...")

        if not extract_epub(epub_path, temp_dir):
            sys.exit(1)

        print("✅ EPUB extracted successfully\n")

        # If no mapping, try to find chapter files
        if not chapter_file:
            print("🔍 Searching for chapter files...")
            epub_dir = Path(temp_dir) / 'EPUB'
            if not epub_dir.exists():
                epub_dir = Path(temp_dir) / 'OPS'

            # Look for common chapter patterns
            patterns = [
                f'chapter{chapter_num}.xhtml',
                f'ch{chapter_num}.xhtml',
                f'chap{chapter_num}.xhtml'
            ]

            for pattern in patterns:
                chapter_path = epub_dir / pattern
                if chapter_path.exists():
                    chapter_file = pattern
                    print(f"✅ Found: {chapter_file}")
                    break

            if not chapter_file:
                print("❌ Could not find chapter file")
                sys.exit(1)

        # Extract chapter content
        result = extract_chapter_content(temp_dir, chapter_file)

        if not result:
            print(f"❌ Could not extract content from {chapter_file}")
            sys.exit(1)

        # Display results
        print(f"\n📊 Chapter Content Extracted:")
        print(f"   File: {result['file_path']}")
        print(f"   Content size: {len(result['full_content'])} characters")
        print(f"   Exercises found: {len(result['exercises'])}\n")

        if result['exercises']:
            print("🎯 Exercises/Labs in this chapter:")
            for i, exercise in enumerate(result['exercises'], 1):
                print(f"   {i}. [{exercise['type'].upper()}] {exercise['id']}")
                print(f"      Preview: {exercise['content'][:100]}...")
                print()
        else:
            print("ℹ️  No exercises detected (may need manual extraction)")

        # Save to output file
        output_file = f"chapter-{chapter_num}-content.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"=== Chapter {chapter_num} Content ===\n\n")
            f.write(result['full_content'])

        print(f"💾 Full content saved to: {output_file}")

        # Save exercises separately
        if result['exercises']:
            exercises_file = f"chapter-{chapter_num}-exercises.json"
            with open(exercises_file, 'w', encoding='utf-8') as f:
                json.dump(result['exercises'], f, indent=2)
            print(f"💾 Exercises saved to: {exercises_file}")

    print("\n✅ Extraction complete!")


if __name__ == "__main__":
    main()
