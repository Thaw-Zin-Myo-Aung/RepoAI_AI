"""
OrchestratorAgent - Base class for pipeline orchestration.

Coordinates all agents in the refactoring pipeline:
1. Intake Agent - Parse user request
2. Planner Agent - Create refactor plan
3. Transformer Agent - Generate code
4. Validator Agent - Validate changes
5. PR Narrator Agent - Create PR description

Handles intelligent error recovery using LLM-powered analysis.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from asyncio import Queue

    from repoai.dependencies import (
        OrchestratorDependencies,
    )
from repoai.llm import ModelRole, PydanticAIAdapter
from repoai.models import (
    CodeChange,
    CodeChanges,
    ValidationResult,
)
from repoai.utils.file_operations import apply_code_change, create_backup_directory
from repoai.utils.logger import get_logger

from .models import OrchestratorDecision, PipelineStage, PipelineState, PipelineStatus
from .prompts import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    RETRY_STRATEGY_INSTRUCTIONS,
    USER_INTENT_INSTRUCTIONS,
)

logger = get_logger(__name__)


class OrchestratorAgent:
    """
    Base orchestrator for autonomous pipeline execution.

    Coordinates all agents and handles intelligent error recovery.
    Does not include user interaction - use ChatOrchestrator for that.

    Example:
        deps = OrchestratorDependencies(
            user_id="user_123",
            session_id="session_456",
            auto_fix_enabled=True
        )

        orchestrator = OrchestratorAgent(deps)
        result = await orchestrator.run("Add JWT authentication")
    """

    def __init__(self, dependencies: OrchestratorDependencies):
        """
        Initialize OrchestratorAgent.

        Args:
            dependencies: Orchestrator dependencies
        """
        self.deps = dependencies
        self.adapter = PydanticAIAdapter()

        # Store confirmation queue for interactive-detailed mode
        self.confirmation_queue: Queue[dict[str, object]] | None = None

        # Track execution mode
        self.mode: str = "autonomous"

        # Initialize or user provided pipeline state
        if self.deps.pipeline_state:
            self.state = self.deps.pipeline_state
        else:
            self.state = PipelineState(
                session_id=self.deps.session_id,
                user_id=self.deps.user_id,
                max_retries=self.deps.max_retries,
            )

        logger.info(
            f"OrchestratorAgent initialized: "
            f"session={self.state.session_id}, "
            f"user={self.state.user_id}"
        )

    def _send_progress(
        self,
        message: str,
        event_type: str | None = None,
        file_path: str | None = None,
        requires_confirmation: bool = False,
        confirmation_type: str | None = None,
        additional_data: dict[str, object] | None = None,
    ) -> None:
        """
        Send progress update via callback if configured.

        Args:
            message: Progress message to send
            event_type: Specific event type (plan_ready, file_created, etc.)
            file_path: File being processed (if applicable)
            requires_confirmation: Whether this event requires user confirmation
            confirmation_type: Type of confirmation needed ('plan' or 'push')
            additional_data: Additional structured data (e.g., file contents, diffs)
        """
        if self.deps.enable_progress_updates and self.deps.send_message:
            try:
                # For enhanced progress updates (SSE), send structured data
                if event_type or file_path or requires_confirmation or additional_data:
                    from repoai.api.models import ProgressUpdate

                    progress_update = ProgressUpdate(
                        session_id=self.state.session_id,
                        stage=self.state.stage,
                        status=self.state.status.value,
                        progress=self.state.progress_percentage / 100.0,
                        message=message,
                        event_type=event_type,
                        file_path=file_path,
                        requires_confirmation=requires_confirmation,
                        confirmation_type=confirmation_type,
                        data=additional_data,
                    )
                    self.deps.send_message(progress_update.model_dump_json())
                else:
                    # For simple progress messages
                    self.deps.send_message(message)
            except Exception as e:
                logger.warning(f"Failed to send progress update: {e}")

    async def run(
        self,
        user_prompt: str,
        mode: str = "autonomous",
        confirmation_queue: Queue[dict[str, object]] | None = None,
    ) -> PipelineState:
        """
        Execute the complete refactoring pipeline.

        Args:
            user_prompt: User's refactoring request
            mode: Execution mode ('autonomous', 'interactive', 'interactive-detailed')
            confirmation_queue: Queue for receiving user confirmations (required for interactive-detailed)

        Returns:
            PipelineState: Complete pipeline state with all results

        Example:
        state = await orchestrator.run("Add JWT authentication to user service")
            if state.is_complete:
                print(f"Success! {state.code_changes.files_modified} files changed")
        """
        self.state.user_prompt = user_prompt
        self.state.status = PipelineStatus.RUNNING
        self.state.start_time = time.time()
        self.mode = mode
        self.confirmation_queue = confirmation_queue

        logger.info(f"Starting pipeline (mode={mode}): {user_prompt[:100]}...")

        # Pre-flight check: detect conversational intents
        conversational_response = await self._check_conversational_intent(user_prompt)
        if conversational_response:
            # This is a greeting/question, not a refactoring request
            logger.info(
                f"Detected conversational intent, responding: {conversational_response[:100]}..."
            )
            self._send_progress(conversational_response)

            # Update state to indicate this was a conversation, not a pipeline run
            self.state.status = PipelineStatus.COMPLETED
            self.state.stage = PipelineStage.COMPLETE
            self.state.end_time = time.time()

            return self.state

        # Not conversational - this is a real refactoring job
        # Now clone the repository if we haven't already
        if self.deps.repository_url and not self.deps.repository_path:
            logger.info("Cloning repository for refactoring pipeline...")
            self._send_progress(f"📦 Cloning repository: {self.deps.repository_url}")

            try:
                from repoai.utils.git_utils import clone_repository

                # Get credentials, use defaults if not provided
                access_token = (
                    self.deps.github_credentials.access_token
                    if self.deps.github_credentials
                    else "mock_token_for_testing"
                )
                branch = (
                    self.deps.github_credentials.branch if self.deps.github_credentials else "main"
                )

                repo_path = clone_repository(
                    repo_url=self.deps.repository_url,
                    access_token=access_token,
                    branch=branch,
                )
                self.deps.repository_path = str(repo_path)
                logger.info(f"✅ Repository cloned to: {self.deps.repository_path}")
                self._send_progress("✅ Repository cloned successfully")

            except Exception as clone_exc:
                logger.error(f"Repository clone failed: {clone_exc}")
                self.state.errors.append(f"Failed to clone repository: {clone_exc}")
                self.state.status = PipelineStatus.FAILED
                self.state.stage = PipelineStage.FAILED
                self.state.end_time = time.time()
                self._send_progress(f"❌ Clone failed: {clone_exc}")
                return self.state

        self._send_progress(f"🚀 Starting pipeline: {user_prompt[:80]}...")

        # Ensure Java test files and pom.xml are valid before build/validation
        if self.deps.repository_path:
            from repoai.utils.java_build_utils import verify_and_fix_java_tests

            verify_and_fix_java_tests(self.deps.repository_path)

        try:
            # Stage 1: Intake
            self._send_progress("📥 Stage 1: Analyzing refactoring request...")
            await self._run_intake_stage()
            self._send_progress(
                f"✅ Intake complete: {self.state.job_spec.intent if self.state.job_spec else 'processed'}"
            )

            # Stage 2: Planning
            self._send_progress("📋 Stage 2: Creating refactoring plan...")
            await self._run_planning_stage()
            self._send_progress(
                f"✅ Plan created: {self.state.plan.total_steps if self.state.plan else 0} steps"
            )

            # Stage 2.5: Plan Confirmation (interactive-detailed mode only)
            if self._is_interactive_detailed():
                await self._wait_for_plan_confirmation()

            # Stage 3: Transformation (with streaming)
            self._send_progress("🔨 Stage 3: Generating code changes...")
            await self._run_transformation_stage_streaming()
            self._send_progress(
                f"✅ Code generated: {self.state.code_changes.files_modified if self.state.code_changes else 0} files modified"
            )

            # Stage 3.5: Validation Confirmation (interactive-detailed mode only)
            validation_mode = "full"  # default: full validation with tests
            if self._is_interactive_detailed():
                validation_mode = await self._wait_for_validation_confirmation()

            # Stage 4: Validation (single run: compilation and tests)
            if validation_mode != "skip":
                self._send_progress(
                    "🔍 Stage 4: Validating code changes (compilation and tests)..."
                )
                await self._run_validation_stage(skip_tests=False)
                validation_status = (
                    "passed"
                    if self.state.validation_result and self.state.validation_result.passed
                    else "completed"
                )
                self._send_progress(f"✅ Validation {validation_status}")
            else:
                self._send_progress("⏭️  Validation skipped by user")
                # Create a basic validation result for skipped validation
                from repoai.explainability.confidence import ConfidenceMetrics
                from repoai.models import ValidationResult

                self.state.validation_result = ValidationResult(
                    plan_id=self.state.plan.plan_id if self.state.plan else "unknown",
                    passed=True,
                    compilation_passed=True,
                    test_coverage=0.0,
                    confidence=ConfidenceMetrics(
                        overall_confidence=1.0,
                        reasoning_quality=1.0,
                        code_safety=0.5,  # Lower since we skipped validation
                        test_coverage=0.0,
                    ),
                    recommendations=["Validation was skipped by user request"],
                )

            # If validation failed, notify user but continue to PR narration and push
            if self.state.validation_result and not self.state.validation_result.passed:
                self.state.stage = PipelineStage.VALIDATION
                self.state.status = PipelineStatus.FAILED
                self.state.add_error("Validation failed after retry attempts")
                self._send_progress(
                    "❌ Validation failed after retries. You may still commit/push these changes.",
                    event_type="validation_failed",
                    additional_data={
                        "error_summary": self._build_error_summary(self.state.validation_result),
                        "failed_checks": getattr(self.state.validation_result, "failed_checks", []),
                        "compilation_passed": getattr(
                            self.state.validation_result, "compilation_passed", None
                        ),
                    },
                )

            # Stage 5: PR Narration
            self._send_progress("📝 Stage 5: Creating PR description...")
            await self._run_narration_stage()
            self._send_progress("✅ PR description ready")

            # Stage 5.5: Push Confirmation (interactive-detailed mode only)
            if self._is_interactive_detailed():
                await self._wait_for_push_confirmation()

            # Stage 6: Git Operations (if we have GitHub credentials)
            if self.deps.github_credentials:
                self._send_progress(
                    "🔀 Stage 6: Executing git operations...", event_type="stage_started"
                )
                await self._run_git_operations_stage()

                # Give time for git operation messages to be sent
                await asyncio.sleep(0.1)

                # Build branch URL for final message
                repo_url = self.deps.github_credentials.repository_url.rstrip("/")
                if repo_url.endswith(".git"):
                    repo_url = repo_url[:-4]
                branch_url = f"{repo_url}/tree/{self.state.git_branch_name}"

                self._send_progress(
                    "✅ Git operations completed",
                    event_type="stage_completed",
                    additional_data={"branch_url": branch_url},
                )

            # Give time for all messages to flush before completion
            await asyncio.sleep(0.1)

            # Mark as complete
            self.state.stage = PipelineStage.COMPLETE
            self.state.status = PipelineStatus.COMPLETED
            self.state.end_time = time.time()

            # Build completion message with validation result
            validation_status = (
                "Passed"
                if (self.state.validation_result and self.state.validation_result.passed)
                else "Failed"
            )
            completion_msg = f"🎉 Refactoring completed! Validation: {validation_status} ({self.state.elapsed_time_ms/1000:.1f}s)"
            self._send_progress(
                completion_msg,
                event_type="pipeline_completed",
                additional_data={
                    "validation_result": (
                        self.state.validation_result.model_dump()
                        if self.state.validation_result
                        else None
                    )
                },
            )

            if self.deps.github_credentials and self.state.git_branch_name:
                # Send branch link as final message
                repo_url = self.deps.github_credentials.repository_url.rstrip("/")
                if repo_url.endswith(".git"):
                    repo_url = repo_url[:-4]
                branch_url = f"{repo_url}/tree/{self.state.git_branch_name}"
                self._send_progress(
                    f"📋 Review your changes: {branch_url}",
                    event_type="branch_link",
                    additional_data={"branch_url": branch_url},
                )

            logger.info(
                f"Pipeline completed successfully: "
                f"{self.state.elapsed_time_ms:.0f}ms, "
                f"{self.state.code_changes.files_modified if self.state.code_changes else 0} files"
            )
            # Pipeline finished — perform optional cleanup of cloned repo and backup
            try:
                from pathlib import Path

                from repoai.utils.file_operations import cleanup_backup, cleanup_cloned_repo

                # Cleanup backup directory if present
                if hasattr(self.state, "backup_directory") and self.state.backup_directory:
                    backup_dir = Path(self.state.backup_directory)
                    logger.info(f"Cleaning up backup directory: {backup_dir}")
                    await cleanup_backup(backup_dir)

                # Cleanup cloned repository if it appears to be in 'cloned_repos'
                if self.deps.repository_path:
                    repo_dir = Path(self.deps.repository_path)
                    logger.info(f"Attempting to cleanup cloned repository: {repo_dir}")
                    await cleanup_cloned_repo(repo_dir)
            except Exception as e:
                logger.warning(f"Cleanup after completion failed: {e}")

        except Exception as e:
            self.state.stage = PipelineStage.FAILED
            self.state.status = PipelineStatus.FAILED
            self.state.add_error(f"Pipeline failed: {str(e)}")
            self.state.end_time = time.time()

            self._send_progress(f"❌ Pipeline failed: {str(e)[:100]}")
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            # On failure attempt cleanup of backup and cloned repo (best-effort)
            try:
                from pathlib import Path

                from repoai.utils.file_operations import cleanup_backup, cleanup_cloned_repo

                if hasattr(self.state, "backup_directory") and self.state.backup_directory:
                    backup_dir = Path(self.state.backup_directory)
                    logger.info(f"Cleaning up backup directory after failure: {backup_dir}")
                    await cleanup_backup(backup_dir)

                if self.deps.repository_path:
                    repo_dir = Path(self.deps.repository_path)
                    logger.info(
                        f"Attempting to cleanup cloned repository after failure: {repo_dir}"
                    )
                    await cleanup_cloned_repo(repo_dir)
            except Exception as e2:
                logger.warning(f"Cleanup after failure failed: {e2}")

        return self.state

    async def _check_conversational_intent(self, user_prompt: str) -> str | None:
        """
        Check if user prompt is conversational (greeting, question) rather than a refactoring request.

        Args:
            user_prompt: User's input text

        Returns:
            Response message if conversational, None if it's a refactoring request

        Example:
            response = await orchestrator._check_conversational_intent("hello")
            if response:
                print(response)  # "👋 Hello! I'm RepoAI..."
        """
        # Quick heuristic check first (avoid LLM call for obvious cases)
        prompt_lower = user_prompt.lower().strip()

        # Strong indicators that this is a refactoring request (highest priority check)
        refactoring_keywords = [
            "refactor",
            "add",
            "create",
            "implement",
            "modify",
            "change",
            "update",
            "migrate",
            "upgrade",
            "fix",
            "improve",
            "extract",
            "rename",
            "move",
            "delete",
            "remove",
            "replace",
            "optimize",
            "enhance",
            "class",
            "method",
            "function",
            "code",
            "repository",
            "service",
            "controller",
            "module",
            "component",
            "file",
            "package",
            "dependency",
            "test",
            "junit",
            "spring",
            "encapsulation",
            "readability",
            "behaviour",
            "validation",
            "register",
        ]

        # If prompt contains ANY refactoring keyword, treat as refactoring (skip all other checks)
        if any(keyword in prompt_lower for keyword in refactoring_keywords):
            return None  # This is definitely a refactoring request

        # Only check conversational intent for prompts WITHOUT refactoring keywords

        # Greetings (short, simple)
        greetings = [
            "hi",
            "hello",
            "hey",
            "good morning",
            "good afternoon",
            "good evening",
            "greetings",
        ]
        if any(
            prompt_lower == greeting or prompt_lower.startswith(f"{greeting} ")
            for greeting in greetings
        ):
            # Only if the greeting is SHORT (not followed by a refactoring request)
            if len(user_prompt.split()) < 5:
                return (
                    "👋 Hello! I'm **RepoAI**, your intelligent code refactoring assistant.\n\n"
                    "I can help you:\n"
                    "- 🔨 Refactor and modernize your codebase\n"
                    "- ✨ Add new features to your application\n"
                    "- 🐛 Fix bugs and improve code quality\n"
                    "- 📦 Migrate to new frameworks or libraries\n\n"
                    "Just describe what you'd like me to do with your code, and I'll create a plan, "
                    "make the changes, validate them, and prepare everything for a pull request!\n\n"
                    "**Example requests:**\n"
                    '- "Add JWT authentication to the user service"\n'
                    '- "Refactor the payment module to use async/await"\n'
                    '- "Migrate from JUnit 4 to JUnit 5"'
                )

        # Questions about capabilities (short questions only)
        capability_keywords = [
            "what can you do",
            "what do you do",
            "help me",
            "how does this work",
            "what is repoai",
            "what are you",
            "who are you",
            "capabilities",
        ]
        if len(user_prompt.split()) < 15 and any(
            keyword in prompt_lower for keyword in capability_keywords
        ):
            return (
                "🤖 I'm **RepoAI**, an AI-powered code refactoring assistant!\n\n"
                "**What I can do:**\n\n"
                "1. **Analyze** your refactoring request using natural language\n"
                "2. **Plan** a detailed strategy for the changes\n"
                "3. **Generate** the necessary code modifications\n"
                "4. **Validate** changes by compiling and running tests\n"
                "5. **Create** comprehensive PR descriptions\n"
                "6. **Push** changes to GitHub when you're ready\n\n"
                "**I work with:**\n"
                "- Java (Spring Boot, Maven, Gradle)\n"
                "- Python (FastAPI, Django, Flask)\n"
                "- JavaScript/TypeScript (Node.js, React)\n\n"
                '**Example:** Tell me "Add caching to the database queries" and I\'ll handle the rest!'
            )

        # Thanks/goodbye
        if len(user_prompt.split()) < 5 and any(
            keyword in prompt_lower for keyword in ["thanks", "thank you", "bye", "goodbye"]
        ):
            return (
                "👍 You're welcome! Feel free to ask me to refactor your code anytime.\n\n"
                "Happy coding! 🚀"
            )

        # If we reach here and prompt is very short (< 10 words), use LLM
        # For longer prompts, assume it's refactoring (avoids expensive LLM calls)
        if len(user_prompt.split()) >= 10:
            return None  # Long prompts are likely refactoring requests

        # Use LLM for short, ambiguous prompts only
        try:
            prompt = f"""Analyze this user input and determine if it's a conversational message (greeting, question about capabilities, small talk) or a code refactoring request.

