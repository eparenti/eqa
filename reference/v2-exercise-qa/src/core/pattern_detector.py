"""Pattern detection for course and exercise content types."""

from pathlib import Path
from typing import List, Optional, Set
import yaml
import re

from .models import CoursePattern, ExercisePattern, ExerciseContext


# AAP Controller YAML indicators
AAP_CONTROLLER_KEYS = {
    'controller_organizations',
    'controller_teams',
    'controller_users',
    'controller_projects',
    'controller_inventories',
    'controller_hosts',
    'controller_groups',
    'controller_job_templates',
    'controller_workflow_job_templates',
    'controller_credentials',
    'controller_credential_types',
    'controller_execution_environments',
    'controller_settings',
    'controller_roles',
    'controller_notifications',
    'controller_schedules',
    'controller_labels',
    'controller_instance_groups',
}

# AAP Controller variable patterns
AAP_CONTROLLER_VAR_PATTERNS = [
    r'controller_host',
    r'controller_username',
    r'controller_password',
    r'controller_validate_certs',
    r'controller_auth',
    r'ah_host',  # Automation Hub
    r'ah_token',
    r'platform_auth',  # AU467 style
    r'aap_hostname',
    r'aap_username',
    r'aap_password',
]

# AAP Controller module patterns (in task definitions)
AAP_MODULE_PATTERNS = [
    r'ansible\.platform\.',       # AU467/RHAAP 2.5+ style
    r'ansible\.controller\.',     # Older style
    r'awx\.awx\.',               # Legacy AWX
    r'infra\.controller_configuration\.',  # Infra collection
]

# Ansible playbook indicators
ANSIBLE_PLAYBOOK_KEYS = {
    'hosts',
    'tasks',
    'handlers',
    'roles',
    'vars',
    'vars_files',
    'pre_tasks',
    'post_tasks',
    'gather_facts',
    'become',
    'become_user',
}


