"""
Example usage of cost attribution and budget management in ScrapeGraphAI.

This example demonstrates:
1. Setting up cost tracking and budget enforcement
2. Creating attribution contexts for multi-tenant scenarios
3. Tracking costs per user/project/tenant
4. Enforcing budget limits
5. Receiving budget alerts
"""

from scrapegraphai.cost_management import (
    AttributionContext,
    CostTracker,
    BudgetEnforcer,
    BudgetRule,
    BudgetPeriod,
    BudgetExceededError,
    inject_attribution_into_state,
)
from scrapegraphai.graphs import SmartScraperGraph
from datetime import datetime


def example_basic_attribution():
    """Basic example: Track costs for a single user."""
    print("=" * 60)
    print("Example 1: Basic Cost Attribution")
    print("=" * 60)

    # Create cost tracker
    tracker = CostTracker()

    # Create attribution context for a user
    attribution = AttributionContext(
        user_id="user123",
        tags={"environment": "production"}
    )

    # Simulate tracking some costs
    tracker.track_cost(
        attribution=attribution,
        node_name="FetchNode",
        model_name="gpt-4",
        total_tokens=1500,
        prompt_tokens=1000,
        completion_tokens=500,
        total_cost_usd=0.045,
        execution_time=2.5,
    )

    tracker.track_cost(
        attribution=attribution,
        node_name="ParseNode",
        model_name="gpt-4",
        total_tokens=800,
        prompt_tokens=600,
        completion_tokens=200,
        total_cost_usd=0.024,
        execution_time=1.2,
    )

    # Get cost summary
    summary = tracker.get_user_costs("user123")
    print(f"\nUser: {summary.entity_id}")
    print(f"Total Cost: ${summary.total_cost_usd:.4f}")
    print(f"Total Tokens: {summary.total_tokens}")
    print(f"Requests: {summary.request_count}")
    print(f"Model Breakdown: {summary.model_breakdown}")


def example_multi_tenant():
    """Example: Track costs across multiple tenants and users."""
    print("\n" + "=" * 60)
    print("Example 2: Multi-Tenant Cost Tracking")
    print("=" * 60)

    tracker = CostTracker()

    # Tenant A, User 1
    attr_a1 = AttributionContext(
        tenant_id="tenant_a",
        user_id="user_a1",
        project_id="project_alpha"
    )
    tracker.track_cost(
        attribution=attr_a1,
        node_name="GenerateNode",
        model_name="gpt-4",
        total_tokens=2000,
        prompt_tokens=1500,
        completion_tokens=500,
        total_cost_usd=0.06,
    )

    # Tenant A, User 2
    attr_a2 = AttributionContext(
        tenant_id="tenant_a",
        user_id="user_a2",
        project_id="project_alpha"
    )
    tracker.track_cost(
        attribution=attr_a2,
        node_name="GenerateNode",
        model_name="gpt-3.5-turbo",
        total_tokens=3000,
        prompt_tokens=2000,
        completion_tokens=1000,
        total_cost_usd=0.015,
    )

    # Tenant B, User 1
    attr_b1 = AttributionContext(
        tenant_id="tenant_b",
        user_id="user_b1",
        project_id="project_beta"
    )
    tracker.track_cost(
        attribution=attr_b1,
        node_name="GenerateNode",
        model_name="gpt-4",
        total_tokens=1000,
        prompt_tokens=700,
        completion_tokens=300,
        total_cost_usd=0.03,
    )

    # Get summaries per tenant
    print("\nTenant A Costs:")
    tenant_a_summary = tracker.get_tenant_costs("tenant_a")
    print(f"  Total: ${tenant_a_summary.total_cost_usd:.4f}")
    print(f"  Requests: {tenant_a_summary.request_count}")

    print("\nTenant B Costs:")
    tenant_b_summary = tracker.get_tenant_costs("tenant_b")
    print(f"  Total: ${tenant_b_summary.total_cost_usd:.4f}")
    print(f"  Requests: {tenant_b_summary.request_count}")

    # Get per-user breakdown
    print("\nPer-User Breakdown:")
    for user_id in ["user_a1", "user_a2", "user_b1"]:
        user_summary = tracker.get_user_costs(user_id)
        print(f"  {user_id}: ${user_summary.total_cost_usd:.4f}")


def example_budget_enforcement():
    """Example: Enforce budget limits with alerts."""
    print("\n" + "=" * 60)
    print("Example 3: Budget Enforcement with Alerts")
    print("=" * 60)

    tracker = CostTracker()
    enforcer = BudgetEnforcer(tracker)

    # Set up budget rule for a user
    user_budget = BudgetRule(
        entity_type="user_id",
        entity_id="user123",
        limit_usd=10.0,
        period=BudgetPeriod.DAILY,
        alert_threshold=0.8,  # Alert at 80% usage
    )
    enforcer.add_budget_rule(user_budget)

    # Register alert callback
    def handle_budget_alert(alert):
        print(f"\n🚨 BUDGET ALERT 🚨")
        print(f"   Entity: {alert.entity_type} {alert.entity_id}")
        print(f"   Usage: ${alert.current_usage:.4f} / ${alert.budget_limit:.4f}")
        print(f"   Utilization: {alert.utilization * 100:.1f}%")
        print(f"   Threshold: {alert.threshold * 100:.1f}%")

    enforcer.register_alert_callback(handle_budget_alert)

    attribution = AttributionContext(user_id="user123")

    # Simulate usage progression
    print("\n1. Initial usage (30%)...")
    tracker.track_cost(
        attribution=attribution,
        node_name="Node1",
        model_name="gpt-4",
        total_tokens=1000,
        prompt_tokens=800,
        completion_tokens=200,
        total_cost_usd=3.0,
    )
    enforcer.check_and_alert(attribution, 3.0)

    status = enforcer.get_budget_status("user_id", "user123")
    print(f"   Status: ${status['current_usage']:.2f} used, "
          f"${status['remaining']:.2f} remaining")

    print("\n2. Increased usage (85% - triggers alert)...")
    tracker.track_cost(
        attribution=attribution,
        node_name="Node2",
        model_name="gpt-4",
        total_tokens=2000,
        prompt_tokens=1500,
        completion_tokens=500,
        total_cost_usd=5.5,
    )
    enforcer.check_and_alert(attribution, 5.5)

    print("\n3. Attempting to exceed budget...")
    try:
        enforcer.check_budget_before_execution(attribution, estimated_cost=2.0)
        print("   ❌ This shouldn't execute")
    except BudgetExceededError as e:
        print(f"   ✓ Execution blocked: {e}")


