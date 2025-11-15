"""
Pr Narrator Agent Implementation.

The PR Narrator Agent is the fifth and final agent in the pipeline.
It carries out the following tasks:
1. Receives ValidationResult and CodeChanges from previous agents.
2. Summarizes code changes in human-readable format.
3. Creates comprehensive PR description with markdown.
4. Documents breaking changes and provides migration guides.
5. Produces PRDescription ready for GitHub/GitLab.

This agent uses models optimized for natural language generation.
"""

from __future__ import annotations

import time
from datetime import datetime

from pydantic_ai import Agent, RunContext

from repoai.dependencies import PRNarratorDependencies
from repoai.explainability import RefactorMetadata
from repoai.llm import ModelRole, PydanticAIAdapter
from repoai.models import CodeChanges, PRDescription, ValidationResult
from repoai.utils.logger import get_logger

from .prompts import (
    PR_NARRATOR_INSTRUCTIONS,
    PR_NARRATOR_JAVA_EXAMPLES,
    PR_NARRATOR_SYSTEM_PROMPT,
)

logger = get_logger(__name__)


def create_pr_narrator_agent(
    adapter: PydanticAIAdapter,
) -> Agent[PRNarratorDependencies, PRDescription]:
    """
    Create and configure the PR Narrator Agent.

    The PR Narrator Agent creates human-readable PR descriptions.

    Args:
        adapter: PydanticAIAdapter to provide models and configurations.

    Returns:
        Configured PR Narrator Agent instance.

    Example:
        adapter = PydanticAIAdapter()
        pr_narrator_agent = create_pr_narrator_agent(adapter)

        result = await pr_narrator_agent.run(
            narrative_prompt,
            deps=dependencies
        )

        pr_description = result.output
    """
    # Get the model and settings for PR Narrator Role
    model = adapter.get_model(role=ModelRole.PR_NARRATOR)
    settings = adapter.get_model_settings(role=ModelRole.PR_NARRATOR)
    spec = adapter.get_spec(role=ModelRole.PR_NARRATOR)

    logger.info(f"Creating PR Narrator Agent with model: {spec.model_id}")

    # Build complete system prompt
    complete_system_prompt = f"""{PR_NARRATOR_SYSTEM_PROMPT}

{PR_NARRATOR_INSTRUCTIONS}

{PR_NARRATOR_JAVA_EXAMPLES}

**Your Task:**
Create a comprehensive, clear, and professional PR description that:
- Summarizes the changes for both technical and non-technical readers
- Explains the "why" behind the changes
- Documents any breaking changes
- Provides migration guidance if needed
- Lists testing performed
"""

    # Create the agent with PRDescription output type
    agent: Agent[PRNarratorDependencies, PRDescription] = Agent(
        model=model,
        deps_type=PRNarratorDependencies,
        output_type=PRDescription,
        system_prompt=complete_system_prompt,
        model_settings=settings,
    )

    # Tool: Categorize changes by type
    @agent.tool
    def categorize_changes(
        ctx: RunContext[PRNarratorDependencies],
    ) -> dict[str, list[str]]:
        """
        Categorize code changes by type.

        Returns:
            dict: Changes grouped by category

        Example:
            categories = categorize_changes()
            # Returns: {"features": [...], "refactoring": [...], "tests": [...]}
        """
        categories: dict[str, list[str]] = {
            "features": [],
            "refactoring": [],
            "bug_fixes": [],
            "tests": [],
            "configuration": [],
            "documentation": [],
        }

        for change in ctx.deps.code_changes.changes:
            file_path = change.file_path.lower()
            class_name = (change.class_name or "").lower()

            # Categorize based on patterns
            if "test" in file_path or "test" in class_name:
                categories["tests"].append(change.file_path)
            elif "pom.xml" in file_path or "build.gradle" in file_path:
                categories["configuration"].append(change.file_path)
            elif "readme" in file_path or "doc" in file_path:
                categories["documentation"].append(change.file_path)
            elif change.change_type == "created":
                categories["features"].append(change.file_path)
            elif change.change_type == "modified":
                categories["refactoring"].append(change.file_path)

        logger.debug(f"Categorized changes: {sum(len(v) for v in categories.values())} files")
        return categories

    # Tool: Generate change summary
    @agent.tool
    def summarize_file_changes(
        ctx: RunContext[PRNarratorDependencies],
    ) -> dict[str, str]:
        """
        Generate human-readable summaries for each file change.

        Returns:
            dict: Map of file path to summary

        Example:
            summaries = summarize_file_changes()
            # Returns: {"JwtService.java": "Added JWT token generation and validation"}
        """
        summaries = {}

        for change in ctx.deps.code_changes.changes:
            # Build summary based on change type and content
            if change.change_type == "created":
                summary = f"Created new {change.class_name or 'file'}"

                # Add more detail based on annotations
                if change.annotations_added:
                    annotations = ", ".join(change.annotations_added[:3])
                    summary += f" ({annotations})"

                # Add method count
                if change.methods_added:
                    summary += f" with {len(change.methods_added)} methods"

            elif change.change_type == "modified":
                summary = f"Modified {change.class_name or 'file'}"

                if change.methods_added:
                    summary += f" - added {len(change.methods_added)} methods"
                if change.methods_modified:
                    summary += f", updated {len(change.methods_modified)} methods"

            elif change.change_type == "deleted":
                summary = f"Deleted {change.class_name or change.file_path}"
            else:
                summary = f"Changed {change.file_path}"

            summaries[change.file_path] = summary

        logger.debug(f"Generated summaries for {len(summaries)} files")
        return summaries

    # Tool: Extract breaking changes
    @agent.tool
    def identify_breaking_changes(
        ctx: RunContext[PRNarratorDependencies],
    ) -> list[str]:
        """
        Identify potential breaking changes from code modifications.

        Returns:
            list[str]: List of breaking changes

        Example:
            breaking = identify_breaking_changes()
            # Returns: ["Changed method signature in UserService"]
        """
        breaking_changes = []

        # Check validation result for breaking changes flag
        if ctx.deps.validation_result.has_critical_issues:
            breaking_changes.append("Contains critical issues that must be addressed")

        # Check for method signature changes
        for change in ctx.deps.code_changes.changes:
            if change.methods_modified:
                for method in change.methods_modified:
                    if "public " in method:
                        breaking_changes.append(
                            f"Modified public method: {method} in {change.class_name}"
                        )

        # Check for dependency changes
        if ctx.deps.code_changes.dependencies_removed:
            for dep in ctx.deps.code_changes.dependencies_removed:
                breaking_changes.append(f"Removed dependency: {dep}")

        logger.debug(f"Identified {len(breaking_changes)} potential breaking changes")
        return breaking_changes

    # Tool: Generate testing summary
    @agent.tool
    def summarize_testing(
        ctx: RunContext[PRNarratorDependencies],
    ) -> str:
        """
        Summarize testing performed and results.

        Returns:
            str: Testing summary

        Example:
            summary = summarize_testing()
            # Returns: "All unit tests passing. Coverage: 85%. Static analysis: PASS."
        """
        validation = ctx.deps.validation_result

        parts = []

        # Compilation
        if validation.compilation_passed:
            parts.append("✅ Compilation: PASS")
        else:
            parts.append("❌ Compilation: FAIL")

        # Tests
        test_count = len(
            [c for c in ctx.deps.code_changes.changes if "test" in c.file_path.lower()]
        )
        if test_count > 0:
            parts.append(f"✅ Tests: {test_count} test files")

        # Coverage
        coverage_pct = validation.test_coverage * 100
        if coverage_pct >= 80:
            parts.append(f"✅ Coverage: {coverage_pct:.0f}%")
        elif coverage_pct >= 60:
            parts.append(f"⚠️  Coverage: {coverage_pct:.0f}% (below 80%)")
        else:
            parts.append(f"❌ Coverage: {coverage_pct:.0f}% (below 60%)")

        # Quality checks
        passed_checks = len([c for c in validation.checks if c.result.passed])
        total_checks = len(validation.checks)
        parts.append(f"Quality checks: {passed_checks}/{total_checks} passed")

        # Security
        if validation.security_vulnerabilities:
            parts.append(f"⚠️  Security: {len(validation.security_vulnerabilities)} issues found")
        else:
            parts.append("✅ Security: No vulnerabilities detected")

        summary = "\n".join(f"- {part}" for part in parts)

        logger.debug("Generated testing summary")
        return summary

    logger.info("PR Narrator Agent created successfully.")
    return agent


