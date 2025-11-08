"""
Refactor API routes.

Endpoints:
- POST /api/refactor           - Start refactoring job
- GET  /api/refactor/{id}      - Get job status
- GET  /api/refactor/{id}/sse  - Server-Sent Events stream
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sse_starlette.sse import EventSourceResponse

from repoai.dependencies import OrchestratorDependencies
from repoai.orchestrator import OrchestratorAgent, PipelineStage, PipelineState, PipelineStatus
from repoai.utils.logger import get_logger

from ..models import (
    JobStatusResponse,
    ProgressUpdate,
    RefactorRequest,
    RefactorResponse,
)

logger = get_logger(__name__)

router = APIRouter()

# In-memory storage (use Redis/DB in production)
active_sessions: dict[str, PipelineState] = {}
session_queues: dict[str, asyncio.Queue[ProgressUpdate | None]] = {}


@router.post("/refactor", response_model=RefactorResponse)
async def start_refactor(
    request: RefactorRequest,
    background_tasks: BackgroundTasks,
) -> RefactorResponse:
    """
    Start a refactoring job.

    Returns session_id immediately and runs pipeline in background.

    Example request:
        POST /api/refactor
        {
            "user_id": "developer_001",
            "user_prompt": "Add JWT authentication",
            "github_credentials": {...},
            "mode": "autonomous"
        }

    Example response:
        {
            "session_id": "session_20250126_143022",
            "status": "running",
            "message": "Refactoring pipeline started",
            "status_url": "/api/refactor/session_20250126_143022",
            "sse_url": "/api/refactor/session_20250126_143022/sse"
        }
    """
    # Generate session ID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    session_id = f"session_{timestamp}_{unique_id}"

    logger.info(f"Starting refactor job: session={session_id}, user={request.user_id}")

    # Create progress queue for SSE
    progress_queue: asyncio.Queue[ProgressUpdate | None] = asyncio.Queue()
    session_queues[session_id] = progress_queue  # Initialize pipeline state
    initial_state = PipelineState(
        session_id=session_id,
        user_id=request.user_id,
        user_prompt=request.user_prompt,
        max_retries=request.max_retries,
        stage=PipelineStage.IDLE,
        status=PipelineStatus.PENDING,
    )
    active_sessions[session_id] = initial_state

    # Start pipeline in background
    background_tasks.add_task(
        run_pipeline,
        session_id=session_id,
        request=request,
        progress_queue=progress_queue,
    )

    # Build response
    base_url = "/api/refactor"
    response = RefactorResponse(
        session_id=session_id,
        status="running",
        message="Refactoring pipeline started",
        status_url=f"{base_url}/{session_id}",
        sse_url=f"{base_url}/{session_id}/sse",
        websocket_url=f"/ws/refactor/{session_id}" if request.mode == "interactive" else None,
    )

    logger.info(f"Refactor job started: {session_id}")
    return response


@router.get("/refactor/{session_id}", response_model=JobStatusResponse)
async def get_status(session_id: str) -> JobStatusResponse:
    """
    Get current status of refactoring job.

    Poll this endpoint to track progress without streaming.

    Example:
        GET /api/refactor/session_20250126_143022

        Response:
        {
            "session_id": "session_20250126_143022",
            "stage": "transformation",
            "status": "running",
            "progress": 0.6,
            "message": "Generating code..."
        }
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    state = active_sessions[session_id]

    # Build status response
    status = JobStatusResponse(
        session_id=state.session_id,
        user_id=state.user_id,
        stage=state.stage,
        status=state.status.value if hasattr(state.status, "value") else str(state.status),
        progress=state.progress_percentage,
        message=_get_stage_message(state),
        elapsed_time_ms=state.elapsed_time_ms,
        job_id=state.job_spec.job_id if state.job_spec else None,
        plan_id=state.plan.plan_id if state.plan else None,
        files_changed=state.code_changes.total_changes if state.code_changes else 0,
        validation_passed=state.validation_result.passed if state.validation_result else False,
        errors=state.errors,
        warnings=state.warnings,
        retry_count=state.retry_count,
        result=state.to_dict() if state.is_complete or state.is_failed else None,
    )

    return status


