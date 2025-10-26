"""
Planner Agent Implementation for RepoAI.

The Planner Agent is the second agent in the pipeline.
It carries out the following tasks:
1. Receives a JobSpec from the Intake Agent.
2. Analyzes the refactoring requirements for java code.
3. Creates a detailed RefactorPlan with ordered steps.
4. Assesses risks and provides mitigation strategies.

This agent uses reasoning models optimized for complex planning.
"""

from __future__ import annotations

import time
from datetime import datetime

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from repoai.dependencies import PlannerDependencies
from repoai.explainability import RefactorMetadata
from repoai.llm import ModelRole, PydanticAIAdapter
from repoai.models import JobSpec, RefactorPlan
from repoai.utils.logger import get_logger

from .prompts import (
    PLANNER_INSTRUCTIONS,
    PLANNER_JAVA_EXAMPLES,
    PLANNER_SYSTEM_PROMPT,
)

logger = get_logger(__name__)


# Helper model for suggest_step_dependencies tool (avoids additionalProperties warning)
class StepInfo(BaseModel):
    """Information about a refactoring step for dependency analysis."""

    step_number: int = Field(description="Step number")
    action: str = Field(description="Action type")
    target_classes: list[str] = Field(default_factory=list, description="Target class names")


def create_planner_agent(adapter: PydanticAIAdapter) -> Agent[PlannerDependencies, RefactorPlan]:
    """
    Create and configure the Planner Agent.

    The Planner Agent analyzes JobSpec and creates a detailed RefactorPlan with ordered steps, risk assessment, and mitigation strategies.

    Args:
        adapter: PydanticAIAdapter to provide models and configurations.

    Returns:
        Configured Planner Agent instance.

    Example:
        adapter = PydanticAIAdapter()
        planner_agent = create_planner_agent(adapter)

        # Run the agent
        result = await planner_agent.run(
            job_spec.model_dump_json(),
            deps=dependencies
        )

        plan = result.output
        print(f"Total steps: {plan.total_steps}")
        print(f"Risk level: {plan.risk_assessment.overall_risk_level}")
    """
    # get the model and settings for the planner role
    model = adapter.get_model(ModelRole.PLANNER)
    settings = adapter.get_model_settings(ModelRole.PLANNER)
    spec = adapter.get_spec(ModelRole.PLANNER)

    logger.info(f"Creating Planner Agent with model: {spec.model_id}")

    # Build Complete System Prompt
    complete_system_prompt = f"""{PLANNER_SYSTEM_PROMPT}

{PLANNER_INSTRUCTIONS}

{PLANNER_JAVA_EXAMPLES}

**Your Task:**
Analyze the provided JobSpec and create a comprehensive RefactorPlan.
Use the provided tools to validate dependencies, assess risks, and order steps properly.
Be thorough in risk assessment and mitigation strategies.
"""
    # Create the Agent with RefactorPlan output type
    agent: Agent[PlannerDependencies, RefactorPlan] = Agent(
        model=model,
        deps_type=PlannerDependencies,
        output_type=RefactorPlan,
        system_prompt=complete_system_prompt,
        model_settings=settings,
    )

    # Tool: Generate Plan ID
    @agent.tool
    def generate_plan_id(ctx: RunContext[PlannerDependencies]) -> str:
        """
        Generate a unique plan ID.

        Returns:
            str: Unique plan ID in the format "plan_YYYYMMDD_HHMMSS".
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        plan_id = f"plan_{timestamp}"
        logger.debug(f"Generated plan ID: {plan_id}")
        return plan_id

    # Tool: Validate Maven Dependency
    @agent.tool
    def validate_maven_dependency(
        ctx: RunContext[PlannerDependencies], dependency: str
    ) -> dict[str, bool | str]:
        """
        Validate Maven dependency format.

        Args:
            dependency: Maven dependency string (eg. "org.springframework.boot:spring-boot-starter-security:3.2.0")

        Returns:
            dict: Validation result with is_valid (bool) and message (str).

        Example:
            result = validate_maven_dependency("org.springframework.boot:spring-boot-starter-security:3.2.0")
            # Returns: {'is_valid': True, 'message': 'Valid Maven dependency format'}
        """
        if not dependency:
            return {"is_valid": False, "message": "Dependency string cannot be empty."}

        parts = dependency.split(":")
        if len(parts) < 2 or len(parts) > 4:
            return {
                "is_valid": False,
                "message": "Invalid Format. Expected: groupId:artifactId[:version][:scope]",
            }

        group_id, artifact_id = parts[0], parts[1]

        if not group_id or not artifact_id:
            return {
                "is_valid": False,
                "message": "groupId and artifactId cannot be empty.",
            }

        # Basic Validation for group ID (reverse domain notation)
        if not all(
            segment.replace("-", "").replace("-", "").isalnum() for segment in group_id.split(".")
        ):
            return {
                "is_valid": False,
                "message": "Invalid groupId format. Should be in reverse domain notation.",
            }

        logger.debug(f"Validated Maven dependency: {dependency}")
        return {"is_valid": True, "message": "Valid Maven dependency format."}

    # Tool: Estimate Step Duration
    @agent.tool
    def estimate_step_duration(
        ctx: RunContext[PlannerDependencies], action: str, complexity: str = "medium"
    ) -> int:
        """
        Estimate duration for a refactoring step in minutes.

        Args:
            action: Action type (e.g., "create_class", "add_method", "refactor_package_structure")
            complexity: Complexity level ("low", "medium", "high")

        Returns:
            int: Estimated duration in minutes.

        Example:
            duration = estimate_step_duration("create_class", "medium")
            # Returns: 15
        """
        base_durations = {
            "create_class": 15,
            "create_interface": 10,
            "create_enum": 8,
            "add_method": 10,
            "extract_method": 12,
            "add_annotation": 5,
            "implement_interface": 20,
            "add_dependency": 5,
            "refactor_package_structure": 30,
            "add_spring_configuration": 20,
            "add_rest_controller": 25,
            "modify_existing_class": 15,
            "add_test_class": 20,
        }

        complexity_multiplier = {"low": 0.7, "medium": 1.0, "high": 1.5}

        base = base_durations.get(action.lower(), 15)
        multiplier = complexity_multiplier.get(complexity.lower(), 1.0)
        estimated = int(base * multiplier)
        logger.debug(f"Estimated duration for {action} ({complexity}): {estimated} minutes")
        return estimated

    # Tool: Calculate Risk Level
    @agent.tool
    def calculate_risk_level(
        ctx: RunContext[PlannerDependencies],
        action: str,
        affects_core_logic: bool = False,
        modifies_interfaces: bool = False,
        changes_dependencies: bool = False,
    ) -> int:
        """
        Calculate risk level for a refactoring step (0-10).

        Args:
            action: Action type
            affects_core_logic: Whether the change affects core business logic
            modifies_interfaces: Whether the change modifies public interfaces
            changes_dependencies: Whether the change adds/removes dependencies

        Returns:
            int: Risk level from 0 (safe) to 10 (very risky).

        Example:
            risk = calculate_risk_level("modify_existing_class", affects_core_logic=True, modifies_interfaces=True)
            # Returns: 7
        """
        base_risks = {
            "create_class": 2,
            "create_interface": 3,
            "create_enum": 1,
            "add_method": 3,
            "extract_method": 4,
            "modify_existing_class": 5,
            "refactor_package_structure": 7,
            "add_dependency": 4,
            "implement_interface": 5,
            "add_spring_configuration": 4,
        }

        risk = base_risks.get(action.lower(), 5)

        # Increase risk based on factors
        if affects_core_logic:
            risk += 2
        if modifies_interfaces:
            risk += 2
        if changes_dependencies:
            risk += 1

        # Cap at 10
        risk = min(risk, 10)

        logger.debug(f"Calculated risk level for {action}: {risk}/10")
        return risk

    @agent.tool
    def suggest_step_dependencies(
        ctx: RunContext[PlannerDependencies], steps: list[StepInfo]
    ) -> dict[int, list[int]]:
        """
        Suggest dependencies between steps based on their actions and targets.

        Args:
            steps: List of step information with step_number, action, and target_classes

        Returns:
            dict: Mapping of step_number to list of dependency step_numbers.

        Example:
            steps = [
                StepInfo(step_number=1, action='create_interface', target_classes=['com.example.IAuth']),
                StepInfo(step_number=2, action='implement_interface', target_classes=['com.example.AuthImpl'])
            ]
            deps = suggest_step_dependencies(steps)
            # Returns: {2: [1]}  # Step 2 depends on Step 1
        """
        dependencies: dict[int, list[int]] = {}

        for step in steps:
            step_num = step.step_number
            action = step.action
            targets = step.target_classes

            depends_on: list[int] = []

            # Rules for dependencies
            if action == "implement_interface":
                # Must create interface first
                for prev_step in steps:
                    prev_num = prev_step.step_number
                    if prev_num >= step_num:
                        continue

                    if prev_step.action == "create_interface":
                        depends_on.append(prev_num)

            elif action == "add_method" or action == "modify_existing_class":
                # Must create class first
                for prev_step in steps:
                    prev_num = prev_step.step_number
                    if prev_num >= step_num:
                        continue

                    if prev_step.action == "create_class" and any(
                        target in prev_step.target_classes for target in targets
                    ):
                        depends_on.append(prev_num)

            elif action == "add_dependency":
                # Should be early in the process
                pass

            elif action == "add_spring_configuration":
                # Should come after class creation
                for prev_step in steps:
                    prev_num = prev_step.step_number
                    if prev_num >= step_num:
                        continue

                    if prev_step.action in ["create_class", "create_interface"]:
                        depends_on.append(prev_num)

            if depends_on:
                dependencies[step_num] = depends_on

        logger.debug(f"Suggested dependencies: {dependencies}")
        return dependencies

    # Tool: Suggest Mitigation Strategies
    @agent.tool
    def suggest_mitigation_strategies(
        ctx: RunContext[PlannerDependencies],
        overall_risk: int,
        breaking_changes: bool,
        compilation_risk: bool,
    ) -> list[str]:
        """
        Suggest mitigation strategies based on risk factors.

        Args:
            overall_risk: Overall risk level (0-10)
            breaking_changes: Whether there are breaking changes
            compilation_risk: Whether there's compilation risk

        Returns:
            list[str]: List of mitigation strategy recommendations.
        """
        strategies = []

        if overall_risk >= 7:
            strategies.append("Implement feature flag for gradual rollout")
            strategies.append("Create detailed rollback plan before deployment")
            strategies.append("Conduct thorough code review with senior engineers")

        if breaking_changes:
            strategies.append("Use @Deprecated annotations for backward compatibility")
            strategies.append("Provide migration guide for API consumers")
            strategies.append("Version the API to maintain old endpoints temporarily")

        if compilation_risk:
            strategies.append("Run full Maven/Gradle build after each major step")
            strategies.append("Set up CI/CD pipeline to catch compilation errors early")
            strategies.append("Use IDE static analysis to identify potential issues")

        strategies.extend(
            [
                "Add comprehensive unit tests for all new methods (minimum 80% coverage)",
                "Run integration tests to verify system behavior",
                "Perform load testing if changes affect performance-critical paths",
            ]
        )

        logger.debug(f"Suggested {len(strategies)} mitigation strategies")
        return strategies

    logger.info("Planner Agent created successfully.")
    return agent


async def run_planner_agent(
    job_spec: JobSpec,
    dependencies: PlannerDependencies,
    adapter: PydanticAIAdapter | None = None,
) -> tuple[RefactorPlan, RefactorMetadata]:
    """
    Run the Planner Agent with a JobSpec.

    Convenience function that creates the agent, runs it, and captures metadata.

    Args:
        job_spec: JobSpec from Intake Agent
        dependencies: Planner Agent dependencies
        adapter: Optional PydanticAIAdapter (creates new one if not provided)

    Returns:
        tuple: (RefactorPlan, RefactorMetadata) with the plan and metadata

    Example:
        from repoai.dependencies.base import PlannerDependencies
        from repoai.models import JobSpec

        deps = PlannerDependencies(
            job_spec=job_spec,
            repository_path="/path/to/repo"
        )

        plan, metadata = await run_planner_agent(job_spec, deps)

        print(f"Total steps: {plan.total_steps}")
        print(f"Risk level: {plan.risk_assessment.overall_risk_level}")
        print(f"Duration: {plan.estimated_duration}")
    """
    if adapter is None:
        adapter = PydanticAIAdapter()

    # Create the Planner Agent
    planner_agent = create_planner_agent(adapter)

    logger.info(f"Running Planner Agent for job: {job_spec.job_id}")
    logger.debug(f"Job Intent: {job_spec.intent}")
    logger.debug(f"Target packages: {job_spec.scope.target_packages}")

    # Track timing
    start_time = time.time()

    # Prepare the prompt with the JobSpec
    prompt = f"""Analyze the following JobSpec and create a detailed RefactorPlan:

