"""EPUB building, parsing, and instruction extraction.

Combines three functions:
- EPUBBuilder: builds EPUBs using the `sk` scaffolding tool
- EPUBParser: parses EPUB structure to find exercises
- InstructionExtractor: extracts step-by-step commands from EPUB content
"""

import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from bs4 import BeautifulSoup, Tag

from .models import CourseContext, ExerciseContext, ExerciseType


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BuildResult:
    """Result of EPUB build operation."""
    success: bool
    message: str
    epub_path: Optional[Path] = None
    stdout: str = ""
    stderr: str = ""


@dataclass
class Command:
    """A command that students should execute."""
    text: str
    expected_output: Optional[str] = None
    is_interactive: bool = False
    prompts: List[Tuple[str, str]] = field(default_factory=list)


class FileActionType(Enum):
    """Type of file action from EPUB instructions."""
    CREATE = "create"
    MODIFY = "modify"


@dataclass
class FileAction:
    """A file that students should create or modify."""
    filename: str
    content: str
    action_type: FileActionType
    context_text: str = ""


@dataclass
class InstructionStep:
    """A single instruction step from the exercise."""
    number: str
    text: str
    commands: List[Command] = field(default_factory=list)
    file_actions: List[FileAction] = field(default_factory=list)
    sub_steps: List['InstructionStep'] = field(default_factory=list)
    is_verification: bool = False


@dataclass
class ExerciseInstructions:
    """Complete extracted instructions for an exercise."""
    exercise_id: str
    title: str
    outcomes: List[str] = field(default_factory=list)
    prerequisites_command: Optional[str] = None
    steps: List[InstructionStep] = field(default_factory=list)
    total_commands: int = 0


# ---------------------------------------------------------------------------
# EPUB Builder
# ---------------------------------------------------------------------------