@router.get("/refactor/{session_id}/sse")
async def stream_progress(session_id: str) -> EventSourceResponse:
    """
    Server-Sent Events stream for real-time progress.

    Streams progress updates as they occur.

    Example:
        GET /api/refactor/session_20250126_143022/sse

        Stream output:
        data: {"stage": "intake", "progress": 0.2, "message": "Parsing request..."}

        data: {"stage": "planning", "progress": 0.4, "message": "Creating plan..."}

        data: {"stage": "complete", "progress": 1.0, "message": "Done!"}
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if session_id not in session_queues:
        raise HTTPException(status_code=500, detail="Progress queue not initialized")

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        """Generate SSE events from progress queue."""
        queue = session_queues[session_id]

        try:
            while True:
                # Wait for progress update
                update = await queue.get()

                # Check for completion signal
                if update is None:
                    logger.info(f"SSE stream completed: {session_id}")
                    break

                # Send progress update
                yield {
                    "event": "progress",
                    "data": update.model_dump_json(),
                }

        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled: {session_id}")
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            yield {
                "event": "error",
                "data": f'{{"error": "{str(e)}"}}',
            }

    return EventSourceResponse(event_generator())


# ============================================================================
# Background Task: Run Pipeline
# ============================================================================


async def run_pipeline(
    session_id: str,
    request: RefactorRequest,
    progress_queue: asyncio.Queue[ProgressUpdate | None],
) -> None:
    """
    Background task to run refactoring pipeline.

    Sends progress updates to queue for SSE streaming.
    """
    try:
        logger.info(f"Pipeline started: {session_id}")

        # Get state
        state = active_sessions[session_id]

        # TODO: Clone GitHub repository for validation
        # - Use request.github_credentials.access_token to authenticate
        # - Clone request.github_credentials.repository_url
        # - Checkout request.github_credentials.branch
        # - Set repository_path in OrchestratorDependencies
        # - This enables Maven/Gradle validation during pipeline execution
        # - Clean up cloned repo after pipeline completion
        repository_path = None  # Will be set after implementing clone logic

        # Configure orchestrator dependencies
        deps = OrchestratorDependencies(
            user_id=request.user_id,
            session_id=session_id,
            pipeline_state=state,
            repository_url=request.github_credentials.repository_url,
            repository_path=repository_path,  # TODO: Set after cloning repo
            auto_fix_enabled=request.auto_fix_enabled,
            max_retries=request.max_retries,
            timeout_seconds=request.timeout_seconds,
            enable_user_interaction=(request.mode == "interactive"),
            enable_progress_updates=True,
            # For autonomous mode, no chat callbacks needed
            send_message=lambda msg: (
                _send_progress_update(session_id, state.stage, msg, progress_queue)
                if request.mode == "autonomous"
                else None
            ),
            high_risk_threshold=request.high_risk_threshold,
            min_test_coverage=request.min_test_coverage,
        )

        # Create orchestrator (autonomous mode for now)
        orchestrator = OrchestratorAgent(deps)

        # Run pipeline
        final_state = await orchestrator.run(request.user_prompt)

        # Update stored state
        active_sessions[session_id] = final_state

        # Send final update
        await progress_queue.put(
            ProgressUpdate(
                session_id=session_id,
                stage=final_state.stage,
                status="completed" if final_state.is_complete else "failed",
                progress=1.0 if final_state.is_complete else final_state.progress_percentage,
                message="Refactoring completed!" if final_state.is_complete else "Pipeline failed",
                data={
                    "files_changed": (
                        final_state.code_changes.total_changes if final_state.code_changes else 0
                    ),
                    "validation_passed": (
                        final_state.validation_result.passed
                        if final_state.validation_result
                        else False
                    ),
                },
            )
        )

        # Signal completion
        await progress_queue.put(None)

        logger.info(
            f"Pipeline completed: {session_id}, "
            f"stage={final_state.stage.value}, "
            f"success={final_state.is_complete}"
        )

    except Exception as e:
        logger.error(f"Pipeline failed: {session_id}, error={e}", exc_info=True)

        # Update state
        if session_id in active_sessions:
            state = active_sessions[session_id]
            state.stage = PipelineStage.FAILED
            state.status = PipelineStatus.FAILED
            state.add_error(str(e))

        # Send error update
        await progress_queue.put(
            ProgressUpdate(
                session_id=session_id,
                stage=PipelineStage.FAILED,
                status="failed",
                progress=0.0,
                message=f"Pipeline failed: {str(e)}",
            )
        )

        # Signal completion
        await progress_queue.put(None)


def _send_progress_update(
    session_id: str,
    stage: PipelineStage,
    message: str,
    queue: asyncio.Queue[ProgressUpdate | None],
) -> None:
    """Send progress update to SSE queue (sync callback for orchestrator)."""
    try:
        state = active_sessions.get(session_id)
        if not state:
            return

        update = ProgressUpdate(
            session_id=session_id,
            stage=stage,
            status=state.status.value if hasattr(state.status, "value") else str(state.status),
            progress=state.progress_percentage,
            message=message,
        )

        # Put in queue (sync call, orchestrator runs in event loop already)
        asyncio.create_task(queue.put(update))

    except Exception as e:
        logger.error(f"Failed to send progress update: {e}")


def _get_stage_message(state: PipelineState) -> str:
    """Generate human-readable message for current stage."""
    if state.is_complete:
        return "Refactoring completed successfully! ✅"

    if state.is_failed:
        return f"Pipeline failed: {state.errors[0] if state.errors else 'Unknown error'}"

    messages = {
        PipelineStage.IDLE: "Waiting to start...",
        PipelineStage.INTAKE: "Parsing refactoring request...",
        PipelineStage.PLANNING: "Creating refactoring plan...",
        PipelineStage.TRANSFORMATION: f"Generating code changes... ({state.code_changes.files_modified if state.code_changes else 0} files)",
        PipelineStage.VALIDATION: f"Validating code... (retry {state.retry_count})",
        PipelineStage.NARRATION: "Creating PR description...",
    }

    return messages.get(state.stage, f"Processing {state.stage.value}...")
