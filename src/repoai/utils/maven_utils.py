"""
Maven utilities for dependency management.

Provides functions to read, parse, and update Maven pom.xml files.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from repoai.utils.logger import get_logger

logger = get_logger(__name__)


def parse_pom_xml(pom_path: Path | str) -> Any:
    """
    Parse a Maven pom.xml file.

    Args:
        pom_path: Path to pom.xml file

    Returns:
        ElementTree object

    Raises:
        FileNotFoundError: If pom.xml doesn't exist
        ET.ParseError: If pom.xml is not valid XML
    """
    pom_path = Path(pom_path)
    if not pom_path.exists():
        raise FileNotFoundError(f"pom.xml not found: {pom_path}")

    tree: Any = ET.parse(pom_path)
    return tree


def get_maven_namespace(root: ET.Element) -> str:
    """
    Extract Maven namespace from root element.

    Args:
        root: Root element of pom.xml

    Returns:
        Namespace string (e.g., "{http://maven.apache.org/POM/4.0.0}")
    """
    # Extract namespace from tag
    if "}" in root.tag:
        return root.tag.split("}")[0] + "}"
    return ""


def get_dependencies(pom_path: Path | str) -> list[dict[str, str]]:
    """
    Extract all dependencies from pom.xml.

    Args:
        pom_path: Path to pom.xml file

    Returns:
        List of dependency dicts with groupId, artifactId, version, scope
    """
    try:
        tree = parse_pom_xml(pom_path)
        root = tree.getroot()
        if root is None:
            return []

        ns = get_maven_namespace(root)

        dependencies = []
        deps_elem = root.find(f"{ns}dependencies")

        if deps_elem is not None:
            for dep in deps_elem.findall(f"{ns}dependency"):
                group_id = dep.find(f"{ns}groupId")
                artifact_id = dep.find(f"{ns}artifactId")
                version = dep.find(f"{ns}version")
                scope = dep.find(f"{ns}scope")

                if group_id is not None and artifact_id is not None:
                    dep_dict: dict[str, str] = {
                        "groupId": group_id.text or "",
                        "artifactId": artifact_id.text or "",
                    }

                    if version is not None and version.text:
                        dep_dict["version"] = version.text

                    if scope is not None and scope.text:
                        dep_dict["scope"] = scope.text

                    dependencies.append(dep_dict)

        return dependencies
    except Exception as e:
        logger.error(f"Failed to get dependencies: {e}")
        return []


def dependency_exists(pom_path: Path | str, group_id: str, artifact_id: str) -> bool:
    """
    Check if a dependency already exists in pom.xml.

    Args:
        pom_path: Path to pom.xml file
        group_id: Maven groupId
        artifact_id: Maven artifactId

    Returns:
        True if dependency exists, False otherwise
    """
    dependencies = get_dependencies(pom_path)
    return any(
        dep["groupId"] == group_id and dep["artifactId"] == artifact_id for dep in dependencies
    )


def add_dependency(
    pom_path: Path | str,
    group_id: str,
    artifact_id: str,
    version: str,
    scope: str | None = None,
) -> bool:
    """
    Add a new dependency to pom.xml.

    Args:
        pom_path: Path to pom.xml file
        group_id: Maven groupId
        artifact_id: Maven artifactId
        version: Dependency version
        scope: Optional scope (compile, test, provided, runtime)

    Returns:
        True if dependency was added successfully, False otherwise
    """
    try:
        # Check if dependency already exists
        if dependency_exists(pom_path, group_id, artifact_id):
            logger.info(f"Dependency {group_id}:{artifact_id} already exists in pom.xml")
            return True

        tree = parse_pom_xml(pom_path)
        root = tree.getroot()
        if root is None:
            logger.error("Failed to get root element from pom.xml")
            return False

        ns = get_maven_namespace(root)

        # Find or create <dependencies> element
        deps_elem = root.find(f"{ns}dependencies")
        if deps_elem is None:
            # Create dependencies element after properties or before build
            properties_elem = root.find(f"{ns}properties")
            if properties_elem is not None:
                # Insert after properties
                idx = list(root).index(properties_elem) + 1
            else:
                # Insert before build or at end
                build_elem = root.find(f"{ns}build")
                if build_elem is not None:
                    idx = list(root).index(build_elem)
                else:
                    idx = len(root)

            deps_elem = ET.Element("dependencies")
            root.insert(idx, deps_elem)

        # Create new dependency element
        dep_elem = ET.SubElement(deps_elem, "dependency")

        # Add groupId
        group_elem = ET.SubElement(dep_elem, "groupId")
        group_elem.text = group_id

        # Add artifactId
        artifact_elem = ET.SubElement(dep_elem, "artifactId")
        artifact_elem.text = artifact_id

        # Add version
        version_elem = ET.SubElement(dep_elem, "version")
        version_elem.text = version

        # Add scope if specified
        if scope:
            scope_elem = ET.SubElement(dep_elem, "scope")
            scope_elem.text = scope

        # Write back to file with proper formatting
        pom_path = Path(pom_path)
        tree.write(pom_path, encoding="UTF-8", xml_declaration=True)

        logger.info(f"✅ Added dependency {group_id}:{artifact_id}:{version} to pom.xml")
        return True

    except Exception as e:
        logger.error(f"Failed to add dependency: {e}")
        return False


def format_pom_xml(pom_path: Path | str) -> None:
    """
    Format pom.xml with proper indentation.

    Args:
        pom_path: Path to pom.xml file
    """
    try:
        pom_path = Path(pom_path)
        content = pom_path.read_text()

        # Basic formatting (this could be enhanced with proper XML formatter)
        lines = content.split("\n")
        formatted_lines = []
        indent_level = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Decrease indent for closing tags
            if stripped.startswith("</"):
                indent_level = max(0, indent_level - 1)

            # Add line with proper indentation
            formatted_lines.append("    " * indent_level + stripped)

            # Increase indent for opening tags (not self-closing)
            if (
                stripped.startswith("<")
                and not stripped.startswith("</")
                and not stripped.endswith("/>")
                and not stripped.startswith("<?")
            ):
                indent_level += 1

        pom_path.write_text("\n".join(formatted_lines) + "\n")

    except Exception as e:
        logger.error(f"Failed to format pom.xml: {e}")


def get_common_dependencies() -> dict[str, dict[str, str]]:
    """
    Return common Maven dependencies with their latest stable versions.

    Returns:
        Dict mapping dependency keys to their maven coordinates
    """
    return {
        # Spring Boot
        "spring-boot-starter": {
            "groupId": "org.springframework.boot",
            "artifactId": "spring-boot-starter",
            "version": "3.2.0",
        },
        "spring-boot-starter-web": {
            "groupId": "org.springframework.boot",
            "artifactId": "spring-boot-starter-web",
            "version": "3.2.0",
        },
        "spring-boot-starter-data-jpa": {
            "groupId": "org.springframework.boot",
            "artifactId": "spring-boot-starter-data-jpa",
            "version": "3.2.0",
        },
        "spring-boot-starter-security": {
            "groupId": "org.springframework.boot",
            "artifactId": "spring-boot-starter-security",
            "version": "3.2.0",
        },
        "spring-boot-starter-test": {
            "groupId": "org.springframework.boot",
            "artifactId": "spring-boot-starter-test",
            "version": "3.2.0",
            "scope": "test",
        },
        # Spring Framework (non-Boot)
        "spring-context": {
            "groupId": "org.springframework",
            "artifactId": "spring-context",
            "version": "6.1.0",
        },
        "spring-web": {
            "groupId": "org.springframework",
            "artifactId": "spring-web",
            "version": "6.1.0",
        },
        # Testing
        "junit-jupiter": {
            "groupId": "org.junit.jupiter",
            "artifactId": "junit-jupiter",
            "version": "5.10.1",
            "scope": "test",
        },
        "mockito-core": {
            "groupId": "org.mockito",
            "artifactId": "mockito-core",
            "version": "5.8.0",
            "scope": "test",
        },
        # Logging
        "slf4j-api": {
            "groupId": "org.slf4j",
            "artifactId": "slf4j-api",
            "version": "2.0.9",
        },
        "logback-classic": {
            "groupId": "ch.qos.logback",
            "artifactId": "logback-classic",
            "version": "1.4.14",
        },
        # Lombok
        "lombok": {
            "groupId": "org.projectlombok",
            "artifactId": "lombok",
            "version": "1.18.30",
            "scope": "provided",
        },
    }
