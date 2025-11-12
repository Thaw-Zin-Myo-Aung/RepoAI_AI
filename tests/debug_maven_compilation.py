"""Debug script to understand Maven compilation failures."""

import asyncio
import subprocess
import tempfile
from pathlib import Path

from repoai.utils.java_build_utils import compile_java_project


async def debug_maven_compilation() -> None:
    """Create a simple Maven project and see what happens during compilation."""

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir) / "test-project"
        project_path.mkdir()

        # Create minimal pom.xml
        pom_xml = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.example</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>

    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework</groupId>
            <artifactId>spring-context</artifactId>
            <version>6.1.0</version>
        </dependency>
    </dependencies>
</project>
"""
        (project_path / "pom.xml").write_text(pom_xml)

        # Create source directory but NO source files
        src_main_java = project_path / "src" / "main" / "java"
        src_main_java.mkdir(parents=True)

        print("=" * 80)
        print("TEST 1: Empty project (no source files)")
        print("=" * 80)

        # Try to compile with our utility
        result = await compile_java_project(project_path, clean=True)

        print("\nCompilation result:")
        print(f"  Success: {result.success}")
        print("  Return code: (not exposed)")
        print(f"  Error count: {result.error_count}")
        print(f"  Warning count: {result.warning_count}")
        print(f"  Duration: {result.duration_ms}ms")

        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for err in result.errors[:5]:
                print(f"  - {err.file_path}:{err.line_number}: {err.message}")

        # Now run Maven directly to see raw output
        print("\n" + "=" * 80)
        print("RAW MAVEN OUTPUT:")
        print("=" * 80)

        try:
            proc = subprocess.run(
                ["mvn", "clean", "compile"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            print(f"\nReturn code: {proc.returncode}")
            print(f"\nSTDOUT:\n{proc.stdout}")
            print(f"\nSTDERR:\n{proc.stderr}")

        except subprocess.TimeoutExpired:
            print("Maven command timed out!")
        except FileNotFoundError:
            print("mvn command not found!")

        # TEST 2: Add a simple Java file
        print("\n" + "=" * 80)
        print("TEST 2: With a simple Java file")
        print("=" * 80)

        com_example = src_main_java / "com" / "example"
        com_example.mkdir(parents=True)

        java_file = """package com.example;

import org.springframework.stereotype.Service;

@Service
public class TestService {
    public String greet() {
        return "Hello, World!";
    }
}
"""
        (com_example / "TestService.java").write_text(java_file)

        # Try again
        result2 = await compile_java_project(project_path, clean=True)

        print("\nCompilation result:")
        print(f"  Success: {result2.success}")
        print(f"  Error count: {result2.error_count}")
        print(f"  Warning count: {result2.warning_count}")
        print(f"  Duration: {result2.duration_ms}ms")

        # Raw Maven output again
        print("\nRAW MAVEN OUTPUT:")
        proc2 = subprocess.run(
            ["mvn", "clean", "compile"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

        print(f"\nReturn code: {proc2.returncode}")
        if proc2.returncode != 0:
            print(f"\nSTDOUT:\n{proc2.stdout}")
            print(f"\nSTDERR:\n{proc2.stderr}")
        else:
            print("\n✅ Compilation succeeded!")


if __name__ == "__main__":
    asyncio.run(debug_maven_compilation())
