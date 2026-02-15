#!/usr/bin/env python3
"""
Enhanced Progress Reporting with Rich UI

Provides beautiful, informative progress output using rich library.
Falls back to basic output if rich is not available.
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# Try to import rich for enhanced UI
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    from rich.layout import Layout
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class EnhancedProgressReporter:
    """
    Enhanced progress reporting with visual feedback.

    Uses rich library if available, falls back to basic output.
    """

    def __init__(self, verbose: bool = True, use_rich: bool = True):
        """
        Initialize progress reporter.

        Args:
            verbose: Enable detailed output
            use_rich: Use rich library if available
        """
        self.verbose = verbose
        self.use_rich = use_rich and RICH_AVAILABLE

        if self.use_rich:
            self.console = Console()
        else:
            self.console = None

        self.current_phase = None
        self.phase_start_time = None
        self.total_phases = 0
        self.completed_phases = 0

        self.test_stats = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'warnings': 0
        }

        self.current_tests = []

    def print_banner(self, title: str, subtitle: Optional[str] = None):
        """Print a banner."""
        if self.use_rich:
            content = f"[bold cyan]{title}[/bold cyan]"
            if subtitle:
                content += f"\n[dim]{subtitle}[/dim]"

            self.console.print(Panel(
                content,
                box=box.DOUBLE,
                border_style="cyan",
                padding=(1, 2)
            ))
        else:
            print("\n" + "=" * 70)
            print(f"  {title}")
            if subtitle:
                print(f"  {subtitle}")
            print("=" * 70)

    def start_phase(self, phase_name: str, total: Optional[int] = None):
        """
        Start a new phase with visual feedback.

        Args:
            phase_name: Name of the phase
            total: Total number of items (for progress calculation)
        """
        self.current_phase = phase_name
        self.phase_start_time = time.time()

        if total:
            self.total_phases = total

        if not self.verbose:
            return

        if self.use_rich:
            # Create header
            if total and self.completed_phases > 0:
                progress = (self.completed_phases / total) * 100
                header = f"[bold yellow]🔄 {phase_name}[/bold yellow] [dim]({self.completed_phases}/{total} - {progress:.1f}%)[/dim]"
            else:
                header = f"[bold yellow]🔄 {phase_name}[/bold yellow]"

            self.console.rule(header, style="yellow")
        else:
            print(f"\n{'='*70}")
            print(f"🔄 {phase_name}")
            if total and self.completed_phases > 0:
                progress = (self.completed_phases / total) * 100
                print(f"   Progress: {self.completed_phases}/{total} ({progress:.1f}%)")
            print(f"{'='*70}")

    def update(self, message: str, status: str = "info", details: Optional[str] = None):
        """
        Update progress with a message.

        Args:
            message: Status message
            status: Status type (info, success, warning, error, running)
            details: Optional additional details
        """
        if not self.verbose:
            return

        icons = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "running": "🔄",
            "debug": "🐛"
        }

        colors = {
            "info": "blue",
            "success": "green",
            "warning": "yellow",
            "error": "red",
            "running": "cyan",
            "debug": "magenta"
        }

        icon = icons.get(status, "•")
        color = colors.get(status, "white")

        if self.use_rich:
            text = f"{icon} [{color}]{message}[/{color}]"
            if details:
                text += f"\n   [dim]{details}[/dim]"
            self.console.print(f"  {text}")
        else:
            print(f"  {icon} {message}")
            if details:
                print(f"     {details}")

        # Track statistics
        if status == "success":
            self.test_stats['passed'] += 1
        elif status == "error":
            self.test_stats['failed'] += 1
        elif status == "warning":
            self.test_stats['warnings'] += 1

    def complete_phase(self, success: bool = True, summary: Optional[str] = None):
        """
        Complete current phase.

        Args:
            success: Whether phase completed successfully
            summary: Optional summary message
        """
        if not self.verbose:
            return

        if self.phase_start_time:
            duration = time.time() - self.phase_start_time

            if self.use_rich:
                status_icon = "✅" if success else "❌"
                status_color = "green" if success else "red"
                msg = f"  [{status_color}]{status_icon} Completed in {duration:.2f}s[/{status_color}]"

                if summary:
                    msg += f" [dim]- {summary}[/dim]"

                self.console.print(msg)
            else:
                status_icon = "✅" if success else "❌"
                print(f"  {status_icon} Completed in {duration:.2f}s")
                if summary:
                    print(f"     {summary}")

        self.completed_phases += 1
        self.current_phase = None
        self.phase_start_time = None

    def print_test_results_table(self, results: List[Dict[str, Any]]):
        """
        Print test results as a table.

        Args:
            results: List of test results
        """
        if not self.verbose:
            return

        if self.use_rich:
            table = Table(title="Test Results", box=box.ROUNDED)

            table.add_column("Category", style="cyan", no_wrap=True)
            table.add_column("Exercise", style="magenta")
            table.add_column("Status", justify="center")
            table.add_column("Duration", justify="right", style="blue")
            table.add_column("Bugs", justify="center", style="yellow")

            for result in results:
                status_icon = "✅" if result.get('passed') else "❌"
                status_color = "green" if result.get('passed') else "red"

                table.add_row(
                    result.get('category', 'Unknown'),
                    result.get('exercise_id', 'Unknown'),
                    f"[{status_color}]{status_icon}[/{status_color}]",
                    f"{result.get('duration_seconds', 0):.1f}s",
                    str(len(result.get('bugs_found', [])))
                )

            self.console.print(table)
        else:
            print("\n" + "=" * 70)
            print("Test Results:")
            print("-" * 70)
            for result in results:
                status = "PASS" if result.get('passed') else "FAIL"
                print(f"  {result.get('category', 'Unknown'):15} | {result.get('exercise_id', 'Unknown'):25} | {status:6} | {result.get('duration_seconds', 0):6.1f}s | {len(result.get('bugs_found', []))} bugs")
            print("=" * 70)

    def print_summary(self, results: dict):
        """
        Print comprehensive summary.

        Args:
            results: Test results dictionary
        """
        if not self.verbose:
            return

        total_tests = results.get('total_tests', 0)
        passed = results.get('passed', 0)
        failed = results.get('failed', 0)
        duration = results.get('duration_seconds', 0)

        if self.use_rich:
            # Create summary panel
            summary_text = f"""
