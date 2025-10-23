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

    def _agents_with_fallback(
        self, role: ModelRole, schema: type[BaseModel] | None = None
    ) -> list[Agent]:
        """Create agents for all models configured for the role, in priority order."""
        agents = []
        for client in self.router.clients(role):
            model = OpenAIChatModel(client.model_id, provider=AIML_PROVIDER, profile=AIML_PROFILE)
            if schema:
                agents.append(Agent(model, deps_type=None, output_type=schema))  # type: ignore
            else:
                agents.append(Agent(model))
        return agents

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
        use_fallback: bool = True,
    ) -> T:
        prompt = "\n".join(msg["content"] for msg in messages)

        if not use_fallback:
            # Simple: use primary model only
            agent = self._agent(role, schema)
            logger.info(
                f"Running async JSON completion with model: {agent.model}, role: {role.name}"
            )
            result = await agent.run(
                prompt, model_settings={"temperature": temperature, "max_tokens": max_output_tokens}
            )
            return result.output  # type: ignore[return-value]

        # Fallback: try each model in order until one succeeds
        agents = self._agents_with_fallback(role, schema)
        last_exception: Exception | None = None

        for i, agent in enumerate(agents):
            try:
                logger.info(
                    f"Attempting JSON completion with model {i+1}/{len(agents)}: {agent.model}, role: {role.name}"
                )
                result = await agent.run(
                    prompt,
                    model_settings={"temperature": temperature, "max_tokens": max_output_tokens},
                )
                return result.output  # type: ignore[return-value]
            except Exception as e:
                last_exception = e
                logger.warning(f"Model {agent.model} failed: {e}")
                if i < len(agents) - 1:
                    logger.info("Trying fallback model...")
                continue

        # All models failed
        if last_exception:
            raise last_exception
        raise RuntimeError(f"No models available for role: {role}")

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
        use_fallback: bool = True,
    ) -> str:
        prompt = "\n".join(msg["content"] for msg in messages)

        if not use_fallback:
            # Simple: use primary model only
            agent = self._agent(role)
            logger.info(
                f"Running async raw completion with model: {agent.model}, role: {role.name}"
            )
            result = await agent.run(
                prompt, model_settings={"temperature": temperature, "max_tokens": max_output_tokens}
            )
            return result.output

        # Fallback: try each model in order until one succeeds
        agents = self._agents_with_fallback(role)
        last_exception: Exception | None = None

        for i, agent in enumerate(agents):
            try:
                logger.info(
                    f"Attempting raw completion with model {i+1}/{len(agents)}: {agent.model}, role: {role.name}"
                )
                result = await agent.run(
                    prompt,
                    model_settings={"temperature": temperature, "max_tokens": max_output_tokens},
                )
                return result.output
            except Exception as e:
                last_exception = e
                logger.warning(f"Model {agent.model} failed: {e}")
                if i < len(agents) - 1:
                    logger.info("Trying fallback model...")
                continue

        # All models failed
        if last_exception:
            raise last_exception
        raise RuntimeError(f"No models available for role: {role}")

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
        use_fallback: bool = True,
    ) -> AsyncIterator[str]:
        """
        Stream unstructured text completion asynchronously.

        Yields text chunks as they arrive. If use_fallback is True (default),
        will try each model in priority order until one successfully streams.

        Args:
            role: Model role for selection
            messages: List of message dicts with "content" key
            temperature: Sampling temperature
            max_output_tokens: Maximum tokens in response
            use_fallback: If True, retry with fallback models on failure

        Yields:
            str: Text chunks from the streaming response
        """
        prompt = "\n".join(msg["content"] for msg in messages)

        if not use_fallback:
            # Simple: use primary model only
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
            return

        # Fallback: try each model in order until one succeeds
        agents = self._agents_with_fallback(role)
        last_exception: Exception | None = None

        for i, agent in enumerate(agents):
            try:
                logger.info(
                    f"Attempting streaming completion with model {i+1}/{len(agents)}: {agent.model}, role: {role.name}"
                )
                async with agent.run_stream(
                    prompt,
                    model_settings={"temperature": temperature, "max_tokens": max_output_tokens},
                ) as stream:
                    async for chunk in stream.stream_text(delta=True):
                        yield chunk
                return  # Successfully streamed
            except Exception as e:
                last_exception = e
                logger.warning(f"Model {agent.model} failed during streaming: {e}")
                if i < len(agents) - 1:
                    logger.info("Trying fallback model for streaming...")
                continue

        # All models failed
        if last_exception:
            raise last_exception
        raise RuntimeError(f"No models available for streaming role: {role}")

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
