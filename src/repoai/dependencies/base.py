"""
Base dependency classes for agents.

Each agent has its own dependency type to ensure type safety and
make testing easier through dependency injection.
"""

from dataclasses import dataclass

from repoai.models import JobSpec


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
            repository_url="https://github.com/example/project"
        )

        result = await intake_agent.run(prompt, deps=deps)
    """

    user_id: str
    """Unique identifier for the user making the request"""

    session_id: str
    """Unique identifier for this refactoring session"""

    repository_url: str | None = None
    """Optional GitHub repository URL for context"""

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
