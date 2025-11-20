"""
Enhanced response wrapper for validated extraction results.

This module provides the ValidatedResponse class which wraps extracted data
with validation results and confidence scores.
"""

from typing import Any, Dict, List, Optional


class ValidatedResponse:
    """
    Enhanced response object that includes extracted data along with
    validation results and confidence scores.

    This class provides a rich interface for accessing extraction quality
    metrics and making decisions about whether to retry or accept the extraction.
    """

    def __init__(
        self,
        data: Dict[str, Any],
        validation_result: Dict[str, Any],
        confidence_scores: Dict[str, Any],
        raw_response: Optional[Any] = None
    ):
        """
        Initialize validated response.

        Args:
            data: The extracted data
            validation_result: Result from ValidationEngine.validate()
            confidence_scores: Result from ConfidenceScorer.calculate_scores()
            raw_response: Original LLM response (optional)
        """
        self._data = data
        self._validation_result = validation_result
        self._confidence_scores = confidence_scores
        self._raw_response = raw_response

    @property
    def data(self) -> Dict[str, Any]:
        """Get the extracted data."""
        return self._data

    @property
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return self._validation_result.get("passed", False)

    @property
    def confidence(self) -> float:
        """Get overall confidence score (0.0-1.0)."""
        return self._confidence_scores.get("overall_confidence", 0.0)

    @property
    def completeness(self) -> float:
        """Get completeness score (0.0-1.0)."""
        return self._confidence_scores.get("completeness", 0.0)

    @property
    def quality_score(self) -> float:
        """Get quality score based on validation (0.0-1.0)."""
        return self._confidence_scores.get("quality_score", 1.0)

    @property
    def field_confidence(self) -> Dict[str, float]:
        """Get per-field confidence scores."""
        return self._confidence_scores.get("field_confidence", {})

    @property
    def errors(self) -> List[Dict[str, Any]]:
        """Get list of validation errors."""
        return self._validation_result.get("errors", [])

    @property
    def warnings(self) -> List[Dict[str, Any]]:
        """Get list of validation warnings."""
        return self._validation_result.get("warnings", [])

    @property
    def has_errors(self) -> bool:
        """Check if there are any validation errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any validation warnings."""
        return len(self.warnings) > 0

    @property
    def missing_required_fields(self) -> List[str]:
        """Get list of missing required fields."""
        return self._confidence_scores.get("missing_required_fields", [])

    @property
    def has_placeholder_values(self) -> bool:
        """Check if data contains placeholder values like 'NA'."""
        return self._confidence_scores.get("has_placeholder_values", False)

    def get_field_confidence(self, field_name: str) -> Optional[float]:
        """
        Get confidence score for a specific field.

        Args:
            field_name: Name of the field

        Returns:
            Confidence score (0.0-1.0) or None if field not found
        """
        return self.field_confidence.get(field_name)

    def get_low_confidence_fields(self, threshold: float = 0.7) -> List[str]:
        """
        Get list of fields with confidence below threshold.

        Args:
            threshold: Minimum acceptable confidence (default 0.7)

        Returns:
            List of field names with low confidence
        """
        return [
            field for field, score in self.field_confidence.items()
            if score < threshold
        ]

    def should_retry(
        self,
        min_confidence: float = 0.7,
        min_completeness: float = 0.8
    ) -> bool:
        """
        Determine if extraction should be retried based on quality metrics.

        Args:
            min_confidence: Minimum acceptable confidence score
            min_completeness: Minimum acceptable completeness score

        Returns:
            True if retry is recommended
        """
        if self.confidence < min_confidence:
            return True

        if self.completeness < min_completeness:
            return True

        if self.missing_required_fields:
            return True

        return False

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert validated response to dictionary format.

        Returns:
            Dictionary containing all response data and metadata
        """
        return {
            "data": self._data,
            "confidence": self.confidence,
            "completeness": self.completeness,
            "quality_score": self.quality_score,
            "field_confidence": self.field_confidence,
            "validation": {
                "passed": self.is_valid,
                "errors": self.errors,
                "warnings": self.warnings,
                "error_count": len(self.errors),
                "warning_count": len(self.warnings)
            },
            "metadata": {
                "has_placeholder_values": self.has_placeholder_values,
                "missing_required_fields": self.missing_required_fields
            }
        }

    def to_legacy_format(self) -> Dict[str, Any]:
        """
        Convert to legacy format (just the data) for backward compatibility.

        This method returns only the extracted data, matching the format
        that existing code expects.

        Returns:
            The extracted data dictionary
        """
        return self._data

    def __repr__(self) -> str:
        """Return string representation of validated response."""
        return (
            f"ValidatedResponse(confidence={self.confidence:.2f}, "
            f"completeness={self.completeness:.2f}, "
            f"errors={len(self.errors)}, "
            f"warnings={len(self.warnings)})"
        )

    def __getitem__(self, key: str) -> Any:
        """
        Allow dictionary-style access to the data.

        This enables using the validated response like a regular dict:
        response["field_name"]
        """
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        """
        Check if a field exists in the data.

        This enables using 'in' operator:
        if "field_name" in response:
        """
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a field value with a default if not found.

        Args:
            key: Field name
            default: Default value if field not found

        Returns:
            Field value or default
        """
        return self._data.get(key, default)

    def keys(self):
        """Get keys from the data (for dict-like interface)."""
        return self._data.keys()

    def values(self):
        """Get values from the data (for dict-like interface)."""
        return self._data.values()

    def items(self):
        """Get items from the data (for dict-like interface)."""
        return self._data.items()
