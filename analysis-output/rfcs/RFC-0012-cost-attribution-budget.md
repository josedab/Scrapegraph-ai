# RFC-0012: Cost Attribution & Budget Management

**Status:** Draft
**Author:** ScrapeGraphAI Analysis Team
**Created:** 2025-11-20
**Based on Commit:** 32d5636ac3465edd0a8af47c6242f16a0beb35f5

## Summary

This RFC proposes implementing comprehensive cost attribution and budget management capabilities for ScrapeGraphAI. Currently, LLM costs are tracked globally via `cb_total` in `base_graph.py` with no mechanism to attribute costs to specific users, projects, or tenants, making it impossible to deploy ScrapeGraphAI in multi-tenant SaaS environments or enforce budget limits. This RFC introduces a context propagation system for attribution metadata, per-entity cost tracking, hard budget limits with pre-execution checks, and real-time budget alerts to enable production deployments with cost controls.

## Motivation

### Current Problems

**Problem 1: No Cost Attribution Context**

The current implementation aggregates costs globally without any attribution to users, projects, or tenants:

```python
# From scrapegraphai/graphs/base_graph.py:246-252
cb_total = {
    "total_tokens": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "successful_requests": 0,
    "total_cost_USD": 0.0,
}
```

**Issues:**
- `cb_total` aggregates all costs globally across execution
- No user_id, project_id, or tenant_id tracking
- Impossible to answer "How much did user X spend?"
- Cannot charge back costs to specific customers
- No visibility into which projects consume the most resources

**Problem 2: No Context Propagation Through Graph State**

Graph execution state contains no attribution metadata:

```python
# From base_graph.py:344-378
def execute(self, initial_state: dict) -> Tuple[dict, list]:
    current_node_name = self.entry_point
    state = initial_state  # No attribution context added

    while current_node_name:
        current_node = self._get_node_by_name(current_node_name)
        result, node_exec_time, cb_data = self._execute_node(
            current_node, state, llm_model, llm_model_name
        )
        # cb_data has no user_id, project_id, or tenant_id
```

**Impact:**
- Attribution context not available during execution
- Callback handlers cannot tag costs with user/project
- Cost tracking remains global and unattributable
- Multi-tenant deployments cannot isolate costs

**Problem 3: No Budget Enforcement Mechanism**

There is no system to enforce budget limits:

```python
# Current: No budget checking before LLM calls
def _execute_node(self, current_node, state, llm_model, llm_model_name):
    curr_time = time.time()

    with self.callback_manager.exclusive_get_callback(
        llm_model, llm_model_name
    ) as cb:
        result = current_node.execute(state)  # Executes regardless of budget
```

**Issues:**
- No pre-execution budget checks
- Users can exceed budgets without warning
- No hard limits to prevent runaway costs
- Costs only known after execution completes
- Risk of unexpected large bills

**Problem 4: No Cost Tracking Per Entity**

The system lacks infrastructure to track costs by entity:

```python
# From base_graph.py:286-289
if cb_data:
    exec_info.append(cb_data)
    for key in cb_total:
        cb_total[key] += cb_data[key]  # Global aggregation only
```

**Missing capabilities:**
- Per-user cost tracking
- Per-project cost tracking
- Per-tenant cost tracking
- Historical cost data storage
- Cost trend analysis
- Budget utilization reporting

### Why This Matters

**SaaS Deployment Blocker:**
- Cannot deploy ScrapeGraphAI as a multi-tenant SaaS
- No way to charge customers based on usage
- No cost isolation between tenants
- Risk of one tenant consuming all resources

**Cost Control & Governance:**
- Risk of runaway costs from uncontrolled scraping
- No ability to set budget limits per user/project
- Cannot prevent users from exceeding allocated budgets
- No alerts when approaching budget limits

**Financial Transparency:**
- Users cannot see their own cost consumption
- Admins cannot generate cost reports by user/project
- No visibility into cost drivers
- Cannot optimize based on cost data

**Compliance & Billing:**
- Cannot generate accurate invoices based on usage
- No audit trail of costs per customer
- Impossible to implement fair usage policies
- Risk of cost disputes without attribution

**Real-World Scenario:**

```
Company deploys ScrapeGraphAI for 100 users:
- User A runs 10 small scraping jobs: $2 in LLM costs
- User B accidentally runs infinite loop scraping: $5,000 in LLM costs
- User C runs legitimate large-scale scraping: $200 in LLM costs

Current system:
- Total cost shown: $5,202
- Attribution: Unknown
- Budget exceeded: Unknown
- Prevention: None
- Billing: Impossible

Desired system:
- User A: $2 (under $50 budget ✓)
- User B: Blocked at $100 budget limit ✗
- User C: $200 (under $500 budget ✓)
- Total: $302 (prevented $4,900 in runaway costs)
- Billing: Accurate per-user invoices
```

## Current State

### Architecture Analysis

**File: `/home/user/Scrapegraph-ai/scrapegraphai/graphs/base_graph.py`**

The `BaseGraph` class manages graph execution with global cost tracking:

1. **Global Cost Aggregation** (lines 246-252):
   - `cb_total` dictionary aggregates costs globally
   - No attribution fields (user_id, project_id, tenant_id)
   - Simple summation without entity tracking
   - No budget checking logic

2. **State Management** (lines 236-342):
   - `state` dictionary passed through nodes
   - No reserved keys for attribution context
   - No mechanism to inject cost tracking metadata
   - State modifications don't preserve attribution

3. **Callback Integration** (lines 71, 201-220):
   - `CustomLLMCallbackManager` tracks token usage
   - Returns `cb_data` with cost information
   - No attribution context attached to callbacks
   - Thread-safe but not multi-tenant aware

4. **Cost Reporting** (lines 310-320):
   - Execution info appended to list
   - Global totals computed at end
   - No per-entity breakdown
   - Output format has no attribution fields

**File: `/home/user/Scrapegraph-ai/scrapegraphai/utils/custom_callback.py`**

The `CustomCallbackHandler` computes costs but lacks attribution:

1. **Token Tracking** (lines 46-50):
   ```python
   total_tokens: int = 0
   prompt_tokens: int = 0
   completion_tokens: int = 0
   successful_requests: int = 0
   total_cost: float = 0.0
   ```
   - Instance variables track aggregates
   - No user_id, project_id, or tenant_id fields
   - No budget checking on `on_llm_end`

2. **Cost Calculation** (lines 117-132):
   - Computes cost using `get_token_cost_for_model()`
   - Updates shared state with lock
   - No budget limit enforcement
   - No cost attribution tagging

**File: `/home/user/Scrapegraph-ai/scrapegraphai/utils/prettify_exec_info.py`**

The output formatting lacks attribution:

```python
# Lines 30-49
def prettify_exec_info(complete_result: list[dict], as_string: bool = True):
    # ...
    lines.append(
        f"{'Node':<20} {'Tokens':<10} {'Prompt':<10} {'Compl.':<10} "
        f"{'Requests':<10} {'Cost ($)':<10} {'Time (s)':<10}"
    )
    # No columns for: User, Project, Tenant, Budget Remaining
```

### Missing Components

**1. Cost Attribution Store:**
- No database or storage for per-entity costs
- No historical cost tracking
- No aggregation by user/project/tenant
- No persistence across sessions

**2. Budget Management Service:**
- No budget definition mechanism
- No budget enforcement logic
- No budget alert system
- No budget reporting

**3. Context Propagation:**
- No standard way to pass attribution through state
- No validation of attribution context
- No middleware to inject/extract context
- No API for setting attribution

**4. Multi-Tenant Isolation:**
- No tenant-level cost isolation
- No cross-tenant cost prevention
- No tenant quota system
- No tenant billing integration

## Detailed Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Request                                 │
│                  {user_id, project_id, tenant_id}                   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AttributionContext                                │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  - user_id: str                                                 │ │
│  │  - project_id: str                                              │ │
│  │  - tenant_id: str                                               │ │
│  │  - session_id: str                                              │ │
│  │  - tags: Dict[str, str]                                         │ │
│  └────────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │ Injected into state
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       BaseGraph.execute()                            │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  1. Check budget before execution (BudgetEnforcer)             │ │
│  │  2. Inject attribution into state                              │ │
│  │  3. Execute nodes with attribution context                     │ │
│  │  4. Track costs per entity (CostTracker)                       │ │
│  │  5. Update budget usage                                        │ │
│  │  6. Check alerts                                               │ │
│  └────────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
                ▼                         ▼
┌──────────────────────────┐  ┌──────────────────────────┐
│    CostTracker           │  │   BudgetEnforcer         │
│                          │  │                          │
│  - track_cost()          │  │  - check_budget()        │
│  - get_usage()           │  │  - enforce_limit()       │
│  - get_breakdown()       │  │  - check_alerts()        │
│                          │  │  - get_remaining()       │
│  Storage:                │  │                          │
│  - Per-user costs        │  │  Budget Rules:           │
│  - Per-project costs     │  │  - Hard limits           │
│  - Per-tenant costs      │  │  - Soft limits (alerts)  │
│  - Historical data       │  │  - Rate limits           │
└──────────────────────────┘  └──────────────────────────┘
                │                         │
                └────────────┬────────────┘
                             ▼
                ┌──────────────────────────┐
                │   CostAttributionStore   │
                │                          │
                │  Backends:               │
                │  - InMemory (default)    │
                │  - SQLite                │
                │  - PostgreSQL            │
                │  - Redis                 │
                └──────────────────────────┘