**User Input:** "{user_prompt}"

**Your Task:**
- If it's conversational (greeting, question, small talk): respond with "CONVERSATIONAL"
- If it's a refactoring/coding request: respond with "REFACTORING"

**Examples:**
- "hi there" → CONVERSATIONAL
- "what can you do?" → CONVERSATIONAL
- "Add JWT auth" → REFACTORING
- "Refactor the database layer" → REFACTORING
- "how are you?" → CONVERSATIONAL
- "Migrate to Python 3.12" → REFACTORING

Respond with ONLY ONE WORD: either "CONVERSATIONAL" or "REFACTORING"."""

            result = await self.adapter.run_raw_async(
                role=ModelRole.ORCHESTRATOR,
                messages=[{"content": prompt}],
                temperature=0.1,
                max_output_tokens=10,
                use_fallback=True,
            )

            classification = result.strip().upper()

            if "CONVERSATIONAL" in classification:
                # Generate a friendly response
                return (
                    "👋 Hi there! I'm RepoAI, your code refactoring assistant.\n\n"
                    "I specialize in making intelligent code changes to your repository. "
                    "Just describe what you'd like me to refactor or improve, and I'll handle the rest!\n\n"
                    "**Try asking me to:**\n"
                    "- Add new features to your code\n"
                    "- Refactor existing modules\n"
                    "- Migrate to new frameworks\n"
                    "- Improve code quality\n\n"
                    "What would you like me to help you with?"
                )

            # If REFACTORING or unclear, let it proceed as normal
            return None

        except Exception as e:
            logger.warning(f"Failed to check conversational intent: {e}")
            # If LLM fails, assume it's a refactoring request to be safe
            return None

    async def _run_intake_stage(self) -> None:
        """Run Intake Agent to parse user request."""
        from repoai.agents.intake_agent import run_intake_agent
        from repoai.dependencies import IntakeDependencies

        self.state.stage = PipelineStage.INTAKE
        stage_start = time.time()

        logger.info("Running Intake Agent...")

        # Prepare dependencies
        intake_deps = IntakeDependencies(
            user_id=self.state.user_id,
            session_id=self.state.session_id,
            repository_url=self.deps.repository_url,
            code_context=None,  # TODO: Add code context from repo
        )

        # Run Intake Agent
        job_spec, metadata = await run_intake_agent(
            self.state.user_prompt, intake_deps, self.adapter
        )

        self.state.job_spec = job_spec
        duration_ms = (time.time() - stage_start) * 1000
        self.state.record_stage_time(PipelineStage.INTAKE, duration_ms)

        logger.info(
            f"Intake completed: intent='{job_spec.intent}', "
            f"packages={len(job_spec.scope.target_packages)}, "
            f"time={duration_ms:.0f}ms"
        )

    async def _run_planning_stage(self) -> None:
        """Run Planner Agent to create refactor plan."""
        from repoai.agents.planner_agent import run_planner_agent
        from repoai.dependencies import PlannerDependencies

        if not self.state.job_spec:
            raise RuntimeError("JobSpec not available - run Intake stage first")

        self.state.stage = PipelineStage.PLANNING
        stage_start = time.time()

        logger.info("Running Planner Agent...")

        # Prepare dependencies
        planner_deps = PlannerDependencies(
            job_spec=self.state.job_spec,
            repository_path=self.deps.repository_path,
            repository_url=self.deps.repository_url,
        )

        # Run Planner Agent
        plan, metadata = await run_planner_agent(self.state.job_spec, planner_deps, self.adapter)

        self.state.plan = plan
        duration_ms = (time.time() - stage_start) * 1000
        self.state.record_stage_time(PipelineStage.PLANNING, duration_ms)

        logger.info(
            f"Planning completed: {plan.total_steps} steps, "
            f"risk={plan.risk_assessment.overall_risk_level}/10, "
            f"time={duration_ms:.0f}ms"
        )

    async def _regenerate_plan_with_modifications(
        self, validation_result: ValidationResult, modifications: str
    ) -> None:
        """
        Regenerate plan with modification instructions from validation errors.

        Args:
            validation_result: The failed validation result
            modifications: Modification instructions from LLM
        """
        from repoai.agents.planner_agent import run_planner_agent
        from repoai.dependencies import PlannerDependencies

        if not self.state.job_spec:
            raise RuntimeError("JobSpec not available")

        logger.info("Regenerating plan with modifications...")

        # Build enhanced requirements list with modifications
        error_summary = self._build_error_summary(validation_result)

        # Add modification instructions to requirements
        enhanced_requirements = list(self.state.job_spec.requirements)
        enhanced_requirements.append(f"CRITICAL - Address validation errors: {modifications}")
        enhanced_requirements.append(f"Previous validation errors: {error_summary[:500]}")

        # Update job spec with enhanced requirements
        from repoai.models import JobSpec

        modified_job_spec = JobSpec(
            job_id=f"{self.state.job_spec.job_id}_modified",
            intent=self.state.job_spec.intent,
            scope=self.state.job_spec.scope,
            requirements=enhanced_requirements,
            constraints=self.state.job_spec.constraints,
        )

        # Prepare dependencies
        planner_deps = PlannerDependencies(
            job_spec=modified_job_spec,
            repository_path=self.deps.repository_path,
            repository_url=self.deps.repository_url,
        )

        # Re-run Planner Agent with modifications
        plan, metadata = await run_planner_agent(modified_job_spec, planner_deps, self.adapter)

        self.state.plan = plan
        logger.info(
            f"Plan regenerated: {plan.total_steps} steps, "
            f"risk={plan.risk_assessment.overall_risk_level}/10"
        )

    async def _run_transformation_stage(self) -> None:
        """Run Transformer Agent to generate code."""
        from repoai.dependencies import TransformerDependencies

        if not self.state.plan:
            raise RuntimeError("RefactorPlan not available - run Planning stage first")

        self.state.stage = PipelineStage.TRANSFORMATION
        stage_start = time.time()

        logger.info("Running Transformer Agent...")

        # Prepare dependencies
        transformer_deps = TransformerDependencies(
            plan=self.state.plan,
            repository_path=self.deps.repository_path,
            repository_url=self.deps.repository_url,
            write_to_disk=True,
            output_path=self.deps.output_path,
            batch_size=self.deps.transformer_batch_size,
            max_tokens=self.deps.transformer_max_tokens,
        )

        # Run Transformer Agent
        from repoai.agents.transformer_agent import run_transformer_and_fix

        code_changes = await run_transformer_and_fix(
            self.adapter, self.state.plan, transformer_deps
        )
        self.state.code_changes = code_changes

        duration_ms = (time.time() - stage_start) * 1000
        self.state.record_stage_time(PipelineStage.TRANSFORMATION, duration_ms)

        logger.info(
            f"Transformation completed: {code_changes.files_modified} files, "
            f"+{code_changes.lines_added}/-{code_changes.lines_removed} lines, "
            f"time={duration_ms:.0f}ms"
        )

    async def _run_transformation_stage_streaming(self, is_retry: bool = False) -> None:
        """
        Run Transformer Agent with streaming and real-time file application.

        This version streams code changes as they're generated and applies them
        immediately to the cloned repository.

        Note: This should only be called for initial transformation. On validation failures,
              use generate_fixes_for_errors() for targeted fixes instead.

        Args:
            is_retry: Deprecated parameter, kept for backward compatibility
        """
        from repoai.agents.transformer_agent import transform_with_streaming
        from repoai.dependencies import TransformerDependencies

        if not self.state.plan:
            raise RuntimeError("RefactorPlan not available - run Planning stage first")

        if not self.deps.repository_path:
            raise RuntimeError("Repository path not set - clone repository first")

        self.state.stage = PipelineStage.TRANSFORMATION
        stage_start = time.time()

        if is_retry:
            logger.info("Running Transformer Agent (retry mode - fixing validation errors)...")
        else:
            logger.info("Running Transformer Agent (streaming mode)...")

        # Create backup before applying changes (only on first run, not retry)
        from pathlib import Path

        repo_path = Path(self.deps.repository_path)

        if is_retry and hasattr(self.state, "backup_directory") and self.state.backup_directory:
            # Reuse existing backup for retry
            backup_dir = Path(self.state.backup_directory)
            logger.info(f"Reusing existing backup for retry: {backup_dir}")
        else:
            # Create new backup for first transformation
            backup_dir = await create_backup_directory(repo_path)
            self.state.backup_directory = str(backup_dir)
            logger.info(f"Created backup: {backup_dir}")

        # Prepare dependencies
        transformer_deps = TransformerDependencies(
            plan=self.state.plan,
            repository_path=self.deps.repository_path,
            repository_url=self.deps.repository_url,
            write_to_disk=True,
            output_path=self.deps.output_path,
        )

        # Add fix instructions to dependencies if available (for retry scenarios)
        if self.state.fix_instructions:
            logger.info(
                f"Including fix instructions in transformer context ({len(self.state.fix_instructions)} chars)"
            )
            # Store fix instructions in a way transformer can access them
            # We'll pass them through the dependencies
            transformer_deps.fix_instructions = self.state.fix_instructions

        # Track changes and progress
        all_changes: list[CodeChange] = []
        files_applied = 0
        total_lines_added = 0
        total_lines_removed = 0

        try:
            # Create progress callback for transformer to stream step-level updates
            def transformer_progress(message: str) -> None:
                """Forward transformer progress messages to SSE with proper event type."""
                logger.info(f"[TRANSFORMER_CALLBACK] Received: {message}")

                # Determine event type from message content
                event_type = "transformer_progress"  # Default
                additional_data: dict[str, object] | None = None

                # Batch-level events (new format from transformer)
                if message.startswith("Proceeding Batch") or "Proceeding Batch" in message:
                    event_type = "batch_started"
                    logger.info("[TRANSFORMER_CALLBACK] Detected batch_started")
                elif message.startswith("Batch") and "Completed" in message:
                    event_type = "batch_completed"
                    # For batch completion, include summary data if available
                    if "Files changed" in message or "Files changed (" in message:
                        # Extract file summary from message
                        try:
                            lines = message.split("\n")
                            file_lines = [
                                line.strip() for line in lines if line.strip().startswith("•")
                            ]
                            additional_data = {
                                "files_summary": file_lines,
                                "files_count": len(file_lines),
                            }
                        except Exception:
                            pass
                elif "failed" in message.lower() or "❌" in message:
                    event_type = "step_failed"
                # Dependency events
                elif "Adding dependency" in message or "Adding common dependency" in message:
                    event_type = "dependency_adding"
                elif "Added dependency" in message:
                    event_type = "dependency_added"
                    # Extract dependency name from message
                    try:
                        # Format: "Added dependency org.springframework:spring-context:6.1.0"
                        if ":" in message:
                            dep_parts = message.split("dependency")[-1].strip()
                            additional_data = {"dependency": dep_parts}
                    except Exception:
                        pass
                # File generation events
                elif "Generating code" in message or "⏳" in message:
                    event_type = "code_generating"

                # Always send progress with event type
                self._send_progress(
                    message,
                    event_type=event_type,
                    additional_data=additional_data,
                )

            # Stream code changes and apply immediately
            async for code_change, _metadata in transform_with_streaming(
                self.state.plan,
                transformer_deps,
                self.adapter,
                transformer_progress,
                batch_size=transformer_deps.batch_size,
            ):
                # Apply file immediately to repository
                try:
                    await apply_code_change(code_change, repo_path, backup_dir)
                    files_applied += 1

                    # Track metrics
                    total_lines_added += code_change.lines_added
                    total_lines_removed += code_change.lines_removed

                    # Collect change
                    all_changes.append(code_change)

                    # Send progress update with file content details
                    self._send_progress(
                        f"✓ Generated & applied: {code_change.file_path} "
                        f"(+{code_change.lines_added}/-{code_change.lines_removed}) "
                        f"[{files_applied} files]",
                        event_type=f"file_{code_change.change_type.lower()}",
                        file_path=code_change.file_path,
                        additional_data={
                            "operation": code_change.change_type,
                            "file_path": code_change.file_path,
                            "class_name": code_change.class_name,
                            "package_name": code_change.package_name,
                            "original_content": code_change.original_content,  # Old content (for edited files)
                            "modified_content": code_change.modified_content,  # New content
                            "diff": code_change.diff,  # Unified diff
                            "lines_added": code_change.lines_added,
                            "lines_removed": code_change.lines_removed,
                            "imports_added": code_change.imports_added,
                            "methods_added": code_change.methods_added,
                            "annotations_added": code_change.annotations_added,
                        },
                    )

                    logger.info(
                        f"Applied {code_change.change_type}: {code_change.file_path} "
                        f"({files_applied}/{len(all_changes) + 1})"
                    )

                except Exception as e:
                    logger.error(f"Failed to apply {code_change.file_path}: {e}")
                    # Continue with other files
                    self._send_progress(f"⚠️  Failed to apply: {code_change.file_path}")

            # Create CodeChanges object from collected changes
            code_changes = CodeChanges(
                plan_id=self.state.plan.plan_id,
                changes=all_changes,
                files_modified=len(all_changes),
                files_created=sum(1 for c in all_changes if c.change_type == "created"),
                files_deleted=sum(1 for c in all_changes if c.change_type == "deleted"),
                lines_added=total_lines_added,
                lines_removed=total_lines_removed,
            )

            self.state.code_changes = code_changes
            duration_ms = (time.time() - stage_start) * 1000
            self.state.record_stage_time(PipelineStage.TRANSFORMATION, duration_ms)

            logger.info(
                f"Streaming transformation completed: {files_applied} files applied, "
                f"+{total_lines_added}/-{total_lines_removed} lines, "
                f"time={duration_ms:.0f}ms"
            )

        except Exception as e:
            error_msg = str(e)

            # Check if it's a token limit error
            is_token_error = any(
                pattern in error_msg
                for pattern in [
                    "token limit",
                    "Token limit",
                    "MALFORMED_FUNCTION_CALL",
                    "context too large",
                ]
            )

            if is_token_error:
                # Log concisely for token errors
                logger.error(
                    "Transformation failed: Token limit exceeded. "
                    "The prompt was too large for the model to process."
                )
            else:
                # Log full error for other issues
                logger.error(f"Transformation streaming failed: {e}")

            # Restore from backup on failure
            from repoai.utils.file_operations import restore_from_backup

            logger.info("Restoring from backup due to error...")
            await restore_from_backup(backup_dir, repo_path)
            raise

    async def _run_validation_stage(self, skip_tests: bool = False) -> None:
        """Run Validator Agent with intelligent retry on failures and real-time build output streaming.

        Args:
            skip_tests: If True, only compile without running tests. If False, run full validation.
        """
        from repoai.agents.validator_agent import run_validator_agent
        from repoai.dependencies import ValidatorDependencies

        if not self.state.code_changes:
            raise RuntimeError("CodeChanges not available - run Transformation stage first")

        self.state.stage = PipelineStage.VALIDATION
        stage_start = time.time()

        if skip_tests:
            logger.info("Running Validator Agent (compile-only mode)...")
        else:
            logger.info("Running Validator Agent (full validation with tests)...")

        # Create progress callback for build/test output streaming
        async def on_build_output(line: str) -> None:
            """Stream Maven/Gradle output to frontend in real-time."""
            # Send via SSE with special event type for build output
            self._send_progress(
                message=line.rstrip(),  # Remove trailing newline
                event_type="build_output",
                additional_data={
                    "output_type": "validation",
                    "raw_line": line,
                },
            )

        while True:
            # Prepare dependencies WITH progress callback
            validator_deps = ValidatorDependencies(
                code_changes=self.state.code_changes,
                repository_path=self.deps.repository_path,
                min_test_coverage=self.deps.min_test_coverage,
                strict_mode=self.deps.require_all_checks_pass,
                run_tests=not skip_tests,  # Invert: run_tests=False when skip_tests=True
                run_compile=skip_tests,  # If skip_tests True, we want compile-only
                progress_callback=on_build_output,  # Enable real-time streaming
            )

            # Run Validator Agent
            validation_result, metadata = await run_validator_agent(
                self.state.code_changes, validator_deps, self.adapter
            )

            self.state.validation_result = validation_result

            # Check if validation passed
            if validation_result.passed:
                logger.info("✓ Validation passed!")
                break

            # Validation failed
            logger.warning(
                f"✗ Validation failed: {len(validation_result.failed_checks)} checks failed"
            )

            # Check if auto-fix is enabled
            if not self.deps.auto_fix_enabled:
                logger.info("Auto-fix disabled, stopping validation")
                break

            # Check retry limit
            if not self.state.can_retry:
                logger.warning(
                    f"Max retries ({self.state.max_retries}) reached, stopping validation"
                )
                try:
                    # Stream detailed failure reasons to the user before stopping
                    error_summary = self._build_error_summary(validation_result)
                    failed_checks = (
                        validation_result.failed_checks
                        if hasattr(validation_result, "failed_checks")
                        else []
                    )
                    self._send_progress(
                        "❌ Validation failed: maximum retries reached",
                        event_type="validation_failed",
                        additional_data={
                            "error_summary": error_summary,
                            "failed_checks": failed_checks,
                            "compilation_passed": getattr(
                                validation_result, "compilation_passed", None
                            ),
                        },
                    )
                except Exception:
                    logger.debug(
                        "Failed sending detailed validation failure progress", exc_info=True
                    )
                break

            # Use LLM to decide retry strategy
            logger.info(
                f"Analyzing errors for retry decision (attempt {self.state.retry_count + 1})..."
            )
            retry_decision = await self._decide_retry_strategy(validation_result)

            # Handle retry decision
            if retry_decision.action == "retry":
                logger.info(
                    f"LLM decision: RETRY (confidence={retry_decision.confidence:.2f}, "
                    f"success_prob={retry_decision.estimated_success_probability or 0:.2f})"
                )
                logger.info(f"Reasoning: {retry_decision.reasoning}")

                self.state.retry_count += 1
                self.state.status = PipelineStatus.RETRYING

                # Apply fix with optional modifications from LLM
                await self._attempt_fix(validation_result, retry_decision.modifications)

            elif retry_decision.action == "modify":
                logger.info(
                    f"LLM decision: MODIFY plan (confidence={retry_decision.confidence:.2f})"
                )
                logger.info(f"Reasoning: {retry_decision.reasoning}")

                if retry_decision.modifications:
                    logger.info(f"Modifications: {retry_decision.modifications[:200]}...")

                    # Increment retry count for plan modification
                    self.state.retry_count += 1
                    self.state.status = PipelineStatus.RETRYING

                    # Re-run planning stage with modification instructions
                    logger.info("Re-running Planner with modification instructions...")
                    await self._regenerate_plan_with_modifications(
                        validation_result, retry_decision.modifications
                    )

                    # Re-run transformation with new plan (streaming mode)
                    logger.info("Re-running Transformer with modified plan...")
                    await self._run_transformation_stage_streaming()

                    # Continue to next validation attempt
                    continue
                else:
                    logger.warning("No modifications provided, treating as abort")
                    break

            elif retry_decision.action == "abort":
                logger.warning(f"LLM decision: ABORT (confidence={retry_decision.confidence:.2f})")
                logger.warning(f"Reasoning: {retry_decision.reasoning}")
                break

            elif retry_decision.action == "escalate":
                logger.warning(
                    f"LLM decision: ESCALATE (confidence={retry_decision.confidence:.2f})"
                )
                logger.warning(f"Reasoning: {retry_decision.reasoning}")
                # Mark for human review
                self.state.add_warning(
                    f"Escalated: {retry_decision.reasoning}. Human review recommended."
                )
                break

            else:
                # Unexpected action (skip, approve, clarify) - treat as abort
                logger.warning(
                    f"Unexpected retry action '{retry_decision.action}', stopping validation"
                )
                break

        duration_ms = (time.time() - stage_start) * 1000
        self.state.record_stage_time(PipelineStage.VALIDATION, duration_ms)

        logger.info(
            f"Validation completed: passed={validation_result.passed}, "
            f"retries={self.state.retry_count}, "
            f"time={duration_ms:.0f}ms"
        )

    async def _attempt_fix(
        self, validation_result: ValidationResult, llm_modifications: str | None = None
    ) -> None:
        """
        Attempt to fix validation errors using targeted fix generation.

        Uses PLANNER role model to analyze errors and suggest fixes,
        then generates ONLY fixes for the broken files (not all files).

        Args:
            validation_result: Validation result with errors
            llm_modifications: Optional modification instructions from orchestrator LLM decision
        """

        logger.info("Analyzing validation errors with LLM...")

        # If orchestrator provided specific modifications, use those
        if llm_modifications:
            logger.info(f"Using orchestrator-provided modifications: {llm_modifications[:200]}...")
            fix_instructions = llm_modifications
        else:
            # Otherwise, analyze errors with PLANNER model
            # Build error analysis prompt
            error_summary = self._build_error_summary(validation_result)

            # Detect specific error patterns
            missing_symbols = self._extract_missing_symbols(error_summary)
            missing_methods = self._extract_missing_methods(error_summary)

            # Build context-aware prompt
            error_context = ""
            if missing_symbols:
                error_context += "\n**Missing Classes/Symbols Detected:**\n"
                for symbol in missing_symbols:
                    error_context += f"  - {symbol} (needs to be created)\n"

            if missing_methods:
                error_context += "\n**Missing Methods Detected:**\n"
                for method in missing_methods:
                    error_context += f"  - {method} (needs to be added to existing class)\n"

            analysis_prompt = f"""You are analyzing validation errors in generated Java code to provide SPECIFIC fix instructions.

