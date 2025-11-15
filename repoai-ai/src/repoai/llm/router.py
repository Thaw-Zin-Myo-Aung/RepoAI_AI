"""
ModelRouter with logging support.
Role-based model selction with ordered fallbacks
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from repoai.utils.logger import get_logger

from .model_registry import ModelSpec, load_defaults_from_env
from .model_roles import ModelRole

logger = get_logger(__name__)


@dataclass(frozen=True)
class _Boundspec:
    """Internal Binding of a model spec."""

    spec: ModelSpec


class ModelClient:
    """
    Model bound to a concrete model_id with sensible defaults.
    Exposes metadata (model_id, provider).
    """

    def __init__(self, bound: _Boundspec) -> None:
        self._bound = bound

    @property
    def model_id(self) -> str:
        """Get the model identifier."""
        return self._bound.spec.model_id

    @property
    def provider(self) -> str:
        """Get the model provider name."""
        return self._bound.spec.provider

    @property
    def spec(self) -> ModelSpec:
        """Get the underlying ModelSpec."""
        return self._bound.spec

    def __repr__(self) -> str:
        return f"ModelClient(model_id={self.model_id}, provider={self.provider})"


class ModelRouter:
    """
    Role-based model selction with ordered fallbacks.
    Automatically loads model config freom .env or uses sensible defaults.

    Usage:

        router = ModelRouter()

        # Get primary model
        primary = router.choose(ModelRole.PLANNER)
        print(primary.model_id) # e.g. "deepseek/deepseek-reasoner-v3.1"

        # Get all models (In priority order)
        for client in router.clients(ModelRole.CODER):
            print(client.model_id)
    """

    def __init__(
        self,
        table: Mapping[ModelRole, list[ModelSpec]] | None = None,
    ) -> None:
        """
        Initialize ModelRouter with model configurations.

        Args:
            table: Optional mapping of ModelRole to list of ModelSpec.
                   If None, loads defaults from environment variables.
        """

        self._table: Mapping[ModelRole, list[ModelSpec]] = table or load_defaults_from_env()

        logger.info("ModelRouter Initialized.")
        for role, specs in self._table.items():
            model_ids = [spec.model_id for spec in specs]
            logger.debug(
                f"Role {role.value}: {len(specs)} models configured - {model_ids}"
                f"primary: {model_ids[0]}, fallbacks: {model_ids[1:]}"
            )

    # ----------------------------------------------------------------
    # Internal Binding Helpers
    # ----------------------------------------------------------------

    def _bind(self, spec: ModelSpec) -> ModelClient:
        """Bind a ModelSpec to a ModelClient."""
        return ModelClient(_Boundspec(spec=spec))

    def _specs(self, role: ModelRole) -> list[ModelSpec]:
        """Get All Model specs for a role."""
        specs = self._table.get(role, [])
        if not specs:
            logger.error(f"No model specs configured for role: {role.value}")
            raise ValueError(f"No model specs configured for role: {role}")
        return specs

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def choose(self, role: ModelRole) -> ModelClient:
        """
        Return the primary model client for the given role.

        Args:
            role: Model Role (INTAKE, PLANNER, PR, CODER)

        Returns:
            ModelClient: Primary model client for the role.

        Example:
            client = router.choose(ModelRole.CODER)
            print(client.model_id)  # e.g. "alibaba/qwen3-coder-480b-a35b-instruct"
        """
        primary = self._bind(self._specs(role)[0])
        logger.debug(f"Chosen primary model for role {role.value}: {primary.model_id}")
        return primary

    def fallbacks(self, role: ModelRole) -> Iterable[ModelClient]:
        """
        Return fallback model clients for the given role (Excludes primary).

        Args:
            role: Model Role (INTAKE, PLANNER, PR, CODER)

        Returns:
            Iterable[ModelClient]: Fallback model clients for the role.

        Example:
            for fallback in router.fallbacks(ModelRole.PLANNER):
                print(fallback.model_id)
        """
        fallback_specs = self._specs(role)[1:]
        logger.debug(f"Retrieved {len(fallback_specs)} fallback models for role {role.value}")
        return (self._bind(spec) for spec in fallback_specs)

    def clients(self, role: ModelRole) -> Iterable[ModelClient]:
        """
        Return all model clients for the given role, in proiority order.
        Include primary and fallbacks.

        Args:
            role: Model Role

        Returns:
            Iterable[ModelClient]: All model clients for the role.

        Example:
            models = list(router.clients(ModelRole.INTAKE))
            print(f"{len(models)} models configured for INTAKE role.")
        """
        all_specs = self._specs(role)
        logger.debug(f"Retrieved {len(all_specs)} total models for role {role.value}")
        return (self._bind(spec) for spec in all_specs)

    def get_config_summary(self) -> dict[str, dict[str, object]]:
        """
        Get a summary of router configuration.

        Returns:
            dict: Configuration summary with roles and model counts.
        """
        summary = {}
        for role, specs in self._table.items():
            summary[role.value] = {
                "primary": specs[0].model_id,
                "fallbacks": [spec.model_id for spec in specs[1:]],
                "total_models": len(specs),
            }
        logger.debug(f"Configuration Summary: {summary}")
        return summary
