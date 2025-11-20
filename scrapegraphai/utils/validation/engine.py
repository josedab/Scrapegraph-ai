"""
Validation engine for orchestrating multiple validation rules.

The ValidationEngine runs multiple validation rules against extracted data
and aggregates the results.
"""

from typing import Any, Dict, List
from .base import ValidationRule, ValidationResult, ValidationSeverity


class ValidationEngine:
    """
    Orchestrates running multiple validation rules against data.

    The engine runs all rules, collects results, and determines
    overall validation status.
    """

    def __init__(self, rules: List[ValidationRule] = None):
        """
        Initialize validation engine with a list of rules.

        Args:
            rules: List of validation rules to apply (default: empty list)
        """
        self.rules = rules or []

    def add_rule(self, rule: ValidationRule) -> None:
        """Add a validation rule to the engine."""
        self.rules.append(rule)

    def add_rules(self, rules: List[ValidationRule]) -> None:
        """Add multiple validation rules to the engine."""
        self.rules.extend(rules)

    def validate(self, data: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Run all validation rules against the data.

        Args:
            data: The data to validate (typically a dictionary)
            context: Additional context for validation (schema, prompt, etc.)

        Returns:
            Dictionary containing validation results:
            {
                "passed": bool,  # True if no ERROR-level failures
                "errors": [...],  # List of ERROR-level failures
                "warnings": [...],  # List of WARNING-level issues
                "info": [...],  # List of INFO-level results
                "all_results": [...]  # All validation results
            }
        """
        if context is None:
            context = {}

        results = []
        errors = []
        warnings = []
        info = []

        # Run all validation rules
        for rule in self.rules:
            try:
                result = rule.validate(data, context)
                results.append(result)

                # Categorize by severity
                if not result.passed:
                    if result.severity == ValidationSeverity.ERROR:
                        errors.append(result)
                    elif result.severity == ValidationSeverity.WARNING:
                        warnings.append(result)
                else:
                    if result.severity == ValidationSeverity.INFO:
                        info.append(result)

            except Exception as e:
                # If a rule itself throws an exception, record it as an error
                error_result = ValidationResult(
                    passed=False,
                    severity=ValidationSeverity.ERROR,
                    rule_name=rule.name,
                    message=f"Validation rule '{rule.name}' threw exception: {str(e)}",
                    suggestion="Check rule implementation"
                )
                results.append(error_result)
                errors.append(error_result)

        # Overall validation passes if there are no ERROR-level failures
        passed = len(errors) == 0

        return {
            "passed": passed,
            "errors": [e.to_dict() for e in errors],
            "warnings": [w.to_dict() for w in warnings],
            "info": [i.to_dict() for i in info],
            "all_results": [r.to_dict() for r in results],
            "error_count": len(errors),
            "warning_count": len(warnings)
        }

    def validate_strict(self, data: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Run validation in strict mode (warnings also cause failure).

        Args:
            data: The data to validate
            context: Additional context for validation

        Returns:
            Same as validate(), but passed=False if there are errors OR warnings
        """
        result = self.validate(data, context)

        # In strict mode, warnings also cause failure
        if result["warning_count"] > 0:
            result["passed"] = False

        return result

    def get_failed_fields(self, validation_result: Dict[str, Any]) -> List[str]:
        """
        Extract list of field names that failed validation.

        Args:
            validation_result: Result from validate() or validate_strict()

        Returns:
            List of field names that have errors
        """
        failed_fields = set()

        for error in validation_result.get("errors", []):
            if error.get("field_name"):
                failed_fields.add(error["field_name"])

        return sorted(list(failed_fields))

    def get_missing_fields(self, validation_result: Dict[str, Any]) -> List[str]:
        """
        Extract list of required fields that are missing.

        Args:
            validation_result: Result from validate() or validate_strict()

        Returns:
            List of field names that are missing
        """
        missing_fields = []

        for error in validation_result.get("errors", []):
            if "missing" in error.get("message", "").lower():
                if error.get("field_name"):
                    missing_fields.append(error["field_name"])

        return missing_fields

    def clear_rules(self) -> None:
        """Remove all validation rules from the engine."""
        self.rules = []

    def __len__(self) -> int:
        """Return number of rules in the engine."""
        return len(self.rules)

    def __repr__(self) -> str:
        """Return string representation of the engine."""
        return f"ValidationEngine(rules={len(self.rules)})"