async def run_pr_narrator_agent(
    code_changes: CodeChanges,
    validation_result: ValidationResult,
    dependencies: PRNarratorDependencies,
    adapter: PydanticAIAdapter | None = None,
) -> tuple[PRDescription, RefactorMetadata]:
    """
    Run the PR Narrator Agent to create a PR description.

    Convenience function that creates PR documentation.

    Args:
        code_changes: CodeChanges from Transformer Agent
        validation_result: ValidationResult from Validator Agent
        dependencies: PR Narrator Agent dependencies
        adapter: Optional PydanticAIAdapter (creates new one if not provided)

    Returns:
        tuple: (PRDescription, RefactorMetadata)

    Example:
        deps = PRNarratorDependencies(
            code_changes=code_changes,
            validation_result=validation_result,
            plan_id="plan_123"
        )

        pr_description, metadata = await run_pr_narrator_agent(
            code_changes, validation_result, deps
        )

        print(pr_description.to_markdown())
    """
    if adapter is None:
        adapter = PydanticAIAdapter()

    # Create the PR Narrator Agent
    pr_narrator_agent = create_pr_narrator_agent(adapter)

    logger.info(f"Running PR Narrator Agent for plan: {code_changes.plan_id}")

    # Track timing
    start_time = time.time()

    # Prepare narrative prompt
    prompt = f"""Create a comprehensive PR description for the following refactoring:

Plan ID: {code_changes.plan_id}

Code Changes Summary:
- Total files changed: {code_changes.total_changes}
- Files created: {code_changes.files_created}
- Files modified: {code_changes.files_modified}
- Files deleted: {code_changes.files_deleted}
- Lines added: {code_changes.lines_added}
- Lines removed: {code_changes.lines_removed}
- Classes created: {code_changes.classes_created}

Validation Results:
- Overall: {'✅ PASSED' if validation_result.passed else '❌ FAILED'}
- Compilation: {'✅ PASSED' if validation_result.compilation_passed else '❌ FAILED'}
- Quality checks: {len([c for c in validation_result.checks if c.result.passed])}/{len(validation_result.checks)} passed
- Test coverage: {validation_result.test_coverage * 100:.0f}%
- Confidence: {validation_result.confidence.overall_confidence:.0%}

Key Files Changed:
"""

    for change in code_changes.changes[:10]:  # Show first 10
        prompt += f"\n- {change.file_path} ({change.change_type})"
        if change.class_name:
            prompt += f" - {change.class_name}"

    prompt += """

Please create a clear, professional PR description that:
1. Summarizes what was changed and why
2. Lists changes by file with descriptions
3. Documents any breaking changes
4. Provides migration guidance if needed
5. Summarizes testing performed
6. Uses proper markdown formatting
"""

    # Run the agent
    result = await pr_narrator_agent.run(prompt, deps=dependencies)

    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000

    # Extract PRDescription
    pr_description: PRDescription = result.output

    # Get model used
    model_used = adapter.get_spec(role=ModelRole.PR_NARRATOR).model_id

    # Create Metadata
    metadata = RefactorMetadata(
        timestamp=datetime.now(),
        agent_name="PRNarratorAgent",
        model_used=model_used,
        confidence_score=0.90,
        reasoning_chain=[
            f"Created PR description for {code_changes.total_changes} file changes",
            f"Documented {len(pr_description.changes_by_file)} files",
            f"Identified {len(pr_description.breaking_changes)} breaking changes",
            f"Generated {len(pr_description.to_markdown().split())} word PR description",
        ],
        data_sources=["code_changes", "validation_result"],
        execution_time_ms=duration_ms,
    )

    # Attach metadata to PR description
    pr_description.metadata = metadata

    logger.info(
        f"PR Narrator Agent completed: "
        f"title_length={len(pr_description.title)}, "
        f"breaking_changes={len(pr_description.breaking_changes)}, "
        f"duration={duration_ms:.0f}ms"
    )

    return pr_description, metadata
