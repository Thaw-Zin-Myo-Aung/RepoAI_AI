from __future__ import annotations

import logging
import os
import time
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    "Read an integer from environment safely with a fallback default."
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"Invalid integer for {name}: {raw}, using default {default}")
        return default


class AIMLClient:
    """
    Thin Wrapper for AIMLAPI HTTP Client (OpenAI-compatible).

    Example usage:
        client = AIMLClient()
        result = client.chat("deepseek/deepseek-chat-v3.1", [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ])
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_s: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.base_url: str = (
            base_url if base_url is not None else os.getenv("AIMLAPI_BASE_URL")
        ) or "https://api.aimlapi.com/v1"

        self.api_key: str = (api_key if api_key is not None else os.getenv("AIMLAPI_KEY")) or ""
        self.timeout_s: int = (
            timeout_s if timeout_s is not None else _env_int("AIML_DEFAULT_TIMEOUT_S", 45)
        )
        self.max_retries: int = (
            max_retries if max_retries is not None else _env_int("AIML_MAX_RETRIES", 2)
        )

        if not self.api_key:
            logger.warning("AIMLAPI_KEY is not set - requests will fail without authentication.")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_output_tokens: int = 1024,
        json_mode: bool = False,
        **extra: Any,
    ) -> dict[str, Any]:
        """
        Send Chat completion request.
        Returns parsed JSON response (Same As OpenAI style).
        """
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            **extra,
        }

        # Response format for pydantic-ai JSON validation
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_exception: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_s) as client:
                    response = client.post(url, headers=self._headers(), json=payload)
                response.raise_for_status()
                data = cast(dict[str, Any], response.json())
                logger.debug(
                    f"AIML response OK (model={model_id}), tokens = {data.get('usage', {})}"
                )
                return data
            except Exception as e:
                last_exception = e
                if attempt >= self.max_retries:
                    logger.error(f"AIML request failed after {attempt + 1} tries {e}")
                    raise
                wait = 1.5**attempt
                logger.warning(f"AIML request error {e}, retrying in {wait:.1f}s...")
                time.sleep(wait)

        if last_exception is not None:
            raise last_exception
        raise RuntimeError("AIML request failed for unknown reasons.")