class EPUBBuilder:
    """Builds EPUBs using the scaffolding `sk` tool."""

    def __init__(self):
        self.sk_path = self._find_sk()

    def _find_sk(self) -> Optional[Path]:
        """Find the sk tool."""
        sk_in_path = shutil.which("sk")
        if sk_in_path:
            return Path(sk_in_path)
        for path in [Path("/usr/bin/sk"), Path("/usr/local/bin/sk")]:
            if path.exists():
                return path
        return None

    def validate_sk_available(self) -> Tuple[bool, str]:
        """Check if sk tool is available."""
        if not self.sk_path:
            return False, "sk tool not found"
        try:
            result = subprocess.run(
                [str(self.sk_path), "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                version = result.stdout.strip() or result.stderr.strip()
                return True, f"sk available: {version}"
            return False, f"sk not working: {result.stderr}"
        except Exception as e:
            return False, f"sk check failed: {e}"

    def _ensure_ssh_agent(self) -> Tuple[bool, str]:
        """Ensure ssh-agent is running with a key loaded."""
        result = subprocess.run(
            ["ssh-add", "-l"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return True, "ssh-agent has keys loaded"

        ed25519_key = Path.home() / ".ssh" / "id_ed25519"
        rsa_key = Path.home() / ".ssh" / "id_rsa"
        key_to_add = ed25519_key if ed25519_key.exists() else rsa_key

        if not key_to_add.exists():
            return False, "No SSH key found (~/.ssh/id_ed25519 or ~/.ssh/id_rsa)"

        result = subprocess.run(
            ["ssh-add", str(key_to_add)], capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return True, f"Added {key_to_add.name} to ssh-agent"
        return False, f"Failed to add key: {result.stderr}"

    def build_epub(self, course_path: Path, force_rebuild: bool = True,
                   timeout: int = 600) -> BuildResult:
        """Build EPUB for a course using sk."""
        if not course_path.exists():
            return BuildResult(False, f"Course not found: {course_path}")
        if not self.sk_path:
            return BuildResult(False, "sk tool not found")

        if not force_rebuild:
            existing = self._find_existing_epub(course_path)
            if existing:
                return BuildResult(True, "Using existing EPUB", epub_path=existing)

        if not (course_path / "outline.yml").exists():
            return BuildResult(False, "Not a scaffolding course (no outline.yml)")

        print(f"Building EPUB for {course_path.name}...")

        ssh_ok, ssh_msg = self._ensure_ssh_agent()
        if not ssh_ok:
            return BuildResult(False, f"SSH setup failed: {ssh_msg}")
        print(f"   {ssh_msg}")

        cmd = [str(self.sk_path), "build", "epub3"]
        print(f"   Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd, cwd=course_path, capture_output=True, text=True, timeout=timeout,
            )
            output = result.stdout + result.stderr

            if result.returncode == 0:
                epub_path = self._find_existing_epub(course_path)
                if epub_path:
                    print(f"   EPUB built: {epub_path}")
                    return BuildResult(True, "EPUB built", epub_path=epub_path,
                                       stdout=result.stdout, stderr=result.stderr)
                return BuildResult(False, "Build completed but EPUB not found",
                                   stdout=result.stdout, stderr=result.stderr)
            else:
                if "Auth fail" in output or "JSchException" in output:
                    return BuildResult(
                        False,
                        "SSH auth failed. Run: eval $(ssh-agent) && ssh-add ~/.ssh/id_ed25519",
                        stdout=result.stdout, stderr=result.stderr,
                    )
                return BuildResult(False, f"Build failed (exit {result.returncode})",
                                   stdout=result.stdout, stderr=result.stderr)
        except subprocess.TimeoutExpired:
            return BuildResult(False, f"Build timed out (>{timeout}s)")
        except Exception as e:
            return BuildResult(False, f"Build error: {e}")

    def _find_existing_epub(self, course_path: Path) -> Optional[Path]:
        """Find existing EPUB in course directory."""
        for location in [course_path, course_path / ".cache" / "generated" / "en-US"]:
            if location.exists():
                epubs = list(location.glob("*.epub"))
                if epubs:
                    return max(epubs, key=lambda p: p.stat().st_mtime)
        return None

    def get_course_info(self, course_path: Path) -> dict:
        """Get basic course info from outline.yml."""
        info = {"course_code": course_path.name, "has_remote_chapters": False}

        metadata_path = course_path / "metadata.yml"
        if metadata_path.exists():
            try:
                with open(metadata_path) as f:
                    meta = yaml.safe_load(f)
                    info["course_code"] = meta.get("code", info["course_code"])
                    info["version"] = meta.get("version", "")
            except Exception:
                pass

        outline_path = course_path / "outline.yml"
        if outline_path.exists():
            try:
                with open(outline_path) as f:
                    outline = yaml.safe_load(f)
                dco = outline.get("dco", {})
                for chapter in dco.get("chapters", []):
                    if isinstance(chapter, dict) and "repository" in chapter:
                        info["has_remote_chapters"] = True
                        break
            except Exception:
                pass

        return info


# ---------------------------------------------------------------------------
# EPUB Parser
# ---------------------------------------------------------------------------

class EPUBParser:
    """Parses EPUB files to extract course structure and exercises."""

    def __init__(self, epub_path: Path, lesson_path: Optional[Path] = None):
        self.epub_path = epub_path
        self.lesson_path = lesson_path or epub_path.parent
        self.temp_dir = None
        self.content_dir = None

    def parse(self) -> CourseContext:
        """Parse EPUB and extract course structure."""
        print(f"Parsing EPUB: {self.epub_path.name}")

        self._extract_epub()

        course_code, course_title, version = self._extract_metadata()
        exercises = self._find_exercises()

        print(f"   Found {len(exercises)} exercises")

        return CourseContext(
            course_code=course_code,
            course_title=course_title,
            version=version,
            pattern="EPUB-based",
            epub_path=self.epub_path,
            exercises=exercises,
        )

    def _extract_epub(self):
        """Extract EPUB to temporary directory."""
        self.temp_dir = tempfile.mkdtemp(prefix="epub_qa_")
        self.content_dir = Path(self.temp_dir) / "EPUB"

        with zipfile.ZipFile(self.epub_path, 'r') as zip_ref:
            zip_ref.extractall(self.temp_dir)

    def _extract_metadata(self) -> Tuple[str, str, str]:
        """Extract course code, title, and version from EPUB."""
        filename = self.epub_path.stem
        parts = filename.split('-')

        course_code = parts[0] if parts else "UNKNOWN"
        version = parts[1] if len(parts) > 1 else "1.0"
        course_title = f"{course_code} Course"

        opf_path = self.content_dir / "content.opf"
        if opf_path.exists():
            try:
                with open(opf_path, 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f, 'xml')
                    title_elem = soup.find('dc:title')
                    if title_elem:
                        course_title = title_elem.text.strip()
            except Exception:
                pass

        return course_code, course_title, version

    def _find_exercises(self) -> List[ExerciseContext]:
        """Find all exercises in EPUB."""
        exercises = []
        if not self.content_dir.exists():
            return exercises

        for html_file in self.content_dir.glob("*.xhtml"):
            exercises.extend(self._parse_chapter_file(html_file))
        for html_file in self.content_dir.glob("*.html"):
            exercises.extend(self._parse_chapter_file(html_file))

        return exercises

    def _parse_chapter_file(self, file_path: Path) -> List[ExerciseContext]:
        """Parse a chapter file to find exercises."""
        exercises = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')

            elements = soup.find_all(['section', 'h2', 'h3'])
            for element in elements:
                section_id = element.get('id', '')
                if section_id.endswith('-ge'):
                    base_id = section_id.removesuffix('-ge')
                    exercises.append(self._create_exercise_context(
                        base_id, ExerciseType.GUIDED_EXERCISE, element, file_path))
                elif section_id.endswith('-lab'):
                    base_id = section_id.removesuffix('-lab')
                    exercises.append(self._create_exercise_context(
                        base_id, ExerciseType.LAB, element, file_path))
        except Exception as e:
            print(f"   Warning: Error parsing {file_path.name}: {e}")

        return exercises

    def _create_exercise_context(self, exercise_id: str, ex_type: ExerciseType,
                                  section, file_path: Path) -> ExerciseContext:
        """Create ExerciseContext from parsed HTML section."""
        title_elem = section.find(['h1', 'h2', 'h3'])
        title = title_elem.text.strip() if title_elem else exercise_id

        chapter_keyword = file_path.stem
        lesson_code = self.lesson_path.name if self.lesson_path else "unknown"

        solution_files = self._find_solution_files(exercise_id)
        grading_script = self._find_grading_script(exercise_id)
        materials_dir = self._find_materials_dir(exercise_id)

        return ExerciseContext(
            id=exercise_id,
            type=ex_type,
            lesson_code=lesson_code,
            chapter=1,
            chapter_title=chapter_keyword.title(),
            title=title,
            lesson_path=self.lesson_path,
            solution_files=solution_files,
            grading_script=grading_script,
            materials_dir=materials_dir,
        )

    def _find_solution_files(self, exercise_id: str) -> List[Path]:
        """Find solution files for an exercise."""
        solution_files = []
        if not self.lesson_path:
            return solution_files

        base_id_underscore = exercise_id.replace('-', '_')

        def collect_solutions(solutions_dir: Path):
            if not solutions_dir.exists():
                return
            for f in solutions_dir.rglob("*"):
                if f.is_file() and not f.name.startswith('.'):
                    solution_files.append(f)

        lesson_lower = self.lesson_path.name.lower()

        for eid in [exercise_id, base_id_underscore]:
            # Pattern 1: materials/labs/<exercise>/solutions/
            collect_solutions(self.lesson_path / "materials" / "labs" / eid / "solutions")
            # Pattern 2: grading/src/<lesson>/materials/labs/<exercise>/solutions/
            collect_solutions(self.lesson_path / "classroom" / "grading" / "src" / lesson_lower / "materials" / "labs" / eid / "solutions")
            # Pattern 3: grading/src/<lesson>/materials/solutions/<exercise>/
            collect_solutions(self.lesson_path / "classroom" / "grading" / "src" / lesson_lower / "materials" / "solutions" / eid)

        return sorted(set(solution_files))

    def _find_grading_script(self, exercise_id: str) -> Optional[Path]:
        """Find grading script for an exercise."""
        if not self.lesson_path:
            return None

        base_id_underscore = exercise_id.replace('-', '_')

        lesson_lower = self.lesson_path.name.lower()
        grading_dir = self.lesson_path / "classroom" / "grading" / "src" / lesson_lower

        if grading_dir.exists():
            for script_id in [exercise_id, base_id_underscore]:
                for ext in ['.sh', '.py']:
                    grade_script = grading_dir / f"grade_{script_id}{ext}"
                    if grade_script.exists():
                        return grade_script

                module_py = grading_dir / f"{script_id}.py"
                if module_py.exists():
                    try:
                        content = module_py.read_text()
                        if 'def grade' in content or 'class ' in content:
                            return module_py
                    except Exception:
                        pass

        return None

    def _find_materials_dir(self, exercise_id: str) -> Optional[Path]:
        """Find materials directory for an exercise."""
        if not self.lesson_path:
            return None

        base_id_underscore = exercise_id.replace('-', '_')
        lesson_lower = self.lesson_path.name.lower()

        for eid in [exercise_id, base_id_underscore]:
            for path in [
                self.lesson_path / "materials" / "labs" / eid,
                self.lesson_path / "classroom" / "grading" / "src" / lesson_lower / "materials" / "labs" / eid,
                self.lesson_path / "classroom" / "grading" / "src" / lesson_lower / "materials" / "git_repos" / eid,
            ]:
                if path.exists():
                    return path
        return None

    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Instruction Extractor
# ---------------------------------------------------------------------------

class InstructionExtractor:
    """Extracts executable instructions from EPUB exercise content."""

    def __init__(self, epub_path: Path):
        self.epub_path = epub_path
        self.temp_dir = None
        self.content_dir = None

    def extract(self, exercise_id: str) -> Optional[ExerciseInstructions]:
        """Extract instructions for a specific exercise."""
        self._extract_epub()

        exercise_content = self._find_exercise_content(exercise_id)
        if not exercise_content:
            self.cleanup()
            return None

        return self._parse_exercise_content(exercise_id, exercise_content)

    def extract_all(self) -> Dict[str, ExerciseInstructions]:
        """Extract instructions for all exercises in the EPUB."""
        self._extract_epub()
        exercises = {}

        for html_file in self.content_dir.glob("*.xhtml"):
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f, 'html.parser')

                for section in soup.find_all(['h2', 'section']):
                    section_id = section.get('id', '')
                    if section_id.endswith('-ge'):
                        base_id = section_id.removesuffix('-ge')
                        instructions = self._parse_exercise_content(base_id, section)
                        if instructions:
                            exercises[base_id] = instructions
                    elif section_id.endswith('-lab'):
                        base_id = section_id.removesuffix('-lab')
                        instructions = self._parse_exercise_content(base_id, section)
                        if instructions:
                            exercises[base_id] = instructions
            except Exception as e:
                print(f"   Warning: Error parsing {html_file.name}: {e}")

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
        """Find exercise content section in EPUB.

        Exercise IDs are stored without -ge/-lab suffix, but the EPUB HTML
        uses section IDs with the suffix. Try both forms.
        """
        if not self.content_dir.exists():
            return None

        # Try: exact id, id-ge, id-lab
        candidates = [exercise_id, f"{exercise_id}-ge", f"{exercise_id}-lab"]

        for html_file in self.content_dir.glob("*.xhtml"):
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f, 'html.parser')
                for candidate_id in candidates:
                    element = soup.find(id=candidate_id)
                    if element:
                        return element
            except Exception:
                continue
        return None

    def _parse_exercise_content(self, exercise_id: str, element: Tag) -> ExerciseInstructions:
        """Parse exercise content into structured instructions."""
        instructions = ExerciseInstructions(
            exercise_id=exercise_id,
            title=self._extract_title(element),
        )

        current = element
        while current:
            current = current.find_next_sibling()
            if not current:
                break
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

        def count_actions(steps):
            total = 0
            for step in steps:
                total += len(step.commands) + len(step.file_actions)
                total += count_actions(step.sub_steps)
            return total

        instructions.total_commands = count_actions(instructions.steps)
        return instructions

    def _extract_title(self, element: Tag) -> str:
        """Extract exercise title."""
        title_elem = element.find(class_='title')
        if title_elem:
            return re.sub(r'\s+', ' ', title_elem.get_text(' ', strip=True))
        return re.sub(r'\s+', ' ', element.get_text(' ', strip=True))

    def _parse_outcomes(self, section: Tag) -> List[str]:
        """Parse outcomes list."""
        return [li.get_text(strip=True) for li in section.find_all('li')
                if li.get_text(strip=True)]

    def _parse_prerequisites(self, section: Tag) -> Optional[str]:
        """Parse prerequisites to find lab start command."""
        for pre in section.find_all('pre'):
            text = pre.get_text()
            if 'lab start' in text:
                match = re.search(r'lab start(?:\s+-t\s+[\w-]+)?\s+[\w-]+', text)
                if match:
                    return match.group()
        return None

    def _parse_instructions(self, section: Tag) -> List[InstructionStep]:
        """Parse the instructions section into steps."""
        steps = []
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
        principal = li.find(class_='principal', recursive=False)
        if not principal:
            principal = li.find(class_='principal')

        if principal:
            text = re.sub(r'\s+', ' ', principal.get_text(' ', strip=True))
        else:
            text = ''
            for child in li.children:
                if isinstance(child, str):
                    text = child.strip()
                    break
                elif child.name == 'span':
                    text = re.sub(r'\s+', ' ', child.get_text(' ', strip=True))
                    break

        step = InstructionStep(number=number, text=text)

        verification_keywords = ['verify', 'confirm', 'check', 'ensure', 'validate']
        step.is_verification = any(kw in text.lower() for kw in verification_keywords)

        # Find commands and file content in code blocks
        for figure in li.find_all('figure', class_='listing', recursive=False):
            for pre in figure.find_all('pre'):
                cmds = self._parse_code_block(pre)
                if cmds:
                    step.commands.extend(cmds)
                elif self._is_file_content_block(pre):
                    filename = self._extract_filename_from_context(figure, li)
                    if filename:
                        file_action = self._parse_file_block(pre, filename)
                        if file_action:
                            step.file_actions.append(file_action)

        for pre in li.find_all('pre', recursive=False):
            cmds = self._parse_code_block(pre)
            if cmds:
                step.commands.extend(cmds)
            elif self._is_file_content_block(pre):
                filename = self._extract_filename_from_context(pre, li)
                if filename:
                    file_action = self._parse_file_block(pre, filename)
                    if file_action:
                        step.file_actions.append(file_action)

        # Parse sub-steps
        nested_ols = li.find_all('ol', recursive=False)
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

    def _is_file_content_block(self, pre: Tag) -> bool:
        """Check if a <pre> block contains file content (not a shell command).

        File content blocks have:
        - No <strong> tags (commands use <strong> for user-typed text)
        - No shell prompt patterns at line starts
        - Actual content (not empty)
        """
        if pre.find('strong'):
            return False

        text = pre.get_text()
        if not text or not text.strip():
            return False

        first_line = text.strip().split('\n')[0].strip()

        # Shell prompt patterns — if present, this is command output, not file content
        prompt_patterns = [
            r'^[\$#]\s',
            r'^\[.*@.*\][\$#]\s',
            r'^.*@.*:.*[\$#]\s',
            r'^➜\s',
            r'^student@',
            r'^user@host',
            r'^root@',
        ]
        for pattern in prompt_patterns:
            if re.match(pattern, first_line):
                return False

        return True

    def _extract_filename_from_context(self, element: Tag, step_element: Tag) -> Optional[str]:
        """Extract target filename from prose context near a file content block.

        Walks backward through preceding siblings of the element to find filename
        references in <code class="literal"> tags within surrounding prose.
        Only matches when the prose clearly indicates the following block is
        file content to write (not a code snippet being described).
        """
        # Walk backward through preceding siblings collecting signals:
        # - Content keywords ("must contain", "following content", etc.)
        # - Filenames in <code class="literal"> tags
        has_content_keyword = False
        found_filename = None

        for sibling in element.previous_siblings:
            if not isinstance(sibling, Tag):
                continue

            # Don't look past another figure (that would be a different block's context)
            if sibling.name == 'figure':
                break

            text = sibling.get_text().lower()

            # Check for content keywords
            if self._has_content_keywords(text):
                has_content_keyword = True

            # Check for filename
            if not found_filename:
                found_filename = self._find_filename_in_element(sibling)

        # If we found content keywords AND a filename in the preceding context, use it
        if has_content_keyword and found_filename:
            return found_filename

        # Strategy 2: Check the step's principal text for file creation language
        principal = step_element.find(class_='principal', recursive=False)
        if not principal:
            principal = step_element.find(class_='principal')
        if principal:
            text = principal.get_text().lower()

            # Content keywords in principal text
            if self._has_content_keywords(text):
                filename = self._find_filename_in_element(principal)
                if filename:
                    return filename

            # File creation/placement language in principal
            if self._has_create_keywords(text):
                filename = self._find_filename_in_element(principal)
                if filename:
                    return filename

            # If preceding sibling had content keywords but no filename,
            # check the principal for the filename
            if has_content_keyword:
                filename = self._find_filename_in_element(principal)
                if filename:
                    return filename

        return None

    @staticmethod
    def _has_content_keywords(text: str) -> bool:
        """Check if text contains keywords indicating the following block is file content."""
        content_keywords = [
            'must consist of', 'must contain', 'following content',
            'beginning of the file', 'the completed',
        ]
        return any(kw in text for kw in content_keywords)

    @staticmethod
    def _has_create_keywords(text: str) -> bool:
        """Check if text contains file creation/placement language (not task-adding)."""
        create_keywords = [
            'create a ', 'create the ',
            'edit the ', 'modify the ', 'update the ',
            'place the contents', 'into the ', 'into a new',
            'copy the ', 'replace the ',
        ]
        snippet_keywords = [
            'add a task', 'add the task', 'add another task',
            'add the second', 'add the third', 'add the fourth',
            'add a second', 'add a third',
            'put the following lines',
        ]
        has_create = any(kw in text for kw in create_keywords)
        has_snippet = any(kw in text for kw in snippet_keywords)
        return has_create and not has_snippet

    def _find_filename_in_element(self, element: Tag) -> Optional[str]:
        """Find a filename in <code class="literal"> tags within an element."""
        file_extensions = (
            '.yml', '.yaml', '.json', '.cfg', '.conf', '.ini', '.txt',
            '.py', '.sh', '.j2', '.jinja2', '.html', '.xml', '.toml',
            '.repo',
        )

        # Collect all candidate filenames, prefer the LAST one
        # (closer to the file content block)
        candidates = []
        for code in element.find_all('code', class_='literal'):
            code_text = code.get_text(strip=True)
            # Skip module paths (e.g., ansible.builtin.service)
            if code_text.count('.') > 1:
                continue
            if any(code_text.endswith(ext) for ext in file_extensions):
                candidates.append(code_text)

        return candidates[-1] if candidates else None

    def _parse_file_block(self, pre: Tag, filename: str) -> Optional[FileAction]:
        """Parse a file content block into a FileAction."""
        content = pre.get_text()
        if not content or not content.strip():
            return None

        # Check for ...output omitted... indicating partial content
        has_omission = bool(pre.find('em', string=re.compile(r'output omitted', re.I)))
        action_type = FileActionType.MODIFY if has_omission else FileActionType.CREATE

        # For MODIFY blocks, skip — we can't reliably apply partial content
        if action_type == FileActionType.MODIFY:
            return None

        # Clean up the content — remove any trailing/leading blank lines
        # but preserve internal whitespace/indentation
        lines = content.split('\n')
        # Strip leading empty lines
        while lines and not lines[0].strip():
            lines.pop(0)
        # Strip trailing empty lines
        while lines and not lines[-1].strip():
            lines.pop()

        content = '\n'.join(lines)
        if not content.strip():
            return None

        # Skip indented snippets — if the first meaningful line starts with 4+
        # spaces, this is likely a task/section snippet, not a complete file
        first_line = lines[0] if lines else ''
        leading_spaces = len(first_line) - len(first_line.lstrip())
        if leading_spaces >= 4:
            return None

        # Ensure file ends with newline
        if not content.endswith('\n'):
            content += '\n'

        return FileAction(
            filename=filename,
            content=content,
            action_type=action_type,
            context_text=f"Write {filename}",
        )

    def _parse_code_block(self, pre: Tag) -> List[Command]:
        """Parse a code block to extract commands."""
        commands = []
        strong_elements = pre.find_all('strong')

        cmd_parts = []
        for strong in strong_elements:
            cmd_text = strong.get_text(strip=True)
            if not cmd_text:
                continue

            # Skip prompts, passwords, and non-command content
            skip_patterns = [
                'redhat', 'admin', 'student', 'yes', 'no', 'y', 'n',
                'Student@123', 'password', 'Password',
            ]
            if cmd_text in skip_patterns:
                continue
            if cmd_text.startswith('- ') or cmd_text.startswith('key:') or cmd_text.startswith('value:'):
                continue
            if '@' in cmd_text and ' ' not in cmd_text and len(cmd_text) < 20:
                continue

            # Skip verification patterns (grep patterns for checking output)
            # These are output snippets students should observe, not commands to execute
            verification_patterns = [
                r'^changed=\d+',           # changed=1, changed=2
                r'^ok=\d+',                # ok=1, ok=2
                r'^failed=\d+',            # failed=1, failed=2
                r'^skipped=\d+',           # skipped=1
                r'^rescued=\d+',           # rescued=1
                r'^ignored=\d+',           # ignored=1
                r'^FAILED!',               # FAILED! =>
                r'^fatal:',                # fatal: [host]
                r'^changed:\s*\[',         # changed: [hostname]
                r'^ok:\s*\[',              # ok: [hostname]
                r'^failed:\s*\[',          # failed: [hostname]
                r'^skipped:\s*\[',         # skipped: [hostname]
                r'^PLAY\s+\[',             # PLAY [playbook name]
                r'^TASK\s+\[',             # TASK [task name]
                r'^ERROR!',                # ERROR! message
                r'^\{.*"changed"',         # {"changed": false...}
                r'^install_package:',      # Variable assignments in examples
                r'^ignore_errors:',        # YAML directives shown as examples
            ]

            is_verification = False
            for pattern in verification_patterns:
                if re.match(pattern, cmd_text):
                    is_verification = True
                    break

            if is_verification:
                continue

            cmd_parts.append(cmd_text)

        if not cmd_parts:
            return commands

        # Build commands, joining continuation lines (ending with \)
        current_cmd = []
        final_commands = []

        for part in cmd_parts:
            current_cmd.append(part)
            if not part.rstrip().endswith('\\'):
                full_cmd = ' '.join(current_cmd)
                full_cmd = re.sub(r'\\\s+', ' ', full_cmd)
                full_cmd = re.sub(r'\s+', ' ', full_cmd).strip()
                if full_cmd:
                    final_commands.append(full_cmd)
                current_cmd = []

        if current_cmd:
            full_cmd = ' '.join(current_cmd)
            full_cmd = re.sub(r'\\\s+', ' ', full_cmd)
            full_cmd = re.sub(r'\s+', ' ', full_cmd).strip()
            if full_cmd:
                final_commands.append(full_cmd)

        # Check for interactive prompts
        is_interactive = False
        prompts = []
        parent_text = pre.get_text()
        if 'Username:' in parent_text or 'Password:' in parent_text:
            is_interactive = True
            for pattern, prompt in [
                (r'Username:\s*(\S+)', 'Username:'),
                (r'Password:\s*(\S+)', 'Password:'),
            ]:
                match = re.search(pattern, parent_text)
                if match:
                    prompts.append((prompt, match.group(1)))

        for cmd_text in final_commands:
            commands.append(Command(
                text=cmd_text,
                is_interactive=is_interactive,
                prompts=prompts if is_interactive else [],
            ))

        return commands

    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None
            self.content_dir = None


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def extract_instructions(epub_path: Path, exercise_id: str) -> Optional[ExerciseInstructions]:
    """Extract instructions for a specific exercise from an EPUB."""
    extractor = InstructionExtractor(epub_path)
    try:
        return extractor.extract(exercise_id)
    finally:
        extractor.cleanup()
