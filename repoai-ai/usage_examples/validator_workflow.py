"""
Example: Complete Intake → Planner → Transformer → Validator Pipeline

This demonstrates the full 4-agent workflow from user prompt to validated code.
Uses real Java file (UserManagementService.java) with AST parser optimization.
"""

import asyncio
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from repoai.agents import (
    run_intake_agent,
    run_planner_agent,
    run_transformer_agent,
    run_validator_agent,
)
from repoai.dependencies import (
    IntakeDependencies,
    PlannerDependencies,
    TransformerDependencies,
    ValidatorDependencies,
)
from repoai.llm import PydanticAIAdapter
from repoai.utils.file_writer import write_code_changes_to_disk
from repoai.utils.logger import get_logger

# Output file for logging
OUTPUT_FILE = Path(__file__).parent / "validator_workflow.log"

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
    Run the complete Intake → Planner → Transformer → Validator pipeline.
    Uses real Java file with AST parser optimization.
    """
    logger.info("=" * 80)
    logger.info("RepoAI: Full Agent Pipeline Demo - Intake → Planner → Transformer → Validator")
    logger.info("=" * 80)

    console.print(
        Panel.fit(
            "[bold cyan]RepoAI: Full 4-Agent Pipeline Demo[/bold cyan]\n"
            "Intake → Planner → Transformer → Validator\n"
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
        code_context={"UserManagementService.java": java_code},
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

    console.print("\n[cyan]Refactoring Steps:[/cyan]")
    for i, step in enumerate(plan.steps[:5], 1):
        step_desc = (
            step.description[:70] + "..." if len(step.description) > 70 else step.description
        )
        console.print(f"  {i}. {step.action}: {step_desc}")
        logger.info(f"Step {i}: {step.action} - {step.description}")

    # ========================================================================
    # STEP 3: Transformer Agent - Generate Code
    # ========================================================================
    console.print("\n[bold]Step 3: Transformer Agent[/bold]")
    console.print("─" * 80)
    logger.info("Starting Transformer Agent...")

    transformer_deps = TransformerDependencies(
        plan=plan,
        repository_path=str(Path(__file__).parent.parent),
        repository_url=intake_deps.repository_url,
        existing_code_context=intake_deps.code_context,
        java_version="17",
        write_to_disk=True,
        output_path=None,  # Will use default /tmp/repoai
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
    # STEP 4: Code Preview (First change only)
    # ========================================================================
    console.print("\n[bold]Step 4: Code Preview[/bold]")
    console.print("─" * 80)
    logger.info("Displaying code preview...")

    if code_changes.changes:
        first_change = code_changes.changes[0]
        logger.info(f"Preview file: {first_change.file_path}")
        logger.info(f"Change type: {first_change.change_type}")
        logger.info(f"Class: {first_change.class_name}")
        logger.info(f"Lines: +{first_change.lines_added}, -{first_change.lines_removed}")

        console.print(f"\n[cyan]File:[/cyan] {first_change.file_path}")
        console.print(f"[cyan]Type:[/cyan] {first_change.change_type}")
        console.print(f"[cyan]Class:[/cyan] {first_change.class_name or 'None'}")
        console.print(
            f"[cyan]Changes:[/cyan] +{first_change.lines_added}, -{first_change.lines_removed}"
        )

        console.print("\n[yellow]Generated Code Preview:[/yellow]")
        if first_change.modified_content:
            preview_lines = first_change.modified_content.split("\n")[:30]
            preview = "\n".join(preview_lines)
            syntax = Syntax(preview, "java", theme="monokai", line_numbers=True, word_wrap=False)
            console.print(syntax)
            if len(first_change.modified_content.split("\n")) > 30:
                console.print("\n... (truncated for display)")

    # ========================================================================
    # STEP 4.5: Save Generated Code Using FileWriter
    # ========================================================================
    console.print("\n[bold]Step 4.5: Save Generated Code Using FileWriter[/bold]")
    console.print("─" * 80)
    logger.info("Using FileWriter utility to save generated code...")

    # Use FileWriter to save code changes with Maven project structure
    output_dir = write_code_changes_to_disk(
        code_changes, base_path=str(Path(__file__).parent / "validator_output")
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
    # STEP 5: Validator Agent - Validate Code Quality
    # ========================================================================
    console.print("\n[bold]Step 5: Validator Agent[/bold]")
    console.print("─" * 80)
    logger.info("Starting Validator Agent...")

    validator_deps = ValidatorDependencies(
        code_changes=code_changes,
        repository_path=str(output_dir) if output_dir.exists() else None,
        test_files_path=None,
        run_tests=False,  # Static analysis only for demo
        run_static_analysis=False,  # Use built-in tools only
        min_test_coverage=0.7,
        strict_mode=False,
    )

    validation_result, validator_metadata = await run_validator_agent(
        code_changes=code_changes, dependencies=validator_deps, adapter=adapter
    )

    # Display validation results
    status_color = "green" if validation_result.passed else "red"
    status_icon = "✓" if validation_result.passed else "✗"

    console.print(
        f"[{status_color}]{status_icon}[/{status_color}] Validation: {'PASSED' if validation_result.passed else 'FAILED'}"
    )
    console.print(
        f"[{status_color}]{status_icon}[/{status_color}] Compilation: {'PASSED' if validation_result.compilation_passed else 'FAILED'}"
    )
    console.print(f"[green]•[/green] Checks: {len(validation_result.checks)}")
    console.print(f"[green]•[/green] Coverage: {validation_result.test_coverage * 100:.1f}%")
    console.print(
        f"[green]•[/green] Confidence: {validation_result.confidence.overall_confidence:.2f}"
    )
    console.print(f"[green]•[/green] Time: {validator_metadata.execution_time_ms:.0f}ms\n")

    # ========================================================================
    # Results Summary
    # ========================================================================
    console.print("\n" + "=" * 80)
    console.print("[bold]VALIDATION DETAILS[/bold]")
    console.print("=" * 80 + "\n")

    # Create checks table
    checks_table = Table(title="Validation Checks", show_header=True)
    checks_table.add_column("Check", style="cyan", width=25)
    checks_table.add_column("Status", width=10)
    checks_table.add_column("Issues", width=45)

    for check_result in validation_result.checks:
        check_name = check_result.name
        check = check_result.result
        status = "[green]✓ PASS[/green]" if check.passed else "[red]✗ FAIL[/red]"
        issues = ", ".join(check.issues[:2]) if check.issues else "None"
        if len(check.issues) > 2:
            issues += f" (+{len(check.issues) - 2} more)"
        checks_table.add_row(check_name, status, issues)

    console.print(checks_table)

    # Confidence metrics
    console.print("\n[bold]Confidence Metrics:[/bold]")
    console.print(f"  Overall: {validation_result.confidence.overall_confidence:.2f}")
    console.print(f"  Reasoning Quality: {validation_result.confidence.reasoning_quality:.2f}")
    console.print(f"  Code Safety: {validation_result.confidence.code_safety:.2f}")
    console.print(f"  Test Coverage: {validation_result.confidence.test_coverage:.2f}")
    console.print(f"  Quality Level: {validation_result.confidence.quality_level}")

    # Recommendations
    if validation_result.recommendations:
        console.print(f"\n[bold]Recommendations ({len(validation_result.recommendations)}):[/bold]")
        for i, rec in enumerate(validation_result.recommendations[:5], 1):
            console.print(f"  {i}. {rec}")
        if len(validation_result.recommendations) > 5:
            console.print(f"  ... and {len(validation_result.recommendations) - 5} more")

    # Failed checks
    if validation_result.failed_checks:
        console.print(
            f"\n[bold red]Failed Checks ({len(validation_result.failed_checks)}):[/bold red]"
        )
        for check_name in validation_result.failed_checks:
            check = validation_result.get_check(check_name)
            if check:
                console.print(f"  • {check_name}:")
                for issue in check.issues[:3]:
                    console.print(f"    - {issue}")

    # Security vulnerabilities
    if validation_result.security_vulnerabilities:
        console.print("\n[bold red]⚠️  Security Vulnerabilities:[/bold red]")
        for vuln in validation_result.security_vulnerabilities:
            console.print(f"  • {vuln}")

    # ========================================================================
    # STEP 7: Pipeline Summary
    # ========================================================================
    console.print("\n" + "=" * 80)
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
    logger.info(f"Validation: {'PASSED' if validation_result.passed else 'FAILED'}")
    logger.info(f"Confidence: {validation_result.confidence.overall_confidence:.2f}")
    logger.info(f"Output directory: {output_dir}")

    total_time = (
        intake_metadata.execution_time_ms
        + planner_metadata.execution_time_ms
        + transformer_metadata.execution_time_ms
        + validator_metadata.execution_time_ms
    )
    logger.info(f"Total execution time: {total_time:.0f}ms")
    logger.info(f"Log saved to: {OUTPUT_FILE}")
    logger.info("=" * 80)

    summary_color = "green" if validation_result.passed else "yellow"
    warning_text = (
        "" if validation_result.passed else "\n⚠️  Some validation checks failed - review above"
    )

    console.print(
        Panel.fit(
            f"[bold {summary_color}]Pipeline Completed Successfully!{warning_text}[/bold {summary_color}]\n\n"
            f"[white]Job ID:[/white] {job_spec.job_id}\n"
            f"[white]Plan ID:[/white] {plan.plan_id}\n"
            f"[white]Intent:[/white] {job_spec.intent}\n\n"
            f"[cyan]Results:[/cyan]\n"
            f"  • Steps executed: {plan.total_steps}\n"
            f"  • Files changed: {len(code_changes.changes)}\n"
            f"  • Code generated: {code_changes.lines_added} lines\n"
            f"  • Classes created: {code_changes.classes_created}\n"
            f"  • Files saved: {len(saved_files)}\n\n"
            f"[cyan]Validation:[/cyan]\n"
            f"  • Status: {'✓ PASSED' if validation_result.passed else '✗ FAILED'}\n"
            f"  • Compilation: {'✓ PASSED' if validation_result.compilation_passed else '✗ FAILED'}\n"
            f"  • Confidence: {validation_result.confidence.overall_confidence:.1%}\n"
            f"  • Test Coverage: {validation_result.test_coverage:.1%}\n"
            f"  • Failed checks: {len(validation_result.failed_checks)}\n\n"
            f"[cyan]Performance:[/cyan]\n"
            f"  • Intake: {intake_metadata.execution_time_ms:.0f}ms\n"
            f"  • Planner: {planner_metadata.execution_time_ms:.0f}ms\n"
            f"  • Transformer: {transformer_metadata.execution_time_ms:.0f}ms\n"
            f"  • Validator: {validator_metadata.execution_time_ms:.0f}ms\n"
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
            "[yellow]Next:[/yellow] Review validation results and address any failed checks",
            title=("✨ Success" if validation_result.passed else "⚠️  Completed with Warnings"),
            border_style=summary_color,
        )
    )

    logger.info("Workflow completed successfully!")


if __name__ == "__main__":
    asyncio.run(run_full_pipeline())
