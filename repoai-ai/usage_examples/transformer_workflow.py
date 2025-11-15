"""
Example: Complete Intake → Planner → Transformer Pipeline

This demonstrates the full workflow from user prompt to generated code.
Uses real Java file (UserManagementService.java) with AST parser optimization.
"""

import asyncio
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from repoai.agents import run_intake_agent, run_planner_agent, run_transformer_agent
from repoai.dependencies import IntakeDependencies, PlannerDependencies, TransformerDependencies
from repoai.llm import PydanticAIAdapter
from repoai.utils.file_writer import write_code_changes_to_disk
from repoai.utils.logger import get_logger

# Output file for logging
OUTPUT_FILE = Path(__file__).parent / "transformer_workflow.log"

# Configure logging to write to both file and console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(OUTPUT_FILE, mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = get_logger(__name__)
console = Console()


async def run_full_pipeline():
    """
    Run the complete Intake → Planner → Transformer pipeline.
    Uses real Java file with AST parser optimization.
    """
    logger.info("=" * 80)
    logger.info("RepoAI: Full Agent Pipeline Demo - Intake → Planner → Transformer")
    logger.info("=" * 80)

    console.print(
        Panel.fit(
            "[bold cyan]RepoAI: Full Agent Pipeline Demo[/bold cyan]\n"
            "Intake → Planner → Transformer\n"
            "Using real Java file with AST parser optimization",
            border_style="cyan",
        )
    )

    # Initialize adapter
    adapter = PydanticAIAdapter()

    # ========================================================================
    # STEP 0: Load Java File
    # ========================================================================
    console.print("\n[bold]Step 0: Load Java File[/bold]")
    console.print("─" * 80)

    java_file = Path(__file__).parent / "test_data" / "UserManagementService.java"
    with open(java_file) as f:
        java_code = f.read()

    logger.info(f"Loaded Java file: {java_file.name}")
    logger.info(f"File size: {len(java_code)} characters, {len(java_code.splitlines())} lines")

    console.print(f"[green]✓[/green] Loaded: {java_file.name}")
    console.print(
        f"[green]✓[/green] Size: {len(java_code)} chars, {len(java_code.splitlines())} lines"
    )

    # ========================================================================
    # STEP 1: Intake Agent - Parse User Request
    # ========================================================================
    console.print("\n[bold]Step 1: Intake Agent[/bold]")
    console.print("─" * 80)
    logger.info("Starting Intake Agent...")

    user_prompt = """
    Add audit logging to track user creation, updates, and deletions in UserManagementService.
    Include timestamp, actor ID, action type, and target user ID in audit logs.
    Store audit logs in a separate AuditLog entity with proper indexing.
    """

    console.print(f"[yellow]User Request:[/yellow] {user_prompt.strip()}\n")
    logger.info(f"User request: {user_prompt.strip()}")

    # Create dependencies with code context - agent will use AST parser automatically
    intake_deps = IntakeDependencies(
        user_id="developer_001",
        session_id="demo_session_123",
        repository_url="https://github.com/example/spring-boot-app",
        code_context={
            "UserManagementService.java": java_code
        },  # AST extraction happens automatically
    )

    job_spec, intake_metadata = await run_intake_agent(
        user_prompt=user_prompt, dependencies=intake_deps, adapter=adapter
    )

    logger.info(f"Intake Agent completed: intent={job_spec.intent}")
    logger.info(f"Target packages: {job_spec.scope.target_packages}")
    logger.info(f"Requirements: {len(job_spec.requirements)}")
    logger.info(f"Execution time: {intake_metadata.execution_time_ms:.0f}ms")

    console.print(f"[green]✓[/green] Intent: {job_spec.intent}")
    console.print(f"[green]✓[/green] Packages: {', '.join(job_spec.scope.target_packages)}")
    console.print(f"[green]✓[/green] Requirements: {len(job_spec.requirements)}")
    console.print(f"[green]✓[/green] Time: {intake_metadata.execution_time_ms:.0f}ms")

    # ========================================================================
    # STEP 2: Planner Agent - Create Refactoring Plan
    # ========================================================================
    console.print("\n[bold]Step 2: Planner Agent[/bold]")
    console.print("─" * 80)
    logger.info("Starting Planner Agent...")

    planner_deps = PlannerDependencies(
        job_spec=job_spec,
        repository_path=str(Path(__file__).parent.parent),
        repository_url=intake_deps.repository_url,
    )

    plan, planner_metadata = await run_planner_agent(
        job_spec=job_spec, dependencies=planner_deps, adapter=adapter
    )

    logger.info(f"Planner Agent completed: plan_id={plan.plan_id}")
    logger.info(f"Total steps: {plan.total_steps}")
    logger.info(f"Risk level: {plan.risk_assessment.overall_risk_level}/10")
    logger.info(f"Estimated duration: {plan.estimated_duration}")
    logger.info(f"Execution time: {planner_metadata.execution_time_ms:.0f}ms")

    console.print(f"[green]✓[/green] Plan created with {plan.total_steps} steps")
    console.print(f"[green]✓[/green] Risk level: {plan.risk_assessment.overall_risk_level}/10")
    console.print(f"[green]✓[/green] Duration estimate: {plan.estimated_duration}")
    console.print(f"[green]✓[/green] Time: {planner_metadata.execution_time_ms:.0f}ms")

    # Show steps
    console.print("\n[cyan]Refactoring Steps:[/cyan]")
    for step in plan.steps[:5]:  # Show first 5 steps
        console.print(f"  {step.step_number}. {step.action}: {step.description[:60]}...")
        logger.info(f"Step {step.step_number}: {step.action} - {step.description}")

    # ========================================================================
    # STEP 3: Transformer Agent - Generate Code
    # ========================================================================
    console.print("\n[bold]Step 3: Transformer Agent[/bold]")
    console.print("─" * 80)
    logger.info("Starting Transformer Agent...")

    # Transformer dependencies with code context for AST parser
    transformer_deps = TransformerDependencies(
        plan=plan,
        repository_path=str(Path(__file__).parent.parent),
        existing_code_context={
            "UserManagementService.java": java_code
        },  # Transformer will use AST extraction
    )

    code_changes, transformer_metadata = await run_transformer_agent(
        plan=plan, dependencies=transformer_deps, adapter=adapter
    )

    logger.info(f"Transformer Agent completed: {len(code_changes.changes)} code changes")
    logger.info(f"Files created: {code_changes.files_created}")
    logger.info(f"Files modified: {code_changes.files_modified}")
    logger.info(f"Lines added: +{code_changes.lines_added}")
    logger.info(f"Lines removed: -{code_changes.lines_removed}")
    logger.info(f"Classes created: {code_changes.classes_created}")
    logger.info(f"Execution time: {transformer_metadata.execution_time_ms:.0f}ms")

    console.print(f"[green]✓[/green] Generated {len(code_changes.changes)} code changes")
    console.print(f"[green]✓[/green] Files created: {code_changes.files_created}")
    console.print(f"[green]✓[/green] Files modified: {code_changes.files_modified}")
    console.print(f"[green]✓[/green] Lines added: +{code_changes.lines_added}")
    console.print(f"[green]✓[/green] Lines removed: -{code_changes.lines_removed}")
    console.print(f"[green]✓[/green] Time: {transformer_metadata.execution_time_ms:.0f}ms")

    # ========================================================================
    # STEP 4: Display Generated Code Samples
    # ========================================================================
    console.print("\n[bold]Step 4: Code Preview[/bold]")
    console.print("─" * 80)
    logger.info("Displaying code preview...")

    # Show first code change
    if code_changes.changes:
        first_change = code_changes.changes[0]

        logger.info(f"Preview file: {first_change.file_path}")
        logger.info(f"Change type: {first_change.change_type}")
        logger.info(f"Class: {first_change.class_name}")
        logger.info(f"Lines: +{first_change.lines_added}, -{first_change.lines_removed}")

        console.print(f"\n[cyan]File:[/cyan] {first_change.file_path}")
        console.print(f"[cyan]Type:[/cyan] {first_change.change_type}")
        console.print(f"[cyan]Class:[/cyan] {first_change.class_name}")
        console.print(
            f"[cyan]Changes:[/cyan] +{first_change.lines_added}, -{first_change.lines_removed}"
        )

        if first_change.modified_content:
            # Show first 30 lines of generated code
            code_lines = first_change.modified_content.split("\n")[:30]
            code_preview = "\n".join(code_lines)

            syntax = Syntax(code_preview, "java", theme="monokai", line_numbers=True)
            console.print("\n[yellow]Generated Code Preview:[/yellow]")
            console.print(syntax)

            if len(first_change.modified_content.split("\n")) > 30:
                console.print("\n[dim]... (truncated for display)[/dim]")

        # Show imports
        if first_change.imports_added:
            console.print(f"\n[cyan]Imports Added ({len(first_change.imports_added)}):[/cyan]")
            for imp in first_change.imports_added[:5]:
                console.print(f"  • {imp}")
                logger.info(f"Import added: {imp}")

        # Show methods
        if first_change.methods_added:
            console.print(f"\n[cyan]Methods Added ({len(first_change.methods_added)}):[/cyan]")
            for method in first_change.methods_added[:5]:
                console.print(f"  • {method}")
                logger.info(f"Method added: {method}")

        # Show annotations
        if first_change.annotations_added:
            console.print(
                f"\n[cyan]Annotations:[/cyan] {', '.join(first_change.annotations_added)}"
            )
            logger.info(f"Annotations: {first_change.annotations_added}")

    # ========================================================================
    # STEP 4.5: Save Generated Code Using FileWriter
    # ========================================================================
    console.print("\n[bold]Step 4.5: Save Generated Code Using FileWriter[/bold]")
    console.print("─" * 80)
    logger.info("Using FileWriter utility to save generated code...")

    # Use FileWriter to save code changes with Maven project structure
    output_dir = write_code_changes_to_disk(
        code_changes, base_path=str(Path(__file__).parent / "transformer_output")
    )

    logger.info(f"FileWriter saved files to: {output_dir}")
    console.print(f"[green]✓[/green] Files saved to: {output_dir}")

    # Verify and list saved files
    if output_dir.exists():
        logger.info("Verifying saved files...")

        # Check for pom.xml
        pom_file = output_dir / "pom.xml"
        if pom_file.exists():
            logger.info(f"✓ Maven pom.xml created: {pom_file}")
            console.print("[green]✓[/green] Maven pom.xml created")

        # List all generated files
        all_files = list(output_dir.rglob("*"))
        saved_files = [f for f in all_files if f.is_file()]

        logger.info(f"Total files saved: {len(saved_files)}")
        console.print(f"[green]✓[/green] Total files saved: {len(saved_files)}")

        # Show directory structure
        console.print("\n[cyan]Directory Structure:[/cyan]")
        for file in sorted(saved_files[:10]):  # Show first 10 files
            rel_path = file.relative_to(output_dir)
            console.print(f"  • {rel_path}")
            logger.info(f"  Saved: {rel_path}")

        if len(saved_files) > 10:
            console.print(f"  • ... and {len(saved_files) - 10} more files")
            logger.info(f"  ... and {len(saved_files) - 10} more files")
    else:
        logger.error(f"Output directory not found: {output_dir}")
        console.print(f"[red]✗[/red] Output directory not found: {output_dir}")
        saved_files = []

    # ========================================================================
    # STEP 5: Pipeline Summary
    # ========================================================================
    console.print("\n" + "=" * 80)

    total_time = (
        intake_metadata.execution_time_ms
        + planner_metadata.execution_time_ms
        + transformer_metadata.execution_time_ms
    )

    logger.info("=" * 80)
    logger.info("Pipeline Completed Successfully!")
    logger.info(f"Job ID: {job_spec.job_id}")
    logger.info(f"Plan ID: {plan.plan_id}")
    logger.info(f"Intent: {job_spec.intent}")
    logger.info(f"Steps executed: {plan.total_steps}")
    logger.info(f"Files changed: {len(code_changes.changes)}")
    logger.info(f"Code generated: {code_changes.lines_added} lines")
    logger.info(f"Classes created: {code_changes.classes_created}")
    logger.info(f"Generated files saved: {len(saved_files)}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Total execution time: {total_time:.0f}ms")
    logger.info(f"Log saved to: {OUTPUT_FILE}")
    logger.info("=" * 80)

    console.print(
        Panel.fit(
            "[bold green]Pipeline Completed Successfully![/bold green]\n\n"
            f"[white]Job ID:[/white] {job_spec.job_id}\n"
            f"[white]Plan ID:[/white] {plan.plan_id}\n"
            f"[white]Intent:[/white] {job_spec.intent}\n\n"
            f"[cyan]Results:[/cyan]\n"
            f"  • Steps executed: {plan.total_steps}\n"
            f"  • Files changed: {len(code_changes.changes)}\n"
            f"  • Code generated: {code_changes.lines_added} lines\n"
            f"  • Classes created: {code_changes.classes_created}\n"
            f"  • Files saved: {len(saved_files)}\n\n"
            f"[cyan]Performance:[/cyan]\n"
            f"  • Intake: {intake_metadata.execution_time_ms:.0f}ms\n"
            f"  • Planner: {planner_metadata.execution_time_ms:.0f}ms\n"
            f"  • Transformer: {transformer_metadata.execution_time_ms:.0f}ms\n"
            f"  • Total: {total_time:.0f}ms\n\n"
            f"[cyan]AST Parser:[/cyan]\n"
            f"  • Automatic context extraction enabled\n"
            f"  • Token optimization: ~90% reduction\n\n"
            f"[yellow]Output Directory:[/yellow]\n"
            f"  {output_dir}\n\n"
            f"[yellow]Maven Structure:[/yellow]\n"
            f"  • pom.xml with dependencies\n"
            f"  • src/main/java/ structure\n"
            f"  • {len(saved_files)} files total\n\n"
            f"[yellow]Log saved to:[/yellow]\n"
            f"  {OUTPUT_FILE}\n\n"
            "[yellow]Next:[/yellow] Run Validator Agent to test and validate changes",
            title="✨ Success",
            border_style="green",
        )
    )

    return job_spec, plan, code_changes