**Validation Issues:**
{error_summary}

{error_context}

**Original Plan:**
- Intent: {self.state.plan.job_id if self.state.plan else 'N/A'}
- Steps: {self.state.plan.total_steps if self.state.plan else 0}
- Risk: {self.state.plan.risk_assessment.overall_risk_level if self.state.plan else 0}/10

**YOUR TASK:**
Analyze the errors and provide SPECIFIC, ACTIONABLE fix instructions that can be directly applied.

**CRITICAL RULES FOR YOUR FIX INSTRUCTIONS:**

1. **DO NOT regenerate from scratch** - Only fix what's broken
2. **Be SPECIFIC** - Mention exact file paths, class names, method signatures
3. **Order matters** - List fixes in dependency order (create missing classes first, then fix code that uses them)
4. **Focus on TEST ERRORS** - Most failures are in test files that don't match refactored main code

**COMMON ERROR PATTERNS AND HOW TO FIX THEM:**

**Pattern 1: Missing class symbols (e.g., "cannot find symbol: class UserRepository")**
→ FIX: The test file is trying to mock/use a class that doesn't exist or was removed
   - If it's a test mock that's no longer needed (class was removed from main code):
     * Remove the @Mock annotation and field from test class
     * Remove it from all test method parameters
     * Update test methods to not use this mock
   - If it's actually needed: Create the class first