```

### Component Design

#### 1. AttributionContext Class

**Location:** `scrapegraphai/cost_management/attribution.py`

```python
"""
Cost attribution context for tracking resource usage per entity.
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional
from datetime import datetime
import uuid


@dataclass
class AttributionContext:
    """
    Attribution context for cost tracking.

    This context is propagated through graph execution to enable
    cost attribution to specific users, projects, and tenants.

    Attributes:
        user_id: Unique identifier for the user initiating the request
        project_id: Unique identifier for the project/workspace
        tenant_id: Unique identifier for the tenant (multi-tenant deployments)
        session_id: Unique identifier for this execution session
        tags: Additional key-value tags for custom attribution
        created_at: Timestamp when context was created
    """

    user_id: Optional[str] = None
    project_id: Optional[str] = None
    tenant_id: Optional[str] = None
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Validate that at least one attribution ID is provided."""
        if not any([self.user_id, self.project_id, self.tenant_id]):
            raise ValueError(
                "AttributionContext requires at least one of: "
                "user_id, project_id, or tenant_id"
            )

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            **asdict(self),
            'created_at': self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'AttributionContext':
        """Create from dictionary."""
        data = data.copy()
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)

    def get_entity_keys(self) -> Dict[str, str]:
        """
        Get all entity identifiers for cost tracking.

        Returns:
            Dict mapping entity type to entity ID
        """
        keys = {}
        if self.user_id:
            keys['user_id'] = self.user_id
        if self.project_id:
            keys['project_id'] = self.project_id
        if self.tenant_id:
            keys['tenant_id'] = self.tenant_id
        return keys


# State key for attribution context
ATTRIBUTION_CONTEXT_KEY = "_attribution_context"


def inject_attribution_into_state(
    state: Dict,
    context: AttributionContext
) -> Dict:
    """
    Inject attribution context into graph state.

    Args:
        state: The graph state dictionary
        context: The attribution context to inject

    Returns:
        Modified state with attribution context
    """
    state[ATTRIBUTION_CONTEXT_KEY] = context
    return state


def extract_attribution_from_state(state: Dict) -> Optional[AttributionContext]:
    """
    Extract attribution context from graph state.

    Args:
        state: The graph state dictionary

    Returns:
        AttributionContext if present, None otherwise
    """
    return state.get(ATTRIBUTION_CONTEXT_KEY)
```

#### 2. CostRecord Class

**Location:** `scrapegraphai/cost_management/models.py`

```python
"""
Data models for cost tracking.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
import uuid


@dataclass
class CostRecord:
    """
    Record of a single cost event.

    Attributes:
        id: Unique identifier for this cost record
        user_id: User who incurred the cost
        project_id: Project associated with the cost
        tenant_id: Tenant associated with the cost
        session_id: Execution session ID
        node_name: Name of the node that incurred the cost
        model_name: LLM model name
        total_tokens: Total tokens consumed
        prompt_tokens: Prompt tokens consumed
        completion_tokens: Completion tokens consumed
        total_cost_usd: Total cost in USD
        timestamp: When the cost was incurred
        tags: Additional metadata tags
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    tenant_id: Optional[str] = None
    session_id: Optional[str] = None
    node_name: str = ""
    model_name: str = ""
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost_usd: float = 0.0
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'project_id': self.project_id,
            'tenant_id': self.tenant_id,
            'session_id': self.session_id,
            'node_name': self.node_name,
            'model_name': self.model_name,
            'total_tokens': self.total_tokens,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_cost_usd': self.total_cost_usd,
            'execution_time': self.execution_time,
            'timestamp': self.timestamp.isoformat(),
            'tags': self.tags,
        }


@dataclass
class CostSummary:
    """
    Aggregated cost summary for an entity.

    Attributes:
        entity_type: Type of entity (user, project, tenant)
        entity_id: ID of the entity
        total_cost_usd: Total cost in USD
        total_tokens: Total tokens consumed
        request_count: Number of requests
        model_breakdown: Cost breakdown by model
        date_range: Date range for this summary
    """

    entity_type: str
    entity_id: str
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    request_count: int = 0
    model_breakdown: Dict[str, float] = field(default_factory=dict)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'total_cost_usd': self.total_cost_usd,
            'total_tokens': self.total_tokens,
            'request_count': self.request_count,
            'model_breakdown': self.model_breakdown,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
        }
