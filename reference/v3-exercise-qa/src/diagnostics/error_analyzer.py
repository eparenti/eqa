"""Error analysis and recommendation generation.

Analyzes error output against known patterns and generates
actionable fix recommendations with commands and verification steps.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from .patterns import ERROR_PATTERNS, PatternInfo, ErrorCategory


@dataclass
class Recommendation:
    """A fix recommendation with commands and verification."""
    title: str
    description: str
    commands: List[str] = field(default_factory=list)
    verification_steps: List[str] = field(default_factory=list)
    priority: int = 1  # 1 = highest priority


@dataclass
class DiagnosticResult:
    """Result of error pattern matching and analysis."""
    pattern_name: str
    pattern_title: str
    severity: str
    category: str
    matched_text: str
    extracted_values: Dict[str, str]
    recommendations: List[Recommendation]
    line_number: Optional[int] = None
    file_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "pattern_name": self.pattern_name,
            "pattern_title": self.pattern_title,
            "severity": self.severity,
            "category": self.category,
            "matched_text": self.matched_text,
            "extracted_values": self.extracted_values,
            "line_number": self.line_number,
            "file_path": self.file_path,
            "recommendations": [
                {
                    "title": r.title,
                    "description": r.description,
                    "commands": r.commands,
                    "verification_steps": r.verification_steps,
                    "priority": r.priority
                }
                for r in self.recommendations
            ]
        }


class ErrorAnalyzer:
    """Analyzes error output and generates fix recommendations."""

    # Common regex for extracting context
    LINE_NUMBER_RE = re.compile(r"line (\d+)", re.IGNORECASE)
    FILE_PATH_RE = re.compile(r"in '([^']+\.ya?ml)'|\"([^\"]+\.ya?ml)\"")
    HOST_RE = re.compile(r"(?:host|server)[a-z]?\b|workstation", re.IGNORECASE)

    def __init__(self, exercise_id: Optional[str] = None):
        """
        Initialize error analyzer.

        Args:
            exercise_id: Optional exercise ID for context in recommendations
        """
        self.exercise_id = exercise_id or "<exercise-id>"

    def analyze(self, error_text: str) -> List[DiagnosticResult]:
        """
        Analyze error text and return diagnostic results.

        Args:
            error_text: Error output to analyze

        Returns:
            List of diagnostic results with recommendations
        """
        results = []

        for pattern in ERROR_PATTERNS:
            match = pattern.regex.search(error_text)
            if match:
                result = self._create_result(pattern, match, error_text)
                results.append(result)

        # Sort by severity (P0 first)
        results.sort(key=lambda r: r.severity)

        return results

    def analyze_single(self, error_text: str) -> Optional[DiagnosticResult]:
        """
        Analyze error text and return the highest priority diagnostic.

        Args:
            error_text: Error output to analyze

        Returns:
            Single highest priority diagnostic result, or None
        """
        results = self.analyze(error_text)
        return results[0] if results else None

    def _create_result(
        self,
        pattern: PatternInfo,
        match: re.Match,
        full_text: str
    ) -> DiagnosticResult:
        """Create a diagnostic result from a pattern match."""
        # Extract named groups
        extracted = {}
        for group_name in pattern.extract_groups:
            try:
                value = match.group(group_name)
                if value:
                    extracted[group_name] = value
            except IndexError:
                pass

        # Extract line number and file path from full text
        line_number = None
        line_match = self.LINE_NUMBER_RE.search(full_text)
        if line_match:
            line_number = int(line_match.group(1))

        file_path = None
        file_match = self.FILE_PATH_RE.search(full_text)
        if file_match:
            file_path = file_match.group(1) or file_match.group(2)

        # Try to extract host
        host_match = self.HOST_RE.search(full_text)
        if host_match:
            extracted.setdefault("host", host_match.group(0))

        # Add exercise_id to extracted values
        extracted["exercise_id"] = self.exercise_id

        # Generate recommendations
        recommendations = self._generate_recommendations(pattern, extracted)

        return DiagnosticResult(
            pattern_name=pattern.name,
            pattern_title=pattern.title,
            severity=pattern.severity,
            category=pattern.category.value,
            matched_text=match.group(0)[:200],
            extracted_values=extracted,
            recommendations=recommendations,
            line_number=line_number,
            file_path=file_path
        )

    def _generate_recommendations(
        self,
        pattern: PatternInfo,
        extracted: Dict[str, str]
    ) -> List[Recommendation]:
        """Generate fix recommendations for a pattern match."""
        recommendations = []

        # Add pattern-specific recommendations based on category
        category = pattern.category

        if category == ErrorCategory.COLLECTION:
            recommendations.extend(self._collection_recommendations(pattern, extracted))
        elif category == ErrorCategory.CONNECTIVITY:
            recommendations.extend(self._connectivity_recommendations(pattern, extracted))
        elif category == ErrorCategory.FILE_SYSTEM:
            recommendations.extend(self._filesystem_recommendations(pattern, extracted))
        elif category == ErrorCategory.VARIABLE:
            recommendations.extend(self._variable_recommendations(pattern, extracted))
        elif category == ErrorCategory.SYNTAX:
            recommendations.extend(self._syntax_recommendations(pattern, extracted))
        elif category == ErrorCategory.PERMISSION:
            recommendations.extend(self._permission_recommendations(pattern, extracted))
        elif category == ErrorCategory.SERVICE:
            recommendations.extend(self._service_recommendations(pattern, extracted))
        elif category == ErrorCategory.NETWORK_DEVICE:
            recommendations.extend(self._network_device_recommendations(pattern, extracted))
        elif category == ErrorCategory.LAB_COMMAND:
            recommendations.extend(self._lab_command_recommendations(pattern, extracted))
        else:
            # Generic recommendation from template
            recommendations.append(self._generic_recommendation(pattern, extracted))

        return recommendations

    def _generic_recommendation(
        self,
        pattern: PatternInfo,
        extracted: Dict[str, str]
    ) -> Recommendation:
        """Create a generic recommendation from pattern templates."""
        # Format templates with extracted values
        fix_text = self._format_template(pattern.fix_template, extracted)
        verification = [
            self._format_template(v, extracted)
            for v in pattern.verification_template
        ]

        return Recommendation(
            title=f"Fix {pattern.title}",
            description=fix_text,
            commands=[],
            verification_steps=verification,
            priority=1
        )

    def _format_template(self, template: str, values: Dict[str, str]) -> str:
        """Format a template string with extracted values."""
        result = template
        for key, value in values.items():
            result = result.replace("{" + key + "}", str(value))
        # Handle missing keys by leaving placeholder
        return result

    def _collection_recommendations(
        self,
        pattern: PatternInfo,
        extracted: Dict[str, str]
    ) -> List[Recommendation]:
        """Generate recommendations for collection errors."""
        recommendations = []
        module = extracted.get("module", "unknown.module")

        # Try to guess collection from module FQCN
        parts = module.split(".")
        if len(parts) >= 2:
            collection_name = f"{parts[0]}.{parts[1]}"
        else:
            collection_name = module

        extracted["collection_name"] = collection_name

        # Quick install
        recommendations.append(Recommendation(
            title="Quick Install (Recommended)",
            description="Install the missing collection immediately",
            commands=[
                f"ansible-galaxy collection install {collection_name}",
                f"ansible-galaxy collection list | grep {collection_name}"
            ],
            verification_steps=[
                "ansible-navigator run <playbook>.yml -m stdout --syntax-check"
            ],
            priority=1
        ))

        # Add to requirements.yml
        recommendations.append(Recommendation(
            title="Add to requirements.yml (Permanent Fix)",
            description="Add collection to requirements.yml for persistent installation",
            commands=[
                "# Edit requirements.yml and add:",
                f"#   - name: {collection_name}",
                f"ansible-galaxy collection install -r requirements.yml"
            ],
            verification_steps=[
                f"ansible-galaxy collection list | grep {collection_name}"
            ],
            priority=2
        ))

        return recommendations

    def _connectivity_recommendations(
        self,
        pattern: PatternInfo,
        extracted: Dict[str, str]
    ) -> List[Recommendation]:
        """Generate recommendations for connectivity errors."""
        recommendations = []
        host = extracted.get("host", "<host>")
        exercise_id = extracted.get("exercise_id", "<exercise>")

        recommendations.append(Recommendation(
            title="Check Lab Environment (Recommended)",
            description="Verify lab is started and hosts are running",
            commands=[
                f"lab status {exercise_id}",
                f"ping -c 1 {host}",
                f"ssh {host} hostname"
            ],
            verification_steps=[
                f"ansible all -m ping"
            ],
            priority=1
        ))

        recommendations.append(Recommendation(
            title="Restart Lab",
            description="Reset lab environment to fix connectivity",
            commands=[
                f"lab finish {exercise_id}",
                f"lab start {exercise_id}"
            ],
            verification_steps=[
                f"lab status {exercise_id}",
                f"ssh {host} hostname"
            ],
            priority=2
        ))

        return recommendations

    def _filesystem_recommendations(
        self,
        pattern: PatternInfo,
        extracted: Dict[str, str]
    ) -> List[Recommendation]:
        """Generate recommendations for file system errors."""
        recommendations = []
        file_path = extracted.get("file", extracted.get("path", "<file>"))

        # Get basename for search
        if "/" in file_path:
            basename = file_path.split("/")[-1]
        else:
            basename = file_path

        extracted["basename"] = basename

        recommendations.append(Recommendation(
            title="Check File Path (Recommended)",
            description="Verify the file exists and path is correct",
            commands=[
                f"ls -la {file_path}",
                f"find . -name '{basename}'",
                "ls -la files/ templates/"
            ],
            verification_steps=[
                f"test -f {file_path} && echo 'File exists'"
            ],
            priority=1
        ))

        recommendations.append(Recommendation(
            title="Create Missing File",
            description="Create the file if it should exist",
            commands=[
                f"# Create the file:",
                f"touch {file_path}",
                "# Or create with content:",
                f"cat > {file_path} << 'EOF'\n<content>\nEOF"
            ],
            verification_steps=[
                f"ls -la {file_path}"
            ],
            priority=2
        ))

        return recommendations

    def _variable_recommendations(
        self,
        pattern: PatternInfo,
        extracted: Dict[str, str]
    ) -> List[Recommendation]:
        """Generate recommendations for variable errors."""
        recommendations = []
        variable = extracted.get("variable", "<variable>")

        recommendations.append(Recommendation(
            title="Define Variable (Recommended)",
            description=f"Add definition for '{variable}'",
            commands=[
                "# In playbook vars section:",
                "vars:",
                f"  {variable}: <value>",
                "",
                "# Or in vars file:",
                f"echo '{variable}: <value>' >> vars.yml"
            ],
            verification_steps=[
                f"grep -r '{variable}' *.yml",
                "ansible-playbook --syntax-check <playbook>.yml"
            ],
            priority=1
        ))

        recommendations.append(Recommendation(
            title="Use Default Filter",
            description="Make variable optional with a default value",
            commands=[
                f"# Change from:",
                f'# "{{{{ {variable} }}}}"',
                f"# To:",
                f'# "{{{{ {variable} | default(\'default_value\') }}}}"'
            ],
            verification_steps=[],
            priority=2
        ))

        return recommendations

    def _syntax_recommendations(
        self,
        pattern: PatternInfo,
        extracted: Dict[str, str]
    ) -> List[Recommendation]:
        """Generate recommendations for syntax errors."""
        recommendations = []
        line = extracted.get("line", "unknown")

        recommendations.append(Recommendation(
            title="Fix YAML Syntax (Recommended)",
            description=f"Check indentation and syntax around line {line}",
            commands=[
                f"# View lines around error:",
                f"head -n $((line + 5)) <file>.yml | tail -15",
                "",
                "# Validate with yamllint:",
                "yamllint <file>.yml",
                "",
                "# Common issues:",
                "# - Use 2-space indentation",
                "# - Space after colons",
                "# - Proper quote matching"
            ],
            verification_steps=[
                "yamllint <file>.yml",
                "ansible-playbook --syntax-check <file>.yml"
            ],
            priority=1
        ))

        return recommendations

    def _permission_recommendations(
        self,
        pattern: PatternInfo,
        extracted: Dict[str, str]
    ) -> List[Recommendation]:
        """Generate recommendations for permission errors."""
        recommendations = []

        recommendations.append(Recommendation(
            title="Add Privilege Escalation (Recommended)",
            description="Use become to elevate privileges",
            commands=[
                "# Add to task:",
                "- name: Task name",
                "  <module>: ...",
                "  become: true",
                "",
                "# Or at play level:",
                "- name: Play name",
                "  hosts: all",
                "  become: true"
            ],
            verification_steps=[
                "# Re-run playbook"
            ],
            priority=1
        ))

        if "selinux" in pattern.name.lower():
            recommendations.append(Recommendation(
                title="Fix SELinux Context",
                description="Restore or set correct SELinux context",
                commands=[
                    "# Check current context:",
                    "ls -lZ <path>",
                    "",
                    "# Restore default context:",
                    "restorecon -Rv <path>",
                    "",
                    "# Set specific context:",
                    "chcon -t httpd_sys_content_t <path>"
                ],
                verification_steps=[
                    "getenforce",
                    "ls -lZ <path>"
                ],
                priority=2
            ))

        return recommendations

    def _service_recommendations(
        self,
        pattern: PatternInfo,
        extracted: Dict[str, str]
    ) -> List[Recommendation]:
        """Generate recommendations for service errors."""
        recommendations = []
        service = (
            extracted.get("service") or
            extracted.get("service2") or
            extracted.get("service3") or
            "<service>"
        )

        recommendations.append(Recommendation(
            title="Check Service Status (Recommended)",
            description=f"Investigate why {service} failed",
            commands=[
                f"systemctl status {service}",
                f"journalctl -u {service} -n 50",
                f"systemctl list-unit-files | grep {service}"
            ],
            verification_steps=[
                f"systemctl is-active {service}"
            ],
            priority=1
        ))

        recommendations.append(Recommendation(
            title="Restart Service",
            description="Try restarting the service",
            commands=[
                f"sudo systemctl restart {service}",
                f"sudo systemctl enable {service}"
            ],
            verification_steps=[
                f"systemctl status {service}"
            ],
            priority=2
        ))

        return recommendations

    def _network_device_recommendations(
        self,
        pattern: PatternInfo,
        extracted: Dict[str, str]
    ) -> List[Recommendation]:
        """Generate recommendations for network device errors."""
        recommendations = []
        host = extracted.get("host", "<device>")

        recommendations.append(Recommendation(
            title="Increase Timeout (Recommended)",
            description="Network devices often need longer timeouts",
            commands=[
                "# In inventory or group_vars:",
                "ansible_command_timeout: 60",
                "ansible_connect_timeout: 30",
                "",
                "# For network_cli:",
                "ansible_network_cli_ssh_type: paramiko"
            ],
            verification_steps=[
                f"ping {host}",
                "ansible-navigator run <playbook>.yml -m stdout"
            ],
            priority=1
        ))

        recommendations.append(Recommendation(
            title="Check Device Connectivity",
            description="Verify network device is reachable",
            commands=[
                f"ping {host}",
                f"ssh {host} 'show version'",
                "# Check inventory settings"
            ],
            verification_steps=[
                f"ssh {host} 'show version'"
            ],
            priority=2
        ))

        return recommendations

    def _lab_command_recommendations(
        self,
        pattern: PatternInfo,
        extracted: Dict[str, str]
    ) -> List[Recommendation]:
        """Generate recommendations for lab command errors."""
        recommendations = []
        exercise_id = extracted.get("exercise_id", "<exercise>")

        recommendations.append(Recommendation(
            title="Reset Lab Environment (Recommended)",
            description="Restart the lab from a clean state",
            commands=[
                f"lab finish {exercise_id}",
                f"lab start {exercise_id}",
                f"lab status {exercise_id}"
            ],
            verification_steps=[
                f"lab status {exercise_id}"
            ],
            priority=1
        ))

        if "grade" in pattern.name:
            recommendations.append(Recommendation(
                title="Apply Solutions",
                description="Copy solution files and re-grade",
                commands=[
                    "# Copy solution files:",
                    "cp solutions/*.sol .",
                    "",
                    "# Or specific file:",
                    "cp solutions/playbook.yml.sol playbook.yml",
                    "",
                    f"lab grade {exercise_id}"
                ],
                verification_steps=[
                    f"lab grade {exercise_id}"
                ],
                priority=2
            ))

        return recommendations


def analyze_error(error_text: str, exercise_id: Optional[str] = None) -> List[DiagnosticResult]:
    """
    Convenience function to analyze error text.

    Args:
        error_text: Error output to analyze
        exercise_id: Optional exercise ID for context

    Returns:
        List of diagnostic results
    """
    analyzer = ErrorAnalyzer(exercise_id)
    return analyzer.analyze(error_text)


def get_top_recommendation(error_text: str, exercise_id: Optional[str] = None) -> Optional[Recommendation]:
    """
    Get the top recommendation for an error.

    Args:
        error_text: Error output to analyze
        exercise_id: Optional exercise ID for context

    Returns:
        Top priority recommendation, or None
    """
    analyzer = ErrorAnalyzer(exercise_id)
    result = analyzer.analyze_single(error_text)
    if result and result.recommendations:
        return result.recommendations[0]
    return None
