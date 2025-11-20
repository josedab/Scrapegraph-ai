# Cost Attribution & Budget Management

This document describes the cost attribution and budget management system in ScrapeGraphAI, enabling cost tracking and budget enforcement for multi-tenant and production deployments.

## Overview

The cost management system provides:

- **Cost Attribution**: Track costs per user, project, and tenant
- **Budget Enforcement**: Set hard and soft budget limits with pre-execution checks
- **Budget Alerts**: Receive notifications when budget thresholds are crossed
- **Cost Reporting**: Generate cost summaries and analyze spending patterns
- **Thread-Safe**: Designed for concurrent use in production environments

## Quick Start

### Basic Usage

```python
from scrapegraphai.cost_management import (
    AttributionContext,
    CostTracker,
    BudgetEnforcer,
    BudgetRule,
    BudgetPeriod,
    inject_attribution_into_state,
)

# 1. Create cost tracker and budget enforcer
tracker = CostTracker()
enforcer = BudgetEnforcer(tracker)

# 2. Set up budget rule
budget = BudgetRule(
    entity_type="user_id",
    entity_id="user123",
    limit_usd=100.0,
    period=BudgetPeriod.MONTHLY,
    alert_threshold=0.8,  # Alert at 80% usage
)
enforcer.add_budget_rule(budget)

# 3. Create attribution context
attribution = AttributionContext(
    user_id="user123",
    project_id="my_project",
)

# 4. Inject attribution into graph state
initial_state = {
    "url": "https://example.com",
    "user_prompt": "Extract content"
}
initial_state = inject_attribution_into_state(initial_state, attribution)

# 5. Create graph with cost management
graph = SmartScraperGraph(
    prompt="Extract the main content",
    source="https://example.com",
    config=graph_config,
    cost_tracker=tracker,
    budget_enforcer=enforcer,
)

# 6. Execute - costs are automatically tracked
result = graph.run()

# 7. Check cost summary
summary = tracker.get_user_costs("user123")
print(f"Total cost: ${summary.total_cost_usd:.4f}")
```

## Core Components

### AttributionContext

Tracks which user, project, or tenant is responsible for costs.

```python
from scrapegraphai.cost_management import AttributionContext

# Create attribution with user ID
ctx = AttributionContext(user_id="user123")

# Create with multiple entity types
ctx = AttributionContext(
    user_id="user123",
    project_id="proj456",
    tenant_id="tenant789",
    tags={"environment": "production", "team": "data-eng"}
)

# Get entity keys
keys = ctx.get_entity_keys()
# Returns: {"user_id": "user123", "project_id": "proj456", "tenant_id": "tenant789"}
```

**Requirements:**
- At least one of `user_id`, `project_id`, or `tenant_id` must be provided
- `session_id` is automatically generated if not provided
- `tags` can be used for custom attribution dimensions

### CostTracker

Records and aggregates costs per entity.

```python
from scrapegraphai.cost_management import CostTracker

tracker = CostTracker()

# Track a cost event (usually done automatically by BaseGraph)
record = tracker.track_cost(
    attribution=attribution,
    node_name="GenerateAnswerNode",
    model_name="gpt-4",
    total_tokens=1000,
    prompt_tokens=800,
    completion_tokens=200,
    total_cost_usd=0.03,
    execution_time=1.5,
)

# Get cost summaries
user_summary = tracker.get_user_costs("user123")
project_summary = tracker.get_project_costs("proj456")
tenant_summary = tracker.get_tenant_costs("tenant789")

# Filter by date range
from datetime import datetime, timedelta
start_date = datetime.utcnow() - timedelta(days=7)
weekly_summary = tracker.get_user_costs("user123", start_date=start_date)

# Get session costs
session_records = tracker.get_session_costs("session-abc-123")
```

**CostSummary attributes:**
- `entity_type`: "user", "project", or "tenant"
- `entity_id`: ID of the entity
- `total_cost_usd`: Total cost in USD
- `total_tokens`: Total tokens consumed
- `request_count`: Number of LLM requests
- `model_breakdown`: Cost breakdown by model name

### BudgetEnforcer

Enforces budget limits and generates alerts.

