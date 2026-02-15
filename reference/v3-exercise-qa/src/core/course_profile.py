"""Course profile builder - analyzes EPUB content to understand the course.

Reads the full coursebook before testing to understand:
- Technology stack (ansible-navigator vs dev tools, AAP controller, etc.)
- Expected workstation environment
- Intentional teaching patterns (deliberate errors, progressive exercises)
- What tools and features the course actually uses
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set, Optional, Dict
from bs4 import BeautifulSoup


@dataclass
class CourseProfile:
    """What we know about the course from reading the EPUB."""

    # Technology stack
    uses_ansible_navigator: bool = False
    uses_ansible_playbook: bool = False
    uses_ansible_dev_tools: bool = False
    uses_aap_controller: bool = False
    uses_execution_environments: bool = False
    uses_containers: bool = False
    uses_openshift: bool = False

    # Expected workstation tools
    expected_tools: Set[str] = field(default_factory=set)

    # Collections referenced in content (not necessarily installed)
    referenced_collections: Set[str] = field(default_factory=set)

    # Hosts mentioned in content (real hosts vs inventory group examples)
    real_hosts: Set[str] = field(default_factory=set)
    example_hosts: Set[str] = field(default_factory=set)

    # Teaching patterns
    has_intentional_errors: bool = False
    exercises_with_deliberate_bugs: Set[str] = field(default_factory=set)
    progressive_exercises: bool = False  # exercises build on each other

    # Course conventions
    uses_sol_files: bool = False
    uses_solve_playbooks: bool = False
    uses_lab_grade: bool = False

    # Raw content for test categories to query
    chapter_summaries: Dict[str, str] = field(default_factory=dict)

    def expects_tool(self, tool: str) -> bool:
        """Check if the course expects a specific tool."""
        return tool in self.expected_tools

    def is_host_real(self, hostname: str) -> bool:
        """Check if a hostname is a real lab host vs an example/group name."""
        if hostname in self.real_hosts:
            return True
        if hostname in self.example_hosts:
            return False
        # Standard lab hosts are always real
        if re.match(r'^(server[a-z]|workstation|bastion|utility|node\d+)$', hostname):
            return True
        return False


class CourseProfileBuilder:
    """Builds a CourseProfile by analyzing EPUB content."""

    # Patterns that indicate technology usage
    NAVIGATOR_PATTERNS = [
        r'ansible-navigator',
        r'navigator\s+run',
        r'-m\s+stdout',
        r'ansible-navigator\.ya?ml',
    ]

    DEV_TOOLS_PATTERNS = [
        r'ansible\s+development\s+tools',
        r'ansible-dev-tools',
        r'ansible-devtools',
        r'adt\b',
        r'vscode.*ansible',
        r'ansible\s+extension',
        r'devcontainer',
    ]

    AAP_PATTERNS = [
        r'automation\s+controller',
        r'ansible\s+controller',
        r'ansible\s+tower',
        r'AAP\s+controller',
        r'controller\.example\.com',
    ]

    CONTAINER_PATTERNS = [
        r'\bpodman\b',
        r'\bdocker\b',
        r'container\s+image',
        r'execution\s+environment',
        r'\bEE\b',
        r'ee-supported',
        r'ee-minimal',
    ]

    OPENSHIFT_PATTERNS = [
        r'\boc\s+',
        r'openshift',
        r'kubernetes',
        r'\bkubectl\b',
    ]

    # Patterns that indicate intentional errors as teaching tools
    INTENTIONAL_ERROR_PATTERNS = [
        r'intentional(?:ly)?\s+(?:broken|incorrect|wrong|error)',
        r'deliberate(?:ly)?\s+(?:broken|incorrect|wrong|error)',
        r'fix\s+the\s+(?:broken|incorrect|error)',
        r'troubleshoot(?:ing)?\s+the',
        r'identify\s+the\s+(?:error|problem|issue|bug)',
        r'find\s+(?:and\s+fix|the\s+error)',
        r'debug(?:ging)?\s+the',
        r'what\s+is\s+wrong',
        r'correct\s+the\s+(?:error|mistake|problem)',
    ]

    # Standard lab hostnames (always real)
    STANDARD_HOSTS = {
        'servera', 'serverb', 'serverc', 'serverd', 'servere',
        'workstation', 'bastion', 'utility',
    }

    # Hostnames that are typically example/group names, not real hosts
    EXAMPLE_HOST_PATTERNS = [
        r'^(web|db|app|cache|redis|lb|proxy|mail)\d*$',
        r'^(prod|dev|staging|test|qa)$',
        r'^(north|south|east|west|europe|asia|americas)',
        r'^(frontend|backend|api|worker)$',
        r'^(master|node|etcd)\d*$',  # k8s groups
    ]

    def build(self, epub_extract_dir: Path, exercises: list = None) -> CourseProfile:
        """
        Build a course profile by reading EPUB content.

        Args:
            epub_extract_dir: Directory where EPUB was extracted
            exercises: List of ExerciseContext objects (optional)

        Returns:
            CourseProfile with detected characteristics
        """
        profile = CourseProfile()

        # Read all HTML content from the EPUB
        all_text = self._read_all_content(epub_extract_dir)

        if not all_text:
            return profile

        # Detect technology stack
        self._detect_tech_stack(all_text, profile)

        # Detect expected tools
        self._detect_expected_tools(all_text, profile)

        # Detect teaching patterns
        self._detect_teaching_patterns(all_text, profile, exercises)

        # Detect course conventions
        self._detect_conventions(all_text, profile)

        # Classify hosts
        self._classify_hosts(all_text, profile)

        # Detect referenced collections
        self._detect_collections(all_text, profile)

        return profile

    def _read_all_content(self, epub_dir: Path) -> str:
        """Read all text content from extracted EPUB HTML files."""
        all_text = []

        for html_file in sorted(epub_dir.rglob("*.xhtml")) + sorted(epub_dir.rglob("*.html")):
            try:
                content = html_file.read_text(encoding='utf-8', errors='ignore')
                soup = BeautifulSoup(content, 'html.parser')
                text = soup.get_text(separator=' ', strip=True)
                all_text.append(text)
            except Exception:
                continue

        return '\n'.join(all_text)

    def _detect_tech_stack(self, text: str, profile: CourseProfile):
        """Detect what technologies the course uses."""
        text_lower = text.lower()

        # ansible-navigator
        nav_count = sum(1 for p in self.NAVIGATOR_PATTERNS if re.search(p, text_lower))
        profile.uses_ansible_navigator = nav_count >= 2

        # ansible dev tools
        dev_count = sum(1 for p in self.DEV_TOOLS_PATTERNS if re.search(p, text_lower))
        profile.uses_ansible_dev_tools = dev_count >= 1

        # ansible-playbook (direct usage, not through navigator)
        playbook_refs = len(re.findall(r'ansible-playbook\b', text_lower))
        # Only flag if ansible-playbook is used AND navigator is not the primary tool
        profile.uses_ansible_playbook = playbook_refs > 3 and not profile.uses_ansible_navigator

        # AAP Controller
        aap_count = sum(1 for p in self.AAP_PATTERNS if re.search(p, text_lower))
        profile.uses_aap_controller = aap_count >= 2

        # Containers / EE
        container_count = sum(1 for p in self.CONTAINER_PATTERNS if re.search(p, text_lower))
        profile.uses_containers = container_count >= 2
        profile.uses_execution_environments = bool(re.search(r'execution.environment', text_lower))

        # OpenShift
        oc_count = sum(1 for p in self.OPENSHIFT_PATTERNS if re.search(p, text_lower))
        profile.uses_openshift = oc_count >= 2

    def _detect_expected_tools(self, text: str, profile: CourseProfile):
        """Detect what tools the course expects on the workstation."""
        text_lower = text.lower()

        tool_patterns = {
            'ansible-navigator': r'ansible-navigator',
            'ansible-playbook': r'ansible-playbook',
            'ansible-lint': r'ansible-lint',
            'yamllint': r'yamllint',
            'ansible-galaxy': r'ansible-galaxy',
            'podman': r'\bpodman\b',
            'docker': r'\bdocker\b',
            'oc': r'\boc\s+(?:login|get|create|apply)',
            'git': r'\bgit\s+(?:clone|pull|push|commit)',
            'python3': r'\bpython3?\b',
            'pip': r'\bpip3?\s+install',
            'uv': r'\buv\s+run',
            'ansible-builder': r'ansible-builder',
            'molecule': r'\bmolecule\b',
            'ansible-dev-tools': r'ansible.*dev.*tools',
        }

        for tool, pattern in tool_patterns.items():
            if re.search(pattern, text_lower):
                profile.expected_tools.add(tool)

    def _detect_teaching_patterns(self, text: str, profile: CourseProfile,
                                   exercises: list = None):
        """Detect if the course uses intentional errors as teaching tools."""
        text_lower = text.lower()

        for pattern in self.INTENTIONAL_ERROR_PATTERNS:
            if re.search(pattern, text_lower):
                profile.has_intentional_errors = True
                break

        # Check each exercise for deliberate error patterns
        if exercises:
            for ex in exercises:
                ex_id = ex.id
                # Check if exercise name suggests troubleshooting
                if any(word in ex_id.lower() for word in
                       ['troubleshoot', 'debug', 'fix', 'review', 'diagnose']):
                    profile.exercises_with_deliberate_bugs.add(ex_id)

        # Check for progressive exercise patterns
        if re.search(r'previous\s+exercise|building\s+on|continuation\s+of', text_lower):
            profile.progressive_exercises = True

    def _detect_conventions(self, text: str, profile: CourseProfile):
        """Detect course-specific conventions."""
        text_lower = text.lower()

        profile.uses_sol_files = bool(re.search(r'\.sol\b', text_lower))
        profile.uses_solve_playbooks = bool(re.search(r'lab\s+solve|solve\s+playbook', text_lower))
        profile.uses_lab_grade = bool(re.search(r'lab\s+grade', text_lower))

    def _classify_hosts(self, text: str, profile: CourseProfile):
        """Classify hostnames as real lab hosts vs example/group names."""
        # Find all hostnames referenced in content
        # Standard lab hosts
        for host in self.STANDARD_HOSTS:
            if host in text.lower():
                profile.real_hosts.add(host)

        # Find inventory-style host references
        host_pattern = r'\b([a-z][a-z0-9_-]*(?:\d+)?)\b'
        for match in re.finditer(host_pattern, text.lower()):
            hostname = match.group(1)
            if len(hostname) < 3 or len(hostname) > 30:
                continue

            # Check if it's a known example pattern
            is_example = any(
                re.match(p, hostname)
                for p in self.EXAMPLE_HOST_PATTERNS
            )
            if is_example:
                profile.example_hosts.add(hostname)

    def _detect_collections(self, text: str, profile: CourseProfile):
        """Detect Ansible collections referenced in the coursebook."""
        # FQCN pattern: namespace.collection.module
        fqcn_pattern = r'\b([a-z_]+\.[a-z_]+)\.[a-z_]+\b'
        for match in re.finditer(fqcn_pattern, text.lower()):
            collection = match.group(1)
            if collection != 'ansible.builtin' and '.' in collection:
                # Filter out obvious non-collection matches
                if not any(collection.startswith(prefix) for prefix in
                           ['www.', 'e.g.', 'i.e.', 'lab.example']):
                    profile.referenced_collections.add(collection)
