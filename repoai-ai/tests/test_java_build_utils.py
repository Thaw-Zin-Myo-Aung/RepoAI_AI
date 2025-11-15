"""
Tests for Java build utilities.

These are integration tests that require Maven/Gradle to be installed.
"""

import asyncio
from pathlib import Path

import pytest

from repoai.utils.java_build_utils import (
    BuildToolInfo,
    CompilationError,
    CompilationResult,
    TestFailure,
    TestResult,
    compile_java_project,
    detect_build_tool,
    run_java_tests,
)

# ============================================================================
# Build Tool Detection Tests
# ============================================================================


@pytest.mark.anyio
async def test_detect_maven_project(tmp_path: Path):
    """Test Maven project detection."""
    # Create fake pom.xml
    pom_xml = tmp_path / "pom.xml"
    pom_xml.write_text("<project></project>")

    build_info = await detect_build_tool(tmp_path)

    assert build_info.tool == "maven"
    assert build_info.config_file == pom_xml
    assert not build_info.has_wrapper  # No mvnw created


@pytest.mark.anyio
async def test_detect_maven_with_wrapper(tmp_path: Path):
    """Test Maven project with wrapper detection."""
    # Create pom.xml and mvnw
    (tmp_path / "pom.xml").write_text("<project></project>")
    mvnw = tmp_path / "mvnw"
    mvnw.write_text("#!/bin/bash")

    build_info = await detect_build_tool(tmp_path)

    assert build_info.tool == "maven"
    assert build_info.has_wrapper
    assert build_info.wrapper_script == mvnw


@pytest.mark.anyio
async def test_detect_gradle_project(tmp_path: Path):
    """Test Gradle project detection."""
    # Create fake build.gradle
    build_gradle = tmp_path / "build.gradle"
    build_gradle.write_text("plugins { id 'java' }")

    build_info = await detect_build_tool(tmp_path)

    assert build_info.tool == "gradle"
    assert build_info.config_file == build_gradle


@pytest.mark.anyio
async def test_detect_unknown_project(tmp_path: Path):
    """Test detection when no build tool found."""
    build_info = await detect_build_tool(tmp_path)

    assert build_info.tool == "unknown"
    assert build_info.config_file is None


@pytest.mark.anyio
async def test_maven_priority_over_gradle(tmp_path: Path):
    """Test that Maven is detected first if both exist."""
    # Create both pom.xml and build.gradle
    (tmp_path / "pom.xml").write_text("<project></project>")
    (tmp_path / "build.gradle").write_text("plugins { id 'java' }")

    build_info = await detect_build_tool(tmp_path)

    # Maven should win
    assert build_info.tool == "maven"


# ============================================================================
# Compilation Tests (Requires actual Maven/Gradle)
# ============================================================================


@pytest.mark.skipif(
    not Path("/usr/bin/mvn").exists() and not Path("/usr/local/bin/mvn").exists(),
    reason="Maven not installed",
)
@pytest.mark.anyio
async def test_compile_nonexistent_project():
    """Test compilation of non-existent project."""
    # Should raise ValueError for nonexistent path
    with pytest.raises(ValueError, match="Repository path does not exist"):
        await compile_java_project("/nonexistent/path")


# ============================================================================
# Error Parsing Tests
# ============================================================================


def test_compilation_error_str():
    """Test CompilationError string representation."""
    error = CompilationError(
        file_path="src/main/java/com/example/Auth.java",
        line_number=23,
        column_number=15,
        error_type="error",
        message="cannot find symbol: class JwtService",
    )

    error_str = str(error)
    assert "ERROR" in error_str
    assert "Auth.java:23:15" in error_str
    assert "cannot find symbol" in error_str


def test_compilation_result_str():
    """Test CompilationResult string representation."""
    result = CompilationResult(
        success=False,
        build_tool="maven",
        duration_ms=5432.1,
        errors=[
            CompilationError(
                file_path="Test.java",
                line_number=10,
                column_number=5,
                error_type="error",
                message="test error",
            )
        ],
        warnings=[],
    )

    result_str = str(result)
    assert "FAILED" in result_str
    assert "maven" in result_str
    assert "1 errors" in result_str
    assert "5432ms" in result_str


