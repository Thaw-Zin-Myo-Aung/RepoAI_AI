"""
FastAPI application for RepoAI.

Provides REST API and WebSocket endpoints for Java backend integration.

Endpoints:
- POST   /api/refactor           - Start refactoring job
- GET    /api/refactor/{id}      - Get job status
- GET    /api/refactor/{id}/sse  - Server-Sent Events for progress
- WS     /ws/refactor/{id}       - WebSocket for interactive mode
- POST   /api/health             - Health check
"""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from repoai.utils.logger import get_logger, setup_logging

from .routes import health, refactor, websocket

logger = get_logger(__name__)


# Global state for job tracking
class AppState:
    """Global application state."""

    def __init__(self) -> None:
        self.active_sessions: dict[str, object] = {}
        self.job_results: dict[str, object] = {}


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for startup/shutdown."""
    # Startup
    setup_logging(level=logging.INFO)
    logger.info("🚀 RepoAI FastAPI service starting...")
    logger.info(f"   Active sessions: {len(app_state.active_sessions)}")

    yield

    # Shutdown
    logger.info("🛑 RepoAI FastAPI service shutting down...")
    logger.info(f"   Total jobs processed: {len(app_state.job_results)}")


# Create FastAPI app
app = FastAPI(
    title="RepoAI API",
    description="AI-powered Java refactoring service",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for Java backend
# Configure allowed origins via `CORS_ALLOWED_ORIGINS` env var.
# Frontend at http://localhost:5173 uses cookies, so default to that origin
# and enable credentials. In production set CORS_ALLOWED_ORIGINS to a
# comma-separated list of allowed origins (e.g. "https://app.example.com").
origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
if origins_env:
    allow_origins = [o.strip() for o in origins_env.split(",") if o.strip()]
    allow_credentials = True
else:
    # Default to local frontend which requires cookies
    allow_origins = ["http://localhost:5173"]
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(refactor.router, prefix="/api", tags=["Refactor"])
app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])


# Root endpoint
@app.get("/")
async def root() -> dict[str, object]:
    """Root endpoint with API info."""
    return {
        "service": "RepoAI",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "health": "GET /api/health",
            "refactor": "POST /api/refactor",
            "status": "GET /api/refactor/{session_id}",
            "stream": "GET /api/refactor/{session_id}/sse",
            "websocket": "WS /ws/refactor/{session_id}",
        },
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "type": type(exc).__name__,
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "repoai.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload in development
        log_level="info",
    )
