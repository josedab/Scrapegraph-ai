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
