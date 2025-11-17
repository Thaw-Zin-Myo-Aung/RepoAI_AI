"""
Refactor API routes.

Endpoints:
- POST /api/refactor                      - Start refactoring job
- GET  /api/refactor/{id}                 - Get job status
- GET  /api/refactor/{id}/sse             - Server-Sent Events stream
- POST /api/refactor/{id}/confirm-plan    - Confirm refactoring plan (interactive-detailed)
- POST /api/refactor/{id}/confirm-validation - Confirm validation level (interactive-detailed)
- POST /api/refactor/{id}/confirm-push    - Confirm git push (interactive-detailed)
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sse_starlette.sse import EventSourceResponse

from repoai.dependencies import OrchestratorDependencies
from repoai.orchestrator import OrchestratorAgent, PipelineStage, PipelineState, PipelineStatus
from repoai.utils.git_utils import cleanup_repository
from repoai.utils.logger import get_logger

from ..models import (
    JobStatusResponse,
    PlanConfirmationRequest,
    ProgressUpdate,
    PushConfirmationRequest,
    RefactorRequest,
    RefactorResponse,
    ValidationConfirmationRequest,
)

logger = get_logger(__name__)

router = APIRouter()

# In-memory storage (use Redis/DB in production)
active_sessions: dict[str, PipelineState] = {}
session_queues: dict[str, asyncio.Queue[ProgressUpdate | None]] = {}
confirmation_queues: dict[str, asyncio.Queue[dict[str, object]]] = {}
# Buffer for storing messages before SSE client connects
session_buffers: dict[str, list[ProgressUpdate | None]] = {}


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
    session_queues[session_id] = progress_queue

    # Initialize message buffer for late SSE connections
    session_buffers[session_id] = []

    # Create confirmation queue for interactive-detailed mode
    if request.mode == "interactive-detailed":
        confirmation_queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        confirmation_queues[session_id] = confirmation_queue

    # Initialize pipeline state
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
        awaiting_confirmation=getattr(state, "awaiting_confirmation", None),
        confirmation_data=getattr(state, "confirmation_data", None),
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
        buffer = session_buffers.get(session_id, [])
        try:
            # First, send any buffered messages (for late connections)
            logger.info(f"SSE connected: {session_id}, buffered_messages={len(buffer)}")
            for buffered_update in buffer:
                if buffered_update is None:
                    # Completion signal in buffer -> emit explicit complete event and stop
                    logger.info(f"SSE stream completed (from buffer): {session_id}")
                    # Emit explicit complete event so clients can act on it
                    yield {
                        "event": "complete",
                        "data": f'{{"session_id":"{session_id}","success":true}}',
                    }
                    # clear buffer and return to close generator
                    if session_id in session_buffers:
                        session_buffers.pop(session_id, None)
                    return

                yield {
                    "event": "progress",
                    "data": buffered_update.model_dump_json(),
                }

            # Clear buffer after sending
            if session_id in session_buffers:
                session_buffers[session_id].clear()

            # Then stream new messages from queue
            while True:
                # Wait for progress update
                update = await queue.get()

                # Check for completion signal
                if update is None:
                    logger.info(f"SSE stream completed: {session_id}")
                    # emit explicit complete event so frontend can handle onmessage/oncomplete
                    yield {
                        "event": "complete",
                        "data": f'{{"session_id":"{session_id}","success":true}}',
                    }
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
        finally:
            # Cleanup session state so reconnects don't replay completed stream
            try:
                session_queues.pop(session_id, None)
                session_buffers.pop(session_id, None)
                confirmation_queues.pop(session_id, None)
                # Keep active_sessions intact so status endpoint still works
                logger.info(f"SSE cleanup done for session: {session_id}")
            except Exception:
                logger.exception("Error during SSE cleanup")

    return EventSourceResponse(event_generator())


@router.post("/refactor/{session_id}/confirm-plan")
async def confirm_plan(session_id: str, request: PlanConfirmationRequest) -> dict[str, str]:
    """
    Confirm or modify the refactoring plan.

    Used in interactive-detailed mode when pipeline is waiting for plan approval.

    Supports two input formats:
    1. Structured: {"action": "approve"} or {"action": "modify", "modifications": "..."}
    2. Natural language: {"user_response": "yes but use Redis instead"}

    Example structured request:
        POST /api/refactor/session_123/confirm-plan
        {"action": "approve"}

    Example natural language request:
        POST /api/refactor/session_123/confirm-plan
        {"user_response": "looks good but add logging to all methods"}

    Example response:
        {"status": "confirmed", "message": "Plan approved, continuing transformation"}
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    state = active_sessions[session_id]

    # Verify pipeline is waiting for plan confirmation
    if state.awaiting_confirmation != "plan":
        raise HTTPException(
            status_code=400,
            detail=f"Session not awaiting plan confirmation (current: {state.awaiting_confirmation})",
        )

    # Validate input - must have either action or user_response, not both
    if request.action and request.user_response:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'action' (structured) or 'user_response' (natural language), not both",
        )

    if not request.action and not request.user_response:
        raise HTTPException(
            status_code=400, detail="Must provide either 'action' or 'user_response'"
        )

    # Validate structured format
    if request.action == "modify" and not request.modifications and not request.user_response:
        raise HTTPException(status_code=400, detail="Modifications required when action='modify'")

    logger.info(
        f"Plan confirmation received: session={session_id}, "
        f"action={request.action or 'natural_language'}, "
        f"user_response={request.user_response[:50] if request.user_response else None}"
    )

    # Put confirmation in queue (orchestrator is waiting for this)
    if session_id in confirmation_queues:
        if request.user_response:
            # Natural language format - orchestrator will use LLM to interpret
            await confirmation_queues[session_id].put({"user_response": request.user_response})
        else:
            # Structured format - direct action
            await confirmation_queues[session_id].put(
                {"action": request.action, "modifications": request.modifications}
            )

    response_message = (
        "Processing natural language response..."
        if request.user_response
        else f"Plan {request.action}d, continuing pipeline"
    )

    return {
        "status": "confirmed",
        "message": response_message,
    }


