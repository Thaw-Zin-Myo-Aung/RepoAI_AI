from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from typing import TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles import ModelProfile
from pydantic_ai.providers.openai import OpenAIProvider

from .model_roles import ModelRole
from .router import ModelRouter

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

# AIMLAPI via OpenAI-compatible provider
AIML_PROVIDER = OpenAIProvider(
    base_url="https://api.aimlapi.com/v1", api_key=os.getenv("AIMLAPI_API_KEY")
)

# Profile for AIMLAPI - uses 'prompted' mode to avoid "strict" parameter which AIMLAPI doesn't support
# This adds a prompt asking for JSON output instead of using OpenAI's native structured output with tools
AIML_PROFILE = ModelProfile(default_structured_output_mode="prompted")


class PydanticAIAdapter:
    """
    Provides high-level AI output validation via `pydantic-ai.Agent`.
    Supports both structured and unstructured outputs, sync and async calls.
    """

    def __init__(self, router: ModelRouter | None = None):
        self.router = router or ModelRouter()

    def _agent(self, role: ModelRole, schema: type[BaseModel] | None = None) -> Agent:
        spec = self.router.choose(role)
        model = OpenAIChatModel(spec.model_id, provider=AIML_PROVIDER, profile=AIML_PROFILE)
        # Create agent with or without structured output type
        if schema:
            return Agent(model, deps_type=None, output_type=schema)  # type: ignore
        return Agent(model)

    # -------------------------------
    # Structured Completions
    # -------------------------------
    async def run_json_async(
        self,
        role: ModelRole,
        schema: type[T],
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_output_tokens: int = 2048,
    ) -> T:
        prompt = "\n".join(msg["content"] for msg in messages)
        agent = self._agent(role, schema)

        logger.info(f"Running async JSON completion with model: {agent.model}, role: {role.name}")
        result = await agent.run(
            prompt, model_settings={"temperature": temperature, "max_tokens": max_output_tokens}
        )
        # result.output contains the validated Pydantic model instance when output_type is set
        return result.output  # type: ignore[return-value]

    # -------------------------------
    # Unstructured Completions
    # -------------------------------
    async def run_raw_async(
        self,
        role: ModelRole,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_output_tokens: int = 2048,
    ) -> str:
        prompt = "\n".join(msg["content"] for msg in messages)
        agent = self._agent(role)

        logger.info(f"Running async raw completion with model: {agent.model}, role: {role.name}")
        result = await agent.run(
            prompt, model_settings={"temperature": temperature, "max_tokens": max_output_tokens}
        )
        return result.output

    # -------------------------------
    # Raw Streaming Completions
    # -------------------------------
    async def stream_raw_async(
        self,
        role: ModelRole,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_output_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        prompt = "\n".join(msg["content"] for msg in messages)
        agent = self._agent(role)

        logger.info(
            f"Running async raw streaming completion with model: {agent.model}, role: {role.name}"
        )
        async with agent.run_stream(
            prompt,
            model_settings={"temperature": temperature, "max_tokens": max_output_tokens},
        ) as stream:
            async for chunk in stream.stream_text(delta=True):
                yield chunk

    # -------------------------------
    # Sync Wrappers
    # -------------------------------
    def run_raw(
        self,
        role: ModelRole,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_output_tokens: int = 2048,
    ) -> str:
        """Sync wrapper for run_raw_async. Note: Cannot be used in Jupyter - use await run_raw_async() instead."""
        return asyncio.run(
            self.run_raw_async(
                role, messages, temperature=temperature, max_output_tokens=max_output_tokens
            )
        )

    def run_json(
        self,
        role: ModelRole,
        schema: type[T],
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_output_tokens: int = 2048,
    ) -> T:
        """Sync wrapper for run_json_async. Note: Cannot be used in Jupyter - use await run_json_async() instead."""
        return asyncio.run(
            self.run_json_async(
                role, schema, messages, temperature=temperature, max_output_tokens=max_output_tokens
            )
        )
