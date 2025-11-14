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
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Any

from pydantic_ai import Agent, RunContext

from repoai.dependencies.base import TransformerDependencies
from repoai.explainability import RefactorMetadata
from repoai.llm import ModelRole, PydanticAIAdapter
from repoai.models import CodeChange, CodeChanges, RefactorPlan
from repoai.parsers.java_ast_parser import extract_relevant_context, parse_java_file
from repoai.utils.file_writer import write_code_changes_to_disk
from repoai.utils.logger import get_logger

from .prompts import (
    TRANSFORMER_INSTRUCTIONS,
    TRANSFORMER_JAVA_EXAMPLES,
    TRANSFORMER_SYSTEM_PROMPT,
    build_transformer_prompt_streaming,
)

logger = get_logger(__name__)


def create_transformer_agent(
    adapter: PydanticAIAdapter,
) -> Agent[TransformerDependencies, CodeChanges]:
    """
    Create and configure the Transformer Agent.

    The Transformer Agent generates actual Java code from RefactorPlan steps.

    Args:
        adapter: PydanticAIAdapter to provide models and configurations.

    Returns:
        Configured Transformer Agent instance (outputs CodeChanges for streaming).

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

    # Create the agent with CodeChanges output type (for streaming multiple files)
    agent: Agent[TransformerDependencies, CodeChanges] = Agent(
        model=model,
        deps_type=TransformerDependencies,
        output_type=CodeChanges,
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

    # Tool: Add Maven dependency to pom.xml
    @agent.tool
    def add_maven_dependency(
        ctx: RunContext[TransformerDependencies], dependency_key: str
    ) -> dict[str, Any]:
        """
        Add a Maven dependency to pom.xml when using external libraries or frameworks.

        CRITICAL: Use this tool WHENEVER you add imports or annotations from external libraries!

        Args:
            dependency_key: Either a common dependency name OR "groupId:artifactId:version"

        Common Dependencies (use these names):
            - "spring-context" - For @Service, @Component, @Autowired
            - "spring-boot-starter-web" - For Spring Boot web (@RestController, etc.)
            - "spring-boot-starter-data-jpa" - For JPA (@Entity, @Repository)
            - "spring-boot-starter-security" - For Spring Security
            - "spring-boot-starter-test" - For Spring Boot testing
            - "junit-jupiter" - For JUnit 5 (@Test, assertions)
            - "mockito-core" - For Mockito (@Mock, @InjectMocks)
            - "lombok" - For Lombok (@Data, @Getter, @Setter)
            - "slf4j-api" - For SLF4J logging
            - "logback-classic" - For Logback

        Custom Format: "groupId:artifactId:version"
            Example: "com.google.guava:guava:32.1.3-jre"

        Returns:
            Dict with success status and dependency details

        Examples:
            # Adding Spring annotation support
            add_maven_dependency("spring-context")

            # Adding Spring Boot web
            add_maven_dependency("spring-boot-starter-web")

            # Adding custom dependency
            add_maven_dependency("com.fasterxml.jackson.core:jackson-databind:2.15.0")
        """
        from pathlib import Path

        from repoai.utils.maven_utils import (
            add_dependency,
            get_common_dependencies,
        )

        repo_path = ctx.deps.repository_path
        if not repo_path:
            logger.warning("Repository path not set, cannot add Maven dependency")
            return {
                "success": False,
                "error": "Repository path not configured",
            }

        pom_path = Path(repo_path) / "pom.xml"
        if not pom_path.exists():
            logger.warning(f"pom.xml not found at {pom_path}")
            return {
                "success": False,
                "error": f"pom.xml not found at {pom_path}",
            }

        # Check if it's a common dependency
        common_deps = get_common_dependencies()
        if dependency_key in common_deps:
            dep = common_deps[dependency_key]
            logger.info(
                f"Adding common dependency: {dep['groupId']}:{dep['artifactId']}:{dep['version']}"
            )

            success = add_dependency(
                pom_path,
                dep["groupId"],
                dep["artifactId"],
                dep["version"],
                dep.get("scope"),
            )

            return {
                "success": success,
                "groupId": dep["groupId"],
                "artifactId": dep["artifactId"],
                "version": dep["version"],
                "message": f"Added {dep['groupId']}:{dep['artifactId']}:{dep['version']}",
            }

        # Parse custom format: groupId:artifactId:version
        try:
            parts = dependency_key.split(":")
            if len(parts) != 3:
                return {
                    "success": False,
                    "error": "Invalid format. Use 'dependency-name' or 'groupId:artifactId:version'",
                }

            group_id, artifact_id, version = parts
            logger.info(f"Adding custom dependency: {group_id}:{artifact_id}:{version}")

            success = add_dependency(pom_path, group_id, artifact_id, version)

            return {
                "success": success,
                "groupId": group_id,
                "artifactId": artifact_id,
                "version": version,
                "message": f"Added {group_id}:{artifact_id}:{version}",
            }

        except Exception as e:
            logger.error(f"Failed to add dependency: {e}")
            return {"success": False, "error": str(e)}

    @agent.tool
    def analyze_java_class(
        ctx: RunContext[TransformerDependencies], file_path: str
    ) -> dict[str, list[str] | str | bool | None]:
        """
        Analyze an existing Java class to understand its structure before modifying it.

        CRITICAL: ALWAYS call this tool BEFORE modifying any existing Java file!
        This ensures you understand what methods, fields, and interfaces already exist.

        Args:
            file_path: Relative path to the Java file (e.g., "src/main/java/com/example/UserService.java")

        Returns:
            Dict containing:
            - class_name: The name of the class
            - package: The package declaration
            - methods: List of method signatures (e.g., ["registerUser(String name, String email)", "getAllUsers()"])
            - fields: List of field declarations (e.g., ["private List<User> users", "public int maxUsers"])
            - interfaces: List of implemented interfaces
            - parent_class: The parent class if any (or None)
            - is_interface: True if this is an interface, False if it's a class

        Example:
            info = analyze_java_class("src/main/java/com/example/app/UserService.java")
            # Returns: {
            #   "class_name": "UserService",
            #   "package": "com.example.app",
            #   "methods": ["registerUser(String name, String email)", "getAllUsers()"],
            #   "fields": ["public List<User> users", "private int maxUsers"],
            #   "interfaces": [],
            #   "parent_class": None,
            #   "is_interface": False
            # }
        """
        import os

        repo_path = ctx.deps.repository_path
        if not repo_path:
            logger.warning("Repository path not set, cannot analyze Java class")
            return {
                "error": "Repository path not configured",
                "class_name": None,
                "package": None,
                "methods": [],
                "fields": [],
                "interfaces": [],
                "parent_class": None,
                "is_interface": False,
            }

        full_path = os.path.join(repo_path, file_path)
        if not os.path.exists(full_path):
            logger.warning(f"Java file not found: {full_path}")
            return {
                "error": f"File not found: {file_path}",
                "class_name": None,
                "package": None,
                "methods": [],
                "fields": [],
                "interfaces": [],
                "parent_class": None,
                "is_interface": False,
            }

        try:
            with open(full_path, encoding="utf-8") as f:
                code = f.read()

            # Parse the Java file
            parsed = parse_java_file(code)

            if not parsed:
                return {
                    "error": "Failed to parse Java file",
                    "class_name": None,
                    "package": None,
                    "methods": [],
                    "fields": [],
                    "interfaces": [],
                    "parent_class": None,
                    "is_interface": False,
                }

            # Extract method signatures with full parameter info
            methods = []
            for method in parsed.methods:
                params = ", ".join(
                    [f"{param_type} {param_name}" for param_type, param_name in method.parameters]
                )
                signature = f"{method.name}({params})"
                methods.append(signature)

            # Extract field declarations with visibility
            fields = []
            for field in parsed.fields:
                if field.is_public:
                    visibility = "public"
                elif field.is_private:
                    visibility = "private"
                else:
                    visibility = "package-private"  # default/package visibility
                fields.append(f"{visibility} {field.type} {field.name}")

            logger.info(f"Analyzed {file_path}: {len(methods)} methods, {len(fields)} fields")

            return {
                "class_name": parsed.name,
                "package": parsed.package,
                "methods": methods,
                "fields": fields,
                "interfaces": parsed.implements,
                "parent_class": parsed.extends,
                "is_interface": parsed.is_interface,
            }

        except Exception as e:
            logger.error(f"Failed to analyze Java class {file_path}: {e}")
            return {
                "error": str(e),
                "class_name": None,
                "package": None,
                "methods": [],
                "fields": [],
                "interfaces": [],
                "parent_class": None,
                "is_interface": False,
            }

    @agent.tool
    def find_test_files_for_class(
        ctx: RunContext[TransformerDependencies], class_file_path: str
    ) -> list[str]:
        """
        Find test files that correspond to a given main class file.

        CRITICAL: Use this tool when modifying a main class to find its test files!
        This ensures test files are also updated to match refactored code.

        Args:
            class_file_path: Path to the main class (e.g., "src/main/java/com/example/UserService.java")

        Returns:
            List of test file paths that test this class

        Example:
            tests = find_test_files_for_class("src/main/java/com/example/app/UserService.java")
            # Returns: ["src/test/java/com/example/app/UserServiceTest.java"]
        """
        import os

        repo_path = ctx.deps.repository_path
        if not repo_path:
            logger.warning("Repository path not set")
            return []

        # Extract class name from path
        # e.g., "src/main/java/com/example/app/UserService.java" -> "UserService"
        class_name = os.path.basename(class_file_path).replace(".java", "")

        test_files = []

        # Common test file naming patterns
        test_patterns = [
            f"{class_name}Test.java",
            f"{class_name}Tests.java",
            f"Test{class_name}.java",
            f"{class_name}TestCase.java",
        ]

        # Search in common test directories
        test_dirs = [
            "src/test/java",
            "test",
            "tests",
            "src/test",
        ]

        for test_dir in test_dirs:
            test_dir_path = os.path.join(repo_path, test_dir)
            if not os.path.exists(test_dir_path):
                continue

            # Walk through test directory
            for root, _, files in os.walk(test_dir_path):
                for file in files:
                    if any(pattern in file for pattern in test_patterns):
                        # Get relative path from repo root
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, repo_path)
                        test_files.append(rel_path)

        if test_files:
            logger.info(f"Found {len(test_files)} test file(s) for {class_name}")
        else:
            logger.debug(f"No test files found for {class_name}")

        return test_files

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

        # Run the agent for this step with increased usage limits
        # (default is 50 requests, but complex refactorings may need more)
        from pydantic_ai import UsageLimits

        result = await transformer_agent.run(
            prompt, deps=dependencies, usage_limits=UsageLimits(request_limit=200)
        )
        code_changes_result: CodeChanges = result.output

        # Extract all changes from the result
        for code_change in code_changes_result.changes:
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


async def transform_with_streaming(
    plan: RefactorPlan,
    dependencies: TransformerDependencies,
    adapter: PydanticAIAdapter | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> AsyncIterator[tuple[CodeChange, RefactorMetadata]]:
    """
    Stream code changes as they are generated (file-level streaming).

    This function processes a RefactorPlan and yields individual CodeChange objects
    as soon as they are generated by the LLM, enabling real-time progress feedback
    and immediate file application.

    Args:
        plan: The RefactorPlan to execute (from Planner Agent)
        dependencies: TransformerDependencies with repository context
        adapter: Optional PydanticAIAdapter (uses default if None)

    Yields:
        Tuple of (CodeChange, RefactorMetadata) for each generated file change

    Example:
        ```python
        async for code_change, metadata in transform_with_streaming(plan, deps):
            print(f"Generated: {code_change.file_path}")
            await apply_file_change(code_change)  # Apply immediately
            await send_progress(metadata)  # Update UI in real-time
        ```

    Note:
        - Yields file-by-file as LLM generates them (not token-by-token)
        - Metadata is updated progressively with each yield
        - Uses existing stream_json_async() from PydanticAIAdapter
        - Supports fallback models automatically
    """
    from repoai.llm.router import ModelRouter

    # Use provided adapter or create default one
    if adapter is None:
        router = ModelRouter()
        adapter = PydanticAIAdapter(router=router)

    logger.info(
        f"Starting streaming transformation: "
        f"steps={len(plan.steps)}, "
        f"repo={dependencies.repository_url or dependencies.repository_path}"
    )

    # Create the transformer agent with all tools
    transformer_agent = create_transformer_agent(adapter)

    # Initialize metadata tracking
    start_time = time.time()
    metadata = RefactorMetadata(
        timestamp=datetime.now(),
        agent_name="Transformer",
        model_used="",
        confidence_score=1.0,
        reasoning_chain=[],
        data_sources=[],
        execution_time_ms=0.0,
    )

    # Track files seen so far to detect new ones
    files_seen: set[str] = set()
    total_lines_added = 0
    total_lines_removed = 0
    file_count = 0

    # Process each step in the refactoring plan
    for step_idx, step in enumerate(plan.steps, start=1):
        # Track files changed in this specific step
        step_files: list[CodeChange] = []

        # Send "Processing step X/Y" message
        if progress_callback:
            progress_callback(f"⚙️  Processing step {step_idx}/{len(plan.steps)}: {step.action}")

        logger.info(f"Streaming step {step_idx}/{len(plan.steps)}: {step.description}")

        # Build prompt for streaming
        prompt = build_transformer_prompt_streaming(
            step=step,
            dependencies=dependencies,
            estimated_duration=plan.estimated_duration,
        )

        # Use the transformer agent directly to enable tool calling during streaming
        # This allows the LLM to call get_file_context and add_maven_dependency tools
        try:
            async with transformer_agent.run_stream(
                prompt,
                deps=dependencies,
                model_settings={"temperature": 0.3, "max_tokens": 8192},
            ) as stream:
                async for partial_changes in stream.stream_output():
                    # Detect newly added files in the partial response
                    for change in partial_changes.changes:
                        if change.file_path not in files_seen:
                            # New file generated!
                            files_seen.add(change.file_path)
                            file_count += 1

                            # Track this file for step summary (only once per unique file)
                            step_files.append(change)

                            # Calculate metrics for this change
                            lines_added, lines_removed = _calculate_diff_stats(change.diff)

                            # Fallback: if diff is empty but we have content, calculate from content
                            if lines_added == 0 and lines_removed == 0:
                                if change.modified_content and change.original_content:
                                    # Modified file: count actual line differences
                                    lines_added = len(
                                        [
                                            line
                                            for line in change.modified_content.splitlines()
                                            if line.strip()
                                        ]
                                    )
                                    lines_removed = len(
                                        [
                                            line
                                            for line in change.original_content.splitlines()
                                            if line.strip()
                                        ]
                                    )
                                elif change.modified_content and not change.original_content:
                                    # New file: count all lines as added
                                    lines_added = len(
                                        [
                                            line
                                            for line in change.modified_content.splitlines()
                                            if line.strip()
                                        ]
                                    )
                                    lines_removed = 0

                            total_lines_added += lines_added
                            total_lines_removed += lines_removed

                            # Update the CodeChange object with calculated stats
                            change.lines_added = lines_added
                            change.lines_removed = lines_removed

                            # Update metadata with current progress
                            current_time = time.time()
                            metadata.execution_time_ms = (current_time - start_time) * 1000
                            metadata.model_used = "gemini-2.5-flash"  # TODO: Get from adapter
                            metadata.data_sources = [
                                f"step:{step_idx}/{len(plan.steps)}",
                                f"file:{change.file_path}",
                                f"files_total:{file_count}",
                                f"lines_added:{total_lines_added}",
                                f"lines_removed:{total_lines_removed}",
                            ]

                            logger.debug(
                                f"Yielding file {file_count}: {change.file_path} "
                                f"(+{lines_added}/-{lines_removed} lines)"
                            )

                            # Yield immediately for real-time processing (only new files)
                            yield change, metadata

            # Send step completion message with file contents summary
            if progress_callback and step_files:
                # Build summary with file contents
                files_summary = "\n".join(
                    [
                        f"  • {change.file_path} ({change.change_type}): "
                        f"+{change.lines_added}/-{change.lines_removed} lines"
                        for change in step_files
                    ]
                )
                progress_callback(
                    f"✅ Step {step_idx}/{len(plan.steps)} completed: {step.action}\n"
                    f"Files changed ({len(step_files)}):\n{files_summary}"
                )

        except Exception as e:
            error_msg = str(e)

            # Check if it's a context/token related error
            is_context_error = any(
                pattern in error_msg
                for pattern in [
                    "MALFORMED_FUNCTION_CALL",
                    "MAX_TOKENS",
                    "token limit",
                    "context length",
                    "UnexpectedModelBehavior",
                ]
            )

            if is_context_error:
                # Log concisely without dumping the entire error object
                logger.warning(
                    f"Step {step_idx} hit token/context limit (MALFORMED_FUNCTION_CALL). "
                    f"Prompt tokens: Check logs for details."
                )
                if progress_callback:
                    progress_callback(
                        f"⚠️  Step {step_idx} context too large, simplifying and retrying..."
                    )

                # Provide clean error message for users
                error_msg = (
                    f"Token limit exceeded for step {step_idx}. "
                    "The prompt is too large for the model to process. "
                    "Try breaking this step into smaller sub-steps."
                )

                # Send error message
                if progress_callback:
                    progress_callback(f"❌ Step {step_idx} failed: {error_msg}")

                # Update metadata with clean error
                metadata.risk_factors.append(f"error:token_limit_step_{step_idx}")

                # Raise a cleaner exception
                raise RuntimeError(error_msg) from None
            else:
                # For non-context errors, log the actual error
                logger.error(f"Error streaming step {step_idx}: {error_msg}")

                # Send error message
                if progress_callback:
                    progress_callback(f"❌ Step {step_idx} failed: {error_msg}")

                # Update metadata with error
                metadata.risk_factors.append(f"error:{error_msg[:200]}")
                raise

    # Final metadata update
    end_time = time.time()
    metadata.execution_time_ms = (end_time - start_time) * 1000

    logger.info(
        f"Streaming transformation completed: "
        f"files={file_count}, "
        f"lines_added={total_lines_added}, "
        f"lines_removed={total_lines_removed}, "
        f"duration={metadata.execution_time_ms:.0f}ms"
    )


def _calculate_diff_stats(diff: str) -> tuple[int, int]:
    """
    Calculate lines added/removed from a unified diff string.

    Args:
        diff: Unified diff string

    Returns:
        Tuple of (lines_added, lines_removed)
    """
    lines_added = 0
    lines_removed = 0

    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            lines_added += 1
        elif line.startswith("-") and not line.startswith("---"):
            lines_removed += 1

    return lines_added, lines_removed