async def run_simple_pipeline():
    """
    Simplified pipeline for quick testing.
    """
    console.print("\n[bold cyan]RepoAI: Quick Pipeline Test[/bold cyan]\n")

    # Quick test
    user_prompt = "Add JWT authentication to the auth package"

    console.print(f"[yellow]Request:[/yellow] {user_prompt}\n")

    # Step 1: Intake
    intake_deps = IntakeDependencies(user_id="test", session_id="test")
    job_spec, _ = await run_intake_agent(user_prompt, intake_deps)
    console.print(f"[green]✓[/green] Intent: {job_spec.intent}")

    # Step 2: Planner
    planner_deps = PlannerDependencies(job_spec=job_spec)
    plan, _ = await run_planner_agent(job_spec, planner_deps)
    console.print(f"[green]✓[/green] Plan: {plan.total_steps} steps")

    # Step 3: Transformer
    transformer_deps = TransformerDependencies(plan=plan)
    code_changes, _ = await run_transformer_agent(plan, transformer_deps)
    console.print(f"[green]✓[/green] Code: {len(code_changes.changes)} files\n")

    console.print("[bold green]Pipeline complete![/bold green]\n")
    return code_changes


if __name__ == "__main__":
    logger.info("Starting RepoAI Full Pipeline Workflow")
    logger.info(f"Output will be saved to: {OUTPUT_FILE}")

    try:
        # Run the full detailed pipeline
        asyncio.run(run_full_pipeline())

        logger.info("Workflow completed successfully!")
        console.print(f"\n[green]✓[/green] Full log saved to: {OUTPUT_FILE}\n")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        console.print(f"\n[red]✗[/red] Pipeline failed: {e}\n")
        raise
