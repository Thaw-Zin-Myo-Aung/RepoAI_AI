from __future__ import annotations

import os
from dataclasses import dataclass

from .model_roles import ModelRole


@dataclass(frozen=True)
class ModelSpec:
    """Single model option for a given logical role."""

    provider: str
    model_id: str
    temperature: float = 0.2
    json_mode: bool = False
    max_output_tokens: int = 2048


ENV_KEYS: dict[ModelRole, str] = {
    ModelRole.INTAKE: "MODEL_ROUTE_INTAKE",
    ModelRole.PLANNER: "MODEL_ROUTE_PLANNER",
    ModelRole.PR_NARRATOR: "MODEL_ROUTE_PR",
    ModelRole.CODER: "MODEL_ROUTE_CODER",
    ModelRole.EMBEDDING: "EMBEDDING_MODEL",
}


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _infer_provider(model_id: str) -> str:
    """Infer provider from model ID - always Gemini now."""
    return "Gemini"


def _default_models_for(role: ModelRole) -> list[str]:
    """Default Gemini models to fallback when env is not set."""
    if role is ModelRole.INTAKE:
        # Fast reasoning for user prompts
        return [
            "gemini-2.0-flash-thinking-exp-01-21",
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash-002",
        ]

    if role is ModelRole.PLANNER:
        # Reasoning and planning
        return [
            "gemini-2.0-flash-thinking-exp-01-21",
            "gemini-exp-1206",
            "gemini-2.0-flash-exp",
        ]

    if role is ModelRole.PR_NARRATOR:
        # Natural Language Processing for PR summaries
        return [
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash-002",
            "gemini-2.0-flash-thinking-exp-01-21",
        ]

    if role is ModelRole.CODER:
        # Code-focused models for refactoring and completions
        return [
            "gemini-exp-1206",
            "gemini-2.0-flash-thinking-exp-01-21",
            "gemini-2.0-flash-exp",
        ]

    if role is ModelRole.EMBEDDING:
        # Embedding model for RAG
        return ["text-embedding-004"]

    return []


def load_defaults_from_env() -> dict[ModelRole, list[ModelSpec]]:
    """
    Build an ordered list of ModelSpec per role from env.
    CSV format for most roles, single value for EMBEDDING is OK.
    """
    table: dict[ModelRole, list[ModelSpec]] = {}

    for role, env_key in ENV_KEYS.items():
        raw = os.getenv(env_key, "")
        ids = _split_csv(raw)

        if not ids:
            ids = _default_models_for(role)

        # Turn model IDs into ModelSpec with light heuristics
        specs: list[ModelSpec] = []
        for model_id in ids:
            # Determine max_output_tokens based on role
            if role in (ModelRole.CODER,):
                max_tokens = 8192  # Code generation needs more tokens
            elif role in (ModelRole.PLANNER, ModelRole.PR_NARRATOR):
                max_tokens = 4096
            else:
                max_tokens = 2048

            specs.append(
                ModelSpec(
                    provider=_infer_provider(model_id),
                    model_id=model_id,
                    temperature=0.2 if role in (ModelRole.CODER,) else 0.3,
                    json_mode=True if role in (ModelRole.PLANNER, ModelRole.INTAKE) else False,
                    max_output_tokens=max_tokens,
                )
            )

        table[role] = specs
    return table
