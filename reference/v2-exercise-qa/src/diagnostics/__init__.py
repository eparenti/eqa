"""Diagnostics module for error pattern matching and fix recommendations.

Provides AI-assisted failure analysis by:
- Matching error output against known patterns
- Generating fix recommendations with commands
- Providing verification steps
"""

from .patterns import ERROR_PATTERNS, PatternInfo
from .error_analyzer import ErrorAnalyzer, DiagnosticResult, Recommendation

__all__ = [
    "ERROR_PATTERNS",
    "PatternInfo",
    "ErrorAnalyzer",
    "DiagnosticResult",
    "Recommendation",
]
