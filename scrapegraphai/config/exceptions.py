"""
Custom exceptions for configuration validation.
"""
from typing import Optional, List


class ConfigurationError(Exception):
    """Raised when graph configuration is invalid."""

    def __init__(self, message: str, suggestions: Optional[List[str]] = None):
        """
        Initialize ConfigurationError with message and optional suggestions.

        Args:
            message: The error message describing the configuration problem
            suggestions: Optional list of helpful suggestions for fixing the error
        """
        super().__init__(message)
        self.suggestions = suggestions or []

    def __str__(self):
        """
        Format the error message with suggestions if available.

        Returns:
            Formatted error message with suggestions
        """
        msg = super().__str__()
        if self.suggestions:
            msg += "\n\nSuggestions:\n"
            msg += "\n".join(f"  - {s}" for s in self.suggestions)
        return msg
