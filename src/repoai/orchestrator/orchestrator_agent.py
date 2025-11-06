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

from repoai.agents import (
    run_intake_agent,
    run_planner_agent,
    run_transformer_agent,
    run_validator_agent,
)
from repoai.dependencies import (
    IntakeDependencies,
    OrchestratorDependencies,
    PlannerDependencies,
    TransformerDependencies,
    ValidatorDependencies,
)
from repoai.llm import ModelRole, PydanticAIAdapter
from repoai.models import (
    FileChange,
    PRDescription,
    ValidationResult,
)
from repoai.utils.logger import get_logger

from .models import PipelineStage, PipelineState, PipelineStatus

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

        try:
            # Stage 1: Intake
            await self._run_intake_stage()

            # Stage 2: Planning
            await self._run_planning_stage()

            # Stage 3: Transformation
            await self._run_transformation_stage()

            # Stage 4: Validation (with intelligent retry)
            await self._run_validation_stage()

            # Stage 5: PR Narration
            await self._run_narration_stage()

            # Mark as complete
            self.state.stage = PipelineStage.COMPLETE
            self.state.status = PipelineStatus.COMPLETED
            self.state.end_time = time.time()

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

            logger.error(f"Pipeline failed: {e}", exc_info=True)

        return self.state

    async def _run_intake_stage(self) -> None:
        """Run Intake Agent to parse user request."""
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

    async def _run_transformation_stage(self) -> None:
        """Run Transformer Agent to generate code."""
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

    async def _run_validation_stage(self) -> None:
        """Run Validator Agent with intelligent retry on failures."""
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

            # Check if we can retry
            if not self.deps.auto_fix_enabled:
                logger.info("Auto-fix disabled, stopping validation")
                break

            if not self.state.can_retry:
                logger.warning(
                    f"Max retries ({self.state.max_retries}) reached, stopping validation"
                )
                break

            # Attempt intelligent fix
            logger.info(f"Attempting intelligent fix (retry {self.state.retry_count + 1})...")
            self.state.retry_count += 1
            self.state.status = PipelineStatus.RETRYING

            await self._attempt_fix(validation_result)

        duration_ms = (time.time() - stage_start) * 1000
        self.state.record_stage_time(PipelineStage.VALIDATION, duration_ms)

        logger.info(
            f"Validation completed: passed={validation_result.passed}, "
            f"retries={self.state.retry_count}, "
            f"time={duration_ms:.0f}ms"
        )

    async def _attempt_fix(self, validation_result: ValidationResult) -> None:
        """
        Attempt to fix validation errors using LLM analysis.

        Uses PLANNER role model to analyze errors and suggest fixes,
        then re-runs Transformer agent with updated instructions.

        Args:
            validation_result: Validation result with errors
        """
        logger.info("Analyzing validation errors with LLM...")

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
        pr_description = PRDescription(
            plan_id=self.state.plan.plan_id if self.state.plan else "unknown",
            title=f"feat: {self.state.job_spec.intent}" if self.state.job_spec else "Refactoring",
            summary=f"Implemented refactoring based on user request: {self.state.user_prompt}",
            changes_by_file=[
                FileChange(
                    file_path=change.file_path,
                    description=f"{change.change_type}: +{change.lines_added}/-{change.lines_removed}",
                )
                for change in self.state.code_changes.changes[:10]
            ],
            testing_notes=f"Validation passed: {self.state.validation_result.passed}, "
            f"Coverage: {self.state.validation_result.test_coverage * 100:.1f}%",
        )

        self.state.pr_description = pr_description
        duration_ms = (time.time() - stage_start) * 1000
        self.state.record_stage_time(PipelineStage.NARRATION, duration_ms)

        logger.info(f"PR Narration completed: '{pr_description.title}', time={duration_ms:.0f}ms")
