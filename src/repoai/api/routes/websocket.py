"""
WebSocket routes for interactive refactoring.

Supports ChatOrchestrator with real-time user interaction:
- Progress updates
- Plan confirmations
- Modification requests
- Error notifications
"""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from repoai.dependencies import OrchestratorDependencies
from repoai.orchestrator import ChatOrchestrator, PipelineStage, PipelineState, PipelineStatus
from repoai.utils.logger import get_logger

from ..models import UserConfirmationRequest

logger = get_logger(__name__)

router = APIRouter()

# Active Websocket connections
active_websockets: dict[str, WebSocket] = {}

# User response queues for interactive mode
user_response_queues: dict[str, asyncio.Queue[str]] = {}


@router.websocket("/refactor/{session_id}")
async def websocket_refactor(websocket: WebSocket, session_id: str) -> None:
    """
    WebSocket endpoint for interactive refactoring.

    Flow:
    1. Client connects
    2. Server runs ChatOrchestrator
    3. Server sends progress updates
    4. Server requests user confirmations when needed
    5. Client responds with decisions
    6. Server continues pipeline
    7. Connection closes when complete

    Message Types (Server → Client):
    - progress: {"type": "progress", "data": {...}}
    - confirmation_request: {"type": "confirmation", "data": {...}}
    - error: {"type": "error", "message": "..."}
    - complete: {"type": "complete", "result": {...}}

    Message Types (Client → Server):
    - confirmation_response: {"type": "response", "response": "approve", ...}
    """
    await websocket.accept()
    logger.info(f"WebSocket connected: session_id={session_id}")

    try:
        # Register WebSocket
        active_websockets[session_id] = websocket

        # Create response queue for user input
        response_queue: asyncio.Queue[str] = asyncio.Queue()
        user_response_queues[session_id] = response_queue  # Get initial request from client
        data = await websocket.receive_json()

        if data.get("type") != "start":
            await websocket.send_json(
                {"type": "error", "message": "First message must be 'start' with refactor request"}
            )
            return

        request_data = data.get("data", {})
        user_id = request_data.get("user_id")
        user_prompt = request_data.get("user_prompt")
        github_creds = request_data.get("github_credentials", {})

        if not user_prompt:
            await websocket.send_json(
                {"type": "error", "message": "Missing user_prompt in request"}
            )
            return

        # Run interactive pipeline
        await run_interactive_pipeline(
            websocket=websocket,
            session_id=session_id,
            user_id=user_id or "anonymous",
            user_prompt=user_prompt,
            repository_url=github_creds.get("repository_url"),
            response_queue=response_queue,
        )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {session_id}, {e}", exc_info=True)
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        # Cleanup
        active_websockets.pop(session_id, None)
        user_response_queues.pop(session_id, None)
        await websocket.close()
        logger.info(f"WebSocket closed: {session_id}")


async def run_interactive_pipeline(
    websocket: WebSocket,
    session_id: str,
    user_id: str,
    user_prompt: str,
    repository_url: str | None,
    response_queue: asyncio.Queue[str],
) -> None:
    """
    Run ChatOrchestrator with WebSocket communication.
    """
    logger.info(f"Starting interactive pipeline: {session_id}")

    # Initialize pipeline state
    state = PipelineState(
        session_id=session_id,
        user_id=user_id,
        user_prompt=user_prompt,
        max_retries=3,
        stage=PipelineStage.IDLE,
        status=PipelineStatus.PENDING,
    )

    # Create send/receive callbacks for ChatOrchestrator
    def send_message(msg: str) -> None:
        """Send message to client (sync callback)."""
        try:
            # Parse if JSON, otherwise send as text
            try:
                data = json.loads(msg)
                msg_type = "progress"
            except json.JSONDecodeError:
                data = {"message": msg}
                msg_type = "message"

            asyncio.create_task(websocket.send_json({"type": msg_type, "data": data}))
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    def get_user_input(prompt: str) -> str:
        """
        Get user input (sync callback).

        Sends confirmation request and waits for response.
        """
        try:
            # Send confirmation request
            request = UserConfirmationRequest(
                session_id=session_id,
                prompt_type="generic",
                prompt=prompt,
                options=["approve", "modify", "reject"],
            )

            asyncio.create_task(
                websocket.send_json({"type": "confirmation", "data": request.model_dump()})
            )

            # Wait for response (blocking, but we're in async context)
            loop = asyncio.get_event_loop()
            response: str = loop.run_until_complete(response_queue.get())

            logger.info(f"Received user response: {response}")
            return response

        except Exception as e:
            logger.error(f"Failed to get user input: {e}")
            return "approve"  # Default to proceed

    # Start listener for user responses
    asyncio.create_task(listen_for_responses(websocket, response_queue))

    try:
        # TODO: Clone GitHub repository for validation
        # - Extract access_token, repository_url, branch from github_credentials
        # - Clone repository to temporary directory
        # - Set repository_path in OrchestratorDependencies
        # - This enables Maven/Gradle validation during pipeline execution
        # - Clean up cloned repo after pipeline completion
        repository_path = None  # Will be set after implementing clone logic

        # Configure orchestrator with WebSocket callbacks
        deps = OrchestratorDependencies(
            user_id=user_id,
            session_id=session_id,
            pipeline_state=state,
            repository_url=repository_url,
            repository_path=repository_path,  # TODO: Set after cloning repo
            enable_user_interaction=True,
            enable_progress_updates=True,
            send_message=send_message,
            get_user_input=get_user_input,
            auto_fix_enabled=True,
            max_retries=3,
            high_risk_threshold=6,
        )

        # Create ChatOrchestrator
        orchestrator = ChatOrchestrator(deps)

        # Run pipeline
        final_state = await orchestrator.run(user_prompt)

        # Send completion
        await websocket.send_json(
            {
                "type": "complete",
                "data": {
                    "session_id": session_id,
                    "success": final_state.is_complete,
                    "result": final_state.to_dict(),
                },
            }
        )

        logger.info(f"Interactive pipeline completed: {session_id}")

    except Exception as e:
        logger.error(f"Interactive pipeline failed: {e}", exc_info=True)
        await websocket.send_json({"type": "error", "message": str(e)})


async def listen_for_responses(websocket: WebSocket, response_queue: asyncio.Queue[str]) -> None:
    """
    Listen for user responses from WebSocket.

    Puts responses in queue for orchestrator to consume.
    """
    try:
        while True:
            message = await websocket.receive_json()

            if message.get("type") == "response":
                # User confirmation response
                response_data = message.get("data", {})
                response = response_data.get("response", "")

                # Handle modification with additional context
                if response.startswith("modify") and response_data.get("additional_context"):
                    response = f"modify: {response_data['additional_context']}"

                await response_queue.put(response)
                logger.debug(f"Queued user response: {response}")

            elif message.get("type") == "cancel":
                # User cancelled
                await response_queue.put("reject")
                logger.info("User cancelled refactoring")
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected during listen")
    except Exception as e:
        logger.error(f"Error listening for responses: {e}")
