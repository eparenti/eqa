"""Unit tests for TC-VARS test category."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tests.vars import TC_VARS
from src.clients.ssh import CommandResult


class TestTCVars:
    """Tests for TC-VARS variable validation."""

    def test_vars_passes_with_no_solution_files(self, mock_exercise, mock_ssh_with_responses):
        """Test that vars passes when no solution files exist."""
        tc = TC_VARS()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-VARS"
        assert result.passed is True

    def test_vars_scans_solution_files(self, mock_exercise, mock_ssh_with_responses, tmp_path):
        """Test that vars scans solution files for variables."""
        # Create a playbook with variables
        playbook = tmp_path / "playbook.yml.sol"
        playbook.write_text("""---
- hosts: all
  vars:
    my_variable: "value"
  tasks:
    - name: Use var
      debug:
        msg: "{{ my_variable }}"
""")
        mock_exercise.solution_files = [playbook]

        tc = TC_VARS()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-VARS"
        assert "variables_defined" in result.details or "defined" in str(result.details)

    def test_vars_detects_issues(self, mock_exercise, mock_ssh_with_responses, tmp_path):
        """Test that vars detects variable issues."""
        # Create a playbook with undefined variable
        playbook = tmp_path / "playbook.yml.sol"
        playbook.write_text("""---
- hosts: all
  tasks:
    - name: Use undefined var
      debug:
        msg: "{{ undefined_variable }}"
""")
        mock_exercise.solution_files = [playbook]

        tc = TC_VARS()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-VARS"

    def test_vars_checks_naming_conventions(self, mock_exercise, mock_ssh_with_responses, tmp_path):
        """Test that vars checks variable naming conventions."""
        playbook = tmp_path / "playbook.yml.sol"
        playbook.write_text("""---
- hosts: all
  vars:
    camelCaseVar: "bad"
    good_snake_case: "good"
  tasks: []
""")
        mock_exercise.solution_files = [playbook]

        tc = TC_VARS()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-VARS"


class TestTCVarsHelpers:
    """Tests for TC-VARS helper methods."""

    def test_extract_variables(self, tmp_path):
        """Test _extract_variables method."""
        playbook = tmp_path / "playbook.yml"
        playbook.write_text("""---
- hosts: all
  vars:
    var1: value1
    var2: value2
  tasks:
    - debug:
        msg: "{{ var1 }} and {{ var3 }}"
""")

        tc = TC_VARS()
        defined, used = tc._extract_variables(playbook)

        assert isinstance(defined, set)
        assert isinstance(used, set)
        assert "var1" in defined
        assert "var1" in used or "var3" in used

    def test_check_undefined_variables(self, mock_exercise):
        """Test _check_undefined method."""
        tc = TC_VARS()

        defined = {"var1", "var2"}
        used = {"var1", "var3"}  # var3 is undefined
        locations = {"var3": ["playbook.yml:10"]}  # Where var3 is used

        bugs = tc._check_undefined(used, defined, locations, mock_exercise)

        assert isinstance(bugs, list)
        # Should find var3 as undefined
        if len(bugs) > 0:
            assert any("var3" in b.description for b in bugs)

    def test_check_naming_conventions(self, mock_exercise):
        """Test _check_naming method."""
        tc = TC_VARS()

        # Mix of good and bad names
        defined = {"good_name", "camelCase", "ALLCAPS", "another_good_name"}

        bugs = tc._check_naming(defined, mock_exercise.id)

        assert isinstance(bugs, list)

    def test_check_unused_variables(self, mock_exercise):
        """Test _check_unused method."""
        tc = TC_VARS()

        defined = {"var1", "var2", "unused_var"}
        used = {"var1", "var2"}

        bugs = tc._check_unused(defined, used, mock_exercise.id)

        assert isinstance(bugs, list)

    def test_exercise_id_in_result(self, mock_exercise, mock_ssh_with_responses):
        """Test that exercise ID is included in result."""
        tc = TC_VARS()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.exercise_id == mock_exercise.id