class PatternDetector:
    """Detects content patterns in exercises and courses."""

    def detect_exercise_pattern(self, exercise: ExerciseContext) -> ExercisePattern:
        """
        Detect the content pattern for an exercise.

        Analyzes solution files and materials to determine the pattern.
        """
        patterns_found: Set[ExercisePattern] = set()

        # Analyze solution files
        for sol_file in exercise.solution_files:
            pattern = self._analyze_file(sol_file)
            if pattern != ExercisePattern.UNKNOWN:
                patterns_found.add(pattern)

        # Analyze materials directory
        if exercise.materials_dir and exercise.materials_dir.exists():
            for yaml_file in exercise.materials_dir.glob("**/*.yml"):
                pattern = self._analyze_file(yaml_file)
                if pattern != ExercisePattern.UNKNOWN:
                    patterns_found.add(pattern)
            for yaml_file in exercise.materials_dir.glob("**/*.yaml"):
                pattern = self._analyze_file(yaml_file)
                if pattern != ExercisePattern.UNKNOWN:
                    patterns_found.add(pattern)

        # Analyze grading script
        if exercise.grading_script:
            if exercise.grading_script.suffix == '.py':
                patterns_found.add(ExercisePattern.PYTHON)
            elif exercise.grading_script.suffix == '.sh':
                patterns_found.add(ExercisePattern.SHELL_SCRIPT)

        # Determine final pattern
        # Priority: AAP_CONTROLLER > ANSIBLE_PLAYBOOK > others
        if not patterns_found:
            return ExercisePattern.UNKNOWN
        elif ExercisePattern.AAP_CONTROLLER in patterns_found:
            # AAP Controller content takes priority - it's the primary content type
            # Even if grading script is Python, the exercise is about Controller
            return ExercisePattern.AAP_CONTROLLER
        elif len(patterns_found) == 1:
            return patterns_found.pop()
        elif ExercisePattern.ANSIBLE_PLAYBOOK in patterns_found:
            # Ansible content with supporting scripts
            return ExercisePattern.ANSIBLE_PLAYBOOK
        else:
            return ExercisePattern.MIXED

    def detect_course_pattern(self, exercises: List[ExerciseContext]) -> CoursePattern:
        """
        Detect the overall course pattern based on exercise patterns.
        """
        if not exercises:
            return CoursePattern.UNKNOWN

        exercise_patterns = [ex.content_pattern for ex in exercises]

        aap_count = sum(1 for p in exercise_patterns
                       if p == ExercisePattern.AAP_CONTROLLER)
        traditional_count = sum(1 for p in exercise_patterns
                               if p in {ExercisePattern.ANSIBLE_PLAYBOOK,
                                       ExercisePattern.SHELL_SCRIPT})
        total = len(exercises)

        # Determine course pattern
        if aap_count == total:
            return CoursePattern.AAP_CONTROLLER
        elif aap_count == 0 and traditional_count > 0:
            return CoursePattern.TRADITIONAL
        elif aap_count > 0 and traditional_count > 0:
            return CoursePattern.HYBRID
        else:
            return CoursePattern.UNKNOWN

    def _analyze_file(self, file_path: Path) -> ExercisePattern:
        """Analyze a single file to determine its pattern."""
        if not file_path.exists():
            return ExercisePattern.UNKNOWN

        suffix = file_path.suffix.lower()

        # Shell scripts
        if suffix == '.sh':
            return ExercisePattern.SHELL_SCRIPT

        # Python files
        if suffix == '.py':
            return ExercisePattern.PYTHON

        # YAML files - need deeper analysis
        if suffix in {'.yml', '.yaml', '.sol'}:
            return self._analyze_yaml_file(file_path)

        return ExercisePattern.UNKNOWN

    def _analyze_yaml_file(self, file_path: Path) -> ExercisePattern:
        """Analyze a YAML file to determine if it's AAP Controller or Ansible."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Quick regex checks for AAP module usage
            for pattern in AAP_MODULE_PATTERNS:
                if re.search(pattern, content):
                    return ExercisePattern.AAP_CONTROLLER

            # Quick regex checks for controller variables
            for pattern in AAP_CONTROLLER_VAR_PATTERNS:
                if re.search(pattern, content):
                    return ExercisePattern.AAP_CONTROLLER

            # Try to parse YAML
            try:
                data = yaml.safe_load(content)
            except yaml.YAMLError:
                return ExercisePattern.UNKNOWN

            if data is None:
                return ExercisePattern.UNKNOWN

            # Handle list of documents (playbooks)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        pattern = self._classify_dict(item)
                        if pattern != ExercisePattern.UNKNOWN:
                            return pattern
                return ExercisePattern.UNKNOWN

            # Handle single dict
            if isinstance(data, dict):
                return self._classify_dict(data)

            return ExercisePattern.UNKNOWN

        except Exception:
            return ExercisePattern.UNKNOWN

    def _classify_dict(self, data: dict) -> ExercisePattern:
        """Classify a YAML dict as AAP Controller or Ansible playbook."""
        keys = set(data.keys())

        # Check for AAP Controller keys
        if keys & AAP_CONTROLLER_KEYS:
            return ExercisePattern.AAP_CONTROLLER

        # Check for Ansible playbook keys
        if keys & ANSIBLE_PLAYBOOK_KEYS:
            return ExercisePattern.ANSIBLE_PLAYBOOK

        # Check for 'name' + 'tasks' pattern (common in playbooks)
        if 'name' in keys and 'tasks' in keys:
            return ExercisePattern.ANSIBLE_PLAYBOOK

        # Check for controller_* keys dynamically
        for key in keys:
            if key.startswith('controller_'):
                return ExercisePattern.AAP_CONTROLLER

        return ExercisePattern.UNKNOWN


def is_aap_controller_content(exercise: ExerciseContext) -> bool:
    """Quick check if exercise contains AAP Controller content."""
    return exercise.content_pattern in {
        ExercisePattern.AAP_CONTROLLER,
        ExercisePattern.MIXED
    }


def is_traditional_ansible(exercise: ExerciseContext) -> bool:
    """Quick check if exercise is traditional Ansible."""
    return exercise.content_pattern == ExercisePattern.ANSIBLE_PLAYBOOK