[bold]Total Tests:[/bold] {total_tests}
[green]✅ Passed:[/green] {passed} ({passed/total_tests*100:.1f}%)
[red]❌ Failed:[/red] {failed} ({failed/total_tests*100:.1f}%)
[blue]⏱️  Duration:[/blue] {duration:.2f}s
            """.strip()

            if results.get('bugs'):
                summary_text += f"\n\n[yellow]🐛 Bugs Found:[/yellow] {len(results['bugs'])}"

                severity_counts = {}
                for bug in results['bugs']:
                    sev = bug.get('severity', 'Unknown')
                    severity_counts[sev] = severity_counts.get(sev, 0) + 1

                for severity in ['P0', 'P1', 'P2', 'P3']:
                    if severity in severity_counts:
                        summary_text += f"\n   {severity}: {severity_counts[severity]}"

            self.console.print(Panel(
                summary_text,
                title="📊 Testing Summary",
                border_style="cyan",
                box=box.DOUBLE
            ))
        else:
            print(f"\n{'='*70}")
            print("📊 TESTING SUMMARY")
            print(f"{'='*70}")
            print(f"  Total Tests: {total_tests}")
            print(f"  ✅ Passed: {passed} ({passed/total_tests*100:.1f}%)" if total_tests > 0 else "  ✅ Passed: 0")
            print(f"  ❌ Failed: {failed} ({failed/total_tests*100:.1f}%)" if total_tests > 0 else "  ❌ Failed: 0")
            print(f"  ⏱️  Duration: {duration:.2f}s")

            if results.get('bugs'):
                print(f"\n  🐛 Bugs Found: {len(results['bugs'])}")
                severity_counts = {}
                for bug in results['bugs']:
                    sev = bug.get('severity', 'Unknown')
                    severity_counts[sev] = severity_counts.get(sev, 0) + 1

                for severity in ['P0', 'P1', 'P2', 'P3']:
                    if severity in severity_counts:
                        print(f"     {severity}: {severity_counts[severity]}")

            print(f"{'='*70}\n")

    def create_progress_bar(self, total: int, description: str = "Processing"):
        """
        Create a progress bar context manager.

        Args:
            total: Total items to process
            description: Description of the task

        Returns:
            Progress context manager (or None if rich not available)
        """
        if not self.use_rich:
            return None

        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console
        )

    def print_bug_details(self, bugs: List[Dict[str, Any]]):
        """
        Print detailed bug information.

        Args:
            bugs: List of bugs
        """
        if not bugs or not self.verbose:
            return

        if self.use_rich:
            for bug in bugs:
                severity = bug.get('severity', 'Unknown')
                severity_colors = {
                    'P0': 'red',
                    'P1': 'yellow',
                    'P2': 'blue',
                    'P3': 'green'
                }
                color = severity_colors.get(severity, 'white')

                content = f"""