```python
from scrapegraphai.cost_management import (
    BudgetEnforcer,
    BudgetRule,
    BudgetPeriod,
    BudgetExceededError,
)

enforcer = BudgetEnforcer(cost_tracker)

# Create budget rules
daily_budget = BudgetRule(
    entity_type="user_id",
    entity_id="user123",
    limit_usd=10.0,
    period=BudgetPeriod.DAILY,
)

monthly_budget = BudgetRule(
    entity_type="project_id",
    entity_id="proj456",
    limit_usd=500.0,
    period=BudgetPeriod.MONTHLY,
    soft_limit_usd=400.0,  # Warning at $400
    alert_threshold=0.8,    # Alert at 80%
)

# Add rules
enforcer.add_budget_rule(daily_budget)
enforcer.add_budget_rule(monthly_budget)

# Register alert callback
def handle_alert(alert):
    print(f"Budget alert: {alert.entity_id} at {alert.utilization*100:.1f}%")
    # Send email, log to monitoring system, etc.

enforcer.register_alert_callback(handle_alert)

# Check budget before execution (done automatically by BaseGraph)
try:
    result = enforcer.check_budget_before_execution(
        attribution,
        estimated_cost=5.0
    )
except BudgetExceededError as e:
    print(f"Budget exceeded: {e}")

# Get budget status
status = enforcer.get_budget_status("user_id", "user123")
print(f"Used: ${status['current_usage']:.2f}")
print(f"Remaining: ${status['remaining']:.2f}")
print(f"Utilization: {status['utilization']*100:.1f}%")
```

**Budget Periods:**
- `BudgetPeriod.DAILY`: Budget resets daily at midnight UTC
- `BudgetPeriod.WEEKLY`: Budget resets weekly on Monday
- `BudgetPeriod.MONTHLY`: Budget resets monthly on the 1st
- `BudgetPeriod.TOTAL`: Lifetime budget (never resets)

**Budget Enforcement:**
- **Hard limit**: Execution is blocked if budget would be exceeded
- **Soft limit**: Warning is issued but execution continues
- **Alert threshold**: Callback triggered when usage crosses threshold

## Integration with Graphs

### Automatic Cost Tracking

When you provide `cost_tracker` and `budget_enforcer` to a graph, costs are automatically tracked:

```python
from scrapegraphai.graphs import SmartScraperGraph
from scrapegraphai.cost_management import (
    AttributionContext,
    CostTracker,
    BudgetEnforcer,
    inject_attribution_into_state,
)

# Setup
tracker = CostTracker()
enforcer = BudgetEnforcer(tracker)
attribution = AttributionContext(user_id="user123")

# Configure graph
graph = SmartScraperGraph(
    prompt="Extract product information",
    source="https://example.com/products",
    config={"llm": {"model": "gpt-4"}},
    cost_tracker=tracker,
    budget_enforcer=enforcer,
)

# Inject attribution
initial_state = inject_attribution_into_state(
    {"url": "https://example.com/products"},
    attribution
)

# Execute - costs tracked automatically
result = graph.run()

# Check costs
summary = tracker.get_user_costs("user123")
print(f"This execution cost: ${summary.total_cost_usd:.4f}")
```

### Execution Flow

When a graph executes with cost management:

1. **Pre-execution**: Budget is checked before any LLM calls
   - If budget exceeded, `BudgetExceededError` is raised
   - Execution is blocked to prevent overspending

2. **During execution**: Costs are tracked per node
   - Attribution context extracted from state
   - Each node's LLM costs recorded
   - Costs attributed to user/project/tenant

3. **Post-execution**: Alerts are checked
   - If budget threshold crossed, callbacks triggered
   - Cost summaries updated in real-time

## Multi-Tenant Deployments

### Tenant Isolation

Track costs separately for each tenant:

```python
# Tenant A - User 1
attr_a1 = AttributionContext(
    tenant_id="tenant_a",
    user_id="user1",
    project_id="proj_alpha"
)

# Tenant A - User 2
attr_a2 = AttributionContext(
    tenant_id="tenant_a",
    user_id="user2",
    project_id="proj_alpha"
)

# Tenant B - User 1
attr_b1 = AttributionContext(
    tenant_id="tenant_b",
    user_id="user1",
    project_id="proj_beta"
)

# Get tenant-level costs
tenant_a_costs = tracker.get_tenant_costs("tenant_a")
tenant_b_costs = tracker.get_tenant_costs("tenant_b")

# Get per-user costs within tenant
user1_a_costs = tracker.get_user_costs("user1")  # All costs for user1
```

### Hierarchical Budgets

Set budgets at multiple levels:

