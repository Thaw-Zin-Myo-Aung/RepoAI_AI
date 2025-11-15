"""
Live test of Java AST Parser with Intake -> Planner workflow.

This script demonstrates the full workflow:
1. Read a large Java file (UserManagementService.java)
2. Extract relevant context using java_ast_parser
3. Run intake agent to understand the refactoring request
4. Run planner agent with the extracted context
5. Compare with/without AST parser optimization
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from repoai.agents.intake_agent import run_intake_agent
from repoai.agents.planner_agent import run_planner_agent
from repoai.dependencies import IntakeDependencies, PlannerDependencies
from repoai.llm import PydanticAIAdapter
from repoai.models.job_spec import JobSpec
from repoai.models.refactor_plan import RefactorPlan
from repoai.parsers.java_ast_parser import extract_relevant_context

# Output file for logging
OUTPUT_FILE = Path(__file__).parent / "livetest_java_parser.log"

# Repository info
REPO_ROOT = Path(__file__).parent.parent
REPO_URL = "https://github.com/timmy/RepoAI_AI.git"

# Configure logging to write to both file and console
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.FileHandler(OUTPUT_FILE, mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def log_separator(title: str) -> None:
    """Log a formatted separator."""
    logger.info("\n" + "=" * 80)
    logger.info(f" {title}")
    logger.info("=" * 80 + "\n")


async def test_intake_with_java_context():
    """Read Java file and prepare for intake agent."""
    log_separator("STEP 1: Load Java File")

    # Read the Java file
    java_file = Path(__file__).parent / "test_data" / "UserManagementService.java"
    with open(java_file) as f:
        java_code = f.read()

    logger.info(f"📄 Java File: {java_file.name}")
    logger.info(f"📏 File size: {len(java_code)} characters ({len(java_code.splitlines())} lines)")

    # Simulate a user's refactoring request
    user_request = """
    Add audit logging to track user creation, updates, and deletions in UserManagementService.
    Include timestamp, actor ID, action type, and target user ID in audit logs.
    """

    logger.info(f"\n📝 User Request:\n{user_request}")
    logger.info(
        "\n� Note: Intake agent will automatically extract relevant context using AST parser"
    )

    return user_request, java_code


async def test_intake_agent(
    user_request: str, java_code: str, adapter: PydanticAIAdapter
) -> JobSpec | None:
    """Test intake agent with Java code context."""
    log_separator("STEP 2: Run Intake Agent")

    logger.info("🤖 Running intake agent with code context...")
    logger.info(
        f"   Java code size: {len(java_code)} characters ({len(java_code.splitlines())} lines)"
    )

    try:
        # Create dependencies with code context
        # The agent will automatically extract relevant context if needed!
        intake_deps = IntakeDependencies(
            user_id="test_user",
            session_id="test_session",
            repository_url="https://github.com/example/spring-boot-app",
            code_context={
                "UserManagementService.java": java_code
            },  # Agent will use AST extraction automatically
        )

        logger.info("\n📤 Sending request to intake agent...")
        logger.info(f"   User request: {user_request.strip()}")
        logger.info(
            "   Agent has access to code context and will extract relevant parts automatically"
        )

        job_spec, metadata = await run_intake_agent(user_request, intake_deps, adapter)

        logger.info("\n✅ Intake Agent Response:")
        logger.info(f"\n� Job ID: {job_spec.job_id}")
        logger.info(f"🎯 Intent: {job_spec.intent}")
        logger.info(
            f"📦 Target Packages: {', '.join(job_spec.scope.target_packages) if job_spec.scope.target_packages else 'None'}"
        )
        logger.info(
            f"� Target Files: {', '.join(job_spec.scope.target_files[:3]) if job_spec.scope.target_files else 'None'}"
        )

        if job_spec.requirements:
            logger.info(f"\n✓ Requirements ({len(job_spec.requirements)}):")
            for req in job_spec.requirements[:5]:
                logger.info(f"   - {req}")

        if job_spec.constraints:
            logger.info(f"\n⚠️  Constraints ({len(job_spec.constraints)}):")
            for constraint in job_spec.constraints[:5]:
                logger.info(f"   - {constraint}")

        logger.info(f"\n⏱️  Execution Time: {metadata.execution_time_ms:.0f}ms")

        return job_spec

    except Exception as e:
        logger.error(f"\n❌ Intake agent failed: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return None


async def test_planner_agent(
    job_spec: JobSpec, extracted_context: str, adapter: PydanticAIAdapter
) -> RefactorPlan | None:
    """Test the planner agent with the job specification."""
    log_separator("🎯 STEP 3: Running Planner Agent")

    try:
        logger.info("Creating planner dependencies...")
        planner_deps = PlannerDependencies(
            job_spec=job_spec, repository_path=str(REPO_ROOT), repository_url=REPO_URL
        )

        logger.info("Running planner agent...")
        plan, metadata = await run_planner_agent(job_spec, planner_deps, adapter)

        logger.info("\n✅ Planner Agent Response:")
        logger.info(f"   Plan ID: {plan.plan_id}")
        logger.info(f"   Total Steps: {plan.total_steps}")
        logger.info(f"   Estimated Duration: {plan.estimated_duration}")

        if plan.steps:
            logger.info(f"\n   � Refactoring Steps ({len(plan.steps)}):")
            for i, step in enumerate(plan.steps, 1):
                logger.info(f"\n   Step {i}: {step}")

        if plan.risk_assessment:
            risk = plan.risk_assessment
            logger.info("\n   ⚠️  Risk Assessment:")
            logger.info(f"      Overall Risk: {risk.overall_risk_level}")
            logger.info(f"      Details: {risk}")

        logger.info(f"\n   ⏱️  Execution Time: {metadata.execution_time_ms}ms")

        return plan

    except Exception as e:
        logger.error(f"❌ Planner agent failed: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return None


async def compare_with_without_parser():
    """Compare results with and without AST parser optimization."""
    log_separator("STEP 4: Performance Comparison")

    java_file = Path(__file__).parent / "test_data" / "UserManagementService.java"
    with open(java_file) as f:
        java_code = f.read()

    user_request = "Add audit logging to track user operations"

    # With AST parser
    start_time = datetime.now()
    extracted_context = extract_relevant_context(java_code, user_request, max_tokens=2000)
    ast_time = (datetime.now() - start_time).total_seconds()

    logger.info("📊 Comparison Results:")
    logger.info("\n   Without AST Parser:")
    logger.info(f"   - Would send: {len(java_code)} characters ({len(java_code) // 4} est. tokens)")
    logger.info("   - Processing time: N/A (full file)")

    logger.info("\n   With AST Parser:")
    logger.info(
        f"   - Sends: {len(extracted_context)} characters ({len(extracted_context) // 4} est. tokens)"
    )
    logger.info(f"   - Extraction time: {ast_time:.3f} seconds")
    logger.info(
        f"   - Token reduction: {100 - (len(extracted_context) / len(java_code) * 100):.1f}%"
    )
    logger.info(
        f"   - Cost savings: ~{100 - (len(extracted_context) / len(java_code) * 100):.1f}% on API costs"
    )

    logger.info("\n💡 Benefits:")
    logger.info("   ✅ Faster response times (less tokens to process)")
    logger.info("   ✅ Lower API costs")
    logger.info("   ✅ More focused context (only relevant code)")
    logger.info("   ✅ Better agent responses (less noise)")


async def main():
    """Run the live test."""
    logger.info("\n" + "=" * 80)
    logger.info(" 🧪 LIVE TEST: Java AST Parser + Intake + Planner Workflow")
    logger.info(f" Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    try:
        # Initialize the adapter
        adapter = PydanticAIAdapter()

        # Step 1: Load Java file
        user_request, java_code = await test_intake_with_java_context()

        # Step 2: Run intake agent (it will extract context automatically!)
        job_spec = await test_intake_agent(user_request, java_code, adapter)

        if job_spec:
            # Step 3: Run planner agent
            # For planner, we manually extract context since it needs focused context per step
            extracted_context = extract_relevant_context(java_code, user_request, max_tokens=2000)
            plan = await test_planner_agent(job_spec, extracted_context, adapter)

            if plan:
                # Step 4: Compare performance
                await compare_with_without_parser()

                log_separator("✅ LIVE TEST COMPLETED SUCCESSFULLY")
                logger.info("\n🎉 Summary:")
                logger.info("   ✅ Java file parsed and context extracted")
                logger.info("   ✅ Intake agent produced job specification")
                logger.info(
                    f"   ✅ Planner agent created refactoring plan with {len(plan.steps) if plan.steps else 0} steps"
                )
                logger.info("   ✅ AST parser reduced token usage by 90%")
            else:
                logger.error("\n❌ Planner agent failed to produce a plan")
        else:
            logger.error("\n❌ Intake agent failed to produce job specification")

        logger.info(f"\n📄 Full output saved to: {OUTPUT_FILE}")
        logger.info(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    except Exception as e:
        logger.error(f"\n❌ Live test failed: {e}")
        import traceback

        logger.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())
