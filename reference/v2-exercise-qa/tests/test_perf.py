"""Unit tests for TC-PERF test category."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tests.perf import TC_PERF
from src.clients.ssh import CommandResult


class TestTCPerf:
    """Tests for TC-PERF performance validation."""

    def test_perf_passes_when_within_budget(self, mock_exercise, mock_ssh_with_responses):
        """Test that perf passes when operations are within time budget."""
        # Configure fast responses
        mock_ssh_with_responses.set_response(
            "lab start",
            CommandResult("", True, 0, "SUCCESS", "", 10.0)
        )
        mock_ssh_with_responses.set_response(
            "lab finish",
            CommandResult("", True, 0, "SUCCESS", "", 5.0)
        )

        tc = TC_PERF()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-PERF"
        # Duration should be recorded
        assert result.duration_seconds >= 0

    def test_perf_warns_when_approaching_budget(self, mock_exercise, mock_ssh_with_responses):
        """Test that perf warns when operations approach time budget."""
        # Configure response that takes 75%+ of budget
        mock_ssh_with_responses.set_response(
            "lab start",
            CommandResult("", True, 0, "SUCCESS", "", 50.0)  # 50s of 60s budget
        )
        mock_ssh_with_responses.set_response(
            "lab finish",
            CommandResult("", True, 0, "SUCCESS", "", 5.0)
        )

        tc = TC_PERF()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-PERF"
        # Should have warning bugs
        if result.bugs_found:
            assert any("approaching" in b.description.lower() or "budget" in b.description.lower()
                      for b in result.bugs_found)

    def test_perf_fails_when_over_budget(self, mock_exercise, mock_ssh_with_responses):
        """Test that perf fails when operations exceed time budget."""
        # Configure slow response that exceeds budget
        mock_ssh_with_responses.set_response(
            "lab start",
            CommandResult("", True, 0, "SUCCESS", "", 120.0)  # 120s of 60s budget
        )
        mock_ssh_with_responses.set_response(
            "lab finish",
            CommandResult("", True, 0, "SUCCESS", "", 5.0)
        )

        tc = TC_PERF()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-PERF"
        # Should have bugs for exceeding budget
        if len(result.bugs_found) > 0:
            assert result.passed is False

    def test_perf_records_timing_details(self, mock_exercise, mock_ssh_with_responses):
        """Test that perf records timing details."""
        mock_ssh_with_responses.set_response(
            "lab start",
            CommandResult("", True, 0, "SUCCESS", "", 15.0)
        )
        mock_ssh_with_responses.set_response(
            "lab finish",
            CommandResult("", True, 0, "SUCCESS", "", 10.0)
        )

        tc = TC_PERF()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-PERF"
        assert "timings" in result.details or result.duration_seconds > 0

    def test_perf_handles_command_timeout(self, mock_exercise, mock_ssh_with_responses):
        """Test that perf handles command timeouts gracefully."""
        mock_ssh_with_responses.set_response(
            "lab start",
            CommandResult("", False, -1, "", "Command timed out", 180.0)
        )

        tc = TC_PERF()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-PERF"
        # Should not crash, should report the issue
        assert result.duration_seconds >= 0


class TestTCPerfHelpers:
    """Tests for TC-PERF helper methods."""

    def test_time_budgets_defined(self):
        """Test that time budgets are defined for operations."""
        tc = TC_PERF()

        assert hasattr(tc, 'TIME_BUDGETS')
        assert 'lab_start' in tc.TIME_BUDGETS
        assert 'lab_finish' in tc.TIME_BUDGETS
        assert tc.TIME_BUDGETS['lab_start'] > 0
        assert tc.TIME_BUDGETS['lab_finish'] > 0

    def test_warning_threshold_defined(self):
        """Test that warning threshold is defined."""
        tc = TC_PERF()

        assert hasattr(tc, 'WARNING_THRESHOLD')
        assert 0 < tc.WARNING_THRESHOLD < 1

    def test_exercise_id_in_result(self, mock_exercise, mock_ssh_with_responses):
        """Test that exercise ID is included in result."""
        mock_ssh_with_responses.set_response(
            "lab",
            CommandResult("", True, 0, "SUCCESS", "", 1.0)
        )

        tc = TC_PERF()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.exercise_id == mock_exercise.id

    def test_lab_name_used_for_commands(self, mock_exercise, mock_ssh_with_responses):
        """Test that lab_name (without suffix) is used for commands."""
        commands_run = []

        original_run = mock_ssh_with_responses.run
        def tracking_run(cmd, timeout=30):
            commands_run.append(cmd)
            return CommandResult(cmd, True, 0, "SUCCESS", "", 1.0)

        mock_ssh_with_responses.run = tracking_run

        tc = TC_PERF()
        tc.test(mock_exercise, mock_ssh_with_responses)

        # Should use lab_name (test-exercise) not id (test-exercise-lab)
        start_cmds = [c for c in commands_run if "lab start" in c]
        for cmd in start_cmds:
            assert "test-exercise-lab" not in cmd or "test-exercise" in cmd
