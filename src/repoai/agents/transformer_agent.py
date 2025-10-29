"""
Transformer Agent implementation.

The Transformer Agent is the third agent in the pipeline.
It carries out the following tasks:
1. Receives a RefactorPlan from the Planner Agent.
2. Generates actual Java code for each refactoring step.
3. Creates CodeChange objects with diffs.
4. Produces CodeChanges output for the Validator Agent.

This agent uses code-specialized models optimized for code generation.
"""

from __future__ import annotations

import difflib
import time
from datetime import datetime

from pydantic_ai import Agent, RunContext

from repoai.dependencies.base import TransformerDependencies
from repoai.explainability import RefactorMetadata
from repoai.llm import ModelRole, PydanticAIAdapter
from repoai.models import CodeChange, CodeChanges, RefactorPlan
from repoai.parsers.java_ast_parser import extract_relevant_context
from repoai.utils.file_writer import write_code_changes_to_disk
from repoai.utils.logger import get_logger

from .prompts import (
    TRANSFORMER_INSTRUCTIONS,
    TRANSFORMER_JAVA_EXAMPLES,
    TRANSFORMER_SYSTEM_PROMPT,
)

logger = get_logger(__name__)


def create_transformer_agent(
    adapter: PydanticAIAdapter,
) -> Agent[TransformerDependencies, CodeChange]:
    """
    Create and configure the Transformer Agent.

    The Transformer Agent generates actual Java code from RefactorPlan steps.

    Args:
        adapter: PydanticAIAdapter to provide models and configurations.

    Returns:
        Configured Transformer Agent instance.

    Example:
        adapter = PydanticAIAdapter()
        transformer_agent = create_transformer_agent(adapter)

        # Run for a single step
        result = await transformer_agent.run(
            step_description,
            deps=dependencies
        )

        code_change = result.output
    """
    # Get the model and settings for Coder Role
    model = adapter.get_model(role=ModelRole.CODER)
    settings = adapter.get_model_settings(role=ModelRole.CODER)
    spec = adapter.get_spec(role=ModelRole.CODER)

    logger.info(f"Creating Transformer Agent with model: {spec.model_id}")

    # Build complete system prompt
    complete_system_prompt = f"""{TRANSFORMER_SYSTEM_PROMPT}

{TRANSFORMER_INSTRUCTIONS}

{TRANSFORMER_JAVA_EXAMPLES}

**Your Task:**
Generate actual Java code for the given refactoring step.
Produce complete, working code that follows Java and Spring Framework best practices.
Include proper imports, annotations, and documentation.
"""

    # Create the agent with CodeChange output type
    agent: Agent[TransformerDependencies, CodeChange] = Agent(
        model=model,
        deps_type=TransformerDependencies,
        output_type=CodeChange,
        system_prompt=complete_system_prompt,
        model_settings=settings,
    )

    # Tool: Generate Java class template
    @agent.tool
    def generate_class_template(
        ctx: RunContext[TransformerDependencies],
        package_name: str,
        class_name: str,
        class_type: str = "class",
    ) -> str:
        """
        Generate a Java class template with package and basic structure.

        Args:
            package_name: Java package (e.g., "com.example.auth")
            class_name: Simple class name (e.g., "JwtService")
            class_type: "class", "interface", "enum", or "annotation"

        Returns:
            str: Java class template

        Example:
            template = generate_class_template("com.example.auth", "JwtService", "class")
        """
        templates = {
            "class": f"""package {package_name};

/**
 * {class_name}
 * 
 * TODO: Add class description
 */
public class {class_name} {{
    
    // TODO: Add fields, constructors, and methods
    
}}
""",
            "interface": f"""package {package_name};

/**
 * {class_name}
 * 
 * TODO: Add interface description
 */
public interface {class_name} {{
    
    // TODO: Add method signatures
    
}}
""",
            "enum": f"""package {package_name};

/**
 * {class_name}
 * 
 * TODO: Add enum description
 */
public enum {class_name} {{
    
    // TODO: Add enum constants
    
}}
""",
            "annotation": f"""package {package_name};

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * {class_name}
 * 
 * TODO: Add annotation description
 */
@Retention(RetentionPolicy.RUNTIME)
@Target(ElementType.TYPE)
public @interface {class_name} {{
    
    // TODO: Add annotation elements
    
}}
""",
        }

        template = templates.get(class_type.lower(), templates["class"])
        logger.debug(f"Generated {class_type} template for {package_name}.{class_name}")
        return template

    # Tool: Extract imports from code
    @agent.tool
    def extract_imports(ctx: RunContext[TransformerDependencies], code: str) -> list[str]:
        """
        Extract import statements from Java code.

        Args:
            code: Java source code

        Returns:
            list[str]: List of import statements

        Example:
            imports = extract_imports(java_code)
            # Returns: ["import java.util.List;", "import org.springframework.stereotype.Service;"]
        """
        imports = []
        for line in code.split("\n"):
            stripped = line.strip()
            if stripped.startswith("import ") and stripped.endswith(";"):
                imports.append(stripped)

        logger.debug(f"Extracted {len(imports)} imports from code")
        return imports

    # Tool: Extract method signatures
    @agent.tool
    def extract_method_signatures(ctx: RunContext[TransformerDependencies], code: str) -> list[str]:
        """
        Extract method signatures from Java code.

        Args:
            code: Java source code

        Returns:
            list[str]: List of method signatures

        Example:
            methods = extract_method_signatures(java_code)
            # Returns: ["public String generateToken(User user)", "public boolean validateToken(String token)"]
        """
        signatures = []
        lines = code.split("\n")

        for i, line in enumerate(lines):
            stripped = line.strip()
            # Simple heuristic: line with "public/private/protected" and "(" but not ending with ";"
            if (
                ("public " in stripped or "private " in stripped or "protected " in stripped)
                and "(" in stripped
                and not stripped.endswith(";")
                and "{"
                in (stripped if "{" in stripped else lines[i + 1] if i + 1 < len(lines) else "")
            ):
                # Extract signature (remove { and everything after)
                sig = stripped.split("{")[0].strip()
                signatures.append(sig)

        logger.debug(f"Extracted {len(signatures)} method signatures")
        return signatures

    # Tool: Extract annotations
    @agent.tool
    def extract_annotations(ctx: RunContext[TransformerDependencies], code: str) -> list[str]:
        """
        Extract annotations from Java code.

        Args:
            code: Java source code

        Returns:
            list[str]: List of annotations

        Example:
            annotations = extract_annotations(java_code)
            # Returns: ["@Service", "@Autowired", "@Override"]
        """
        annotations = []
        for line in code.split("\n"):
            stripped = line.strip()
            if (
                stripped.startswith("@")
                and not stripped.startswith("@param")
                and not stripped.startswith("@return")
            ):
                # Extract just the annotation (before any parameters)
                annotation = stripped.split("(")[0] if "(" in stripped else stripped
                annotations.append(annotation)

        logger.debug(f"Extracted {len(annotations)} annotations")
        return annotations

    # Tool: Generate unified diff
    @agent.tool
    def generate_diff(
        ctx: RunContext[TransformerDependencies],
        original: str | None,
        modified: str,
        file_path: str,
    ) -> str:
        """
        Generate unified diff between original and modified content.

        Args:
            original: Original file content (None for new files)
            modified: Modified file content
            file_path: File path for diff header

        Returns:
            str: Unified diff string

        Example:
            diff = generate_diff(old_code, new_code, "src/main/java/Auth.java")
        """
        if original is None:
            # New file
            original_lines = []
        else:
            original_lines = original.splitlines(keepends=True)

        modified_lines = modified.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )

        diff_text = "\n".join(diff)
        logger.debug(f"Generated diff for {file_path}: {len(diff_text)} bytes")
        return diff_text

    # Tool: Count lines added/removed
    @agent.tool
    def count_diff_lines(ctx: RunContext[TransformerDependencies], diff: str) -> dict[str, int]:
        """
        Count lines added and removed in a diff.

        Args:
            diff: Unified diff string

        Returns:
            dict: {"added": int, "removed": int}

        Example:
            counts = count_diff_lines(diff_text)
            # Returns: {"added": 45, "removed": 12}
        """
        added = 0
        removed = 0

        for line in diff.split("\n"):
            if line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1

        logger.debug(f"Diff line counts: +{added}, -{removed}")
        return {"added": added, "removed": removed}

    # Tool: Extract relevant context from existing file
    @agent.tool
    def get_file_context(ctx: RunContext[TransformerDependencies], file_path: str) -> str:
        """
        Get relevant context from an existing Java file.

        For large files (2000+ lines), uses AST extraction to get only
        relevant methods, fields, and imports based on the refactoring intent.

        Args:
            file_path: Path to the Java file

        Returns:
            str: Relevant file context (full or extracted)

        Example:
            context = get_file_context("src/main/java/.../UserService.java")
            # Returns targeted context for large files
        """
        # Check if we have existing code context
        if ctx.deps.existing_code_context and file_path in ctx.deps.existing_code_context:
            code = ctx.deps.existing_code_context[file_path]

            # For large files, extract only relevant context
            line_count = len(code.split("\n"))
            if line_count > 500:
                logger.info(f"Large file detected ({line_count} lines), using AST extraction")
                intent = (
                    ctx.deps.plan.job_id.split("_")[-1]
                    if hasattr(ctx.deps.plan, "job_id")
                    else "refactor"
                )
                relevant_context = extract_relevant_context(code, intent)
                logger.debug(
                    f"Extracted context: {len(relevant_context)} chars from {len(code)} chars"
                )
                return relevant_context

            return code

        # No existing context
        logger.debug(f"No existing context for {file_path}")
        return f"// File: {file_path}\n// (New file - no existing content)"

    logger.info("Transformer Agent created successfully.")
    return agent


