"""
Chat-Enabled Orchestrator Agent

Extends the base Orchestrator to handle conversational interactions.
This is the agent that talks to users via chat interface.
"""

from __future__ import annotations

from typing import Callable

from repoai.orchestrator import OrchestratorAgent, PipelineStage, PipelineState
from repoai.utils.logger import get_logger

logger = get_logger(__name__)


class ChatOrchestrator(OrchestratorAgent):
    """
    Chat-enabled orchestrator that interacts with users.

    This agent:
    - Sends messages to the chat interface
    - Asks for user input when needed
    - Provides real-time updates
    - Handles user commands (pause, cancel, etc.)

    Example:
        async def send_to_chat(message):
            # Your chat implementation
            await websocket.send(message)

        async def get_from_user(question):
            # Your chat implementation
            return await websocket.receive()

        orchestrator = ChatOrchestrator(
            send_message=send_to_chat,
            get_user_input=get_from_user
        )

        result = await orchestrator.run_with_chat(user_prompt)
    """

    def __init__(
        self,
        send_message: Callable[[str], None] | None = None,
        get_user_input: Callable[[str], str] | None = None,
        **kwargs,
    ):
        """
        Initialize chat-enabled orchestrator.

        Args:
            send_message: Function to send messages to chat UI
            get_user_input: Function to get input from user
            **kwargs: Additional args for base OrchestratorAgent
        """
        super().__init__(**kwargs)
        self.send_message = send_message or self._default_send
        self.get_user_input = get_user_input or self._default_input
        logger.info("Chat Orchestrator initialized")

    def _default_send(self, message: str):
        """Default message sender (prints to console)."""
        print(f"🤖 Agent: {message}")

    async def _default_input(self, question: str) -> str:
        """Default input getter (uses input())."""
        return input(f"🤖 Agent: {question}\n👤 You: ")

    # ========================================================================
    # Chat-Enhanced Pipeline Methods
    # ========================================================================

    async def run_with_chat(
        self,
        user_prompt: str,
        user_id: str = "default_user",
        repository_url: str | None = None,
    ) -> PipelineState:
        """
        Run pipeline with chat interactions.

        Sends updates and asks for input at key decision points.

        Args:
            user_prompt: User's refactoring request
            user_id: User identifier
            repository_url: Optional repository URL

        Returns:
            PipelineState: Final pipeline state
        """
        # Greet user
        await self.send_message(
            f'👋 Hello! I\'ll help you with: "{user_prompt}"\n\n' "Let me analyze your request..."
        )

        # Initialize state
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        state = PipelineState(
            session_id=session_id,
            stage=PipelineStage.INTAKE,
            user_prompt=user_prompt,
            max_retries=self.max_retries,
        )

        try:
            # Stage 1: Intake with confirmation
            await self.send_message("📝 Step 1/5: Understanding your request...")
            state = await self._run_intake(state, user_id, repository_url)

            if not state.job_spec:
                return self._fail(state, "Could not understand request")

            # Ask for confirmation
            confirmed = await self._confirm_intent(state)
            if not confirmed:
                await self.send_message("❌ Request cancelled by user.")
                return self._fail(state, "User cancelled")

            # Stage 2: Planning with risk approval
            await self.send_message("\n🎯 Step 2/5: Creating execution plan...")
            state = await self._run_planner(state)

            if not state.plan:
                return self._fail(state, "Could not create plan")

            # Show plan summary
            await self._show_plan_summary(state)

            # Ask for approval if high risk
            if state.plan.risk_assessment.overall_risk_level >= 7:
                approved = await self._approve_high_risk_plan(state)
                if not approved:
                    await self.send_message("❌ High-risk plan rejected.")
                    return self._fail(state, "User rejected high-risk plan")

            # Stage 3-4: Transform & Validate Loop with updates
            await self.send_message("\n💻 Step 3-4/5: Generating and validating code...")
            state = await self._run_transform_validate_loop_with_chat(state)

            if not state.validation_result or not state.validation_result.passed:
                await self.send_message(
                    f"❌ Validation failed after {state.retry_count} attempts.\n"
                    f"Issues found: {', '.join(state.validation_result.failed_checks)}"
                )
                return self._fail(state, "Validation failed")

            # Stage 5: PR Narration
            await self.send_message("\n📄 Step 5/5: Creating PR description...")
            state = await self._run_pr_narrator(state)

            if not state.pr_description:
                return self._fail(state, "Could not create PR description")

            # Show success
            await self._show_success(state)

            state.stage = PipelineStage.COMPLETE
            return state

        except Exception as e:
            logger.exception(f"Pipeline error: {e}")
            await self.send_message(f"❌ Error: {str(e)}")
            return self._fail(state, str(e))

    # ========================================================================
    # Chat Interaction Methods
    # ========================================================================

    async def _confirm_intent(self, state: PipelineState) -> bool:
        """Ask user to confirm understood intent."""
        job_spec = state.job_spec

        message = f"""
✅ I understood your request as:

**Intent:** {job_spec.intent}
**Target:** {', '.join(job_spec.scope.target_packages)}
**Language:** {job_spec.scope.language}

**Requirements:** ({len(job_spec.requirements)})
{chr(10).join(f'  • {req}' for req in job_spec.requirements[:3])}
{f'  ... and {len(job_spec.requirements) - 3} more' if len(job_spec.requirements) > 3 else ''}

Is this correct? (yes/no)
"""

        await self.send_message(message)
        response = await self.get_user_input("Confirm (yes/no): ")

        return response.lower() in ["yes", "y", "ok", "correct", "confirm"]

    async def _show_plan_summary(self, state: PipelineState):
        """Show plan summary to user."""
        plan = state.plan

        message = f"""
✅ Plan created successfully!

**Steps:** {plan.total_steps}
**Risk Level:** {plan.risk_assessment.overall_risk_level}/10
**Estimated Duration:** {plan.estimated_duration}

**Key Steps:**
{chr(10).join(f'  {i+1}. {step.action}: {step.description[:60]}...' for i, step in enumerate(plan.steps[:5]))}
{f'  ... and {plan.total_steps - 5} more steps' if plan.total_steps > 5 else ''}

**Affected Modules:**
{chr(10).join(f'  • {module}' for module in plan.risk_assessment.affected_modules[:5])}
"""

        await self.send_message(message)

    async def _approve_high_risk_plan(self, state: PipelineState) -> bool:
        """Ask user to approve high-risk plan."""
        plan = state.plan
        risk = plan.risk_assessment

        message = f"""
⚠️  **High-Risk Refactoring Detected**

**Risk Level:** {risk.overall_risk_level}/10

**Risk Factors:**
{chr(10).join(f'  • {factor}' for factor in [
    f"Breaking changes: {risk.breaking_changes}",
    f"Compilation risk: {risk.compilation_risk}",
    f"Affected modules: {len(risk.affected_modules)}"
])}

**Mitigation Strategies:**
{chr(10).join(f'  • {strategy}' for strategy in risk.mitigation_strategies[:3])}

Do you want to proceed? (yes/no)
"""

        await self.send_message(message)
        response = await self.get_user_input("Approve (yes/no): ")

        return response.lower() in ["yes", "y", "proceed", "ok"]

    async def _run_transform_validate_loop_with_chat(self, state: PipelineState) -> PipelineState:
        """
        Transform-Validate loop with chat updates.
        """
        while state.retry_count <= state.max_retries:
            attempt = state.retry_count + 1

            if state.retry_count > 0:
                await self.send_message(f"\n🔄 Retry attempt {attempt}/{state.max_retries + 1}...")

            # Transform
            await self.send_message("  ⚙️  Generating code...")
            state = await self._run_transformer(state)

            if not state.code_changes:
                await self.send_message("  ❌ Code generation failed")
                break

            await self.send_message(
                f"  ✅ Generated {state.code_changes.total_changes} files "
                f"(+{state.code_changes.lines_added} lines)"
            )

            # Validate
            await self.send_message("  🔍 Validating code quality...")
            state = await self._run_validator(state)

            if not state.validation_result:
                await self.send_message("  ❌ Validation failed")
                break

            # Check result
            validation = state.validation_result

            if validation.passed:
                await self.send_message(
                    f"  ✅ Validation passed! "
                    f"(Confidence: {validation.confidence.overall_confidence:.0%}, "
                    f"Coverage: {validation.test_coverage:.0%})"
                )
                return state

            # Failed - show issues
            await self.send_message(
                f"  ⚠️  Validation issues found:\n"
                f"{chr(10).join(f'    • {check}' for check in validation.failed_checks[:3])}"
            )

            # Check if we can retry
            if not state.can_retry:
                await self.send_message("  ❌ Max retries reached")
                break

            # Ask user about retry
            if self.auto_fix_enabled:
                await self.send_message("  🔧 Attempting auto-fix...")
                state = await self._attempt_fix(state)
            else:
                retry = await self._ask_retry(state)
                if not retry:
                    await self.send_message("  ❌ User chose not to retry")
                    break
                state = await self._attempt_fix(state)

            state.retry_count += 1

        return state

    async def _ask_retry(self, state: PipelineState) -> bool:
        """Ask user if they want to retry after validation failure."""
        message = f"""
Validation failed. Would you like to:
1. Auto-fix and retry
2. Cancel

Choice (1/2):
"""
        await self.send_message(message)
        response = await self.get_user_input("Your choice: ")

        return response in ["1", "retry", "fix", "yes"]

    async def _show_success(self, state: PipelineState):
        """Show success message with results."""
        pr_desc = state.pr_description
        validation = state.validation_result

        message = f"""
🎉 **Refactoring Complete!**

**Summary:**
{pr_desc.summary[:200]}...

**Changes:**
  • {state.code_changes.files_created} files created
  • {state.code_changes.files_modified} files modified
  • {state.code_changes.lines_added} lines added

**Quality:**
  • Validation: ✅ PASSED
  • Confidence: {validation.confidence.overall_confidence:.0%}
  • Test Coverage: {validation.test_coverage:.0%}
  • Retries needed: {state.retry_count}

**PR Title:**
{pr_desc.title}

**Next Steps:**
1. Review the generated code
2. Run tests in your environment
3. Create pull request with the description

Would you like to see the full PR description? (yes/no)
"""

        await self.send_message(message)
        response = await self.get_user_input("Show PR description? (yes/no): ")

        if response.lower() in ["yes", "y", "show"]:
            await self.send_message(f"\n{pr_desc.to_markdown()}")


