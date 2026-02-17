#!/usr/bin/env python3
"""EPUB extraction, parsing, and instruction extraction.

All output is JSON to stdout, diagnostics to stderr.
Caches extraction to /tmp/eqa-epub-<md5>/ to avoid re-extracting.

Usage:
    python3 epub_tool.py parse <epub_path> [--lesson-path <path>]
    python3 epub_tool.py instructions <epub_path> <exercise_id>
    python3 epub_tool.py build <course_path> [--force]
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# Lazy-loaded at first use
_bs4_loaded = False
Tag = None
BeautifulSoup = None


def _ensure_bs4():
    global _bs4_loaded, Tag, BeautifulSoup
    if not _bs4_loaded:
        from bs4 import BeautifulSoup as BS, Tag as T
        BeautifulSoup = BS
        Tag = T
        _bs4_loaded = True


def _output(data):
    print(json.dumps(data, default=str))


def _err(msg):
    print(msg, file=sys.stderr)


def _epub_cache_dir(epub_path: str) -> str:
    """Get or create cached extraction directory for an EPUB."""
    md5 = hashlib.md5(epub_path.encode()).hexdigest()[:12]
    cache_dir = f"/tmp/eqa-epub-{md5}"
    if not os.path.exists(cache_dir) or not os.path.exists(os.path.join(cache_dir, "EPUB")):
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
        os.makedirs(cache_dir, exist_ok=True)
        with zipfile.ZipFile(epub_path, 'r') as zf:
            zf.extractall(cache_dir)
        _err(f"Extracted EPUB to {cache_dir}")
    return cache_dir


def _find_exercises(content_dir: str, lesson_path: str = None):
    """Find all exercises in extracted EPUB content."""
    _ensure_bs4()

    exercises = []
    content_path = Path(content_dir)

    for html_file in sorted(list(content_path.glob("*.xhtml")) + list(content_path.glob("*.html"))):
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')

            for section in soup.find_all('section'):
                classes = section.get('class', [])
                if not isinstance(classes, list):
                    classes = classes.split()
                if 'sect2' not in classes:
                    continue

                is_ge = 'ge' in classes
                is_lab = 'lab' in classes
                if not is_ge and not is_lab:
                    continue

                ex_type = "GE" if is_ge else "Lab"

                # Extract exercise ID from 'lab start <name>'
                exercise_id = None
                for pre in section.find_all('pre'):
                    text = pre.get_text()
                    if 'lab start' in text:
                        match = re.search(r'lab start(?:\s+-t\s+[\w-]+)?\s+([\w-]+)', text)
                        if match:
                            exercise_id = match.group(1)
                            break

                if not exercise_id:
                    continue

                # Extract title
                title_elem = section.find(['h1', 'h2', 'h3'])
                title = title_elem.text.strip() if title_elem else exercise_id

                # Find solution files
                solution_files = _find_solution_files(exercise_id, lesson_path) if lesson_path else []

                exercises.append({
                    "id": exercise_id,
                    "type": ex_type,
                    "title": re.sub(r'\s+', ' ', title),
                    "chapter_file": html_file.name,
                    "solution_files": solution_files,
                })
        except Exception as e:
            _err(f"Warning: Error parsing {html_file.name}: {e}")

    return exercises


def _find_solution_files(exercise_id: str, lesson_path: str) -> list:
    """Find solution files for an exercise."""
    if not lesson_path:
        return []

    lesson = Path(lesson_path)
    base_id_underscore = exercise_id.replace('-', '_')
    lesson_lower = lesson.name.lower()
    solution_files = []

    def collect(solutions_dir: Path):
        if not solutions_dir.exists():
            return
        for f in solutions_dir.rglob("*"):
            if f.is_file() and not f.name.startswith('.'):
                solution_files.append(str(f))

    for eid in [exercise_id, base_id_underscore]:
        collect(lesson / "materials" / "labs" / eid / "solutions")
        collect(lesson / "classroom" / "grading" / "src" / lesson_lower / "materials" / "labs" / eid / "solutions")
        collect(lesson / "classroom" / "grading" / "src" / lesson_lower / "materials" / "solutions" / eid)

    return sorted(set(solution_files))


def cmd_parse(args):
    """Parse EPUB and return course structure."""
    _ensure_bs4()

    epub_path = os.path.abspath(args.epub_path)
    if not os.path.exists(epub_path):
        _output({"success": False, "error": f"EPUB not found: {epub_path}"})
        return

    cache_dir = _epub_cache_dir(epub_path)
    content_dir = os.path.join(cache_dir, "EPUB")

    if not os.path.exists(content_dir):
        _output({"success": False, "error": "EPUB has no EPUB/ directory"})
        return

    # Extract metadata
    filename = Path(epub_path).stem
    parts = filename.split('-')
    course_code = parts[0] if parts else "UNKNOWN"
    version = parts[1] if len(parts) > 1 else "1.0"
    course_title = f"{course_code} Course"

    opf_path = os.path.join(content_dir, "content.opf")
    if os.path.exists(opf_path):
        try:
            with open(opf_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'xml')
                title_elem = soup.find('dc:title')
                if title_elem:
                    course_title = title_elem.text.strip()
        except Exception:
            pass

    lesson_path = args.lesson_path or str(Path(epub_path).parent)
    exercises = _find_exercises(content_dir, lesson_path)

    _output({
        "success": True,
        "course_code": course_code,
        "course_title": course_title,
        "version": version,
        "exercises": exercises,
        "extract_dir": cache_dir,
        "epub_path": epub_path,
    })


def cmd_instructions(args):
    """Extract step-by-step instructions for a specific exercise."""
    _ensure_bs4()

    epub_path = os.path.abspath(args.epub_path)
    if not os.path.exists(epub_path):
        _output({"success": False, "error": f"EPUB not found: {epub_path}"})
        return

    cache_dir = _epub_cache_dir(epub_path)
    content_dir = Path(cache_dir) / "EPUB"
    exercise_id = args.exercise_id

    # Find exercise section
    section = None
    for html_file in sorted(list(content_dir.glob("*.xhtml")) + list(content_dir.glob("*.html"))):
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')

            for s in soup.find_all('section'):
                classes = s.get('class', [])
                if not isinstance(classes, list):
                    classes = classes.split()
                if 'sect2' not in classes:
                    continue
                if 'ge' not in classes and 'lab' not in classes:
                    continue

                for pre in s.find_all('pre'):
                    text = pre.get_text()
                    if re.search(
                        rf'lab start(?:\s+-t\s+[\w-]+)?\s+{re.escape(exercise_id)}\b',
                        text,
                    ):
                        section = s
                        break
                if section:
                    break
        except Exception:
            continue
        if section:
            break

    if not section:
        _output({"success": False, "error": f"Exercise {exercise_id} not found in EPUB"})
        return

    # Parse the exercise content
    result = _parse_exercise(exercise_id, section)
    _output(result)


def _parse_exercise(exercise_id: str, element) -> dict:
    """Parse exercise content into structured instructions."""
    # Extract title
    h2 = element.find('h2')
    if h2:
        title = re.sub(r'\s+', ' ', h2.get_text(' ', strip=True))
    else:
        title_elem = element.find(class_='title')
        title = re.sub(r'\s+', ' ', title_elem.get_text(' ', strip=True)) if title_elem else exercise_id

    outcomes = []
    prerequisites_command = None
    steps = []

    for child in element.find_all('section', recursive=False):
        h3 = child.find('h3')
        heading_text = h3.get_text(strip=True).lower() if h3 else ''
        classes = child.get('class', [])
        if not isinstance(classes, list):
            classes = classes.split()

        if 'outcomes' in heading_text or 'Outcomes' in classes:
            outcomes = [li.get_text(strip=True) for li in child.find_all('li')
                        if li.get_text(strip=True)]
        elif 'prerequisites' in heading_text or 'Prerequisites' in classes:
            for pre in child.find_all('pre'):
                text = pre.get_text()
                if 'lab start' in text:
                    match = re.search(r'lab start(?:\s+-t\s+[\w-]+)?\s+[\w-]+', text)
                    if match:
                        prerequisites_command = match.group()
        elif ('instructions' in heading_text or 'Checklist' in classes or 'Lab' in classes):
            ol = child.find('ol', class_='arabic')
            if ol:
                step_num = 1
                for li in ol.find_all('li', recursive=False):
                    step = _parse_step(li, str(step_num))
                    if step:
                        steps.append(step)
                    step_num += 1

    # Count total commands
    def count_actions(step_list):
        total = 0
        for s in step_list:
            total += len(s.get("commands", []))
            total += len(s.get("file_actions", []))
            total += count_actions(s.get("sub_steps", []))
        return total

    return {
        "success": True,
        "exercise_id": exercise_id,
        "title": title,
        "outcomes": outcomes,
        "prerequisites_command": prerequisites_command,
        "steps": steps,
        "total_commands": count_actions(steps),
    }


def _parse_step(li, number: str) -> dict:
    """Parse a single instruction step."""
    # Extract principal text
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
            elif hasattr(child, 'name') and child.name == 'span':
                text = re.sub(r'\s+', ' ', child.get_text(' ', strip=True))
                break

    verification_keywords = ['verify', 'confirm', 'check', 'ensure', 'validate']
    is_verification = any(kw in text.lower() for kw in verification_keywords)

    commands = []
    file_actions = []

    # Find commands in figure/listing blocks
    for figure in li.find_all('figure', class_='listing', recursive=False):
        for pre in figure.find_all('pre'):
            cmds = _parse_code_block(pre)
            if cmds:
                commands.extend(cmds)
            elif _is_file_content_block(pre):
                filename = _extract_filename(figure, li)
                if filename:
                    fa = _parse_file_block(pre, filename)
                    if fa:
                        file_actions.append(fa)

    # Find commands in direct pre blocks
    for pre in li.find_all('pre', recursive=False):
        cmds = _parse_code_block(pre)
        if cmds:
            commands.extend(cmds)
        elif _is_file_content_block(pre):
            filename = _extract_filename(pre, li)
            if filename:
                fa = _parse_file_block(pre, filename)
                if fa:
                    file_actions.append(fa)

    # Parse sub-steps
    sub_steps = []
    nested_ols = li.find_all('ol', recursive=False)
    for div in li.find_all('div', class_='ordered-list', recursive=False):
        nested_ols.extend(div.find_all('ol', recursive=False))

    for nested_ol in nested_ols:
        step_letter = 'a'
        for nested_li in nested_ol.find_all('li', recursive=False):
            sub_step = _parse_step(nested_li, f"{number}.{step_letter}")
            if sub_step:
                sub_steps.append(sub_step)
            step_letter = chr(ord(step_letter) + 1)

    return {
        "number": number,
        "text": text,
        "is_verification": is_verification,
        "commands": commands,
        "file_actions": file_actions,
        "sub_steps": sub_steps,
    }


def _is_file_content_block(pre) -> bool:
    """Check if a <pre> block contains file content (not a command)."""
    if pre.find('strong'):
        return False

    text = pre.get_text()
    if not text or not text.strip():
        return False

    first_line = text.strip().split('\n')[0].strip()
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


def _extract_filename(element, step_element) -> str:
    """Extract target filename from prose context near a file content block."""
    has_content_keyword = False
    found_filename = None

    content_keywords = [
        'must consist of', 'must contain', 'following content',
        'beginning of the file', 'the completed',
    ]
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

    file_extensions = (
        '.yml', '.yaml', '.json', '.cfg', '.conf', '.ini', '.txt',
        '.py', '.sh', '.j2', '.jinja2', '.html', '.xml', '.toml', '.repo',
    )

    def find_filename_in(elem):
        candidates = []
        for code in elem.find_all('code', class_='literal'):
            code_text = code.get_text(strip=True)
            if code_text.count('.') > 1:
                continue
            if any(code_text.endswith(ext) for ext in file_extensions):
                candidates.append(code_text)
        return candidates[-1] if candidates else None

    for sibling in element.previous_siblings:
        if not isinstance(sibling, Tag):
            continue
        if sibling.name == 'figure':
            break
        text = sibling.get_text().lower()
        if any(kw in text for kw in content_keywords):
            has_content_keyword = True
        if not found_filename:
            found_filename = find_filename_in(sibling)

    if has_content_keyword and found_filename:
        return found_filename

    principal = step_element.find(class_='principal', recursive=False)
    if not principal:
        principal = step_element.find(class_='principal')
    if principal:
        text = principal.get_text().lower()
        if any(kw in text for kw in content_keywords):
            fn = find_filename_in(principal)
            if fn:
                return fn
        has_create = any(kw in text for kw in create_keywords)
        has_snippet = any(kw in text for kw in snippet_keywords)
        if has_create and not has_snippet:
            fn = find_filename_in(principal)
            if fn:
                return fn
        if has_content_keyword:
            fn = find_filename_in(principal)
            if fn:
                return fn

    return None


def _parse_file_block(pre, filename: str) -> dict:
    """Parse file content block into a file action."""
    content = pre.get_text()
    if not content or not content.strip():
        return None

    # Check for partial content
    has_omission = bool(pre.find('em', string=re.compile(r'output omitted', re.IGNORECASE)))
    if has_omission:
        return None

    lines = content.split('\n')
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    content = '\n'.join(lines)
    if not content.strip():
        return None

    # Skip indented snippets
    first_line = lines[0] if lines else ''
    leading_spaces = len(first_line) - len(first_line.lstrip())
    if leading_spaces >= 4:
        return None

    if not content.endswith('\n'):
        content += '\n'

    return {
        "filename": filename,
        "content": content,
        "action_type": "create",
    }


def _parse_code_block(pre) -> list:
    """Parse a code block to extract commands."""
    commands = []
    strong_elements = pre.find_all('strong')

    cmd_parts = []
    for strong in strong_elements:
        cmd_text = strong.get_text(strip=True)
        if not cmd_text:
            continue

        # Skip prompts, passwords, non-commands
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

        # Skip verification output patterns
        verification_patterns = [
            r'^changed=\d+', r'^ok=\d+', r'^failed=\d+',
            r'^skipped=\d+', r'^rescued=\d+', r'^ignored=\d+',
            r'^FAILED!', r'^fatal:', r'^changed:\s*\[', r'^ok:\s*\[',
            r'^failed:\s*\[', r'^skipped:\s*\[', r'^PLAY\s+\[',
            r'^TASK\s+\[', r'^ERROR!', r'^\{.*"changed"',
            r'^install_package:', r'^ignore_errors:',
        ]
        if any(re.match(p, cmd_text) for p in verification_patterns):
            continue

        cmd_parts.append(cmd_text)

    if not cmd_parts:
        return commands

    # Join continuation lines
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
                prompts.append([prompt, match.group(1)])

    for cmd_text in final_commands:
        commands.append({
            "text": cmd_text,
            "is_interactive": is_interactive,
            "prompts": prompts if is_interactive else [],
        })

    return commands


def cmd_summary(args):
    """Summarize exercise testability — which steps have commands vs GUI-only."""
    _ensure_bs4()

    epub_path = os.path.abspath(args.epub_path)
    if not os.path.exists(epub_path):
        _output({"success": False, "error": f"EPUB not found: {epub_path}"})
        return

    cache_dir = _epub_cache_dir(epub_path)
    content_dir = os.path.join(cache_dir, "EPUB")
    lesson_path = args.lesson_path or str(Path(epub_path).parent)

    exercises = _find_exercises(content_dir, lesson_path)
    summaries = []

    for ex in exercises:
        exercise_id = ex["id"]

        # Find exercise section
        section = None
        content_path = Path(content_dir)
        for html_file in sorted(list(content_path.glob("*.xhtml")) + list(content_path.glob("*.html"))):
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f, 'html.parser')
                for s in soup.find_all('section'):
                    classes = s.get('class', [])
                    if not isinstance(classes, list):
                        classes = classes.split()
                    if 'sect2' not in classes:
                        continue
                    for pre in s.find_all('pre'):
                        if re.search(rf'lab start(?:\s+-t\s+[\w-]+)?\s+{re.escape(exercise_id)}\b', pre.get_text()):
                            section = s
                            break
                    if section:
                        break
            except Exception:
                continue
            if section:
                break

        if not section:
            summaries.append({"id": exercise_id, "type": ex["type"], "error": "not found in EPUB"})
            continue

        parsed = _parse_exercise(exercise_id, section)

        def classify_steps(steps):
            total = 0
            gui_only = 0
            with_commands = 0
            with_files = 0
            total_cmds = 0
            total_files = 0
            for s in steps:
                total += 1
                cmds = len(s.get("commands", []))
                files = len(s.get("file_actions", []))
                total_cmds += cmds
                total_files += files
                if cmds > 0:
                    with_commands += 1
                elif files > 0:
                    with_files += 1
                else:
                    gui_only += 1
                sub = classify_steps(s.get("sub_steps", []))
                total += sub["total"]
                gui_only += sub["gui_only"]
                with_commands += sub["with_commands"]
                with_files += sub["with_files"]
                total_cmds += sub["total_commands"]
                total_files += sub["total_files"]
            return {
                "total": total, "gui_only": gui_only,
                "with_commands": with_commands, "with_files": with_files,
                "total_commands": total_cmds, "total_files": total_files,
            }

        stats = classify_steps(parsed.get("steps", []))
        summaries.append({
            "id": exercise_id,
            "type": ex["type"],
            "title": parsed.get("title", ""),
            "steps": stats["total"],
            "gui_only_steps": stats["gui_only"],
            "command_steps": stats["with_commands"],
            "file_steps": stats["with_files"],
            "total_commands": stats["total_commands"],
            "total_files": stats["total_files"],
            "has_solutions": len(ex.get("solution_files", [])) > 0,
            "testable": stats["with_commands"] > 0 or stats["with_files"] > 0,
        })

    _output({"success": True, "exercises": summaries})


def cmd_build(args):
    """Build EPUB via sk."""
    course_path = Path(args.course_path).expanduser().resolve()

    if not course_path.exists():
        _output({"success": False, "error": f"Course not found: {course_path}"})
        return

    sk_path = shutil.which("sk")
    if not sk_path:
        for p in ["/usr/bin/sk", "/usr/local/bin/sk"]:
            if os.path.exists(p):
                sk_path = p
                break

    if not sk_path:
        _output({"success": False, "error": "sk tool not found"})
        return

    if not (course_path / "outline.yml").exists():
        _output({"success": False, "error": "Not a scaffolding course (no outline.yml)"})
        return

    if not args.force:
        epub = _find_epub(course_path)
        if epub:
            _output({"success": True, "epub_path": str(epub), "cached": True})
            return

    # Ensure ssh-agent
    try:
        result = subprocess.run(["ssh-add", "-l"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            for key in [Path.home() / ".ssh" / "id_ed25519", Path.home() / ".ssh" / "id_rsa"]:
                if key.exists():
                    subprocess.run(["ssh-add", str(key)], capture_output=True, text=True, timeout=10)
                    break
    except Exception:
        pass

    _err(f"Building EPUB for {course_path.name}...")
    try:
        result = subprocess.run(
            [sk_path, "build", "epub3"],
            cwd=course_path, capture_output=True, text=True, timeout=600,
        )
        if result.returncode == 0:
            epub = _find_epub(course_path)
            if epub:
                _output({"success": True, "epub_path": str(epub)})
                return
            _output({"success": False, "error": "Build completed but EPUB not found"})
        else:
            output = result.stdout + result.stderr
            if "Auth fail" in output or "JSchException" in output:
                _output({"success": False, "error": "SSH auth failed. Run: eval $(ssh-agent) && ssh-add"})
            else:
                _output({"success": False, "error": f"Build failed (exit {result.returncode})",
                         "stdout": result.stdout[-500:], "stderr": result.stderr[-500:]})
    except subprocess.TimeoutExpired:
        _output({"success": False, "error": "Build timed out"})
    except Exception as e:
        _output({"success": False, "error": str(e)})


def _find_epub(directory: Path) -> Path:
    """Find most recent EPUB in directory."""
    for location in [directory, directory / ".cache" / "generated" / "en-US"]:
        if location.exists():
            epubs = list(location.glob("*.epub"))
            if epubs:
                return max(epubs, key=lambda p: p.stat().st_mtime)
    return None


def main():
    parser = argparse.ArgumentParser(description="EPUB tool for eqa")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # parse
    p_parse = subparsers.add_parser("parse")
    p_parse.add_argument("epub_path")
    p_parse.add_argument("--lesson-path", default=None)
    p_parse.set_defaults(func=cmd_parse)

    # instructions
    p_inst = subparsers.add_parser("instructions")
    p_inst.add_argument("epub_path")
    p_inst.add_argument("exercise_id")
    p_inst.set_defaults(func=cmd_instructions)

    # summary
    p_summary = subparsers.add_parser("summary")
    p_summary.add_argument("epub_path")
    p_summary.add_argument("--lesson-path", default=None)
    p_summary.set_defaults(func=cmd_summary)

    # build
    p_build = subparsers.add_parser("build")
    p_build.add_argument("course_path")
    p_build.add_argument("--force", action="store_true")
    p_build.set_defaults(func=cmd_build)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
