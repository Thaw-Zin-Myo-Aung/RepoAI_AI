"""Data models for Orchestrator Agent."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from . import CodeChanges, JobSpec, PRDescription, RefactorPlan, ValidationResult


class PipelineStage(str, Enum):
    """
    Pipeline execution stages.

    Tracks which stage the orchestrator is currently executing.
    """

    IDLE = "idle"
    INTAKE = "intake"
    PLANNING = "planning"
    TRANSFORMATION = "transformation"
    VALIDATION = "validation"
    NARRATION = "narration"
    COMPLETE = "complete"
    FAILED = "failed"


class PipelineStatus(str, Enum):
    """Status of Pipeline execution."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PipelineState:
    """
    Complete state of the refactoring pipeline.

    Tracks all results, metadata, and progress for a pipeline execution.
    This is the main state object passed between orchestrator methods.

    Example:
        state = PipelineState(
            session_id="session_123",
            stage=PipelineStage.INTAKE,
            user_prompt="Add JWT authentication"
        )

        # Access state
        print(f"Stage: {state.stage}")
        print(f"Progress: {state.progress_percentage:.0f}%")
        print(f"Time: {state.elapsed_time_ms:.0f}ms")
    """

    # Identity
    session_id: str
    """Unique session identifier"""

    user_id: str = "default_user"
    """User who initiated the request"""

    # Pipeline tracking
    stage: PipelineStage = PipelineStage.IDLE
    """Current pipeline stage"""

    status: PipelineStatus = PipelineStatus.PENDING
    """Current execution status"""

    user_prompt: str = ""
    """Original user prompt/request"""

    # Agent results (populated as pipeline progresses)
    job_spec: JobSpec | None = None
    """Result from Intake Agent"""

    plan: RefactorPlan | None = None
    """Result from Planner Agent"""

    code_changes: CodeChanges | None = None
    """Result from Transformer Agent"""

    validation_result: ValidationResult | None = None
    """Result from Validator Agent"""

    pr_description: PRDescription | None = None
    """Result from PR Narrator Agent"""

    # Retry and error tracking
    retry_count: int = 0
    """Number of validation retries attempted"""

    max_retries: int = 3
    """Maximum allowed retries"""

    errors: list[str] = field(default_factory=list)
    """List of error messages"""

    warnings: list[str] = field(default_factory=list)
    """List of warning messages"""

    # Timing
    start_time: float = field(default_factory=time.time)
    """Pipeline start timestamp"""

    end_time: float | None = None
    """Pipeline end timestamp"""

    stage_timings: dict[str, float] = field(default_factory=dict)
    """Time spent in each stage (ms)"""

    # User interactions
    user_confirmations: list[dict[str, str]] = field(default_factory=list)
    """Record of user confirmations requested and receieved"""

    @property
    def elapsed_time_ms(self) -> float:
        """Calculate elapsed time in milliseconds."""
        end = self.end_time if self.end_time else time.time()
        return (end - self.start_time) * 1000

    @property
    def can_retry(self) -> bool:
        """Check if we can retry failed validations."""
        return self.retry_count < self.max_retries

    @property
    def progress_percentage(self) -> float:
        """
        Calculate overall progress (0.0 - 1.0).

        Based on stage completion:
        - Intake: 0.2
        - Planning: 0.4
        - Transformation: 0.6
        - Validation: 0.8
        - Narration: 1.0
        """
        stage_progress = {
            PipelineStage.IDLE: 0.0,
            PipelineStage.INTAKE: 0.2,
            PipelineStage.PLANNING: 0.4,
            PipelineStage.TRANSFORMATION: 0.6,
            PipelineStage.VALIDATION: 0.8,
            PipelineStage.NARRATION: 0.9,
            PipelineStage.COMPLETE: 1.0,
            PipelineStage.FAILED: 0.0,
        }
        return stage_progress.get(self.stage, 0.0)

    @property
    def is_complete(self) -> bool:
        """Check if pipeline completed successfully."""
        return self.stage == PipelineStage.COMPLETE

    @property
    def is_failed(self) -> bool:
        """Check if pipeline failed."""
        return self.stage == PipelineStage.FAILED

    @property
    def is_running(self) -> bool:
        """Check if pipeline is currently running."""
        return self.status == PipelineStatus.RUNNING

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)

    def record_stage_time(self, stage: PipelineStage, duration_ms: float) -> None:
        """Record time spent in a stage."""
        self.stage_timings[stage.value] = duration_ms

    def to_dict(self) -> dict[str, object]:
        """Convert state to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "stage": self.stage.value,
            "status": self.status.value,
            "user_prompt": self.user_prompt,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "errors": self.errors,
            "warnings": self.warnings,
            "elapsed_time_ms": self.elapsed_time_ms,
            "progress_percentage": self.progress_percentage,
            "is_complete": self.is_complete,
            "is_failed": self.is_failed,
            # Results summaries
            "job_id": self.job_spec.job_id if self.job_spec else None,
            "plan_id": self.plan.plan_id if self.plan else None,
            "files_changed": self.code_changes.total_changes if self.code_changes else 0,
            "validation_passed": self.validation_result.passed if self.validation_result else False,
            "pr_title": self.pr_description.title if self.pr_description else None,
        }


class PipelineUpdateMessage(BaseModel):
    """
    Progress update message for real-time streaming.

    Sent to users via WebSocket or similar for live progress tracking.

    Example:
        update = PipelineUpdateMessage(
            session_id="session_123",
            stage=PipelineStage.TRANSFORMATION,
            status="running",
            progress=0.6,
            message="Generating code..."
        )

        # Send to user
        await websocket.send_json(update.model_dump())
    """

    session_id: str = Field(description="Session identifier")

    stage: PipelineStage = Field(description="Current pipeline stage")

    status: str = Field(description="Status: running, complete, failed")

    progress: float = Field(ge=0.0, le=1.0, description="Progress (0.0 - 1.0)")

    message: str = Field(description="Human-readable status message")

    timestamp: datetime = Field(default_factory=datetime.now)

    data: dict[str, object] | None = Field(
        default=None, description="Additional data (e.g., partial results)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "session_20250126_143022",
                "stage": "transformation",
                "status": "running",
                "progress": 0.6,
                "message": "Generating code... (3/5 files)",
                "timestamp": "2025-01-26T14:30:45",
                "data": {"files_completed": 3, "files_total": 5},
            }
        }
    )


class PipeLineResult(BaseModel):
    """
    Final result of pipeline execution.

    Returned to API clients or saved to database.

    Example:
        result = PipelineResult(
            session_id="session_123",
            success=True,
            stage=PipelineStage.COMPLETE,
            job_id="job_123",
            plan_id="plan_123",
            elapsed_time_ms=15234.5
        )
    """

    session_id: str = Field(description="Session identifier")

    user_id: str = Field(description="User who initiated the request")

    success: bool = Field(description="Whether pipeline completed successfully")

    stage: PipelineStage = Field(description="Final stage reached")

    # IDs for tracking
    job_id: str | None = Field(default=None, description="Job ID from Intake")

    plan_id: str | None = Field(default=None, description="Plan ID from Planner")

    # Summary statistics
    files_changed: int = Field(default=0, description="Total files changed")

    lines_added: int = Field(default=0, description="Total lines added")

    classes_created: int = Field(default=0, description="Classes created")

    validation_passed: bool = Field(default=False, description="Validation result")

    confidence_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Overall confidence (0.0-1.0)"
    )

    test_coverage: float = Field(default=0.0, ge=0.0, le=1.0, description="Test coverage (0.0-1.0)")

    # PR information
    pr_title: str | None = Field(default=None, description="PR title")

    pr_url: str | None = Field(default=None, description="PR URL if created")

    # Error tracking
    errors: list[str] = Field(default_factory=list, description="Error messages")

    warnings: list[str] = Field(default_factory=list, description="Warning messages")

    retry_count: int = Field(default=0, description="Number of retries")

    # Timing
    elapsed_time_ms: float = Field(description="Total execution time (ms)")

    started_at: datetime = Field(default_factory=datetime.now)

    completed_at: datetime | None = Field(default=None)

    # Full state (optional, for debugging)
    full_state: dict[str, object] | None = Field(
        default=None, description="Complete pipeline state (for debugging)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "session_20250126_143022",
                "user_id": "developer_001",
                "success": True,
                "stage": "complete",
                "job_id": "job_20250126_143030",
                "plan_id": "plan_20250126_143045",
                "files_changed": 5,
                "lines_added": 247,
                "classes_created": 2,
                "validation_passed": True,
                "confidence_score": 0.92,
                "test_coverage": 0.85,
                "pr_title": "feat: Add JWT authentication to user service",
                "errors": [],
                "warnings": [],
                "retry_count": 1,
                "elapsed_time_ms": 15234.5,
            }
        }
    )
