"""
Test build output streaming functionality.

This tests the new real-time Maven/Gradle output streaming feature.
"""

from pathlib import Path

import pytest

from repoai.utils.java_build_utils import compile_java_project


@pytest.mark.asyncio
async def test_compilation_with_progress_callback(tmp_path: Path) -> None:
    """Test that progress callback receives compilation output lines."""

    # Create simple Java project
    src_dir = tmp_path / "src" / "main" / "java" / "com" / "example"
    src_dir.mkdir(parents=True)

    (src_dir / "Main.java").write_text(
        """
package com.example;

public class Main {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}
"""
    )

    # Create pom.xml
    (tmp_path / "pom.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <groupId>com.example</groupId>
    <artifactId>test-streaming</artifactId>
    <version>1.0-SNAPSHOT</version>
    
    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>
</project>
"""
    )

    # Collect output lines
    output_lines: list[str] = []

    async def progress_callback(line: str) -> None:
        """Collect output lines from build process."""
        output_lines.append(line)
        print(f"BUILD: {line.rstrip()}")  # Also print for visibility

    # Run compilation with callback
    result = await compile_java_project(repo_path=tmp_path, progress_callback=progress_callback)

    # Verify compilation result first
    assert result.success, f"Compilation should succeed, got errors: {result.errors}"

    # Verify callback received output
    assert len(output_lines) > 0, f"No output lines received from compilation. Result: {result}"

    # Verify Maven output patterns
    # Note: Maven uses ANSI color codes, so we need to strip them or search more flexibly
    non_empty_lines = [line for line in output_lines if line.strip()]
    has_maven_output = any(
        "INFO" in line or "Building" in line or "SUCCESS" in line for line in non_empty_lines
    )
    assert (
        has_maven_output
    ), f"Expected Maven output patterns. Got {len(non_empty_lines)} non-empty lines"

    # Verify we got substantial output
    assert (
        len(non_empty_lines) >= 5
    ), f"Expected at least 5 lines of output, got {len(non_empty_lines)}"
    assert result.build_tool == "maven"
    assert result.error_count == 0


@pytest.mark.asyncio
async def test_compilation_without_callback(tmp_path: Path) -> None:
    """Test that compilation still works without progress callback (backward compatibility)."""

    # Create simple Java project
    src_dir = tmp_path / "src" / "main" / "java" / "com" / "example"
    src_dir.mkdir(parents=True)

    (src_dir / "HelloWorld.java").write_text(
        """
package com.example;

public class HelloWorld {
    public void greet() {
        System.out.println("Hello!");
    }
}
"""
    )

    # Create pom.xml
    (tmp_path / "pom.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test-no-streaming</artifactId>
    <version>1.0</version>
    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
    </properties>
</project>
"""
    )

    # Run compilation WITHOUT callback
    result = await compile_java_project(repo_path=tmp_path, progress_callback=None)

    # Should still work with traditional subprocess.run
    assert result.success, f"Compilation should succeed, got errors: {result.errors}"
    assert result.build_tool == "maven"
    assert result.error_count == 0
    assert len(result.stdout) > 0, "Should capture stdout even without streaming"


@pytest.mark.asyncio
async def test_streaming_captures_errors(tmp_path: Path) -> None:
    """Test that streaming captures compilation errors."""

    # Create Java file with error
    src_dir = tmp_path / "src" / "main" / "java" / "com" / "example"
    src_dir.mkdir(parents=True)

    (src_dir / "Broken.java").write_text(
        """
package com.example;

public class Broken {
    public void method() {
        // Missing semicolon causes error
        String x = "test"
    }
}
"""
    )

    # Create pom.xml
    (tmp_path / "pom.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test-errors</artifactId>
    <version>1.0</version>
    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
    </properties>
</project>
"""
    )

    output_lines: list[str] = []

    async def progress_callback(line: str) -> None:
        output_lines.append(line)

    # Run compilation with callback
    result = await compile_java_project(repo_path=tmp_path, progress_callback=progress_callback)

    # Verify compilation failed
    assert not result.success, "Compilation should fail due to syntax error"
    assert result.error_count > 0, "Should have at least one error"

    # Verify error appears in streamed output
    has_error_in_output = any("ERROR" in line or "error" in line for line in output_lines)
    assert has_error_in_output, "Expected error message in streamed output"


@pytest.mark.asyncio
async def test_callback_called_for_each_line(tmp_path: Path) -> None:
    """Test that callback is called for each output line individually."""

    # Create simple project
    src_dir = tmp_path / "src" / "main" / "java"
    src_dir.mkdir(parents=True)

    (src_dir / "Test.java").write_text("public class Test {}")

    (tmp_path / "pom.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>test</groupId>
    <artifactId>test</artifactId>
    <version>1.0</version>
    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
    </properties>
</project>
"""
    )

    call_count = 0

    async def progress_callback(line: str) -> None:
        nonlocal call_count
        call_count += 1
        # Verify each call receives a single line (not batched)
        assert "\n" in line or line.endswith("\n"), "Each callback should receive individual lines"

    await compile_java_project(repo_path=tmp_path, progress_callback=progress_callback)

    # Verify callback was called multiple times (Maven produces many log lines)
    assert call_count > 5, f"Expected multiple callback calls, got {call_count}"


if __name__ == "__main__":
    # Run tests manually
    import sys

    sys.exit(pytest.main([__file__, "-v", "-s"]))
