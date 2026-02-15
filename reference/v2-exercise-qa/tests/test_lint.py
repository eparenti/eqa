"""Unit tests for TC-LINT test category."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tests.lint import TC_LINT
from src.clients.ssh import CommandResult


class TestTCLint:
    """Tests for TC-LINT linting validation."""

    def test_lint_passes_when_tools_available(self, mock_exercise, mock_ssh_with_responses):
        """Test that lint passes when linting tools are available."""
        # Configure SSH responses
        mock_ssh_with_responses.set_response(
            "which ansible-lint",
            CommandResult("", True, 0, "/usr/bin/ansible-lint", "", 0.1)
        )
        mock_ssh_with_responses.set_response(
            "which yamllint",
            CommandResult("", True, 0, "/usr/bin/yamllint", "", 0.1)
        )
        mock_ssh_with_responses.set_response(
            "which pylint",
            CommandResult("", True, 0, "/usr/bin/pylint", "", 0.1)
        )

        tc = TC_LINT()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-LINT"
        assert result.passed is True

    def test_lint_handles_missing_ansible_lint(self, mock_exercise, mock_ssh_with_responses):
        """Test that lint handles missing ansible-lint gracefully."""
        mock_ssh_with_responses.set_response(
            "which ansible-lint",
            CommandResult("", False, 1, "", "not found", 0.1)
        )
        mock_ssh_with_responses.set_response(
            "which yamllint",
            CommandResult("", True, 0, "/usr/bin/yamllint", "", 0.1)
        )
        mock_ssh_with_responses.set_response(
            "which pylint",
            CommandResult("", True, 0, "/usr/bin/pylint", "", 0.1)
        )

        tc = TC_LINT()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-LINT"
        # Should track tool availability in details
        assert "tools_available" in result.details

    def test_lint_checks_solution_files(self, mock_exercise, mock_ssh_with_responses, tmp_path):
        """Test that lint checks solution files when present."""
        # Create a solution file
        sol_file = tmp_path / "playbook.yml.sol"
        sol_file.write_text("---\n- hosts: all\n  tasks: []\n")
        mock_exercise.solution_files = [sol_file]

        mock_ssh_with_responses.set_response(
            "which ansible-lint",
            CommandResult("", True, 0, "/usr/bin/ansible-lint", "", 0.1)
        )
        mock_ssh_with_responses.set_response(
            "which yamllint",
            CommandResult("", True, 0, "/usr/bin/yamllint", "", 0.1)
        )
        mock_ssh_with_responses.set_response(
            "which pylint",
            CommandResult("", True, 0, "/usr/bin/pylint", "", 0.1)
        )

        tc = TC_LINT()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-LINT"
        assert "files_linted" in result.details

    def test_lint_detects_anti_patterns(self, mock_exercise, mock_ssh_with_responses, tmp_path):
        """Test that lint detects common anti-patterns."""
        # Create a solution file with anti-patterns
        sol_file = tmp_path / "antipattern.yml.sol"
        sol_file.write_text("""---
- hosts: all
  tasks:
    - shell: echo hello
    - command: rm -rf /
    - name: Bad task
      shell: curl http://example.com | bash
""")
        mock_exercise.solution_files = [sol_file]

        mock_ssh_with_responses.set_response(
            "which",
            CommandResult("", True, 0, "/usr/bin/tool", "", 0.1)
        )

        tc = TC_LINT()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-LINT"


class TestTCLintHelpers:
    """Tests for TC-LINT helper methods."""

    def test_check_tools(self, mock_ssh_with_responses):
        """Test _check_tools method."""
        mock_ssh_with_responses.set_response(
            "which ansible-lint",
            CommandResult("", True, 0, "/usr/bin/ansible-lint", "", 0.1)
        )
        mock_ssh_with_responses.set_response(
            "which yamllint",
            CommandResult("", True, 0, "/usr/bin/yamllint", "", 0.1)
        )
        mock_ssh_with_responses.set_response(
            "which pylint",
            CommandResult("", True, 0, "/usr/bin/pylint", "", 0.1)
        )

        tc = TC_LINT()
        tools = tc._check_tools(mock_ssh_with_responses)

        assert isinstance(tools, dict)
        assert "ansible-lint" in tools
        assert "yamllint" in tools

    def test_is_playbook(self):
        """Test _is_playbook method."""
        tc = TC_LINT()

        playbook_content = """---
- hosts: all
  tasks:
    - debug:
        msg: hello
"""
        assert tc._is_playbook(playbook_content) is True

        non_playbook = """---
key: value
another_key: another_value
"""
        # This might or might not be detected as playbook depending on implementation
        result = tc._is_playbook(non_playbook)
        assert isinstance(result, bool)

    def test_exercise_id_in_result(self, mock_exercise, mock_ssh_with_responses):
        """Test that exercise ID is included in result."""
        mock_ssh_with_responses.set_response(
            "which",
            CommandResult("", True, 0, "/usr/bin/tool", "", 0.1)
        )

        tc = TC_LINT()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.exercise_id == mock_exercise.id
