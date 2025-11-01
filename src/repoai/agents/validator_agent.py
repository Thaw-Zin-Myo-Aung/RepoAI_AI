"""
Validator Agent implementation.

The Validator Agent is the fourth agent in the pipeline.
It carries out the following tasks:
1. Receives CodeChanges from the Transformer Agent.
2. Validates Java code compilation.
3. Runs static analysis (Checkstyle, PMD, SpotBugs).
4. Executes unit tests (JUnit).
5. Measures code coverage.
6. Checks for security vulnerabilities.
7. Produces ValidationResult with confidence metrics.

This agent uses models optimized for code analysis and validation.
"""

from __future__ import annotations

import time
from datetime import datetime

from pydantic_ai import Agent, RunContext

from repoai.dependencies.base import ValidatorDependencies
from repoai.explainability import RefactorMetadata
from repoai.llm import ModelRole, PydanticAIAdapter
from repoai.models import CodeChanges, ValidationResult
from repoai.utils.logger import get_logger

from .prompts import (
    VALIDATOR_INSTRUCTIONS,
    VALIDATOR_JAVA_EXAMPLES,
    VALIDATOR_SYSTEM_PROMPT,
)

logger = get_logger(__name__)


def create_validator_agent(
    adapter: PydanticAIAdapter,
) -> Agent[ValidatorDependencies, ValidationResult]:
    """
    Create and configure the Validator Agent.

    The Validator Agent validates code changes and runs quality checks.

    Args:
        adapter: PydanticAIAdapter to provide models and configurations.

    Returns:
        Configured Validator Agent instance.

    Example:
        adapter = PydanticAIAdapter()
        validator_agent = create_validator_agent(adapter)

        result = await validator_agent.run(
            validation_prompt,
            deps=dependencies
        )

        validation_result = result.output
    """
    # Get the model settings for Coder Role (Validation uses same role)
    model = adapter.get_model(role=ModelRole.CODER)
    settings = adapter.get_model_settings(role=ModelRole.CODER)
    spec = adapter.get_spec(role=ModelRole.CODER)

    logger.info(f"Creating Validator Agent with model: {spec.model_id}")

    # Build complete system prompt
    complete_system_prompt = f"""{VALIDATOR_SYSTEM_PROMPT}

{VALIDATOR_INSTRUCTIONS}

{VALIDATOR_JAVA_EXAMPLES}

**Your Task:**
Analyze the code changes and validate them against Java best practices,
Spring Framework conventions, and quality standards.
Identify potential issues, risks, and provide recommendations.
"""

    # Create the Agent with ValidatioRnResult output type
    agent: Agent[ValidatorDependencies, ValidationResult] = Agent(
        model=model,
        deps_type=ValidatorDependencies,
        output_type=ValidationResult,
        system_prompt=complete_system_prompt,
        model_settings=settings,
    )

    # Tool: Check Java Compilation
    @agent.tool
    def check_compilation(
        ctx: RunContext[ValidatorDependencies],
        code: str,
    ) -> dict[str, bool | list[str]]:
        """
        Check if Java code has obvious compilation issues.

        This is a static analysis check, not actual compilation.
        Looks for common issues like:
        - Missing semicolons
        - Unbalanced braces
        - Invalid syntax patterns

        Args:
            code: Java source code

        Returns:
            dict: {"compiles": bool, "errors": list[str]}

        Example:
            result = check_compilation(java_code)
        if not result["compiles"]:
            print(result["errors"])
        """
        errors = []

        # Check for balanced braces
        open_braces = code.count("{")
        close_braces = code.count("}")
        if open_braces != close_braces:
            errors.append(f"Unbalanced braces: {open_braces} open, {close_braces} close")

        # Check for balanced parentheses
        open_parens = code.count("(")
        close_parens = code.count(")")
        if open_parens != close_parens:
            errors.append(f"Unbalanced parentheses: {open_parens} open, {close_parens} close")

        # Check for package declaration
        if "class " in code and "package " not in code:
            errors.append("Missing package declaration")

        # Check for common syntax issues
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Skip comments and empty lines
            if stripped.startswith("//") or stripped.startswith("/*") or not stripped:
                continue

            # Check for statements that should end with semicolon
            if any(keyword in stripped for keyword in ["return ", "throw ", "break", "continue"]):
                if (
                    not stripped.endswith(";")
                    and not stripped.endswith("{")
                    and not stripped.endswith("}")
                ):
                    errors.append(f"Line {i}: Statement may be missing semicolon")

        compiles = len(errors) == 0
        logger.debug(f"Compilation check: {'PASS' if compiles else 'FAIL'}, {len(errors)} errors")

        return {"compiles": compiles, "errors": errors}

    # Tool: Check code quality
    @agent.tool
    def check_code_quality(
        ctx: RunContext[ValidatorDependencies],
        code: str,
    ) -> dict[str, float | list[str]]:
        """
        Perform static code quality analysis.

        Checks for:
        - Method length (should be < 50 lines)
        - Cyclomatic complexity (simple heuristic)
        - Code duplication indicators
        - Naming conventions
        - Magic numbers

        Args:
            code: Java source code

        Returns:
            dict: {"score": float (0-10), "issues": list[str]}

        Example:
            result = check_code_quality(java_code)
            print(f"Quality score: {result['score']}/10")
        """
        issues = []
        score = 10.0

        lines = code.split("\n")

        # Check method length
        in_method = False
        method_line_count = 0
        method_start = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Detect method start
            if (
                ("public " in line or "private " in line or "protected " in line)
                and "(" in line
                and "{" in line
            ):
                in_method = True
                method_start = i
                method_line_count = 0

            if in_method:
                method_line_count += 1

                # Detect method end
                if stripped == "}":
                    if method_line_count > 50:
                        issues.append(
                            f"Method starting at line {method_start} is too long ({method_line_count} lines)"
                        )
                        score -= 0.5
                    in_method = False

        # Check for magic numbers
        for i, line in enumerate(lines, 1):
            # Look for numeric literals (excluding common ones like 0, 1, -1)
            import re

            numbers = re.findall(r"\b(\d+)\b", line)
            for num in numbers:
                if num not in ["0", "1", "2", "10", "100", "1000"] and not line.strip().startswith(
                    "//"
                ):
                    issues.append(f"Line {i}: Magic number {num} should be a constant")
                    score -= 0.2
                    break  # Only report once per line

        # Check naming conventions
        for i, line in enumerate(lines, 1):
            # Check class names (should be PascalCase)
            if "class " in line:
                import re

                match = re.search(r"class\s+([A-Za-z_][A-Za-z0-9_]*)", line)
                if match:
                    class_name = match.group(1)
                    if not class_name[0].isupper():
                        issues.append(
                            f"Line {i}: Class name '{class_name}' should start with uppercase"
                        )
                        score -= 0.5

            # Check method names (should be camelCase)
            if ("public " in line or "private " in line) and "(" in line:
                import re

                match = re.search(
                    r"(public|private|protected)\s+\w+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", line
                )
                if match:
                    method_name = match.group(2)
                    if method_name[0].isupper():
                        issues.append(
                            f"Line {i}: Method name '{method_name}' should start with lowercase"
                        )
                        score -= 0.3

        # Cap score at 0
        score = max(0.0, score)

        logger.debug(f"Code quality check: score={score:.1f}/10, {len(issues)} issues")
        return {"score": score, "issues": issues}

    # Tool: Check for spring Framework conventions
    @agent.tool
    def check_spring_conventions(
        ctx: RunContext[ValidatorDependencies],
        code: str,
    ) -> dict[str, bool | list[str]]:
        """
        Check Spring Framework best practices.

        Validates:
        - Proper use of annotations (@Service, @RestController, etc.)
        - Constructor injection (preferred over field injection)
        - @Autowired usage
        - REST endpoint naming
        - Transaction management

        Args:
            code: Java source code

        Returns:
            dict: {"follows_conventions": bool, "violations": list[str]}

        Example:
            result = check_spring_conventions(spring_code)
        """
        violations = []

        # Check for field injection (discouraged)
        if "@Autowired" in code:
            lines = code.split("\n")
            for i, line in enumerate(lines, 1):
                if "@Autowired" in line:
                    # Check if next line is a field (not a constructor)
                    if i < len(lines):
                        next_line = lines[i].strip()
                        if "private " in next_line and "(" not in next_line:
                            violations.append(
                                f"Line {i}: Use constructor injection instead of @Autowired field injection"
                            )

        # Check for @Service without interface
        if "@Service" in code and "implements " not in code:
            violations.append("@Service class should implement an interface for better testability")

        # Check REST controller conventions
        if "@RestController" in code:
            # Check for @RequestMapping at class level
            if (
                "@RequestMapping" not in code
                and "@GetMapping" not in code
                and "@PostMapping" not in code
            ):
                violations.append(
                    "@RestController should have @RequestMapping or mapping annotations"
                )

        # Check for transaction boundaries
        if "@Transactional" in code:
            # Check if on service layer
            if "@Service" not in code and "@Repository" not in code:
                violations.append(
                    "@Transactional should typically be on service or repository classes"
                )

        follows_conventions = len(violations) == 0
        logger.debug(f"Spring conventions check: {len(violations)} violations")

        return {"follows_conventions": follows_conventions, "violations": violations}

    # Tool: Estimate Test Coverage
    @agent.tool
    def estimate_test_coverage(
        ctx: RunContext[ValidatorDependencies],
        production_code: str,
        test_code: str = "",
    ) -> dict[str, float | int]:
        """
        Estimate test coverage based on production and test code.

        This is a heuristic estimate, not actual coverage measurement.
        Compares number of public methods vs test methods.

        Args:
            production_code: Main Java source code
            test_code: JUnit test code (if available)

        Returns:
            dict: {"coverage": float, "public_methods": int, "test_methods": int}

        Example:
            result = estimate_test_coverage(service_code, test_code)
            print(f"Estimated coverage: {result['coverage'] * 100}%")
        """
        # Count public methods in production code
        public_methods = 0
        for line in production_code.split("\n"):
            if "public " in line and "(" in line and "class " not in line:
                public_methods += 1

        # Count test methods
        test_methods = 0
        if test_code:
            for line in test_code.split("\n"):
                if "@Test" in line or "test" in line.lower() and "void " in line:
                    test_methods += 1

        # Estimate coverage (rough heuristic)
        if public_methods == 0:
            coverage = 0.0
        else:
            coverage = min(1.0, test_methods / public_methods)

        logger.debug(
            f"Coverage estimate: {coverage*100:.1f}% "
            f"({test_methods} tests for {public_methods} public methods)"
        )

        return {
            "coverage": coverage,
            "public_methods": public_methods,
            "test_methods": test_methods,
        }

    # Tool: Check for security issues
    @agent.tool
    def check_security_issues(
        ctx: RunContext[ValidatorDependencies],
        code: str,
    ) -> dict[str, list[str]]:
        """
        Check for common security vulnerabilities.

        Looks for:
        - SQL injection risks
        - Hard-coded credentials
        - Insecure cryptography
        - Missing input validation
        - Exposed sensitive data

        Args:
            code: Java source code

        Returns:
            dict: {"vulnerabilities": list[str]}

        Example:
            result = check_security_issues(code)
            if result["vulnerabilities"]:
                print("Security issues found!")
        """
        vulnerabilities = []

        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Check for SQL injection risks
            if "Statement" in line and "execute" in line.lower():
                if "?" not in line:  # No prepared statement
                    vulnerabilities.append(
                        f"Line {i}: Potential SQL injection risk - use PreparedStatement"
                    )

            # Check for hard-coded credentials
            if any(
                keyword in stripped.lower() for keyword in ["password", "secret", "apikey", "token"]
            ):
                if "=" in stripped and ('"' in stripped or "'" in stripped):
                    vulnerabilities.append(f"Line {i}: Possible hard-coded credential")

            # Check for weak crypto
            if "MD5" in line or "SHA1" in line:
                vulnerabilities.append(f"Line {i}: Weak cryptographic algorithm (MD5/SHA1)")

            # Check for missing input validation
            if "@RequestParam" in line or "@PathVariable" in line:
                # Look for validation annotations
                if "@Valid" not in line and "@NotNull" not in line and "@Size" not in line:
                    vulnerabilities.append(f"Line {i}: Input parameter lacks validation annotation")

        logger.debug(f"Security check: {len(vulnerabilities)} potential vulnerabilities")
        return {"vulnerabilities": vulnerabilities}

    logger.info("Validator Agent created successfully.")
    return agent


