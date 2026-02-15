#!/usr/bin/env python3
"""
TC-CONTRACT: Component Contract Validation

Validates contracts between exercise components (EPUB ↔ Solutions ↔ Grading).
Catches cases where instructions, solution files, and grading scripts are out of sync.

Contract checks:
- EPUB references file → Solution file exists
- EPUB describes resource → Solution creates resource
- Solution creates resource → Grading verifies resource
- EPUB step count aligns with solution complexity
- File references match between components
"""

import sys
import re
import yaml
from pathlib import Path
from typing import List, Dict, Set, Optional
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.test_result import TestResult, Bug, BugSeverity, ExerciseContext
from lib.ssh_connection import SSHConnection


class TC_CONTRACT:
    """
    Component contract validation test category.

    Ensures EPUB instructions, solution files, and grading scripts are aligned.
    """

    def __init__(self):
        """Initialize contract tester."""
        pass

    def test(
        self,
        exercise: ExerciseContext,
        ssh: SSHConnection,
        epub_content: str = None,
        grading_script_path: str = None
    ) -> TestResult:
        """
        Test exercise for component contract violations.

        Args:
            exercise: Exercise context
            ssh: SSH connection to workstation
            epub_content: EPUB HTML content (optional)
            grading_script_path: Path to grading script (optional)

        Returns:
            TestResult with contract violation bugs
        """
        print(f"\n📋 TC-CONTRACT: Component Contract Validation")
        print("=" * 60)
        print("  Validating EPUB ↔ Solutions ↔ Grading alignment")

        bugs_found = []

        # Extract contracts from each component
        epub_contracts = self._extract_epub_contracts(epub_content) if epub_content else {}
        solution_contracts = self._extract_solution_contracts(exercise, ssh)
        grading_contracts = self._extract_grading_contracts(exercise, ssh, grading_script_path)

        # Validation 1: EPUB file references → Solution files exist
        print("\n  1. Validating EPUB file references...")
        file_bugs = self._validate_file_references(exercise, epub_contracts, solution_contracts)
        bugs_found.extend(file_bugs)
        if file_bugs:
            print(f"     ⚠️  Found {len(file_bugs)} file reference mismatch(es)")
        else:
            print("     ✅ File references aligned")

        # Validation 2: EPUB resources → Solution creates resources
        print("\n  2. Validating resource creation...")
        resource_bugs = self._validate_resource_creation(exercise, epub_contracts, solution_contracts)
        bugs_found.extend(resource_bugs)
        if resource_bugs:
            print(f"     ⚠️  Found {len(resource_bugs)} resource mismatch(es)")
        else:
            print("     ✅ Resources aligned")

        # Validation 3: Solution creates → Grading verifies
        print("\n  3. Validating grading coverage...")
        grading_bugs = self._validate_grading_coverage(exercise, solution_contracts, grading_contracts)
        bugs_found.extend(grading_bugs)
        if grading_bugs:
            print(f"     ⚠️  Found {len(grading_bugs)} grading gap(s)")
        else:
            print("     ✅ Grading coverage complete")

        # Validation 4: Component complexity alignment
        print("\n  4. Validating component complexity...")
        complexity_bugs = self._validate_complexity_alignment(exercise, epub_contracts, solution_contracts)
        bugs_found.extend(complexity_bugs)
        if complexity_bugs:
            print(f"     ⚠️  Found complexity misalignment")
        else:
            print("     ✅ Component complexity aligned")

        # Summary
        print(f"\n{'=' * 60}")
        if bugs_found:
            print(f"Contract Violations: {len(bugs_found)} issue(s) found")
        else:
            print("Contract Validation: ✅ All components aligned")
        print(f"{'=' * 60}")

        return TestResult(
            category="TC-CONTRACT",
            exercise_id=exercise.id,
            passed=(len(bugs_found) == 0),
            timestamp="",
            duration_seconds=0,
            bugs_found=bugs_found,
            details={
                'epub_files': len(epub_contracts.get('files', [])),
                'solution_files': len(solution_contracts.get('files', [])),
                'epub_resources': len(epub_contracts.get('resources', [])),
                'solution_resources': len(solution_contracts.get('resources', [])),
                'grading_checks': len(grading_contracts.get('checks', []))
            },
            summary=f"Contract: {len(bugs_found)} alignment issue(s)"
        )

    def _extract_epub_contracts(self, epub_content: str) -> Dict:
        """Extract contract expectations from EPUB content."""
        if not epub_content:
            return {'files': [], 'resources': [], 'steps': 0, 'services': [], 'commands': []}

        contracts = {
            'files': set(),
            'resources': set(),
            'services': set(),
            'commands': set(),
            'steps': 0
        }

        # Extract file references
        # Patterns: "Create file /path/to/file", "Edit /etc/config.conf", "playbook.yml"
        file_patterns = [
            r'(?:create|edit|modify|update)\s+(?:file\s+)?([/~][\w\-./]+)',
            r'([/~][\w\-./]+\.(?:yml|yaml|conf|sh|py|txt|json|xml))',
            r'(?:playbook|script|configuration):\s*([/~\w\-./]+)',
        ]

        for pattern in file_patterns:
            matches = re.findall(pattern, epub_content, re.IGNORECASE)
            for match in matches:
                # Normalize file paths
                file_path = match.strip()
                if file_path and not file_path.startswith('http'):
                    contracts['files'].add(file_path)

        # Extract resource references (OpenShift/K8s)
        resource_patterns = [
            r'(?:create|deploy|configure)\s+(?:a\s+)?(\w+)(?:\s+named\s+[\w\-]+)?',
            r'(pod|deployment|service|route|configmap|secret|pvc)(?:s)?\s+(?:named|called)?\s*[\w\-]*',
        ]

        for pattern in resource_patterns:
            matches = re.findall(pattern, epub_content, re.IGNORECASE)
            for match in matches:
                resource = match.strip().lower()
                if resource in ['pod', 'deployment', 'service', 'route', 'configmap', 'secret', 'pvc', 'application']:
                    contracts['resources'].add(resource)

        # Extract service references (RHEL)
        service_pattern = r'(httpd|nginx|postgresql|mariadb|firewalld|chronyd|sshd)(?:\.service)?'
        services = re.findall(service_pattern, epub_content, re.IGNORECASE)
        contracts['services'].update(s.lower() for s in services)

        # Count numbered steps
        step_matches = re.findall(r'^\s*\d+\.|\n\s*\d+\.', epub_content)
        contracts['steps'] = len(step_matches)

        return {
            'files': list(contracts['files']),
            'resources': list(contracts['resources']),
            'services': list(contracts['services']),
            'commands': list(contracts['commands']),
            'steps': contracts['steps']
        }

    def _extract_solution_contracts(self, exercise: ExerciseContext, ssh: SSHConnection) -> Dict:
        """Extract what solution files actually create/configure."""
        contracts = {
            'files': [],
            'resources': [],
            'services': [],
            'solution_file_count': 0
        }

        # Find solution files
        find_result = ssh.run(
            f"find ~/*/solutions/{exercise.id}/ -name '*.sol' 2>/dev/null || true",
            timeout=30
        )

        if find_result.return_code != 0 or not find_result.stdout.strip():
            return contracts

        solution_files = find_result.stdout.strip().split('\n')
        contracts['solution_file_count'] = len(solution_files)

        for sol_file in solution_files:
            # Read solution file
            cat_result = ssh.run(f"cat {sol_file}", timeout=30)
            if cat_result.return_code != 0:
                continue

            content = cat_result.stdout
            filename = Path(sol_file).name

            # Ansible playbook analysis
            if filename.endswith('.yml.sol') or filename.endswith('.yaml.sol'):
                try:
                    # Try to parse as YAML
                    yaml_content = yaml.safe_load(content)
                    if isinstance(yaml_content, list):
                        # Playbook with multiple plays
                        for play in yaml_content:
                            if isinstance(play, dict) and 'tasks' in play:
                                contracts['files'].extend(self._extract_ansible_files(play['tasks']))
                                contracts['services'].extend(self._extract_ansible_services(play['tasks']))
                except yaml.YAMLError:
                    pass

            # OpenShift/K8s manifest analysis
            if filename.endswith('.yaml.sol') or filename.endswith('.yml.sol'):
                try:
                    yaml_content = yaml.safe_load(content)
                    if isinstance(yaml_content, dict) and 'kind' in yaml_content:
                        # Kubernetes manifest
                        kind = yaml_content.get('kind', '').lower()
                        contracts['resources'].append(kind)
                except yaml.YAMLError:
                    pass

            # Shell script analysis
            if filename.endswith('.sh.sol'):
                # Extract systemctl commands
                service_matches = re.findall(r'systemctl\s+\w+\s+([\w\-]+)(?:\.service)?', content)
                contracts['services'].extend(service_matches)

                # Extract file operations
                file_matches = re.findall(r'(?:touch|mkdir|cp|mv|echo\s+.*\s*>\s*)([/~][\w\-./]+)', content)
                contracts['files'].extend(file_matches)

        # Deduplicate
        contracts['files'] = list(set(contracts['files']))
        contracts['resources'] = list(set(contracts['resources']))
        contracts['services'] = list(set(contracts['services']))

        return contracts

    def _extract_grading_contracts(
        self,
        exercise: ExerciseContext,
        ssh: SSHConnection,
        grading_script_path: str = None
    ) -> Dict:
        """Extract what grading script actually checks."""
        contracts = {
            'checks': [],
            'files_checked': [],
            'services_checked': [],
            'resources_checked': []
        }

        if not grading_script_path:
            # Try to find grading script
            find_result = ssh.run(
                f"find ~/*/grading-scripts/ -name '*{exercise.id}*' -o -name 'lab.py' 2>/dev/null | head -1",
                timeout=30
            )
            if find_result.return_code == 0 and find_result.stdout.strip():
                grading_script_path = find_result.stdout.strip().split('\n')[0]

        if not grading_script_path:
            return contracts

        # Read grading script
        cat_result = ssh.run(f"cat {grading_script_path}", timeout=30)
        if cat_result.return_code != 0:
            return contracts

        content = cat_result.stdout

        # Extract file checks
        file_check_patterns = [
            r'file_exists\([\'"]([^\'"]+)[\'"]\)',
            r'check_file\([\'"]([^\'"]+)[\'"]\)',
            r'Path\([\'"]([^\'"]+)[\'"]\)\.exists\(\)',
        ]
        for pattern in file_check_patterns:
            matches = re.findall(pattern, content)
            contracts['files_checked'].extend(matches)

        # Extract service checks
        service_patterns = [
            r'systemctl.*\s+([\w\-]+)(?:\.service)?',
            r'check_service\([\'"]([^\'"]+)[\'"]\)',
        ]
        for pattern in service_patterns:
            matches = re.findall(pattern, content)
            contracts['services_checked'].extend(matches)

        # Extract resource checks (OpenShift)
        resource_patterns = [
            r'oc\s+get\s+(\w+)',
            r'check_resource\([\'"](\w+)[\'"]\)',
        ]
        for pattern in resource_patterns:
            matches = re.findall(pattern, content)
            contracts['resources_checked'].extend(matches)

        # Count total checks
        check_patterns = [
            r'def\s+test_\w+',
            r'assert\s+',
            r'self\.assertTrue',
            r'self\.assertEqual',
        ]
        for pattern in check_patterns:
            matches = re.findall(pattern, content)
            contracts['checks'].extend(matches)

        return contracts

    def _extract_ansible_files(self, tasks: List) -> List[str]:
        """Extract files touched by Ansible tasks."""
        files = []
        for task in tasks:
            if not isinstance(task, dict):
                continue

            # Check common file modules
            for module in ['copy', 'template', 'file', 'lineinfile', 'blockinfile']:
                if module in task:
                    if isinstance(task[module], dict):
                        if 'dest' in task[module]:
                            files.append(task[module]['dest'])
                        elif 'path' in task[module]:
                            files.append(task[module]['path'])

        return files

    def _extract_ansible_services(self, tasks: List) -> List[str]:
        """Extract services managed by Ansible tasks."""
        services = []
        for task in tasks:
            if not isinstance(task, dict):
                continue

            # Check service/systemd modules
            for module in ['service', 'systemd']:
                if module in task:
                    if isinstance(task[module], dict) and 'name' in task[module]:
                        services.append(task[module]['name'])

        return services

    def _validate_file_references(
        self,
        exercise: ExerciseContext,
        epub_contracts: Dict,
        solution_contracts: Dict
    ) -> List[Bug]:
        """Validate that files mentioned in EPUB exist in solutions."""
        bugs = []

        epub_files = set(epub_contracts.get('files', []))
        solution_files = set(solution_contracts.get('files', []))

        if not epub_files:
            return bugs

        # Find EPUB files not in solutions
        missing_files = []
        for epub_file in epub_files:
            # Check if any solution file matches (basename or full path)
            basename = Path(epub_file).name
            found = any(
                basename in str(sol_file) or epub_file in str(sol_file)
                for sol_file in solution_files
            )
            if not found and not self._is_common_system_file(epub_file):
                missing_files.append(epub_file)

        if missing_files and len(missing_files) <= 5:  # Only report if reasonable number
            bugs.append(Bug(
                id=f"CONTRACT-FILES-{exercise.id}",
                severity=BugSeverity.P1_CRITICAL,
                exercise_id=exercise.id,
                category="TC-CONTRACT",
                description=f"Contract Violation: EPUB references {len(missing_files)} file(s) not found in solution",
                expected_output=f"Solution should create/modify: {', '.join(missing_files[:3])}",
                actual_output=f"Solution files found: {len(solution_files)}",
                fix_recommendation=f"""
EPUB instructions reference files that aren't in the solution:

**Missing files:**
{chr(10).join(f'- {f}' for f in missing_files[:5])}

**Action Required:**
1. Review EPUB content for file references
2. Ensure solution files create/configure these files
3. Update solution files or remove file references from EPUB

**Example Fix:**
If EPUB says "Create playbook.yml", ensure solution contains playbook.yml.sol
""",
                verification_steps=[
                    "Review EPUB for file references",
                    f"Check if solution creates: {', '.join(missing_files[:3])}",
                    "Update solution files or EPUB as needed"
                ]
            ))

        return bugs

    def _validate_resource_creation(
        self,
        exercise: ExerciseContext,
        epub_contracts: Dict,
        solution_contracts: Dict
    ) -> List[Bug]:
        """Validate that resources mentioned in EPUB are created by solutions."""
        bugs = []

        epub_resources = set(epub_contracts.get('resources', []))
        solution_resources = set(solution_contracts.get('resources', []))

        if not epub_resources:
            return bugs

        # Find resources mentioned but not created
        missing_resources = epub_resources - solution_resources

        if missing_resources:
            bugs.append(Bug(
                id=f"CONTRACT-RESOURCES-{exercise.id}",
                severity=BugSeverity.P2_HIGH,
                exercise_id=exercise.id,
                category="TC-CONTRACT",
                description=f"Contract Violation: EPUB describes {len(missing_resources)} resource(s) not in solution",
                expected_output=f"Solution should create: {', '.join(missing_resources)}",
                actual_output=f"Solution creates: {', '.join(solution_resources) if solution_resources else 'none'}",
                fix_recommendation=f"""
EPUB instructions describe resources that solution doesn't create:

**Missing resources:**
{chr(10).join(f'- {r}' for r in missing_resources)}

**Action Required:**
1. Review EPUB for resource descriptions (pods, deployments, services, etc.)
2. Ensure solution manifests create these resources
3. Update solution files or clarify EPUB instructions

**Example Fix:**
If EPUB says "Create a deployment", ensure solution contains deployment.yaml.sol
""",
                verification_steps=[
                    "Review EPUB for resource descriptions",
                    "Check solution YAML manifests",
                    "Verify solution creates expected resources"
                ]
            ))

        return bugs

    def _validate_grading_coverage(
        self,
        exercise: ExerciseContext,
        solution_contracts: Dict,
        grading_contracts: Dict
    ) -> List[Bug]:
        """Validate that grading checks what solution creates."""
        bugs = []

        solution_services = set(solution_contracts.get('services', []))
        grading_services = set(grading_contracts.get('services_checked', []))

        solution_files = set(solution_contracts.get('files', []))
        grading_files = set(grading_contracts.get('files_checked', []))

        # Check if solution creates services but grading doesn't verify them
        unchecked_services = solution_services - grading_services
        if unchecked_services and len(solution_services) > 0:
            bugs.append(Bug(
                id=f"CONTRACT-GRADING-{exercise.id}",
                severity=BugSeverity.P3_LOW,
                exercise_id=exercise.id,
                category="TC-CONTRACT",
                description=f"Grading Gap: Solution configures {len(unchecked_services)} service(s) not verified by grading",
                expected_output=f"Grading should check: {', '.join(unchecked_services)}",
                actual_output=f"Grading checks: {', '.join(grading_services) if grading_services else 'none'}",
                fix_recommendation=f"""
Solution configures services that grading script doesn't verify:

**Unchecked services:**
{chr(10).join(f'- {s}' for s in unchecked_services)}

**Action Required:**
1. Review solution for service configurations
2. Add grading checks for these services
3. Verify service state, enabled status, etc.

**Example Fix:**
Add to grading script:
```python
def test_service_running(self):
    result = ssh.run("systemctl is-active {list(unchecked_services)[0] if unchecked_services else 'service'}")
    assert result.stdout.strip() == "active"
```
""",
                verification_steps=[
                    "Review solution for service configurations",
                    "Add grading checks for all services",
                    "Test grading script detects misconfigurations"
                ]
            ))

        return bugs

    def _validate_complexity_alignment(
        self,
        exercise: ExerciseContext,
        epub_contracts: Dict,
        solution_contracts: Dict
    ) -> List[Bug]:
        """Validate that complexity is aligned between EPUB and solution."""
        bugs = []

        epub_steps = epub_contracts.get('steps', 0)
        solution_files = solution_contracts.get('solution_file_count', 0)

        # Heuristic: If EPUB has many steps (>10) but only 1 solution file, might be missing files
        if epub_steps > 10 and solution_files == 1:
            bugs.append(Bug(
                id=f"CONTRACT-COMPLEXITY-{exercise.id}",
                severity=BugSeverity.P3_LOW,
                exercise_id=exercise.id,
                category="TC-CONTRACT",
                description=f"Complexity Mismatch: EPUB has {epub_steps} steps but only {solution_files} solution file(s)",
                expected_output=f"Expected multiple solution files for {epub_steps}-step exercise",
                actual_output=f"Found {solution_files} solution file(s)",
                fix_recommendation="""
Exercise appears complex (many EPUB steps) but has few solution files.

**Possible issues:**
- Missing solution files for some steps
- EPUB is overly detailed for simple exercise
- Solution combines multiple steps into one file

**Action Required:**
1. Review EPUB step count vs. solution complexity
2. Ensure all major tasks have solution files
3. Consider if EPUB needs simplification

This is informational - verify this is intentional.
""",
                verification_steps=[
                    "Review EPUB step count",
                    "Review solution file count and complexity",
                    "Verify alignment is intentional"
                ]
            ))

        return bugs

    def _is_common_system_file(self, file_path: str) -> bool:
        """Check if file is a common system file that wouldn't be in solutions."""
        common_files = [
            '/etc/hosts',
            '/etc/resolv.conf',
            '/etc/passwd',
            '/etc/group',
            '/proc/',
            '/sys/',
            '/dev/',
        ]
        return any(file_path.startswith(cf) for cf in common_files)


def main():
    """Test TC-CONTRACT."""
    from lib.test_result import ExerciseType

    print("TC-CONTRACT: Component Contract Validation Demo")
    print("=" * 80)

    # Create test exercise
    exercise = ExerciseContext(
        id="example-exercise",
        type=ExerciseType.GUIDED_EXERCISE,
        lesson_code="test",
        chapter=1,
        chapter_title="Test",
        title="Example Exercise"
    )

    # Sample EPUB content
    epub_content = """
    <h1>Exercise Instructions</h1>
    <ol>
      <li>Create playbook.yml to deploy web server</li>
      <li>Configure httpd service to start on boot</li>
      <li>Create deployment manifest for myapp</li>
      <li>Verify service is running</li>
    </ol>
    """

    # Create SSH connection
    ssh = SSHConnection("localhost", username="student")

    # Run contract validation
    tester = TC_CONTRACT()
    result = tester.test(exercise, ssh, epub_content=epub_content)

    print("\n" + "=" * 80)
    print(f"Result: {'PASS' if result.passed else 'FAIL'}")
    print(f"Contract Violations: {len(result.bugs_found)}")
    print("=" * 80)

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
