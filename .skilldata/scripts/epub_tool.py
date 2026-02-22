#!/usr/bin/env python3
"""EPUB extraction, parsing, and instruction extraction.

All output is JSON to stdout, diagnostics to stderr.
Caches extraction to ~/.cache/eqa/epub-<md5>/ to avoid re-extracting.

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
import zipfile
from pathlib import Path

from eqa_common import _output, _err, get_cache_dir, find_epub, json_safe

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


def _epub_cache_dir(epub_path: str) -> str:
    """Get or create cached extraction directory for an EPUB.

    Cache key includes a hash of this tool's source so that parsing
    bug fixes automatically invalidate stale caches.
    """
    mtime = str(os.path.getmtime(epub_path))
    tool_hash = hashlib.md5(Path(__file__).read_bytes()).hexdigest()[:8]
    md5 = hashlib.md5((epub_path + mtime + tool_hash).encode()).hexdigest()[:12]
    cache_dir = os.path.join(get_cache_dir(), f"epub-{md5}")
    if not os.path.exists(cache_dir) or not os.path.exists(os.path.join(cache_dir, "EPUB")):
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
        os.makedirs(cache_dir, exist_ok=True)
        with zipfile.ZipFile(epub_path, 'r') as zf:
            zf.extractall(cache_dir)
        _err(f"Extracted EPUB to {cache_dir}")
    return cache_dir


_exercise_map_cache = {}


def _build_exercise_map(content_path):
    """Parse all HTML files once. Returns {exercise_id: {section, chapter_file, type, title}}.

    Consolidates the glob+parse+search loop that was previously duplicated
    in _find_exercises(), cmd_instructions(), and cmd_summary().

    Results are cached in-memory keyed by content_path to avoid re-parsing
    within the same process invocation.
    """
    content_key = str(content_path)
    if content_key in _exercise_map_cache:
        return _exercise_map_cache[content_key]

    _ensure_bs4()

    exercise_map = {}
    content_path = Path(content_path)

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

                is_ge = 'ge' in classes
                is_lab = 'lab' in classes
                if not is_ge and not is_lab:
                    continue

                ex_type = "GE" if is_ge else "Lab"

                # Extract exercise ID from 'lab start <name>'
                exercise_id = None
                for pre in s.find_all('pre'):
                    text = pre.get_text()
                    if 'lab start' in text:
                        match = re.search(r'lab start(?:\s+-t\s+[\w-]+)?\s+([\w-]+)', text)
                        if match:
                            exercise_id = match.group(1)
                            break

                if not exercise_id:
                    continue

                # Extract title
                title_elem = s.find(['h1', 'h2', 'h3'])
                title = title_elem.text.strip() if title_elem else exercise_id

                exercise_map[exercise_id] = {
                    "section": s,
                    "chapter_file": html_file.name,
                    "type": ex_type,
                    "title": re.sub(r'\s+', ' ', title),
                }
        except Exception as e:
            _err(f"Warning: Error parsing {html_file.name}: {e}")

    # Validation: warn if HTML files have sections but none matched the
    # expected CSS classes.  This catches silent failures when the EPUB
    # template changes its class names (e.g. sect2, ge, lab).
    if not exercise_map:
        total_sections = 0
        for html_file in sorted(list(content_path.glob("*.xhtml")) + list(content_path.glob("*.html"))):
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f, 'html.parser')
                total_sections += len(soup.find_all('section'))
            except Exception:
                pass
        if total_sections > 0:
            _err(
                f"WARNING: Found {total_sections} <section> elements but "
                f"none matched expected exercise classes (sect2 + ge/lab). "
                f"The EPUB template may have changed its CSS class names."
            )

    _exercise_map_cache[content_key] = exercise_map
    return exercise_map


def _find_exercises(content_dir: str, lesson_path: str = None):
    """Find all exercises in extracted EPUB content."""
    exercise_map = _build_exercise_map(content_dir)

    exercises = []
    for exercise_id, info in exercise_map.items():
        # Find solution files
        solution_files = _find_solution_files(exercise_id, lesson_path) if lesson_path else []

        exercises.append({
            "id": exercise_id,
            "type": info["type"],
            "title": info["title"],
            "chapter_file": info["chapter_file"],
            "solution_files": solution_files,
        })

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


@json_safe
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


@json_safe
def cmd_instructions(args):
    """Extract step-by-step instructions for a specific exercise."""
    _ensure_bs4()

    epub_path = os.path.abspath(args.epub_path)
    if not os.path.exists(epub_path):
        _output({"success": False, "error": f"EPUB not found: {epub_path}"})
        return

    cache_dir = _epub_cache_dir(epub_path)
    content_dir = os.path.join(cache_dir, "EPUB")
    exercise_id = args.exercise_id

    exercise_map = _build_exercise_map(content_dir)
    info = exercise_map.get(exercise_id)

    if not info:
        _output({"success": False, "error": f"Exercise {exercise_id} not found in EPUB"})
        return

    # Parse the exercise content
    result = _parse_exercise(exercise_id, info["section"])
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

    # Parse sub-steps from nested ordered lists
    sub_steps = []
    nested_lists = li.find_all('ol', recursive=False)
    for div in li.find_all('div', class_='ordered-list', recursive=False):
        nested_lists.extend(div.find_all('ol', recursive=False))
    # Also check itemized lists (ul inside div.itemized-list) — some EPUBs use
    # unordered lists for sub-items that contain file content or commands
    for div in li.find_all('div', class_=lambda c: c and 'itemized-list' in c, recursive=False):
        nested_lists.extend(div.find_all('ul', recursive=False))

    for nested_list in nested_lists:
        step_letter = 'a'
        for nested_li in nested_list.find_all('li', recursive=False):
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
    # In command blocks, <strong> wraps what the student types at a prompt.
    # In file content blocks, <strong> highlights new/changed lines.
    # Distinguish by checking the full block context, not just the strong text.
    strong_tags = pre.find_all('strong')
    if strong_tags:
        full_text = pre.get_text()
        first_line = full_text.strip().split('\n')[0].strip() if full_text else ''

        # If the block starts with a shell prompt, it's a command block
        prompt_indicators = [r'^[\$#]\s', r'^\[.*@.*\][\$#]', r'^student@', r'^root@', r'^➜']
        for p in prompt_indicators:
            if re.match(p, first_line):
                return False

        # If the strong text IS the entire meaningful content (typical of commands),
        # and it doesn't look like config/YAML, treat as command
        strong_text = ' '.join(s.get_text(strip=True) for s in strong_tags)
        non_strong_text = full_text.replace(strong_text, '').strip()

        # Command blocks: strong text is the command, non-strong is just prompt/output
        # File content blocks: strong text is a highlighted portion of larger content
        if not non_strong_text or len(non_strong_text) < len(strong_text) * 0.3:
            # Strong text dominates — likely a command block
            return False

        # If we get here, the block has substantial non-strong content alongside
        # strong content — this is file content with highlighted changes

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
    _ensure_bs4()
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
        '.fact', '.rules', '.te', '.pp', '.service', '.timer', '.socket',
    )

    def find_filename_in(elem):
        candidates = []
        for code in elem.find_all('code', class_='literal'):
            code_text = code.get_text(strip=True)
            # Skip FQCN module paths (e.g., ansible.builtin.service)
            if code_text.count('.') > 1:
                continue
            # Match files with known extensions
            if any(code_text.endswith(ext) for ext in file_extensions):
                candidates.append(code_text)
            # Match dotfiles (.cert_pass, .web_pass, .gitignore, etc.)
            elif code_text.startswith('.') and len(code_text) > 1 and '/' not in code_text:
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

    # Strategy 3: Check following siblings of the element.
    for sibling in element.next_siblings:
        if not isinstance(sibling, Tag):
            continue
        if sibling.name == 'figure':
            break
        fn = find_filename_in(sibling)
        if fn:
            sib_text = sibling.get_text().lower()
            if any(kw in sib_text for kw in ['save', 'name', 'file as']):
                return fn

    # Strategy 4: Check ancestor steps for the filename.
    node = step_element.parent
    while node:
        if node.name == 'li':
            ancestor_principal = node.find(class_='principal', recursive=False)
            if ancestor_principal:
                fn = find_filename_in(ancestor_principal)
                if fn:
                    return fn
        node = node.parent
        # Don't go past section boundaries
        if node and node.name == 'section':
            break

    return None


def _parse_file_block(pre, filename: str) -> dict:
    """Parse file content block into a file action."""
    content = pre.get_text()
    if not content or not content.strip():
        return None

    # Check for partial content (output omitted markers)
    has_omission = bool(pre.find('em', string=re.compile(r'output omitted', re.IGNORECASE)))
    action_type = "modify" if has_omission else "create"

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
        "action_type": action_type,
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
            'redhat', 'admin', 'student',
            'Student@123', 'password', 'Password',
        ]
        if cmd_text in skip_patterns:
            continue
        # Skip y/n/yes/no only when they follow a prompt pattern (not standalone commands)
        if cmd_text.lower() in ('y', 'n', 'yes', 'no'):
            block_text = pre.get_text()
            # Check if this appears after a prompt like "? (y/n)" or "(yes/no)"
            prompt_context = re.search(
                r'(\?\s*\((?:y/?n|yes/?no)\)|[Cc]ontinue\?|[Pp]roceed\?|[Cc]onfirm|Password:)',
                block_text,
            )
            if prompt_context:
                continue
        if cmd_text.startswith('- ') or cmd_text.startswith('key:') or cmd_text.startswith('value:'):
            continue
        # Skip config file directives (key = value patterns from ansible.cfg etc.)
        if re.match(r'^[a-z_]+\s*=\s*\S', cmd_text):
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

    # Check for interactive prompts (login, vault passwords)
    is_interactive = False
    prompts = []
    parent_text = pre.get_text()

    # Collect all password/prompt responses from the code block context
    prompt_responses = set()

    if 'Username:' in parent_text or 'Password:' in parent_text:
        is_interactive = True
        for pattern, prompt in [
            (r'Username:\s*(\S+)', 'Username:'),
            (r'Password:\s*(\S+)', 'Password:'),
        ]:
            match = re.search(pattern, parent_text)
            if match:
                prompts.append([prompt, match.group(1)])
                prompt_responses.add(match.group(1))

    # Detect ansible-vault password prompts
    vault_prompt_pattern = r'(?:New vault password|Confirm new vault password|Vault password)\s*(?:\([^)]+\))?:\s*(\S+)'
    vault_matches = re.findall(vault_prompt_pattern, parent_text)
    if vault_matches:
        is_interactive = True
        for pw in vault_matches:
            prompt_responses.add(pw)
        # Build prompt pairs for vault
        seen_prompts = set()
        for m in re.finditer(vault_prompt_pattern, parent_text):
            prompt_text = m.group(0).split(':')[0].strip() + ':'
            response = m.group(1)
            key = (prompt_text, response)
            if key not in seen_prompts:
                prompts.append([re.escape(prompt_text.split('(')[0].strip()), response])
                seen_prompts.add(key)

    # Filter out bare password strings that were extracted as "commands"
    filtered_commands = []
    for cmd_text in final_commands:
        if cmd_text in prompt_responses:
            continue
        filtered_commands.append(cmd_text)

    for cmd_text in filtered_commands:
        commands.append({
            "text": cmd_text,
            "is_interactive": is_interactive,
            "prompts": prompts if is_interactive else [],
        })

    return commands


@json_safe
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

    exercise_map = _build_exercise_map(content_dir)
    summaries = []

    for exercise_id, info in exercise_map.items():
        section = info["section"]
        solution_files = _find_solution_files(exercise_id, lesson_path) if lesson_path else []

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
            "type": info["type"],
            "title": parsed.get("title", ""),
            "steps": stats["total"],
            "gui_only_steps": stats["gui_only"],
            "command_steps": stats["with_commands"],
            "file_steps": stats["with_files"],
            "total_commands": stats["total_commands"],
            "total_files": stats["total_files"],
            "has_solutions": len(solution_files) > 0,
            "testable": stats["with_commands"] > 0 or stats["with_files"] > 0,
        })

    _output({"success": True, "exercises": summaries})


@json_safe
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
        epub = find_epub(course_path)
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
            epub = find_epub(course_path)
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