Job ID: {job_spec.job_id}
Intent: {job_spec.intent}
Language: {job_spec.scope.language}
Build System: {job_spec.scope.build_system}

Target Packages: {', '.join(job_spec.scope.target_packages)}
Target Files: {', '.join(job_spec.scope.target_files)}

Requirements:
{chr(10).join(f'- {req}' for req in job_spec.requirements)}

Constraints:
{chr(10).join(f'- {const}' for const in job_spec.constraints)}

Create a comprehensive RefactorPlan with:
1. Ordered refactoring steps with proper dependencies
2. Java-specific actions (create classes, add annotations, modify Spring configs, etc.)
3. Risk assessment with compilation risks and mitigation strategies
4. Realistic time estimates for each step
"""
    # Run the agent
    result = await planner_agent.run(prompt, deps=dependencies)

    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000

    # Extract RefactorPlan
    plan: RefactorPlan = result.output

    # Get Model used
    model_used = adapter.get_spec(role=ModelRole.PLANNER).model_id

    # Create Metadata
    metadata = RefactorMetadata(
        timestamp=datetime.now(),
        agent_name="PlannerAgent",
        model_used=model_used,
        confidence_score=0.90,  # TODO: Calculate actual confidence
        reasoning_chain=[
            f"Analyzed JobSpec for intent: {job_spec.intent}",
            f"Generated {plan.total_steps} refactoring steps",
            f"Assessed overall risk level: {plan.risk_assessment.overall_risk_level}/10",
            f"Identified {len(plan.risk_assessment.affected_modules)} affected modules",
            f"Created {len(plan.risk_assessment.mitigation_strategies)} mitigation strategies",
        ],
        data_sources=["job_spec", "repository_structure"],
        execution_time_ms=duration_ms,
    )

    # Attach metadata to the plan
    plan.metadata = metadata

    logger.info(
        f"Planner Agent completed: "
        f"steps={plan.total_steps}, "
        f"risk={plan.risk_assessment.overall_risk_level}/10, "
        f"duration={duration_ms:.0f}ms"
    )

    return plan, metadata
