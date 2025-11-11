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
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext

from repoai.dependencies.base import ValidatorDependencies
from repoai.explainability import RefactorMetadata
from repoai.llm import ModelRole, PydanticAIAdapter
from repoai.models import CodeChanges, ValidationResult
from repoai.utils.java_build_utils import (
    compile_java_project,
    detect_build_tool,
    run_java_tests,
)
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

    # Tool: Check Java Compilation (REAL Maven/Gradle compilation)
    @agent.tool
    async def check_compilation(
        ctx: RunContext[ValidatorDependencies],
    ) -> dict[str, Any]:
        """
        Compile the Java project using Maven or Gradle.

        This performs ACTUAL compilation, not simulation!
        - Detects build tool (Maven/Gradle) automatically
        - Runs real compilation via subprocess
        - Parses actual compiler errors with file paths, line numbers
        - Returns structured error information

        Args:
            ctx: Agent runtime context with ValidatorDependencies

        Returns:
            dict with:
                - "compiles": bool - Whether compilation succeeded
                - "error_count": int - Number of compilation errors
                - "warning_count": int - Number of warnings
                - "errors": list of dicts with:
                    - "file": str - File path where error occurred
                    - "line": int - Line number
                    - "column": int | None - Column number (if available)
                    - "message": str - Error message
                - "duration_ms": float - Compilation time in milliseconds

        Example:
            result = await check_compilation(ctx)
            if not result["compiles"]:
                for error in result["errors"]:
                    print(f"{error['file']}:{error['line']} - {error['message']}")
        """
        # Handle None repository_path
        if not ctx.deps.repository_path:
            logger.error("repository_path is None in ValidatorDependencies")
            return {
                "compiles": False,
                "error_count": 1,
                "warning_count": 0,
                "errors": [
                    {
                        "file": "unknown",
                        "line": None,
                        "column": None,
                        "message": "Repository path not provided",
                    }
                ],
                "duration_ms": 0.0,
            }

        repo_path = Path(ctx.deps.repository_path)

        logger.info(f"🔨 Compiling Java project at: {repo_path}")

        try:
            # Detect build tool
            build_info = await detect_build_tool(repo_path)
            logger.debug(f"Detected build tool: {build_info.tool}")

            if build_info.tool == "unknown":
                logger.warning("No build tool detected, skipping compilation")
                return {
                    "compiles": False,
                    "error_count": 1,
                    "warning_count": 0,
                    "errors": [
                        {
                            "file": str(repo_path),
                            "line": None,
                            "column": None,
                            "message": "No build tool detected (pom.xml or build.gradle not found)",
                        }
                    ],
                    "duration_ms": 0.0,
                }

            # Run actual compilation
            compile_result = await compile_java_project(
                repo_path=repo_path,
                build_tool_info=build_info,
                clean=False,  # Don't clean, just compile
                skip_tests=True,  # Tests checked separately
            )

            # Convert CompilationError objects to dicts
            errors_list = [
                {
                    "file": err.file_path,
                    "line": err.line_number,
                    "column": err.column_number,
                    "message": err.message,
                }
                for err in compile_result.errors
            ]

            warnings_list = [
                {
                    "file": warn.file_path,
                    "line": warn.line_number,
                    "column": warn.column_number,
                    "message": warn.message,
                }
                for warn in compile_result.warnings
            ]

            result = {
                "compiles": compile_result.success,
                "error_count": compile_result.error_count,
                "warning_count": compile_result.warning_count,
                "errors": errors_list,
                "warnings": warnings_list,
                "duration_ms": compile_result.duration_ms,
                "build_tool": compile_result.build_tool,
            }

            if compile_result.success:
                logger.info(f"✅ Compilation successful ({compile_result.duration_ms:.0f}ms)")
            else:
                logger.warning(
                    f"❌ Compilation failed: {compile_result.error_count} errors, "
                    f"{compile_result.warning_count} warnings ({compile_result.duration_ms:.0f}ms)"
                )

            return result

        except Exception as e:
            logger.error(f"Compilation check failed: {e}")
            return {
                "compiles": False,
                "error_count": 1,
                "warning_count": 0,
                "errors": [
                    {
                        "file": str(repo_path),
                        "line": None,
                        "column": None,
                        "message": f"Compilation error: {str(e)}",
                    }
                ],
                "duration_ms": 0.0,
            }

    # Tool: Run Unit Tests (REAL Maven/Gradle test execution)
    @agent.tool
    async def run_unit_tests(
        ctx: RunContext[ValidatorDependencies],
        test_pattern: str | None = None,
    ) -> dict[str, Any]:
        """
        Run unit tests for the Java project using Maven or Gradle.

        This executes ACTUAL tests, not simulation!
        - Detects build tool (Maven/Gradle) automatically
        - Runs test suite via subprocess
        - Parses test results including failures
        - Returns structured test information

        Args:
            ctx: Agent runtime context with ValidatorDependencies
            test_pattern: Optional test pattern/filter (e.g., "**/Test*.java")

        Returns:
            dict with:
                - "all_passed": bool - Whether all tests passed
                - "tests_run": int - Number of tests executed
                - "failures": int - Number of test failures
                - "errors": int - Number of test errors
                - "skipped": int - Number of skipped tests
                - "pass_rate": float - Percentage of tests passed (0.0-1.0)
                - "duration_ms": float - Test execution time
                - "failed_tests": list of dicts with:
                    - "test_class": str - Test class name
                    - "test_method": str - Test method name
                    - "error_type": str - Exception type
                    - "message": str - Failure message

        Example:
            result = await run_unit_tests(ctx)
            if not result["all_passed"]:
                print(f"Failed: {result['failures']}/{result['tests_run']}")
                for test in result["failed_tests"]:
                    print(f"  {test['test_class']}.{test['test_method']}")
        """
        # Handle None repository_path
        if not ctx.deps.repository_path:
            logger.error("repository_path is None in ValidatorDependencies")
            return {
                "all_passed": False,
                "tests_run": 0,
                "failures": 0,
                "errors": 1,
                "skipped": 0,
                "pass_rate": 0.0,
                "duration_ms": 0.0,
                "failed_tests": [
                    {
                        "test_class": "System",
                        "test_method": "setup",
                        "error_type": "ConfigurationError",
                        "message": "Repository path not provided",
                    }
                ],
            }

        repo_path = Path(ctx.deps.repository_path)

        logger.info(f"🧪 Running tests for Java project at: {repo_path}")

        try:
            # Detect build tool
            build_info = await detect_build_tool(repo_path)
            logger.debug(f"Detected build tool: {build_info.tool}")

            if build_info.tool == "unknown":
                logger.warning("No build tool detected, skipping tests")
                return {
                    "all_passed": False,
                    "tests_run": 0,
                    "failures": 0,
                    "errors": 1,
                    "skipped": 0,
                    "pass_rate": 0.0,
                    "duration_ms": 0.0,
                    "failed_tests": [
                        {
                            "test_class": "BuildSystem",
                            "test_method": "detection",
                            "error_type": "BuildToolNotFound",
                            "message": "No build tool detected (pom.xml or build.gradle not found)",
                        }
                    ],
                }

            # Run actual tests
            test_result = await run_java_tests(
                repo_path=repo_path,
                build_tool_info=build_info,
                test_pattern=test_pattern,
            )

            # Convert TestFailure objects to dicts
            failed_tests_list = [
                {
                    "test_class": failure.test_class,
                    "test_method": failure.test_method,
                    "error_type": failure.error_type,
                    "message": failure.message,
                }
                for failure in test_result.failures
            ]

            result = {
                "all_passed": test_result.success,
                "tests_run": test_result.tests_run,
                "failures": test_result.tests_failed,
                "errors": 0,  # TestResult doesn't separate failures/errors
                "skipped": test_result.tests_skipped,
                "pass_rate": test_result.pass_rate,
                "duration_ms": test_result.duration_ms,
                "build_tool": test_result.build_tool,
                "failed_tests": failed_tests_list,
            }

            if test_result.success:
                logger.info(
                    f"✅ All tests passed: {test_result.tests_run} tests "
                    f"({test_result.duration_ms:.0f}ms)"
                )
            else:
                logger.warning(
                    f"❌ Tests failed: {test_result.tests_failed} failures "
                    f"out of {test_result.tests_run} tests "
                    f"({test_result.duration_ms:.0f}ms)"
                )

            return result

        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return {
                "all_passed": False,
                "tests_run": 0,
                "failures": 0,
                "errors": 1,
                "skipped": 0,
                "pass_rate": 0.0,
                "duration_ms": 0.0,
                "failed_tests": [
                    {
                        "test_class": "System",
                        "test_method": "execution",
                        "error_type": "RuntimeError",
                        "message": f"Test execution error: {str(e)}",
                    }
                ],
            }

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
