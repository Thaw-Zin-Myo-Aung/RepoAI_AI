"""
Example: Using Intake Agent → Planner Agent Pipeline

This demonstrates the complete workflow from user prompt to refactoring plan.
"""

import asyncio

from repoai.agents.intake_agent import run_intake_agent
from repoai.agents.planner_agent import run_planner_agent
from repoai.dependencies import IntakeDependencies, PlannerDependencies
from repoai.llm import PydanticAIAdapter
from repoai.utils.logger import get_logger, setup_logging

# Set up logging
setup_logging()
logger = get_logger(__name__)


async def run_complete_pipeline():
    """
    Run the complete Intake → Planner pipeline.

    This example shows:
    1. User provides a refactoring request
    2. Intake Agent parses it into a JobSpec
    3. Planner Agent creates a detailed RefactorPlan
    """

    # Initialize the adapter (uses Gemini models from .env)
    adapter = PydanticAIAdapter()

    # ========================================================================
    # Step 1: Intake Agent - Parse User Request
    # ========================================================================
    logger.info("=" * 80)
    logger.info("STEP 1: Running Intake Agent")
    logger.info("=" * 80)

    user_prompt = """
    Add JWT authentication to the user service and protect /api/*
    Use the latest Spring Security with JWT tokens.
    The authentication should work alongside our existing session-based auth 
    for backward compatibility. Focus on the com.example.auth and 
    com.example.security packages.
    """

    intake_deps = IntakeDependencies(
        user_id="user_123",
        session_id="session_456",
        repository_url="https://github.com/example/spring-boot-app",
    )

    # Run Intake Agent
    job_spec, intake_metadata = await run_intake_agent(
        user_prompt=user_prompt, dependencies=intake_deps, adapter=adapter
    )

    logger.info("\n✅ Intake Agent Complete!")
    logger.info(f"   Job ID: {job_spec.job_id}")
    logger.info(f"   Intent: {job_spec.intent}")
    logger.info(f"   Target Packages: {', '.join(job_spec.scope.target_packages)}")
    logger.info(f"   Requirements: {len(job_spec.requirements)} items")
    logger.info(f"   Constraints: {len(job_spec.constraints)} items")
    logger.info(f"   Execution Time: {intake_metadata.execution_time_ms:.0f}ms\n")

    # ========================================================================
    # Step 2: Planner Agent - Create Refactoring Plan
    # ========================================================================
    logger.info("=" * 80)
    logger.info("STEP 2: Running Planner Agent")
    logger.info("=" * 80)

    planner_deps = PlannerDependencies(
        job_spec=job_spec,
        repository_path="/path/to/local/repo",  # Optional
        repository_url=intake_deps.repository_url,
    )

    # Run Planner Agent
    plan, planner_metadata = await run_planner_agent(
        job_spec=job_spec, dependencies=planner_deps, adapter=adapter
    )

    logger.info("\n✅ Planner Agent Complete!")
    logger.info(f"   Plan ID: {plan.plan_id}")
    logger.info(f"   Total Steps: {plan.total_steps}")
    logger.info(f"   Overall Risk: {plan.risk_assessment.overall_risk_level}/10")
    logger.info(f"   Estimated Duration: {plan.estimated_duration}")
    logger.info(f"   Execution Time: {planner_metadata.execution_time_ms:.0f}ms\n")

    # ========================================================================
    # Step 3: Display Detailed Plan
    # ========================================================================
    logger.info("=" * 80)
    logger.info("REFACTORING PLAN DETAILS")
    logger.info("=" * 80)

    for step in plan.steps:
        logger.info(f"\nStep {step.step_number}: {step.action}")
        logger.info(f"  Description: {step.description}")
        logger.info(f"  Target Files: {', '.join(step.target_files)}")
        if step.target_classes:
            logger.info(f"  Target Classes: {', '.join(step.target_classes)}")
        logger.info(f"  Risk Level: {step.risk_level}/10")
        logger.info(f"  Estimated Time: {step.estimated_time_mins} minutes")
        if step.dependencies:
            logger.info(f"  Depends On: Steps {', '.join(map(str, step.dependencies))}")

    # ========================================================================
    # Step 4: Display Risk Assessment
    # ========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("RISK ASSESSMENT")
    logger.info("=" * 80)

    risk = plan.risk_assessment
    logger.info(f"\nOverall Risk Level: {risk.overall_risk_level}/10")
    logger.info(f"Breaking Changes: {risk.breaking_changes}")
    logger.info(f"Compilation Risk: {risk.compilation_risk}")
    logger.info(f"Dependency Conflicts: {risk.dependency_conflicts}")
    logger.info("\nAffected Modules:")
    for module in risk.affected_modules:
        logger.info(f"  - {module}")

    logger.info("\nFramework Impacts:")
    for framework in risk.framework_impacts:
        logger.info(f"  - {framework}")

    logger.info("\nMitigation Strategies:")
    for i, strategy in enumerate(risk.mitigation_strategies, 1):
        logger.info(f"  {i}. {strategy}")

    logger.info(f"\nRequired Test Coverage: {risk.test_coverage_required * 100}%")

    # ========================================================================
    # Step 5: Summary
    # ========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("PIPELINE SUMMARY")
    logger.info("=" * 80)
    logger.info("\n✅ Successfully generated refactoring plan!")
    logger.info(f"   Total Steps: {plan.total_steps}")
    logger.info(f"   High-Risk Steps: {len(plan.high_risk_steps)}")
    logger.info(
        f"   Total Time: {intake_metadata.execution_time_ms + planner_metadata.execution_time_ms:.0f}ms"
    )
    logger.info("\n🚀 Ready for Transformer Agent (code generation phase)\n")

    return job_spec, plan


async def run_simple_example():
    """
    Simplified example for quick testing.
    """
    # Simple refactoring request
    user_prompt = """
    Add JWT authentication to the user service and protect /api/* endpoints.
    Use Spring Security with JWT tokens for the auth layer.
    """

    # Intake phase
    intake_deps = IntakeDependencies(
        user_id="dev_001",
        session_id="test_session",
    )

    job_spec, _ = await run_intake_agent(user_prompt, intake_deps)

    print("\n📋 JobSpec Created:")
    print(f"   Intent: {job_spec.intent}")
    print(f"   Packages: {job_spec.scope.target_packages}")

    print(f"JobSpec Details:\n{job_spec}\n")
    print("=" * 80 + "\n")
    print(f"Metadata:\n{_}\n")

    # Planning phase
    planner_deps = PlannerDependencies(job_spec=job_spec)
    plan, _ = await run_planner_agent(job_spec, planner_deps)

    print("\n📝 RefactorPlan Created:")
    print(f"   Steps: {plan.total_steps}")
    print(f"   Risk: {plan.risk_assessment.overall_risk_level}/10")
    print(f"   Duration: {plan.estimated_duration}")

    print(f"RefactorPlan Details:\n{plan}\n")
    print("=" * 80 + "\n")
    print(f"Metadata:\n{_}\n")

    return plan


if __name__ == "__main__":
    # Run the complete pipeline
    print("\n🤖 RepoAI: Intake → Planner Pipeline Demo\n")

    # Choose which example to run:
    asyncio.run(run_complete_pipeline())  # Detailed example with JWT authentication
    # asyncio.run(run_simple_example())  # Quick example with JPA refactoring
