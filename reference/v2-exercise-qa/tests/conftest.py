"""Pytest fixtures for exercise-qa-2 tests."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.models import ExerciseContext, ExerciseType
from src.clients.ssh import CommandResult


@pytest.fixture
def mock_exercise():
    """Create a mock exercise context."""
    return ExerciseContext(
        id='test-exercise-lab',
        type=ExerciseType.LAB,
        lesson_code='TEST001',
        chapter=1,
        chapter_title='Test Chapter',
        title='Test Exercise Lab',
        lesson_path=Path('/tmp/test-lesson'),
        solution_files=[],
        grading_script=None,
        materials_dir=None
    )


@pytest.fixture
def mock_exercise_ge():
    """Create a mock guided exercise context."""
    return ExerciseContext(
        id='test-exercise-ge',
        type=ExerciseType.GUIDED_EXERCISE,
        lesson_code='TEST001',
        chapter=1,
        chapter_title='Test Chapter',
        title='Test Guided Exercise',
        lesson_path=Path('/tmp/test-lesson'),
        solution_files=[],
        grading_script=None,
        materials_dir=None
    )


@pytest.fixture
def mock_ssh():
    """Create a mock SSH connection."""
    ssh = Mock()

    def make_result(success=True, stdout="", stderr="", return_code=0):
        return CommandResult(
            command="test",
            success=success,
            return_code=return_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=1.0
        )

    ssh.run = Mock(return_value=make_result(success=True, stdout="success"))
    ssh.make_result = make_result
    return ssh


@pytest.fixture
def mock_ssh_with_responses():
    """Create a mock SSH that can be configured with specific responses."""
    class ConfigurableSSH:
        def __init__(self):
            self.responses = {}
            self.default_response = CommandResult(
                command="default",
                success=True,
                return_code=0,
                stdout="",
                stderr="",
                duration_seconds=0.1
            )

        def set_response(self, command_pattern: str, response: CommandResult):
            self.responses[command_pattern] = response

        def run(self, command: str, timeout: int = 30) -> CommandResult:
            for pattern, response in self.responses.items():
                if pattern in command:
                    return CommandResult(
                        command=command,
                        success=response.success,
                        return_code=response.return_code,
                        stdout=response.stdout,
                        stderr=response.stderr,
                        duration_seconds=response.duration_seconds
                    )
            return CommandResult(
                command=command,
                success=self.default_response.success,
                return_code=self.default_response.return_code,
                stdout=self.default_response.stdout,
                stderr=self.default_response.stderr,
                duration_seconds=self.default_response.duration_seconds
            )

    return ConfigurableSSH()


@pytest.fixture
def tmp_exercise_dir(tmp_path):
    """Create a temporary exercise directory structure."""
    exercise_dir = tmp_path / "test-exercise"
    exercise_dir.mkdir()

    # Create materials directory
    materials = exercise_dir / "materials" / "labs" / "test-exercise"
    materials.mkdir(parents=True)

    # Create solutions directory
    solutions = materials / "solutions"
    solutions.mkdir()

    return exercise_dir
