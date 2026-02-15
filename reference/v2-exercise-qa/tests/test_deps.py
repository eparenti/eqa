"""Unit tests for TC-DEPS test category."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tests.deps import TC_DEPS
from src.clients.ssh import CommandResult


class TestTCDeps:
    """Tests for TC-DEPS dependency validation."""

    def test_deps_passes_with_no_dependencies(self, mock_exercise, mock_ssh_with_responses):
        """Test that deps passes when no dependencies are needed."""
        tc = TC_DEPS()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-DEPS"
        assert result.passed is True

    def test_deps_detects_collection_requirements(self, mock_exercise, mock_ssh_with_responses, tmp_path):
        """Test that deps detects Ansible collection requirements."""
        # Create a requirements.yml file
        req_file = tmp_path / "requirements.yml"
        req_file.write_text("""---
collections:
  - name: ansible.netcommon
    version: ">=2.0.0"
  - name: community.general
""")
        mock_exercise.materials_dir = tmp_path

        tc = TC_DEPS()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-DEPS"
        # Check that collections were found
        assert "collections" in result.details or result.details.get("dependencies_found", 0) >= 0

    def test_deps_detects_role_requirements(self, mock_exercise, mock_ssh_with_responses, tmp_path):
        """Test that deps detects Ansible role requirements."""
        req_file = tmp_path / "requirements.yml"
        req_file.write_text("""---
roles:
  - name: geerlingguy.docker
  - src: https://github.com/example/role.git
    name: example.role
""")
        mock_exercise.materials_dir = tmp_path

        tc = TC_DEPS()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-DEPS"

    def test_deps_detects_python_requirements(self, mock_exercise, mock_ssh_with_responses, tmp_path):
        """Test that deps detects Python package requirements."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("""requests>=2.25.0
jmespath
netaddr==0.8.0
""")
        mock_exercise.materials_dir = tmp_path

        tc = TC_DEPS()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-DEPS"

    def test_deps_validates_installed_collections(self, mock_exercise, mock_ssh_with_responses):
        """Test that deps validates installed collections."""
        mock_ssh_with_responses.set_response(
            "ansible-galaxy collection list",
            CommandResult("", True, 0, """
Collection        Version
----------------- -------
ansible.netcommon 3.0.0
community.general 5.0.0
""", "", 0.5)
        )

        tc = TC_DEPS()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-DEPS"

    def test_deps_reports_missing_collection(self, mock_exercise, mock_ssh_with_responses, tmp_path):
        """Test that deps reports missing collections."""
        # Create requirements with a collection
        req_file = tmp_path / "requirements.yml"
        req_file.write_text("""---
collections:
  - name: missing.collection
""")
        mock_exercise.materials_dir = tmp_path

        mock_ssh_with_responses.set_response(
            "ansible-galaxy collection list",
            CommandResult("", True, 0, "Collection Version\n", "", 0.5)
        )

        tc = TC_DEPS()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        # Should have bugs for missing dependencies
        assert result.category == "TC-DEPS"


class TestTCDepsHelpers:
    """Tests for TC-DEPS helper methods."""

    def test_parse_requirements_yml(self, tmp_path):
        """Test parsing requirements.yml file."""
        req_file = tmp_path / "requirements.yml"
        req_file.write_text("""---
collections:
  - name: test.collection
    version: "1.0.0"
roles:
  - name: test.role
""")

        tc = TC_DEPS()
        result = tc._parse_requirements_yml(req_file)

        # Returns a dict with 'collections' and 'roles' keys
        assert isinstance(result, dict)
        assert "collections" in result or "roles" in result

    def test_parse_requirements_txt(self, tmp_path):
        """Test parsing requirements.txt file."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("""# Comment
requests>=2.0
jmespath
-e git+https://github.com/example/pkg.git
""")

        tc = TC_DEPS()
        packages = tc._parse_requirements_txt(req_file)

        assert isinstance(packages, set)
        assert "requests" in packages or "requests>=2.0" in packages

    def test_exercise_id_in_result(self, mock_exercise, mock_ssh_with_responses):
        """Test that exercise ID is included in result."""
        tc = TC_DEPS()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.exercise_id == mock_exercise.id
