"""
Comprehensive tests for cost management functionality.
"""
import pytest
from datetime import datetime, timedelta
from scrapegraphai.cost_management import (
    AttributionContext,
    CostRecord,
    CostSummary,
    CostTracker,
    InMemoryCostStorage,
    BudgetRule,
    BudgetPeriod,
    BudgetEnforcer,
    BudgetExceededError,
    BudgetAlert,
    inject_attribution_into_state,
    extract_attribution_from_state,
)


class TestAttributionContext:
    """Tests for AttributionContext."""

    def test_create_with_user_id(self):
        """Test creating attribution context with user_id."""
        ctx = AttributionContext(user_id="user123")
        assert ctx.user_id == "user123"
        assert ctx.project_id is None
        assert ctx.tenant_id is None
        assert ctx.session_id is not None

    def test_create_with_all_ids(self):
        """Test creating attribution context with all IDs."""
        ctx = AttributionContext(
            user_id="user123",
            project_id="proj456",
            tenant_id="tenant789"
        )
        assert ctx.user_id == "user123"
        assert ctx.project_id == "proj456"
        assert ctx.tenant_id == "tenant789"

    def test_requires_at_least_one_id(self):
        """Test that at least one ID is required."""
        with pytest.raises(ValueError, match="requires at least one"):
            AttributionContext()

    def test_to_dict(self):
        """Test converting to dictionary."""
        ctx = AttributionContext(user_id="user123", tags={"env": "prod"})
        d = ctx.to_dict()
        assert d["user_id"] == "user123"
        assert d["tags"] == {"env": "prod"}
        assert "created_at" in d

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "user_id": "user123",
            "project_id": "proj456",
            "tenant_id": None,
            "session_id": "session789",
            "tags": {"env": "test"},
            "created_at": datetime.utcnow().isoformat(),
        }
        ctx = AttributionContext.from_dict(data)
        assert ctx.user_id == "user123"
        assert ctx.project_id == "proj456"
        assert ctx.session_id == "session789"

    def test_get_entity_keys(self):
        """Test getting entity keys."""
        ctx = AttributionContext(user_id="user123", project_id="proj456")
        keys = ctx.get_entity_keys()
        assert keys == {"user_id": "user123", "project_id": "proj456"}

    def test_inject_and_extract_from_state(self):
        """Test injecting and extracting attribution from state."""
        ctx = AttributionContext(user_id="user123")
        state = {"some_key": "some_value"}

        # Inject
        state = inject_attribution_into_state(state, ctx)
        assert "_attribution_context" in state

        # Extract
        extracted = extract_attribution_from_state(state)
        assert extracted is ctx
        assert extracted.user_id == "user123"

    def test_extract_from_empty_state(self):
        """Test extracting from state without attribution."""
        state = {"some_key": "some_value"}
        extracted = extract_attribution_from_state(state)
        assert extracted is None


class TestCostRecord:
    """Tests for CostRecord."""

    def test_create_cost_record(self):
        """Test creating a cost record."""
        record = CostRecord(
            user_id="user123",
            project_id="proj456",
            node_name="GenerateAnswerNode",
            model_name="gpt-4",
            total_tokens=1000,
            prompt_tokens=800,
            completion_tokens=200,
            total_cost_usd=0.05,
        )
        assert record.user_id == "user123"
        assert record.total_tokens == 1000
        assert record.total_cost_usd == 0.05
        assert record.id is not None

    def test_cost_record_to_dict(self):
        """Test converting cost record to dict."""
        record = CostRecord(
            user_id="user123",
            node_name="TestNode",
            model_name="gpt-4",
            total_cost_usd=0.01,
        )
        d = record.to_dict()
        assert d["user_id"] == "user123"
        assert d["node_name"] == "TestNode"
        assert d["model_name"] == "gpt-4"
        assert "timestamp" in d