async def run_transformer_agent(
    plan: RefactorPlan,
    dependencies: TransformerDependencies,
    adapter: PydanticAIAdapter | None = None,
) -> tuple[CodeChanges, RefactorMetadata]:
    """
    Run the Transformer Agent for all steps in a RefactorPlan.

    Convenience function that processes all steps and generates code changes.

    Args:
        plan: RefactorPlan from Planner Agent
        dependencies: Transformer Agent dependencies
        adapter: Optional PydanticAIAdapter (creates new one if not provided)

    Returns:
        tuple: (CodeChanges, RefactorMetadata) with all code changes and metadata

    Example:
        from repoai.dependencies.base import TransformerDependencies

        deps = TransformerDependencies(
            plan=plan,
            repository_path="/path/to/repo"
        )

        code_changes, metadata = await run_transformer_agent(plan, deps)

        print(f"Files modified: {code_changes.files_modified}")
        print(f"Classes created: {code_changes.classes_created}")
    """
    if adapter is None:
        adapter = PydanticAIAdapter()

    # Create the Transformer Agent
    transformer_agent = create_transformer_agent(adapter)

    logger.info(f"Running Transformer Agent for plan: {plan.plan_id}")
    logger.debug(f"Total steps to process: {plan.total_steps}")

    # Track timing
    start_time = time.time()

    # Process each step
    all_changes: list[CodeChange] = []

    for step in plan.steps:
        logger.info(f"Processing step {step.step_number}/{plan.total_steps}: {step.action}")

        # Prepare prompt for this step
        prompt = f"""Generate Java code for the following refactoring step:

Step Number: {step.step_number}
Action: {step.action}
Description: {step.description}

Target Files: {', '.join(step.target_files)}
Target Classes: {', '.join(step.target_classes) if step.target_classes else 'N/A'}

Requirements:
- Follow Java coding standards and best practices
- Use proper Spring Framework annotations if applicable
- Include comprehensive JavaDoc comments
- Handle exceptions appropriately
- Write clean, maintainable code

Generate the complete code change including:
1. Full file content (original and modified)
2. List of imports added/removed
3. List of methods added/modified
4. List of annotations used
"""

        # Run the agent for this step
        result = await transformer_agent.run(prompt, deps=dependencies)
        code_change: CodeChange = result.output

        # Ensure change_type is set
        if not code_change.change_type:
            if step.action.startswith("create_"):
                code_change.change_type = "created"
            elif step.action.startswith("delete_"):
                code_change.change_type = "deleted"
            else:
                code_change.change_type = "modified"

        all_changes.append(code_change)
        logger.info(
            f"Step {step.step_number} completed: "
            f"{code_change.change_type} {code_change.file_path} "
            f"(+{code_change.lines_added}, -{code_change.lines_removed})"
        )

    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000

    # Aggregate statistics
    total_lines_added = sum(c.lines_added for c in all_changes)
    total_lines_removed = sum(c.lines_removed for c in all_changes)
    files_created = sum(1 for c in all_changes if c.change_type == "created")
    files_modified = sum(1 for c in all_changes if c.change_type == "modified")
    files_deleted = sum(1 for c in all_changes if c.change_type == "deleted")
    classes_created = sum(1 for c in all_changes if c.change_type == "created" and c.class_name)

    # Get model used
    model_used = adapter.get_spec(role=ModelRole.CODER).model_id

    # Create CodeChanges object
    code_changes = CodeChanges(
        plan_id=plan.plan_id,
        changes=all_changes,
        files_modified=files_modified,
        files_created=files_created,
        files_deleted=files_deleted,
        lines_added=total_lines_added,
        lines_removed=total_lines_removed,
        classes_created=classes_created,
    )

    # Create Metadata
    metadata = RefactorMetadata(
        timestamp=datetime.now(),
        agent_name="TransformerAgent",
        model_used=model_used,
        confidence_score=0.88,  # TODO: Calculate actual confidence
        reasoning_chain=[
            f"Processed {plan.total_steps} refactoring steps",
            f"Generated {len(all_changes)} code changes",
            f"Created {files_created} new files",
            f"Modified {files_modified} existing files",
            f"Total changes: +{total_lines_added}, -{total_lines_removed} lines",
        ],
        data_sources=["refactor_plan", "code_templates", "spring_framework_patterns"],
        execution_time_ms=duration_ms,
    )

    # Attach metadata to code changes
    code_changes.metadata = metadata

    # Write files to disk if requested
    if dependencies.write_to_disk:
        output_dir = write_code_changes_to_disk(
            code_changes, base_path=dependencies.output_path or "/tmp/repoai"
        )
        logger.info(f"Code changes written to disk: {output_dir}")

        # Store output directory in metadata
        metadata.data_sources.append(f"output_dir:{output_dir}")

    logger.info(
        f"Transformer Agent completed: "
        f"files={len(all_changes)}, "
        f"lines_added={total_lines_added}, "
        f"lines_removed={total_lines_removed}, "
        f"duration={duration_ms:.0f}ms"
    )

    return code_changes, metadata
