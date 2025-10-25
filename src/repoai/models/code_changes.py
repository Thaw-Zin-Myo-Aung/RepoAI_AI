"""
Code change models - output from Transformer Agent.
Represents the actual code modifications made.
"""

from pydantic import BaseModel, ConfigDict, Field

from repoai.explainability.metadata import RefactorMetadata


class CodeChange(BaseModel):
    """
    Single file change in the refactoring.

    Represents one file that was created, modified, or deleted.
    Includes language-specific details (Java classes, packages, annotations, etc.).
    """

    file_path: str = Field(
        description="Path to the changed file (e.g., 'src/main/java/com/example/Auth.java')"
    )

    change_type: str = Field(
        description="Type of change: 'created', 'modified', 'deleted', 'moved', or 'refactored'"
    )

    class_name: str | None = Field(
        default=None,
        description="Fully qualified class name for Java (e.g., 'com.example.auth.JwtService')",
    )

    package_name: str | None = Field(
        default=None, description="Java package name (e.g., 'com.example.auth')"
    )

    original_content: str | None = Field(
        default=None, description="Original file content (None for created files)"
    )

    modified_content: str | None = Field(
        default=None, description="New file content (None for deleted files)"
    )

    diff: str = Field(description="Unified diff of the changes")

    lines_added: int = Field(ge=0, default=0, description="Number of lines added")

    lines_removed: int = Field(ge=0, default=0, description="Number of lines removed")

    imports_added: list[str] = Field(
        default_factory=list,
        description="New import statements added (e.g., 'import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;')",
    )

    imports_removed: list[str] = Field(
        default_factory=list, description="Import statements removed"
    )

    methods_added: list[str] = Field(
        default_factory=list,
        description="Method signatures added (e.g., 'public String generateToken(User user)')",
    )

    methods_modified: list[str] = Field(
        default_factory=list, description="Method signatures modified"
    )

    annotations_added: list[str] = Field(
        default_factory=list,
        description="Annotations added (e.g., '@Service', '@Autowired', '@RestController', '@Override')",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_path": "src/main/java/com/example/auth/JwtService.java",
                "change_type": "created",
                "class_name": "com.example.auth.JwtService",
                "package_name": "com.example.auth",
                "original_content": None,
                "modified_content": "package com.example.auth;\n\nimport io.jsonwebtoken.Jwts;\n\n@Service\npublic class JwtService {...}",
                "diff": "--- /dev/null\n+++ b/src/main/java/com/example/auth/JwtService.java\n@@ -0,0 +1,45 @@\n+package com.example.auth;...",
                "lines_added": 45,
                "lines_removed": 0,
                "imports_added": [
                    "import io.jsonwebtoken.Jwts",
                    "import org.springframework.stereotype.Service",
                ],
                "imports_removed": [],
                "methods_added": [
                    "public String generateToken(User user)",
                    "public boolean validateToken(String token)",
                ],
                "methods_modified": [],
                "annotations_added": ["@Service"],
            }
        }
    )


class CodeChanges(BaseModel):
    """
    Complete set of code changes from Transformer Agent.

    Represents all code modifications made during refactoring.
    This is the output of the Transformer Agent and input to the Validator Agent.
    Includes language-specific metrics (Java classes, build system changes, etc.).

    Example:
        changes = CodeChanges(
            plan_id="plan_abc123",
            changes=[...],
            files_modified=3,
            classes_created=2,
            dependencies_added=["org.springframework.boot:spring-boot-starter-security:3.2.0"]
        )
    """

    plan_id: str = Field(description="Plan ID these changes implement")

    changes: list[CodeChange] = Field(description="List of file changes")

    files_modified: int = Field(ge=0, description="Total number of files changed")

    files_created: int = Field(ge=0, default=0, description="Number of files created")

    files_deleted: int = Field(ge=0, default=0, description="Number of files deleted")

    lines_added: int = Field(ge=0, description="Total lines added across all files")

    lines_removed: int = Field(ge=0, description="Total lines removed across all files")

    classes_created: int = Field(ge=0, default=0, description="Number of new Java classes created")

    interfaces_created: int = Field(
        ge=0, default=0, description="Number of new Java interfaces created"
    )

    enums_created: int = Field(ge=0, default=0, description="Number of new Java enums created")

    build_config_changes: list[CodeChange] = Field(
        default_factory=list,
        description="Changes to build configuration files (pom.xml, build.gradle, etc.)",
    )

    dependencies_added: list[str] = Field(
        default_factory=list,
        description="Maven/Gradle dependencies added (e.g., 'org.springframework.boot:spring-boot-starter-security:3.2.0')",
    )

    dependencies_removed: list[str] = Field(
        default_factory=list, description="Dependencies removed"
    )

    plugins_added: list[str] = Field(default_factory=list, description="Maven/Gradle plugins added")

    metadata: RefactorMetadata | None = Field(
        default=None, description="Metadata about how these changes were generated"
    )

    @property
    def total_changes(self) -> int:
        """Total number of file changes."""
        return len(self.changes)

    @property
    def net_lines_changed(self) -> int:
        """Net change in lines of code (added - removed)."""
        return self.lines_added - self.lines_removed

    @property
    def total_java_artifacts(self) -> int:
        """Total Java artifacts created (classes + interfaces + enums)."""
        return self.classes_created + self.interfaces_created + self.enums_created

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "plan_id": "plan_20250115_103100",
                "changes": [],
                "files_modified": 3,
                "files_created": 2,
                "files_deleted": 0,
                "lines_added": 150,
                "lines_removed": 25,
                "classes_created": 2,
                "interfaces_created": 1,
                "enums_created": 0,
                "build_config_changes": [],
                "dependencies_added": [
                    "org.springframework.boot:spring-boot-starter-security:3.2.0",
                    "io.jsonwebtoken:jjwt-api:0.12.3",
                ],
                "dependencies_removed": [],
                "plugins_added": [],
            }
        }
    )
