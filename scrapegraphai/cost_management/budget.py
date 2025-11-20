"""
Budget management and enforcement.
"""
from dataclasses import dataclass
from typing import Optional, Dict, List
from enum import Enum
from datetime import datetime, timedelta

from .tracker import CostTracker
from .attribution import AttributionContext


class BudgetPeriod(Enum):
    """Budget period types."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    TOTAL = "total"  # Lifetime budget


class BudgetExceededError(Exception):
    """Raised when budget limit is exceeded."""
    pass


@dataclass
class BudgetAlert:
    """
    Budget alert notification.

    Attributes:
        entity_type: Type of entity (user, project, tenant)
        entity_id: ID of the entity
        current_usage: Current usage in USD
        budget_limit: Budget limit in USD
        utilization: Utilization percentage (0.0-1.0)
        threshold: Alert threshold that was crossed
        period: Budget period
        timestamp: When the alert was triggered
    """
    entity_type: str
    entity_id: str
    current_usage: float
    budget_limit: float
    utilization: float
    threshold: float
    period: BudgetPeriod
    timestamp: datetime

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'current_usage': self.current_usage,
            'budget_limit': self.budget_limit,
            'utilization': self.utilization,
            'threshold': self.threshold,
            'period': self.period.value,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class BudgetRule:
    """
    Budget rule definition.

    Attributes:
        entity_type: Type of entity (user, project, tenant)
        entity_id: ID of the entity
        limit_usd: Budget limit in USD
        period: Budget period (daily, weekly, monthly, total)
        soft_limit_usd: Soft limit for warnings (optional)
        alert_threshold: Alert when this % of budget is used (0.0-1.0)
    """

    entity_type: str  # 'user', 'project', or 'tenant'
    entity_id: str
    limit_usd: float
    period: BudgetPeriod = BudgetPeriod.MONTHLY
    soft_limit_usd: Optional[float] = None
    alert_threshold: float = 0.8  # Alert at 80% by default

    def __post_init__(self):
        """Validate budget rule."""
        if self.limit_usd <= 0:
            raise ValueError("Budget limit must be positive")

        if self.soft_limit_usd and self.soft_limit_usd >= self.limit_usd:
            raise ValueError("Soft limit must be less than hard limit")

        if not 0.0 < self.alert_threshold <= 1.0:
            raise ValueError("Alert threshold must be between 0.0 and 1.0")

    def get_date_range(self) -> tuple[Optional[datetime], datetime]:
        """
        Get the date range for this budget period.

        Returns:
            Tuple of (start_date, end_date) for the current period
        """
        now = datetime.utcnow()

        if self.period == BudgetPeriod.DAILY:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.period == BudgetPeriod.WEEKLY:
            days_since_monday = now.weekday()
            start = (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif self.period == BudgetPeriod.MONTHLY:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:  # TOTAL
            start = None

        return start, now


class BudgetEnforcer:
    """
    Enforces budget limits and generates alerts.

    Features:
    - Hard budget limits with pre-execution checks
    - Soft budget limits with warnings
    - Alert thresholds
    - Budget utilization tracking
    """

    def __init__(self, cost_tracker: CostTracker):
        """
        Initialize budget enforcer.

        Args:
            cost_tracker: CostTracker instance for querying costs
        """
        self.cost_tracker = cost_tracker
        self.budget_rules: Dict[tuple[str, str], BudgetRule] = {}
        self._alert_callbacks: List[callable] = []
        self._alerted_thresholds: Dict[tuple[str, str], set] = {}

    def add_budget_rule(self, rule: BudgetRule):
        """
        Add a budget rule.

        Args:
            rule: BudgetRule to add
        """
        key = (rule.entity_type, rule.entity_id)
        self.budget_rules[key] = rule
        # Reset alert tracking when rule is added/modified
        self._alerted_thresholds[key] = set()

    def remove_budget_rule(self, entity_type: str, entity_id: str):
        """Remove a budget rule."""
        key = (entity_type, entity_id)
        if key in self.budget_rules:
            del self.budget_rules[key]
        if key in self._alerted_thresholds:
            del self._alerted_thresholds[key]

    def register_alert_callback(self, callback: callable):
        """
        Register a callback for budget alerts.

        Args:
            callback: Function that takes (alert: BudgetAlert)
        """
        self._alert_callbacks.append(callback)

    def check_budget_before_execution(
        self,
        attribution: AttributionContext,
        estimated_cost: Optional[float] = 0.0,
    ) -> Dict[str, any]:
        """
        Check if execution would exceed budget limits.

        Args:
            attribution: Attribution context
            estimated_cost: Estimated cost for the operation (optional)

        Returns:
            Dict with:
                - allowed: bool indicating if execution is allowed
                - budget_info: Dict of entity -> budget info
                - violations: List of budget rules that would be violated

        Raises:
            BudgetExceededError: If hard budget limit would be exceeded
        """
        budget_info = {}
        violations = []

        for entity_type, entity_id in attribution.get_entity_keys().items():
            key = (entity_type, entity_id)
            if key not in self.budget_rules:
                continue

            rule = self.budget_rules[key]
            start_date, end_date = rule.get_date_range()

            # Get current usage
            if entity_type == 'user_id':
                summary = self.cost_tracker.get_user_costs(entity_id, start_date, end_date)
            elif entity_type == 'project_id':
                summary = self.cost_tracker.get_project_costs(entity_id, start_date, end_date)
            elif entity_type == 'tenant_id':
                summary = self.cost_tracker.get_tenant_costs(entity_id, start_date, end_date)
            else:
                continue

            current_usage = summary.total_cost_usd
            projected_usage = current_usage + estimated_cost
            utilization = projected_usage / rule.limit_usd if rule.limit_usd > 0 else 0.0

            budget_info[entity_type] = {
                'current_usage': current_usage,
                'projected_usage': projected_usage,
                'limit': rule.limit_usd,
                'remaining': rule.limit_usd - current_usage,
                'utilization': utilization,
                'period': rule.period.value,
            }

            # Check hard limit
            if projected_usage >= rule.limit_usd:
                violations.append({
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'rule': rule,
                    'current_usage': current_usage,
                    'projected_usage': projected_usage,
                    'violation_type': 'hard_limit',
                })

            # Check soft limit
            elif rule.soft_limit_usd and projected_usage >= rule.soft_limit_usd:
                violations.append({
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'rule': rule,
                    'current_usage': current_usage,
                    'projected_usage': projected_usage,
                    'violation_type': 'soft_limit',
                })

        # Block execution if any hard limit would be violated
        hard_limit_violations = [v for v in violations if v['violation_type'] == 'hard_limit']
        if hard_limit_violations:
            violation = hard_limit_violations[0]
            raise BudgetExceededError(
                f"Budget exceeded for {violation['entity_type']} {violation['entity_id']}: "
                f"${violation['projected_usage']:.4f} would exceed limit of "
                f"${violation['rule'].limit_usd:.4f} "
                f"(period: {violation['rule'].period.value})"
            )

        return {
            'allowed': len(hard_limit_violations) == 0,
            'budget_info': budget_info,
            'violations': violations,
        }

    def check_and_alert(self, attribution: AttributionContext, cost_incurred: float):
        """
        Check budget utilization and trigger alerts if thresholds are crossed.

        Args:
            attribution: Attribution context
            cost_incurred: Cost that was just incurred
        """
        for entity_type, entity_id in attribution.get_entity_keys().items():
            key = (entity_type, entity_id)
            if key not in self.budget_rules:
                continue

            rule = self.budget_rules[key]
            start_date, end_date = rule.get_date_range()

            # Get current usage
            if entity_type == 'user_id':
                summary = self.cost_tracker.get_user_costs(entity_id, start_date, end_date)
            elif entity_type == 'project_id':
                summary = self.cost_tracker.get_project_costs(entity_id, start_date, end_date)
            elif entity_type == 'tenant_id':
                summary = self.cost_tracker.get_tenant_costs(entity_id, start_date, end_date)
            else:
                continue

            current_usage = summary.total_cost_usd
            utilization = current_usage / rule.limit_usd if rule.limit_usd > 0 else 0.0

            # Check if alert threshold crossed
            if utilization >= rule.alert_threshold:
                # Only alert once per threshold per budget period
                if key not in self._alerted_thresholds:
                    self._alerted_thresholds[key] = set()

                threshold_key = f"{rule.alert_threshold}_{rule.period.value}"
                if threshold_key not in self._alerted_thresholds[key]:
                    self._alerted_thresholds[key].add(threshold_key)

                    alert = BudgetAlert(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        current_usage=current_usage,
                        budget_limit=rule.limit_usd,
                        utilization=utilization,
                        threshold=rule.alert_threshold,
                        period=rule.period,
                        timestamp=datetime.utcnow(),
                    )

                    # Trigger alert callbacks
                    for callback in self._alert_callbacks:
                        try:
                            callback(alert)
                        except Exception as e:
                            # Don't let callback errors break execution
                            print(f"Error in budget alert callback: {e}")

    def get_budget_status(
        self,
        entity_type: str,
        entity_id: str,
    ) -> Optional[Dict]:
        """
        Get current budget status for an entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Returns:
            Dict with budget status or None if no rule exists
        """
        key = (entity_type, entity_id)
        if key not in self.budget_rules:
            return None

        rule = self.budget_rules[key]
        start_date, end_date = rule.get_date_range()

        # Get current usage
        if entity_type == 'user_id':
            summary = self.cost_tracker.get_user_costs(entity_id, start_date, end_date)
        elif entity_type == 'project_id':
            summary = self.cost_tracker.get_project_costs(entity_id, start_date, end_date)
        elif entity_type == 'tenant_id':
            summary = self.cost_tracker.get_tenant_costs(entity_id, start_date, end_date)
        else:
            return None

        current_usage = summary.total_cost_usd
        utilization = current_usage / rule.limit_usd if rule.limit_usd > 0 else 0.0

        return {
            'entity_type': entity_type,
            'entity_id': entity_id,
            'current_usage': current_usage,
            'limit': rule.limit_usd,
            'soft_limit': rule.soft_limit_usd,
            'remaining': rule.limit_usd - current_usage,
            'utilization': utilization,
            'period': rule.period.value,
            'alert_threshold': rule.alert_threshold,
        }
