from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .model_registry import ModelSpec, load_defaults_from_env
from .model_roles import ModelRole


@dataclass(frozen=True)
class _Boundspec:
    """Internal binding of a model spec.

    Previously also included a concrete HTTP client (AIMLClient) used for
    direct chat calls. Now we only bind the spec since pydantic-ai providers
    handle all HTTP interactions.
    """

    spec: ModelSpec


class ModelClient:
    """Model bound to a concrete model_id with sensible defaults.

    This wrapper exposes metadata (model_id, provider) and can be extended
    if we later want to attach additional per-model configuration. Direct HTTP
    chat functionality was removed in favor of pydantic-ai providers.
    """

    def __init__(self, bound: _Boundspec) -> None:
        self._bound = bound

    @property
    def model_id(self) -> str:
        return self._bound.spec.model_id

    @property
    def provider(self) -> str:
        return self._bound.spec.provider


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
        table: Mapping[ModelRole, list[ModelSpec]] | None = None,
    ) -> None:
        # Routing data (role -> ordered list of model specs)
        self._table: Mapping[ModelRole, list[ModelSpec]] = table or load_defaults_from_env()

    # Binding Helpers
    def _bind(self, spec: ModelSpec) -> ModelClient:
        return ModelClient(_Boundspec(spec=spec))

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

    # Direct chat with fallback was removed as pydantic-ai now handles
    # model communication. Use PydanticAIAdapter with ModelRouter instead.