@router.post("/refactor/{session_id}/confirm-validation")
async def confirm_validation(
    session_id: str, request: ValidationConfirmationRequest
) -> dict[str, str]:
    """
    Confirm validation level for code changes.

    Used in interactive-detailed mode when pipeline is waiting for validation approval.

    Supports two input formats:
    1. Structured: {"validation_mode": "full"} or {"validation_mode": "compile_only"} or {"validation_mode": "skip"}
    2. Natural language: {"user_response": "run all tests"}

    Validation modes:
    - "full": Compile code and run all tests (default, recommended)
    - "compile_only": Only compile code, skip test execution
    - "skip": Skip validation entirely (risky, not recommended)

    Example structured request:
        POST /api/refactor/session_123/confirm-validation
        {"validation_mode": "full"}

    Example natural language request:
        POST /api/refactor/session_123/confirm-validation
        {"user_response": "just compile, skip the test suite"}

    Example response:
        {
            "status": "confirmed",
            "message": "Validation mode set to: full"
        }
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    state = active_sessions[session_id]

    # Verify pipeline is waiting for validation confirmation
    if state.awaiting_confirmation != "validation":
        raise HTTPException(
            status_code=400,
            detail=f"Session not awaiting validation confirmation (current: {state.awaiting_confirmation})",
        )

    # Validate input - must have either validation_mode or user_response, not both
    if request.validation_mode and request.user_response:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'validation_mode' (structured) or 'user_response' (natural language), not both",
        )

    if not request.validation_mode and not request.user_response:
        raise HTTPException(
            status_code=400, detail="Must provide either 'validation_mode' or 'user_response'"
        )

    logger.info(
        f"Validation confirmation received: session={session_id}, "
        f"validation_mode={request.validation_mode or 'natural_language'}, "
        f"user_response={request.user_response[:50] if request.user_response else None}"
    )

    # Put confirmation in queue (orchestrator is waiting for this)
    if session_id in confirmation_queues:
        if request.user_response:
            # Natural language format - orchestrator will use LLM to interpret
            await confirmation_queues[session_id].put({"user_response": request.user_response})
        else:
            # Structured format - direct validation mode
            await confirmation_queues[session_id].put(
                {
                    "validation_mode": request.validation_mode,
                }
            )

    if request.user_response:
        return {
            "status": "confirmed",
            "message": "Processing natural language response...",
        }
    elif request.validation_mode == "full":
        return {
            "status": "confirmed",
            "message": "Validation mode set to: full (compile + run tests)",
        }
    elif request.validation_mode == "compile_only":
        return {
            "status": "confirmed",
            "message": "Validation mode set to: compile_only (skip tests)",
        }
    else:  # skip
        return {
            "status": "confirmed",
            "message": "Validation mode set to: skip (no validation - risky!)",
        }


@router.post("/refactor/{session_id}/confirm-push")
async def confirm_push(session_id: str, request: PushConfirmationRequest) -> dict[str, str]:
    """
    Confirm or cancel pushing changes to GitHub.

    Used in interactive-detailed mode when pipeline is waiting for push approval.

    Supports two input formats:
    1. Structured: {"action": "approve"} or {"action": "cancel"}
    2. Natural language: {"user_response": "yes, push it"}

    Example structured request:
        POST /api/refactor/session_123/confirm-push
        {"action": "approve"}

    Example natural language request:
        POST /api/refactor/session_123/confirm-push
        {"user_response": "yes but regenerate the commit message"}

    Example response:
        {
            "status": "confirmed",
            "message": "Push approved, committing and pushing to GitHub"
        }
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    state = active_sessions[session_id]

    # Verify pipeline is waiting for push confirmation
    if state.awaiting_confirmation != "push":
        raise HTTPException(
            status_code=400,
            detail=f"Session not awaiting push confirmation (current: {state.awaiting_confirmation})",
        )

    # Validate input - must have either action or user_response, not both
    if request.action and request.user_response:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'action' (structured) or 'user_response' (natural language), not both",
        )

    if not request.action and not request.user_response:
        raise HTTPException(
            status_code=400, detail="Must provide either 'action' or 'user_response'"
        )

    logger.info(
        f"Push confirmation received: session={session_id}, "
        f"action={request.action or 'natural_language'}, "
        f"user_response={request.user_response[:50] if request.user_response else None}"
    )

    # Put confirmation in queue (orchestrator is waiting for this)
    if session_id in confirmation_queues:
        if request.user_response:
            # Natural language format - orchestrator will use LLM to interpret
            await confirmation_queues[session_id].put({"user_response": request.user_response})
        else:
            # Structured format - direct action with optional overrides
            await confirmation_queues[session_id].put(
                {
                    "action": request.action,
                    "branch_name_override": request.branch_name_override,
                    "commit_message_override": request.commit_message_override,
                }
            )

    if request.user_response:
        return {
            "status": "confirmed",
            "message": "Processing natural language response...",
        }
    elif request.action == "approve":
        return {
            "status": "confirmed",
            "message": "Push approved, committing and pushing to GitHub",
        }
    else:
        return {
            "status": "cancelled",
            "message": "Push cancelled, changes will not be pushed",
        }


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

    Optimization: Repository cloning is deferred until after conversational intent check.
    If it's just a greeting, we skip cloning entirely.
    """
    repository_path = None
    try:
        logger.info(f"Pipeline started: {session_id}")

        # Get state
        state = active_sessions[session_id]

        # Configure orchestrator dependencies WITHOUT repository initially
        # Repository will be cloned inside orchestrator only if needed
        deps = OrchestratorDependencies(
            user_id=request.user_id,
            session_id=session_id,
            pipeline_state=state,
            repository_url=request.github_credentials.repository_url,
            repository_path=None,  # Will be set after conversational check
            github_credentials=request.github_credentials,
            auto_fix_enabled=request.auto_fix_enabled,
            max_retries=request.max_retries,
            timeout_seconds=request.timeout_seconds,
            enable_user_interaction=(
                request.mode == "interactive" or request.mode == "interactive-detailed"
            ),
            enable_progress_updates=True,
            # Enhanced send_message callback that handles all event types including build_output
            send_message=lambda msg: _send_progress_to_queue(session_id, msg, progress_queue),
            high_risk_threshold=request.high_risk_threshold,
            min_test_coverage=request.min_test_coverage,
        )

        # Create orchestrator
        orchestrator = OrchestratorAgent(deps)

        # Get confirmation queue if in interactive-detailed mode
        confirmation_queue = (
            confirmation_queues.get(session_id) if request.mode == "interactive-detailed" else None
        )

        # Run pipeline with mode and confirmation queue
        # Orchestrator will check conversational intent first, then clone if needed
        final_state = await orchestrator.run(
            request.user_prompt, mode=request.mode, confirmation_queue=confirmation_queue
        )

        # Update stored state
        active_sessions[session_id] = final_state

        # Only send completion message for actual pipeline runs (not conversations)
        # For conversational responses, the orchestrator already sent the greeting message
        is_conversational = final_state.job_spec is None and final_state.plan is None

        if not is_conversational:
            # This was a real pipeline run, send completion summary
            if final_state.is_complete:
                completion_message = "Refactoring completed!"
                files_changed = (
                    final_state.code_changes.total_changes if final_state.code_changes else 0
                )
            else:
                completion_message = "Pipeline failed"
                files_changed = 0

            # Send final update
            final_update = ProgressUpdate(
                session_id=session_id,
                stage=final_state.stage,
                status="completed" if final_state.is_complete else "failed",
                progress=1.0 if final_state.is_complete else final_state.progress_percentage,
                message=completion_message,
                data={
                    "files_changed": files_changed,
                    "validation_passed": (
                        final_state.validation_result.passed
                        if final_state.validation_result
                        else False
                    ),
                },
            )
            await progress_queue.put(final_update)

            # Buffer final update
            if session_id in session_buffers:
                session_buffers[session_id].append(final_update)

        # Signal completion
        await progress_queue.put(None)

        # Buffer completion signal
        if session_id in session_buffers:
            session_buffers[session_id].append(None)

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
        error_update = ProgressUpdate(
            session_id=session_id,
            stage=PipelineStage.FAILED,
            status="failed",
            progress=0.0,
            message=f"Pipeline failed: {str(e)}",
        )
        await progress_queue.put(error_update)

        # Buffer error update
        if session_id in session_buffers:
            session_buffers[session_id].append(error_update)

        # Signal completion
        await progress_queue.put(None)

        # Buffer completion signal
        if session_id in session_buffers:
            session_buffers[session_id].append(None)

    finally:
        # Clean up cloned repository
        if repository_path:
            logger.info(f"Cleaning up repository: {repository_path}")
            cleanup_repository(repository_path)


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

        # Also buffer for late SSE connections
        if session_id in session_buffers:
            session_buffers[session_id].append(update)

    except Exception as e:
        logger.error(f"Failed to send progress update: {e}")


def _send_progress_to_queue(
    session_id: str,
    msg: str,
    queue: asyncio.Queue[ProgressUpdate | None],
) -> None:
    """
    Enhanced progress callback that handles all event types.

    Handles:
    - Simple string messages
    - JSON-serialized ProgressUpdate objects (includes build_output events)

    Args:
        session_id: Session identifier
        msg: Either a simple string message or JSON-serialized ProgressUpdate
        queue: Progress queue for SSE streaming
    """
    try:
        state = active_sessions.get(session_id)
        if not state:
            logger.warning(f"[QUEUE] No state found for session {session_id}")
            return

        # Try to parse as JSON ProgressUpdate first
        try:
            import json

            data = json.loads(msg)

            # If it's already a ProgressUpdate dict, create object and send
            if isinstance(data, dict) and "session_id" in data:
                update = ProgressUpdate(**data)
                logger.info(
                    f"[QUEUE] Parsed ProgressUpdate: event_type={update.event_type}, message={update.message[:50]}..."
                )
                asyncio.create_task(queue.put(update))

                # Also buffer for late SSE connections
                if session_id in session_buffers:
                    session_buffers[session_id].append(update)
                    logger.debug(
                        f"[QUEUE] Buffered update (buffer size: {len(session_buffers[session_id])})"
                    )
                return
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            # Not JSON, treat as simple string message
            logger.debug(f"[QUEUE] Not JSON, treating as string: {str(e)[:100]}")
            pass

        # Fallback: treat as simple string message
        logger.info(f"[QUEUE] Creating simple ProgressUpdate: {msg[:50]}...")
        update = ProgressUpdate(
            session_id=session_id,
            stage=state.stage,
            status=state.status.value if hasattr(state.status, "value") else str(state.status),
            progress=state.progress_percentage,
            message=msg,
        )
        asyncio.create_task(queue.put(update))

        # Also buffer for late SSE connections
        if session_id in session_buffers:
            session_buffers[session_id].append(update)
            logger.debug(
                f"[QUEUE] Buffered simple update (buffer size: {len(session_buffers[session_id])})"
            )

    except Exception as e:
        logger.error(f"Failed to send progress to queue: {e}", exc_info=True)


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
