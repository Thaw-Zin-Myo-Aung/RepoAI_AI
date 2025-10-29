"""
File Writer Module - Writes generated code to disk.

Handles writing CodeChanges to actual files on disk for:
- Real compilation with Maven (default) or Gradle (when detected)
- Actual test execution
- Static analysis tools
- Easy inspection and debugging

Build System Priority:
- Maven is the default build system (most common in enterprise Java)
- Gradle is only used when build.gradle exists in the project
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from repoai.models import CodeChanges
from repoai.utils.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class FileWriter:
    """
    Writes generated code changes to disk.

    Creates a staging directory structure where generated files
    can be compiled, tested, and validated before being applied
    to the actual repository.

    Example:
        writer = FileWriter(base_path="/tmp/repoai")
        output_dir = writer.write_code_changes(code_changes)
        print(f"Files written to: {output_dir}")

        # Later, clean up
        writer.cleanup(code_changes.plan_id)
    """

    def __init__(self, base_path: str = "tmp/repoai"):
        """
        Initializes FileWrite.

        Args:
            base_path: Base directory for writing generated files.
        """

        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"FileWriter initialized with base_path: {self.base_path}")

    def write_code_changes(
        self,
        code_changes: CodeChanges,
        create_project_structure: bool = True,
    ) -> Path:
        """
        Write all code changes to disk.

        Creates directory structure:
        /tmp/repoai/
        └── plan_20250126_123456/
            ├── src/
            │   └── main/
            │       └── java/
            │           └── com/
            │               └── example/
            │                   ├── JwtService.java
            │                   └── AuthController.java
            ├── src/test/java/...
            └── pom.xml (Maven default)

        Args:
            code_changes: CodeChanges object with all changes
            create_project_structure: If True, create Maven project structure

        Returns:
            Path: Directory where files were written

        Example:
            output_dir = writer.write_code_changes(code_changes)
            # Files now exist at output_dir/src/main/java/...
        """
        # Create plan-specific directory
        plan_dir = self.base_path / code_changes.plan_id
        plan_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Writing {len(code_changes.changes)} files to {plan_dir}")

        files_written = 0

        for change in code_changes.changes:
            if change.change_type == "deleted":
                # Don't write deleted files
                logger.debug(f"Skipping deleted file: {change.file_path}")
                continue

            if not change.modified_content:
                logger.warning(f"No content for {change.file_path}, skipping")
                continue

            # Write the file
            full_path = plan_dir / change.file_path
            self._write_file(full_path, change.modified_content)
            files_written += 1

        logger.info(f"Successfully wrote {files_written} files to {plan_dir}")

        # Create build configuration if needed
        if create_project_structure:
            self._create_build_config(plan_dir, code_changes)

        return plan_dir

    def _write_file(self, file_path: Path, content: str) -> None:
        """
        Write a single file to disk.

        Args:
            file_path: Full path where file should be written
            content: File content
        """
        # Create parent directories
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        file_path.write_text(content, encoding="utf-8")
        logger.debug(f"Wrote file: {file_path}")

    def _create_build_config(self, plan_dir: Path, code_changes: CodeChanges) -> None:
        """
        Create Maven build configuration (default for Java projects).

        Maven is the primary build system. Gradle is only preserved if
        build.gradle already exists in the changes.

        Args:
            plan_dir: Directory where build config should be created
            code_changes: CodeChanges with dependency information
        """
        # Check if pom.xml already exists in changes
        has_pom = any(change.file_path.endswith("pom.xml") for change in code_changes.changes)

        if has_pom:
            logger.debug("pom.xml already in changes, skipping generation")
            return

        # Check if build.gradle already exists (preserve Gradle if detected)
        has_gradle = any(
            change.file_path.endswith("build.gradle") for change in code_changes.changes
        )

        if has_gradle:
            logger.debug("build.gradle detected in changes, preserving Gradle setup")
            return

        # Default to Maven: create minimal pom.xml if dependencies were added
        if code_changes.dependencies_added:
            logger.info("Creating minimal pom.xml with dependencies (Maven default)")
            pom_content = self._generate_minimal_pom(code_changes)
            pom_path = plan_dir / "pom.xml"
            self._write_file(pom_path, pom_content)

    def _generate_minimal_pom(self, code_changes: CodeChanges) -> str:
        """
        Generate minimal Maven pom.xml with dependencies.

        Maven is the default build system for Java enterprise applications.
        This generates a standard Spring Boot compatible pom.xml structure.

        Args:
            code_changes: CodeChanges with dependencies

        Returns:
            str: pom.xml content (Maven format)
        """
        dependencies_xml = ""
        for dep in code_changes.dependencies_added:
            # Parse dependency string: groupId:artifactId:version
            parts = dep.split(":")
            if len(parts) >= 2:
                group_id = parts[0]
                artifact_id = parts[1]
                version = parts[2] if len(parts) > 2 else "LATEST"

                dependencies_xml += f"""        <dependency>
            <groupId>{group_id}</groupId>
            <artifactId>{artifact_id}</artifactId>
            <version>{version}</version>
        </dependency>
"""

        pom_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.example</groupId>
    <artifactId>repoai-generated</artifactId>
    <version>1.0-SNAPSHOT</version>
    <packaging>jar</packaging>

    <properties>
        <java.version>17</java.version>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>

    <dependencies>
{dependencies_xml}
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.11.0</version>
            </plugin>
        </plugins>
    </build>
</project>
"""
        return pom_content

    def cleanup(self, plan_id: str) -> None:
        """
        Clean up generated files for a plan.

        Args:
            plan_id: Plan ID to clean up

        Example:
            writer.cleanup("plan_20250126_123456")
        """
        plan_dir = self.base_path / plan_id

        if plan_dir.exists():
            shutil.rmtree(plan_dir)
            logger.info(f"Cleaned up {plan_dir}")
        else:
            logger.debug(f"Nothing to clean up for {plan_id}")

    def cleanup_all(self) -> None:
        """
        Clean up all generated files (use with caution).

        Example:
            writer.cleanup_all()  # Removes everything in /tmp/repoai
        """
        if self.base_path.exists():
            shutil.rmtree(self.base_path)
            self.base_path.mkdir(parents=True, exist_ok=True)
            logger.warning(f"Cleaned up all files in {self.base_path}")

    def get_output_directory(self, plan_id: str) -> Path:
        """
        Get the output directory for a plan.

        Args:
            plan_id: Plan ID

        Returns:
            Path: Output directory path
        """
        return self.base_path / plan_id

    def list_generated_files(self, plan_id: str) -> list[Path]:
        """
        List all generated files for a plan.

        Args:
            plan_id: Plan ID

        Returns:
            list[Path]: List of generated file paths
        """
        plan_dir = self.base_path / plan_id

        if not plan_dir.exists():
            return []

        files = []
        for file_path in plan_dir.rglob("*"):
            if file_path.is_file():
                files.append(file_path)

        return files


def write_code_changes_to_disk(code_changes: CodeChanges, base_path: str = "/tmp/repoai") -> Path:
    """
    Convenience function to write code changes to disk.

    Args:
        code_changes: CodeChanges to write
        base_path: Base directory for output

    Returns:
        Path: Directory where files were written

    Example:
        output_dir = write_code_changes_to_disk(code_changes)
        print(f"Files at: {output_dir}")
    """
    writer = FileWriter(base_path)
    return writer.write_code_changes(code_changes)