def example_with_graph():
    """Example: Integrate cost tracking with a graph execution."""
    print("\n" + "=" * 60)
    print("Example 4: Integration with SmartScraperGraph")
    print("=" * 60)

    # Setup cost tracking
    tracker = CostTracker()
    enforcer = BudgetEnforcer(tracker)

    # Set user budget
    user_budget = BudgetRule(
        entity_type="user_id",
        entity_id="alice",
        limit_usd=100.0,
        period=BudgetPeriod.MONTHLY,
    )
    enforcer.add_budget_rule(user_budget)

    # Create attribution context
    attribution = AttributionContext(
        user_id="alice",
        project_id="web_scraping_project",
        tags={"environment": "production", "team": "data-eng"}
    )

    # Note: This is conceptual - actual graph execution would require proper config
    print("\nGraph Configuration:")
    print(f"  User: {attribution.user_id}")
    print(f"  Project: {attribution.project_id}")
    print(f"  Budget: ${user_budget.limit_usd:.2f} ({user_budget.period.value})")

    # In actual usage, you would:
    # 1. Create your graph with cost_tracker and budget_enforcer
    graph_config = {
        "llm": {
            "model": "gpt-4",
            "api_key": "YOUR_API_KEY",
        },
        "verbose": False,
    }

    # 2. Inject attribution into initial state
    initial_state = {
        "url": "https://example.com",
        "user_prompt": "Extract main content"
    }
    initial_state = inject_attribution_into_state(initial_state, attribution)

    # 3. Create graph with cost management
    # graph = SmartScraperGraph(
    #     prompt="Extract the main content",
    #     source="https://example.com",
    #     config=graph_config,
    #     cost_tracker=tracker,
    #     budget_enforcer=enforcer,
    # )

    # 4. Execute - costs will be automatically tracked
    # result = graph.run()

    print("\n  ✓ Attribution injected into state")
    print("  ✓ Budget enforcer will check limits before execution")
    print("  ✓ Cost tracker will record all LLM costs")
    print("  ✓ Alerts will be triggered at threshold")


def example_cost_reporting():
    """Example: Generate cost reports and analyze trends."""
    print("\n" + "=" * 60)
    print("Example 5: Cost Reporting and Analysis")
    print("=" * 60)

    tracker = CostTracker()

    # Simulate multiple scraping operations
    users = ["alice", "bob", "charlie"]
    projects = ["project_a", "project_b"]

    print("\nSimulating scraping operations...")
    for i, user in enumerate(users):
        for j, project in enumerate(projects):
            attribution = AttributionContext(
                user_id=user,
                project_id=project,
                tenant_id="company_xyz"
            )

            # Simulate 3 nodes per operation
            for node_num in range(3):
                cost = (i + 1) * (j + 1) * 0.01  # Varying cost
                tracker.track_cost(
                    attribution=attribution,
                    node_name=f"Node{node_num}",
                    model_name="gpt-4" if node_num % 2 == 0 else "gpt-3.5-turbo",
                    total_tokens=1000 * (i + 1),
                    prompt_tokens=700 * (i + 1),
                    completion_tokens=300 * (i + 1),
                    total_cost_usd=cost,
                )

    # Generate reports
    print("\n📊 Cost Report by User:")
    print("-" * 40)
    for user in users:
        summary = tracker.get_user_costs(user)
        print(f"{user:10s}: ${summary.total_cost_usd:7.4f} "
              f"({summary.request_count} requests)")

    print("\n📊 Cost Report by Project:")
    print("-" * 40)
    for project in projects:
        summary = tracker.get_project_costs(project)
        print(f"{project:12s}: ${summary.total_cost_usd:7.4f} "
              f"({summary.request_count} requests)")
        if summary.model_breakdown:
            print(f"             Model breakdown:")
            for model, cost in summary.model_breakdown.items():
                print(f"               {model:15s}: ${cost:.4f}")

    print("\n📊 Total Company Cost:")
    print("-" * 40)
    tenant_summary = tracker.get_tenant_costs("company_xyz")
    print(f"Total: ${tenant_summary.total_cost_usd:.4f}")
    print(f"Total Requests: {tenant_summary.request_count}")
    print(f"Total Tokens: {tenant_summary.total_tokens}")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("ScrapeGraphAI Cost Management Examples")
    print("=" * 60)

    example_basic_attribution()
    example_multi_tenant()
    example_budget_enforcement()
    example_with_graph()
    example_cost_reporting()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("1. AttributionContext tracks user/project/tenant for cost attribution")
    print("2. CostTracker records and aggregates costs per entity")
    print("3. BudgetEnforcer prevents runaway costs with hard limits")
    print("4. Budget alerts notify when thresholds are exceeded")
    print("5. Easy integration with existing graphs via parameters")
    print()


if __name__ == "__main__":
    main()
