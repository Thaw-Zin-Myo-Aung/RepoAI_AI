"""
PR description models - output from PR Narrator Agent.
Represents documentation for the refactoring changes.
"""

from pydantic import BaseModel, Field

from repoai.explainability.metadata import RefactorMetadata


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
            changes_by_file={
                "src/auth/jwt_utils.py": "Created JWT utility functions",
                "src/middleware/auth.py": "Added authentication middleware"
            },
            testing_notes="All unit tests passing, added 12 new tests"
        )
    """

    plan_id: str = Field(description="Plan ID this PR implements")

    title: str = Field(description="PR title (concise summary)")

    summary: str = Field(description="Detailed summary of the changes")

    changes_by_file: dict[str, str] = Field(
        description="Map of file path to description of changes"
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

        for file_path, description in self.changes_by_file.items():
            lines.append(f"- **{file_path}**: {description}")

        if self.breaking_changes:
            lines.extend(
                [
                    "",
                    "## ⚠️ Breaking Changes",
                ]
            )
            for change in self.breaking_changes:
                lines.append(f"- {change}")

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

    class Config:
        json_schema_extra = {
            "example": {
                "plan_id": "plan_20250115_103100",
                "title": "feat: Add JWT authentication to user service",
                "summary": "Implemented JWT-based authentication for improved security and scalability",
                "changes_by_file": {
                    "src/auth/jwt_utils.py": "Created JWT utility module with token generation and validation",
                    "src/middleware/auth.py": "Added JWT authentication middleware",
                },
                "breaking_changes": [],
                "migration_guide": None,
                "testing_notes": "All existing tests pass. Added 12 new unit tests for JWT functionality.",
            }
        }