```python
# Tenant-level budget (total for all users)
tenant_budget = BudgetRule(
    entity_type="tenant_id",
    entity_id="tenant_a",
    limit_usd=10000.0,
    period=BudgetPeriod.MONTHLY,
)

# Project-level budget
project_budget = BudgetRule(
    entity_type="project_id",
    entity_id="proj_alpha",
    limit_usd=5000.0,
    period=BudgetPeriod.MONTHLY,
)

# User-level budget
user_budget = BudgetRule(
    entity_type="user_id",
    entity_id="user1",
    limit_usd=500.0,
    period=BudgetPeriod.MONTHLY,
)

# Add all rules - all will be checked
enforcer.add_budget_rule(tenant_budget)
enforcer.add_budget_rule(project_budget)
enforcer.add_budget_rule(user_budget)

# Attribution with all levels
attribution = AttributionContext(
    tenant_id="tenant_a",
    project_id="proj_alpha",
    user_id="user1",
)

# Execution will be blocked if ANY budget exceeded
```

## Cost Reporting

### Generate Reports

```python
from datetime import datetime, timedelta

# Get current month costs
start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
monthly_summary = tracker.get_user_costs("user123", start_date=start_of_month)

print(f"Month-to-date costs:")
print(f"  Total: ${monthly_summary.total_cost_usd:.2f}")
print(f"  Requests: {monthly_summary.request_count}")
print(f"  Tokens: {monthly_summary.total_tokens:,}")
print(f"\nCost by model:")
for model, cost in monthly_summary.model_breakdown.items():
    print(f"  {model}: ${cost:.2f}")

# Get last 7 days
week_ago = datetime.utcnow() - timedelta(days=7)
weekly_summary = tracker.get_user_costs("user123", start_date=week_ago)

# Get specific date range
start = datetime(2024, 1, 1)
end = datetime(2024, 1, 31)
jan_summary = tracker.get_user_costs("user123", start_date=start, end_date=end)
```

### Export Cost Data

```python
# Get all records for a session
session_records = tracker.get_session_costs("session-abc-123")

# Convert to list of dicts for export
records_data = [record.to_dict() for record in session_records]

# Export to JSON
import json
with open('costs.json', 'w') as f:
    json.dump(records_data, f, indent=2)

# Export to CSV
import csv
with open('costs.csv', 'w', newline='') as f:
    if records_data:
        writer = csv.DictWriter(f, fieldnames=records_data[0].keys())
        writer.writeheader()
        writer.writerows(records_data)
```

## Storage Backends

### In-Memory Storage (Default)

```python
from scrapegraphai.cost_management import CostTracker, InMemoryCostStorage

# Default - uses in-memory storage
tracker = CostTracker()

# Explicit in-memory storage
storage = InMemoryCostStorage()
tracker = CostTracker(storage_backend=storage)
```

**Pros:**
- Fast
- No external dependencies
- Good for testing and development

**Cons:**
- Data lost when process restarts
- Not suitable for production with multiple instances
- Limited by available memory

### Custom Storage Backend

You can implement custom storage backends for persistence:

```python
class CustomCostStorage:
    """Example custom storage backend."""

    def store_record(self, record):
        """Store a cost record."""
        # Implement storage logic (e.g., database insert)
        pass

    def get_records_by_user(self, user_id, start_date=None, end_date=None):
        """Get records for a user."""
        # Implement query logic
        pass

    def get_records_by_project(self, project_id, start_date=None, end_date=None):
        """Get records for a project."""
        pass

    def get_records_by_tenant(self, tenant_id, start_date=None, end_date=None):
        """Get records for a tenant."""
        pass

    def get_records_by_session(self, session_id):
        """Get records for a session."""
        pass

# Use custom storage
custom_storage = CustomCostStorage()
tracker = CostTracker(storage_backend=custom_storage)
```

## Best Practices

### 1. Always Set Budgets in Production

```python
# ❌ Bad: No budget limits
tracker = CostTracker()
graph = SmartScraperGraph(..., cost_tracker=tracker)

# ✅ Good: Budget limits prevent runaway costs
tracker = CostTracker()
enforcer = BudgetEnforcer(tracker)
enforcer.add_budget_rule(BudgetRule(
    entity_type="user_id",
    entity_id="user123",
    limit_usd=100.0,
    period=BudgetPeriod.MONTHLY,
))
graph = SmartScraperGraph(
    ...,
    cost_tracker=tracker,
    budget_enforcer=enforcer,
)
```

### 2. Use Multi-Level Attribution

```python
# ✅ Track at multiple levels for better insights
attribution = AttributionContext(
    tenant_id="acme_corp",      # Company using your service
    project_id="web_scraping",  # Specific project/workspace
    user_id="alice@acme.com",   # Individual user
    tags={
        "environment": "production",
        "team": "data-engineering",
        "cost_center": "analytics",
    }
)
```

### 3. Register Alert Callbacks

