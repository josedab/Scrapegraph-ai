"""
Cost management module for ScrapeGraphAI.

This module provides cost attribution, tracking, and budget management
capabilities for multi-tenant and production deployments.
"""

from .attribution import (
    AttributionContext,
    ATTRIBUTION_CONTEXT_KEY,
    inject_attribution_into_state,
    extract_attribution_from_state,
)
from .models import CostRecord, CostSummary
from .tracker import CostTracker, InMemoryCostStorage
from .budget import (
    BudgetRule,
    BudgetPeriod,
    BudgetEnforcer,
    BudgetExceededError,
    BudgetAlert,
)

__all__ = [
    "AttributionContext",
    "ATTRIBUTION_CONTEXT_KEY",
    "inject_attribution_into_state",
    "extract_attribution_from_state",
    "CostRecord",
    "CostSummary",
    "CostTracker",
    "InMemoryCostStorage",
    "BudgetRule",
    "BudgetPeriod",
    "BudgetEnforcer",
    "BudgetExceededError",
    "BudgetAlert",
]
