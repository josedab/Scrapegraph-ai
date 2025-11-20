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
        execution_time: Execution time in seconds
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
        start_date: Start of date range for this summary
        end_date: End of date range for this summary
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