class TestCostSummary:
    """Tests for CostSummary."""

    def test_create_cost_summary(self):
        """Test creating a cost summary."""
        summary = CostSummary(
            entity_type="user",
            entity_id="user123",
            total_cost_usd=10.50,
            total_tokens=5000,
            request_count=10,
        )
        assert summary.entity_type == "user"
        assert summary.total_cost_usd == 10.50
        assert summary.request_count == 10

    def test_cost_summary_to_dict(self):
        """Test converting cost summary to dict."""
        summary = CostSummary(
            entity_type="project",
            entity_id="proj456",
            total_cost_usd=25.00,
            model_breakdown={"gpt-4": 20.0, "gpt-3.5": 5.0},
        )
        d = summary.to_dict()
        assert d["entity_type"] == "project"
        assert d["total_cost_usd"] == 25.00
        assert d["model_breakdown"] == {"gpt-4": 20.0, "gpt-3.5": 5.0}


class TestInMemoryCostStorage:
    """Tests for InMemoryCostStorage."""

    def test_store_and_retrieve_by_user(self):
        """Test storing and retrieving records by user."""
        storage = InMemoryCostStorage()
        record = CostRecord(
            user_id="user123",
            node_name="TestNode",
            model_name="gpt-4",
            total_cost_usd=0.05,
        )
        storage.store_record(record)

        records = storage.get_records_by_user("user123")
        assert len(records) == 1
        assert records[0].user_id == "user123"

    def test_store_and_retrieve_by_project(self):
        """Test storing and retrieving records by project."""
        storage = InMemoryCostStorage()
        record = CostRecord(
            project_id="proj456",
            node_name="TestNode",
            model_name="gpt-4",
            total_cost_usd=0.05,
        )
        storage.store_record(record)

        records = storage.get_records_by_project("proj456")
        assert len(records) == 1
        assert records[0].project_id == "proj456"

    def test_filter_by_date(self):
        """Test filtering records by date range."""
        storage = InMemoryCostStorage()

        # Create records with different timestamps
        now = datetime.utcnow()
        old_record = CostRecord(
            user_id="user123",
            node_name="OldNode",
            model_name="gpt-4",
            total_cost_usd=0.01,
        )
        old_record.timestamp = now - timedelta(days=2)

        new_record = CostRecord(
            user_id="user123",
            node_name="NewNode",
            model_name="gpt-4",
            total_cost_usd=0.02,
        )
        new_record.timestamp = now

        storage.store_record(old_record)
        storage.store_record(new_record)

        # Get records from last day
        start_date = now - timedelta(days=1)
        records = storage.get_records_by_user("user123", start_date=start_date)
        assert len(records) == 1
        assert records[0].node_name == "NewNode"


