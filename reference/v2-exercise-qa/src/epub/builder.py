"""
EPUB Builder - Builds EPUBs using the scaffolding `sk` tool.

Prerequisites:
- `sk` tool installed
- SSH key (Ed25519 preferred) with access to RedHatTraining GitHub org
- ssh-agent running with key loaded

Usage:
    builder = EPUBBuilder()
    result = builder.build_epub(course_path)
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class BuildResult:
    """Result of EPUB build operation."""
    success: bool
    message: str
    epub_path: Optional[Path] = None
    stdout: str = ""
    stderr: str = ""


class EPUBBuilder:
    """Builds EPUBs using the scaffolding `sk` tool."""

    def __init__(self):
        """Initialize EPUB builder."""
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
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                version = result.stdout.strip() or result.stderr.strip()
                return True, f"sk available: {version}"
            return False, f"sk not working: {result.stderr}"
        except Exception as e:
            return False, f"sk check failed: {e}"

    def validate_ssh_access(self) -> Tuple[bool, str]:
        """Check if SSH access to GitHub works."""
        try:
            result = subprocess.run(
                ["ssh", "-T", "git@github.com"],
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stdout + result.stderr
            if "successfully authenticated" in output.lower():
                return True, "SSH access confirmed"
            return False, "SSH access failed"
        except Exception as e:
            return False, f"SSH check failed: {e}"

    def _ensure_ssh_agent(self) -> Tuple[bool, str]:
        """Ensure ssh-agent is running with a key loaded."""
        # Check if agent has keys
        result = subprocess.run(
            ["ssh-add", "-l"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            return True, "ssh-agent has keys loaded"

        # Try to add Ed25519 key (preferred for JSch compatibility)
        ed25519_key = Path.home() / ".ssh" / "id_ed25519"
        rsa_key = Path.home() / ".ssh" / "id_rsa"

        key_to_add = ed25519_key if ed25519_key.exists() else rsa_key

        if not key_to_add.exists():
            return False, "No SSH key found (~/.ssh/id_ed25519 or ~/.ssh/id_rsa)"

        result = subprocess.run(
            ["ssh-add", str(key_to_add)],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            return True, f"Added {key_to_add.name} to ssh-agent"
        return False, f"Failed to add key: {result.stderr}"

    def build_epub(self, course_path: Path, force_rebuild: bool = True, timeout: int = 600) -> BuildResult:
        """Build EPUB for a course using sk.

        Args:
            course_path: Path to course directory
            force_rebuild: If True, rebuild even if EPUB exists
            timeout: Build timeout in seconds (default: 600)
        """
        if not course_path.exists():
            return BuildResult(False, f"Course not found: {course_path}")

        if not self.sk_path:
            return BuildResult(False, "sk tool not found")

        # Check for existing EPUB
        if not force_rebuild:
            existing = self._find_existing_epub(course_path)
            if existing:
                return BuildResult(True, "Using existing EPUB", epub_path=existing)

        # Must have outline.yml for scaffolding course
        if not (course_path / "outline.yml").exists():
            return BuildResult(False, "Not a scaffolding course (no outline.yml)")

        print(f"📦 Building EPUB for {course_path.name}...")

        # Ensure ssh-agent has key loaded
        ssh_ok, ssh_msg = self._ensure_ssh_agent()
        if not ssh_ok:
            return BuildResult(False, f"SSH setup failed: {ssh_msg}")
        print(f"   {ssh_msg}")

        # Run sk build epub3
        cmd = [str(self.sk_path), "build", "epub3"]
        print(f"   Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=course_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            output = result.stdout + result.stderr

            if result.returncode == 0:
                epub_path = self._find_existing_epub(course_path)
                if epub_path:
                    print(f"✅ EPUB built: {epub_path}")
                    return BuildResult(True, "EPUB built", epub_path=epub_path,
                                       stdout=result.stdout, stderr=result.stderr)
                return BuildResult(False, "Build completed but EPUB not found",
                                   stdout=result.stdout, stderr=result.stderr)
            else:
                # Check for common errors
                if "Auth fail" in output or "JSchException" in output:
                    return BuildResult(
                        False,
                        "SSH auth failed. Run: eval $(ssh-agent) && ssh-add ~/.ssh/id_ed25519",
                        stdout=result.stdout,
                        stderr=result.stderr
                    )
                return BuildResult(False, f"Build failed (exit {result.returncode})",
                                   stdout=result.stdout, stderr=result.stderr)

        except subprocess.TimeoutExpired:
            return BuildResult(False, "Build timed out (>10 min)")
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
        import yaml

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
