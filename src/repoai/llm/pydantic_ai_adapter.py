"""
PydanticAIAdapter with agent creation support.
Methods to get models and settings for custom agent creation.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.settings import ModelSettings

from repoai.config.settings import get_settings
from repoai.utils.logger import get_logger

from .model_registry import ModelSpec
from .model_roles import ModelRole
from .router import ModelRouter

if TYPE_CHECKING:
    from pydantic_ai.usage import RunUsage

logger = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)


@dataclass
class AgentRunMetadata:
    """
    Metadata from an agent run for explainability and logging.
    """

    agent_name: str
    model_used: str
    role: ModelRole
    timestamp: datetime
    duration_ms: float
    usage: RunUsage | None = None
    fallback_attempts: int = 0
    success: bool = True
    error_message: str | None = None


class PydanticAIAdapter:
    """
    PydanticAIAdapter for agent creation and execution.
    Provides:
    - Model retrieval for custom agent creation
    - Structured and unstructured completions with fallback
    - Streaming support
    - Usage tracking integration
    - Metadata capture for explainability

    Example:
        # Get model for custom agent
        adapter = PydanticAIAdapter()
        model = adapter.get_model(ModelRole.INTAKE)

        # Create custom agent
        agent = Agent(
            model=model,
            deps_type=MyDeps,
            output_type=MyOutput,
            system_prompt="..."
        )

        # Or use built-in completion methods
        result = await adapter.run_json_async(
            ModelRole.PLANNER,
            PlanSchema,
            messages=[{"content": "Create a plan"}]
        )
    """

    def __init__(self, router: ModelRouter | None = None):
        self.router = router or ModelRouter()
        logger.debug("PydanticAIAdapter initialized with ModelRouter.")

    # ---------------------------------------------------------------
    # Model Retrieval for Custom Agent Creation
    # ---------------------------------------------------------------

    def get_model(self, role: ModelRole) -> GoogleModel:
        """
        Get Configured Gemini model for a role without creating an agent.

        Args:
            role: Model role (INTAKE, PLANNER, CODER, etc.)

        Returns:
            GoogleModel: Configured Gemini model instance

        Example:
            model = adapter.get_model(ModelRole.INTAKE)
            agent = Agent(
                model=model,
                deps_type=RepoAIDependencies,
                output_type=JobSpec,
                system_prompt="You are an intake agent..."
            )
        """
        spec = self.router.choose(role)
        logger.debug(f"Retrieved model for role {role.value}: {spec.model_id}")

        # Set GOOGLE_API_KEY in environment
        import os

        os.environ["GOOGLE_API_KEY"] = get_settings().GOOGLE_API_KEY
        return GoogleModel(spec.model_id)

    def get_models_with_fallback(self, role: ModelRole) -> list[GoogleModel]:
        """
        Get all Gemini models for a role, in priority order.
        Useful for implementing manual fallback in agent creation.

        Args:
            role: Model role

        Returns:
            list[GoogleModel]: List of Gemini models in fallback order
        """
        import os

        os.environ["GOOGLE_API_KEY"] = get_settings().GOOGLE_API_KEY

        models: list[GoogleModel] = []
        for client in self.router.clients(role):
            models.append(GoogleModel(client.model_id))

        logger.debug(
            f"Retrieved {len(models)} models for role {role.value}."
            f"{[str(model) for model in models]}"
        )
        return models

    def get_model_ids_with_fallback(self, role: ModelRole) -> list[str]:
        """
        Get model IDs for a role in fallback order (primary + fallbacks).

        Args:
            role: Model role

        Returns:
            list[str]: List of model ID strings in priority order

        Example:
            model_ids = adapter.get_model_ids_with_fallback(ModelRole.INTAKE)
            # Returns: ['deepseek/deepseek-chat-v3.1', 'alibaba/qwen-max', ...]
        """
        model_ids = [client.model_id for client in self.router.clients(role)]
        logger.debug(f"Retrieved {len(model_ids)} model IDs for role {role.value}: {model_ids}")
        return model_ids

    def get_model_settings(self, role: ModelRole) -> ModelSettings:
        """
        Get default model settings (temperature, max_tokens) for a role.

        Args:
            role: Model role

        Returns:
            ModelSettings: Settings TypedDict with 'temperature' and 'max_tokens'

        Example:
            settings = adapter.get_model_settings(ModelRole.CODER)
            agent = Agent(model=model, model_settings=settings, ...)
        """
        client = self.router.choose(role)
        spec = client.spec
        settings: ModelSettings = {
            "temperature": spec.temperature,
            "max_tokens": spec.max_output_tokens,
        }

        logger.debug(
            f"Retrieved settings for role {role.value}: "
            f"temp={settings['temperature']}, max_tokens={settings['max_tokens']}"
        )
        return settings

    def get_spec(self, role: ModelRole) -> ModelSpec:
        """
        Get full ModelSpec for a role.

        Args:
            role: Model role

        Returns:
            ModelSpec: Complete model specification
        """
        return self.router.choose(role)._bound.spec

    # ---------------------------------------------------------------
    # Internal Agent Creation (Legacy Completion Methods)
    # ---------------------------------------------------------------

    def _agent(self, role: ModelRole, schema: type[BaseModel] | None = None) -> Agent:
        import os

        os.environ["GOOGLE_API_KEY"] = get_settings().GOOGLE_API_KEY

        spec = self.router.choose(role)
        model = GoogleModel(spec.model_id)
        # Create agent with or without structured output type
        if schema:
            return Agent(model, deps_type=None, output_type=schema)  # type: ignore
        return Agent(model)

    def _agents_with_fallback(
        self, role: ModelRole, schema: type[BaseModel] | None = None
    ) -> list[tuple[Agent, str]]:
        """
        Create agents for all models configured for the role, in priority order.

        Returns:
            list of tuples: (Agent, model_id_string)
        """
        import os

        os.environ["GOOGLE_API_KEY"] = get_settings().GOOGLE_API_KEY

        agents = []
        for client in self.router.clients(role):
            model = GoogleModel(client.model_id)
            if schema:
                agent = Agent(model, deps_type=None, output_type=schema)  # type: ignore
            else:
                agent = Agent(model)
            agents.append((agent, client.model_id))
        return agents

    # ---------------------------------------------------------------
    # Structured Completions
    # ---------------------------------------------------------------

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
        """
        Run structured JSON completion with Pydantic validation.

        Args:
            role: Model role for selection
            schema: Pydantic model class for output validation
            messages: List of message dicts with "content" key
            temperature: Sampling temperature
            max_output_tokens: Maximum tokens in response
            use_fallback: If True, retry with fallback models on failure

        Returns:
            Instance of schema class with validated output
        """
        prompt = "\n".join(msg["content"] for msg in messages)

        logger.info(
            f"Starting JSON completion: role= {role.value}, "
            f"Schema= {schema.__name__}, use_fallback= {use_fallback}"
        )

        if not use_fallback:
            agent = self._agent(role, schema)
            spec = self.router.choose(role).spec
            logger.info(f"Using primary model: {spec.model_id}")

            start_time = time.time()
            result = await agent.run(
                prompt, model_settings={"temperature": temperature, "max_tokens": max_output_tokens}
            )
            duration = (time.time() - start_time) * 1000
            logger.info(
                f"Completed JSON completion with primary model in {duration:.2f} ms."
                f" Model: {spec.model_id}"
            )
            return result.output  # type: ignore[return-value]

        # Fallback: try each model in order until one succeeds
        agents = self._agents_with_fallback(role, schema)
        last_exception: Exception | None = None

        for i, (agent, model_id) in enumerate(agents):
            try:
                logger.info(
                    f"Attempting JSON completion {i+1}/{len(agents)}: "
                    f"Model: {model_id}, role: {role.value}"
                )
                start_time = time.time()
                result = await agent.run(
                    prompt,
                    model_settings={"temperature": temperature, "max_tokens": max_output_tokens},
                )
                duration = (time.time() - start_time) * 1000
                logger.info(f"JSON completion succeeded on attempt {i+1}: " f"{duration:.2f} ms")
                return result.output  # type: ignore[return-value]

            except Exception as e:
                last_exception = e
                logger.warning(f"Model {model_id} failed (attempt {i+1}/{len(agents)}): {e}")
                if i < len(agents) - 1:
                    logger.info("Trying fallback model...")
                continue
        # All models failed
        if last_exception:
            raise last_exception
        raise RuntimeError(f"No models available for role: {role}")

    # -----------------------------------------------
    # Unstructured Completions
    # -----------------------------------------------

    async def run_raw_async(
        self,
        role: ModelRole,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_output_tokens: int = 2048,
        use_fallback: bool = True,
    ) -> str:
        """
        Run unstructured text completion.

        Args:
            role: Model role for selection
            messages: List of message dicts with "content" key
            temperature: Sampling temperature
            max_output_tokens: Maximum tokens in response
            use_fallback: If True, retry with fallback models on failure

        Returns:
            str: Raw text response from model
        """
        prompt = "\n".join(msg["content"] for msg in messages)
        logger.info(f"Starting raw completion: role={role.value}, fallback={use_fallback}")

        if not use_fallback:
            agent = self._agent(role)
            spec = self.router.choose(role).spec
            logger.info(f"Using primary model: {spec.model_id}")

            start_time = time.time()
            result = await agent.run(
                prompt, model_settings={"temperature": temperature, "max_tokens": max_output_tokens}
            )
            duration = (time.time() - start_time) * 1000
            logger.info(
                f"Raw completion succeeded: {duration:.2f} ms. "
                f"output length={len(result.output)} "
            )
            return result.output

        # Fallback: try each model in order until one succeeds
        agents = self._agents_with_fallback(role)
        last_exception: Exception | None = None

        for i, (agent, model_id) in enumerate(agents):
            try:
                logger.info(f"Attempting raw completion {i+1}/{len(agents)}: model={model_id}")

                start_time = time.time()
                result = await agent.run(
                    prompt,
                    model_settings={"temperature": temperature, "max_tokens": max_output_tokens},
                )
                duration = (time.time() - start_time) * 1000

                logger.info(
                    f"Raw completion succeeded on attempt {i+1}: "
                    f"{duration:.2f} ms, output length={len(result.output)}"
                )
                return result.output

            except Exception as e:
                last_exception = e
                logger.warning(f"Model {model_id} failed: {e}")
                if i < len(agents) - 1:
                    logger.info("Trying fallback model...")
                continue

        logger.error(f"All models failed for role {role.value}.")
        if last_exception:
            raise last_exception
        raise RuntimeError(f"No models available for role: {role}")

    # -----------------------------------------------
    # Raw Streaming Completions
    # -----------------------------------------------

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
        Stream unstructured text completion.

        Args:
            role: Model role for selection
            messages: List of message dicts with "content" key
            temperature: Sampling temperature
            max_output_tokens: Maximum tokens in response
            use_fallback: If True, retry with fallback models on failure

        Yields:
            AsyncIterator[str]: Async iterator yielding text chunks
        """
        prompt = "\n".join(msg["content"] for msg in messages)
        logger.info(f"Starting raw streaming completion: role={role.value}")

        if not use_fallback:
            agent = self._agent(role)
            spec = self.router.choose(role).spec
            logger.debug(f"Using primary model: {spec.model_id}")

            async with agent.run_stream(
                prompt,
                model_settings={"temperature": temperature, "max_tokens": max_output_tokens},
            ) as stream:
                async for chunk in stream.stream_text(delta=True):
                    yield chunk

            logger.info("Streaming completed successfully")
            return

        # Fallback: try each model
        agents = self._agents_with_fallback(role)
        last_exception: Exception | None = None

        for i, (agent, model_id) in enumerate(agents):
            try:
                logger.info(f"Attempting streaming {i+1}/{len(agents)}: model={model_id}")

                async with agent.run_stream(
                    prompt,
                    model_settings={"temperature": temperature, "max_tokens": max_output_tokens},
                ) as stream:
                    async for chunk in stream.stream_text(delta=True):
                        yield chunk

                logger.info(f"Streaming succeeded on attempt {i+1}")
                return

            except Exception as e:
                last_exception = e
                logger.warning(f"Streaming failed with model {model_id}: {e}")
                if i < len(agents) - 1:
                    logger.info("Trying fallback model for streaming...")
                continue

        logger.error("All models failed for streaming")
        if last_exception:
            raise last_exception
        raise RuntimeError(f"No models available for streaming role: {role}")

    # ---------------------------------------------------------------
    # Sync Wrappers
    # ---------------------------------------------------------------
    def run_raw(
        self,
        role: ModelRole,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_output_tokens: int = 2048,
    ) -> str:
        """Sync wrapper for run_raw_async."""
        logger.debug("Running raw completion (sync wrapper)")
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
        """Sync wrapper for run_json_async."""
        logger.debug(f"Running JSON completion (sync wrapper): schema={schema.__name__}")
        return asyncio.run(
            self.run_json_async(
                role, schema, messages, temperature=temperature, max_output_tokens=max_output_tokens
            )
        )
