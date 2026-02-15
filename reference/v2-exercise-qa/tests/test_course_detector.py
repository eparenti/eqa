"""
Unit tests for course auto-detection.
"""

import pytest
import tempfile
from pathlib import Path

from src.core.course_detector import (
    CourseDetector,
    CourseInfo,
    CourseType,
    LabFramework,
    VersionInfo,
    ExerciseInfo,
    detect_course
)


class TestVersionInfo:
    """Tests for VersionInfo dataclass."""

    def test_canonical_prefers_metadata(self):
        """Canonical version should prefer metadata.yml."""
        version = VersionInfo(
            metadata_version="2.5",
            about_version="2.5.1"
        )
        assert version.canonical == "2.5"

    def test_canonical_falls_back_to_about(self):
        """Should fall back to __about__.py version."""
        version = VersionInfo(about_version="2.5.1")
        assert version.canonical == "2.5.1"

    def test_canonical_unknown_when_empty(self):
        """Should return 'unknown' when no versions."""
        version = VersionInfo()
        assert version.canonical == "unknown"

    def test_is_consistent_single_version(self):
        """Single version is always consistent."""
        version = VersionInfo(metadata_version="2.5")
        assert version.is_consistent is True

    def test_is_consistent_matching_major_minor(self):
        """Versions with same major.minor are consistent."""
        version = VersionInfo(
            metadata_version="2.5",
            about_version="2.5.1"
        )
        assert version.is_consistent is True

    def test_is_inconsistent_different_versions(self):
        """Different major.minor versions are inconsistent."""
        version = VersionInfo(
            metadata_version="2.5",
            about_version="2.6.0"
        )
        assert version.is_consistent is False


class TestExerciseInfo:
    """Tests for ExerciseInfo dataclass."""

    def test_full_id_for_ge(self):
        """GE full ID includes -ge suffix."""
        ex = ExerciseInfo(
            id="install-config",
            type="ge",
            chapter_keyword="install",
            topic_keyword="config"
        )
        assert ex.full_id == "install-config-ge"

    def test_full_id_for_lab(self):
        """Lab full ID includes -lab suffix."""
        ex = ExerciseInfo(
            id="rbac-review",
            type="lab",
            chapter_keyword="rbac",
            topic_keyword="review"
        )
        assert ex.full_id == "rbac-review-lab"

    def test_lab_name(self):
        """Lab name should be chapter-topic."""
        ex = ExerciseInfo(
            id="install-config",
            type="ge",
            chapter_keyword="install",
            topic_keyword="config"
        )
        assert ex.lab_name == "install-config"


class TestCourseDetectorWithFixtures:
    """Tests using temporary directory fixtures."""

    def test_detect_course_code_from_metadata(self, tmp_path):
        """Should detect course code from metadata.yml."""
        # Create metadata.yml
        metadata = tmp_path / "metadata.yml"
        metadata.write_text("code: AU467\nversion: '2.5'\n")

        detector = CourseDetector(tmp_path)
        code = detector._detect_course_code()

        assert code == "AU467"

    def test_detect_course_code_from_dirname(self, tmp_path):
        """Should fall back to directory name pattern."""
        # Create a directory with course code pattern
        course_dir = tmp_path / "AU467-lessons"
        course_dir.mkdir()

        detector = CourseDetector(course_dir)
        code = detector._detect_course_code()

        assert code == "AU467"

    def test_detect_version_from_metadata(self, tmp_path):
        """Should detect version from metadata.yml."""
        metadata = tmp_path / "metadata.yml"
        metadata.write_text("code: AU467\nversion: '2.5'\n")

        detector = CourseDetector(tmp_path)
        version = detector._detect_version()

        assert version.metadata_version == "2.5"

    def test_detect_version_from_about(self, tmp_path):
        """Should detect version from __about__.py."""
        # Create classroom/grading/src/pkg/__about__.py
        about_dir = tmp_path / "classroom" / "grading" / "src" / "au467"
        about_dir.mkdir(parents=True)
        about_file = about_dir / "__about__.py"
        about_file.write_text('__version__ = "2.5.1"\n')

        detector = CourseDetector(tmp_path)
        version = detector._detect_version()

        assert version.about_version == "2.5.1"

    def test_detect_scaffolding_from_skeleton(self, tmp_path):
        """Should detect scaffolding via outline.yml skeleton."""
        outline = tmp_path / "outline.yml"
        outline.write_text("""
course:
  courseinfo:
    sku: AU467
skeleton:
  repository: git@github.com:RedHatTraining/scaffolding.git
  revision: 1.2
""")

        detector = CourseDetector(tmp_path)
        course_type = detector._detect_course_type()

        assert course_type == CourseType.SCAFFOLDING

    def test_detect_traditional_from_guides(self, tmp_path):
        """Should detect traditional course via guides/ directory."""
        guides_dir = tmp_path / "guides"
        guides_dir.mkdir()

        detector = CourseDetector(tmp_path)
        course_type = detector._detect_course_type()

        assert course_type == CourseType.TRADITIONAL

    def test_detect_dynolabs5_from_pyproject(self, tmp_path):
        """Should detect Dynolabs 5 from rht-labs-core version."""
        pyproject_dir = tmp_path / "classroom" / "grading"
        pyproject_dir.mkdir(parents=True)
        pyproject = pyproject_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "rht-labs-au467"
