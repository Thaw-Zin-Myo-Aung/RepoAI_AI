"""
Debug Maven output to understand error format.
"""

import asyncio
import tempfile
from pathlib import Path

from repoai.utils.java_build_utils import compile_java_project


async def debug_maven_errors():
    """See what Maven actually outputs for errors."""
    print("\n" + "=" * 80)
    print("Debug Maven Error Output")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_dir = Path(tmp_dir)

        # Create pom.xml
        (project_dir / "pom.xml").write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test</artifactId>
    <version>1.0</version>
    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
    </properties>
</project>
"""
        )

        # Create broken Java file
        src_dir = project_dir / "src" / "main" / "java" / "com" / "example"
        src_dir.mkdir(parents=True)
        (src_dir / "Broken.java").write_text(
            """package com.example;

public class Broken {
    public void test() {
        // Missing semicolon
        String x = "hello"
        System.out.println(x);
    }
}
"""
        )

        print("\nCompiling broken code...\n")
        result = await compile_java_project(project_dir)

        print("=" * 80)
        print("STDOUT:")
        print("=" * 80)
        print(result.stdout)

        print("\n" + "=" * 80)
        print("STDERR:")
        print("=" * 80)
        print(result.stderr)

        print("\n" + "=" * 80)
        print(f"Parsed Errors: {len(result.errors)}")
        print("=" * 80)
        for error in result.errors:
            print(f"  {error}")

        print("\n" + "=" * 80)
        print(f"Parsed Warnings: {len(result.warnings)}")
        print("=" * 80)
        for warning in result.warnings:
            print(f"  {warning}")


if __name__ == "__main__":
    asyncio.run(debug_maven_errors())