def test_test_result_pass_rate():
    """Test TestResult pass rate calculation."""
    result = TestResult(
        success=True,
        build_tool="maven",
        duration_ms=1000,
        tests_run=10,
        tests_passed=8,
        tests_failed=2,
        tests_skipped=0,
    )

    assert result.pass_rate == 0.8  # 80%

    # Zero tests case
    result_empty = TestResult(
        success=True,
        build_tool="maven",
        duration_ms=100,
        tests_run=0,
    )
    assert result_empty.pass_rate == 0.0


def test_test_failure_str():
    """Test TestFailure string representation."""
    failure = TestFailure(
        test_class="com.example.auth.JwtServiceTest",
        test_method="testTokenGeneration",
        error_type="AssertionError",
        message="Expected 'valid' but got 'invalid'",
    )

    failure_str = str(failure)
    assert "JwtServiceTest.testTokenGeneration" in failure_str
    assert "AssertionError" in failure_str


def test_build_tool_info_get_command():
    """Test BuildToolInfo command generation."""
    # Maven with wrapper
    maven_info = BuildToolInfo(
        tool="maven",
        wrapper_script=Path("/path/to/mvnw"),
        has_wrapper=True,
    )
    assert maven_info.get_command() == ["/path/to/mvnw"]

    # Maven without wrapper
    maven_info_no_wrapper = BuildToolInfo(
        tool="maven",
        has_wrapper=False,
    )
    assert maven_info_no_wrapper.get_command() == ["mvn"]

    # Gradle
    gradle_info = BuildToolInfo(
        tool="gradle",
        has_wrapper=False,
    )
    assert gradle_info.get_command() == ["gradle"]

    # Unknown
    unknown_info = BuildToolInfo(tool="unknown")
    with pytest.raises(ValueError, match="Unknown build tool"):
        unknown_info.get_command()


# ============================================================================
# Manual Test (Run this manually to see it work!)
# ============================================================================


async def manual_test_with_real_project():
    """
    Manual test to demonstrate with a real Java project.

    You can run this manually:

        python -c "
        import asyncio
        from tests.test_java_build_utils import manual_test_with_real_project
        asyncio.run(manual_test_with_real_project())
        "

    Or just call it from a Python script.
    """
    print("\n" + "=" * 80)
    print("MANUAL TEST: Java Build Utils with Real Project")
    print("=" * 80)

    # Example: Test with spring-petclinic or any local Maven project
    # Change this to a real project path on your system
    test_project = Path("/path/to/spring-petclinic")  # <-- Change this!

    if not test_project.exists():
        print(f"\n❌ Test project not found: {test_project}")
        print("   Please update the path in manual_test_with_real_project()")
        return

    print(f"\n📁 Testing with: {test_project}")

    # Test 1: Detect build tool
    print("\n1️⃣  Detecting build tool...")
    build_info = await detect_build_tool(test_project)
    print(f"   ✓ Detected: {build_info.tool}")
    print(f"   ✓ Config: {build_info.config_file}")
    print(f"   ✓ Wrapper: {build_info.has_wrapper}")

    # Test 2: Compile project
    print("\n2️⃣  Compiling project...")
    compile_result = await compile_java_project(test_project, clean=True)
    print(f"   {compile_result}")

    if not compile_result.success:
        print("\n   ❌ Compilation errors:")
        for error in compile_result.errors[:5]:  # Show first 5
            print(f"      {error}")

    # Test 3: Run tests
    print("\n3️⃣  Running tests...")
    test_result = await run_java_tests(test_project)
    print(f"   {test_result}")

    if not test_result.success:
        print("\n   ❌ Test failures:")
        for failure in test_result.failures[:5]:  # Show first 5
            print(f"      {failure}")

    print("\n" + "=" * 80)
    print("MANUAL TEST COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    # Run manual test
    asyncio.run(manual_test_with_real_project())