dependencies = [
    "rht-labs-core==4.45.0",
]
""")

        detector = CourseDetector(tmp_path)
        framework, version = detector._detect_lab_framework()

        assert framework == LabFramework.DYNOLABS_5
        assert version == "4.45.0"

    def test_detect_shell_scripts(self, tmp_path):
        """Should detect shell-based grading."""
        grading_dir = tmp_path / "classroom" / "grading"
        grading_dir.mkdir(parents=True)
        (grading_dir / "grade.sh").write_text("#!/bin/bash\n")

        detector = CourseDetector(tmp_path)
        framework, version = detector._detect_lab_framework()

        assert framework == LabFramework.SHELL_SCRIPTS
        assert version is None

    def test_parse_outline_course_structure(self, tmp_path):
        """Should parse exercises from outline.yml course structure."""
        outline = tmp_path / "outline.yml"
        outline.write_text("""
course:
  courseinfo:
    sku: AU467
    title: Test Course
    product_name: Test Product
    status: final
  chapters:
    - keyword: install
      title: Installing
      topics:
        - keyword: config
          title: Configuration
          sections:
            - type: lecture
              time: 15
            - type: ge
              time: 20
              objectives:
                - Configure the system
        - keyword: review
          title: Review
          sections:
            - type: lab
              time: 30
""")

        detector = CourseDetector(tmp_path)
        info = CourseInfo(course_code="AU467")
        detector._parse_outline(info)

        assert len(info.exercises) == 2
        assert info.exercises[0].type == "ge"
        assert info.exercises[0].lab_name == "install-config"
        assert info.exercises[1].type == "lab"
        assert info.exercises[1].lab_name == "install-review"

    def test_parse_outline_lesson_structure(self, tmp_path):
        """Should parse exercises from outline.yml lesson structure."""
        outline = tmp_path / "outline.yml"
        outline.write_text("""
lesson:
  lessoninfo:
    sku: AU0031L
    goal: Learn Ansible basics
    status: final
  chapters:
    - keyword: intro
      title: Introduction
      topics:
        - keyword: devenv
          title: Dev Environment
          sections:
            - type: ge
              time: 25
""")

        detector = CourseDetector(tmp_path)
        info = CourseInfo(course_code="AU0031L")
        detector._parse_outline(info)

        assert len(info.exercises) == 1
        assert info.exercises[0].type == "ge"
        assert info.exercises[0].lab_name == "intro-devenv"

    def test_full_detection_workflow(self, tmp_path):
        """Test complete detection workflow."""
        # Setup minimal course structure
        (tmp_path / "metadata.yml").write_text("code: TEST123\nversion: '1.0'\n")
        (tmp_path / "content").mkdir()
        (tmp_path / "content" / "introduction").mkdir()

        grading_dir = tmp_path / "classroom" / "grading"
        grading_dir.mkdir(parents=True)
        (grading_dir / "pyproject.toml").write_text("""
[project]
dependencies = ["rht-labs-core==5.0.0"]
""")

        (tmp_path / "outline.yml").write_text("""
course:
  courseinfo:
    sku: TEST123
    title: Test Course
  chapters:
    - keyword: ch1
      topics:
        - keyword: ex1
          sections:
            - type: ge
              time: 10
skeleton:
  repository: test
""")

        info = detect_course(tmp_path)

        assert info.course_code == "TEST123"
        assert info.version.canonical == "1.0"
        assert info.course_type == CourseType.SCAFFOLDING
        assert info.lab_framework == LabFramework.DYNOLABS_5
        assert info.lab_framework_version == "5.0.0"
        assert len(info.exercises) == 1
        assert info.detection_confidence >= 0.8


class TestConvenienceFunction:
    """Tests for detect_course convenience function."""

    def test_detect_course_returns_course_info(self, tmp_path):
        """detect_course should return CourseInfo."""
        (tmp_path / "metadata.yml").write_text("code: TEST\nversion: '1.0'\n")

        info = detect_course(tmp_path)

        assert isinstance(info, CourseInfo)
        assert info.course_code == "TEST"

    def test_detect_course_raises_on_missing_path(self):
        """Should raise ValueError for non-existent path."""
        with pytest.raises(ValueError, match="does not exist"):
            detect_course("/nonexistent/path")
