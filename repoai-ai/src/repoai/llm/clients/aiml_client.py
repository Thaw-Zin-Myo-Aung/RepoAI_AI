"""
DEPRECATED: Manual AIMLClient has been removed.

This module is no longer used. Please use `PydanticAIAdapter` with
`OpenAIChatModel` and `OpenAIProvider` instead, which handle HTTP
communication and structured outputs via pydantic-ai.

If you need role-based model selection, use `ModelRouter` to obtain the
model_id for the role, then construct the pydantic-ai model accordingly.
"""

raise ImportError(
    "repoai.llm.clients.aiml_client is deprecated and has been removed. "
    "Use repoai.llm.pydantic_ai_adapter.PydanticAIAdapter instead."
)
