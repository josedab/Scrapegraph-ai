"""
Confidence scoring system for LLM-extracted data.

The ConfidenceScorer calculates various quality metrics including:
- Overall confidence score
- Completeness score (% of expected fields found)
- Quality score (format and validation compliance)
- Per-field confidence scores
"""

from typing import Any, Dict, List, Optional


class ConfidenceScorer:
    """
    Calculates confidence scores for extracted data.

    Confidence is based on:
    1. Completeness: How many expected fields were found
    2. Quality: How well the data passes validation rules
    3. Content: Presence of "NA" or empty values reduces confidence
    """

    def __init__(
        self,
        expected_fields: Optional[List[str]] = None,
        required_fields: Optional[List[str]] = None
    ):
        """
        Initialize confidence scorer.

        Args:
            expected_fields: List of fields expected in the data
            required_fields: Subset of expected_fields that are required
        """
        self.expected_fields = expected_fields or []
        self.required_fields = required_fields or []

    def calculate_scores(
        self,
        data: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive confidence scores for the data.

        Args:
            data: The extracted data
            validation_result: Result from ValidationEngine.validate()

        Returns:
            Dictionary containing:
            {
                "overall_confidence": float (0.0-1.0),
                "completeness": float (0.0-1.0),
                "quality_score": float (0.0-1.0),
                "field_confidence": dict {field_name: score},
                "has_placeholder_values": bool,
                "missing_required_fields": list
            }
        """
        completeness = self._calculate_completeness(data)
        quality_score = self._calculate_quality_score(validation_result)
        field_confidence = self._calculate_field_confidence(data, validation_result)
        has_placeholders = self._detect_placeholder_values(data)
        missing_required = self._get_missing_required_fields(data)

        # Overall confidence is weighted average of completeness and quality
        # Reduce confidence significantly if there are placeholder values
        base_confidence = (completeness * 0.4 + quality_score * 0.6)

        if has_placeholders:
            base_confidence *= 0.7  # 30% penalty for placeholder values

        if missing_required:
            base_confidence *= 0.5  # 50% penalty for missing required fields

        overall_confidence = max(0.0, min(1.0, base_confidence))

        return {
            "overall_confidence": round(overall_confidence, 3),
            "completeness": round(completeness, 3),
            "quality_score": round(quality_score, 3),
            "field_confidence": field_confidence,
            "has_placeholder_values": has_placeholders,
            "missing_required_fields": missing_required
        }

    def _calculate_completeness(self, data: Dict[str, Any]) -> float:
        """
        Calculate what percentage of expected fields are present and non-empty.

        Args:
            data: The extracted data

        Returns:
            Completeness score between 0.0 and 1.0
        """
        if not self.expected_fields:
            # If no expected fields defined, base on whether data exists
            return 1.0 if data and len(data) > 0 else 0.0

        present_count = 0
        for field in self.expected_fields:
            if field in data:
                value = data[field]
                # Check if value is meaningful (not None, not empty string, not empty list/dict)
                if self._is_meaningful_value(value):
                    present_count += 1

        return present_count / len(self.expected_fields) if self.expected_fields else 0.0

    def _calculate_quality_score(self, validation_result: Dict[str, Any]) -> float:
        """
        Calculate quality score based on validation results.

        Args:
            validation_result: Result from ValidationEngine.validate()

        Returns:
            Quality score between 0.0 and 1.0
        """
        total_checks = len(validation_result.get("all_results", []))
        if total_checks == 0:
            # No validation rules applied, assume perfect quality
            return 1.0

        error_count = validation_result.get("error_count", 0)
        warning_count = validation_result.get("warning_count", 0)

        # Errors hurt more than warnings
        error_penalty = error_count * 0.3
        warning_penalty = warning_count * 0.1

        total_penalty = error_penalty + warning_penalty
        quality_score = max(0.0, 1.0 - (total_penalty / max(1, total_checks)))

        return quality_score

    def _calculate_field_confidence(
        self,
        data: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Calculate per-field confidence scores.

        Args:
            data: The extracted data
            validation_result: Result from ValidationEngine.validate()

        Returns:
            Dictionary mapping field names to confidence scores (0.0-1.0)
        """
        field_confidence = {}

        # Build a map of field names to their validation results
        field_errors = {}
        field_warnings = {}

        for error in validation_result.get("errors", []):
            field_name = error.get("field_name")
            if field_name:
                field_errors.setdefault(field_name, []).append(error)

        for warning in validation_result.get("warnings", []):
            field_name = warning.get("field_name")
            if field_name:
                field_warnings.setdefault(field_name, []).append(warning)

        # Calculate confidence for each field in the data
        for field_name, value in data.items():
            base_confidence = 1.0

            # Check if field is empty or placeholder
            if not self._is_meaningful_value(value):
                base_confidence = 0.1
            elif self._is_placeholder_value(value):
                base_confidence = 0.2

            # Reduce confidence based on errors
            if field_name in field_errors:
                error_count = len(field_errors[field_name])
                base_confidence *= (0.5 ** error_count)  # Exponential decrease

            # Reduce confidence based on warnings
            if field_name in field_warnings:
                warning_count = len(field_warnings[field_name])
                base_confidence *= (0.8 ** warning_count)

            field_confidence[field_name] = round(max(0.0, min(1.0, base_confidence)), 3)

        return field_confidence

    def _is_meaningful_value(self, value: Any) -> bool:
        """Check if a value is meaningful (not None, not empty)."""
        if value is None:
            return False
        if isinstance(value, str) and value.strip() == "":
            return False
        if isinstance(value, (list, dict)) and len(value) == 0:
            return False
        return True

    def _is_placeholder_value(self, value: Any) -> bool:
        """Check if a value is a placeholder like "NA" or "Not Found"."""
        if not isinstance(value, str):
            return False

        placeholder_patterns = [
            "NA", "N/A", "n/a", "na",
            "Not Available", "Not Found", "not found",
            "None", "Unknown", "unknown"
        ]

        return value.strip() in placeholder_patterns

    def _detect_placeholder_values(self, data: Dict[str, Any]) -> bool:
        """Check if the data contains any placeholder values."""
        for value in data.values():
            if self._is_placeholder_value(value):
                return True
        return False

    def _get_missing_required_fields(self, data: Dict[str, Any]) -> List[str]:
        """Get list of required fields that are missing or empty."""
        missing = []

        for field in self.required_fields:
            if field not in data or not self._is_meaningful_value(data[field]):
                missing.append(field)

        return missing

    def should_retry(
        self,
        scores: Dict[str, Any],
        min_confidence: float = 0.7,
        min_completeness: float = 0.8
    ) -> bool:
        """
        Determine if extraction should be retried based on scores.

        Args:
            scores: Result from calculate_scores()
            min_confidence: Minimum acceptable confidence score
            min_completeness: Minimum acceptable completeness score

        Returns:
            True if scores are below thresholds and retry is recommended
        """
        if scores["overall_confidence"] < min_confidence:
            return True

        if scores["completeness"] < min_completeness:
            return True

        if scores.get("missing_required_fields"):
            return True

        return False

    def get_retry_focus_fields(self, scores: Dict[str, Any]) -> List[str]:
        """
        Get list of fields that should be focused on in a retry attempt.

        Args:
            scores: Result from calculate_scores()

        Returns:
            List of field names that need retry
        """
        focus_fields = []

        # Include missing required fields
        focus_fields.extend(scores.get("missing_required_fields", []))

        # Include fields with low confidence
        field_confidence = scores.get("field_confidence", {})
        for field, confidence in field_confidence.items():
            if confidence < 0.7 and field not in focus_fields:
                focus_fields.append(field)

        # Include fields that are missing from expected fields
        for field in self.expected_fields:
            if field not in field_confidence and field not in focus_fields:
                focus_fields.append(field)

        return focus_fields