```python
# ✅ Get notified before budget is exhausted
def send_budget_alert(alert):
    # Log to monitoring system
    logger.warning(f"Budget alert: {alert.entity_id} at {alert.utilization*100}%")

    # Send email notification
    send_email(
        to=f"{alert.entity_id}@company.com",
        subject=f"Budget Alert: {alert.utilization*100:.0f}% Used",
        body=f"You've used ${alert.current_usage:.2f} of ${alert.budget_limit:.2f}"
    )

    # Post to Slack
    post_to_slack(
        channel="#cost-alerts",
        message=f"⚠️ {alert.entity_id}: {alert.utilization*100:.0f}% budget used"
    )

enforcer.register_alert_callback(send_budget_alert)
```

### 4. Use Appropriate Budget Periods

```python
# Development/testing: Daily budgets
dev_budget = BudgetRule(
    entity_type="user_id",
    entity_id="dev_user",
    limit_usd=10.0,
    period=BudgetPeriod.DAILY,
)

# Production users: Monthly budgets
prod_budget = BudgetRule(
    entity_type="user_id",
    entity_id="prod_user",
    limit_usd=1000.0,
    period=BudgetPeriod.MONTHLY,
)

# Free tier: Total lifetime budget
free_budget = BudgetRule(
    entity_type="user_id",
    entity_id="free_user",
    limit_usd=5.0,
    period=BudgetPeriod.TOTAL,
)
```

### 5. Monitor and Adjust

```python
# Regularly review usage patterns
summary = tracker.get_user_costs("user123")

if summary.total_cost_usd > 50.0:
    # User is high-value, increase budget
    new_budget = BudgetRule(
        entity_type="user_id",
        entity_id="user123",
        limit_usd=200.0,
        period=BudgetPeriod.MONTHLY,
    )
    enforcer.add_budget_rule(new_budget)

# Analyze cost efficiency
if summary.request_count > 1000:
    avg_cost_per_request = summary.total_cost_usd / summary.request_count
    print(f"Average cost per request: ${avg_cost_per_request:.4f}")
```

## Troubleshooting

### Budget Checks Failing

**Problem:** Budget checks always fail even with sufficient budget.

**Solution:** Ensure entity_type matches in both BudgetRule and attribution:

```python
# ❌ Wrong: Mismatch in entity type
rule = BudgetRule(entity_type="user", entity_id="user123", ...)
attribution = AttributionContext(user_id="user123")  # Creates "user_id" key

# ✅ Correct: Entity type matches
rule = BudgetRule(entity_type="user_id", entity_id="user123", ...)
attribution = AttributionContext(user_id="user123")
```

### Costs Not Being Tracked

**Problem:** No costs appear in summaries.

**Solutions:**

1. Ensure attribution is injected into state:
```python
state = inject_attribution_into_state(state, attribution)
```

2. Ensure graph has cost_tracker:
```python
graph = SmartScraperGraph(..., cost_tracker=tracker)
```

3. Check that LLM calls are being made:
```python
# Costs only tracked when LLM is actually called
summary = tracker.get_user_costs("user123")
print(f"Requests: {summary.request_count}")  # Should be > 0
```

### Memory Usage Growing

**Problem:** Memory usage increases over time with in-memory storage.

**Solution:** Implement storage pruning or use persistent backend:

```python
# Option 1: Prune old records periodically
def prune_old_records(storage, days=30):
    cutoff = datetime.utcnow() - timedelta(days=days)
    storage.records = [
        r for r in storage.records
        if r.timestamp > cutoff
    ]

# Option 2: Use custom storage with automatic cleanup
class PersistentStorage:
    def store_record(self, record):
        # Write to database
        db.insert(record.to_dict())

    def cleanup_old_records(self, days=90):
        cutoff = datetime.utcnow() - timedelta(days=days)
        db.delete_where(timestamp__lt=cutoff)
```

## API Reference

See the module docstrings for complete API documentation:

```python
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
    ATTRIBUTION_CONTEXT_KEY,
    inject_attribution_into_state,
    extract_attribution_from_state,
)

# Get help on any class
help(AttributionContext)
help(CostTracker)
help(BudgetEnforcer)
```

## Examples

See `examples/cost_management_example.py` for complete working examples.

## Contributing

To extend the cost management system:

1. **Custom Storage Backends**: Implement the storage interface for your database
2. **Alert Integrations**: Create callbacks for your monitoring system
3. **Cost Estimation**: Add pre-execution cost estimation for better budget checks
4. **Reporting**: Build custom reporting dashboards using the cost data

For questions or issues, please open an issue on GitHub.
