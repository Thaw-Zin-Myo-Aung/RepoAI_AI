"""
Intake Agent implementation.

The Intake Agent is the first agent in the pipeline.
It carries out the following tasks:
1. Parses user refactoring requests.
2. Extracts a structured Job Specification.
3. Creates a Jobspec for the Planner Agent.

This agent uses fast reasoning models optimized for intent parsing.
"""

from __future__ import annotations

import time
from datetime import datetime
from uuid import uuid4

from pydantic_ai import Agent, RunContext

from repoai.dependencies import IntakeDependencies
from repoai.explainability import RefactorMetadata
from repoai.llm import ModelRole, PydanticAIAdapter
from repoai.models import JobSpec
from repoai.utils.logger import get_logger

from .prompts import INTAKE_INSTRUCTIONS, INTAKE_JAVA_EXAMPLES, INTAKE_SYSTEM_PROMPT

logger = get_logger(__name__)


def create_intake_agent(adapter: PydanticAIAdapter) -> Agent[IntakeDependencies, JobSpec]:
    """
    Create and configure the Intake Agent.

    The Intake Agent parses user refactoring requests and creates a structured JobSpec.

    Args:
        adapter = PydanticAIAdapter: Adapter to provide models and configurations.

    Returns:
        Configured Intake Agent instance.

    Example:
        adapter = PydanticAIAdapter()
        intake_agent = create_intake_agent(adapter)

        # Run the agent
        result = await intake_agent.run(
            "Add JWT authentication to the user service",
            deps=dependencies
        )

        job_spec = result.output
        print(f"Intent: {job_spec.intent}")
        print(f"Scope: {job_spec.scope.target_packages}")
    """
    # Get the model and settings for Intake Role
    model = adapter.get_model(role=ModelRole.INTAKE)
    settings = adapter.get_model_settings(role=ModelRole.INTAKE)
    spec = adapter.get_spec(role=ModelRole.INTAKE)

    logger.info(f"Creating Intake Agent with model: {spec.model_id}")

    # Build complete system prompt with instructions and examples
    complete_system_prompt = f"""{INTAKE_SYSTEM_PROMPT}

{INTAKE_INSTRUCTIONS}

{INTAKE_JAVA_EXAMPLES}

**Your Task:**
Parse the user's request and create a complete JobSpec with all required fields.
Use the provided tools to generate job IDs, validate packages, and suggest file patterns.
Be specific and detailed in requirements and constraints.
"""

    # Create the agent with JobSpec output Type
    agent: Agent[IntakeDependencies, JobSpec] = Agent(
        model=model,
        deps_type=IntakeDependencies,
        output_type=JobSpec,
        system_prompt=complete_system_prompt,
        model_settings=settings,
    )

    # Tool: Generate Unique Job ID
    @agent.tool
    def generate_job_id(ctx: RunContext[IntakeDependencies]) -> str:
        """
        Generate a unique job ID.

        Returns:
            str: Unique job ID in the format "job_YYYYMMDD_HHMMSS_UUID".
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid4())[:8]
        job_id = f"job_{timestamp}_{unique_id}"

        logger.debug(f"Generated Job ID: {job_id}")
        return job_id

    # Tool: Validate Java Package Naming
    @agent.tool
    def validate_java_package(
        ctx: RunContext[IntakeDependencies], package_name: str
    ) -> dict[str, bool | str]:
        """
        Validate Java package naming conventions.

        Args:
            package_name: Java package name (eg. "com.example.auth")

        Returns:
            dict: Validation result with is_valid (bool) and message (str).

        Example:
            result = validate_java_package("com.example.auth")
            print(result)  # {'is_valid': True, 'message': 'Valid package name.'}
        """
        # Java Package naming rules:
        # - All lowercase
        # - Dot-separated segments
        # - Each segment starts with a letter
        # - Can contain letters, digits, underscores

        if not package_name:
            return {"is_valid": False, "message": "Package name cannot be empty."}

        segments = package_name.split(".")

        for segment in segments:
            if not segment:
                return {"is_valid": False, "message": "Package segments cannot be empty"}

            if not segment[0].isalpha():
                return {
                    "is_valid": False,
                    "message": f"Segment '{segment}' must start with a letter",
                }

            if not segment.replace("_", "").isalnum():
                return {
                    "is_valid": False,
                    "message": f"Segment '{segment}' contains invalid characters",
                }

            if segment != segment.lower():
                return {"is_valid": False, "message": "Package names must be all lowercase"}

        logger.debug(f"Validated Java package: {package_name} - Valid")
        return {"is_valid": True, "message": "Valid Java package name"}

    @agent.tool
    def suggest_file_patterns(ctx: RunContext[IntakeDependencies], intent: str) -> list[str]:
        """
        Suggest file patterns based on the refactoring intent.

        Args:
            intent: Refactoring intent (eg, "add_jwt_authentication")

        Returns:
            list[str]: Suggested glob patterns for target files.

        Example:
            patterns = suggest_file_patterns("add_jwt_authentication")
            # Returns: ["src/main/java/**/auth/**/*.java", "src/main/java/**/security/**/*.java"]
        """
        intent_lower = intent.lower()

        patterns_map = {
            "auth": ["src/main/java/**/auth/**/*.java", "src/main/java/**/security/**/*.java"],
            "jwt": ["src/main/java/**/auth/**/*.java", "src/main/java/**/security/**/*.java"],
            "oauth": ["src/main/java/**/auth/**/*.java", "src/main/java/**/oauth/**/*.java"],
            "database": [
                "src/main/java/**/repository/**/*.java",
                "src/main/java/**/entity/**/*.java",
            ],
            "jpa": ["src/main/java/**/repository/**/*.java", "src/main/java/**/entity/**/*.java"],
            "rest": ["src/main/java/**/controller/**/*.java", "src/main/java/**/api/**/*.java"],
            "service": ["src/main/java/**/service/**/*.java"],
            "controller": ["src/main/java/**/controller/**/*.java"],
            "entity": ["src/main/java/**/entity/**/*.java", "src/main/java/**/model/**/*.java"],
            "config": ["src/main/java/**/config/**/*.java"],
            "spring": ["src/main/java/**/*.java"],  # Spring affects everything
        }

        suggested = []
        for keyword, patterns in patterns_map.items():
            if keyword in intent_lower:
                suggested.extend(patterns)

        # Remove duplicates while preserving order
        suggested = list(dict.fromkeys(suggested))

        # Default if no matches
        if not suggested:
            suggested = ["src/main/java/**/*.java"]

        logger.debug(f"Suggested file patterns for {intent}: {suggested}")
        return suggested

    # Tool: Suggest common exclusions
    @agent.tool
    def suggest_exclusions(ctx: RunContext[IntakeDependencies]) -> list[str]:
        """
        Suggest common file exclusion patterns for java projects.

        Returns:
            list[str]: Common exclusion patterns.
        """
        exclusions = [
            "**/target/**",  # Maven build output
            "**/build/**",  # Gradle build output
            "**/out/**",  # IntelliJ build output
            "**/generated/**",  # Generated code
            "**/generated-sources/**",
            "**/.idea/**",  # IDE files
            "**/.gradle/**",  # Gradle cache
            "**/node_modules/**",  # If project has frontend
        ]

        logger.debug(f"Suggested exclusions: {exclusions}")
        return exclusions

    logger.info("Intake Agent created successfully.")
    return agent


async def run_intake_agent(
    user_prompt: str,
    dependencies: IntakeDependencies,
    adapter: PydanticAIAdapter | None = None,
) -> tuple[JobSpec, RefactorMetadata]:
    """
    Run the Intake Agent with a user prompt.

    Convenience functions that creates the agent, runs it and captures metadata.

    Args:
        user_prompt: User's refactoring request.
        dependencies: Intake Agent dependencies.
        adapter: Optional PydanticAIAdapter (Creates new one if not provided).

    Returns:
        tuple: (JobSpec, RefactorMetadata) with the parsed job spec and metadata.

    Example:
        from repoai.dependencies import IntakeDependencies

        deps = IntakeDependencies(
            user_id="user_123",
            session_id="session_456"
        )

        job_spec, metadata = await run_intake_agent(
            "Add JWT authentication to user service",
            deps
        )

        print(f"Intent: {job_spec.intent}")
        print(f"Confidence: {metadata.confidence_score}")
    """
    if adapter is None:
        adapter = PydanticAIAdapter()

    # Create the Intake Agent
    intake_agent = create_intake_agent(adapter)

    logger.info(f"Running Intake Agent for user: {dependencies.user_id}")
    logger.debug(f"User Prompt: {user_prompt}")

    # Track Timing
    start_time = time.time()

    # Run the agent
    result = await intake_agent.run(user_prompt, deps=dependencies)

    # Calculation duration
    duration_ms = (time.time() - start_time) * 1000

    # Extract JobSpec
    job_spec: JobSpec = result.output

    # Get model used
    model_used = adapter.get_spec(role=ModelRole.INTAKE).model_id

    # Create Metadata
    metadata = RefactorMetadata(
        timestamp=datetime.now(),
        agent_name="IntakeAgent",
        model_used=model_used,
        confidence_score=0.95,  # TODO: Calculate actual confidence
        reasoning_chain=[
            f"Parsed user prompt: {user_prompt[:100]}...",
            f"Identified intent: {job_spec.intent}",
            f"Determined scope: {len(job_spec.scope.target_packages)} packages, {len(job_spec.scope.target_files)} file patterns",
            f"Extracted {len(job_spec.requirements)} requirements",
            f"Identified {len(job_spec.constraints)} constraints",
        ],
        data_sources=["user_prompt"],
        execution_time_ms=duration_ms,
    )

    # Attach metadata to the JobSpec
    job_spec.metadata = metadata

    logger.info(
        f"Intake Agent completed: intent='{job_spec.intent}', "
        f"duration={duration_ms:.0f}ms, "
        f"requirements={len(job_spec.requirements)}, "
        f"constraints={len(job_spec.constraints)}"
    )
    return job_spec, metadata
