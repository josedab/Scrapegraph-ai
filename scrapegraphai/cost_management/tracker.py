"""
Cost tracking service for attribution.
"""
from typing import Dict, List, Optional
from datetime import datetime
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