```

#### 3. CostTracker Class

**Location:** `scrapegraphai/cost_management/tracker.py`

```python
"""
Cost tracking service for attribution.
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import threading

from .models import CostRecord, CostSummary
from .attribution import AttributionContext


class CostTracker:
    """
    Tracks costs per user, project, and tenant.

    Features:
    - Per-entity cost tracking
    - Historical cost data storage
    - Cost aggregation and reporting
    - Thread-safe operations
    """

    def __init__(self, storage_backend=None):
        """
        Initialize cost tracker.

        Args:
            storage_backend: Backend for persisting cost data.
                           If None, uses in-memory storage.
        """
        self.storage = storage_backend or InMemoryCostStorage()
        self._lock = threading.Lock()

    def track_cost(
        self,
        attribution: AttributionContext,
        node_name: str,
        model_name: str,
        total_tokens: int,
        prompt_tokens: int,
        completion_tokens: int,
        total_cost_usd: float,
        execution_time: float = 0.0,
    ) -> CostRecord:
        """
        Track a cost event.

        Args:
            attribution: Attribution context
            node_name: Name of the node
            model_name: LLM model name
            total_tokens: Total tokens used
            prompt_tokens: Prompt tokens
            completion_tokens: Completion tokens
            total_cost_usd: Total cost in USD
            execution_time: Execution time in seconds

        Returns:
            CostRecord that was created and stored
        """
        with self._lock:
            record = CostRecord(
                user_id=attribution.user_id,
                project_id=attribution.project_id,
                tenant_id=attribution.tenant_id,
                session_id=attribution.session_id,
                node_name=node_name,
                model_name=model_name,
                total_tokens=total_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_cost_usd=total_cost_usd,
                execution_time=execution_time,
                tags=attribution.tags,
            )

            self.storage.store_record(record)
            return record

    def get_user_costs(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> CostSummary:
        """
        Get cost summary for a user.

        Args:
            user_id: User ID
            start_date: Start of date range (None = all time)
            end_date: End of date range (None = now)

        Returns:
            CostSummary for the user
        """
        with self._lock:
            records = self.storage.get_records_by_user(user_id, start_date, end_date)
            return self._aggregate_records('user', user_id, records, start_date, end_date)

    def get_project_costs(
        self,
        project_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> CostSummary:
        """Get cost summary for a project."""
        with self._lock:
            records = self.storage.get_records_by_project(project_id, start_date, end_date)
            return self._aggregate_records('project', project_id, records, start_date, end_date)

    def get_tenant_costs(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> CostSummary:
        """Get cost summary for a tenant."""
        with self._lock:
            records = self.storage.get_records_by_tenant(tenant_id, start_date, end_date)
            return self._aggregate_records('tenant', tenant_id, records, start_date, end_date)

    def _aggregate_records(
        self,
        entity_type: str,
        entity_id: str,
        records: List[CostRecord],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> CostSummary:
        """Aggregate cost records into summary."""
        total_cost = 0.0
        total_tokens = 0
        model_breakdown = defaultdict(float)

        for record in records:
            total_cost += record.total_cost_usd
            total_tokens += record.total_tokens
            model_breakdown[record.model_name] += record.total_cost_usd

        return CostSummary(
            entity_type=entity_type,
            entity_id=entity_id,
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            request_count=len(records),
            model_breakdown=dict(model_breakdown),
            start_date=start_date,
            end_date=end_date,
        )

    def get_session_costs(self, session_id: str) -> List[CostRecord]:
        """Get all cost records for a session."""
        with self._lock:
            return self.storage.get_records_by_session(session_id)


class InMemoryCostStorage:
    """In-memory storage backend for cost records."""

    def __init__(self):
        self.records: List[CostRecord] = []
        self._user_index: Dict[str, List[CostRecord]] = defaultdict(list)
        self._project_index: Dict[str, List[CostRecord]] = defaultdict(list)
        self._tenant_index: Dict[str, List[CostRecord]] = defaultdict(list)
        self._session_index: Dict[str, List[CostRecord]] = defaultdict(list)

    def store_record(self, record: CostRecord):
        """Store a cost record."""
        self.records.append(record)

        if record.user_id:
            self._user_index[record.user_id].append(record)
        if record.project_id:
            self._project_index[record.project_id].append(record)
        if record.tenant_id:
            self._tenant_index[record.tenant_id].append(record)
        if record.session_id:
            self._session_index[record.session_id].append(record)

    def get_records_by_user(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[CostRecord]:
        """Get records for a user, optionally filtered by date."""
        records = self._user_index.get(user_id, [])
        return self._filter_by_date(records, start_date, end_date)

    def get_records_by_project(
        self,
        project_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[CostRecord]:
        """Get records for a project."""
        records = self._project_index.get(project_id, [])
        return self._filter_by_date(records, start_date, end_date)

    def get_records_by_tenant(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[CostRecord]:
        """Get records for a tenant."""
        records = self._tenant_index.get(tenant_id, [])
        return self._filter_by_date(records, start_date, end_date)

    def get_records_by_session(self, session_id: str) -> List[CostRecord]:
        """Get records for a session."""
        return self._session_index.get(session_id, [])

    def _filter_by_date(
        self,
        records: List[CostRecord],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> List[CostRecord]:
        """Filter records by date range."""
        if not start_date and not end_date:
            return records

        filtered = []
        for record in records:
            if start_date and record.timestamp < start_date:
                continue
            if end_date and record.timestamp > end_date:
                continue
            filtered.append(record)

        return filtered
```

#### 4. BudgetRule and BudgetEnforcer Classes

**Location:** `scrapegraphai/cost_management/budget.py`

```python
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

    def add_budget_rule(self, rule: BudgetRule):
        """
        Add a budget rule.

        Args:
            rule: BudgetRule to add
        """
        key = (rule.entity_type, rule.entity_id)
        self.budget_rules[key] = rule

    def remove_budget_rule(self, entity_type: str, entity_id: str):
        """Remove a budget rule."""
        key = (entity_type, entity_id)
        if key in self.budget_rules:
            del self.budget_rules[key]

    def register_alert_callback(self, callback: callable):
        """
        Register a callback for budget alerts.

        Args:
            callback: Function that takes (rule, usage, utilization)
        """
        self._alert_callbacks.append(callback)

    def check_budget_before_execution(
        self,
        attribution: AttributionContext,
        estimated_cost: Optional[float] = None,
    ):
        """
        Check budget before executing an operation.

        Raises BudgetExceededError if any applicable budget would be exceeded.

        Args:
            attribution: Attribution context
            estimated_cost: Estimated cost of operation (if known)
        """
        # Check all applicable budgets
        for entity_type, entity_id in attribution.get_entity_keys().items():
            rule = self.budget_rules.get((entity_type, entity_id))
            if not rule:
                continue

            # Get current usage for the period
            start_date, end_date = rule.get_date_range()

            if entity_type == 'user':
                summary = self.cost_tracker.get_user_costs(entity_id, start_date, end_date)
            elif entity_type == 'project':
                summary = self.cost_tracker.get_project_costs(entity_id, start_date, end_date)
            elif entity_type == 'tenant':
                summary = self.cost_tracker.get_tenant_costs(entity_id, start_date, end_date)
            else:
                continue

            current_usage = summary.total_cost_usd

            # Check hard limit
            if estimated_cost:
                projected_usage = current_usage + estimated_cost
                if projected_usage > rule.limit_usd:
                    raise BudgetExceededError(
                        f"Budget exceeded for {entity_type} '{entity_id}': "
                        f"Current: ${current_usage:.2f}, "
                        f"Estimated: ${estimated_cost:.2f}, "
                        f"Limit: ${rule.limit_usd:.2f}, "
                        f"Period: {rule.period.value}"
                    )
            else:
                # No estimated cost, just check if already over
                if current_usage >= rule.limit_usd:
                    raise BudgetExceededError(
                        f"Budget exceeded for {entity_type} '{entity_id}': "
                        f"Current: ${current_usage:.2f}, "
                        f"Limit: ${rule.limit_usd:.2f}, "
                        f"Period: {rule.period.value}"
                    )

            # Check soft limit
            if rule.soft_limit_usd and current_usage >= rule.soft_limit_usd:
                self._trigger_alert(
                    rule,
                    current_usage,
                    current_usage / rule.limit_usd,
                    "Soft limit exceeded"
                )

            # Check alert threshold
            utilization = current_usage / rule.limit_usd
            if utilization >= rule.alert_threshold:
                self._trigger_alert(
                    rule,
                    current_usage,
                    utilization,
                    f"Alert threshold {rule.alert_threshold*100:.0f}% reached"
                )

    def get_budget_status(
        self,
        entity_type: str,
        entity_id: str,
    ) -> Dict:
        """
        Get budget status for an entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of entity

        Returns:
            Dict with budget status information
        """
        rule = self.budget_rules.get((entity_type, entity_id))
        if not rule:
            return {
                'has_budget': False,
                'entity_type': entity_type,
                'entity_id': entity_id,
            }

        start_date, end_date = rule.get_date_range()

        if entity_type == 'user':
            summary = self.cost_tracker.get_user_costs(entity_id, start_date, end_date)
        elif entity_type == 'project':
            summary = self.cost_tracker.get_project_costs(entity_id, start_date, end_date)
        elif entity_type == 'tenant':
            summary = self.cost_tracker.get_tenant_costs(entity_id, start_date, end_date)
        else:
            return {'has_budget': False}

        current_usage = summary.total_cost_usd
        remaining = rule.limit_usd - current_usage
        utilization = current_usage / rule.limit_usd

        return {
            'has_budget': True,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'limit_usd': rule.limit_usd,
            'soft_limit_usd': rule.soft_limit_usd,
            'current_usage_usd': current_usage,
            'remaining_usd': max(0, remaining),
            'utilization': utilization,
            'period': rule.period.value,
            'is_exceeded': current_usage >= rule.limit_usd,
            'is_soft_exceeded': rule.soft_limit_usd and current_usage >= rule.soft_limit_usd,
            'alert_triggered': utilization >= rule.alert_threshold,
        }

    def _trigger_alert(
        self,
        rule: BudgetRule,
        current_usage: float,
        utilization: float,
        message: str,
    ):
        """Trigger budget alert callbacks."""
        for callback in self._alert_callbacks:
            try:
                callback(rule, current_usage, utilization, message)
            except Exception as e:
                # Log error but don't fail the check
                print(f"Budget alert callback failed: {e}")
```

#### 5. Integration with BaseGraph

**Modified:** `scrapegraphai/graphs/base_graph.py`

```python
class BaseGraph:
    """
    BaseGraph manages the execution flow with cost attribution and budget enforcement.
    """

    def __init__(
        self,
        nodes: list,
        edges: list,
        entry_point: str,
        use_burr: bool = False,
        burr_config: dict = None,
        graph_name: str = "Custom",
        # NEW: Cost management parameters
        enable_cost_tracking: bool = True,
        cost_tracker: Optional['CostTracker'] = None,
        budget_enforcer: Optional['BudgetEnforcer'] = None,
    ):
        # ... existing initialization ...

        # Cost management setup
        self.enable_cost_tracking = enable_cost_tracking

        if self.enable_cost_tracking:
            from ..cost_management.tracker import CostTracker
            from ..cost_management.budget import BudgetEnforcer

            self.cost_tracker = cost_tracker or CostTracker()
            self.budget_enforcer = budget_enforcer or BudgetEnforcer(self.cost_tracker)
        else:
            self.cost_tracker = None
            self.budget_enforcer = None

    def _execute_standard(self, initial_state: dict) -> Tuple[dict, list]:
        """
        Executes the graph with cost attribution and budget enforcement.
        """
        from ..cost_management.attribution import (
            extract_attribution_from_state,
            ATTRIBUTION_CONTEXT_KEY
        )

        # Extract attribution context from state
        attribution = extract_attribution_from_state(initial_state)

        # Check budget before execution if attribution provided
        if self.enable_cost_tracking and attribution and self.budget_enforcer:
            try:
                self.budget_enforcer.check_budget_before_execution(attribution)
            except Exception as e:
                logger.error(f"Budget check failed: {e}")
                raise

        current_node_name = self.entry_point
        state = initial_state

        total_exec_time = 0.0
        exec_info = []
        cb_total = {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "successful_requests": 0,
            "total_cost_USD": 0.0,
        }

        # NEW: Per-entity cost tracking
        entity_costs = {}
        if attribution:
            for entity_type, entity_id in attribution.get_entity_keys().items():
                entity_costs[f"{entity_type}:{entity_id}"] = 0.0

        start_time = time.time()
        error_node = None
        source_type = None
        llm_model = None
        llm_model_name = None
        embedder_model = None
        source = []
        prompt = None
        schema = None

        while current_node_name:
            current_node = self._get_node_by_name(current_node_name)

            if source_type is None:
                source_type, source, prompt = self._update_source_info(
                    current_node, state
                )

            if llm_model is None:
                llm_model, llm_model_name, embedder_model = self._get_model_info(
                    current_node
                )

            if schema is None:
                schema = self._get_schema(current_node)

            try:
                result, node_exec_time, cb_data = self._execute_node(
                    current_node, state, llm_model, llm_model_name
                )
                total_exec_time += node_exec_time

                if cb_data:
                    # Add attribution to cb_data
                    if attribution:
                        cb_data['user_id'] = attribution.user_id
                        cb_data['project_id'] = attribution.project_id
                        cb_data['tenant_id'] = attribution.tenant_id
                        cb_data['session_id'] = attribution.session_id

                    exec_info.append(cb_data)

                    # Update global totals
                    for key in cb_total:
                        cb_total[key] += cb_data[key]

                    # Track cost per entity
                    if self.enable_cost_tracking and attribution:
                        self.cost_tracker.track_cost(
                            attribution=attribution,
                            node_name=cb_data['node_name'],
                            model_name=llm_model_name or "unknown",
                            total_tokens=cb_data['total_tokens'],
                            prompt_tokens=cb_data['prompt_tokens'],
                            completion_tokens=cb_data['completion_tokens'],
                            total_cost_usd=cb_data['total_cost_USD'],
                            execution_time=node_exec_time,
                        )

                        # Update entity cost tracking
                        for entity_type, entity_id in attribution.get_entity_keys().items():
                            key = f"{entity_type}:{entity_id}"
                            entity_costs[key] += cb_data['total_cost_USD']

                        # Check if we're approaching/exceeding budget
                        if self.budget_enforcer:
                            try:
                                self.budget_enforcer.check_budget_before_execution(attribution)
                            except Exception as budget_error:
                                logger.warning(f"Budget exceeded during execution: {budget_error}")
                                # Optionally: could raise to stop execution immediately
                                # raise

                current_node_name = self._get_next_node(current_node, result)

            except Exception as e:
                error_node = current_node.node_name
                graph_execution_time = time.time() - start_time
                log_graph_execution(
                    graph_name=self.graph_name,
                    source=source,
                    prompt=prompt,
                    schema=schema,
                    llm_model=llm_model_name,
                    embedder_model=embedder_model,
                    source_type=source_type,
                    execution_time=graph_execution_time,
                    error_node=error_node,
                    exception=str(e),
                )
                raise e

        # Add TOTAL RESULT with attribution
        total_result = {
            "node_name": "TOTAL RESULT",
            "total_tokens": cb_total["total_tokens"],
            "prompt_tokens": cb_total["prompt_tokens"],
            "completion_tokens": cb_total["completion_tokens"],
            "successful_requests": cb_total["successful_requests"],
            "total_cost_USD": cb_total["total_cost_USD"],
            "exec_time": total_exec_time,
        }

        # Add attribution to total
        if attribution:
            total_result['user_id'] = attribution.user_id
            total_result['project_id'] = attribution.project_id
            total_result['tenant_id'] = attribution.tenant_id
            total_result['session_id'] = attribution.session_id
            total_result['entity_breakdown'] = entity_costs

        exec_info.append(total_result)

        graph_execution_time = time.time() - start_time
        response = state.get("answer", None) if source_type == "url" else None
        content = state.get("parsed_doc", None) if response is not None else None

        log_graph_execution(
            graph_name=self.graph_name,
            source=source,
            prompt=prompt,
            schema=schema,
            llm_model=llm_model_name,
            embedder_model=embedder_model,
            source_type=source_type,
            content=content,
            response=response,
            execution_time=graph_execution_time,
            total_tokens=(
                cb_total["total_tokens"] if cb_total["total_tokens"] > 0 else None
            ),
        )

        return state, exec_info
```

## Example Usage

### Basic Cost Attribution

```python
"""
Basic usage: Track costs per user.
"""
from scrapegraphai.graphs import SmartScraperGraph
from scrapegraphai.cost_management.attribution import (
    AttributionContext,
    inject_attribution_into_state
)

# Create graph configuration
graph_config = {
    "llm": {"model": "gpt-4o-mini"},
}

# Create graph
graph = SmartScraperGraph(
    prompt="Extract all product prices",
    source="https://example.com/products",
    config=graph_config,
    enable_cost_tracking=True,  # Enable cost tracking
)

# Create attribution context for user
attribution = AttributionContext(
    user_id="user-12345",
    project_id="project-67890",
    tags={"environment": "production"}
)

# Inject attribution into initial state
initial_state = inject_attribution_into_state(
    {"url": "https://example.com/products"},
    attribution
)

# Run graph - costs will be tracked per user
result, exec_info = graph.run(initial_state)

# Costs are now attributed to user-12345
print(f"Total cost: ${exec_info[-1]['total_cost_USD']:.4f}")
print(f"User: {exec_info[-1].get('user_id')}")
print(f"Project: {exec_info[-1].get('project_id')}")

# Query user's total costs
if graph.cost_tracker:
    user_summary = graph.cost_tracker.get_user_costs("user-12345")
    print(f"\nUser total costs: ${user_summary.total_cost_usd:.2f}")
    print(f"Total requests: {user_summary.request_count}")
    print(f"Model breakdown: {user_summary.model_breakdown}")
```

### Budget Enforcement

```python
"""
Budget enforcement: Prevent runaway costs.
"""
from scrapegraphai.graphs import SmartScraperGraph
from scrapegraphai.cost_management.attribution import AttributionContext, inject_attribution_into_state
from scrapegraphai.cost_management.budget import BudgetRule, BudgetPeriod, BudgetExceededError

# Create graph with budget enforcement
graph = SmartScraperGraph(
    prompt="Extract product data",
    source="https://example.com/products",
    config={"llm": {"model": "gpt-4o-mini"}},
    enable_cost_tracking=True,
)

# Set budget rule: $10/month for user
budget_rule = BudgetRule(
    entity_type="user",
    entity_id="user-12345",
    limit_usd=10.0,
    period=BudgetPeriod.MONTHLY,
    soft_limit_usd=8.0,  # Warning at $8
    alert_threshold=0.8,  # Alert at 80%
)

graph.budget_enforcer.add_budget_rule(budget_rule)

# Register alert callback
def on_budget_alert(rule, usage, utilization, message):
    print(f"⚠️  BUDGET ALERT: {message}")
    print(f"   User: {rule.entity_id}")
    print(f"   Usage: ${usage:.2f} / ${rule.limit_usd:.2f} ({utilization*100:.1f}%)")

graph.budget_enforcer.register_alert_callback(on_budget_alert)

# Create attribution
attribution = AttributionContext(user_id="user-12345")

# Try to run graph
try:
    initial_state = inject_attribution_into_state({}, attribution)
    result, exec_info = graph.run(initial_state)
    print("✓ Execution completed successfully")

except BudgetExceededError as e:
    print(f"✗ Budget exceeded: {e}")

    # Check budget status
    status = graph.budget_enforcer.get_budget_status("user", "user-12345")
    print(f"\nBudget Status:")
    print(f"  Limit: ${status['limit_usd']:.2f}")
    print(f"  Used: ${status['current_usage_usd']:.2f}")
    print(f"  Remaining: ${status['remaining_usd']:.2f}")
    print(f"  Utilization: {status['utilization']*100:.1f}%")
```

### Multi-Tenant SaaS Deployment

```python
"""
Multi-tenant SaaS: Track costs per tenant and user.
"""
from scrapegraphai.graphs import SmartScraperGraph
from scrapegraphai.cost_management.attribution import AttributionContext, inject_attribution_into_state
from scrapegraphai.cost_management.budget import BudgetRule, BudgetPeriod
from datetime import datetime, timedelta

# Initialize graph once (shared across requests)
graph = SmartScraperGraph(
    prompt="Extract data",
    source="",
    config={"llm": {"model": "gpt-4o-mini"}},
    enable_cost_tracking=True,
)

# Set tenant-level budgets
tenants = [
    ("tenant-acme", 1000.0),      # Acme Corp: $1000/month
    ("tenant-globex", 500.0),     # Globex Inc: $500/month
    ("tenant-initech", 2000.0),   # Initech: $2000/month
]

for tenant_id, limit in tenants:
    graph.budget_enforcer.add_budget_rule(
        BudgetRule(
            entity_type="tenant",
            entity_id=tenant_id,
            limit_usd=limit,
            period=BudgetPeriod.MONTHLY,
        )
    )

# Set user-level budgets
users = [
    ("user-alice", "tenant-acme", 50.0),
    ("user-bob", "tenant-acme", 100.0),
    ("user-charlie", "tenant-globex", 50.0),
]

for user_id, tenant_id, limit in users:
    graph.budget_enforcer.add_budget_rule(
        BudgetRule(
            entity_type="user",
            entity_id=user_id,
            limit_usd=limit,
            period=BudgetPeriod.MONTHLY,
        )
    )

# Handle incoming request from user
def handle_scraping_request(user_id: str, tenant_id: str, url: str, prompt: str):
    """Handle a scraping request with cost attribution."""

    # Create attribution context
    attribution = AttributionContext(
        user_id=user_id,
        tenant_id=tenant_id,
        tags={
            "api_version": "v1",
            "client_ip": "1.2.3.4",
        }
    )

    # Check budget before processing
    try:
        graph.budget_enforcer.check_budget_before_execution(attribution)
    except BudgetExceededError as e:
        return {
            "error": "Budget exceeded",
            "message": str(e),
            "status": 429,  # Too Many Requests
        }

    # Inject attribution and execute
    initial_state = inject_attribution_into_state(
        {"url": url, "user_prompt": prompt},
        attribution
    )

    try:
        result, exec_info = graph.run(initial_state)

        # Return result with cost information
        return {
            "success": True,
            "result": result,
            "cost_usd": exec_info[-1]['total_cost_USD'],
            "user_id": user_id,
            "tenant_id": tenant_id,
        }

    except Exception as e:
        return {
            "error": "Execution failed",
            "message": str(e),
            "status": 500,
        }

# Generate monthly invoice for tenant
def generate_tenant_invoice(tenant_id: str, month: int, year: int):
    """Generate cost breakdown invoice for a tenant."""

    # Calculate date range
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    # Get tenant costs
    tenant_summary = graph.cost_tracker.get_tenant_costs(
        tenant_id,
        start_date,
        end_date
    )

    # Get per-user breakdown for this tenant
    # (In production, you'd query all users for this tenant)

    invoice = {
        "tenant_id": tenant_id,
        "period": f"{year}-{month:02d}",
        "total_cost_usd": tenant_summary.total_cost_usd,
        "total_requests": tenant_summary.request_count,
        "total_tokens": tenant_summary.total_tokens,
        "model_breakdown": tenant_summary.model_breakdown,
    }

    return invoice

# Example: Process requests
print("Request 1: Alice from Acme")
result1 = handle_scraping_request(
    user_id="user-alice",
    tenant_id="tenant-acme",
    url="https://example.com/page1",
    prompt="Extract prices"
)
print(f"Cost: ${result1.get('cost_usd', 0):.4f}\n")

print("Request 2: Charlie from Globex")
result2 = handle_scraping_request(
    user_id="user-charlie",
    tenant_id="tenant-globex",
    url="https://example.com/page2",
    prompt="Extract products"
)
print(f"Cost: ${result2.get('cost_usd', 0):.4f}\n")

# Generate invoice
invoice = generate_tenant_invoice("tenant-acme", 11, 2025)
print(f"Acme Corp Invoice: ${invoice['total_cost_usd']:.2f}")
```

### Cost Reporting & Analytics

```python
"""
Cost reporting and analytics.
"""
from scrapegraphai.cost_management.tracker import CostTracker
from datetime import datetime, timedelta
import json

# Assume cost_tracker has historical data
cost_tracker = CostTracker()

# Get user costs for last 30 days
user_id = "user-12345"
end_date = datetime.utcnow()
start_date = end_date - timedelta(days=30)

summary = cost_tracker.get_user_costs(user_id, start_date, end_date)

print(f"User Cost Report: {user_id}")
print(f"Period: {start_date.date()} to {end_date.date()}")
print(f"=" * 50)
print(f"Total Cost: ${summary.total_cost_usd:.2f}")
print(f"Total Tokens: {summary.total_tokens:,}")
print(f"Total Requests: {summary.request_count}")
print(f"\nModel Breakdown:")
for model, cost in summary.model_breakdown.items():
    percentage = (cost / summary.total_cost_usd * 100) if summary.total_cost_usd > 0 else 0
    print(f"  {model}: ${cost:.2f} ({percentage:.1f}%)")

# Get daily breakdown
session_records = cost_tracker.get_session_costs(session_id="session-abc")
print(f"\nSession Details:")
for record in session_records:
    print(f"  {record.timestamp}: {record.node_name} - ${record.total_cost_usd:.4f}")

# Export to JSON for external reporting
report = {
    "user_id": user_id,
    "period": {
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
    },
    "summary": summary.to_dict(),
}

with open(f"cost_report_{user_id}.json", "w") as f:
    json.dump(report, f, indent=2)

print(f"\nReport exported to cost_report_{user_id}.json")
```

## Implementation Plan

### Phase 1: Foundation (Week 1-2)
**Goal:** Core cost attribution infrastructure

**Tasks:**
1. Create `scrapegraphai/cost_management/` package
   - `__init__.py`
   - `attribution.py` - AttributionContext class
   - `models.py` - CostRecord and CostSummary classes
   - `tracker.py` - CostTracker and InMemoryCostStorage
   - `budget.py` - BudgetRule and BudgetEnforcer

2. Implement AttributionContext
   - Data class with user_id, project_id, tenant_id
   - Validation logic
   - State injection/extraction helpers
   - Serialization methods

3. Implement CostTracker
   - In-memory storage backend
   - Per-entity cost tracking
   - Query methods (by user, project, tenant)
   - Thread-safe operations

4. Add unit tests
   - Test attribution context creation
   - Test cost tracking
   - Test storage operations
   - Test thread safety

**Success Criteria:**
- 90% test coverage for new modules
- All tests pass
- Documentation complete
- No dependencies on base_graph yet

### Phase 2: Budget Management (Week 3-4)
**Goal:** Budget enforcement and alerts

**Tasks:**
1. Implement BudgetRule
   - Budget period types
   - Validation logic
   - Date range calculation

2. Implement BudgetEnforcer
   - Pre-execution budget checks
   - Hard limit enforcement
   - Soft limit warnings
   - Alert callbacks
   - Budget status queries

3. Add budget tests
   - Test budget rule validation
   - Test enforcement logic
   - Test alert triggers
   - Test multi-entity budgets

4. Documentation
   - Budget configuration guide
   - Alert callback examples
   - Best practices

**Success Criteria:**
- Budget enforcement works correctly
- Alerts fire at thresholds
- Clear error messages
- 90% test coverage

### Phase 3: BaseGraph Integration (Week 5-6)
**Goal:** Integrate with graph execution

**Tasks:**
1. Modify BaseGraph class
   - Add cost_tracker and budget_enforcer parameters
   - Inject attribution context check
   - Pre-execution budget validation
   - Post-node cost tracking
   - Update exec_info with attribution

2. Update callback handlers
   - Extract attribution from state
   - Pass attribution to cost_tracker
   - Preserve attribution in cb_data

3. Update prettify_exec_info
   - Add attribution columns
   - Show per-entity breakdown
   - Display budget status

4. Integration tests
   - End-to-end cost tracking
   - Budget enforcement in graphs
   - Multi-node attribution
   - Error handling

**Success Criteria:**
- Backward compatible (all existing tests pass)
- Attribution flows through graph execution
- Costs tracked per entity
- Budget errors raised appropriately

### Phase 4: Storage Backends (Week 7-8)
**Goal:** Persistent storage options

**Tasks:**
1. Implement SQLite backend
   - Schema definition
   - CRUD operations
   - Migration script
   - Query optimization

2. Implement PostgreSQL backend (optional)
   - Connection pooling
   - Async queries
   - Indexes

3. Add storage backend tests
   - Test all CRUD operations
   - Test date range queries
   - Test concurrent access
   - Test migrations

4. Configuration management
   - Environment variables
   - Storage backend selection
   - Connection parameters

**Success Criteria:**
- SQLite backend fully functional
- Data persists across sessions
- Performance acceptable (<100ms queries)
- Migration path from in-memory

### Phase 5: Reporting & UI (Week 9-10)
**Goal:** Cost reporting and visualization

**Tasks:**
1. Enhanced reporting
   - Daily/weekly/monthly aggregations
   - Trend analysis
   - Cost forecasting
   - Export formats (JSON, CSV)

2. CLI commands
   - `scrapegraph costs user <user_id>`
   - `scrapegraph costs project <project_id>`
   - `scrapegraph budget set <entity> <limit>`
   - `scrapegraph budget status <entity>`

3. API endpoints (if web UI exists)
   - GET /api/costs/users/:id
   - GET /api/costs/projects/:id
   - POST /api/budgets
   - GET /api/budgets/:entity

4. Documentation
   - Complete user guide
   - API reference
   - Migration guide
   - Troubleshooting

**Success Criteria:**
- Comprehensive reporting available
- CLI tools functional
- Documentation complete
- User feedback positive

### Phase 6: Production Deployment (Week 11-12)
**Goal:** Production-ready deployment

**Tasks:**
1. Performance optimization
   - Query optimization
   - Index tuning
   - Caching strategy
   - Batch operations

2. Monitoring & Alerting
   - Metrics collection
   - Alert integrations (email, Slack, PagerDuty)
   - Dashboard setup
   - SLA monitoring

3. Security audit
   - Input validation
   - SQL injection prevention
   - Access control
   - Audit logging

4. Gradual rollout
   - Enable for test users
   - Monitor error rates
   - Gather feedback
   - Expand to production

**Success Criteria:**
- Production deployment complete
- No performance degradation
- Budget enforcement working
- Cost attribution accurate
- User feedback positive

## Backwards Compatibility

### Breaking Changes

**None.** This RFC is fully backward compatible.

### Compatibility Strategy

1. **Opt-in by Default (Phase 1-3):**
   ```python
   # Default: Cost tracking enabled but optional
   graph = SmartScraperGraph(
       prompt="...",
       source="...",
       config={},
       enable_cost_tracking=True,  # Enabled but doesn't require attribution
   )

   # Without attribution: Works as before
   result = graph.run()

   # With attribution: Enhanced tracking
   attribution = AttributionContext(user_id="user-123")
   state = inject_attribution_into_state({}, attribution)
   result = graph.run(state)
   ```

2. **Budget Enforcement Opt-in:**
   ```python
   # Budget enforcement requires explicit setup
   graph.budget_enforcer.add_budget_rule(budget_rule)
   # Until budget rules are added, no enforcement happens
   ```

3. **exec_info Backward Compatible:**
   ```python
   # Existing code continues to work
   result, exec_info = graph.run()

   # exec_info format unchanged:
   # - Still has node_name, total_cost_USD, etc.
   # - NEW fields added: user_id, project_id, tenant_id (optional)

   # Old code ignores new fields
   for info in exec_info:
       print(info['total_cost_USD'])  # Still works
   ```

4. **Storage Backend Configurable:**
   ```bash
   # Default: In-memory (no persistence, zero config)
   # Optional: Enable persistence
   export SCRAPEGRAPH_COST_STORAGE=sqlite
   export SCRAPEGRAPH_COST_DB_PATH=/path/to/costs.db
   ```

### API Stability

**Guaranteed Stable:**
- All existing BaseGraph methods
- exec_info structure (new fields are additive)
- Callback handler interfaces
- Graph configuration format

**New Optional APIs:**
- `enable_cost_tracking` parameter (default: True)
- `cost_tracker` parameter (default: None = auto-create)
- `budget_enforcer` parameter (default: None = auto-create)
- Attribution context in state (optional)

### Migration Path

**For Existing Users:**
1. No changes required
2. Costs tracked globally as before
3. Can gradually adopt attribution
4. Can add budget rules as needed

**For New Multi-Tenant Deployments:**
1. Enable cost tracking (default)
2. Inject attribution context
3. Set budget rules
4. Choose storage backend

## Performance Impact

### Expected Overhead

**Cost Tracking Overhead:**
- Per-node tracking: ~0.1-0.5ms per node
- Database write (async): ~1-5ms per record
- Memory overhead: ~200 bytes per cost record
- **Total impact: <1% execution time increase**

**Budget Checking Overhead:**
- Pre-execution check: ~1-10ms (depends on storage backend)
- In-memory: <1ms
- SQLite: 1-5ms
- PostgreSQL: 5-10ms
- **Total impact: Negligible for multi-second LLM calls**

### Benchmarking

```python
# Test: 100 graph executions with cost tracking
import time
from scrapegraphai.graphs import SmartScraperGraph
from scrapegraphai.cost_management.attribution import AttributionContext, inject_attribution_into_state

graph_config = {"llm": {"model": "gpt-4o-mini"}}

# Without cost tracking
graph_no_tracking = SmartScraperGraph(
    prompt="Extract data",
    source="https://example.com",
    config=graph_config,
    enable_cost_tracking=False,
)

start = time.time()
for i in range(100):
    graph_no_tracking.run()
time_without = time.time() - start

# With cost tracking
graph_with_tracking = SmartScraperGraph(
    prompt="Extract data",
    source="https://example.com",
    config=graph_config,
    enable_cost_tracking=True,
)

attribution = AttributionContext(user_id="test-user")
state = inject_attribution_into_state({}, attribution)

start = time.time()
for i in range(100):
    graph_with_tracking.run(state)
time_with = time.time() - start

overhead_pct = ((time_with - time_without) / time_without) * 100
print(f"Without tracking: {time_without:.2f}s")
print(f"With tracking: {time_with:.2f}s")
print(f"Overhead: {overhead_pct:.2f}%")

# Expected results:
# Without tracking: ~150s (100 * 1.5s avg)
# With tracking: ~151s
# Overhead: ~0.7%
```

### Storage Performance

**In-Memory Storage:**
- Writes: O(1) - instant
- Reads by entity: O(n) - linear scan
- Memory: O(n) - grows with records
- **Best for:** Development, testing, single-server deployments

**SQLite Storage:**
- Writes: ~1-5ms per record
- Reads by entity: ~1-10ms with indexes
- Memory: Minimal (disk-based)
- **Best for:** Production, single-server, moderate volume

**PostgreSQL Storage:**
- Writes: ~5-10ms per record
- Reads by entity: ~5-20ms with indexes
- Memory: Minimal (remote DB)
- **Best for:** Production, multi-server, high volume

### Scalability

**Single Server:**
- In-memory: 1M+ records easily
- SQLite: 10M+ records with good performance
- Overhead: Negligible

**Multi-Server (Distributed):**
- PostgreSQL: Shared cost tracking across servers
- Redis: Fast caching layer
- Horizontal scaling: Fully supported

## Alternatives Considered

### Alternative 1: No Cost Attribution (Status Quo)

**Description:** Continue with global cost aggregation only.

**Pros:**
- Simplest implementation
- No overhead
- No complexity

**Cons:**
- Cannot deploy as SaaS
- No budget enforcement
- No cost visibility
- No multi-tenant support
- Risk of runaway costs

**Why Not Chosen:** Blocking for SaaS deployments and cost control.

---

### Alternative 2: Post-hoc Cost Attribution

**Description:** Track costs globally, then attribute later based on logs.

**Pros:**
- No runtime overhead
- Simpler integration
- Can attribute retroactively

**Cons:**
- Cannot enforce budgets in real-time
- Risk of data loss
- Complex log correlation
- No hard limits possible
- Higher risk of cost overruns

**Why Not Chosen:** Cannot prevent runaway costs, only detect them after the fact.

---

### Alternative 3: External Cost Tracking Service

**Description:** Send cost data to external service (e.g., DataDog, New Relic).

**Pros:**
- Leverages existing infrastructure
- Professional dashboards
- Advanced analytics

**Cons:**
- Requires external dependency
- Additional costs
- Network latency
- Cannot enforce budgets locally
- Privacy concerns

**Why Not Chosen:** Adds external dependency and doesn't enable budget enforcement.

---

### Alternative 4: LLM Provider-Level Tracking

**Description:** Rely on OpenAI/Anthropic usage tracking.

**Pros:**
- Accurate billing data
- No implementation needed
- Provider-native

**Cons:**
- No real-time access
- No per-user attribution
- No budget enforcement
- Delayed data (hours/days)
- Doesn't work across providers

**Why Not Chosen:** Insufficient granularity and no enforcement capability.

---

### Alternative 5: Callback-Only Attribution

**Description:** Add attribution only to callbacks, not state.

**Pros:**
- Less invasive
- Simpler state management

**Cons:**
- Attribution not available in nodes
- Cannot check budget before LLM call
- Harder to propagate context
- Limited flexibility

**Why Not Chosen:** State propagation provides more flexibility and enables pre-execution checks.

---

### Decision Matrix

| Alternative | Real-time | Budget Enforcement | Multi-tenant | Complexity | Score |
|------------|-----------|-------------------|--------------|------------|-------|
| **State-based Attribution (Chosen)** | ✓ | ✓ | ✓ | Medium | **5/5** |
| Status Quo | ✓ | ✗ | ✗ | Low | 2/5 |
| Post-hoc Attribution | ✗ | ✗ | ✓ | Medium | 2/5 |
| External Service | ✓ | ✗ | ✓ | High | 3/5 |
| Provider Tracking | ✗ | ✗ | ✗ | Low | 1/5 |
| Callback-Only | ✓ | Partial | ✓ | Low | 3/5 |

## Security Considerations

### Threat Model

**Threat 1: Budget Bypass**

**Description:** Malicious user attempts to bypass budget limits.

**Attack Vectors:**
- Omit attribution context
- Forge user_id/tenant_id
- Race condition in budget checks

**Mitigation:**
```python
# Require attribution for sensitive operations
if not attribution:
    raise ValueError("Attribution required for execution")

# Validate attribution against authentication
if not validate_user_auth(attribution.user_id, auth_token):
    raise PermissionError("Invalid user_id")

# Atomic budget checks with locks
with budget_enforcer._lock:
    check_and_decrement_budget(attribution)
```

---

**Threat 2: Cost Data Exposure**

**Description:** Unauthorized access to cost data.

**Mitigation:**
- Access control on cost queries
- Tenant isolation in multi-tenant deployments
- Audit logging of cost data access
- Encryption at rest (for persistent storage)

```python
def get_user_costs(user_id: str, requesting_user_id: str):
    """Only allow users to see their own costs."""
    if user_id != requesting_user_id and not is_admin(requesting_user_id):
        raise PermissionError("Cannot access other user's costs")
    return cost_tracker.get_user_costs(user_id)
```

---

**Threat 3: SQL Injection (Persistent Storage)**

**Description:** SQL injection via user-controlled attribution fields.

**Mitigation:**
- Parameterized queries only
- Input validation on all IDs
- ORM usage (SQLAlchemy)
- Whitelisted characters

```python
# Good: Parameterized query
cursor.execute(
    "SELECT * FROM costs WHERE user_id = ?",
    (user_id,)
)

# Bad: String interpolation
# cursor.execute(f"SELECT * FROM costs WHERE user_id = '{user_id}'")
```

---

**Threat 4: Resource Exhaustion**

**Description:** Attacker creates many users/projects to exhaust storage.

**Mitigation:**
- Tenant-level limits on users/projects
- Storage quotas
- Automatic archival of old data
- Rate limiting on entity creation

---

### Privacy Considerations

**PII in Attribution Context:**
- user_id, project_id should be pseudonymous IDs
- Avoid storing email addresses or names in attribution
- Tags field can contain sensitive data - document carefully

**Data Retention:**
- Implement data retention policies
- Automatic purging of old cost records
- GDPR compliance for user data deletion

**Audit Trail:**
- Log all budget rule changes
- Log cost data access
- Retain audit logs separately from cost data

## Open Questions

### Question 1: Storage Backend Default

**Context:** Should we default to in-memory or persistent storage?

**Current Proposal:** In-memory by default

**Trade-offs:**
- In-memory: Zero config, fast, but data lost on restart
- SQLite: Persistent, minimal config, slightly slower
- PostgreSQL: Production-ready, requires setup

**Request for Input:** What's the best default for most users?

---

### Question 2: Budget Enforcement Timing

**Context:** When should we check budgets?

**Options:**
1. Before graph execution (current proposal)
2. Before each LLM call
3. After each LLM call
4. Combination of above

**Trade-offs:**
- Before graph: Fast fail, but coarse-grained
- Before each LLM call: Fine-grained, but more checks
- After each call: Accurate, but can overshoot

**Request for Input:** Best balance between accuracy and performance?

---

### Question 3: Attribution Inheritance

**Context:** Should child processes/threads inherit attribution?

**Scenario:**
```python
# Parent execution with attribution
attribution = AttributionContext(user_id="user-123")
graph.run(with_attribution(attribution))

# If graph spawns async tasks, should they inherit attribution?
```

**Options:**
1. Explicit passing only (current)
2. Thread-local context variables
3. Async context propagation

**Request for Input:** Is automatic inheritance needed?

---

### Question 4: Cost Estimation

**Context:** Should we estimate costs before execution?

**Current:** No cost estimation

**Proposed:**
- Estimate based on prompt length
- Estimate based on historical data
- Provide budget.check_with_estimate()

**Trade-offs:**
- Pros: Better budget planning, fewer overruns
- Cons: Estimates can be inaccurate, added complexity

**Request for Input:** Is cost estimation worth implementing?

---

### Question 5: Multi-Model Attribution

**Context:** How to attribute costs across multiple LLM providers?

**Scenario:**
```python
# Graph uses GPT-4 for generation, Claude for validation
# Both should be attributed to same user
```

**Current:** Attribution works across models

**Question:** Any special handling needed for multi-model scenarios?

---

### Question 6: Budget Rollover

**Context:** Should unused budget roll over to next period?

**Current:** No rollover

**Alternatives:**
- Allow rollover up to N%
- Banking system (accumulate credits)
- Use-it-or-lose-it (current)

**Request for Input:** What's the desired behavior?

---

### How to Provide Input

**For Community:**
- Comment on GitHub issue #[TBD]
- Discord #architecture channel
- Email team@scrapegraphai.com

**For Core Team:**
- RFC review meeting (Week of 2025-11-25)
- Async feedback via GitHub
- Vote on open questions

**Timeline:**
- RFC feedback period: 2 weeks
- Decisions finalized: Week of 2025-12-09
- Implementation starts: Week of 2025-12-16

## Success Metrics

### Primary Metrics

**Metric 1: Cost Attribution Accuracy**

**Definition:** Percentage of LLM costs correctly attributed to entities

**Target:** 100% of costs attributed when attribution context provided

**Measurement:**
```python
# Verify all costs are attributed
def test_attribution_accuracy():
    attribution = AttributionContext(user_id="test-user")
    state = inject_attribution_into_state({}, attribution)

    result, exec_info = graph.run(state)

    # Check all nodes have attribution
    for info in exec_info[:-1]:  # Exclude TOTAL
        assert info.get('user_id') == "test-user"
        assert info.get('total_cost_USD') >= 0

    # Check total matches sum
    node_total = sum(info['total_cost_USD'] for info in exec_info[:-1])
    assert abs(exec_info[-1]['total_cost_USD'] - node_total) < 0.01
```

---

**Metric 2: Budget Enforcement Success Rate**

**Definition:** Percentage of budget exceedances prevented before execution

**Target:** 100% of over-budget executions blocked

**Measurement:**
```python
# Set $1 budget, try to execute $2 worth of operations
def test_budget_enforcement():
    budget_rule = BudgetRule(
        entity_type="user",
        entity_id="test-user",
        limit_usd=1.0,
        period=BudgetPeriod.TOTAL,
    )
    graph.budget_enforcer.add_budget_rule(budget_rule)

    # First execution: Should succeed
    result1 = execute_graph_with_attribution()
    assert result1['success'] == True

    # Second execution: Should fail (budget exceeded)
    with pytest.raises(BudgetExceededError):
        execute_graph_with_attribution()

    # Verify costs stopped at limit
    summary = graph.cost_tracker.get_user_costs("test-user")
    assert summary.total_cost_usd <= 1.0
```

---

**Metric 3: Multi-Tenant Cost Isolation**

**Definition:** Zero cost leakage between tenants

**Target:** 100% cost isolation

**Measurement:**
```python
# Execute for two tenants, verify isolation
def test_tenant_isolation():
    tenant_a_costs = execute_for_tenant("tenant-a")
    tenant_b_costs = execute_for_tenant("tenant-b")

    # Get costs for each tenant
    summary_a = graph.cost_tracker.get_tenant_costs("tenant-a")
    summary_b = graph.cost_tracker.get_tenant_costs("tenant-b")

    # Verify no cost leakage
    assert summary_a.total_cost_usd == tenant_a_costs
    assert summary_b.total_cost_usd == tenant_b_costs
    assert summary_a.total_cost_usd != summary_b.total_cost_usd
```

---

### Secondary Metrics

**Metric 4: Performance Overhead**

**Definition:** Execution time increase due to cost tracking

**Target:** <2% overhead

**Measurement:**
```python
# Benchmark with/without cost tracking
avg_time_without = benchmark_executions(enable_cost_tracking=False)
avg_time_with = benchmark_executions(enable_cost_tracking=True)

overhead_pct = ((avg_time_with - avg_time_without) / avg_time_without) * 100
assert overhead_pct < 2.0
```

---

**Metric 5: Storage Performance**

**Definition:** Query response time for cost data

**Target:** <100ms for typical queries

**Measurement:**
```python
import time

# Simulate 10,000 cost records
populate_cost_data(num_records=10000)

# Measure query performance
start = time.time()
summary = cost_tracker.get_user_costs("user-123")
query_time_ms = (time.time() - start) * 1000

assert query_time_ms < 100  # Less than 100ms
```

---

**Metric 6: Budget Alert Accuracy**

**Definition:** Percentage of alerts triggered at correct thresholds

**Target:** 100% alerts triggered when threshold reached

**Measurement:**
```python
# Track alerts
alerts_received = []

def alert_callback(rule, usage, utilization, message):
    alerts_received.append((utilization, message))

graph.budget_enforcer.register_alert_callback(alert_callback)

# Set 80% threshold, spend to 85%
budget_rule = BudgetRule(
    entity_type="user",
    entity_id="test-user",
    limit_usd=10.0,
    alert_threshold=0.8,
)

# Execute until over threshold
execute_until_cost("test-user", target_cost=8.5)

# Verify alert was triggered
assert len(alerts_received) > 0
assert alerts_received[0][0] >= 0.8  # Utilization >= 80%
```

---

### Monitoring Dashboard

```
┌─────────────────────────────────────────────────────────────────────┐
│  ScrapeGraphAI Cost Attribution & Budget Metrics                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Attribution Accuracy:     [██████████] 100%                        │
│  Budget Enforcement:       [██████████] 100%                        │
│  Tenant Isolation:         [██████████] 100%                        │
│  Performance Overhead:     1.2% (target: <2%)                       │
│  Query Performance:        45ms avg (target: <100ms)                │
│  Alert Accuracy:           [██████████] 100%                        │
│                                                                      │
│  Live Stats:                                                         │
│  ├─ Active Users:          1,247                                    │
│  ├─ Active Projects:       438                                      │
│  ├─ Active Tenants:        52                                       │
│  ├─ Total Costs (today):   $1,284.32                                │
│  └─ Avg Cost/Request:      $0.042                                   │
│                                                                      │
│  Budget Alerts (Last 24h):                                          │
│  ⚠️  14:32 - user-12345: 85% of monthly budget used                 │
│  ⚠️  13:15 - project-abc: 90% of monthly budget used                │
│  🚫 12:48 - user-67890: Budget exceeded, execution blocked          │
│                                                                      │
│  Top Spenders (This Month):                                         │
│  1. tenant-acme:    $4,582.19 / $5,000.00 (91.6%)                   │
│  2. tenant-globex:  $1,234.56 / $2,000.00 (61.7%)                   │
│  3. project-x:      $892.40 / $1,000.00 (89.2%)                     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## References

### Code References

1. **BaseGraph Cost Tracking**
   - File: `/home/user/Scrapegraph-ai/scrapegraphai/graphs/base_graph.py`
   - Lines 246-252: Global `cb_total` aggregation
   - Lines 286-289: Cost aggregation logic
   - Lines 310-320: Execution info construction
   - Issue: No attribution context

2. **Callback Handlers**
   - File: `/home/user/Scrapegraph-ai/scrapegraphai/utils/custom_callback.py`
   - Lines 46-50: Token tracking variables
   - Lines 117-132: Cost calculation and update
   - Issue: No user_id, project_id, tenant_id fields

3. **LLM Callback Manager**
   - File: `/home/user/Scrapegraph-ai/scrapegraphai/utils/llm_callback_manager.py`
   - Lines 36-68: Exclusive callback acquisition
   - Issue: No attribution context propagation

4. **Cost Display**
   - File: `/home/user/Scrapegraph-ai/scrapegraphai/utils/prettify_exec_info.py`
   - Lines 30-49: Execution info formatting
   - Issue: No attribution columns

### External References

5. **Multi-Tenant SaaS Best Practices**
   - AWS Multi-Tenant SaaS Architecture: https://aws.amazon.com/blogs/apn/how-to-build-a-multi-tenant-saas-application/
   - Tenant isolation patterns
   - Cost allocation strategies

6. **LLM Cost Tracking**
   - OpenAI Usage Tracking: https://platform.openai.com/usage
   - Anthropic Console: https://console.anthropic.com/usage
   - Token counting methodologies

7. **Budget Enforcement Patterns**
   - Rate limiting algorithms
   - Pre-execution validation
   - Circuit breaker patterns

8. **Cost Attribution in Cloud**
   - AWS Cost Allocation Tags
   - GCP Labels for billing
   - Azure Resource Tags

### Related RFCs

9. **RFC-0004: Structured Logging**
   - Related: Cost events should be logged
   - Integration: Log budget violations, cost milestones

10. **RFC-0009: Webhook Event System**
    - Related: Budget alerts could use webhooks
    - Integration: Fire webhooks on budget events

### Academic References

11. **Multi-Tenant Database Design**
    - Shared schema vs. separate schema
    - Tenant isolation techniques
    - Query performance in multi-tenant systems

12. **Resource Metering in Cloud**
    - Usage metering architectures
    - Real-time vs. batch processing
    - Cost attribution algorithms

---

## Appendix: Complete Example

### A1: Full SaaS Implementation

```python
"""
Complete example: Multi-tenant SaaS deployment with cost attribution and budgets.
"""
from scrapegraphai.graphs import SmartScraperGraph
from scrapegraphai.cost_management.attribution import (
    AttributionContext,
    inject_attribution_into_state
)
from scrapegraphai.cost_management.budget import (
    BudgetRule,
    BudgetPeriod,
    BudgetExceededError
)
from scrapegraphai.cost_management.tracker import CostTracker
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ScrapeGraphSaaS:
    """
    Multi-tenant SaaS wrapper for ScrapeGraphAI with cost management.
    """

    def __init__(self, llm_config: Dict):
        """Initialize SaaS instance."""
        # Create shared cost tracker (use PostgreSQL in production)
        self.cost_tracker = CostTracker()

        # Create shared graph (reused across requests)
        self.graph = SmartScraperGraph(
            prompt="",  # Set per-request
            source="",  # Set per-request
            config=llm_config,
            enable_cost_tracking=True,
            cost_tracker=self.cost_tracker,
        )

        # Setup budget alerts
        self.graph.budget_enforcer.register_alert_callback(
            self._on_budget_alert
        )

        logger.info("SaaS instance initialized")

    def add_tenant(
        self,
        tenant_id: str,
        monthly_budget_usd: float,
    ):
        """
        Add a new tenant with budget.

        Args:
            tenant_id: Tenant identifier
            monthly_budget_usd: Monthly budget limit in USD
        """
        budget_rule = BudgetRule(
            entity_type="tenant",
            entity_id=tenant_id,
            limit_usd=monthly_budget_usd,
            period=BudgetPeriod.MONTHLY,
            soft_limit_usd=monthly_budget_usd * 0.8,  # Alert at 80%
            alert_threshold=0.75,
        )

        self.graph.budget_enforcer.add_budget_rule(budget_rule)
        logger.info(f"Added tenant {tenant_id} with ${monthly_budget_usd}/month budget")

    def add_user(
        self,
        user_id: str,
        tenant_id: str,
        monthly_budget_usd: float,
    ):
        """Add a new user with budget."""
        budget_rule = BudgetRule(
            entity_type="user",
            entity_id=user_id,
            limit_usd=monthly_budget_usd,
            period=BudgetPeriod.MONTHLY,
            soft_limit_usd=monthly_budget_usd * 0.9,
            alert_threshold=0.85,
        )

        self.graph.budget_enforcer.add_budget_rule(budget_rule)
        logger.info(f"Added user {user_id} (tenant: {tenant_id}) with ${monthly_budget_usd}/month budget")

    def execute_scraping(
        self,
        user_id: str,
        tenant_id: str,
        url: str,
        prompt: str,
        project_id: Optional[str] = None,
    ) -> Dict:
        """
        Execute scraping with full cost attribution and budget enforcement.

        Args:
            user_id: User initiating the request
            tenant_id: Tenant the user belongs to
            url: URL to scrape
            prompt: Scraping prompt
            project_id: Optional project identifier

        Returns:
            Dict with result and cost information
        """
        # Create attribution context
        attribution = AttributionContext(
            user_id=user_id,
            tenant_id=tenant_id,
            project_id=project_id,
            tags={
                "url": url,
                "prompt_length": str(len(prompt)),
            }
        )

        # Check budget before execution
        try:
            self.graph.budget_enforcer.check_budget_before_execution(attribution)
        except BudgetExceededError as e:
            logger.warning(f"Budget exceeded for user {user_id}: {e}")
            return {
                "success": False,
                "error": "budget_exceeded",
                "message": str(e),
                "budget_status": self._get_budget_statuses(user_id, tenant_id),
            }

        # Prepare state with attribution
        initial_state = inject_attribution_into_state(
            {
                "url": url,
                "user_prompt": prompt,
            },
            attribution
        )

        # Execute scraping
        try:
            result, exec_info = self.graph.run(initial_state)

            # Extract cost info
            total_info = exec_info[-1]
            cost_usd = total_info['total_cost_USD']

            logger.info(
                f"Scraping completed for user {user_id}: "
                f"${cost_usd:.4f}, {total_info['total_tokens']} tokens"
            )

            return {
                "success": True,
                "result": result,
                "cost_usd": cost_usd,
                "tokens": total_info['total_tokens'],
                "execution_time": total_info['exec_time'],
                "session_id": attribution.session_id,
                "budget_status": self._get_budget_statuses(user_id, tenant_id),
            }

        except Exception as e:
            logger.error(f"Scraping failed for user {user_id}: {e}")
            return {
                "success": False,
                "error": "execution_failed",
                "message": str(e),
            }

    def get_user_usage(self, user_id: str) -> Dict:
        """Get usage statistics for a user."""
        summary = self.cost_tracker.get_user_costs(user_id)
        budget_status = self.graph.budget_enforcer.get_budget_status("user", user_id)

        return {
            "user_id": user_id,
            "total_cost_usd": summary.total_cost_usd,
            "total_tokens": summary.total_tokens,
            "request_count": summary.request_count,
            "model_breakdown": summary.model_breakdown,
            "budget": budget_status,
        }

    def get_tenant_usage(self, tenant_id: str) -> Dict:
        """Get usage statistics for a tenant."""
        summary = self.cost_tracker.get_tenant_costs(tenant_id)
        budget_status = self.graph.budget_enforcer.get_budget_status("tenant", tenant_id)

        return {
            "tenant_id": tenant_id,
            "total_cost_usd": summary.total_cost_usd,
            "total_tokens": summary.total_tokens,
            "request_count": summary.request_count,
            "model_breakdown": summary.model_breakdown,
            "budget": budget_status,
        }

    def _get_budget_statuses(self, user_id: str, tenant_id: str) -> Dict:
        """Get budget statuses for user and tenant."""
        return {
            "user": self.graph.budget_enforcer.get_budget_status("user", user_id),
            "tenant": self.graph.budget_enforcer.get_budget_status("tenant", tenant_id),
        }

    def _on_budget_alert(
        self,
        rule,
        current_usage: float,
        utilization: float,
        message: str
    ):
        """Handle budget alerts."""
        logger.warning(
            f"BUDGET ALERT: {rule.entity_type} {rule.entity_id} - "
            f"{message} (${current_usage:.2f} / ${rule.limit_usd:.2f}, "
            f"{utilization*100:.1f}%)"
        )

        # In production: Send email, Slack notification, etc.
        # send_alert_notification(rule, current_usage, utilization, message)


# Example usage
if __name__ == "__main__":
    # Initialize SaaS instance
    saas = ScrapeGraphSaaS(llm_config={"llm": {"model": "gpt-4o-mini"}})

    # Setup tenants
    saas.add_tenant("tenant-acme", monthly_budget_usd=1000.0)
    saas.add_tenant("tenant-globex", monthly_budget_usd=500.0)

    # Setup users
    saas.add_user("user-alice", "tenant-acme", monthly_budget_usd=100.0)
    saas.add_user("user-bob", "tenant-acme", monthly_budget_usd=200.0)
    saas.add_user("user-charlie", "tenant-globex", monthly_budget_usd=50.0)

    # Execute scraping for Alice
    print("\n=== Alice's Request ===")
    result = saas.execute_scraping(
        user_id="user-alice",
        tenant_id="tenant-acme",
        url="https://example.com/products",
        prompt="Extract product names and prices",
        project_id="project-ecommerce"
    )

    if result["success"]:
        print(f"✓ Scraping completed")
        print(f"  Cost: ${result['cost_usd']:.4f}")
        print(f"  Tokens: {result['tokens']}")
        print(f"  User budget: {result['budget_status']['user']['utilization']*100:.1f}% used")
        print(f"  Tenant budget: {result['budget_status']['tenant']['utilization']*100:.1f}% used")
    else:
        print(f"✗ Scraping failed: {result.get('message')}")

    # Get user usage
    print("\n=== Alice's Usage ===")
    usage = saas.get_user_usage("user-alice")
    print(f"Total cost: ${usage['total_cost_usd']:.2f}")
    print(f"Requests: {usage['request_count']}")
    print(f"Budget remaining: ${usage['budget']['remaining_usd']:.2f}")

    # Get tenant usage
    print("\n=== Acme Corp Usage ===")
    tenant_usage = saas.get_tenant_usage("tenant-acme")
    print(f"Total cost: ${tenant_usage['total_cost_usd']:.2f}")
    print(f"Requests: {tenant_usage['request_count']}")
    print(f"Budget remaining: ${tenant_usage['budget']['remaining_usd']:.2f}")
```

---

**End of RFC-0012**

---

**Feedback and questions welcome!**

Please direct comments to the RFC discussion thread or reach out to the ScrapeGraphAI team on Discord.
