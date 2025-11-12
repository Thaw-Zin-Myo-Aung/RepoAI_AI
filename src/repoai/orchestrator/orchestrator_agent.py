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

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repoai.dependencies import (
        OrchestratorDependencies,
    )
from repoai.llm import ModelRole, PydanticAIAdapter
from repoai.models import (
    CodeChange,
    CodeChanges,
    FileChange,
    PRDescription,
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

    def _send_progress(self, message: str) -> None:
        """
        Send progress update via callback if configured.

        Args:
            message: Progress message to send
        """
        if self.deps.enable_progress_updates and self.deps.send_message:
            try:
                self.deps.send_message(message)
            except Exception as e:
                logger.warning(f"Failed to send progress update: {e}")

    async def run(self, user_prompt: str) -> PipelineState:
        """
        Execute the complete refactoring pipeline.

        Args:
            user_prompt: User's refactoring request

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

        logger.info(f"Starting pipeline: {user_prompt[:100]}...")
        self._send_progress(f"🚀 Starting pipeline: {user_prompt[:80]}...")

        try:
            # Stage 1: Intake
            self._send_progress("📥 Stage 1/5: Analyzing refactoring request...")
            await self._run_intake_stage()
            self._send_progress(
                f"✅ Intake complete: {self.state.job_spec.intent if self.state.job_spec else 'processed'}"
            )

            # Stage 2: Planning
            self._send_progress("📋 Stage 2/5: Creating refactoring plan...")
            await self._run_planning_stage()
            self._send_progress(
                f"✅ Plan created: {self.state.plan.total_steps if self.state.plan else 0} steps"
            )

            # Stage 3: Transformation
            self._send_progress("🔨 Stage 3/5: Generating code changes...")
            await self._run_transformation_stage()
            self._send_progress(
                f"✅ Code generated: {self.state.code_changes.files_modified if self.state.code_changes else 0} files modified"
            )

            # Stage 4: Validation (with intelligent retry)
            self._send_progress("🔍 Stage 4/5: Validating code changes...")
            await self._run_validation_stage()
            validation_status = (
                "passed"
                if self.state.validation_result and self.state.validation_result.passed
                else "completed"
            )
            self._send_progress(f"✅ Validation {validation_status}")

            # Stage 5: PR Narration
            self._send_progress("📝 Stage 5/5: Creating PR description...")
            await self._run_narration_stage()
            self._send_progress("✅ PR description ready")

            # Mark as complete
            self.state.stage = PipelineStage.COMPLETE
            self.state.status = PipelineStatus.COMPLETED
            self.state.end_time = time.time()

            self._send_progress(
                f"🎉 Pipeline completed successfully! ({self.state.elapsed_time_ms/1000:.1f}s)"
            )

            logger.info(
                f"Pipeline completed successfully: "
                f"{self.state.elapsed_time_ms:.0f}ms, "
                f"{self.state.code_changes.files_modified if self.state.code_changes else 0} files"
            )

        except Exception as e:
            self.state.stage = PipelineStage.FAILED
            self.state.status = PipelineStatus.FAILED
            self.state.add_error(f"Pipeline failed: {str(e)}")
            self.state.end_time = time.time()

            self._send_progress(f"❌ Pipeline failed: {str(e)[:100]}")
            logger.error(f"Pipeline failed: {e}", exc_info=True)

        return self.state

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
        from repoai.agents.transformer_agent import run_transformer_agent
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
        )

        # Run Transformer Agent
        code_changes, metadata = await run_transformer_agent(
            self.state.plan, transformer_deps, self.adapter
        )

        self.state.code_changes = code_changes
        duration_ms = (time.time() - stage_start) * 1000
        self.state.record_stage_time(PipelineStage.TRANSFORMATION, duration_ms)

        logger.info(
            f"Transformation completed: {code_changes.files_modified} files, "
            f"+{code_changes.lines_added}/-{code_changes.lines_removed} lines, "
            f"time={duration_ms:.0f}ms"
        )

    async def _run_transformation_stage_streaming(self) -> None:
        """
        Run Transformer Agent with streaming and real-time file application.

        This version streams code changes as they're generated and applies them
        immediately to the cloned repository.
        """
        from repoai.agents.transformer_agent import transform_with_streaming
        from repoai.dependencies import TransformerDependencies

        if not self.state.plan:
            raise RuntimeError("RefactorPlan not available - run Planning stage first")

        if not self.deps.repository_path:
            raise RuntimeError("Repository path not set - clone repository first")

        self.state.stage = PipelineStage.TRANSFORMATION
        stage_start = time.time()

        logger.info("Running Transformer Agent (streaming mode)...")

        # Create backup before applying changes
        from pathlib import Path

        repo_path = Path(self.deps.repository_path)
        backup_dir = await create_backup_directory(repo_path)
        logger.info(f"Created backup: {backup_dir}")

        # Prepare dependencies
        transformer_deps = TransformerDependencies(
            plan=self.state.plan,
            repository_path=self.deps.repository_path,
            repository_url=self.deps.repository_url,
            write_to_disk=True,
            output_path=self.deps.output_path,
        )

        # Track changes and progress
        all_changes: list[CodeChange] = []
        files_applied = 0
        total_lines_added = 0
        total_lines_removed = 0

        try:
            # Stream code changes and apply immediately
            async for code_change, _metadata in transform_with_streaming(
                self.state.plan, transformer_deps, self.adapter
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

                    # Send progress update
                    self._send_progress(
                        f"✓ Generated & applied: {code_change.file_path} "
                        f"(+{code_change.lines_added}/-{code_change.lines_removed}) "
                        f"[{files_applied} files]"
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
            logger.error(f"Transformation streaming failed: {e}")
            # Restore from backup on failure
            from repoai.utils.file_operations import restore_from_backup

            logger.info("Restoring from backup due to error...")
            await restore_from_backup(backup_dir, repo_path)
            raise

    async def _run_validation_stage(self) -> None:
        """Run Validator Agent with intelligent retry on failures."""
        from repoai.agents.validator_agent import run_validator_agent
        from repoai.dependencies import ValidatorDependencies

        if not self.state.code_changes:
            raise RuntimeError("CodeChanges not available - run Transformation stage first")

        self.state.stage = PipelineStage.VALIDATION
        stage_start = time.time()

        logger.info("Running Validator Agent...")

        while True:
            # Prepare dependencies
            validator_deps = ValidatorDependencies(
                code_changes=self.state.code_changes,
                repository_path=self.deps.repository_path,
                min_test_coverage=self.deps.min_test_coverage,
                strict_mode=self.deps.require_all_checks_pass,
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

                    # Re-run transformation with new plan
                    logger.info("Re-running Transformer with modified plan...")
                    await self._run_transformation_stage()

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
        Attempt to fix validation errors using LLM analysis.

        Uses PLANNER role model to analyze errors and suggest fixes,
        then re-runs Transformer agent with updated instructions.

        Args:
            validation_result: Validation result with errors
            llm_modifications: Optional modification instructions from orchestrator LLM decision
        """
        from repoai.agents.transformer_agent import run_transformer_agent
        from repoai.dependencies import TransformerDependencies

        logger.info("Analyzing validation errors with LLM...")

        # If orchestrator provided specific modifications, use those
        if llm_modifications:
            logger.info(f"Using orchestrator-provided modifications: {llm_modifications[:200]}...")
            fix_instructions = llm_modifications
        else:
            # Otherwise, analyze errors with PLANNER model
            # Build error analysis prompt
            error_summary = self._build_error_summary(validation_result)

            analysis_prompt = f"""You are analyzing validation errors in generated Java code.

**Validation Issues:**
{error_summary}

**Original Plan:**
- Intent: {self.state.plan.job_id if self.state.plan else 'N/A'}
- Steps: {self.state.plan.total_steps if self.state.plan else 0}
- Risk: {self.state.plan.risk_assessment.overall_risk_level if self.state.plan else 0}/10

**Your Task:**
1. Analyze the validation errors
2. Identify root causes (compilation errors, missing imports, logic issues)
3. Suggest specific fixes for the Transformer agent
4. Provide updated instructions to regenerate the code correctly

**Output Format:**
Provide clear, actionable fix instructions that can be used to regenerate the code.
Focus on:
- Missing imports
- Syntax errors
- Logic issues
- Spring annotation problems
"""

            # Use PLANNER role for intelligent analysis
            fix_instructions = await self.adapter.run_raw_async(
                role=ModelRole.PLANNER,
                messages=[{"content": analysis_prompt}],
                temperature=0.3,
                max_output_tokens=2048,
            )

            logger.info(f"LLM analysis complete: {len(fix_instructions)} chars")
            logger.debug(f"Fix instructions: {fix_instructions[:500]}...")

        # Re-run Transformer with updated instructions
        # (In practice, you'd modify the plan or add context to transformer_deps)
        logger.info("Re-running Transformer Agent with fix instructions...")

        # For now, we just re-run the transformer
        # TODO: Pass fix_instructions as additional context to Transformer
        transformer_deps = TransformerDependencies(
            plan=self.state.plan,  # type: ignore
            repository_path=self.deps.repository_path,
            write_to_disk=True,
            output_path=self.deps.output_path,
        )

        code_changes, metadata = await run_transformer_agent(
            plan=self.state.plan,  # type: ignore
            dependencies=transformer_deps,
            adapter=self.adapter,
        )

        self.state.code_changes = code_changes
        logger.info("Code regenerated with fix instructions")

    def _build_error_summary(self, validation_result: ValidationResult) -> str:
        """Build human-readable error summary from validation result."""
        lines = []

        # Compilation errors
        if not validation_result.compilation_passed:
            lines.append("**Compilation Errors:**")
            for check_result in validation_result.checks:
                if check_result.result.compilation_errors:
                    for error in check_result.result.compilation_errors:
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

        # TODO: Implement PR Narrator Agent
        # For now, create a basic PR description
        # Type narrowing: we know code_changes is not None due to guard above
        code_changes = self.state.code_changes
        validation_result = self.state.validation_result

        pr_description = PRDescription(
            plan_id=self.state.plan.plan_id if self.state.plan else "unknown",
            title=f"feat: {self.state.job_spec.intent}" if self.state.job_spec else "Refactoring",
            summary=f"Implemented refactoring based on user request: {self.state.user_prompt}",
            changes_by_file=[
                FileChange(
                    file_path=change.file_path,
                    description=f"{change.change_type}: +{change.lines_added}/-{change.lines_removed}",
                )
                for change in code_changes.changes[:10]
            ],
            testing_notes=f"Validation passed: {validation_result.passed}, "
            f"Coverage: {validation_result.test_coverage * 100:.1f}%",
        )

        self.state.pr_description = pr_description
        duration_ms = (time.time() - stage_start) * 1000
        self.state.record_stage_time(PipelineStage.NARRATION, duration_ms)

        logger.info(f"PR Narration completed: '{pr_description.title}', time={duration_ms:.0f}ms")

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
                f"Retry decision: action={result.action}, "
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