**Pattern 2: Missing annotation (e.g., "cannot find symbol: class MockitoExtension")**
→ FIX: Missing import or missing Maven dependency
   - Add import: `import org.mockito.junit.jupiter.MockitoExtension;`
   - Verify dependency exists in pom.xml

**Pattern 3: Wrong constructor arguments (e.g., "required: no arguments, found: int")**
→ FIX: Test is calling old constructor signature, but main class constructor changed
   - Update test to use new constructor signature
   - Example: If UserService now has no-arg constructor, change `new UserService(100)` to `new UserService()`

**Pattern 4: Test file doesn't match refactored main class**
→ FIX: Most common issue! When you refactor main code, tests break
   - If main class removed a dependency → Remove it from test mocks
   - If main class changed method signature → Update test calls
   - If main class changed constructor → Update test instantiation

**OUTPUT FORMAT:**
Provide instructions as a numbered list of SPECIFIC actions:

1. **File: [exact file path]**
   - Problem: [what's wrong]
   - Fix: [exactly what to change]
   - Example: Change line 15 from `new UserService(100)` to `new UserService()`

2. **File: [exact file path]**
   - Problem: [what's wrong]
   - Fix: [exactly what to change]
   
Focus on the ROOT CAUSE, not symptoms. If tests are broken, the root cause is usually:
- Test file wasn't updated after refactoring main class
- Test is mocking classes that were removed
- Test is using old method signatures

**Now analyze the errors above and provide SPECIFIC fix instructions:**
"""

            # Use PLANNER role for intelligent analysis
            fix_instructions = await self.adapter.run_raw_async(
                role=ModelRole.PLANNER,
                messages=[{"content": analysis_prompt}],
                temperature=0.3,
                max_output_tokens=4096,  # Increased for detailed instructions
            )

            logger.info(f"LLM analysis complete: {len(fix_instructions)} chars")
            logger.debug(f"Fix instructions: {fix_instructions[:500]}...")

        # Generate TARGETED fixes for broken files only (not all files)
        logger.info("Generating targeted fixes for broken files...")

        from repoai.agents.transformer_fix_agent import generate_fixes_for_errors
        from repoai.dependencies import TransformerDependencies
        from repoai.utils.file_operations import apply_code_change

        # Validate required state
        if not self.state.plan:
            raise RuntimeError("Plan is required for fix generation")
        if not self.deps.repository_path:
            raise RuntimeError("Repository path is required for fix generation")

        # Prepare dependencies
        transformer_deps = TransformerDependencies(
            plan=self.state.plan,
            repository_path=self.deps.repository_path,
            repository_url=self.deps.repository_url,
            write_to_disk=True,
            output_path=self.deps.output_path,
        )

        # Generate fixes
        fixes = await generate_fixes_for_errors(
            validation_result=validation_result,
            fix_instructions=fix_instructions,
            dependencies=transformer_deps,
            adapter=self.adapter,
        )

        logger.info(f"Generated {len(fixes)} fixes")

        # Apply fixes to repository
        repo_path = Path(self.deps.repository_path)
        backup_dir = Path(self.state.backup_directory) if self.state.backup_directory else None

        if not fixes:
            # Stream fallback SSE event if no fixes
            self._send_progress(
                "No error files found, no fix applied.",
                event_type="fix_attempt",
            )
        else:
            for fix in fixes:
                logger.info(f"Applying fix to {fix.file_path}")
                await apply_code_change(fix, repo_path, backup_dir)

                # Stream file_operation SSE event for each fix
                self._send_progress(
                    f"✓ Applied fix: {fix.file_path} (+{fix.lines_added}/-{fix.lines_removed})",
                    event_type="file_operation",
                    file_path=fix.file_path,
                )

                # Update code_changes state with the fix
                if self.state.code_changes:
                    # Replace or add the fixed file in code_changes
                    existing_idx = next(
                        (
                            i
                            for i, c in enumerate(self.state.code_changes.changes)
                            if c.file_path == fix.file_path
                        ),
                        None,
                    )
                    if existing_idx is not None:
                        self.state.code_changes.changes[existing_idx] = fix
                    else:
                        self.state.code_changes.changes.append(fix)

            logger.info(f"Applied {len(fixes)} fixes to repository")

    def _build_error_summary(self, validation_result: ValidationResult) -> str:
        """Build human-readable error summary from validation result."""
        lines = []

        # Compilation errors - categorize by source type
        if not validation_result.compilation_passed:
            main_errors = []
            test_errors = []

            for check_result in validation_result.checks:
                if check_result.result.compilation_errors:
                    for error in check_result.result.compilation_errors:
                        # Categorize by file path
                        if "/src/test/" in error or "/test/" in error:
                            test_errors.append(error)
                        else:
                            main_errors.append(error)

            if main_errors:
                lines.append("**Main Code Compilation Errors:**")
                for error in main_errors:
                    lines.append(f"  - {error}")

            if test_errors:
                if main_errors:
                    lines.append("")  # Add blank line between categories
                lines.append("**Test Code Compilation Errors:**")
                lines.append("  (Tests need to be updated to match refactored main code)")
                for error in test_errors:
                    lines.append(f"  - {error}")

        # Failed checks
        if validation_result.failed_checks:
            lines.append("\n**Failed Checks:**")
            for check_name in validation_result.failed_checks:
                check = validation_result.get_check(check_name)
                if check and check.issues:
                    lines.append(f"  {check_name}:")
                    for issue in check.issues[:5]:  # Limit to 5 issues per check
                        lines.append(f"    - {issue}")

        # Security vulnerabilities
        if validation_result.security_vulnerabilities:
            lines.append("\n**Security Vulnerabilities:**")
            for vuln in validation_result.security_vulnerabilities:
                lines.append(f"  - {vuln}")

        return "\n".join(lines)

    def _extract_missing_symbols(self, error_summary: str) -> list[str]:
        """Extract missing class/symbol names from compilation errors."""
        import re

        missing_symbols = []
        # Match patterns like "cannot find symbol: class UserRepository"
        pattern = r"cannot find symbol.*?class\s+(\w+)"
        matches = re.findall(pattern, error_summary, re.IGNORECASE)
        missing_symbols.extend(matches)

        # Also match "symbol: class UserRepository"
        pattern2 = r"symbol:\s+class\s+(\w+)"
        matches2 = re.findall(pattern2, error_summary, re.IGNORECASE)
        missing_symbols.extend(matches2)

        # Remove duplicates and return
        return list(set(missing_symbols))

    def _extract_missing_methods(self, error_summary: str) -> list[str]:
        """Extract missing method names from compilation errors."""
        import re

        missing_methods = []
        # Match patterns like "cannot find symbol: method getPassword()"
        pattern = r"cannot find symbol.*?method\s+(\w+\([^)]*\))"
        matches = re.findall(pattern, error_summary, re.IGNORECASE)
        missing_methods.extend(matches)

        # Also match "symbol: method getPassword()"
        pattern2 = r"symbol:\s+method\s+(\w+\([^)]*\))"
        matches2 = re.findall(pattern2, error_summary, re.IGNORECASE)
        missing_methods.extend(matches2)

        # Remove duplicates and return
        return list(set(missing_methods))

    async def _run_narration_stage(self) -> None:
        """Run PR Narrator Agent to create PR description."""
        if not self.state.code_changes or not self.state.validation_result:
            raise RuntimeError(
                "CodeChanges and ValidationResult not available - "
                "run Transformation and Validation first"
            )

        self.state.stage = PipelineStage.NARRATION
        stage_start = time.time()

        logger.info("Running PR Narrator Agent...")

        # Import PR Narrator Agent
        from repoai.agents.pr_narrator_agent import run_pr_narrator_agent
        from repoai.dependencies import PRNarratorDependencies

        # Prepare dependencies
        pr_deps = PRNarratorDependencies(
            code_changes=self.state.code_changes,
            validation_result=self.state.validation_result,
            plan_id=self.state.plan.plan_id if self.state.plan else "unknown",
        )

        # Run PR Narrator Agent to generate comprehensive PR description
        pr_description, pr_metadata = await run_pr_narrator_agent(
            code_changes=self.state.code_changes,
            validation_result=self.state.validation_result,
            dependencies=pr_deps,
            adapter=self.adapter,
        )

        self.state.pr_description = pr_description
        duration_ms = (time.time() - stage_start) * 1000
        self.state.record_stage_time(PipelineStage.NARRATION, duration_ms)

        logger.info(
            f"PR Narration completed: '{pr_description.title}', "
            f"{len(pr_description.changes_by_file)} files documented, "
            f"{len(pr_description.breaking_changes)} breaking changes, "
            f"time={duration_ms:.0f}ms"
        )

    def _is_interactive_detailed(self) -> bool:
        """Check if we're in interactive-detailed mode."""
        return self.mode == "interactive-detailed"

    def _build_plan_summary(self) -> str:
        """
        Build a human-readable plan summary for user confirmation.

        Returns:
            Formatted plan summary with key information
        """
        if not self.state.plan or not self.state.job_spec:
            return "Plan not available"

        plan = self.state.plan
        job = self.state.job_spec

        summary_lines = [
            "# Refactoring Plan Summary",
            "",
            f"**Intent:** {job.intent}",
            f"**Total Steps:** {plan.total_steps}",
            f"**Risk Level:** {plan.risk_assessment.overall_risk_level}/10",
            f"**Breaking Changes:** {'Yes' if plan.risk_assessment.breaking_changes else 'No'}",
            "",
            "## Steps:",
        ]

        for i, step in enumerate(plan.steps[:10], 1):  # Limit to first 10 steps
            summary_lines.append(f"{i}. {step.description}")
            if step.target_files:
                summary_lines.append(f"   Files: {', '.join(step.target_files[:5])}")

        if len(plan.steps) > 10:
            summary_lines.append(f"... and {len(plan.steps) - 10} more steps")

        summary_lines.extend(
            [
                "",
                "## Target Packages:",
                *[f"  - {pkg}" for pkg in job.scope.target_packages[:5]],
            ]
        )

        if len(job.scope.target_packages) > 5:
            summary_lines.append(f"  ... and {len(job.scope.target_packages) - 5} more")

        return "\n".join(summary_lines)

    async def _wait_for_plan_confirmation(self) -> None:
        """
        Wait for user to approve/modify/cancel the refactoring plan.

        This method pauses the pipeline and waits for user confirmation
        via the confirmation queue. Supports both:
        1. Structured format: {"action": "approve", "modifications": "..."}
        2. Natural language: {"user_response": "yes but use Redis instead"}

        The LLM will interpret natural language responses intelligently.

        Raises:
            RuntimeError: If confirmation queue is not available or user cancels
        """
        if not self.confirmation_queue:
            logger.warning("No confirmation queue available, skipping plan confirmation")
            return

        logger.info("Waiting for plan confirmation...")

        # Update pipeline state
        self.state.stage = PipelineStage.AWAITING_PLAN_CONFIRMATION
        self.state.status = PipelineStatus.PAUSED
        self.state.awaiting_confirmation = "plan"

        # Build plan summary
        plan_summary = self._build_plan_summary()
        self.state.confirmation_data = {"plan_summary": plan_summary}

        # Send progress update with confirmation required and plan details
        self._send_progress(
            "⏸️  Plan ready for review - awaiting your confirmation",
            event_type="plan_ready",
            requires_confirmation=True,
            confirmation_type="plan",
            additional_data={
                "plan_summary": plan_summary,
                "plan_id": self.state.plan.plan_id if self.state.plan else None,
                "steps": [
                    {
                        "step_number": step.step_number,
                        "action": step.action,
                        "description": step.description,
                        "target_files": step.target_files,
                        "target_classes": step.target_classes,
                        "dependencies": step.dependencies,
                        "dependency_descriptions": (
                            [
                                f"Step {dep}: {self.state.plan.steps[dep - 1].description}"
                                for dep in step.dependencies
                                if self.state.plan and dep > 0 and dep <= len(self.state.plan.steps)
                            ]
                            if step.dependencies
                            else []
                        ),
                    }
                    for step in (self.state.plan.steps if self.state.plan else [])
                ],
                "estimated_duration": (
                    self.state.plan.estimated_duration if self.state.plan else None
                ),
                "total_steps": len(self.state.plan.steps) if self.state.plan else 0,
            },
        )

        try:
            # Wait for confirmation response (with timeout)
            logger.info("Waiting for user confirmation on plan...")
            confirmation = await asyncio.wait_for(self.confirmation_queue.get(), timeout=3600.0)

            # Check if this is a natural language response
            if "user_response" in confirmation:
                logger.info("Received natural language response, using LLM to interpret...")
                user_response = str(confirmation["user_response"])

                # Use LLM to interpret user intent
                decision = await self._interpret_user_intent(user_response, plan_summary)

                # Map LLM decision to action
                action: str = decision.action
                modifications: str | None = decision.modifications

                logger.info(
                    f"LLM interpreted response: action={action}, "
                    f"confidence={decision.confidence:.2f}, "
                    f"reasoning={decision.reasoning}"
                )
            else:
                # Structured format (backward compatible)
                action_obj = confirmation.get("action")
                modifications_obj = confirmation.get("modifications")

                # Type narrowing
                action = str(action_obj) if action_obj else "cancel"
                modifications = str(modifications_obj) if modifications_obj else None

                logger.info(f"Received structured confirmation: action={action}")

            if action == "approve":
                logger.info("Plan approved by user, continuing pipeline")
                self.state.awaiting_confirmation = None
                self.state.confirmation_data = None
                self.state.status = PipelineStatus.RUNNING
                # Update stage to transformation so pipeline continues
                self.state.stage = PipelineStage.TRANSFORMATION

                # Send progress update that plan was approved
                self._send_progress("✅ Plan approved - starting code generation...")

            elif action == "modify":
                logger.info(
                    f"User requested plan modifications: {str(modifications or '')[:100]}..."
                )

                if not modifications or not isinstance(modifications, str):
                    raise RuntimeError("Modification action requires modification instructions")

                # Regenerate plan with modifications
                self.state.awaiting_confirmation = None
                self.state.confirmation_data = None
                self.state.status = PipelineStatus.RUNNING
                # Go back to planning stage to regenerate plan
                self.state.stage = PipelineStage.PLANNING

                # Send progress update
                self._send_progress("🔄 Regenerating plan with modifications...")

                # Re-run planning with modifications (similar to validation retry)
                if self.state.validation_result:
                    await self._regenerate_plan_with_modifications(
                        self.state.validation_result, modifications
                    )
                else:
                    # Create a dummy validation result for the regeneration
                    from repoai.explainability.confidence import ConfidenceMetrics
                    from repoai.models import ValidationResult as VR

                    dummy_result = VR(
                        plan_id=self.state.plan.plan_id if self.state.plan else "",
                        passed=True,
                        checks=[],
                        test_coverage=0.0,
                        confidence=ConfidenceMetrics(
                            overall_confidence=0.8,
                            reasoning_quality=0.8,
                            code_safety=0.8,
                            test_coverage=0.0,
                        ),
                    )
                    await self._regenerate_plan_with_modifications(dummy_result, modifications)

            elif action == "cancel":
                logger.info("User cancelled the refactoring")
                self.state.status = PipelineStatus.CANCELLED
                raise RuntimeError("Refactoring cancelled by user")

            elif action == "clarify":
                logger.warning("LLM needs clarification from user")
                self.state.status = PipelineStatus.PAUSED
                # Send message back asking for clarification
                self._send_progress(
                    f"⚠️  Could not understand your response. Please clarify: {decision.reasoning if 'decision' in locals() else 'Please provide clearer instructions'}",
                    event_type="clarification_needed",
                    requires_confirmation=True,
                    confirmation_type="plan",
                )
                # Wait for clarification
                await self._wait_for_plan_confirmation()

            else:
                raise RuntimeError(f"Invalid plan confirmation action: {action}")

        except asyncio.TimeoutError:
            logger.error("Plan confirmation timeout (1 hour)")
            self.state.status = PipelineStatus.FAILED
            raise RuntimeError("Plan confirmation timeout - no response from user") from None

    async def _wait_for_validation_confirmation(self) -> str:
        """
        Wait for user to choose validation mode.

        Returns:
            str: Validation mode - \"full\" (compile + tests), \"compile_only\", or \"skip\"

        Raises:
            RuntimeError: If confirmation queue is not available
        """
        if not self.confirmation_queue:
            logger.warning("No confirmation queue available, defaulting to full validation")
            return "full"

        logger.info("Waiting for validation mode confirmation...")

        # Update pipeline state
        self.state.stage = PipelineStage.AWAITING_VALIDATION_CONFIRMATION
        self.state.status = PipelineStatus.PAUSED
        self.state.awaiting_confirmation = "validation"

        # Build validation summary
        validation_summary = f"""# Validation Options

**Files to Validate:** {self.state.code_changes.files_modified if self.state.code_changes else 0} files changed
**Changes:** +{self.state.code_changes.lines_added if self.state.code_changes else 0}/-{self.state.code_changes.lines_removed if self.state.code_changes else 0} lines

Choose validation level:
1. **Full Validation** - Compile code + run all tests (recommended)
2. **Compile Only** - Only check if code compiles, skip tests (faster)
3. **Skip** - Skip validation entirely (not recommended)
"""

        self.state.confirmation_data = {"validation_summary": validation_summary}

        # Send progress update
        self._send_progress(
            "⏸️  Choose validation mode - awaiting your confirmation",
            event_type="validation_ready",
            requires_confirmation=True,
            confirmation_type="validation",
            additional_data={
                "validation_summary": validation_summary,
                "files_changed": (
                    self.state.code_changes.files_modified if self.state.code_changes else 0
                ),
                "lines_added": (
                    self.state.code_changes.lines_added if self.state.code_changes else 0
                ),
                "lines_removed": (
                    self.state.code_changes.lines_removed if self.state.code_changes else 0
                ),
                "validation_passed": (
                    self.state.validation_result.passed if self.state.validation_result else False
                ),
            },
        )

        try:
            # Wait for confirmation response (with timeout)
            logger.info("Waiting for user confirmation on validation mode...")
            confirmation = await asyncio.wait_for(self.confirmation_queue.get(), timeout=3600.0)

            # Check if this is a natural language response
            if "user_response" in confirmation:
                logger.info("Received natural language response, using LLM to interpret...")
                user_response = str(confirmation["user_response"])

                # Use LLM to interpret validation mode intent
                decision = await self._interpret_validation_intent(
                    user_response, validation_summary
                )

                # Extract mode from modifications or reasoning
                mode = "full"  # default
                if decision.modifications:
                    mods_lower = decision.modifications.lower()
                    if "skip" in mods_lower:
                        mode = "skip"
                    elif "compile" in mods_lower and "only" in mods_lower:
                        mode = "compile_only"
                    elif "full" in mods_lower or "test" in mods_lower:
                        mode = "full"

                logger.info(
                    f"LLM interpreted validation mode: {mode}, "
                    f"confidence={decision.confidence:.2f}"
                )

                self.state.awaiting_confirmation = None
                self.state.status = PipelineStatus.RUNNING
                return mode
            else:
                # Structured format
                mode_obj = confirmation.get("validation_mode", "full")
                mode = str(mode_obj)

                logger.info(f"Received structured validation mode: {mode}")

                self.state.awaiting_confirmation = None
                self.state.status = PipelineStatus.RUNNING
                return mode

        except asyncio.TimeoutError:
            logger.error("Validation confirmation timeout (1 hour), defaulting to full validation")
            return "full"

    async def _wait_for_push_confirmation(self) -> None:
        """
        Wait for user to approve/cancel pushing changes to GitHub.

        This method pauses the pipeline and waits for user confirmation
        before executing git operations. Supports both:
        1. Structured format: {"action": "approve", "branch_name_override": "..."}
        2. Natural language: {"user_response": "yes, push it"}

        The LLM will interpret natural language responses intelligently.

        Raises:
            RuntimeError: If confirmation queue is not available or user cancels
        """
        if not self.confirmation_queue:
            logger.warning("No confirmation queue available, skipping push confirmation")
            return

        logger.info("Waiting for push confirmation...")

        # Update pipeline state
        self.state.stage = PipelineStage.AWAITING_PUSH_CONFIRMATION
        self.state.status = PipelineStatus.PAUSED
        self.state.awaiting_confirmation = "push"

        # Build push summary with file changes
        files_changed = []
        if self.state.code_changes:
            for change in self.state.code_changes.changes[:20]:  # Limit to 20 files
                files_changed.append(
                    {
                        "file_path": change.file_path,
                        "change_type": change.change_type,
                        "lines_added": change.lines_added,
                        "lines_removed": change.lines_removed,
                    }
                )

        # Build push summary for LLM context
        push_summary_lines = [
            "# Push Confirmation",
            "",
            f"**Files Changed:** {self.state.code_changes.files_modified if self.state.code_changes else 0}",
            f"**Validation:** {'✅ Passed' if self.state.validation_result and self.state.validation_result.passed else '❌ Failed'}",
            "",
        ]

        if self.state.pr_description:
            push_summary_lines.extend(
                [
                    "## PR Description",
                    f"**Title:** {self.state.pr_description.title}",
                    f"**Summary:** {self.state.pr_description.summary[:200]}...",
                    "",
                ]
            )

        push_summary_lines.extend(
            [
                "## Files to Push:",
                *[
                    f"  - {change['file_path']} ({change['change_type']})"
                    for change in files_changed[:10]
                ],
            ]
        )

        if len(files_changed) > 10:
            push_summary_lines.append(f"  ... and {len(files_changed) - 10} more files")

        push_summary = "\n".join(push_summary_lines)

        self.state.confirmation_data = {
            "files_changed": files_changed,
            "total_files": self.state.code_changes.files_modified if self.state.code_changes else 0,
            "validation_passed": (
                self.state.validation_result.passed if self.state.validation_result else False
            ),
            "push_summary": push_summary,
        }

        # Send progress update with confirmation required and push details
        self._send_progress(
            "⏸️  Code changes ready - awaiting push confirmation",
            event_type="push_ready",
            requires_confirmation=True,
            confirmation_type="push",
            additional_data={
                "files_changed": files_changed,
                "total_files": (
                    self.state.code_changes.files_modified if self.state.code_changes else 0
                ),
                "files_created": (
                    self.state.code_changes.files_created if self.state.code_changes else 0
                ),
                "files_deleted": (
                    self.state.code_changes.files_deleted if self.state.code_changes else 0
                ),
                "lines_added": (
                    self.state.code_changes.lines_added if self.state.code_changes else 0
                ),
                "lines_removed": (
                    self.state.code_changes.lines_removed if self.state.code_changes else 0
                ),
                "validation_passed": (
                    self.state.validation_result.passed if self.state.validation_result else False
                ),
                "validation_summary": (
                    {
                        "compilation_passed": self.state.validation_result.compilation_passed,
                        "test_coverage": self.state.validation_result.test_coverage,
                        "junit_results": (
                            {
                                "tests_run": self.state.validation_result.junit_test_results.tests_run,
                                "tests_passed": self.state.validation_result.junit_test_results.tests_passed,
                                "tests_failed": self.state.validation_result.junit_test_results.tests_failed,
                                "tests_skipped": self.state.validation_result.junit_test_results.tests_skipped,
                            }
                            if self.state.validation_result.junit_test_results
                            else None
                        ),
                    }
                    if self.state.validation_result
                    else None
                ),
                "pr_description": (
                    {
                        "title": self.state.pr_description.title,
                        "summary": self.state.pr_description.summary,
                        "testing_notes": self.state.pr_description.testing_notes,
                    }
                    if self.state.pr_description
                    else None
                ),
                "push_summary": push_summary,
            },
        )

        try:
            # Wait for confirmation response (with timeout)
            logger.info("Waiting for user confirmation on push...")
            confirmation = await asyncio.wait_for(self.confirmation_queue.get(), timeout=3600.0)

            # Check if this is a natural language response
            if "user_response" in confirmation:
                logger.info("Received natural language response, using LLM to interpret...")
                user_response = str(confirmation["user_response"])

                # Use LLM to interpret user intent for push confirmation
                decision = await self._interpret_push_intent(user_response, push_summary)

                # Map LLM decision to action
                action: str = decision.action
                branch_override: str | None = None
                message_override: str | None = None

                # Extract overrides from modifications if provided
                if decision.modifications:
                    # LLM provides modifications in structured format:
                    # "branch: feature/my-branch\ncommit_message: My message"
                    mods = decision.modifications
                    mods_lower = mods.lower()

                    # Extract branch name - check for "branch:" prefix (new format)
                    # e.g., "branch: feature/caching"
                    if "branch:" in mods_lower:
                        branch_start = mods_lower.index("branch:") + len("branch:")
                        # Extract up to newline or end
                        branch_line = mods[branch_start:].split("\n")[0].strip()
                        branch_override = branch_line.strip('"').strip("'")
                        logger.info(f"Extracted branch name from LLM: {branch_override}")
                    # Fallback to old format: "branch name:", "use branch"
                    elif any(phrase in mods_lower for phrase in ["branch name:", "use branch"]):
                        for phrase in ["branch name:", "use branch"]:
                            if phrase in mods_lower:
                                branch_start = mods_lower.index(phrase) + len(phrase)
                                branch_candidate = mods[branch_start:].strip()
                                # Take up to newline, space, or end
                                branch_override = branch_candidate.split()[0].strip('"').strip("'")
                                logger.info(
                                    f"Extracted branch name from LLM (legacy): {branch_override}"
                                )
                                break

                    # Extract commit message - check for "commit_message:" prefix (new format)
                    # e.g., "commit_message: fix caching bug"
                    if "commit_message:" in mods_lower:
                        msg_start = mods_lower.index("commit_message:") + len("commit_message:")
                        # Extract up to newline or end
                        msg_line = mods[msg_start:].split("\n")[0].strip()
                        message_override = msg_line.strip('"').strip("'")
                        logger.info(
                            f"Extracted commit message from LLM: {message_override[:50]}..."
                        )
                    # Fallback to old format: "commit message:", "message:", "use message"
                    elif any(
                        phrase in mods_lower
                        for phrase in ["commit message:", "message:", "use message"]
                    ):
                        for phrase in ["commit message:", "message:", "use message"]:
                            if phrase in mods_lower:
                                msg_start = mods_lower.index(phrase) + len(phrase)
                                msg_candidate = mods[msg_start:].strip()
                                # Take until newline or end
                                message_override = (
                                    msg_candidate.split("\n")[0].strip('"').strip("'")
                                )
                                logger.info(
                                    f"Extracted commit message from LLM (legacy): {message_override[:50]}..."
                                )
                                break

                logger.info(
                    f"LLM interpreted push response: action={action}, "
                    f"confidence={decision.confidence:.2f}, "
                    f"reasoning={decision.reasoning}"
                )
            else:
                # Structured format (backward compatible)
                action_obj = confirmation.get("action")
                branch_override_obj = confirmation.get("branch_name_override")
                message_override_obj = confirmation.get("commit_message_override")

                # Type narrowing
                action = str(action_obj) if action_obj else "cancel"
                branch_override = str(branch_override_obj) if branch_override_obj else None
                message_override = str(message_override_obj) if message_override_obj else None

                logger.info(f"Received structured push confirmation: action={action}")

            if action == "approve":
                logger.info("Push approved by user, will execute git operations")

                # Check if user wants to regenerate commit message with PR narrator
                if message_override and any(
                    keyword in message_override.lower()
                    for keyword in ["regenerate", "rewrite", "improve", "better"]
                ):
                    logger.info(
                        "User requested commit message regeneration, calling PR narrator agent..."
                    )
                    self._send_progress("🔄 Regenerating commit message with PR narrator agent...")

                    # Call PR narrator agent to generate a new commit message
                    # Only if we have code_changes and validation_result
                    if self.state.code_changes and self.state.validation_result:
                        try:
                            from repoai.agents.pr_narrator_agent import run_pr_narrator_agent
                            from repoai.dependencies import PRNarratorDependencies

                            pr_deps = PRNarratorDependencies(
                                code_changes=self.state.code_changes,
                                validation_result=self.state.validation_result,
                                plan_id=self.state.plan.plan_id if self.state.plan else "unknown",
                            )

                            pr_description, _ = await run_pr_narrator_agent(
                                code_changes=self.state.code_changes,
                                validation_result=self.state.validation_result,
                                dependencies=pr_deps,
                                adapter=self.adapter,
                            )

                            # Use the new PR description summary as commit message
                            self.state.pr_description = pr_description
                            message_override = pr_description.summary
                            logger.info(
                                f"Generated new commit message: {message_override[:100]}..."
                            )
                            self._send_progress(
                                f"✅ New commit message: {message_override[:80]}..."
                            )

                        except Exception as e:
                            logger.error(f"Failed to regenerate commit message: {e}")
                            self._send_progress(
                                "⚠️  Failed to regenerate commit message, using original"
                            )
                    else:
                        logger.warning(
                            "Cannot regenerate commit message: missing code_changes or validation_result"
                        )
                        self._send_progress("⚠️  Cannot regenerate commit message, using original")

                # Store overrides if provided
                if branch_override:
                    logger.info(f"Using custom branch name: {branch_override}")
                    self.state.confirmation_data = self.state.confirmation_data or {}
                    self.state.confirmation_data["branch_override"] = branch_override

                if message_override:
                    msg_str = str(message_override)
                    logger.info(f"Using custom commit message: {msg_str[:50]}...")
                    self.state.confirmation_data = self.state.confirmation_data or {}
                    self.state.confirmation_data["message_override"] = msg_str

                self.state.awaiting_confirmation = None
                self.state.status = PipelineStatus.RUNNING

            elif action == "cancel":
                logger.info("User cancelled the push")
                self.state.status = PipelineStatus.CANCELLED
                raise RuntimeError(
                    "Push cancelled by user - pipeline stopping without git operations"
                )

            elif action == "clarify":
                logger.warning("LLM needs clarification from user")
                self.state.status = PipelineStatus.PAUSED
                # Send message back asking for clarification
                self._send_progress(
                    f"⚠️  Could not understand your response. Please clarify: {decision.reasoning if 'decision' in locals() else 'Please provide clearer instructions'}",
                    event_type="clarification_needed",
                    requires_confirmation=True,
                    confirmation_type="push",
                )
                # Wait for clarification
                await self._wait_for_push_confirmation()

            else:
                raise RuntimeError(f"Invalid push confirmation action: {action}")

        except asyncio.TimeoutError:
            logger.error("Push confirmation timeout (1 hour)")
            self.state.status = PipelineStatus.FAILED
            raise RuntimeError("Push confirmation timeout - no response from user") from None

    async def _run_git_operations_stage(self) -> None:
        """
        Execute git operations: create branch, commit changes, push to remote.

        Uses GitHub credentials from dependencies and handles branch/message overrides
        from user confirmation.

        Raises:
            RuntimeError: If git operations fail or credentials are missing
        """
        if not self.deps.github_credentials:
            raise RuntimeError("GitHub credentials not available")

        if not self.deps.repository_path:
            raise RuntimeError("Repository path not set")

        logger.info("Starting git operations stage...")

        self.state.stage = PipelineStage.GIT_OPERATIONS
        stage_start = time.time()

        try:
            from pathlib import Path

            from repoai.utils.git_utils import commit_changes, create_branch, push_to_remote

            repo_path = Path(self.deps.repository_path)

            # Get branch name (use override if provided)
            branch_override = None
            message_override = None
            if self.state.confirmation_data:
                branch_override = self.state.confirmation_data.get("branch_override")
                message_override = self.state.confirmation_data.get("message_override")

            # Ensure branch_name is a string
            branch_name = (
                str(branch_override) if branch_override else f"repoai/{self.state.session_id}"
            )

            # Step 1: Create branch
            self._send_progress(
                f"🌿 Creating branch: {branch_name}",
                event_type="git_operation",
                additional_data={"operation": "create_branch", "branch_name": branch_name},
            )
            logger.info(f"Creating branch: {branch_name}")

            create_branch(repo_path, branch_name)
            self.state.git_branch_name = branch_name

            # Notify user: Branch created
            self._send_progress(
                f"✅ Branch created: {branch_name}",
                event_type="git_operation",
                additional_data={"operation": "branch_created", "branch_name": branch_name},
            )
            logger.info(f"✅ Branch '{branch_name}' created successfully")

            # Step 2: Commit changes
            commit_message_raw = message_override or (
                self.state.pr_description.summary
                if self.state.pr_description
                else self.state.user_prompt
            )
            commit_message = (
                str(commit_message_raw) if commit_message_raw else "RepoAI automated refactoring"
            )

            self._send_progress(
                f"💾 Committing changes: {commit_message[:50]}...",
                event_type="git_operation",
                additional_data={"operation": "commit", "message": commit_message[:100]},
            )
            logger.info(f"Committing changes: {commit_message[:100]}")

            # Use user info if available, otherwise defaults
            author_name = "RepoAI Bot"
            author_email = "repoai@example.com"

            commit_hash = commit_changes(repo_path, commit_message, author_name, author_email)
            self.state.git_commit_hash = commit_hash

            # Notify user: Committed
            self._send_progress(
                f"✅ Changes committed: {commit_hash[:8]}",
                event_type="git_operation",
                additional_data={
                    "operation": "commit_created",
                    "commit_hash": commit_hash,
                    "short_hash": commit_hash[:8],
                },
            )
            logger.info(f"✅ Created commit: {commit_hash}")

            # Step 3: Push to remote
            self._send_progress(
                f"📤 Pushing to remote: {branch_name}",
                event_type="git_operation",
                additional_data={"operation": "push", "branch_name": branch_name},
            )
            logger.info(f"Pushing branch '{branch_name}' to remote")

            push_to_remote(
                repo_path,
                branch_name,
                self.deps.github_credentials.access_token,
                self.deps.github_credentials.repository_url,
            )

            self.state.git_push_status = "success"

            # Construct branch URL from repository URL
            # repository_url format: https://github.com/owner/repo or https://github.com/owner/repo.git
            repo_url = self.deps.github_credentials.repository_url.rstrip("/")
            if repo_url.endswith(".git"):
                repo_url = repo_url[:-4]
            branch_url = f"{repo_url}/tree/{branch_name}"

            # Notify user: Push successful with link
            self._send_progress(
                "✅ Successfully pushed to remote!",
                event_type="git_operation",
                additional_data={
                    "operation": "push_completed",
                    "branch_name": branch_name,
                    "branch_url": branch_url,
                },
            )
            self._send_progress(
                f"🔗 View your changes: {branch_url}",
                event_type="git_operation",
                additional_data={"operation": "branch_url", "url": branch_url},
            )
            logger.info(f"✅ Successfully pushed to {repo_url}")
            logger.info(f"🔗 Branch URL: {branch_url}")

            # Record stage time
            duration_ms = (time.time() - stage_start) * 1000
            self.state.record_stage_time(PipelineStage.GIT_OPERATIONS, duration_ms)

            logger.info(f"Git operations completed: branch={branch_name}, time={duration_ms:.0f}ms")

        except Exception as e:
            self.state.git_push_status = "failed"
            logger.error(f"Git operations failed: {e}", exc_info=True)
            raise RuntimeError(f"Git operations failed: {str(e)}") from e

    async def _interpret_user_intent(
        self, user_response: str, plan_summary: str
    ) -> OrchestratorDecision:
        """
        Use LLM to interpret user's response to plan confirmation.

        Args:
            user_response: User's natural language response
            plan_summary: Summary of the refactoring plan

        Returns:
            OrchestratorDecision with action, reasoning, and confidence

        Example:
            decision = await orchestrator._interpret_user_intent(
                "yes but use Redis instead of database",
                plan_summary
            )
            if decision.action == "modify":
                print(decision.modifications)
        """
        logger.info(f"Interpreting user intent: '{user_response[:50]}...'")

        # Build prompt for LLM
        prompt = f"""**Refactor Plan Summary:**
{plan_summary}

**User Response:**
"{user_response}"

{USER_INTENT_INSTRUCTIONS}

Analyze the user's response and determine their intent. Output a valid OrchestratorDecision."""

        try:
            # Use ORCHESTRATOR role for meta-decisions
            result = await self.adapter.run_json_async(
                role=ModelRole.ORCHESTRATOR,
                schema=OrchestratorDecision,
                messages=[{"content": f"{ORCHESTRATOR_SYSTEM_PROMPT}\n\n{prompt}"}],
                temperature=0.2,
                max_output_tokens=1024,
                use_fallback=True,
            )

            logger.info(
                f"User intent interpreted: action={result.action}, "
                f"confidence={result.confidence:.2f}"
            )

            if result.confidence < 0.5:
                logger.warning(
                    f"Low confidence decision ({result.confidence:.2f}): {result.reasoning}"
                )

            return result

        except Exception as e:
            logger.error(f"Failed to interpret user intent: {e}", exc_info=True)

            # Fallback: return clarify decision
            return OrchestratorDecision(
                action="clarify",
                reasoning=f"Failed to parse user response due to error: {str(e)}",
                confidence=0.0,
                modifications=None,
                next_step="ask_user_to_rephrase",
                estimated_success_probability=None,
            )

    async def _interpret_push_intent(
        self, user_response: str, push_summary: str
    ) -> OrchestratorDecision:
        """
        Use LLM to interpret natural language response for push confirmation.

        This method takes a user's natural language response (e.g., "yes push it",
        "cancel", "looks good") and uses an LLM to determine the user's intent
        regarding pushing changes to GitHub.

        Args:
            user_response: User's natural language response to push confirmation
            push_summary: Context about the push (files, validation status, PR description)

        Returns:
            OrchestratorDecision with action (approve/cancel/clarify), reasoning, and confidence

        Example:
            decision = await orchestrator._interpret_push_intent(
                "yes, push it",
                push_summary
            )
            if decision.action == "approve":
                # Proceed with git push
        """
        logger.info(f"Interpreting push intent: '{user_response[:50]}...'")

        push_intent_instructions = """
You are analyzing a user's response to a push confirmation prompt.

**Your Task:**
Determine if the user wants to:
1. **approve** - Push changes to GitHub (e.g., "yes", "looks good", "push it", "go ahead")
2. **cancel** - Cancel the push (e.g., "no", "cancel", "don't push", "abort")
3. **clarify** - Response is unclear or needs more information

**Rules:**
- Default to "clarify" if you're not confident (confidence < 0.7)
- Common approval phrases: yes, ok, sure, looks good, push it, go ahead, proceed
- Common cancel phrases: no, cancel, abort, don't push, stop, wait
- Be lenient with informal language
- If user wants to modify commit message or branch name, still set action to "approve"
- In modifications field, include any requested changes on separate lines:
  * "branch: <branch-name>" if they want different branch name
  * "commit_message: <new message>" if they want different commit message

**Branch Name Extraction:**
Extract branch names from phrases like:
- "push to <branch>" → "branch: <branch>"
- "use branch <branch>" → "branch: <branch>"
- "create branch <branch>" → "branch: <branch>"
- "push it to <branch>" → "branch: <branch>"
Common branch patterns: feature/*, bugfix/*, hotfix/*, release/*, or simple names

**Examples:**
- "yes but use commit message: Fix critical bug" → action=approve, modifications="commit_message: Fix critical bug"
- "push to feature/caching branch" → action=approve, modifications="branch: feature/caching"
- "yes, push it to bugfix/login-issue" → action=approve, modifications="branch: bugfix/login-issue"
- "use message: Improve performance" → action=approve, modifications="commit_message: Improve performance"
- "yes, push to my-feature" → action=approve, modifications="branch: my-feature"

Output your decision as a valid OrchestratorDecision JSON object.
"""

        # Build prompt for LLM
        prompt = f"""**Push Summary:**
{push_summary}

**User Response:**
"{user_response}"

{push_intent_instructions}

Analyze the user's response and determine if they approve or cancel the push."""

        try:
            # Use ORCHESTRATOR role for push decisions
            result = await self.adapter.run_json_async(
                role=ModelRole.ORCHESTRATOR,
                schema=OrchestratorDecision,
                messages=[{"content": f"{ORCHESTRATOR_SYSTEM_PROMPT}\n\n{prompt}"}],
                temperature=0.2,
                max_output_tokens=512,
                use_fallback=True,
            )

            logger.info(
                f"Push intent interpreted: action={result.action}, "
                f"confidence={result.confidence:.2f}, "
                f"reasoning={result.reasoning}"
            )

            if result.confidence < 0.7:
                logger.warning(
                    f"Low confidence push decision ({result.confidence:.2f}), "
                    "requesting clarification"
                )
                # Override to clarify if confidence is too low
                result.action = "clarify"

            return result

        except Exception as e:
            logger.error(f"Failed to interpret push intent: {e}", exc_info=True)

            # Fallback: return clarify decision
            return OrchestratorDecision(
                action="clarify",
                reasoning=f"Failed to parse push response due to error: {str(e)}",
                confidence=0.0,
                modifications=None,
                next_step="ask_user_to_rephrase",
                estimated_success_probability=None,
            )

    async def _interpret_validation_intent(
        self, user_response: str, validation_summary: str
    ) -> OrchestratorDecision:
        """
        Use LLM to interpret natural language response for validation mode selection.

        Args:
            user_response: User's natural language response
            validation_summary: Context about validation options

        Returns:
            OrchestratorDecision with modifications containing the validation mode
        """
        logger.info(f"Interpreting validation intent: '{user_response[:50]}...'")

        validation_intent_instructions = """
You are analyzing a user's response to choose a validation mode.

**Validation Modes:**
1. **full** - Run compilation + all tests (recommended, most thorough)
2. **compile_only** - Only compile, skip tests (faster but less thorough)
3. **skip** - Skip validation entirely (fastest but risky)

**Your Task:**
Determine which validation mode the user wants and set it in the modifications field.

**Rules:**
- Common "full" phrases: yes, run tests, full validation, test everything, validate thoroughly
- Common "compile_only" phrases: just compile, compile only, skip tests, no tests
- Common "skip" phrases: skip, skip validation, don't validate, no validation
- Set modifications to: "full", "compile_only", or "skip"
- Default to "full" if unclear
- Set action to "approve" always (we just need the mode)

**Examples:**
- "yes, run full validation" → action=approve, modifications="full"
- "just compile, skip tests" → action=approve, modifications="compile_only"
- "skip validation" → action=approve, modifications="skip"
- "run all tests" → action=approve, modifications="full"
- "compile only please" → action=approve, modifications="compile_only"

Output your decision as a valid OrchestratorDecision JSON object.
"""

        prompt = f"""**Validation Summary:**
{validation_summary}

**User Response:**
"{user_response}"

{validation_intent_instructions}

Analyze the user's response and determine which validation mode they want."""

        try:
            result = await self.adapter.run_json_async(
                role=ModelRole.ORCHESTRATOR,
                schema=OrchestratorDecision,
                messages=[{"content": f"{ORCHESTRATOR_SYSTEM_PROMPT}\n\n{prompt}"}],
                temperature=0.2,
                max_output_tokens=256,
                use_fallback=True,
            )

            logger.info(
                f"Validation intent interpreted: modifications={result.modifications}, "
                f"confidence={result.confidence:.2f}"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to interpret validation intent: {e}", exc_info=True)
            # Fallback: return full validation
            return OrchestratorDecision(
                action="approve",
                reasoning="Failed to parse, defaulting to full validation",
                confidence=0.5,
                modifications="full",
                next_step=None,
                estimated_success_probability=None,
            )

    async def _decide_retry_strategy(
        self, validation_result: ValidationResult
    ) -> OrchestratorDecision:
        """
        Use LLM to decide retry strategy for validation failures.

        Args:
            validation_result: Validation result with errors

        Returns:
            OrchestratorDecision with retry action and strategy

        Example:
            decision = await orchestrator._decide_retry_strategy(validation_result)
            if decision.action == "retry":
                print(f"Retry with {decision.estimated_success_probability:.0%} success chance")
            elif decision.action == "abort":
                print(f"Aborting: {decision.reasoning}")
        """
        logger.info("Analyzing validation errors for retry decision...")

        # Build error summary
        error_summary = self._build_error_summary(validation_result)

        # Build context about retry history
        retry_context = f"""**Retry Context:**
- Current attempt: {self.state.retry_count + 1}/{self.state.max_retries}
- Previous attempts: {self.state.retry_count}
- Validation passed: {validation_result.passed}
- Failed checks: {len(validation_result.failed_checks)}
"""

        # Build prompt for LLM
        prompt = f"""**Validation Errors:**
{error_summary}

{retry_context}

**Original Plan:**
- Intent: {self.state.job_spec.intent if self.state.job_spec else 'N/A'}
- Target packages: {len(self.state.job_spec.scope.target_packages) if self.state.job_spec else 0}

**Pipeline State:**
- Stage: {self.state.stage.value}
- Status: {self.state.status.value}

{RETRY_STRATEGY_INSTRUCTIONS}

Analyze the validation errors and decide the best retry strategy. Output a valid OrchestratorDecision."""

        try:
            # Stream the orchestration reasoning so the UI can display LLM analysis in real-time.
            # Use structured streaming to get partial OrchestratorDecision objects.
            logger.info("Starting streamed retry-decision analysis (structured)...")
            last_result: OrchestratorDecision | None = None

            async for partial in self.adapter.stream_json_async(
                role=ModelRole.ORCHESTRATOR,
                schema=OrchestratorDecision,
                messages=[{"content": f"{ORCHESTRATOR_SYSTEM_PROMPT}\n\n{prompt}"}],
                temperature=0.2,
                max_output_tokens=4096,
                use_fallback=True,
            ):
                # `partial` may be a partial schema instance; capture as last_result
                try:
                    last_result = partial
                except Exception:
                    # In case partial isn't fully validated yet, skip assigning
                    pass

                # Stream the reasoning text to the frontend as it becomes available
                reasoning_text = getattr(partial, "reasoning", None) if partial else None
                if reasoning_text:
                    try:
                        # Send incremental reasoning updates via progress channel
                        self._send_progress(
                            message=reasoning_text,
                            event_type="llm_reasoning",
                            additional_data={
                                "stage": "validation_analysis",
                                "partial": True,
                            },
                        )
                    except Exception:
                        logger.debug(
                            "Failed sending partial reasoning progress update", exc_info=True
                        )

            # If streaming provided at least one structured output, use it
            if last_result:
                result = last_result
                logger.info(
                    f"Retry decision (streamed): action={result.action}, "
                    f"confidence={result.confidence:.2f}, "
                    f"success_prob={result.estimated_success_probability or 0:.2f}"
                )
                if (
                    result.estimated_success_probability
                    and result.estimated_success_probability < 0.3
                ):
                    logger.warning(
                        f"Low success probability ({result.estimated_success_probability:.2f}) "
                        f"for {result.action} action"
                    )
                return result

            # If streaming didn't produce a validated result, fall back to non-streaming call
            logger.info(
                "Stream did not yield a final validated decision; falling back to JSON completion"
            )

            # Use ORCHESTRATOR role for meta-decisions (fallback)
            result = await self.adapter.run_json_async(
                role=ModelRole.ORCHESTRATOR,
                schema=OrchestratorDecision,
                messages=[{"content": f"{ORCHESTRATOR_SYSTEM_PROMPT}\n\n{prompt}"}],
                temperature=0.2,
                max_output_tokens=4096,  # Increased for complex error analysis
                use_fallback=True,
            )

            logger.info(
                f"Retry decision (fallback): action={result.action}, "
                f"confidence={result.confidence:.2f}, "
                f"success_prob={result.estimated_success_probability or 0:.2f}"
            )

            if result.estimated_success_probability and result.estimated_success_probability < 0.3:
                logger.warning(
                    f"Low success probability ({result.estimated_success_probability:.2f}) "
                    f"for {result.action} action"
                )

            return result

        except Exception as e:
            logger.error(f"Failed to decide retry strategy: {e}", exc_info=True)

            # Fallback: abort on error
            return OrchestratorDecision(
                action="abort",
                reasoning=f"Failed to analyze validation errors due to error: {str(e)}",
                confidence=0.5,
                modifications=None,
                next_step="report_analysis_failure",
                estimated_success_probability=0.0,
            )