# ============================================================================
# Usage Examples
# ============================================================================


async def example_console_chat():
    """Example using console (stdin/stdout) as chat interface."""

    def send_to_console(message: str):
        print(f"\n🤖 RepoAI: {message}\n")

    async def get_from_console(question: str) -> str:
        return input(f"🤖 RepoAI: {question}\n👤 You: ")

    orchestrator = ChatOrchestrator(
        send_message=send_to_console,
        get_user_input=get_from_console,
        max_retries=3,
        auto_fix_enabled=True,
    )

    # Get user request
    user_prompt = input("👤 What refactoring would you like? ")

    # Run with chat
    result = await orchestrator.run_with_chat(user_prompt)

    if result.stage == PipelineStage.COMPLETE:
        print("\n✅ Success! PR description saved.")
    else:
        print(f"\n❌ Failed at {result.stage}")


async def example_websocket_chat():
    """Example using WebSocket as chat interface."""

    # Pseudo-code for WebSocket integration
    class WebSocketChat:
        def __init__(self, websocket):
            self.websocket = websocket

        async def send(self, message: str):
            await self.websocket.send_json({"type": "message", "content": message})

        async def receive(self, question: str) -> str:
            await self.websocket.send_json({"type": "question", "content": question})
            response = await self.websocket.receive_json()
            return response["answer"]

    # Usage
    # chat = WebSocketChat(websocket)
    # orchestrator = ChatOrchestrator(
    #     send_message=chat.send,
    #     get_user_input=chat.receive
    # )
    # result = await orchestrator.run_with_chat(user_prompt)


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_console_chat())
