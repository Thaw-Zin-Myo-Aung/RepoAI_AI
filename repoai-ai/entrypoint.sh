#!/usr/bin/env sh
# Entrypoint that prefers `uv run` if available, falls back to `uvicorn`.
PORT=${PORT:-8000}
if command -v uv >/dev/null 2>&1; then
  exec uv run uvicorn src.repoai.api.main:app --host 0.0.0.0 --port "$PORT"
else
  exec uvicorn src.repoai.api.main:app --host 0.0.0.0 --port "$PORT"
fi
