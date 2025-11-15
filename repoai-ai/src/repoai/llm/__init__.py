"""
LLM infrastructure for RepoAI.

Provides model routing, role-based selection, and Pydantic AI integration.
"""

from .model_registry import ModelSpec, load_defaults_from_env
from .model_roles import ModelRole
from .pydantic_ai_adapter import AgentRunMetadata, PydanticAIAdapter
from .router import ModelClient, ModelRouter

# UsageTracker - Skip for MVP, add later in production phase
# from .usage_tracker import UsageTracker

__all__ = [
    "ModelRole",
    "ModelSpec",
    "load_defaults_from_env",
    "ModelRouter",
    "ModelClient",
    "PydanticAIAdapter",
    "AgentRunMetadata",
]
