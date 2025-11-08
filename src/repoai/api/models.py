"""
API request/response models for FastAPI endpoints.

Pydantic models for:
- Refactor requests from Java backend
- Progress updates
- Status responses
- Error handling
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from repoai.orchestrator import PipelineStage

# ============================================================================
# Request Models (from Java backend)
# ============================================================================


class GitHubCredentials(BaseModel):
    """GitHub repository access credentials."""

    access_token: str = Field(description="GitHub personal access token")
    repository_url: str = Field(
        description="GitHub repository URL (e.g., https://github.com/user/repo)"
    )
    branch: str = Field(default="main", description="Target branch")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "ghp_xxxxxxxxxxxxxxxxxxxx",
                "repository_url": "https://github.com/example/spring-boot-app",
                "branch": "main",
            }
        }
    )


class RefactorRequest(BaseModel):
    """
    Refactor request from Java backend.

    Example:
        {
            "user_id": "developer_001",
            "user_prompt": "Add JWT authentication to user service",
            "github_credentials": {...},
            "mode": "autonomous",
            "auto_fix_enabled": true
        }
    """

    user_id: str = Field(description="User identifier")
    user_prompt: str = Field(description="Refactoring intent/request")
    github_credentials: GitHubCredentials = Field(description="GitHub access")

    mode: str = Field(
        default="autonomous", description="Execution mode: 'autonomous' or 'interactive'"
    )

    auto_fix_enabled: bool = Field(
        default=True, description="Whether to automatically fix validation errors"
    )

    max_retries: int = Field(default=3, ge=0, le=5, description="Maximum validation retry attempts")

    high_risk_threshold: int = Field(
        default=7, ge=0, le=10, description="Risk level requiring approval (interactive mode)"
    )

    min_test_coverage: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum required test coverage"
    )

    timeout_seconds: int = Field(
        default=300, ge=60, le=3600, description="Pipeline execution timeout"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "developer_001",
                "user_prompt": "Add JWT authentication to user service using Spring Security",
                "github_credentials": {
                    "access_token": "ghp_xxxxxxxxxxxxxxxxxxxx",
                    "repository_url": "https://github.com/example/spring-boot-app",
                    "branch": "main",
                },
                "mode": "autonomous",
                "auto_fix_enabled": True,
                "max_retries": 3,
                "high_risk_threshold": 7,
                "min_test_coverage": 0.7,
                "timeout_seconds": 300,
            }
        }
    )


# ============================================================================
# Response Models (to Java backend)
# ============================================================================


class RefactorResponse(BaseModel):
    """
    Immediate response after starting refactor job.

    Returns session_id for tracking progress.
    """

    session_id: str = Field(description="Unique session identifier")
    status: str = Field(description="Initial status (pending/running)")
    message: str = Field(description="Human-readable message")
    created_at: datetime = Field(default_factory=datetime.now)

    # URLs for tracking progress
    status_url: str = Field(description="URL to check status")
    sse_url: str = Field(description="Server-Sent Events URL for streaming")
    websocket_url: str | None = Field(
        default=None, description="WebSocket URL (interactive mode only)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "session_20250126_143022",
                "status": "running",
                "message": "Refactoring pipeline started",
                "created_at": "2025-01-26T14:30:22",
                "status_url": "/api/refactor/session_20250126_143022",
                "sse_url": "/api/refactor/session_20250126_143022/sse",
                "websocket_url": "/ws/refactor/session_20250126_143022",
            }
        }
    )


class JobStatusResponse(BaseModel):
    """
    Current status of refactoring job.

    Used for polling status endpoint.
    """

    session_id: str
    user_id: str
    stage: PipelineStage
    status: str  # pending, running, paused, completed, failed
    progress: float = Field(ge=0.0, le=1.0, description="Progress (0.0 - 1.0)")

    message: str = Field(description="Current status message")
    elapsed_time_ms: float = Field(description="Time elapsed in milliseconds")

    # Job results (populated when available)
    job_id: str | None = None
    plan_id: str | None = None
    files_changed: int = 0
    validation_passed: bool = False

    # Errors/warnings
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    retry_count: int = 0

    # Final results (when complete)
    result: dict[str, object] | None = Field(
        default=None, description="Complete result (when stage=complete)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "session_20250126_143022",
                "user_id": "developer_001",
                "stage": "transformation",
                "status": "running",
                "progress": 0.6,
                "message": "Generating code changes... (3/5 files)",
                "elapsed_time_ms": 45230.5,
                "job_id": "job_20250126_143030",
                "plan_id": "plan_20250126_143045",
                "files_changed": 3,
                "validation_passed": False,
                "errors": [],
                "warnings": [],
                "retry_count": 0,
            }
        }
    )


class ProgressUpdate(BaseModel):
    """
    Real-time progress update (SSE/WebSocket).

    Sent during pipeline execution for live tracking.
    """

    session_id: str
    stage: PipelineStage
    status: str
    progress: float = Field(ge=0.0, le=1.0)
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)

    # Optional data for specific stages
    data: dict[str, object] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "session_20250126_143022",
                "stage": "validation",
                "status": "running",
                "progress": 0.8,
                "message": "Validating code changes...",
                "timestamp": "2025-01-26T14:35:00",
                "data": {"checks_completed": 3, "checks_total": 5, "current_check": "compilation"},
            }
        }
    )


class UserConfirmationRequest(BaseModel):
    """
    Request for user confirmation (interactive mode).

    Sent via WebSocket when user decision needed.
    """

    session_id: str
    prompt_type: str = Field(description="Type: plan_approval, high_risk, retry")
    prompt: str = Field(description="Question for user")
    options: list[str] = Field(description="Available options")
    context: dict[str, object] | None = Field(
        default=None, description="Additional context (e.g., plan summary, error details)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "session_20250126_143022",
                "prompt_type": "plan_approval",
                "prompt": "Review and approve refactoring plan",
                "options": ["approve", "modify: <instructions>", "reject"],
                "context": {"plan_steps": 6, "risk_level": 5, "breaking_changes": False},
            }
        }
    )


class UserConfirmationResponse(BaseModel):
    """
    User's response to confirmation request.

    Sent from Java backend via WebSocket.
    """

    session_id: str
    response: str = Field(description="User's decision (approve, modify, reject, etc.)")
    additional_context: str | None = Field(
        default=None, description="Additional context (e.g., modification instructions)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "session_20250126_143022",
                "response": "modify",
                "additional_context": "Add comprehensive logging to authentication methods",
            }
        }
    )


# ============================================================================
# Error Models
# ============================================================================


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(description="Error type")
    message: str = Field(description="Error message")
    session_id: str | None = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.now)
    details: dict[str, object] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "ValidationError",
                "message": "Invalid GitHub access token",
                "session_id": None,
                "timestamp": "2025-01-26T14:30:00",
                "details": {"field": "github_credentials.access_token"},
            }
        }
    )


# ============================================================================
# Health Check
# ============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(description="Service status (healthy, degraded, unhealthy)")
    version: str = Field(description="API version")
    timestamp: datetime = Field(default_factory=datetime.now)

    services: dict[str, str] = Field(
        description="Status of dependent services", default_factory=dict
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "0.1.0",
                "timestamp": "2025-01-26T14:30:00",
                "services": {
                    "gemini_api": "healthy",
                    "github_api": "healthy",
                    "database": "not_configured",
                },
            }
        }
    )