[bold]{bug.get('id', 'Unknown')}[/bold]
[{color}]Severity:[/{color}] {severity}
[cyan]Category:[/cyan] {bug.get('category', 'Unknown')}

[yellow]Description:[/yellow]
{bug.get('description', 'No description')}

[green]Fix Recommendation:[/green]
{bug.get('fix_recommendation', 'No recommendation')}

[blue]Verification Steps:[/blue]
""".strip()

                for step in bug.get('verification_steps', []):
                    content += f"\n  {step}"

                self.console.print(Panel(
                    content,
                    border_style=color,
                    box=box.ROUNDED
                ))
                self.console.print()  # Blank line
        else:
            print("\n" + "=" * 70)
            print("🐛 BUG DETAILS")
            print("=" * 70)

            for bug in bugs:
                print(f"\n{bug.get('id', 'Unknown')}")
                print(f"  Severity: {bug.get('severity', 'Unknown')}")
                print(f"  Category: {bug.get('category', 'Unknown')}")
                print(f"\n  Description:")
                print(f"    {bug.get('description', 'No description')}")
                print(f"\n  Fix Recommendation:")
                print(f"    {bug.get('fix_recommendation', 'No recommendation')}")
                print(f"\n  Verification Steps:")
                for step in bug.get('verification_steps', []):
                    print(f"    {step}")
                print("-" * 70)


def demo():
    """Demo the enhanced progress reporter."""
    reporter = EnhancedProgressReporter(verbose=True)

    reporter.print_banner(
        "Exercise QA Testing",
        "Automated quality assurance for Red Hat Training courses"
    )

    # Phase 1
    reporter.start_phase("Environment Setup", total=3)
    reporter.update("Detecting workstation", "running")
    time.sleep(0.5)
    reporter.update("Workstation: workstation", "success")

    reporter.update("Testing SSH connection", "running")
    time.sleep(0.5)
    reporter.update("SSH connection verified", "success")

    reporter.complete_phase(success=True)

    # Phase 2
    reporter.start_phase("Testing Exercise: <exercise-name>", total=3)

    test_categories = ["TC-PREREQ", "TC-EXEC", "TC-SOL", "TC-IDEM", "TC-CLEAN"]
    results = []

    for category in test_categories:
        reporter.update(f"Running {category}", "running")
        time.sleep(0.3)

        # Simulate result
        passed = category != "TC-IDEM"  # Simulate one failure
        results.append({
            'category': category,
            'exercise_id': '<exercise-name>',
            'passed': passed,
            'duration_seconds': 12.5,
            'bugs_found': [] if passed else [{'severity': 'P1'}]
        })

        if passed:
            reporter.update(f"{category} passed", "success")
        else:
            reporter.update(f"{category} failed", "error", "Idempotency check failed")

    reporter.complete_phase(success=False, summary="1 test failed")

    # Print results table
    reporter.print_test_results_table(results)

    # Print summary
    summary = {
        'total_tests': 5,
        'passed': 4,
        'failed': 1,
        'duration_seconds': 62.5,
        'bugs': [
            {
                'id': 'BUG-CONTROL-FLOW-IDEM',
                'severity': 'P1',
                'category': 'TC-IDEM',
                'description': 'Exercise directory not removed after lab finish',
                'fix_recommendation': 'Update finish.yml to remove exercise directory',
                'verification_steps': [
                    '1. Update finish.yml',
                    '2. Run: lab finish <exercise-name>',
                    '3. Verify directory removed'
                ]
            }
        ]
    }

    reporter.print_summary(summary)

    # Print bug details
    reporter.print_bug_details(summary['bugs'])


if __name__ == "__main__":
    demo()
