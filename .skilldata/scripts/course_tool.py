#!/usr/bin/env python3
"""Course detection and input resolution.

All output is JSON to stdout, diagnostics to stderr.

Usage:
    python3 course_tool.py resolve <input> [--chapter N]
    python3 course_tool.py detect <repo_path>
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


def _output(data):
    print(json.dumps(data, default=str))


def _err(msg):
    print(msg, file=sys.stderr)


def cmd_resolve(args):
    """Resolve input (lesson code, path, course code) to epub_path + lesson_path."""
    input_str = args.input

    if args.chapter:
        result = _resolve_chapter(input_str, args.chapter)
    else:
        result = _resolve_input(input_str)

    _output(result)


def _resolve_chapter(input_str: str, chapter_num: int) -> dict:
    """Resolve course code + chapter number to epub_path, lesson_path, lesson_code."""
    course_dir = _find_course_dir(input_str)
    if not course_dir:
        return {"success": False, "error": f"Could not find course directory for: {input_str}"}

    outline_path = course_dir / "outline.yml"
    if not outline_path.exists():
        return {"success": False, "error": f"No outline.yml in {course_dir}"}

    try:
        with open(outline_path) as f:
            outline = yaml.safe_load(f)
    except Exception as e:
        return {"success": False, "error": f"Failed to parse outline.yml: {e}"}

    root = outline.get('course', outline.get('lesson', {}))
    chapters = root.get('chapters', [])

    is_multi_repo = any(ch.get('repository') for ch in chapters)
    unit_label = "lesson" if is_multi_repo else "chapter"

    if chapter_num < 1 or chapter_num > len(chapters):
        chapter_list = []
        for i, ch in enumerate(chapters, 1):
            keyword = ch.get('keyword', ch.get('remoteChapter', '?'))
            repo = ch.get('repository', '')
            lesson = re.search(r'/([A-Z]{2}\d{3,4}[A-Z]?)\.git', repo)
            lesson_str = lesson.group(1) if lesson else ""
            chapter_list.append({"number": i, "keyword": keyword, "lesson_code": lesson_str})
        return {
            "success": False,
            "error": f"{unit_label.title()} {chapter_num} not found. Course has {len(chapters)} {unit_label}s.",
            "chapters": chapter_list,
        }

    chapter = chapters[chapter_num - 1]
    keyword = chapter.get('keyword', chapter.get('remoteChapter', ''))

    repo_url = chapter.get('repository', '')
    lesson_match = re.search(r'/([A-Z]{2}\d{3,4}[A-Z]?)\.git', repo_url)
    lesson_code = lesson_match.group(1) if lesson_match else None

    if lesson_code:
        # Multi-repo: find lesson directory
        lesson_dir = _find_lesson_dir(course_dir, lesson_code)
        if not lesson_dir:
            return {"success": False, "error": f"Lesson directory not found for {lesson_code}"}

        epub = _find_epub_in_dir(lesson_dir)
        if not epub:
            epub = _try_build_epub(lesson_dir)

        if not epub:
            return {"success": False, "error": f"No EPUB found for {lesson_code}"}

        return {
            "success": True,
            "epub_path": str(epub),
            "lesson_path": str(lesson_dir),
            "lesson_code": lesson_code.lower(),
            "chapter_number": chapter_num,
            "keyword": keyword,
            "multi_repo": True,
        }
    else:
        # Single-repo: use course EPUB
        epub = _find_epub_in_dir(course_dir)
        if not epub:
            epub = _try_build_epub(course_dir)
        if not epub:
            return {"success": False, "error": f"No EPUB found in {course_dir}"}

        return {
            "success": True,
            "epub_path": str(epub),
            "lesson_path": str(course_dir),
            "lesson_code": input_str.lower(),
            "chapter_number": chapter_num,
            "keyword": keyword,
            "multi_repo": False,
        }


def _resolve_input(input_str: str) -> dict:
    """Resolve input to epub_path + lesson_path."""
    input_path = Path(input_str).expanduser().resolve()

    # Direct EPUB path
    if input_path.suffix == '.epub' and input_path.exists():
        return {
            "success": True,
            "epub_path": str(input_path),
            "lesson_path": str(input_path.parent),
        }

    # Directory
    if input_path.is_dir():
        epub = _find_epub_in_dir(input_path)
        if epub:
            return {
                "success": True,
                "epub_path": str(epub),
                "lesson_path": str(input_path),
            }
        epub = _try_build_epub(input_path)
        if epub:
            return {
                "success": True,
                "epub_path": str(epub),
                "lesson_path": str(input_path),
            }
        return {"success": False, "error": f"No EPUB found in {input_path}"}

    # Lesson code search
    search_dirs = [
        Path.cwd(),
        Path.home() / "git-repos" / "active",
    ]

    for base in search_dirs:
        if not base.exists():
            continue

        candidate = base / input_str
        if candidate.is_dir():
            epub = _find_epub_in_dir(candidate)
            if epub:
                return {
                    "success": True,
                    "epub_path": str(epub),
                    "lesson_path": str(candidate),
                    "lesson_code": input_str.lower(),
                }

        for lesson_dir in base.glob(f"*-lessons/{input_str}"):
            if lesson_dir.is_dir():
                epub = _find_epub_in_dir(lesson_dir)
                if epub:
                    return {
                        "success": True,
                        "epub_path": str(epub),
                        "lesson_path": str(lesson_dir),
                        "lesson_code": input_str.lower(),
                    }

    return {"success": False, "error": f"Could not resolve: {input_str}"}


def _find_course_dir(input_str: str) -> Path:
    """Find course directory for a course code."""
    input_path = Path(input_str).expanduser().resolve()
    if input_path.is_dir() and (input_path / "outline.yml").exists():
        return input_path

    search_dirs = [
        Path.cwd(),
        Path.home() / "git-repos" / "active",
    ]

    for base in search_dirs:
        if not base.exists():
            continue
        candidate = base / input_str
        if candidate.is_dir() and (candidate / "outline.yml").exists():
            return candidate

    return None


def _find_lesson_dir(course_dir: Path, lesson_code: str) -> Path:
    """Find lesson directory for a given lesson code."""
    parent = course_dir.parent

    for d in parent.glob(f"*-lessons/{lesson_code}"):
        if d.is_dir():
            return d

    sibling = parent / lesson_code
    if sibling.is_dir():
        return sibling

    return None


def _find_epub_in_dir(directory: Path) -> Path:
    """Find most recent EPUB in directory."""
    for location in [directory, directory / ".cache" / "generated" / "en-US"]:
        if location.exists():
            epubs = list(location.glob("*.epub"))
            if epubs:
                return max(epubs, key=lambda p: p.stat().st_mtime)
    return None


def _try_build_epub(directory: Path) -> Path:
    """Try to build EPUB using sk."""
    sk_path = shutil.which("sk")
    if not sk_path or not (directory / "outline.yml").exists():
        return None

    _err(f"Building EPUB for {directory.name}...")
    try:
        result = subprocess.run(
            [sk_path, "build", "epub3"],
            cwd=directory, capture_output=True, text=True, timeout=600,
        )
        if result.returncode == 0:
            return _find_epub_in_dir(directory)
    except Exception:
        pass
    return None


def cmd_detect(args):
    """Auto-detect course metadata and structure from repo."""
    repo_path = Path(args.repo_path).expanduser().resolve()
    if not repo_path.exists():
        _output({"success": False, "error": f"Path does not exist: {repo_path}"})
        return

    info = {"success": True}
    notes = []

    # Course code
    metadata_path = repo_path / "metadata.yml"
    if metadata_path.exists():
        try:
            with open(metadata_path) as f:
                metadata = yaml.safe_load(f)
                if metadata and 'code' in metadata:
                    info["course_code"] = metadata['code']
                    notes.append("Course code from metadata.yml")
                info["sku"] = metadata.get('code')
        except Exception:
            pass

    if "course_code" not in info:
        match = re.match(r'^([A-Z]{2}\d{3,4}[A-Z]?)', repo_path.name)
        info["course_code"] = match.group(1) if match else repo_path.name
        notes.append("Course code from directory name")

    # Version
    version = {}
    if metadata_path.exists():
        try:
            with open(metadata_path) as f:
                m = yaml.safe_load(f)
                if m and 'version' in m:
                    version["metadata"] = str(m['version'])
        except Exception:
            pass

    about_paths = list(repo_path.glob("classroom/grading/src/*/__about__.py"))
    if about_paths:
        try:
            content = about_paths[0].read_text()
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                version["about"] = match.group(1)
        except Exception:
            pass

    info["version"] = version.get("metadata") or version.get("about") or "unknown"

    # Course type
    outline_path = repo_path / "outline.yml"
    if outline_path.exists():
        try:
            with open(outline_path) as f:
                outline = yaml.safe_load(f)
                if outline and 'skeleton' in outline:
                    info["course_type"] = "scaffolding"
                elif (repo_path / "content").exists():
                    info["course_type"] = "scaffolding"
                else:
                    info["course_type"] = "unknown"
        except Exception:
            info["course_type"] = "unknown"
    else:
        info["course_type"] = "traditional" if (repo_path / "guides").exists() else "unknown"

    # Lab framework
    pyproject_path = repo_path / "classroom" / "grading" / "pyproject.toml"
    if pyproject_path.exists():
        try:
            content = pyproject_path.read_text()
            match = re.search(r'rht-labs-core[=<>~]+([0-9.]+)', content)
            if match:
                ver = match.group(1)
                major = int(ver.split('.')[0])
                info["lab_framework"] = "dynolabs5" if major >= 4 else "dynolabs4"
                info["lab_framework_version"] = ver
            elif 'aap_api' in content or 'aap-api' in content:
                info["lab_framework"] = "aap_api"
            else:
                info["lab_framework"] = "python"
        except Exception:
            info["lab_framework"] = "unknown"
    else:
        grading_dir = repo_path / "classroom" / "grading"
        if grading_dir.exists() and list(grading_dir.glob("**/*.sh")):
            info["lab_framework"] = "shell"
        else:
            info["lab_framework"] = "none"

    # Parse outline for exercises and chapters
    if outline_path.exists():
        try:
            with open(outline_path) as f:
                outline = yaml.safe_load(f)
            root = outline.get('course', outline.get('lesson', {}))

            courseinfo = root.get('courseinfo', root.get('lessoninfo', {}))
            info["course_title"] = courseinfo.get('title') or courseinfo.get('goal')
            info["product_name"] = courseinfo.get('product_name')
            info["status"] = courseinfo.get('status')

            chapters = []
            exercises = []
            for chapter in root.get('chapters', []):
                ch_keyword = chapter.get('keyword', '')
                ch_title = chapter.get('title', '')
                ch_repo = chapter.get('repository', '')

                chapters.append({
                    "keyword": ch_keyword,
                    "title": ch_title,
                    "repository": ch_repo,
                })

                for topic in chapter.get('topics', []):
                    t_keyword = topic.get('keyword', '')
                    for section in topic.get('sections', []):
                        if section.get('type') in ('ge', 'lab'):
                            exercises.append({
                                "id": f"{ch_keyword}-{t_keyword}",
                                "type": section['type'],
                                "chapter": ch_keyword,
                                "topic": t_keyword,
                                "title": topic.get('title', ''),
                                "time_minutes": section.get('time'),
                            })

            info["chapters"] = chapters
            info["exercises"] = exercises
            notes.append(f"Parsed {len(chapters)} chapters, {len(exercises)} exercises")
        except Exception as e:
            notes.append(f"Error parsing outline: {e}")

    info["notes"] = notes
    _output(info)


def main():
    parser = argparse.ArgumentParser(description="Course tool for eqa")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # resolve
    p_resolve = subparsers.add_parser("resolve")
    p_resolve.add_argument("input")
    p_resolve.add_argument("--chapter", type=int, default=None)
    p_resolve.set_defaults(func=cmd_resolve)

    # detect
    p_detect = subparsers.add_parser("detect")
    p_detect.add_argument("repo_path")
    p_detect.set_defaults(func=cmd_detect)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
