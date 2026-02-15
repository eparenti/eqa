"""TC-DEPS: Dependency validation.

Tests that all dependencies are satisfied:
- Python packages
- Ansible collections
- System packages
- Version requirements
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from ..core.models import TestResult, Bug, BugSeverity, ExerciseContext
from ..clients.ssh import SSHConnection


class TC_DEPS:
    """Dependency validation test category."""

    # Common Ansible collections used in training
    COMMON_COLLECTIONS = [
        'ansible.builtin',
        'ansible.posix',
        'ansible.netcommon',
        'community.general',
        'community.mysql',
        'community.postgresql',
        'redhat.rhel_system_roles',
    ]

    def test(self, exercise: ExerciseContext, ssh: SSHConnection) -> TestResult:
        """
        Test that all dependencies are satisfied.

        Args:
            exercise: Exercise context
            ssh: SSH connection

        Returns:
            TestResult with bugs found (if any)
        """
        print(f"\n✓ TC-DEPS: Testing dependencies...")

        bugs_found = []
        start_time = datetime.now()

        # Extract dependencies from exercise files
        print("   → Scanning for dependencies...")
        required_collections = set()
        required_roles = set()
        required_python = set()

        # Scan solution files
        for sol_file in exercise.solution_files:
            if sol_file.exists():
                deps = self._extract_dependencies(sol_file)
                required_collections.update(deps['collections'])
                required_roles.update(deps['roles'])
                required_python.update(deps['python'])

        # Scan grading script
        if exercise.grading_script and exercise.grading_script.exists():
            deps = self._extract_dependencies(exercise.grading_script)
            required_collections.update(deps['collections'])
            required_roles.update(deps['roles'])

        # Scan materials
        if exercise.materials_dir and exercise.materials_dir.exists():
            for yml_file in exercise.materials_dir.rglob("*.yml"):
                deps = self._extract_dependencies(yml_file)
                required_collections.update(deps['collections'])
                required_roles.update(deps['roles'])

            # Check requirements files
            for req_file in exercise.materials_dir.rglob("requirements.yml"):
                deps = self._parse_requirements_yml(req_file)
                required_collections.update(deps['collections'])
                required_roles.update(deps['roles'])

            for req_file in exercise.materials_dir.rglob("requirements.txt"):
                required_python.update(self._parse_requirements_txt(req_file))

        print(f"      Found {len(required_collections)} collection(s), {len(required_roles)} role(s), {len(required_python)} Python package(s)")

        # Check collections
        if required_collections:
            print("   → Checking Ansible collections...")
            collection_bugs = self._check_collections(required_collections, exercise.id, ssh)
            bugs_found.extend(collection_bugs)

        # Check roles
        if required_roles:
            print("   → Checking Ansible roles...")
            role_bugs = self._check_roles(required_roles, exercise.id, ssh)
            bugs_found.extend(role_bugs)

        # Check Python packages
        if required_python:
            print("   → Checking Python packages...")
            python_bugs = self._check_python_packages(required_python, exercise.id, ssh)
            bugs_found.extend(python_bugs)

        # Check execution environment (if AAP exercise)
        print("   → Checking execution environment...")
        ee_bugs = self._check_execution_environment(exercise, ssh)
        bugs_found.extend(ee_bugs)

        if len(bugs_found) == 0:
            print("      ✓ All dependencies satisfied")
        else:
            print(f"      ⚠  Found {len(bugs_found)} dependency issue(s)")

        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            category="TC-DEPS",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            bugs_found=bugs_found,
            details={
                'collections_required': list(required_collections),
                'roles_required': list(required_roles),
                'python_required': list(required_python),
                'issues_found': len(bugs_found)
            }
        )

    def _extract_dependencies(self, file_path: Path) -> Dict[str, Set[str]]:
        """Extract dependencies from an Ansible or grading file."""
        deps = {
            'collections': set(),
            'roles': set(),
            'python': set(),
        }

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return deps

        is_yaml = file_path.suffix in ['.yml', '.yaml', '.sol']
        is_python = file_path.suffix == '.py'

        if is_yaml:
            # Find collection references (FQCN modules) in YAML
            # Pattern: namespace.collection.module:
            fqcn_pattern = r'\b([a-z_]+\.[a-z_]+)\.[a-z_]+[:\s]'
            for match in re.finditer(fqcn_pattern, content):
                collection = match.group(1)
                if collection not in ['ansible.builtin']:
                    deps['collections'].add(collection)
        elif is_python:
            # In Python grading scripts, only look for ansible.* collection FQCNs
            # Avoids false positives from Python module paths (labs.ui, etc.)
            ansible_fqcn = r'["\']?(ansible\.[a-z_]+)\.[a-z_]+["\']?'
            for match in re.finditer(ansible_fqcn, content):
                collection = match.group(1)
                if collection not in ['ansible.builtin']:
                    deps['collections'].add(collection)

        # YAML-only parsing below
        if is_yaml:
            # Find collections block
            collections_block = re.search(r'collections:\s*\n((?:\s+-\s+\S+\n?)+)', content)
            if collections_block:
                for line in collections_block.group(1).split('\n'):
                    match = re.match(r'\s*-\s*(\S+)', line)
                    if match:
                        deps['collections'].add(match.group(1))

            # Find role references
            roles_pattern = r'role:\s*["\']?(\S+)["\']?'
            for match in re.finditer(roles_pattern, content):
                deps['roles'].add(match.group(1))

            # Find roles in roles block
            roles_block = re.search(r'roles:\s*\n((?:\s+-.*\n?)+)', content)
            if roles_block:
                for line in roles_block.group(1).split('\n'):
                    match = re.match(r'\s*-\s*(?:role:\s*)?["\']?(\S+)', line)
                    if match and not match.group(1).startswith('{'):
                        deps['roles'].add(match.group(1).rstrip('"\''))

        return deps

    def _parse_requirements_yml(self, file_path: Path) -> Dict[str, Set[str]]:
        """Parse requirements.yml for collections and roles."""
        deps = {
            'collections': set(),
            'roles': set(),
        }

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return deps

        # Find collections
        in_collections = False
        in_roles = False

        for line in content.split('\n'):
            if 'collections:' in line:
                in_collections = True
                in_roles = False
            elif 'roles:' in line:
                in_roles = True
                in_collections = False
            elif line.strip().startswith('- '):
                item = line.strip()[2:].strip()
                # Handle both simple and dict format
                if in_collections:
                    if 'name:' in item:
                        match = re.search(r'name:\s*(\S+)', item)
                        if match:
                            deps['collections'].add(match.group(1))
                    else:
                        deps['collections'].add(item.split()[0])
                elif in_roles:
                    if 'name:' in item:
                        match = re.search(r'name:\s*(\S+)', item)
                        if match:
                            deps['roles'].add(match.group(1))
                    else:
                        deps['roles'].add(item.split()[0])

        return deps

    def _parse_requirements_txt(self, file_path: Path) -> Set[str]:
        """Parse requirements.txt for Python packages."""
        packages = set()

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return packages

        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                # Extract package name (before version specifier)
                match = re.match(r'^([a-zA-Z0-9_-]+)', line)
                if match:
                    packages.add(match.group(1).lower())

        return packages

    # Course-internal collections bundled with lab packages (not system-installed)
    COURSE_INTERNAL_COLLECTIONS = [
        'lab.',           # lab.example, lab.* - bundled with course lab packages
        'training.',      # training.* - internal training collections
        'classroom.',     # classroom.* - internal classroom collections
        'rht.',           # rht.dynolabs_aap, rht.* - DynoLabs framework collections
    ]

    # Collections included in standard Ansible execution environments
    # These are available in EE but may not be system-installed
    EE_INCLUDED_COLLECTIONS = {
        'ansible.posix',
        'ansible.netcommon',
        'ansible.utils',
        'ansible.windows',
        'ansible.controller',    # AAP Controller modules (bundled in EE)
        'ansible.platform',      # AAP Platform modules (bundled in EE)
        'awx.awx',               # AWX/Controller modules (legacy name)
        'community.general',
        'community.mysql',
        'community.postgresql',
        'community.crypto',
        'redhat.rhel_system_roles',
        'containers.podman',
        'kubernetes.core',
        'amazon.aws',
        'google.cloud',
        'azure.azcollection',
        'infoblox.nios_modules',
    }

    def _check_collections(self, collections: Set[str], exercise_id: str,
                           ssh: SSHConnection) -> List[Bug]:
        """Check that required collections are installed."""
        bugs = []

        # Filter out course-internal and EE-included collections
        external_collections = set()
        for collection in collections:
            is_internal = any(collection.startswith(prefix) for prefix in self.COURSE_INTERNAL_COLLECTIONS)
            is_ee_included = collection in self.EE_INCLUDED_COLLECTIONS

            if is_internal:
                print(f"      ⏭  Skipping {collection} (course-internal, bundled with lab package)")
            elif is_ee_included:
                print(f"      ⏭  Skipping {collection} (included in standard execution environments)")
            elif collection != 'ansible.builtin':
                external_collections.add(collection)

        if not external_collections:
            return bugs

        # Get installed collections
        result = ssh.run("ansible-galaxy collection list --format json 2>/dev/null || ansible-galaxy collection list 2>/dev/null", timeout=30)

        installed = set()
        if result.success:
            # Parse output - could be JSON or text
            output = result.stdout
            for collection in external_collections:
                if collection in output:
                    installed.add(collection)

        # Check each required external collection
        for collection in external_collections:
            if collection not in installed:
                # Double-check with specific query
                check = ssh.run(f"ansible-galaxy collection list {collection} 2>/dev/null", timeout=10)
                if not check.success or collection not in check.stdout:
                    bugs.append(Bug(
                        id=f"DEPS-COLL-{collection.replace('.', '-')}-{exercise_id}",
                        severity=BugSeverity.P1_CRITICAL,
                        category="TC-DEPS",
                        exercise_id=exercise_id,
                        description=f"Required collection not installed: {collection}",
                        fix_recommendation=f"Install collection: ansible-galaxy collection install {collection}",
                        verification_steps=[
                            f"Run: ansible-galaxy collection install {collection}",
                            f"Verify: ansible-galaxy collection list | grep {collection}"
                        ]
                    ))
                else:
                    print(f"      ✓ Collection available: {collection}")

        return bugs

    # Placeholder/example role names used in training content
    PLACEHOLDER_ROLES = {
        'username.rolename',
        'author.rolename',
        'namespace.rolename',
        'example.role',
        'myname.myrole',
    }

    def _check_roles(self, roles: Set[str], exercise_id: str, ssh: SSHConnection) -> List[Bug]:
        """Check that required roles are available."""
        bugs = []

        for role in roles:
            # Skip roles that are likely local
            if '.' not in role and '/' not in role:
                continue

            # Skip placeholder/example role names used in training content
            role_clean = role.strip().rstrip(',')
            if role_clean in self.PLACEHOLDER_ROLES or 'username' in role_clean or 'example' in role_clean.lower():
                print(f"      ⏭  Skipping {role_clean} (placeholder/example role name)")
                continue

            # Check if role is installed
            result = ssh.run(f"ansible-galaxy role list 2>/dev/null | grep -q '{role_clean}'", timeout=10)
            if not result.success:
                bugs.append(Bug(
                    id=f"DEPS-ROLE-{role_clean.replace('.', '-').replace('/', '-')}-{exercise_id}",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-DEPS",
                    exercise_id=exercise_id,
                    description=f"Required role not installed: {role_clean}",
                    fix_recommendation=f"Install role: ansible-galaxy role install {role_clean}",
                    verification_steps=[
                        f"Run: ansible-galaxy role install {role_clean}",
                        f"Verify: ansible-galaxy role list | grep {role_clean}"
                    ]
                ))

        return bugs

    def _check_python_packages(self, packages: Set[str], exercise_id: str,
                               ssh: SSHConnection) -> List[Bug]:
        """Check that required Python packages are installed."""
        bugs = []

        for package in packages:
            # Check if package is installed
            result = ssh.run(f"python3 -c 'import {package}' 2>/dev/null || pip3 show {package} 2>/dev/null", timeout=10)
            if not result.success:
                bugs.append(Bug(
                    id=f"DEPS-PY-{package}-{exercise_id}",
                    severity=BugSeverity.P2_HIGH,
                    category="TC-DEPS",
                    exercise_id=exercise_id,
                    description=f"Required Python package not installed: {package}",
                    fix_recommendation=f"Install package: pip3 install {package}",
                    verification_steps=[
                        f"Run: pip3 install {package}",
                        f"Verify: python3 -c 'import {package}'"
                    ]
                ))

        return bugs

    def _check_execution_environment(self, exercise: ExerciseContext,
                                      ssh: SSHConnection) -> List[Bug]:
        """Check execution environment for AAP exercises."""
        bugs = []

        # Check if this is an AAP exercise
        aap_indicators = ['aap', 'controller', 'tower', 'ee-', 'execution-environment']
        is_aap = any(ind in exercise.id.lower() or ind in exercise.lesson_code.lower()
                     for ind in aap_indicators)

        if not is_aap:
            return bugs

        # Check for EE definition file
        if exercise.materials_dir:
            ee_files = list(exercise.materials_dir.rglob("execution-environment.yml"))
            if ee_files:
                for ee_file in ee_files:
                    # Validate EE file structure
                    try:
                        content = ee_file.read_text()
                        if 'version:' not in content:
                            bugs.append(Bug(
                                id=f"DEPS-EE-VERSION-{exercise.id}",
                                severity=BugSeverity.P2_HIGH,
                                category="TC-DEPS",
                                exercise_id=exercise.id,
                                description=f"EE definition missing version: {ee_file.name}",
                                fix_recommendation="Add version field to execution-environment.yml",
                                verification_steps=["Add: version: 1 (or 3 for newer format)"]
                            ))
                    except Exception:
                        pass

        return bugs
