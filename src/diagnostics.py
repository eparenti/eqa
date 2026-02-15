"""AI-powered diagnostics for exercise testing issues.

Analyzes errors, categorizes problems, and provides intelligent fix suggestions.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Tuple

from .models import SimulationResult, ExecutedStep, Bug, BugSeverity


class IssueCategory(Enum):
    """Categories of issues found during testing."""
    COMMAND_NOT_FOUND = "command_not_found"
    FILE_NOT_FOUND = "file_not_found"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    SYNTAX_ERROR = "syntax_error"
    CONNECTION_ERROR = "connection_error"
    SERVICE_ERROR = "service_error"
    GRADING_BUG = "grading_bug"
    INSTRUCTION_ERROR = "instruction_error"
    ENVIRONMENT_ERROR = "environment_error"
    DEPENDENCY_ERROR = "dependency_error"
    CONFIGURATION_ERROR = "configuration_error"
    UNKNOWN = "unknown"


@dataclass
class DiagnosticIssue:
    """A diagnosed issue with context and fix suggestions."""
    category: IssueCategory
    severity: BugSeverity
    title: str
    description: str
    context: str  # Where it happened
    evidence: List[str]  # Error messages, command outputs
    root_cause: str
    fix_suggestions: List[str]
    verification_steps: List[str]
    affected_exercises: List[str]

    def to_markdown(self) -> str:
        """Format as markdown section."""
        lines = [
            f"### [{self.severity.value}] {self.title}",
            "",
            f"**Category**: {self.category.value.replace('_', ' ').title()}",
            f"**Context**: {self.context}",
            "",
            "**Root Cause**:",
            self.root_cause,
            "",
            "**Evidence**:",
        ]
        for evidence in self.evidence:
            lines.append(f"```")
            lines.append(evidence)
            lines.append(f"```")

        lines.extend([
            "",
            "**Fix Suggestions**:",
        ])
        for i, suggestion in enumerate(self.fix_suggestions, 1):
            lines.append(f"{i}. {suggestion}")

        lines.extend([
            "",
            "**Verification Steps**:",
        ])
        for i, step in enumerate(self.verification_steps, 1):
            lines.append(f"{i}. {step}")

        if self.affected_exercises:
            lines.extend([
                "",
                f"**Affected Exercises**: {', '.join(self.affected_exercises)}",
            ])

        lines.append("")
        return "\n".join(lines)


class ErrorAnalyzer:
    """Analyzes errors and provides intelligent diagnostics."""

    # Error pattern database
    ERROR_PATTERNS = [
        # Command not found
        (r"command not found|No such file or directory.*(/usr/bin|/bin)",
         IssueCategory.COMMAND_NOT_FOUND,
         BugSeverity.P0_BLOCKER),

        # File/directory not found
        (r"No such file or directory|cannot stat|does not exist",
         IssueCategory.FILE_NOT_FOUND,
         BugSeverity.P1_CRITICAL),

        # Permission denied
        (r"Permission denied|Operation not permitted|cannot create directory.*Permission denied",
         IssueCategory.PERMISSION_DENIED,
         BugSeverity.P1_CRITICAL),

        # Timeout
        (r"timeout|timed out|Timeout",
         IssueCategory.TIMEOUT,
         BugSeverity.P1_CRITICAL),

        # Syntax errors
        (r"syntax error|unexpected token|invalid syntax",
         IssueCategory.SYNTAX_ERROR,
         BugSeverity.P2_HIGH),

        # Connection errors
        (r"Connection refused|Connection timed out|Network is unreachable|Could not resolve host",
         IssueCategory.CONNECTION_ERROR,
         BugSeverity.P1_CRITICAL),

        # Service errors
        (r"service.*not running|Failed to start|systemctl.*failed|Unit.*not found",
         IssueCategory.SERVICE_ERROR,
         BugSeverity.P1_CRITICAL),

        # Dependency errors
        (r"No module named|ModuleNotFoundError|ImportError|package.*not installed",
         IssueCategory.DEPENDENCY_ERROR,
         BugSeverity.P1_CRITICAL),

        # Configuration errors
        (r"config.*not found|configuration error|invalid configuration",
         IssueCategory.CONFIGURATION_ERROR,
         BugSeverity.P2_HIGH),
    ]

    def analyze_result(self, result: SimulationResult) -> List[DiagnosticIssue]:
        """Analyze a simulation result and extract diagnostic issues.

        Only analyzes actual failures, not expected errors (WARN status).
        """
        issues = []

        # Only analyze if the exercise actually failed
        if not result.success:
            # Analyze failed steps (exclude WARN - those are expected failures)
            failed_steps = [s for s in result.steps_executed if s.result.value.upper() == 'FAIL']
            for step in failed_steps:
                issue = self._analyze_step_failure(step, result)
                if issue:
                    issues.append(issue)

            # Analyze environment issues (only for actual failures)
            env_issue = self._analyze_environment_issues(result)
            if env_issue:
                issues.append(env_issue)

        # Analyze grading bugs (Labs only) - check for invalid grading behavior
        if hasattr(result, 'grade_without_solution_passed') and hasattr(result, 'grade_with_solution_passed'):
            grading_issue = self._analyze_grading_bugs(result)
            if grading_issue:
                issues.append(grading_issue)

        return issues

    def _analyze_step_failure(self, step: ExecutedStep, result: SimulationResult) -> Optional[DiagnosticIssue]:
        """Analyze a failed step and create a diagnostic issue."""
        if not step.error:
            return None

        error_text = step.error.lower()

        # Match against known patterns
        category = IssueCategory.UNKNOWN
        severity = BugSeverity.P2_HIGH

        for pattern, cat, sev in self.ERROR_PATTERNS:
            if re.search(pattern, step.error, re.IGNORECASE):
                category = cat
                severity = sev
                break

        # Generate context-aware fix suggestions
        fixes = self._generate_fix_suggestions(category, step, result)
        verification = self._generate_verification_steps(category, step)
        root_cause = self._determine_root_cause(category, step)

        return DiagnosticIssue(
            category=category,
            severity=severity,
            title=self._generate_title(category, step),
            description=f"Step {step.number} failed: {step.text[:100]}",
            context=f"{result.exercise_id} - Step {step.number} ({result.phase})",
            evidence=[
                f"Command: {step.command or 'N/A'}",
                f"Error: {step.error}",
            ],
            root_cause=root_cause,
            fix_suggestions=fixes,
            verification_steps=verification,
            affected_exercises=[result.exercise_id],
        )

    def _analyze_grading_bugs(self, result: SimulationResult) -> Optional[DiagnosticIssue]:
        """Analyze grading validation failures."""
        issues = []

        # Check if grading without solution incorrectly passed
        if result.grade_without_solution_passed is True:
            issues.append("Grading script passed without solution (should fail)")

        # Check if grading with solution incorrectly failed
        if result.grade_with_solution_passed is False:
            issues.append("Grading script failed with solution (should pass)")

        if not issues:
            return None

        return DiagnosticIssue(
            category=IssueCategory.GRADING_BUG,
            severity=BugSeverity.P0_BLOCKER,
            title="Grading Script Validation Failed",
            description="The lab grading script does not correctly validate student work",
            context=f"{result.exercise_id} - Grading Validation",
            evidence=issues,
            root_cause=self._diagnose_grading_root_cause(result),
            fix_suggestions=self._generate_grading_fixes(result),
            verification_steps=[
                "Run lab grade without completing any steps - should fail",
                "Complete all lab steps correctly",
                "Run lab grade - should pass with 100% score",
                "Test edge cases (partial completion, incorrect answers)",
            ],
            affected_exercises=[result.exercise_id],
        )

    def _analyze_environment_issues(self, result: SimulationResult) -> Optional[DiagnosticIssue]:
        """Detect patterns that suggest environment problems."""
        # Look for multiple command-not-found errors
        cmd_not_found_count = sum(
            1 for step in result.steps_executed
            if step.error and "command not found" in step.error.lower()
        )

        if cmd_not_found_count >= 2:
            missing_cmds = []
            for step in result.steps_executed:
                if step.error and "command not found" in step.error.lower():
                    match = re.search(r"(\w+): command not found", step.error)
                    if match:
                        missing_cmds.append(match.group(1))

            return DiagnosticIssue(
                category=IssueCategory.ENVIRONMENT_ERROR,
                severity=BugSeverity.P0_BLOCKER,
                title="Multiple Missing Commands Detected",
                description=f"Environment appears to be missing required tools: {', '.join(set(missing_cmds))}",
                context=f"{result.exercise_id} - Environment Setup",
                evidence=[f"Missing commands: {', '.join(set(missing_cmds))}"],
                root_cause="The exercise assumes packages are installed that are not present in the student environment",
                fix_suggestions=[
                    f"Add prerequisite installation steps for: {', '.join(set(missing_cmds))}",
                    "Update the exercise introduction to list required packages",
                    "Add lab setup script that installs dependencies",
                    "Document the required environment in the course prerequisites",
                ],
                verification_steps=[
                    "Provision a fresh student workstation",
                    "Verify all required commands are available before starting exercise",
                    f"Test that '{' '.join(set(missing_cmds))}' commands exist",
                ],
                affected_exercises=[result.exercise_id],
            )

        return None

    def _generate_title(self, category: IssueCategory, step: ExecutedStep) -> str:
        """Generate a clear title for the issue."""
        titles = {
            IssueCategory.COMMAND_NOT_FOUND: f"Command Not Found",
            IssueCategory.FILE_NOT_FOUND: f"File or Directory Missing",
            IssueCategory.PERMISSION_DENIED: f"Permission Denied",
            IssueCategory.TIMEOUT: f"Command Timeout",
            IssueCategory.SYNTAX_ERROR: f"Syntax Error in Command",
            IssueCategory.CONNECTION_ERROR: f"Network Connection Failed",
            IssueCategory.SERVICE_ERROR: f"Service Not Available",
            IssueCategory.DEPENDENCY_ERROR: f"Missing Dependency",
            IssueCategory.CONFIGURATION_ERROR: f"Configuration Error",
            IssueCategory.INSTRUCTION_ERROR: f"Instruction Error",
        }

        base_title = titles.get(category, "Unknown Error")

        # Add command context if available
        if step.command:
            cmd_short = step.command.split()[0] if ' ' in step.command else step.command
            return f"{base_title}: {cmd_short}"

        return base_title

    def _determine_root_cause(self, category: IssueCategory, step: ExecutedStep) -> str:
        """Determine the root cause based on error category and context."""
        root_causes = {
            IssueCategory.COMMAND_NOT_FOUND: self._diagnose_command_not_found(step),
            IssueCategory.FILE_NOT_FOUND: self._diagnose_file_not_found(step),
            IssueCategory.PERMISSION_DENIED: self._diagnose_permission_denied(step),
            IssueCategory.TIMEOUT: self._diagnose_timeout(step),
            IssueCategory.SYNTAX_ERROR: self._diagnose_syntax_error(step),
            IssueCategory.CONNECTION_ERROR: self._diagnose_connection_error(step),
            IssueCategory.SERVICE_ERROR: self._diagnose_service_error(step),
            IssueCategory.DEPENDENCY_ERROR: self._diagnose_dependency_error(step),
            IssueCategory.CONFIGURATION_ERROR: "Configuration file is missing or contains invalid settings",
        }

        return root_causes.get(category, "Unable to determine root cause - manual investigation needed")

    def _diagnose_command_not_found(self, step: ExecutedStep) -> str:
        """Diagnose command not found errors."""
        if not step.command:
            return "Command not available in student environment"

        cmd = step.command.split()[0]

        # Common package mappings
        pkg_mapping = {
            'git': 'git',
            'curl': 'curl',
            'wget': 'wget',
            'docker': 'docker',
            'podman': 'podman',
            'kubectl': 'kubernetes-client',
            'oc': 'openshift-client',
            'ansible': 'ansible',
            'python3': 'python3',
            'pip': 'python3-pip',
            'npm': 'npm',
            'node': 'nodejs',
            'mysql': 'mysql',
            'psql': 'postgresql',
        }

        pkg = pkg_mapping.get(cmd, cmd)
        return f"The command '{cmd}' is not installed. Required package: {pkg}. Either the exercise needs a setup step to install it, or the course prerequisites need updating."

    def _diagnose_file_not_found(self, step: ExecutedStep) -> str:
        """Diagnose file not found errors."""
        # Extract filename from error
        if step.error:
            match = re.search(r"'([^']+)'|\"([^\"]+)\"", step.error)
            if match:
                file = match.group(1) or match.group(2)
                return f"The instruction references file '{file}' which doesn't exist. Either: (1) A previous step failed to create it, (2) The instruction has the wrong path, or (3) A setup step is missing."

        return "The instruction references a file or directory that doesn't exist. This could be due to a missing setup step or incorrect path in the instruction."

    def _diagnose_permission_denied(self, step: ExecutedStep) -> str:
        """Diagnose permission errors."""
        if step.command and 'sudo' not in step.command:
            return "The operation requires elevated privileges, but the instruction doesn't use 'sudo'. Either add 'sudo' to the command or adjust file/directory permissions."

        return "Permission denied - the student user doesn't have rights to perform this operation. Review file ownership and permissions."

    def _diagnose_timeout(self, step: ExecutedStep) -> str:
        """Diagnose timeout errors."""
        return "The command exceeded the timeout limit. Possible causes: (1) Service not running, (2) Infinite loop in script, (3) Network connectivity issue, (4) Command needs more time. Review the command and verify all prerequisites are met."

    def _diagnose_syntax_error(self, step: ExecutedStep) -> str:
        """Diagnose syntax errors."""
        return f"The command has incorrect syntax. Review the instruction for typos, missing quotes, or incorrect shell syntax. Command: {step.command or 'N/A'}"

    def _diagnose_connection_error(self, step: ExecutedStep) -> str:
        """Diagnose connection errors."""
        return "Cannot connect to the target service. Verify: (1) Service is running, (2) Firewall allows connection, (3) Hostname/IP is correct, (4) Network is configured properly."

    def _diagnose_service_error(self, step: ExecutedStep) -> str:
        """Diagnose service errors."""
        if step.command:
            match = re.search(r"systemctl.*start\s+(\S+)|service\s+(\S+)", step.command)
            if match:
                service = match.group(1) or match.group(2)
                return f"Service '{service}' failed to start. Check: (1) Service is installed, (2) Configuration is valid, (3) Dependencies are met, (4) Port conflicts, (5) System logs with 'journalctl -u {service}'"

        return "Service failed to start or is not available. Check service status, configuration, and system logs."

    def _diagnose_dependency_error(self, step: ExecutedStep) -> str:
        """Diagnose dependency errors."""
        if step.error:
            match = re.search(r"No module named '([^']+)'|package\s+(\S+)\s+not", step.error)
            if match:
                module = match.group(1) or match.group(2)
                return f"Python module '{module}' is not installed. Add installation step: 'pip3 install {module}' or document in prerequisites."

        return "Required software dependency is not installed. Add installation steps or update course prerequisites."

    def _diagnose_grading_root_cause(self, result: SimulationResult) -> str:
        """Diagnose grading script issues."""
        causes = []

        if result.grade_without_solution_passed is True:
            causes.append("Grading script has insufficient validation - passes even without student completing the work")

        if result.grade_with_solution_passed is False:
            causes.append("Grading script validation is too strict or checking for wrong conditions - fails even with correct solution")

        return " AND ".join(causes)

    def _generate_fix_suggestions(self, category: IssueCategory, step: ExecutedStep,
                                    result: SimulationResult) -> List[str]:
        """Generate context-aware fix suggestions."""
        fixes = {
            IssueCategory.COMMAND_NOT_FOUND: [
                "Add a setup step to install the required package",
                "Update course prerequisites to list required packages",
                "Add validation step to check command availability before using it",
                "Consider if the command is necessary or if there's an alternative approach",
            ],
            IssueCategory.FILE_NOT_FOUND: [
                "Review previous steps to ensure the file is created correctly",
                "Verify the file path in the instruction is correct",
                "Add a step to create the file or directory if missing",
                "Check if the working directory is correct before running the command",
            ],
            IssueCategory.PERMISSION_DENIED: [
                "Add 'sudo' to the command if it requires root privileges",
                "Create a setup step to adjust file/directory permissions",
                "Ensure the student user is in the correct group for access",
                "Review if the operation should be run as a different user",
            ],
            IssueCategory.TIMEOUT: [
                f"Verify all prerequisite services are running before step {step.number}",
                "Increase the timeout value if the operation legitimately needs more time",
                "Add a step to verify service readiness before proceeding",
                "Check if there's an infinite loop or blocking operation",
            ],
            IssueCategory.SYNTAX_ERROR: [
                f"Review and test the command syntax: {step.command or 'N/A'}",
                "Check for missing quotes, brackets, or other syntax elements",
                "Verify variable substitution is working correctly",
                "Test the command manually to ensure it works",
            ],
            IssueCategory.CONNECTION_ERROR: [
                "Add a step to start the required service",
                "Verify firewall rules allow the connection",
                "Check that the hostname/IP address is correct",
                "Add a connectivity test before attempting the connection",
            ],
            IssueCategory.SERVICE_ERROR: [
                "Verify the service is installed before attempting to start it",
                "Check service configuration files for errors",
                "Review system logs for specific error messages",
                "Ensure all service dependencies are met",
            ],
            IssueCategory.DEPENDENCY_ERROR: [
                "Add installation step for the missing package/module",
                "Update requirements.txt or package.json if applicable",
                "Document the dependency in course prerequisites",
                "Consider using a virtual environment to isolate dependencies",
            ],
            IssueCategory.GRADING_BUG: self._generate_grading_fixes(result),
        }

        return fixes.get(category, [
            "Review the error message and command output",
            "Test the step manually to understand the failure",
            "Check exercise prerequisites and setup steps",
            "Consult with course developers for context",
        ])

    def _generate_grading_fixes(self, result: SimulationResult) -> List[str]:
        """Generate fix suggestions for grading bugs."""
        fixes = []

        if result.grade_without_solution_passed is True:
            fixes.extend([
                "Review the grading script validation logic - it should fail when work is incomplete",
                "Add checks to verify all required files/configurations exist",
                "Ensure grading tests validate actual functionality, not just file existence",
                "Add negative test cases to verify incorrect solutions fail",
            ])

        if result.grade_with_solution_passed is False:
            fixes.extend([
                "Review why the grading script is failing with correct solution",
                "Check if grading script assumptions match the solution approach",
                "Verify grading script doesn't have hardcoded values that don't match solution",
                "Test grading script manually with solution to identify specific failure",
            ])

        if not fixes:
            fixes.append("Review and test the grading script with various student submissions")

        return fixes

    def _generate_verification_steps(self, category: IssueCategory, step: ExecutedStep) -> List[str]:
        """Generate verification steps for the fix."""
        verifications = {
            IssueCategory.COMMAND_NOT_FOUND: [
                "Verify the command is available: which {cmd}",
                "Test the command works: {cmd} --version",
                "Run the exercise from a clean environment",
            ],
            IssueCategory.FILE_NOT_FOUND: [
                "Verify the file exists: ls -la {file}",
                "Check the working directory is correct: pwd",
                "Run all prerequisite steps successfully",
            ],
            IssueCategory.PERMISSION_DENIED: [
                "Check file permissions: ls -la {file}",
                "Verify user can perform the operation",
                "Test the command with adjusted permissions",
            ],
            IssueCategory.TIMEOUT: [
                "Verify all services are running: systemctl status",
                "Test connectivity: ping/curl/telnet",
                "Run the command and monitor for completion",
            ],
        }

        default = [
            f"Fix the instruction at step {step.number}",
            "Test the corrected step manually",
            "Run the full exercise to ensure all steps pass",
        ]

        return verifications.get(category, default)


def analyze_all_results(results: List[SimulationResult]) -> Dict[IssueCategory, List[DiagnosticIssue]]:
    """Analyze all results and group issues by category.

    Returns:
        Dictionary mapping issue categories to lists of issues
    """
    analyzer = ErrorAnalyzer()
    all_issues = []

    for result in results:
        issues = analyzer.analyze_result(result)
        all_issues.extend(issues)

    # Group by category
    grouped: Dict[IssueCategory, List[DiagnosticIssue]] = {}
    for issue in all_issues:
        if issue.category not in grouped:
            grouped[issue.category] = []
        grouped[issue.category].append(issue)

    # Merge issues affecting multiple exercises
    merged: Dict[IssueCategory, List[DiagnosticIssue]] = {}
    for category, issues in grouped.items():
        merged[category] = _merge_similar_issues(issues)

    return merged


def _merge_similar_issues(issues: List[DiagnosticIssue]) -> List[DiagnosticIssue]:
    """Merge similar issues that affect multiple exercises."""
    if len(issues) <= 1:
        return issues

    # Group by title (similar errors)
    groups: Dict[str, List[DiagnosticIssue]] = {}
    for issue in issues:
        # Use root cause as grouping key for better merging
        key = issue.root_cause
        if key not in groups:
            groups[key] = []
        groups[key].append(issue)

    merged = []
    for issues_group in groups.values():
        if len(issues_group) == 1:
            merged.append(issues_group[0])
        else:
            # Merge multiple issues into one
            base = issues_group[0]
            all_exercises = []
            all_evidence = []

            for issue in issues_group:
                all_exercises.extend(issue.affected_exercises)
                all_evidence.extend(issue.evidence)

            base.affected_exercises = sorted(set(all_exercises))
            base.evidence = list(set(all_evidence))[:5]  # Limit evidence
            base.description = f"Affects {len(base.affected_exercises)} exercise(s)"
            merged.append(base)

    return merged


def generate_diagnostics_report(results: List[SimulationResult]) -> str:
    """Generate a comprehensive diagnostics report with AI-powered analysis.

    Args:
        results: List of simulation results to analyze

    Returns:
        Markdown formatted diagnostics report
    """
    grouped_issues = analyze_all_results(results)

    if not grouped_issues:
        return "# Diagnostics Report\n\nNo issues detected. All exercises passed successfully."

    lines = [
        "# AI Diagnostics Report",
        "",
        "This report provides intelligent analysis of issues found during testing,",
        "with root cause analysis and actionable fix suggestions.",
        "",
    ]

    # Summary of issues by severity
    all_issues_flat = [issue for issues in grouped_issues.values() for issue in issues]
    severity_counts = {
        BugSeverity.P0_BLOCKER: sum(1 for i in all_issues_flat if i.severity == BugSeverity.P0_BLOCKER),
        BugSeverity.P1_CRITICAL: sum(1 for i in all_issues_flat if i.severity == BugSeverity.P1_CRITICAL),
        BugSeverity.P2_HIGH: sum(1 for i in all_issues_flat if i.severity == BugSeverity.P2_HIGH),
        BugSeverity.P3_LOW: sum(1 for i in all_issues_flat if i.severity == BugSeverity.P3_LOW),
    }

    lines.extend([
        "## Issue Summary",
        "",
        f"| Severity | Count |",
        f"|----------|-------|",
        f"| P0 (Blocker) | {severity_counts[BugSeverity.P0_BLOCKER]} |",
        f"| P1 (Critical) | {severity_counts[BugSeverity.P1_CRITICAL]} |",
        f"| P2 (High) | {severity_counts[BugSeverity.P2_HIGH]} |",
        f"| P3 (Low) | {severity_counts[BugSeverity.P3_LOW]} |",
        f"| **Total** | **{len(all_issues_flat)}** |",
        "",
        "---",
        "",
    ])

    # Priority order for categories
    priority_order = [
        IssueCategory.GRADING_BUG,
        IssueCategory.ENVIRONMENT_ERROR,
        IssueCategory.COMMAND_NOT_FOUND,
        IssueCategory.DEPENDENCY_ERROR,
        IssueCategory.SERVICE_ERROR,
        IssueCategory.CONNECTION_ERROR,
        IssueCategory.FILE_NOT_FOUND,
        IssueCategory.PERMISSION_DENIED,
        IssueCategory.TIMEOUT,
        IssueCategory.CONFIGURATION_ERROR,
        IssueCategory.SYNTAX_ERROR,
        IssueCategory.INSTRUCTION_ERROR,
        IssueCategory.UNKNOWN,
    ]

    # Output issues by category in priority order
    for category in priority_order:
        if category not in grouped_issues:
            continue

        issues = grouped_issues[category]
        category_name = category.value.replace('_', ' ').title()

        lines.extend([
            f"## {category_name} Issues",
            "",
        ])

        for issue in issues:
            lines.append(issue.to_markdown())
            lines.append("---")
            lines.append("")

    return "\n".join(lines)