class TestCostTracker:
    """Tests for CostTracker."""

    def test_track_cost(self):
        """Test tracking a cost event."""
        tracker = CostTracker()
        attribution = AttributionContext(user_id="user123")

        record = tracker.track_cost(
            attribution=attribution,
            node_name="GenerateAnswerNode",
            model_name="gpt-4",
            total_tokens=1000,
            prompt_tokens=800,
            completion_tokens=200,
            total_cost_usd=0.05,
            execution_time=1.5,
        )

        assert record.user_id == "user123"
        assert record.total_cost_usd == 0.05
        assert record.execution_time == 1.5

    def test_get_user_costs(self):
        """Test getting cost summary for a user."""
        tracker = CostTracker()
        attribution = AttributionContext(user_id="user123")

        # Track multiple costs
        tracker.track_cost(
            attribution=attribution,
            node_name="Node1",
            model_name="gpt-4",
            total_tokens=1000,
            prompt_tokens=800,
            completion_tokens=200,
            total_cost_usd=0.05,
        )
        tracker.track_cost(
            attribution=attribution,
            node_name="Node2",
            model_name="gpt-4",
            total_tokens=500,
            prompt_tokens=400,
            completion_tokens=100,
            total_cost_usd=0.03,
        )

        summary = tracker.get_user_costs("user123")
        assert summary.entity_type == "user"
        assert summary.entity_id == "user123"
        assert summary.total_cost_usd == 0.08
        assert summary.total_tokens == 1500
        assert summary.request_count == 2

    def test_get_project_costs(self):
        """Test getting cost summary for a project."""
        tracker = CostTracker()
        attribution = AttributionContext(project_id="proj456")

        tracker.track_cost(
            attribution=attribution,
            node_name="Node1",
            model_name="gpt-4",
            total_tokens=1000,
            prompt_tokens=800,
            completion_tokens=200,
            total_cost_usd=0.10,
        )

        summary = tracker.get_project_costs("proj456")
        assert summary.entity_type == "project"
        assert summary.total_cost_usd == 0.10

    def test_model_breakdown(self):
        """Test model cost breakdown."""
        tracker = CostTracker()
        attribution = AttributionContext(user_id="user123")

        # Track costs for different models
        tracker.track_cost(
            attribution=attribution,
            node_name="Node1",
            model_name="gpt-4",
            total_tokens=1000,
            prompt_tokens=800,
            completion_tokens=200,
            total_cost_usd=0.05,
        )
        tracker.track_cost(
            attribution=attribution,
            node_name="Node2",
            model_name="gpt-3.5-turbo",
            total_tokens=1000,
            prompt_tokens=800,
            completion_tokens=200,
            total_cost_usd=0.01,
        )

        summary = tracker.get_user_costs("user123")
        assert summary.model_breakdown["gpt-4"] == 0.05
        assert summary.model_breakdown["gpt-3.5-turbo"] == 0.01


class TestBudgetRule:
    """Tests for BudgetRule."""

    def test_create_budget_rule(self):
        """Test creating a budget rule."""
        rule = BudgetRule(
            entity_type="user",
            entity_id="user123",
            limit_usd=100.0,
            period=BudgetPeriod.MONTHLY,
        )
        assert rule.limit_usd == 100.0
        assert rule.period == BudgetPeriod.MONTHLY
        assert rule.alert_threshold == 0.8

    def test_budget_rule_validation(self):
        """Test budget rule validation."""
        # Negative limit should fail
        with pytest.raises(ValueError, match="must be positive"):
            BudgetRule(
                entity_type="user",
                entity_id="user123",
                limit_usd=-10.0,
            )

        # Soft limit >= hard limit should fail
        with pytest.raises(ValueError, match="less than hard limit"):
            BudgetRule(
                entity_type="user",
                entity_id="user123",
                limit_usd=100.0,
                soft_limit_usd=100.0,
            )

    def test_get_date_range_daily(self):
        """Test getting date range for daily budget."""
        rule = BudgetRule(
            entity_type="user",
            entity_id="user123",
            limit_usd=10.0,
            period=BudgetPeriod.DAILY,
        )
        start, end = rule.get_date_range()
        assert start is not None
        assert start.hour == 0
        assert start.minute == 0
        assert (end - start).total_seconds() <= 86400  # Within one day

    def test_get_date_range_monthly(self):
        """Test getting date range for monthly budget."""
        rule = BudgetRule(
            entity_type="user",
            entity_id="user123",
            limit_usd=100.0,
            period=BudgetPeriod.MONTHLY,
        )
        start, end = rule.get_date_range()
        assert start is not None
        assert start.day == 1
        assert start.hour == 0

    def test_get_date_range_total(self):
        """Test getting date range for total budget."""
        rule = BudgetRule(
            entity_type="user",
            entity_id="user123",
            limit_usd=1000.0,
            period=BudgetPeriod.TOTAL,
        )
        start, end = rule.get_date_range()
        assert start is None  # No start date for total budget


