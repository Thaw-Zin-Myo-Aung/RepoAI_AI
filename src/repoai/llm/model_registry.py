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
    """Light heuristic to infer provider from model ID."""
    m = model_id.lower()
    if "deepseek" in m:
        return "DeepSeek"
    if "qwen" in m or "qwq" in m:
        return "Qwen"
    if "bge" in m or "minilm" in m:
        return "Local Embedding"
    return "AIMLAPI"


def _default_models_for(role: ModelRole) -> list[str]:
    """Default models to fallback when env is not set."""
    if role is ModelRole.INTAKE:
        # Fast reasoning for user prompts
        return [
            "deepseek/deepseek-chat-v3.1",
            "alibaba/qwen-max",
            "claude-sonnet-4-5-20250929",
        ]

    if role is ModelRole.PLANNER:
        # Reasoning and JSON output
        return [
            "deepseek/deepseek-reasoner-v3.1",
            "alibaba/qwen3-next-80b-a3b-thinking",
            "claude-opus-4-20250514",
        ]

    if role is ModelRole.PR_NARRATOR:
        # Natural Language Processing for PR summaries
        return [
            "deepseek/deepseek-chat-v3.1",
            "claude-haiku-4-5-20251001",
            "alibaba/qwen3-235b-a22b-thinking-2507",
        ]

    if role is ModelRole.CODER:
        # Code-focused LLM for refactoring and completions
        return [
            "alibaba/qwen3-coder-480b-a35b-instruct",
            "Qwen/Qwen2.5-Coder-32B-Instruct",
            "deepseek/deepseek-chat-v3.1",
            "claude-opus-4-1-20250805",
        ]

    if role is ModelRole.EMBEDDING:
        # Small Embedding model for RAG
        return ["bge-small"]

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
        specs: list[ModelSpec] = [
            ModelSpec(
                provider=_infer_provider(model_id),
                model_id=model_id,
                # Sensible per-role defaults
                temperature=0.2 if role in (ModelRole.CODER,) else 0.3,
                json_mode=True if role in (ModelRole.PLANNER, ModelRole.INTAKE) else False,
                max_output_tokens=(
                    4096 if role in (ModelRole.PLANNER, ModelRole.PR_NARRATOR) else 2048
                ),
            )
            for model_id in ids
        ]

        table[role] = specs
    return table