async def run_validator_agent(
    code_changes: CodeChanges,
    dependencies: ValidatorDependencies,
    adapter: PydanticAIAdapter | None = None,
) -> tuple[ValidationResult, RefactorMetadata]:
    """
    Run the Validator Agent on code changes.

    Convenience function that validates code and produces ValidationResult.

    Args:
        code_changes: CodeChanges from Transformer Agent
        dependencies: Validator Agent dependencies
        adapter: Optional PydanticAIAdapter (creates new one if not provided)

    Returns:
        tuple: (ValidationResult, RefactorMetadata)

    Example:
        deps = ValidatorDependencies(code_changes=code_changes)
        validation_result, metadata = await run_validator_agent(code_changes, deps)

        if validation_result.passed:
            print("✅ All validations passed!")
        else:
            print(f"❌ Failed checks: {validation_result.failed_checks}")
    """
    if adapter is None:
        adapter = PydanticAIAdapter()

    # Create the Validator Agent
    validator_agent = create_validator_agent(adapter)

    logger.info(f"Running Validator Agent for plan: {code_changes.plan_id}")
    logger.debug(f"Validating {len(code_changes.changes)} code changes")

    # Track timing
    start_time = time.time()

    # Prepare validation prompt
    prompt = f"""Validate the following code changes:

Plan ID: {code_changes.plan_id}
Total Changes: {len(code_changes.changes)}
Files Created: {code_changes.files_created}
Files Modified: {code_changes.files_modified}
Lines Added: {code_changes.lines_added}
Lines Removed: {code_changes.lines_removed}

Code Changes Summary:
"""

    for change in code_changes.changes[:5]:  # Show first 5 for context
        prompt += f"""
- File: {change.file_path}
  Type: {change.change_type}
  Class: {change.class_name or 'N/A'}
  Changes: +{change.lines_added}, -{change.lines_removed}
"""

    prompt += """

Please validate these changes by checking:
1. Java compilation (syntax, braces, semicolons)
2. Code quality (method length, naming conventions, magic numbers)
3. Spring Framework conventions
4. Test coverage estimates
5. Security vulnerabilities

Provide a comprehensive ValidationResult with all checks and confidence metrics.
"""

    # Run the agent
    result = await validator_agent.run(prompt, deps=dependencies)

    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000

    # Extract ValidationResult
    validation_result: ValidationResult = result.output

    # Get model used
    model_used = adapter.get_spec(role=ModelRole.CODER).model_id

    # Create Metadata
    metadata = RefactorMetadata(
        timestamp=datetime.now(),
        agent_name="ValidatorAgent",
        model_used=model_used,
        confidence_score=validation_result.confidence.overall_confidence,
        reasoning_chain=[
            f"Validated {len(code_changes.changes)} code changes",
            f"Compilation check: {'PASS' if validation_result.compilation_passed else 'FAIL'}",
            f"Total checks: {len(validation_result.checks)}",
            f"Failed checks: {len(validation_result.failed_checks)}",
            f"Confidence: {validation_result.confidence.overall_confidence:.2f}",
        ],
        data_sources=["code_changes", "static_analysis", "quality_checks"],
        execution_time_ms=duration_ms,
    )

    # Attach metadata to validation result
    validation_result.metadata = metadata

    logger.info(
        f"Validator Agent completed: "
        f"passed={validation_result.passed}, "
        f"checks={len(validation_result.checks)}, "
        f"confidence={validation_result.confidence.overall_confidence:.2f}, "
        f"duration={duration_ms:.0f}ms"
    )

    return validation_result, metadata
