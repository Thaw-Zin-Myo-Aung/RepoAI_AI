"""
Quick test of java_build_utils with a minimal Maven project.
"""

import asyncio
import tempfile
from pathlib import Path

from repoai.utils.java_build_utils import (
    compile_java_project,
    detect_build_tool,
)


async def test_maven_build_utils():
    """Test build utils with a minimal Maven project."""
    print("\n" + "=" * 80)
    print("Testing Java Build Utils with Maven")
    print("=" * 80)

    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_dir = Path(tmp_dir)
        print(f"\n📁 Project directory: {project_dir}")

        # Create minimal pom.xml
        pom_xml = project_dir / "pom.xml"
        pom_xml.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <groupId>com.example</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0-SNAPSHOT</version>
    
    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>
</project>
"""
        )
        print("✓ Created pom.xml")

        # Create source directory structure
        src_dir = project_dir / "src" / "main" / "java" / "com" / "example"
        src_dir.mkdir(parents=True)

        # Create a simple Java class
        java_file = src_dir / "HelloWorld.java"
        java_file.write_text(
            """package com.example;

public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
    
    public String getMessage() {
        return "Hello from RepoAI!";
    }
}
"""
        )
        print("✓ Created HelloWorld.java")

        # Test 1: Detect build tool
        print("\n1️⃣  Detecting build tool...")
        build_info = await detect_build_tool(project_dir)
        print(f"   Tool: {build_info.tool}")
        print(f"   Config: {build_info.config_file}")
        print(f"   Wrapper: {build_info.has_wrapper}")
        assert build_info.tool == "maven", "Should detect Maven"

        # Test 2: Compile project
        print("\n2️⃣  Compiling project...")
        compile_result = await compile_java_project(project_dir, clean=True)
        print(f"   {compile_result}")

        if compile_result.success:
            print("   ✓ Compilation successful!")
            # Check if class file was created
            class_file = project_dir / "target" / "classes" / "com" / "example" / "HelloWorld.class"
            if class_file.exists():
                print(f"   ✓ Class file created: {class_file.name}")
        else:
            print("   ✗ Compilation failed")
            for error in compile_result.errors:
                print(f"      ERROR: {error}")

        # Test 3: Create a Java file with errors
        print("\n3️⃣  Testing compilation error detection...")
        broken_file = src_dir / "BrokenClass.java"
        broken_file.write_text(
            """package com.example;

public class BrokenClass {
    public void doSomething() {
        // Missing semicolon
        String msg = "This will fail"
        System.out.println(msg);
    }
    // Missing closing brace
"""
        )
        print("   ✓ Created BrokenClass.java (with intentional errors)")

        compile_result2 = await compile_java_project(project_dir, clean=False)
        print(f"   {compile_result2}")

        if not compile_result2.success:
            print("   ✓ Correctly detected compilation errors:")
            for i, error in enumerate(compile_result2.errors[:3], 1):
                print(f"      {i}. {error}")
        else:
            print("   ⚠️  Expected compilation to fail, but it succeeded?")

    print("\n" + "=" * 80)
    print("Test Complete!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_maven_build_utils())
