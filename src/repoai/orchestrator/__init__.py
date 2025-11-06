"""
Orchestrator package for RepoAI.

Coordinates multi-agent refactoring pipeline with intelligent error recovery.

Two orchestrator types:
1. OrchestratorAgent - Autonomous execution (API endpoints, background jobs)
2. ChatOrchestrator - Interactive with user confirmations (WebSocket, chat UI)

Example Usage:

    # Autonomous (API)
    from repoai.orchestrator import OrchestratorAgent
    from repoai.dependencies import OrchestratorDependencies

    deps = OrchestratorDependencies(
        user_id="user_123",
        session_id="session_456",
        auto_fix_enabled=True,
        max_retries=3
    )

    orchestrator = OrchestratorAgent(deps)
    state = await orchestrator.run("Add JWT authentication")

    if state.is_complete:
        print(f"Success! {state.code_changes.files_modified} files changed")

    # Interactive (Chat)
    from repoai.orchestrator import ChatOrchestrator

    def send_msg(msg: str):
        websocket.send(msg)

    def get_input(prompt: str) -> str:
        return websocket.receive()

    deps = OrchestratorDependencies(
        user_id="user_123",
        session_id="session_456",
        enable_user_interaction=True,
        send_message=send_msg,
        get_user_input=get_input,
        enable_progress_updates=True
    )

    chat_orchestrator = ChatOrchestrator(deps)
    state = await chat_orchestrator.run("Add JWT authentication")

    # User will be asked to:
    # 1. Confirm plan after generation
    # 2. Review high-risk changes
    # 3. Decide on retry strategies
"""

# from .chat_orchestrator import ChatOrchestrator
from .models import PipelineStage, PipelineState, PipelineStatus
from .orchestrator_agent import OrchestratorAgent

__all__ = [
    "OrchestratorAgent",
    # "ChatOrchestrator",
    "PipelineStage",
    "PipelineState",
    "PipelineStatus",
]
