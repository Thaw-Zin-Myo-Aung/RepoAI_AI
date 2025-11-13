"""
Base dependency classes for agents.

Each agent has its own dependency type to ensure type safety and
make testing easier through dependency injection.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repoai.api.models import GitHubCredentials

from repoai.models import (
    CodeChanges,
    JobSpec,
    RefactorPlan,
    ValidationResult,
)
from repoai.orchestrator.models import PipelineState


# Dependencies for the Intake Agent
@dataclass
class IntakeDependencies:
    """
    Dependencies for the Intake Agent.

    The Intake Agent needs minimal dependencies since it only parses
    user prompts. Future enhancements might add repository access for
    context-aware parsing.

    Example:
        deps = IntakeDependencies(
            user_id="user_123",
            session_id="session_abc",
            repository_url="https://github.com/example/project",
            code_context={"src/main/java/.../UserService.java": java_code}
        )

        result = await intake_agent.run(prompt, deps=deps)
    """

    user_id: str
    """Unique identifier for the user making the request"""

    session_id: str
    """Unique identifier for this refactoring session"""

    repository_url: str | None = None
    """Optional GitHub repository URL for context"""

    code_context: dict[str, str] | None = None
    """Optional map of file paths to their code content for context-aware analysis"""

    max_retries: int = 3
    """Maximum number of retries for agent execution"""

    timeout_seconds: int = 60
    """Timeout for agent execution in seconds"""


# Dependencies for the Planner Agent
@dataclass
class PlannerDependencies:
    """
    Dependencies for the Planner Agent.

    The Planner Agent needs the JobSpec and optional repository access for context-aware planning.

    Example:
        deps = PlannerDependencies(
            job_spec=job_spec,
            repository_path="https://github.com/example/project",
            max_retries=2,
            )

            result = await planner_agent.run(prompts, deps=deps)
    """

    job_spec: JobSpec
    """JobSpec from Intake Agent with refactoring requirements"""

    repository_path: str | None = None
    """Optional local path to the repository for analysis"""

    repository_url: str | None = None
    """Optional GitHub repository URL for context"""

    max_retries: int = 3
    """Maximum number of retries for agent execution"""

    timeout_seconds: int = 120
    """Timeout for agent execution in seconds (Planner needs more time)"""

    enable_caching: bool = True
    """Whether to enable caching for repeated queries"""


# Dependencies for the Transformer Agent
@dataclass
class TransformerDependencies:
    """
    Dependencies for the Transformer Agent.

    The Transformer Agent needs the RefactorPlan and repository access
    to generate actual code changes.

    Example:
        deps = TransformerDependencies(
            plan=plan,
            repository_path="/path/to/repo",
            existing_code_context={"Auth.java": "..."},
            write_to_disk=True,
            output_path="/tmp/repoai"
        )

        result = await transformer_agent.run(prompt, deps=deps)
    """

    plan: RefactorPlan
    """RefactorPlan from Planner Agent with steps to execute"""

    repository_path: str | None = None
    """Optional local path to the repository"""

    repository_url: str | None = None
    """Optional GitHub repository URL"""

    existing_code_context: dict[str, str] | None = None
    """Optional map of file paths to their current content"""

    max_retries: int = 3
    """Maximum number of retries for agent execution"""

    timeout_seconds: int = 180
    """Timeout for agent execution in seconds (Transformer needs more time)"""

    enable_code_analysis: bool = True
    """Whether to enable static code analysis during generation"""

    java_version: str = "17"
    """Target Java version for code generation"""

    write_to_disk: bool = True
    """Whether to write generated files to disk (needed for compilation/testing)"""

    output_path: str | None = None
    """Output directory path (defaults to /tmp/repoai if None)"""

    fix_instructions: str | None = None
    """Optional fix instructions for retry scenarios (to fix validation errors)"""


# Dependencies for the Validator Agent
@dataclass
class ValidatorDependencies:
    """
    Dependencies for the Validator Agent.

    The Validator Agent needs the CodeChanges and optional test results
    for comprehensive validation.

    Example:
        deps = ValidatorDependencies(
            code_changes=code_changes,
            run_tests=True,
            test_files_path="/path/to/tests"
        )

        result = await validator_agent.run(prompt, deps=deps)
    """

    code_changes: CodeChanges
    """CodeChanges from Transformer Agent to validate."""

    repository_path: str | None = None
    """Optional local path to the repository."""

    test_files_path: str | None = None
    """Optional path to test files for coverage analysis."""

    run_tests: bool = False
    """Whether to actually run unit tests (require test environment)."""

    run_static_analysis: bool = False
    """Whether to run actual static analysis tools (Checkstyle, PMD)"""

    max_retries: int = 2
    """Maximum number of retries for agent executions."""

    timeout_seconds: int = 120
    """Timeout for agent execution in seconds."""

    min_test_coverage: float = 0.7
    """Minimum required test coverage (0.0-1.0)"""

    strict_mode: bool = False
    """If True, fail on any quality issues."""

    progress_callback: Callable[[str], Awaitable[None]] | None = None
    """Optional async callback to receive real-time build/test output."""


# Dependencies for the PR Narrator Agent
@dataclass
class PRNarratorDependencies:
    """
    Dependencies for the PR Narrator Agent.

    The PR Narrator Agent needs code changes and validation results to create comprehensive PR Descriptions.

    Example:
        deps = PRNarratorDependencies(
            code_changes=code_changes,
            validation_result=validation_result,
            plan_id="plan_123",
            include_migration_guide=True
        )

        result = await pr_narrator_agent.run(prompt, deps=deps)
    """

    code_changes: CodeChanges
    """CodeChanges from Transformer Agent."""

    validation_result: ValidationResult
    """ValidationResult from Validator Agent."""

    plan_id: str
    """Plan ID for reference"""

    repository_url: str | None = None
    """Optional Repository URL for PR links"""

    include_migration_guide: bool = True
    """Whether to include migration guides for breaking changes."""

    max_retries: int = 2
    """Maximum number of retries for agent executions."""

    timeout_seconds: int = 90
    """Timeout for agent execution in seconds."""

    target_audience: str = "technical"
    """Target Audience: 'technical', 'business', or 'mixed'."""


# Dependencies for the Orchestrator Agent
@dataclass
class OrchestratorDependencies:
    """
    Dependencies for the Orchestrator Agent.

    The Orchestrator coordinates all other agents and manages the workflow.

    Example:
        deps = OrchestratorDependencies(
            user_id="developer_001",
            session_id="session_123",
            repository_url="https://github.com/example/repo",
            max_retries=3,
            auto_fix_enabled=True,
            send_message=my_send_function,
            get_user_input=my_input_function
        )

        orchestrator = OrchestratorAgent(deps)
        result = await orchestrator.run(user_prompt)
    """

    user_id: str
    """Unique identifier for the user"""

    session_id: str
    """Unique identifier for this session"""

    pipeline_state: PipelineState | None = None
    """Optional pipeline state for tracking execution progress"""

    repository_url: str | None = None
    """Optional repository URL for context"""

    repository_path: str | None = None
    """Optional local repository path"""

    github_credentials: "GitHubCredentials | None" = None
    """GitHub credentials for commit/push operations (required for git operations stage)"""

    max_retries: int = 3
    """Maximum number of validation retry attempts"""

    auto_fix_enabled: bool = True
    """Whether to automatically attempt to fix validation errors"""

    timeout_seconds: int = 300
    """Total timeout for pipeline execution (5 minutes)"""

    enable_user_interaction: bool = True
    """Whether to ask user for confirmations"""

    enable_progress_updates: bool = True
    """Whether to send real-time progress updates"""

    output_path: str | None = None
    """Path for writing generated files (defaults to /tmp/repoai)"""

    # Chat interface callbacks (optional)
    send_message: Callable[[str], None] | None = None
    """Function to send messages to user (e.g., websocket.send)"""

    get_user_input: Callable[[str], str] | None = None
    """Function to get input from user (e.g., websocket.receive)"""

    # Approval thresholds
    high_risk_threshold: int = 7
    """Risk level (0-10) that requires user approval"""

    low_confidence_threshold: float = 0.7
    """Confidence level (0-1) that requires user confirmation"""

    # Quality requirements
    min_test_coverage: float = 0.7
    """Minimum required test coverage (0.0-1.0)"""

    require_all_checks_pass: bool = False
    """If True, all validation checks must pass (strict mode)"""

    allow_breaking_changes: bool = True
    """Whether to allow refactorings with breaking changes"""
