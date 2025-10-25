"""
Job Specification models - output from INTAKE Agent
Defines what refactoring work needs to be done.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from repoai.explainability.metadata import RefactorMetadata


class JobScope(BaseModel):
    """
    Scope definition for refactoring work

    Defines which files, modules and patterns are included/excluded from the refactoring operation.
    Supports multiple programming languages with language-specific configurations.
    """

    target_files: list[str] = Field(
        description="Specific files to refactor (glob patterns supported, e.g., 'src/**/*.java', 'src/**/*.py')"
    )

    target_packages: list[str] = Field(
        default_factory=list,
        description="Java package names to refactor (e.g., 'com.example.auth', 'com.example.service.*')",
    )

    target_modules: list[str] = Field(
        default_factory=list, description="Python module names to refactor (language-specific)"
    )

    language: str = Field(
        default="java",
        description="Target programming language (e.g., 'java', 'python', 'typescript', 'kotlin')",
    )

    build_system: str | None = Field(
        default=None,
        description="Build system used (e.g., 'maven', 'gradle', 'ant' for Java; 'pip', 'poetry' for Python)",
    )

    exclude_patterns: list[str] = Field(
        default_factory=list,
        description="Patterns to exclude (e.g., '**/*Test.java', 'node_modules/**', '**/target/**')",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "target_files": ["src/main/java/com/example/auth/**/*.java"],
                "target_packages": ["com.example.auth", "com.example.security"],
                "target_modules": [],
                "language": "java",
                "build_system": "maven",
                "exclude_patterns": ["**/*Test.java", "**/target/**", "**/generated/**"],
            }
        }


class JobSpec(BaseModel):
    """
    Complete job specification from INTAKE Agent.

    Represents the parsed and structured user intent for refactoring.
    This is the output of the INTAKE Agent and input to the PLANNER agent.

    Example:
        job_spec = JobSpec(
            job_id="job_abc123",
                intent="add_jwt_authentication",
                scope=JobScope(
                    target_files=["src/auth/**/*.py"],
                    target_modules=["authentication"]
                ),
                requirements=[
                    "Implement JWT token generation",
                    "Add token validation middleware",
                    "Support refresh tokens"
                ],
                constraints=[
                    "Maintain backward compatibility",
                    "No breaking changes to existing API"
                ]
            )
    """

    job_id: str = Field(description="Unique identifier for this refactoring job")

    intent: str = Field(
        description="Primary refactoring intent (eg. 'add_authentication', 'optimize_queries')"
    )

    scope: JobScope = Field(description="Scope of the refactoring work")

    requirements: list[str] = Field(description="specific requirements to fulfill")

    constraints: list[str] = Field(
        default_factory=list, description="Constraints and limitations to respect"
    )

    created_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp when the job spec was created"
    )

    metadadata: RefactorMetadata | None = Field(
        default=None, description="Metadata about how this job spec was created"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job_20250115_103045",
                "intent": "add_jwt_authentication",
                "scope": {
                    "target_files": ["src/auth/**/*.py"],
                    "target_modules": ["authentication"],
                    "exclude_patterns": [],
                },
                "requirements": [
                    "Implement JWT token generation and validation",
                    "Add authentication middleware",
                    "Support token refresh mechanism",
                ],
                "constraints": [
                    "Maintain backward compatibility with session auth",
                    "No breaking changes to user API",
                ],
                "created_at": "2025-01-15T10:30:45",
            }
        }
