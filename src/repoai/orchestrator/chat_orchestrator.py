"""
ChatOrchestrator - Interactive orchestrator with user confirmations.

Extends OrchestratorAgent with user interaction capabilities:
- Asks for confirmations at key decision points
- Shows progress updates
- Allows plan modification/regeneration
- Handles high-risk and low-confidence scenarios

Example:
    def send_msg(msg: str):
        websocket.send(msg)

    def get_input(prompt: str) -> str:
        return websocket.receive()

    deps = OrchestratorDependencies(
        user_id="user_123",
        session_id="session_456",
        enable_user_interaction=True,
        send_message=send_msg,
        get_user_input=get_input
    )

    chat_orchestrator = ChatOrchestrator(deps)
    result = await chat_orchestrator.run("Add JWT authentication")
"""

from __future__ import annotations

import time

from repoai.agents import run_planner_agent
from repoai.dependencies import OrchestratorDependencies, PlannerDependencies
from repoai.models import RefactorPlan
from repoai.utils.logger import get_logger

from .models import PipelineStage, PipelineStatus, PipelineUpdateMessage
from .orchestrator_agent import OrchestratorAgent

logger = get_logger(__name__)


class ChatOrchestrator(OrchestratorAgent):
    """
    Interactive orchestrator with user confirmations.

    Extends base OrchestratorAgent with chat-based interaction:
    - Progress updates via send_message callback
    - User confirmations via get_user_input callback
    - Plan review and modification support
    - Risk-based approval workflows

    Example:
        orchestrator = ChatOrchestrator(deps)
        await orchestrator.run("Add JWT auth")

        # User will be asked for confirmations at:
        # 1. After plan generation (if high-risk or user requests)
        # 2. Before code transformation (if plan has breaking changes)
        # 3. After validation failures (retry decision)
    """

    def __init__(self, dependencies: OrchestratorDependencies):
        """
        Initialize ChatOrchestrator.

        Args:
            dependencies: Orchestrator dependencies with chat callbacks
        """
        super().__init__(dependencies)

        if not self.deps.enable_user_interaction:
            logger.warning(
                "User Interaction disabled - ChatOrchestrator will behave like base OrchestratorAgent."
            )

        if not self.deps.send_message:
            logger.warning(
                "send_message callback not provided - progress updates will not be sent."
            )

        if not self.deps.get_user_input:
            logger.warning(
                "get_user_input callback not provided - user confirmations will be skipped."
            )

    def send_message(self, message: str, data: dict[str, object] | None = None) -> None:
        """
        Send message to user via callback.

        Args:
            message: Message text
            data: Optional additional data
        """
        if not self.deps.send_message:
            logger.debug(f"Message (no callback): {message}")
            return

        try:
            self.deps.send_message(message)
            logger.debug(f"Sent message: {message[:100]}...")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    def get_user_input(self, prompt: str) -> str:
        """
        Get input from user via callback.

        Args:
            prompt: Input prompt

        Returns:
            User's input string
        """
        if not self.deps.get_user_input:
            logger.warning(f"User input requested but no callback: {prompt}")
            return ""

        try:
            response = self.deps.get_user_input(prompt)
            logger.debug(f"User response: {response[:50]}...")
            return response
        except Exception as e:
            logger.error(f"Failed to get user input: {e}")
            return ""

    def send_progress_update(
        self,
        stage: PipelineStage,
        message: str,
        data: dict[str, object] | None = None,
    ) -> None:
        """
        Send structured progress update.

        Args:
            stage: Current pipeline stage
            message: Status message
            data: Optional additional data
        """
        if not self.deps.enable_progress_updates:
            return

        update = PipelineUpdateMessage(
            session_id=self.state.session_id,
            stage=stage,
            status=self.state.status.value,
            progress=self.state.progress_percentage,
            message=message,
            data=data,
        )

        # Send as JSON if callback expects it
        import json

        self.send_message(json.dumps(update.model_dump()))

    async def _run_planning_stage(self) -> None:
        """
        Run Planner Agent with user confirmation support.

        After generating plan, asks user to:
        1. Approve plan
        2. Request modifications
        3. Regenerate plan with new instructions
        """
        if not self.state.job_spec:
            raise RuntimeError("JobSpec not available - run Intake stage first")

        # Initial plan generation
        await self._generate_plan()

        # Ask for user confirmation if interaction enabled
        if self.deps.enable_user_interaction:
            await self._confirm_plan()

    async def _generate_plan(self) -> None:
        """Generate refactor plan (can be called multiple times)."""
        self.state.stage = PipelineStage.PLANNING
        self.state.status = PipelineStatus.RUNNING
        stage_start = time.time()

        self.send_progress_update(
            PipelineStage.PLANNING,
            "Creating refactoring plan...",
            {"job_intent": self.state.job_spec.intent if self.state.job_spec else "unknown"},
        )

        logger.info("Running Planner Agent...")

        # Prepare dependencies
        planner_deps = PlannerDependencies(
            job_spec=self.state.job_spec,  # type: ignore
            repository_path=self.deps.repository_path,
            repository_url=self.deps.repository_url,
        )

        # Run Planner Agent
        if not self.state.job_spec:
            raise RuntimeError("JobSpec not available - run Intake stage first")

        plan, metadata = await run_planner_agent(
            self.state.job_spec,
            planner_deps,
            self.adapter,
        )

        self.state.plan = plan
        duration_ms = (time.time() - stage_start) * 1000
        self.state.record_stage_time(PipelineStage.PLANNING, duration_ms)

        logger.info(
            f"Planning completed: {plan.total_steps} steps, "
            f"risk={plan.risk_assessment.overall_risk_level}/10"
        )

    async def _confirm_plan(self) -> None:
        """
        Ask user to confirm or modify the plan.

        Workflow:
        1. Show plan summary
        2. Ask for approval
        3. If rejected:
           a. Ask for modification instructions
           b. Regenerate plan
           c. Repeat confirmation
        """
        if not self.state.plan:
            return

        plan = self.state.plan

        while True:
            # Build plan summary
            summary = self._build_plan_summary(plan)

            # Send plan to user
            self.send_message(f"\n📋 **Refactoring Plan**\n{summary}")

            # Check if approval needed
            needs_approval = self._should_approve_plan(plan)

            if not needs_approval:
                logger.info("Plan approved automatically (low risk)")
                self.send_message("✓ Plan approved automatically (low risk)")
                break

            # Ask for confirmation
            self.state.status = PipelineStatus.PAUSED
            self.send_message(
                "\n❓ **Plan Confirmation Required**\n"
                "Options:\n"
                "  - 'approve' - Proceed with this plan\n"
                "  - 'modify: <instructions>' - Regenerate with modifications\n"
                "  - 'reject' - Cancel refactoring"
            )

            response = self.get_user_input("Your decision:").strip().lower()

            # Record confirmation
            self.state.user_confirmations.append(
                {
                    "stage": "planning",
                    "prompt": "Plan confirmation",
                    "response": response,
                    "timestamp": str(time.time()),
                }
            )

            # Use LLM to interpret user intent
            decision = await self._interpret_user_intent(response, summary)

            # Handle decision based on LLM analysis
            if decision.action == "approve":
                logger.info(f"User approved plan (confidence={decision.confidence:.2f})")
                self.send_message(
                    f"✓ Plan approved! {decision.reasoning}\n" "Proceeding to code generation..."
                )
                self.state.status = PipelineStatus.RUNNING
                break

            elif decision.action == "modify":
                if not decision.modifications:
                    logger.warning("Modify action without modifications - asking user to clarify")
                    self.send_message(
                        "⚠️ I understand you want to modify the plan, but I need more details. "
                        "Please specify what changes you'd like."
                    )
                    continue

                logger.info(
                    f"User requested modifications (confidence={decision.confidence:.2f}): "
                    f"{decision.modifications[:100]}"
                )

                self.send_message(
                    f"🔄 {decision.reasoning}\n" f"Regenerating plan with: {decision.modifications}"
                )

                # Regenerate plan with updated instructions
                await self._regenerate_plan_with_modifications(decision.modifications)

                # Loop continues to show new plan

            elif decision.action == "abort":
                logger.info(f"User rejected plan (confidence={decision.confidence:.2f})")
                self.send_message(f"✗ {decision.reasoning}\n" "Refactoring cancelled.")
                raise RuntimeError("User rejected refactoring plan")

            elif decision.action == "clarify":
                logger.info(
                    f"Unclear user intent (confidence={decision.confidence:.2f}), "
                    "asking for clarification"
                )
                self.send_message(
                    f"❓ {decision.reasoning}\n\n"
                    "Please clarify your response:\n"
                    "  - Type 'approve' to proceed with the plan\n"
                    "  - Type 'modify: <your changes>' to update the plan\n"
                    "  - Type 'reject' to cancel"
                )
                # Loop continues to ask again

            else:
                # Fallback for unexpected actions (skip, escalate, retry)
                logger.warning(
                    f"Unexpected action '{decision.action}' for plan confirmation - "
                    "treating as clarify"
                )
                self.send_message(
                    f"⚠️ I couldn't understand your response clearly. {decision.reasoning}\n"
                    "Please use: 'approve', 'modify: <instructions>', or 'reject'"
                )
                # Loop continues to ask again

    async def _regenerate_plan_with_modifications(self, modifications: str) -> None:
        """
        Regenerate plan with user modifications.

        Args:
            modifications: User's modification instructions
        """
        if not self.state.job_spec:
            return

        logger.info(f"Regenerating plan with modifications: {modifications}")

        # Update job spec with modification context
        # (In practice, you might update requirements or add context)
        original_requirements = self.state.job_spec.requirements.copy()
        self.state.job_spec.requirements.append(f"User modification: {modifications}")

        try:
            # Regenerate plan
            await self._generate_plan()

            logger.info("Plan regenerated successfully")
            self.send_message("✓ Plan regenerated with your modifications")

        except Exception as e:
            logger.error(f"Failed to regenerate plan: {e}")
            self.send_message(f"❌ Failed to regenerate plan: {e}")

            # Restore original requirements
            self.state.job_spec.requirements = original_requirements
            raise

    def _build_plan_summary(self, plan: RefactorPlan) -> str:
        """Build human-readable plan summary."""
        lines = [
            f"**Plan ID:** {plan.plan_id}",
            f"**Total Steps:** {plan.total_steps}",
            f"**Estimated Duration:** {plan.estimated_duration}",
            f"**Risk Level:** {plan.risk_assessment.overall_risk_level}/10",
            "",
            "**Steps:**",
        ]

        for step in plan.steps[:10]:  # Show first 10 steps
            risk_emoji = "🔴" if step.risk_level >= 7 else "🟡" if step.risk_level >= 4 else "🟢"
            lines.append(
                f"  {step.step_number}. {risk_emoji} {step.action} - {step.description[:80]}..."
            )

        if plan.total_steps > 10:
            lines.append(f"  ... and {plan.total_steps - 10} more steps")

        lines.extend(
            [
                "",
                "**Risk Assessment:**",
                f"  - Breaking Changes: {'Yes ⚠️' if plan.risk_assessment.breaking_changes else 'No ✓'}",
                f"  - Compilation Risk: {'Yes' if plan.risk_assessment.compilation_risk else 'No'}",
                f"  - Affected Modules: {', '.join(plan.risk_assessment.affected_modules[:3])}",
            ]
        )

        if plan.risk_assessment.mitigation_strategies:
            lines.append("\n**Mitigation Strategies:**")
            for strategy in plan.risk_assessment.mitigation_strategies[:3]:
                lines.append(f"  - {strategy}")

        return "\n".join(lines)

    def _should_approve_plan(self, plan: RefactorPlan) -> bool:
        """
        Determine if plan requires user approval.

        Approval needed if:
        - High risk (>= threshold)
        - Breaking changes
        - User interaction enabled

        Args:
            plan: Refactor plan

        Returns:
            bool: True if approval needed
        """
        if not self.deps.enable_user_interaction:
            return False

        # High risk requires approval
        if plan.risk_assessment.overall_risk_level >= self.deps.high_risk_threshold:
            logger.info(
                f"Plan requires approval: high risk "
                f"({plan.risk_assessment.overall_risk_level}/10)"
            )
            return True

        # Breaking changes require approval
        if plan.risk_assessment.breaking_changes and not self.deps.allow_breaking_changes:
            logger.info("Plan requires approval: breaking changes detected")
            return True

        # Low risk - no approval needed
        return False

    async def _run_transformation_stage(self) -> None:
        """Run Transformer Agent with progress updates."""
        self.send_progress_update(
            PipelineStage.TRANSFORMATION,
            "Generating code changes...",
            {"total_steps": self.state.plan.total_steps if self.state.plan else 0},
        )

        # Call base implementation
        await super()._run_transformation_stage()

        self.send_progress_update(
            PipelineStage.TRANSFORMATION,
            f"✓ Generated {self.state.code_changes.files_modified if self.state.code_changes else 0} files",
            {
                "files_modified": (
                    self.state.code_changes.files_modified if self.state.code_changes else 0
                ),
                "lines_added": (
                    self.state.code_changes.lines_added if self.state.code_changes else 0
                ),
            },
        )

    async def _run_validation_stage(self) -> None:
        """Run Validator Agent with interactive retry decisions."""
        self.send_progress_update(
            PipelineStage.VALIDATION, "Validating code changes...", {"retry_count": 0}
        )

        # Call base implementation (handles validation logic)
        await super()._run_validation_stage()

        # Send validation results
        if self.state.validation_result:
            if self.state.validation_result.passed:
                self.send_message(
                    f"✅ **Validation Passed!**\n"
                    f"  - Confidence: {self.state.validation_result.confidence.overall_confidence:.2%}\n"
                    f"  - Coverage: {self.state.validation_result.test_coverage:.2%}"
                )
            else:
                self.send_message(
                    f"⚠️ **Validation Issues Detected**\n"
                    f"  - Failed Checks: {len(self.state.validation_result.failed_checks)}\n"
                    f"  - Retries Used: {self.state.retry_count}/{self.state.max_retries}"
                )

    async def _attempt_fix(self, validation_result) -> None:  # type: ignore
        """
        Attempt fix with user notification.

        Overrides base implementation to add progress updates.
        """
        self.send_progress_update(
            PipelineStage.VALIDATION,
            f"Analyzing errors and attempting fix (retry {self.state.retry_count})...",
            {"retry_count": self.state.retry_count, "max_retries": self.state.max_retries},
        )

        # Call base implementation
        await super()._attempt_fix(validation_result)

        self.send_message(
            f"🔄 Fix applied - re-validating code (retry {self.state.retry_count})..."
        )

    async def _run_narration_stage(self) -> None:
        """Run PR Narrator Agent with progress updates."""
        self.send_progress_update(
            PipelineStage.NARRATION,
            "Creating PR description...",
            {"plan_id": self.state.plan.plan_id if self.state.plan else "unknown"},
        )

        # Call base implementation
        await super()._run_narration_stage()

        # Show PR description
        if self.state.pr_description:
            self.send_message(
                f"\n📝 **PR Description Created**\n"
                f"**Title:** {self.state.pr_description.title}\n"
                f"**Summary:** {self.state.pr_description.summary[:200]}...\n"
                f"**Files Changed:** {len(self.state.pr_description.changes_by_file)}"
            )
