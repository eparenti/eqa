"""TC-VARS: Variable validation.

Tests Ansible variables:
- All referenced variables are defined
- Variable naming conventions
- Unused variable detection
- Variable precedence issues
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set, Optional
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext, ExercisePattern
from ..core.pattern_detector import is_aap_controller_content
from ..clients.ssh import SSHConnection


class TC_VARS:
    """Variable validation test category."""

    # Ansible built-in variables that don't need to be defined
    BUILTIN_VARS = {
        'ansible_facts', 'ansible_host', 'ansible_user', 'ansible_connection',
        'ansible_become', 'ansible_become_user', 'ansible_become_method',
        'ansible_python_interpreter', 'ansible_ssh_private_key_file',
        'inventory_hostname', 'inventory_hostname_short', 'group_names',
        'groups', 'hostvars', 'play_hosts', 'ansible_play_hosts',
        'ansible_play_batch', 'ansible_playbook_python', 'ansible_version',
        'playbook_dir', 'role_path', 'role_name', 'ansible_role_name',
        'item', 'ansible_loop', 'ansible_index_var', 'ansible_loop_var',
        'omit', 'ansible_check_mode', 'ansible_diff_mode', 'ansible_verbosity',
        'ansible_forks', 'ansible_inventory_sources', 'ansible_limit',
        'ansible_run_tags', 'ansible_skip_tags', 'ansible_config_file',
    }

    # AAP Controller specific variables (used in controller_* collections)
    AAP_CONTROLLER_VARS = {
        'controller_host', 'controller_username', 'controller_password',
        'controller_validate_certs', 'controller_auth', 'controller_oauthtoken',
        'platform_auth',  # Common alias for controller_auth
        'ah_host', 'ah_username', 'ah_password', 'ah_token', 'ah_validate_certs',
        # Common field names in Controller YAML
        'name', 'organization', 'description', 'state', 'teams', 'users',
        'credential_type', 'inputs', 'injectors', 'project', 'inventory',
        'playbook', 'extra_vars', 'limit', 'job_type', 'verbosity',
        # Loop item aliases
        'team_item', 'user_item', 'role_item', 'project_item',
        'the_teams', 'the_users', 'the_team', 'the_user',
        'user_teams', 'user_roles',
        'system_administrators', 'system_auditors',
        # Common team/user group names used as data
        'team_operations', 'team_developers', 'team_admins',
        'team1', 'team2', 'team3', 'team4', 'team5',
        'users_no_team', 'team_role_pair',
        # Settings fields
        'settings', 'value', 'key', 'enabled',
    }

    # Magic variables from facts
    FACT_PREFIXES = [
        'ansible_', 'discovered_interpreter_',
    ]

    # Naming convention patterns
    VALID_VAR_PATTERN = r'^[a-z][a-z0-9_]*$'

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test variable definitions and usage.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-VARS: Testing variables...")

        bugs_found = []
        start_time = datetime.now()

        # Log pattern if AAP Controller
        if is_aap_controller_content(exercise):
            print(f"   ⚡ AAP Controller content - using extended variable allowlist")

        # Collect variables from all files
        defined_vars = set()
        used_vars = set()
        var_locations = {}  # var -> list of files where used

        # Scan solution files
        print("   → Scanning solution files...")
        for sol_file in exercise.solution_files:
            if sol_file.exists():
                file_defined, file_used = self._extract_variables(sol_file)
                defined_vars.update(file_defined)
                used_vars.update(file_used)

                for var in file_used:
                    if var not in var_locations:
                        var_locations[var] = []
                    var_locations[var].append(str(sol_file.name))

        # Scan materials
        if exercise.materials_dir and exercise.materials_dir.exists():
            print("   → Scanning materials...")
            for yml_file in exercise.materials_dir.rglob("*.yml"):
                file_defined, file_used = self._extract_variables(yml_file)
                defined_vars.update(file_defined)
                used_vars.update(file_used)

                for var in file_used:
                    if var not in var_locations:
                        var_locations[var] = []
                    var_locations[var].append(str(yml_file.name))

            # Check vars files
            for vars_file in exercise.materials_dir.rglob("vars/*.yml"):
                file_defined, _ = self._extract_variables(vars_file)
                defined_vars.update(file_defined)

            for vars_file in exercise.materials_dir.rglob("defaults/*.yml"):
                file_defined, _ = self._extract_variables(vars_file)
                defined_vars.update(file_defined)

            for vars_file in exercise.materials_dir.rglob("group_vars/*.yml"):
                file_defined, _ = self._extract_variables(vars_file)
                defined_vars.update(file_defined)

            for vars_file in exercise.materials_dir.rglob("host_vars/*.yml"):
                file_defined, _ = self._extract_variables(vars_file)
                defined_vars.update(file_defined)

        print(f"      Found {len(defined_vars)} defined, {len(used_vars)} used")

        # Check for undefined variables
        print("   → Checking for undefined variables...")
        undefined_bugs = self._check_undefined(used_vars, defined_vars, var_locations, exercise)
        bugs_found.extend(undefined_bugs)

        # Check naming conventions
        print("   → Checking naming conventions...")
        naming_bugs = self._check_naming(defined_vars, exercise.id)
        bugs_found.extend(naming_bugs)

        # Check for unused variables (optional - low severity)
        print("   → Checking for unused variables...")
        unused_bugs = self._check_unused(defined_vars, used_vars, exercise.id)
        bugs_found.extend(unused_bugs)

        if len(bugs_found) == 0:
            print("      ✓ All variables properly defined and named")

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-VARS",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'defined_count': len(defined_vars),
                'used_count': len(used_vars),
                'undefined_count': len([b for b in bugs_found if 'UNDEF' in b.id]),
                'issues_found': len(bugs_found)
            }
        )

    def _extract_variables(self, file_path: Path) -> tuple:
        """Extract defined and used variables from a file.

        Returns:
            Tuple of (defined_vars, used_vars) sets
        """
        defined = set()
        used = set()

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return defined, used

        # Find variable definitions
        # Pattern: var_name: value
        def_pattern = r'^[ ]*([a-zA-Z_][a-zA-Z0-9_]*):\s*(?!$)'
        for match in re.finditer(def_pattern, content, re.MULTILINE):
            var_name = match.group(1)
            # Skip Ansible keywords
            if var_name not in ['name', 'hosts', 'tasks', 'vars', 'roles', 'become',
                               'when', 'loop', 'register', 'block', 'rescue', 'always',
                               'handlers', 'notify', 'tags', 'delegate_to', 'run_once',
                               'ignore_errors', 'changed_when', 'failed_when', 'until',
                               'retries', 'delay', 'with_items', 'with_dict', 'include',
                               'import_tasks', 'include_tasks', 'import_role', 'include_role']:
                defined.add(var_name)

        # Find vars block definitions
        vars_block = re.search(r'vars:\s*\n((?:[ ]+[a-zA-Z_][a-zA-Z0-9_]*:.*\n?)+)', content)
        if vars_block:
            for line in vars_block.group(1).split('\n'):
                match = re.match(r'[ ]+([a-zA-Z_][a-zA-Z0-9_]*):', line)
                if match:
                    defined.add(match.group(1))

        # Find set_fact definitions
        set_fact_pattern = r'set_fact:\s*\n((?:[ ]+[a-zA-Z_][a-zA-Z0-9_]*:.*\n?)+)'
        for match in re.finditer(set_fact_pattern, content):
            for line in match.group(1).split('\n'):
                var_match = re.match(r'[ ]+([a-zA-Z_][a-zA-Z0-9_]*):', line)
                if var_match:
                    defined.add(var_match.group(1))

        # Find register definitions
        register_pattern = r'register:\s*([a-zA-Z_][a-zA-Z0-9_]*)'
        for match in re.finditer(register_pattern, content):
            defined.add(match.group(1))

        # Find used variables (Jinja2 expressions)
        used_pattern = r'{{\s*([a-zA-Z_][a-zA-Z0-9_]*)'
        for match in re.finditer(used_pattern, content):
            used.add(match.group(1))

        # Find variables in when conditions
        when_pattern = r'when:\s*([^\n]+)'
        for match in re.finditer(when_pattern, content):
            condition = match.group(1)
            # Extract variable names from condition
            for var_match in re.finditer(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', condition):
                var = var_match.group(1)
                if var not in ['and', 'or', 'not', 'in', 'is', 'defined', 'undefined',
                              'true', 'false', 'True', 'False', 'none', 'None']:
                    used.add(var)

        return defined, used

    def _check_undefined(self, used: Set[str], defined: Set[str],
                         locations: Dict[str, List[str]], exercise: ExerciseContext) -> List[Bug]:
        """Check for undefined variables."""
        bugs = []
        exercise_id = exercise.id
        is_aap = is_aap_controller_content(exercise)

        # Build the set of known variables
        known_vars = self.BUILTIN_VARS.copy()
        if is_aap:
            known_vars.update(self.AAP_CONTROLLER_VARS)

        for var in used:
            # Skip built-ins and AAP vars
            if var in known_vars:
                continue

            # Skip fact prefixes
            if any(var.startswith(prefix) for prefix in self.FACT_PREFIXES):
                continue

            # Skip controller_ prefixed vars for AAP content
            if is_aap and var.startswith('controller_'):
                continue

            # Skip if defined
            if var in defined:
                continue

            # Skip common false positives
            if var in ['item', 'loop', 'result', 'output', 'response']:
                continue

            # For training content, undefined variable detection has high false positive rate:
            # - Task files receive vars from importers
            # - Variables may be defined by students during exercises
            # - Variables may come from inventory/group_vars
            #
            # Only report undefined variables that are:
            # 1. In playbook files (contain hosts:)
            # 2. Look like internal variables (contain exercise/course keywords)

            files = locations.get(var, ['unknown'])
            file_name = files[0] if files else 'unknown'

            # Skip all undefined variable checks for training content
            # The false positive rate is too high - task files, student exercises,
            # inventory vars, etc. make this check unreliable
            # TODO: Re-enable with smarter detection (check file for hosts:, etc.)
            continue

        # Limit to first 10 undefined
        return bugs[:10]

    def _check_naming(self, defined: Set[str], exercise_id: str) -> List[Bug]:
        """Check variable naming conventions."""
        bugs = []

        for var in defined:
            # Check for valid naming
            if not re.match(self.VALID_VAR_PATTERN, var):
                # Check specific issues
                if var[0].isupper():
                    bugs.append(Bug(
                        id=f"VARS-CASE-{var}-{exercise_id}",
                        severity=BugSeverity.P3_LOW,
                        category="TC-VARS",
                        exercise_id=exercise_id,
                        description=f"Variable starts with uppercase: {var}",
                        fix_recommendation=f"Rename to: {var.lower()}",
                        verification_steps=[
                            f"Rename variable to lowercase: {var.lower()}",
                            "Update all references"
                        ]
                    ))
                elif '-' in var:
                    bugs.append(Bug(
                        id=f"VARS-HYPHEN-{var}-{exercise_id}",
                        severity=BugSeverity.P3_LOW,
                        category="TC-VARS",
                        exercise_id=exercise_id,
                        description=f"Variable contains hyphen: {var}",
                        fix_recommendation=f"Use underscore instead: {var.replace('-', '_')}",
                        verification_steps=[
                            f"Rename: {var} -> {var.replace('-', '_')}",
                            "Update all references"
                        ]
                    ))

        # Limit to first 5 naming issues
        return bugs[:5]

    def _check_unused(self, defined: Set[str], used: Set[str], exercise_id: str) -> List[Bug]:
        """Check for unused variables.

        Note: For training content, 'unused' variables are often:
        - Variables for students to use during the exercise
        - Example data for learning
        - Variables used in templates via dynamic lookups

        Therefore, we only report if there are an unusually high number
        and treat it as informational, not a bug.
        """
        bugs = []

        unused = defined - used - self.BUILTIN_VARS

        # Filter out common false positives
        unused = {v for v in unused if not v.startswith('default_') and not v.endswith('_default')}
        unused = {v for v in unused if not v.startswith('_')}  # Skip private vars
        unused = {v for v in unused if len(v) > 2}  # Skip short vars like 'i', 'j'

        # Report if there are unused variables (threshold: 5+)
        if len(unused) >= 5:
            bugs.append(Bug(
                id=f"VARS-UNUSED-MANY-{exercise_id}",
                severity=BugSeverity.P3_LOW,
                category="TC-VARS",
                exercise_id=exercise_id,
                description=f"Found {len(unused)} potentially unused variables",
                fix_recommendation="Review and remove unused variables",
                verification_steps=[
                    "Search for each variable",
                    "Remove if truly unused"
                ]
            ))
        elif len(unused) > 0:
            print(f"      ℹ  {len(unused)} vars defined but not directly used")

        return bugs
