"""
EPUB Instruction Extractor

Extracts step-by-step instructions from EPUB exercise content,
including commands to execute and expected outputs.

This enables testing from the student's perspective - following
exactly what they see in the course materials.
"""

import re
import zipfile
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from bs4 import BeautifulSoup, Tag


@dataclass
class Command:
    """A command that students should execute."""
    text: str                          # The command text
    expected_output: Optional[str] = None  # Expected output after command
    is_interactive: bool = False       # Requires user input (prompts)
    prompts: List[Tuple[str, str]] = field(default_factory=list)  # (prompt, response) pairs


@dataclass
class InstructionStep:
    """A single instruction step from the exercise."""
    number: str                        # Step number (1, 2, 1.a, etc.)
    text: str                          # Instruction text
    commands: List[Command] = field(default_factory=list)
    sub_steps: List['InstructionStep'] = field(default_factory=list)
    is_verification: bool = False      # Step that verifies previous work


@dataclass
class ExerciseInstructions:
    """Complete extracted instructions for an exercise."""
    exercise_id: str
    title: str
    outcomes: List[str] = field(default_factory=list)
    prerequisites_command: Optional[str] = None  # lab start command
    steps: List[InstructionStep] = field(default_factory=list)
    total_commands: int = 0


class InstructionExtractor:
    """
    Extracts executable instructions from EPUB exercise content.

    Usage:
        extractor = InstructionExtractor(epub_path)
        instructions = extractor.extract("install-config-ge")

        for step in instructions.steps:
            print(f"Step {step.number}: {step.text}")
            for cmd in step.commands:
                print(f"  $ {cmd.text}")
    """

    def __init__(self, epub_path: Path):
        self.epub_path = epub_path
        self.temp_dir = None
        self.content_dir = None

    def extract(self, exercise_id: str) -> Optional[ExerciseInstructions]:
        """
        Extract instructions for a specific exercise.

        Args:
            exercise_id: Exercise ID (e.g., "install-config-ge")

        Returns:
            ExerciseInstructions with parsed steps and commands
        """
        self._extract_epub()

        # Find the exercise in EPUB
        exercise_content = self._find_exercise_content(exercise_id)
        if not exercise_content:
            self.cleanup()
            return None

        # Parse the content
        instructions = self._parse_exercise_content(exercise_id, exercise_content)

        return instructions

    def extract_all(self) -> Dict[str, ExerciseInstructions]:
        """Extract instructions for all exercises in the EPUB."""
        self._extract_epub()

        exercises = {}

        # Find all XHTML files
        for html_file in self.content_dir.glob("*.xhtml"):
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f, 'html.parser')

                # Find exercise sections
                for section in soup.find_all(['h2', 'section']):
                    section_id = section.get('id', '')
                    if section_id.endswith('-ge') or section_id.endswith('-lab'):
                        instructions = self._parse_exercise_section(section_id, section, soup)
                        if instructions:
                            exercises[section_id] = instructions

            except Exception as e:
                print(f"Warning: Error parsing {html_file.name}: {e}")

        return exercises

    def _extract_epub(self):
        """Extract EPUB to temporary directory."""
        if self.temp_dir:
            return

        self.temp_dir = tempfile.mkdtemp(prefix="epub_instructions_")
        self.content_dir = Path(self.temp_dir) / "EPUB"

        with zipfile.ZipFile(self.epub_path, 'r') as zip_ref:
            zip_ref.extractall(self.temp_dir)

    def _find_exercise_content(self, exercise_id: str) -> Optional[Tag]:
        """Find exercise content section in EPUB."""
        if not self.content_dir.exists():
            return None

        # Search all XHTML files for the exercise
        for html_file in self.content_dir.glob("*.xhtml"):
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f, 'html.parser')

                # Find element with matching ID
                element = soup.find(id=exercise_id)
                if element:
                    return element

            except Exception:
                continue

        return None

    def _parse_exercise_content(self, exercise_id: str, element: Tag) -> ExerciseInstructions:
        """Parse exercise content into structured instructions."""
        instructions = ExerciseInstructions(
            exercise_id=exercise_id,
            title=self._extract_title(element)
        )

        # Get the parent document for context
        soup = element.find_parent()
        while soup and soup.name != '[document]':
            soup = soup.parent

        # Find all sibling sections until next h2
        current = element
        while current:
            current = current.find_next_sibling()
            if not current:
                break

            # Stop at next h2 (next exercise/chapter)
            if current.name == 'h2':
                break

            if current.name == 'section':
                section_title = current.get('title', '').lower()

                if 'outcomes' in section_title:
                    instructions.outcomes = self._parse_outcomes(current)

                elif 'prerequisites' in section_title:
                    instructions.prerequisites_command = self._parse_prerequisites(current)

                elif 'instructions' in section_title:
                    instructions.steps = self._parse_instructions(current)

        # Count total commands
        def count_commands(steps):
            total = 0
            for step in steps:
                total += len(step.commands)
                total += count_commands(step.sub_steps)
            return total

        instructions.total_commands = count_commands(instructions.steps)

        return instructions

    def _parse_exercise_section(self, exercise_id: str, element: Tag, soup: BeautifulSoup) -> Optional[ExerciseInstructions]:
        """Parse exercise from section element."""
        return self._parse_exercise_content(exercise_id, element)

    def _extract_title(self, element: Tag) -> str:
        """Extract exercise title from header element."""
        title_elem = element.find(class_='title')
        if title_elem:
            return title_elem.get_text(strip=True)

        # Fall back to full text
        return element.get_text(strip=True)

    def _parse_outcomes(self, section: Tag) -> List[str]:
        """Parse outcomes list."""
        outcomes = []
        for li in section.find_all('li'):
            text = li.get_text(strip=True)
            if text:
                outcomes.append(text)
        return outcomes

    def _parse_prerequisites(self, section: Tag) -> Optional[str]:
        """Parse prerequisites section to find lab start command."""
        # Find code blocks
        for pre in section.find_all('pre'):
            text = pre.get_text()
            # Look for lab start command
            if 'lab start' in text:
                # Extract the full lab start command with optional flags
                # Formats:
                #   lab start exercise-name
                #   lab start -t lesson-code exercise-name
                match = re.search(r'lab start(?:\s+-t\s+[\w-]+)?\s+[\w-]+', text)
                if match:
                    return match.group()
        return None

    def _parse_instructions(self, section: Tag) -> List[InstructionStep]:
        """Parse the instructions section into steps."""
        steps = []

        # Find ordered lists (numbered steps)
        ol = section.find('ol', class_='arabic')
        if ol:
            step_num = 1
            for li in ol.find_all('li', recursive=False):
                step = self._parse_step(li, str(step_num))
                if step:
                    steps.append(step)
                step_num += 1

        return steps

    def _parse_step(self, li: Tag, number: str) -> InstructionStep:
        """Parse a single instruction step."""
        # Get the main instruction text
        principal = li.find(class_='principal', recursive=False)
        if not principal:
            # Try finding it anywhere in the li
            principal = li.find(class_='principal')

        if principal:
            text = principal.get_text(strip=True)
        else:
            # Get first text content before any nested elements
            text = ''
            for child in li.children:
                if isinstance(child, str):
                    text = child.strip()
                    break
                elif child.name == 'span':
                    text = child.get_text(strip=True)
                    break

        step = InstructionStep(
            number=number,
            text=text
        )

        # Check if this is a verification step
        verification_keywords = ['verify', 'confirm', 'check', 'ensure', 'validate']
        step.is_verification = any(kw in text.lower() for kw in verification_keywords)

        # Find commands in code blocks - check directly in li first
        for figure in li.find_all('figure', class_='listing', recursive=False):
            for pre in figure.find_all('pre'):
                commands = self._parse_code_block(pre)
                step.commands.extend(commands)

        for pre in li.find_all('pre', recursive=False):
            commands = self._parse_code_block(pre)
            step.commands.extend(commands)

        # Parse sub-steps - they can be in <ol> or <div class="ordered-list"><ol>
        # First, try finding nested ol directly
        nested_ols = li.find_all('ol', recursive=False)

        # Also check for ol inside ordered-list divs
        for div in li.find_all('div', class_='ordered-list', recursive=False):
            nested_ols.extend(div.find_all('ol', recursive=False))

        for nested_ol in nested_ols:
            step_letter = 'a'
            for nested_li in nested_ol.find_all('li', recursive=False):
                sub_step = self._parse_step(nested_li, f"{number}.{step_letter}")
                if sub_step:
                    step.sub_steps.append(sub_step)
                step_letter = chr(ord(step_letter) + 1)

        return step

    def _parse_code_block(self, pre: Tag) -> List[Command]:
        """Parse a code block to extract commands and expected output."""
        commands = []

        # Get the full text with structure
        full_text = pre.get_text()

        # Find commands (marked with <strong> in original HTML)
        strong_elements = pre.find_all('strong')

        # Collect command parts, handling continuation lines (ending with \)
        cmd_parts = []
        for strong in strong_elements:
            cmd_text = strong.get_text(strip=True)
            if not cmd_text:
                continue

            # Skip prompts, passwords, and non-command content
            skip_patterns = [
                'redhat', 'admin', 'student', 'yes', 'no', 'y', 'n',
                'Student@123', 'password', 'Password'
            ]
            if cmd_text in skip_patterns:
                continue

            # Skip YAML content (starts with - or key:)
            if cmd_text.startswith('- ') or cmd_text.startswith('key:') or cmd_text.startswith('value:'):
                continue

            # Skip if it looks like a password (contains @ and no spaces, short)
            if '@' in cmd_text and ' ' not in cmd_text and len(cmd_text) < 20:
                continue

            cmd_parts.append(cmd_text)

        if not cmd_parts:
            return commands

        # Build commands, joining only continuation lines (ending with \)
        current_cmd = []
        final_commands = []

        for part in cmd_parts:
            current_cmd.append(part)
            # If this part doesn't end with \, it's the end of a command
            if not part.rstrip().endswith('\\'):
                # Join the parts and clean up
                full_cmd = ' '.join(current_cmd)
                full_cmd = re.sub(r'\\\s+', ' ', full_cmd)  # Remove \ continuations
                full_cmd = re.sub(r'\s+', ' ', full_cmd).strip()
                if full_cmd:
                    final_commands.append(full_cmd)
                current_cmd = []

        # Handle any remaining parts
        if current_cmd:
            full_cmd = ' '.join(current_cmd)
            full_cmd = re.sub(r'\\\s+', ' ', full_cmd)
            full_cmd = re.sub(r'\s+', ' ', full_cmd).strip()
            if full_cmd:
                final_commands.append(full_cmd)

        # Check if this is an interactive command
        is_interactive = False
        prompts = []

        # Look for prompts (Username:, Password:, etc.) in surrounding context
        parent_text = pre.get_text()
        if 'Username:' in parent_text or 'Password:' in parent_text:
            is_interactive = True
            # Extract prompt/response pairs
            prompt_patterns = [
                (r'Username:\s*(\S+)', 'Username:'),
                (r'Password:\s*(\S+)', 'Password:'),
            ]
            for pattern, prompt in prompt_patterns:
                match = re.search(pattern, parent_text)
                if match:
                    prompts.append((prompt, match.group(1)))

        # Create Command objects for each extracted command
        for cmd_text in final_commands:
            command = Command(
                text=cmd_text,
                expected_output=None,  # TODO: extract per-command output
                is_interactive=is_interactive,
                prompts=prompts if is_interactive else []
            )
            commands.append(command)

        return commands

    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None
            self.content_dir = None


def extract_instructions(epub_path: Path, exercise_id: str) -> Optional[ExerciseInstructions]:
    """
    Convenience function to extract instructions for an exercise.

    Args:
        epub_path: Path to EPUB file
        exercise_id: Exercise ID

    Returns:
        ExerciseInstructions or None if not found
    """
    extractor = InstructionExtractor(epub_path)
    try:
        return extractor.extract(exercise_id)
    finally:
        extractor.cleanup()
