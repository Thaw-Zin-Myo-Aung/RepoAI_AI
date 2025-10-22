from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .clients.aiml_client import AIMLClient
from .model_registry import ModelSpec, load_defaults_from_env
from .model_roles import ModelRole


@dataclass(frozen=True)
class _Boundspec:
    spec: ModelSpec
    client: AIMLClient


class ModelClient:
    """Modeel bound to a concrete AIML model_id with sensible defaults."""

    def __init__(self, bound: _Boundspec) -> None:
        self._bound = bound

    @property
    def model_id(self) -> str:
        return self._bound.spec.model_id

    @property
    def provider(self) -> str:
        return self._bound.spec.provider

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        json_mode: bool | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        s = self._bound.spec
        return self._bound.client.chat(
            model_id=s.model_id,
            messages=messages,
            temperature=s.temperature if temperature is None else temperature,
            max_output_tokens=(
                s.max_output_tokens if max_output_tokens is None else max_output_tokens
            ),
            json_mode=s.json_mode if json_mode is None else json_mode,
            **extra,
        )


class ModelRouter:
    """
    Role-based model selection with ordered fallbacks.
    Usage:

        router = ModelRouter()

        out = router.chat_with_fallback(ModelRole.PLANNER, messages)

        #or:
        client = router.choose(ModelRole.CODER)
        out = client.chat(messages, temperature=0.1)
    """

    def __init__(
        self,
        aiml_client: AIMLClient | None = None,
        table: Mapping[ModelRole, list[ModelSpec]] | None = None,
    ) -> None:
        self._aiml = aiml_client or AIMLClient()
        self._table: Mapping[ModelRole, list[ModelSpec]] = table or load_defaults_from_env()

    # Binding Helpers
    def _bind(self, spec: ModelSpec) -> ModelClient:
        return ModelClient(_Boundspec(spec=spec, client=self._aiml))

    def _specs(self, role: ModelRole) -> list[ModelSpec]:
        specs = self._table.get(role, [])
        if not specs:
            raise ValueError(f"No model specs configured for role: {role}")
        return specs

    # Public API
    def choose(self, role: ModelRole) -> ModelClient:
        "Return the primary model client for the given role."
        return self._bind(self._specs(role)[0])

    def fallbacks(self, role: ModelRole) -> Iterable[ModelClient]:
        "Return all model clients for the given role, in order of preference."
        return (self._bind(spec) for spec in self._specs(role)[1:])

    def clients(self, role: ModelRole) -> Iterable[ModelClient]:
        "Return all model clients for the given role, in order of preference."
        return (self._bind(spec) for spec in self._specs(role))

    def chat_with_fallback(
        self,
        role: ModelRole,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        json_mode: bool | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """
        Try each model in order until one succeeds.
        Raises the last exception if all models fail.
        """
        last_exception: Exception | None = None
        for client in self.clients(role):
            try:
                return client.chat(
                    messages,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    json_mode=json_mode,
                    **extra,
                )
            except Exception as e:
                last_exception = e
                continue

        if last_exception is not None:
            raise last_exception
        raise RuntimeError("No models available for role: {role}")
