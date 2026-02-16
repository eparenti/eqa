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

    # Development environment
    uses_dev_containers: bool = False
    uses_vscode: bool = False
    dev_container_image: Optional[str] = None

    # Tool locations (workstation, container, or both)
    workstation_tools: Set[str] = field(default_factory=set)
    container_tools: Set[str] = field(default_factory=set)
    expected_tools: Set[str] = field(default_factory=set)  # All tools

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

    def tool_location(self, tool: str) -> str:
        """Determine where a tool is expected to run.

        Returns: 'workstation', 'container', 'both', or 'unknown'
        """
        in_workstation = tool in self.workstation_tools
        in_container = tool in self.container_tools

        if in_workstation and in_container:
            return 'both'
        elif in_workstation:
            return 'workstation'
        elif in_container:
            return 'container'
        elif tool in self.expected_tools:
            return 'unknown'
        return 'unknown'

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

    def summary(self) -> str:
        """Generate a human-readable summary of the course profile."""
        lines = []
        lines.append("Course Profile:")

        # Development environment
        env = []
        if self.uses_dev_containers:
            env.append("dev containers")
            if self.dev_container_image:
                env.append(f"({self.dev_container_image.split('/')[-1]})")
        if self.uses_vscode:
            env.append("VS Code")
        if env:
            lines.append(f"  Environment: {' + '.join(env)}")

        # Technology stack
        tech = []
        if self.uses_ansible_navigator:
            location = "container" if self.uses_dev_containers else "workstation"
            tech.append(f"ansible-navigator ({location})")
        if self.uses_ansible_playbook:
            tech.append("ansible-playbook")
        if self.uses_ansible_dev_tools:
            tech.append("ansible-dev-tools")
        if self.uses_aap_controller:
            tech.append("AAP Controller")
        if self.uses_execution_environments:
            tech.append("EE")
        if self.uses_containers and not self.uses_dev_containers:
            tech.append("containers")
        if self.uses_openshift:
            tech.append("OpenShift")

        if tech:
            lines.append(f"  Technology: {', '.join(tech)}")

        # Tool locations
        if self.workstation_tools:
            tools = sorted(self.workstation_tools)[:4]
            more = f" + {len(self.workstation_tools) - 4} more" if len(self.workstation_tools) > 4 else ""
            lines.append(f"  Workstation tools: {', '.join(tools)}{more}")

        if self.container_tools:
            tools = sorted(self.container_tools)[:4]
            more = f" + {len(self.container_tools) - 4} more" if len(self.container_tools) > 4 else ""
            lines.append(f"  Container tools: {', '.join(tools)}{more}")

        # Collections
        if self.referenced_collections:
            colls = sorted(self.referenced_collections)[:3]
            more = f" + {len(self.referenced_collections) - 3} more" if len(self.referenced_collections) > 3 else ""
            lines.append(f"  Collections: {', '.join(colls)}{more}")

        # Teaching patterns
        patterns = []
        if self.has_intentional_errors:
            patterns.append("intentional errors")
        if self.progressive_exercises:
            patterns.append("progressive exercises")
        if patterns:
            lines.append(f"  Teaching patterns: {', '.join(patterns)}")

        return "\n".join(lines)


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

        # Detect development environment FIRST (affects tool location detection)
        self._detect_dev_environment(all_text, profile)

        # Detect technology stack
        self._detect_tech_stack(all_text, profile)

        # Detect expected tools and their locations
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

    def _detect_dev_environment(self, text: str, profile: CourseProfile):
        """Detect development environment (dev containers, VS Code, etc.)."""
        text_lower = text.lower()

        # Dev containers
        devcontainer_indicators = [
            r'\.devcontainer',
            r'devcontainer\.json',
            r'development\s+container',
            r'dev\s+container',
            r'open.*folder.*inside.*dev',
            r'reopen.*in.*container',
        ]
        devcontainer_count = sum(1 for p in devcontainer_indicators if re.search(p, text_lower))
        profile.uses_dev_containers = devcontainer_count >= 2

        # Extract dev container image if found
        if profile.uses_dev_containers:
            # Look for common image patterns
            image_match = re.search(r'(registry\.redhat\.io/[^\s"]+|quay\.io/[^\s"]+)', text)
            if image_match:
                profile.dev_container_image = image_match.group(1)

        # VS Code
        vscode_indicators = [
            r'visual\s+studio\s+code',
            r'\bvs\s+code\b',
            r'\bvscode\b',
            r'explorer\s+icon.*activity\s+bar',
            r'click.*file.*›.*new.*text.*file',
            r'activities\s+overview.*red\s+hat',  # Common VS Code workflow in courses
        ]
        vscode_count = sum(1 for p in vscode_indicators if re.search(p, text_lower))
        profile.uses_vscode = vscode_count >= 2

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
        """Detect what tools the course expects and where they run."""
        text_lower = text.lower()

        # Define tool patterns and their likely locations
        tool_patterns = {
            'lab': r'\blab\s+(?:start|finish|grade)',
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

                # Determine tool location based on course structure
                if tool == 'lab':
                    # lab command always runs on workstation
                    profile.workstation_tools.add(tool)
                elif profile.uses_dev_containers:
                    # In dev container courses, classify tools by usage context
                    if tool in ['ansible-navigator', 'ansible-playbook', 'ansible-lint',
                                'yamllint', 'ansible-galaxy', 'ansible-builder', 'molecule']:
                        # Ansible tools run in container
                        profile.container_tools.add(tool)
                    elif tool in ['git', 'podman', 'oc']:
                        # These may be on workstation or both
                        profile.workstation_tools.add(tool)
                    else:
                        # Others likely in container
                        profile.container_tools.add(tool)
                else:
                    # Traditional courses - everything on workstation
                    profile.workstation_tools.add(tool)

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