class TestBudgetEnforcer:
    """Tests for BudgetEnforcer."""

    def test_add_and_remove_budget_rule(self):
        """Test adding and removing budget rules."""
        tracker = CostTracker()
        enforcer = BudgetEnforcer(tracker)

        rule = BudgetRule(
            entity_type="user",
            entity_id="user123",
            limit_usd=100.0,
        )
        enforcer.add_budget_rule(rule)

        assert ("user", "user123") in enforcer.budget_rules

        enforcer.remove_budget_rule("user", "user123")
        assert ("user", "user123") not in enforcer.budget_rules

    def test_check_budget_within_limit(self):
        """Test budget check when within limit."""
        tracker = CostTracker()
        enforcer = BudgetEnforcer(tracker)

        rule = BudgetRule(
            entity_type="user_id",
            entity_id="user123",
            limit_usd=100.0,
        )
        enforcer.add_budget_rule(rule)

        attribution = AttributionContext(user_id="user123")

        # Should not raise exception
        result = enforcer.check_budget_before_execution(attribution, estimated_cost=10.0)
        assert result["allowed"] is True

    def test_check_budget_exceeds_limit(self):
        """Test budget check when exceeding limit."""
        tracker = CostTracker()
        enforcer = BudgetEnforcer(tracker)

        rule = BudgetRule(
            entity_type="user_id",
            entity_id="user123",
            limit_usd=10.0,
        )
        enforcer.add_budget_rule(rule)

        attribution = AttributionContext(user_id="user123")

        # Track some costs
        tracker.track_cost(
            attribution=attribution,
            node_name="Node1",
            model_name="gpt-4",
            total_tokens=1000,
            prompt_tokens=800,
            completion_tokens=200,
            total_cost_usd=9.0,
        )

        # Should raise exception when trying to spend more
        with pytest.raises(BudgetExceededError, match="Budget exceeded"):
            enforcer.check_budget_before_execution(attribution, estimated_cost=2.0)

    def test_soft_limit_warning(self):
        """Test soft limit generates warning."""
        tracker = CostTracker()
        enforcer = BudgetEnforcer(tracker)

        rule = BudgetRule(
            entity_type="user_id",
            entity_id="user123",
            limit_usd=100.0,
            soft_limit_usd=50.0,
        )
        enforcer.add_budget_rule(rule)

        attribution = AttributionContext(user_id="user123")

        # Track costs up to soft limit
        tracker.track_cost(
            attribution=attribution,
            node_name="Node1",
            model_name="gpt-4",
            total_tokens=1000,
            prompt_tokens=800,
            completion_tokens=200,
            total_cost_usd=45.0,
        )

        # Should not raise but should report soft limit violation
        result = enforcer.check_budget_before_execution(attribution, estimated_cost=10.0)
        assert result["allowed"] is True
        soft_violations = [v for v in result["violations"] if v["violation_type"] == "soft_limit"]
        assert len(soft_violations) > 0

    def test_budget_alert_callback(self):
        """Test budget alert callback is triggered."""
        tracker = CostTracker()
        enforcer = BudgetEnforcer(tracker)

        alerts_received = []

        def alert_callback(alert: BudgetAlert):
            alerts_received.append(alert)

        enforcer.register_alert_callback(alert_callback)

        rule = BudgetRule(
            entity_type="user_id",
            entity_id="user123",
            limit_usd=100.0,
            alert_threshold=0.8,
        )
        enforcer.add_budget_rule(rule)

        attribution = AttributionContext(user_id="user123")

        # Track costs to trigger alert (80% of budget)
        tracker.track_cost(
            attribution=attribution,
            node_name="Node1",
            model_name="gpt-4",
            total_tokens=1000,
            prompt_tokens=800,
            completion_tokens=200,
            total_cost_usd=85.0,
        )

        enforcer.check_and_alert(attribution, 85.0)

        assert len(alerts_received) > 0
        alert = alerts_received[0]
        assert alert.entity_id == "user123"
        assert alert.utilization >= 0.8

    def test_get_budget_status(self):
        """Test getting budget status."""
        tracker = CostTracker()
        enforcer = BudgetEnforcer(tracker)

        rule = BudgetRule(
            entity_type="user_id",
            entity_id="user123",
            limit_usd=100.0,
        )
        enforcer.add_budget_rule(rule)

        attribution = AttributionContext(user_id="user123")

        tracker.track_cost(
            attribution=attribution,
            node_name="Node1",
            model_name="gpt-4",
            total_tokens=1000,
            prompt_tokens=800,
            completion_tokens=200,
            total_cost_usd=25.0,
        )

        status = enforcer.get_budget_status("user_id", "user123")
        assert status["current_usage"] == 25.0
        assert status["limit"] == 100.0
        assert status["remaining"] == 75.0
        assert status["utilization"] == 0.25


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_workflow(self):
        """Test complete workflow: attribution -> tracking -> budget enforcement."""
        # Setup
        tracker = CostTracker()
        enforcer = BudgetEnforcer(tracker)

        rule = BudgetRule(
            entity_type="user_id",
            entity_id="user123",
            limit_usd=10.0,
            alert_threshold=0.7,
        )
        enforcer.add_budget_rule(rule)

        attribution = AttributionContext(user_id="user123", tags={"env": "test"})

        alerts_received = []
        enforcer.register_alert_callback(lambda a: alerts_received.append(a))

        # Execute within budget
        enforcer.check_budget_before_execution(attribution, estimated_cost=2.0)

        # Track cost
        tracker.track_cost(
            attribution=attribution,
            node_name="Node1",
            model_name="gpt-4",
            total_tokens=1000,
            prompt_tokens=800,
            completion_tokens=200,
            total_cost_usd=2.0,
        )

        # Check alerts
        enforcer.check_and_alert(attribution, 2.0)

        # Track more costs to trigger alert
        tracker.track_cost(
            attribution=attribution,
            node_name="Node2",
            model_name="gpt-4",
            total_tokens=1000,
            prompt_tokens=800,
            completion_tokens=200,
            total_cost_usd=6.0,
        )

        enforcer.check_and_alert(attribution, 6.0)

        # Should have triggered alert (8.0 / 10.0 = 80% > 70% threshold)
        assert len(alerts_received) > 0

        # Try to exceed budget
        with pytest.raises(BudgetExceededError):
            enforcer.check_budget_before_execution(attribution, estimated_cost=3.0)

        # Verify summary
        summary = tracker.get_user_costs("user123")
        assert summary.total_cost_usd == 8.0
        assert summary.request_count == 2

    def test_multi_entity_tracking(self):
        """Test tracking costs across multiple entity types."""
        tracker = CostTracker()
        enforcer = BudgetEnforcer(tracker)

        # Setup budget rules for different entities
        user_rule = BudgetRule(
            entity_type="user_id",
            entity_id="user123",
            limit_usd=100.0,
        )
        project_rule = BudgetRule(
            entity_type="project_id",
            entity_id="proj456",
            limit_usd=200.0,
        )

        enforcer.add_budget_rule(user_rule)
        enforcer.add_budget_rule(project_rule)

        # Attribution with both user and project
        attribution = AttributionContext(
            user_id="user123",
            project_id="proj456",
        )

        # Track cost
        tracker.track_cost(
            attribution=attribution,
            node_name="Node1",
            model_name="gpt-4",
            total_tokens=1000,
            prompt_tokens=800,
            completion_tokens=200,
            total_cost_usd=10.0,
        )

        # Verify both entities are tracked
        user_summary = tracker.get_user_costs("user123")
        project_summary = tracker.get_project_costs("proj456")

        assert user_summary.total_cost_usd == 10.0
        assert project_summary.total_cost_usd == 10.0

        # Verify budget status for both
        user_status = enforcer.get_budget_status("user_id", "user123")
        project_status = enforcer.get_budget_status("project_id", "proj456")

        assert user_status["remaining"] == 90.0
        assert project_status["remaining"] == 190.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
