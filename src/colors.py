"""Colorized terminal output utilities.

Provides ANSI escape code support for terminal output with:
- Auto-detection of TTY
- Respect for NO_COLOR environment variable
- Semantic color methods (success, error, warning, header)
- Severity-based coloring for P0-P3 bugs
"""

import os
import sys
from typing import Optional


class ColorFormatter:
    """Terminal color formatter with ANSI escape codes."""

    # ANSI escape codes
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colors
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"

    def __init__(self, force_color: Optional[bool] = None):
        """
        Initialize color formatter.

        Args:
            force_color: If True, force colors on. If False, force colors off.
                        If None, auto-detect based on TTY and NO_COLOR.
        """
        self._force_color = force_color
        self._enabled = self._should_enable_colors()

    def _should_enable_colors(self) -> bool:
        """Determine if colors should be enabled."""
        # Explicit override
        if self._force_color is not None:
            return self._force_color

        # Respect NO_COLOR environment variable (https://no-color.org/)
        if os.environ.get("NO_COLOR"):
            return False

        # Check if FORCE_COLOR is set
        if os.environ.get("FORCE_COLOR"):
            return True

        # Check if stdout is a TTY
        if not hasattr(sys.stdout, "isatty"):
            return False

        return sys.stdout.isatty()

    @property
    def enabled(self) -> bool:
        """Check if colors are enabled."""
        return self._enabled

    def enable(self):
        """Enable color output."""
        self._enabled = True

    def disable(self):
        """Disable color output."""
        self._enabled = False

    def _wrap(self, text: str, *codes: str) -> str:
        """Wrap text with ANSI codes if enabled."""
        if not self._enabled:
            return text
        code_str = "".join(codes)
        return f"{code_str}{text}{self.RESET}"

    # Semantic methods

    def success(self, text: str) -> str:
        """Format text as success (green)."""
        return self._wrap(text, self.GREEN)

    def error(self, text: str) -> str:
        """Format text as error (red)."""
        return self._wrap(text, self.RED)

    def warning(self, text: str) -> str:
        """Format text as warning (yellow)."""
        return self._wrap(text, self.YELLOW)

    def info(self, text: str) -> str:
        """Format text as info (cyan)."""
        return self._wrap(text, self.CYAN)

    def header(self, text: str) -> str:
        """Format text as header (bold blue)."""
        return self._wrap(text, self.BOLD, self.BLUE)

    def title(self, text: str) -> str:
        """Format text as title (bold white)."""
        return self._wrap(text, self.BOLD, self.WHITE)

    def dim(self, text: str) -> str:
        """Format text as dimmed."""
        return self._wrap(text, self.DIM)

    def bold(self, text: str) -> str:
        """Format text as bold."""
        return self._wrap(text, self.BOLD)

    def underline(self, text: str) -> str:
        """Format text as underlined."""
        return self._wrap(text, self.UNDERLINE)

    # Severity-based coloring for bugs

    def severity(self, text: str, level: str) -> str:
        """
        Format text based on bug severity level.

        Args:
            text: Text to format
            level: Severity level (P0, P1, P2, P3)

        Returns:
            Formatted text
        """
        level_upper = level.upper()
        if level_upper == "P0":
            # Blocker - bright red with bold
            return self._wrap(text, self.BOLD, self.BRIGHT_RED)
        elif level_upper == "P1":
            # Critical - red
            return self._wrap(text, self.RED)
        elif level_upper == "P2":
            # High - yellow
            return self._wrap(text, self.YELLOW)
        elif level_upper == "P3":
            # Low - dim
            return self._wrap(text, self.DIM)
        else:
            return text

    def severity_badge(self, level: str) -> str:
        """
        Create a colored severity badge.

        Args:
            level: Severity level (P0, P1, P2, P3)

        Returns:
            Formatted badge like [P0]
        """
        return self.severity(f"[{level.upper()}]", level)

    # Status indicators

    def pass_status(self, text: str = "PASS") -> str:
        """Format pass status."""
        return self._wrap(text, self.GREEN, self.BOLD)

    def fail_status(self, text: str = "FAIL") -> str:
        """Format fail status."""
        return self._wrap(text, self.RED, self.BOLD)

    def skip_status(self, text: str = "SKIP") -> str:
        """Format skip status."""
        return self._wrap(text, self.YELLOW)

    # Icons with color

    def check_icon(self) -> str:
        """Return a green checkmark."""
        return self.success("✓")

    def cross_icon(self) -> str:
        """Return a red cross."""
        return self.error("✗")

    def warning_icon(self) -> str:
        """Return a yellow warning sign."""
        return self.warning("⚠")

    def info_icon(self) -> str:
        """Return a cyan info icon."""
        return self.info("ℹ")

    # Composite formatting

    def test_result(self, passed: bool, category: str, duration: float) -> str:
        """
        Format a test result line.

        Args:
            passed: Whether the test passed
            category: Test category name
            duration: Duration in seconds

        Returns:
            Formatted result line
        """
        if passed:
            icon = self.check_icon()
            status = self.pass_status()
        else:
            icon = self.cross_icon()
            status = self.fail_status()

        duration_str = self.dim(f"({duration:.1f}s)")
        return f"   {icon} {status} {category} {duration_str}"

    def bug_line(self, severity: str, description: str) -> str:
        """
        Format a bug description line.

        Args:
            severity: Bug severity (P0, P1, P2, P3)
            description: Bug description

        Returns:
            Formatted bug line
        """
        badge = self.severity_badge(severity)
        return f"      {badge} {description}"

    def section_header(self, title: str, width: int = 70) -> str:
        """
        Format a section header with decorative line.

        Args:
            title: Section title
            width: Total width of the header

        Returns:
            Formatted header
        """
        line = "=" * width
        return f"{self.bold(line)}\n{self.header(title)}\n{self.bold(line)}"

    def progress_header(self, current: int, total: int, name: str) -> str:
        """
        Format a progress header.

        Args:
            current: Current item number
            total: Total items
            name: Item name

        Returns:
            Formatted progress header
        """
        progress = self.dim(f"[{current}/{total}]")
        return f"\n{progress} {self.bold(name)}"


# Global formatter instance
_formatter: Optional[ColorFormatter] = None


def get_formatter() -> ColorFormatter:
    """Get the global color formatter instance."""
    global _formatter
    if _formatter is None:
        _formatter = ColorFormatter()
    return _formatter


def set_formatter(formatter: ColorFormatter):
    """Set the global color formatter instance."""
    global _formatter
    _formatter = formatter


def disable_colors():
    """Disable colors globally."""
    get_formatter().disable()


def enable_colors():
    """Enable colors globally."""
    get_formatter().enable()


# Convenience functions that use the global formatter


def success(text: str) -> str:
    """Format text as success."""
    return get_formatter().success(text)


def error(text: str) -> str:
    """Format text as error."""
    return get_formatter().error(text)


def warning(text: str) -> str:
    """Format text as warning."""
    return get_formatter().warning(text)


def info(text: str) -> str:
    """Format text as info."""
    return get_formatter().info(text)


def header(text: str) -> str:
    """Format text as header."""
    return get_formatter().header(text)


def bold(text: str) -> str:
    """Format text as bold."""
    return get_formatter().bold(text)


def dim(text: str) -> str:
    """Format text as dimmed."""
    return get_formatter().dim(text)


def severity(text: str, level: str) -> str:
    """Format text based on severity level."""
    return get_formatter().severity(text, level)


def severity_badge(level: str) -> str:
    """Create a colored severity badge."""
    return get_formatter().severity_badge(level)
