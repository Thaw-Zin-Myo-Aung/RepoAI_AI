"""
Java Build Utilities for Maven and Gradle.

This module provides utilities for:
1. Detecting build tools (Maven/Gradle)
2. Compiling Java projects
3. Running tests (JUnit)
4. Parsing compilation errors and test results
5. Managing build processes

Supports both Maven and Gradle build systems with automatic detection.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from repoai.utils.logger import get_logger

logger = get_logger(__name__)

# Progress callback type for streaming build output
ProgressCallback = Callable[[str], Awaitable[None]]


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class CompilationError:
    """Represents a single compilation error."""

    file_path: str
    line_number: int | None
    column_number: int | None
    error_type: str  # "error", "warning"
    message: str
    code_snippet: str | None = None

    def __str__(self) -> str:
        location = f"{self.file_path}"
        if self.line_number:
            location += f":{self.line_number}"
            if self.column_number:
                location += f":{self.column_number}"
        return f"{self.error_type.upper()}: {location} - {self.message}"


@dataclass
class CompilationResult:
    """Result of Java compilation."""

    success: bool
    build_tool: str  # "maven" or "gradle"
    duration_ms: float
    errors: list[CompilationError] = field(default_factory=list)
    warnings: list[CompilationError] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def __str__(self) -> str:
        status = "✓ SUCCESS" if self.success else "✗ FAILED"
        return (
            f"Compilation {status} ({self.build_tool}): "
            f"{self.error_count} errors, {self.warning_count} warnings, "
            f"{self.duration_ms:.0f}ms"
        )


@dataclass
class TestFailure:
    """Represents a single test failure."""

    test_class: str
    test_method: str
    error_type: str  # e.g., "AssertionError", "NullPointerException"
    message: str
    stack_trace: str | None = None

    def __str__(self) -> str:
        return f"{self.test_class}.{self.test_method}: {self.error_type} - {self.message}"


@dataclass
class TestResult:
    """Result of running Java tests."""

    success: bool
    build_tool: str
    duration_ms: float
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    failures: list[TestFailure] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""

    @property
    def pass_rate(self) -> float:
        """Calculate test pass rate (0.0 to 1.0)."""
        if self.tests_run == 0:
            return 0.0
        return self.tests_passed / self.tests_run

    def __str__(self) -> str:
        status = "✓ SUCCESS" if self.success else "✗ FAILED"
        return (
            f"Tests {status} ({self.build_tool}): "
            f"{self.tests_passed}/{self.tests_run} passed "
            f"({self.pass_rate * 100:.1f}%), "
            f"{self.tests_failed} failed, {self.tests_skipped} skipped, "
            f"{self.duration_ms:.0f}ms"
        )


@dataclass
class BuildToolInfo:
    """Information about detected build tool."""

    tool: Literal["maven", "gradle", "unknown"]
    config_file: Path | None = None
    wrapper_script: Path | None = None  # mvnw or gradlew
    has_wrapper: bool = False

    def get_command(self) -> list[str]:
        """Get the command to execute the build tool."""
        if self.has_wrapper and self.wrapper_script:
            return [str(self.wrapper_script.resolve())]
        elif self.tool == "maven":
            return ["mvn"]
        elif self.tool == "gradle":
            return ["gradle"]
        else:
            raise ValueError(f"Unknown build tool: {self.tool}")


# ============================================================================
# Build Tool Detection
# ============================================================================


async def detect_build_tool(repo_path: str | Path) -> BuildToolInfo:
    """
    Detect which build tool (Maven or Gradle) is used in the project.

    Checks for:
    1. Maven: pom.xml, mvnw (wrapper)
    2. Gradle: build.gradle, build.gradle.kts, gradlew (wrapper)

    Args:
        repo_path: Path to the Java project root

    Returns:
        BuildToolInfo with detected tool and configuration

    Example:
        build_info = await detect_build_tool("/path/to/project")
        if build_info.tool == "maven":
            print(f"Maven project with config: {build_info.config_file}")
    """
    repo_path = Path(repo_path)

    if not repo_path.exists():
        raise ValueError(f"Repository path does not exist: {repo_path}")

    logger.debug(f"Detecting build tool in {repo_path}")

    # Check for Maven
    pom_xml = repo_path / "pom.xml"
    mvnw = repo_path / "mvnw"

    if pom_xml.exists():
        logger.info("Detected Maven project (pom.xml found)")
        return BuildToolInfo(
            tool="maven",
            config_file=pom_xml,
            wrapper_script=mvnw if mvnw.exists() else None,
            has_wrapper=mvnw.exists(),
        )

    # Check for Gradle
    build_gradle = repo_path / "build.gradle"
    build_gradle_kts = repo_path / "build.gradle.kts"
    gradlew = repo_path / "gradlew"

    gradle_config = None
    if build_gradle.exists():
        gradle_config = build_gradle
    elif build_gradle_kts.exists():
        gradle_config = build_gradle_kts

    if gradle_config:
        logger.info(f"Detected Gradle project ({gradle_config.name} found)")
        return BuildToolInfo(
            tool="gradle",
            config_file=gradle_config,
            wrapper_script=gradlew if gradlew.exists() else None,
            has_wrapper=gradlew.exists(),
        )

    logger.warning(f"No build tool detected in {repo_path}")
    return BuildToolInfo(tool="unknown")


# ============================================================================
# Streaming Helpers
# ============================================================================


async def _stream_process_output(stdout: Any) -> AsyncIterator[str]:
    """
    Asynchronously stream output from subprocess line by line.

    This function reads from a subprocess stdout/stderr stream and yields
    lines as they arrive, enabling real-time progress updates.

    Args:
        stdout: subprocess.PIPE stdout/stderr stream

    Yields:
        Output lines as they arrive from the process

    Example:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
        async for line in _stream_process_output(process.stdout):
            await progress_callback(line)
    """
    loop = asyncio.get_event_loop()

    while True:
        # Read line in thread pool to avoid blocking event loop
        line = await loop.run_in_executor(None, stdout.readline)

        if not line:
            break

        yield line


# ============================================================================
# Compilation
# ============================================================================


async def compile_java_project(
    repo_path: str | Path,
    build_tool_info: BuildToolInfo | None = None,
    clean: bool = False,
    skip_tests: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> CompilationResult:
    """
    Compile a Java project using Maven or Gradle with optional real-time output streaming.

    Args:
        repo_path: Path to the Java project root
        build_tool_info: Optional pre-detected build tool info
        clean: Whether to clean before compiling
        skip_tests: Whether to skip running tests during compilation
        progress_callback: Optional async callback to receive output lines in real-time

    Returns:
        CompilationResult with success status and error details

    Example:
        result = await compile_java_project("/path/to/project", clean=True)
        if not result.success:
            for error in result.errors:
                print(f"Error: {error}")
    """

    repo_path = Path(repo_path)
    start_time = time.time()

    # Detect build tool if not provided
    if build_tool_info is None:
        build_tool_info = await detect_build_tool(repo_path)

    if build_tool_info.tool == "unknown":
        return CompilationResult(
            success=False,
            build_tool="unknown",
            duration_ms=0,
            errors=[
                CompilationError(
                    file_path=str(repo_path),
                    line_number=None,
                    column_number=None,
                    error_type="error",
                    message="No build tool detected (pom.xml or build.gradle not found)",
                )
            ],
        )

    logger.info(f"Compiling Java project with {build_tool_info.tool}")

    # Build command
    command = build_tool_info.get_command()

    if build_tool_info.tool == "maven":
        if clean:
            command.append("clean")
        command.append("compile")
        if skip_tests:
            command.append("-DskipTests")
    elif build_tool_info.tool == "gradle":
        if clean:
            command.append("clean")
        command.append("compileJava")
        if skip_tests:
            command.append("-x")
            command.append("test")

    logger.debug(f"Running command: {' '.join(command)}")

    # Execute compilation with streaming support
    try:
        if progress_callback:
            # Use Popen for streaming output
            process = subprocess.Popen(
                command,
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,  # Line buffered
            )

            output_lines = []

            # Stream output line by line
            if process.stdout:
                async for line in _stream_process_output(process.stdout):
                    output_lines.append(line)
                    # Send to progress callback
                    await progress_callback(line)

            # Wait for completion
            return_code = process.wait(timeout=300)

            duration_ms = (time.time() - start_time) * 1000

            # Parse errors from collected output
            full_output = "".join(output_lines)
            errors, warnings = _parse_build_output(full_output, build_tool_info.tool)

            success = return_code == 0

            compilation_result = CompilationResult(
                success=success,
                build_tool=build_tool_info.tool,
                duration_ms=duration_ms,
                errors=errors,
                warnings=warnings,
                stdout=full_output,
                stderr="",  # Merged into stdout
            )

        else:
            # No streaming - use traditional subprocess.run
            result = subprocess.run(
                command,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            duration_ms = (time.time() - start_time) * 1000

            # Parse output for errors
            errors, warnings = _parse_build_output(
                result.stdout + result.stderr, build_tool_info.tool
            )

            success = result.returncode == 0

            compilation_result = CompilationResult(
                success=success,
                build_tool=build_tool_info.tool,
                duration_ms=duration_ms,
                errors=errors,
                warnings=warnings,
                stdout=result.stdout,
                stderr=result.stderr,
            )

        logger.info(str(compilation_result))
        return compilation_result

    except subprocess.TimeoutExpired as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"Compilation timeout after {duration_ms:.0f}ms")
        return CompilationResult(
            success=False,
            build_tool=build_tool_info.tool,
            duration_ms=duration_ms,
            errors=[
                CompilationError(
                    file_path=str(repo_path),
                    line_number=None,
                    column_number=None,
                    error_type="error",
                    message=f"Compilation timeout after {duration_ms:.0f}ms",
                )
            ],
            stdout=e.stdout.decode() if e.stdout else "",
            stderr=e.stderr.decode() if e.stderr else "",
        )

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"Compilation failed: {e}")
        return CompilationResult(
            success=False,
            build_tool=build_tool_info.tool,
            duration_ms=duration_ms,
            errors=[
                CompilationError(
                    file_path=str(repo_path),
                    line_number=None,
                    column_number=None,
                    error_type="error",
                    message=f"Compilation error: {str(e)}",
                )
            ],
        )


# ============================================================================
# Error Parsing
# ============================================================================


def _parse_build_output(
    output: str, build_tool: str
) -> tuple[list[CompilationError], list[CompilationError]]:
    """
    Parse Maven or Gradle build output for errors and warnings.

    Maven error format:
        [ERROR] /path/to/File.java:[line,column] error message

    Gradle error format:
        /path/to/File.java:line: error: error message

    Args:
        output: Combined stdout + stderr from build
        build_tool: "maven" or "gradle"

    Returns:
        Tuple of (errors, warnings)
    """
    errors: list[CompilationError] = []
    warnings: list[CompilationError] = []

    if build_tool == "maven":
        errors, warnings = _parse_maven_output(output)
    elif build_tool == "gradle":
        errors, warnings = _parse_gradle_output(output)

    return errors, warnings


def _parse_maven_output(output: str) -> tuple[list[CompilationError], list[CompilationError]]:
    """Parse Maven compilation output."""
    errors: list[CompilationError] = []
    warnings: list[CompilationError] = []

    # Strip ANSI color codes first (Maven outputs colored text)
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    output = ansi_escape.sub("", output)

    # Maven pattern: [ERROR] /path/to/File.java:[line,column] message
    # Example: [ERROR] /home/user/project/src/main/java/com/example/Auth.java:[23,15] cannot find symbol
    # Note: Sometimes column is optional: [ERROR] /path/File.java:[line] message
    pattern = re.compile(r"\[(ERROR|WARNING)\]\s+([^\s]+\.java):\[(\d+)(?:,(\d+))?\]\s+(.+)")

    for line in output.split("\n"):
        match = pattern.search(line)
        if match:
            error_type = match.group(1).lower()
            file_path = match.group(2)
            line_num = int(match.group(3))
            col_num = int(match.group(4)) if match.group(4) else None
            message = match.group(5).strip()

            compilation_error = CompilationError(
                file_path=file_path,
                line_number=line_num,
                column_number=col_num,
                error_type=error_type,
                message=message,
            )

            if error_type == "error":
                errors.append(compilation_error)
            else:
                warnings.append(compilation_error)

    return errors, warnings


def _parse_gradle_output(output: str) -> tuple[list[CompilationError], list[CompilationError]]:
    """Parse Gradle compilation output."""
    errors: list[CompilationError] = []
    warnings: list[CompilationError] = []

    # Gradle pattern: /path/to/File.java:line: error: message
    # Example: /home/user/project/src/main/java/com/example/Auth.java:23: error: cannot find symbol
    pattern = re.compile(r"([^\s]+\.java):(\d+):\s+(error|warning):\s+(.+)")

    for line in output.split("\n"):
        match = pattern.search(line)
        if match:
            file_path = match.group(1)
            line_num = int(match.group(2))
            error_type = match.group(3).lower()
            message = match.group(4).strip()

            compilation_error = CompilationError(
                file_path=file_path,
                line_number=line_num,
                column_number=None,  # Gradle doesn't always provide column
                error_type=error_type,
                message=message,
            )

            if error_type == "error":
                errors.append(compilation_error)
            else:
                warnings.append(compilation_error)

    return errors, warnings


# ============================================================================
# Testing
# ============================================================================


async def run_java_tests(
    repo_path: str | Path,
    build_tool_info: BuildToolInfo | None = None,
    test_pattern: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> TestResult:
    """
    Run JUnit tests in a Java project with optional real-time output streaming.

    Args:
        repo_path: Path to the Java project root
        build_tool_info: Optional pre-detected build tool info
        test_pattern: Optional pattern to filter tests (e.g., "*ServiceTest")
        progress_callback: Optional async callback to receive output lines in real-time

    Returns:
        TestResult with test outcomes and failure details

    Example:
        result = await run_java_tests("/path/to/project")
        print(f"Pass rate: {result.pass_rate * 100:.1f}%")
        for failure in result.failures:
            print(f"Failed: {failure}")
    """

    repo_path = Path(repo_path)
    start_time = time.time()

    # Detect build tool if not provided
    if build_tool_info is None:
        build_tool_info = await detect_build_tool(repo_path)

    if build_tool_info.tool == "unknown":
        return TestResult(
            success=False,
            build_tool="unknown",
            duration_ms=0,
        )

    logger.info(f"Running tests with {build_tool_info.tool}")

    # Build command
    command = build_tool_info.get_command()

    if build_tool_info.tool == "maven":
        command.append("test")
        if test_pattern:
            command.append(f"-Dtest={test_pattern}")
    elif build_tool_info.tool == "gradle":
        command.append("test")
        if test_pattern:
            command.append(f"--tests={test_pattern}")

    logger.debug(f"Running command: {' '.join(command)}")

    # Execute tests with streaming support
    try:
        if progress_callback:
            # Use Popen for streaming output
            process = subprocess.Popen(
                command,
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,  # Line buffered
            )

            output_lines = []

            # Stream output line by line
            if process.stdout:
                async for line in _stream_process_output(process.stdout):
                    output_lines.append(line)
                    # Send to progress callback
                    await progress_callback(line)

            # Wait for completion
            return_code = process.wait(timeout=600)

            duration_ms = (time.time() - start_time) * 1000

            # Parse test results from collected output
            full_output = "".join(output_lines)
            test_stats, failures = _parse_test_output(full_output, build_tool_info.tool)

            tests_run = test_stats.get("run", 0)
            # Consider a test run with zero tests as a non-success for validation purposes
            if tests_run == 0:
                logger.warning("No tests detected by build tool (tests_run=0)")

            success = (return_code == 0) and (tests_run > 0)

            test_result = TestResult(
                success=success,
                build_tool=build_tool_info.tool,
                duration_ms=duration_ms,
                tests_run=test_stats.get("run", 0),
                tests_passed=test_stats.get("passed", 0),
                tests_failed=test_stats.get("failed", 0),
                tests_skipped=test_stats.get("skipped", 0),
                failures=failures,
                stdout=full_output,
                stderr="",  # Merged into stdout
            )

        else:
            # No streaming - use traditional subprocess.run
            result = subprocess.run(
                command,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for tests
            )

            duration_ms = (time.time() - start_time) * 1000

            # Parse test output
            test_stats, failures = _parse_test_output(
                result.stdout + result.stderr, build_tool_info.tool
            )

            tests_run = test_stats.get("run", 0)
            if tests_run == 0:
                logger.warning("No tests detected by build tool (tests_run=0)")

            success = (result.returncode == 0) and (tests_run > 0)

            test_result = TestResult(
                success=success,
                build_tool=build_tool_info.tool,
                duration_ms=duration_ms,
                tests_run=test_stats.get("run", 0),
                tests_passed=test_stats.get("passed", 0),
                tests_failed=test_stats.get("failed", 0),
                tests_skipped=test_stats.get("skipped", 0),
                failures=failures,
                stdout=result.stdout,
                stderr=result.stderr,
            )

        logger.info(str(test_result))
        return test_result

    except subprocess.TimeoutExpired as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"Test timeout after {duration_ms:.0f}ms")
        return TestResult(
            success=False,
            build_tool=build_tool_info.tool,
            duration_ms=duration_ms,
            stdout=e.stdout.decode() if e.stdout else "",
            stderr=e.stderr.decode() if e.stderr else "",
        )

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"Test execution failed: {e}")
        return TestResult(
            success=False,
            build_tool=build_tool_info.tool,
            duration_ms=duration_ms,
        )


def _parse_test_output(output: str, build_tool: str) -> tuple[dict[str, int], list[TestFailure]]:
    """
    Parse test output for statistics and failures.

    Args:
        output: Combined stdout + stderr from test run
        build_tool: "maven" or "gradle"

    Returns:
        Tuple of (test_stats dict, failures list)
    """
    if build_tool == "maven":
        return _parse_maven_test_output(output)
    elif build_tool == "gradle":
        return _parse_gradle_test_output(output)
    else:
        return {}, []


def _parse_maven_test_output(output: str) -> tuple[dict[str, int], list[TestFailure]]:
    """Parse Maven test output."""
    stats = {"run": 0, "passed": 0, "failed": 0, "skipped": 0}
    failures: list[TestFailure] = []

    # Maven summary: Tests run: 10, Failures: 2, Errors: 0, Skipped: 1
    summary_pattern = re.compile(
        r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)"
    )

    # Maven failure: testMethod(com.example.TestClass)  Time elapsed: 0.002 s  <<< FAILURE!
    failure_pattern = re.compile(r"(\w+)\(([^)]+)\)\s+Time elapsed:.*?<<<\s*(FAILURE|ERROR)!")

    for line in output.split("\n"):
        # Parse summary
        summary_match = summary_pattern.search(line)
        if summary_match:
            run = int(summary_match.group(1))
            failed = int(summary_match.group(2)) + int(summary_match.group(3))
            skipped = int(summary_match.group(4))
            passed = run - failed - skipped

            stats["run"] = run
            stats["passed"] = passed
            stats["failed"] = failed
            stats["skipped"] = skipped

        # Parse failure
        failure_match = failure_pattern.search(line)
        if failure_match:
            test_method = failure_match.group(1)
            test_class = failure_match.group(2)
            error_type = failure_match.group(3)

            failures.append(
                TestFailure(
                    test_class=test_class,
                    test_method=test_method,
                    error_type=error_type,
                    message=line.strip(),
                )
            )

    return stats, failures


def _parse_gradle_test_output(output: str) -> tuple[dict[str, int], list[TestFailure]]:
    """Parse Gradle test output."""
    stats = {"run": 0, "passed": 0, "failed": 0, "skipped": 0}
    failures: list[TestFailure] = []

    # Gradle summary: 10 tests completed, 2 failed, 1 skipped
    # Or: BUILD SUCCESSFUL in 5s with 8 tests
    for line in output.split("\n"):
        if "tests completed" in line.lower():
            # Extract numbers
            numbers = re.findall(r"(\d+)\s+tests?\s+completed", line)
            if numbers:
                stats["run"] = int(numbers[0])

            failures_match = re.search(r"(\d+)\s+failed", line)
            if failures_match:
                stats["failed"] = int(failures_match.group(1))

            skipped_match = re.search(r"(\d+)\s+skipped", line)
            if skipped_match:
                stats["skipped"] = int(skipped_match.group(1))

            stats["passed"] = stats["run"] - stats["failed"] - stats["skipped"]

        # Parse individual failure
        if "FAILED" in line and ":test" in line:
            # Example: com.example.TestClass > testMethod FAILED
            parts = line.split(">")
            if len(parts) >= 2:
                test_class = parts[0].strip()
                test_info = parts[1].strip()
                test_method = test_info.split()[0] if test_info else "unknown"

                failures.append(
                    TestFailure(
                        test_class=test_class,
                        test_method=test_method,
                        error_type="FAILED",
                        message=line.strip(),
                    )
                )

    return stats, failures
