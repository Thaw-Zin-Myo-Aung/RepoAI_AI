"""
PR description models - output from PR Narrator Agent.
Represents documentation for the refactoring changes.
"""

from pydantic import BaseModel, ConfigDict, Field

from repoai.explainability.metadata import RefactorMetadata


class FileChange(BaseModel):
    """
    Description of changes made to a single file.

    Gemini-compatible structure (no dict fields).
    """

    file_path: str = Field(description="Path to the changed file")
    description: str = Field(description="Description of changes made to this file")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_path": "src/auth/jwt_utils.py",
                "description": "Created JWT utility module with token generation and validation",
            }
        }
    )


class PRDescription(BaseModel):
    """
    Pull request description from PR Narrator Agent.

    Human-readable documentation of the refactoring changes.
    This is the output of the PR Narrator Agent.

    Example:
        pr_desc = PRDescription(
            plan_id="plan_abc123",
            title="Add JWT Authentication",
            summary="Implemented JWT-based authentication...",
            changes_by_file=[
                FileChange(
                    file_path="src/auth/jwt_utils.py",
                    description="Created JWT utility functions"
                ),
                FileChange(
                    file_path="src/middleware/auth.py",
                    description="Added authentication middleware"
                )
            ],
            testing_notes="All unit tests passing, added 12 new tests"
        )
    """

    plan_id: str = Field(description="Plan ID this PR implements")

    title: str = Field(description="PR title (concise summary)")

    summary: str = Field(description="Detailed summary of the changes")

    changes_by_file: list[FileChange] = Field(
        default_factory=list,
        description="List of file changes with descriptions (Gemini-compatible)",
    )

    breaking_changes: list[str] = Field(
        default_factory=list, description="List of breaking changes (if any)"
    )

    migration_guide: str | None = Field(
        default=None, description="Migration guide for users (if needed)"
    )

    testing_notes: str = Field(description="Description of testing performed")

    metadata: RefactorMetadata | None = Field(
        default=None, description="Metadata about how this PR description was generated"
    )

    @property
    def has_breaking_changes(self) -> bool:
        """Whether this PR includes breaking changes."""
        return len(self.breaking_changes) > 0

    def to_markdown(self) -> str:
        """Generate markdown-formatted PR description."""
        lines = [
            f"# {self.title}",
            "",
            "## Summary",
            self.summary,
            "",
            "## Changes",
        ]

        for change in self.changes_by_file:
            lines.append(f"- **{change.file_path}**: {change.description}")

        if self.breaking_changes:
            lines.extend(
                [
                    "",
                    "## ⚠️ Breaking Changes",
                ]
            )
            for breaking_change in self.breaking_changes:
                lines.append(f"- {breaking_change}")

        if self.migration_guide:
            lines.extend(
                [
                    "",
                    "## Migration Guide",
                    self.migration_guide,
                ]
            )

        lines.extend(
            [
                "",
                "## Testing",
                self.testing_notes,
            ]
        )

        return "\n".join(lines)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "plan_id": "plan_20250115_103100",
                "title": "feat: Add JWT authentication to user service",
                "summary": "Implemented JWT-based authentication for improved security and scalability",
                "changes_by_file": [
                    {
                        "file_path": "src/auth/jwt_utils.py",
                        "description": "Created JWT utility module with token generation and validation",
                    },
                    {
                        "file_path": "src/middleware/auth.py",
                        "description": "Added JWT authentication middleware",
                    },
                ],
                "breaking_changes": [],
                "migration_guide": None,
                "testing_notes": "All existing tests pass. Added 12 new unit tests for JWT functionality.",
            }
        }
    )
