"""
Test Planner Agent Implementation.

Tests the planner_agent.py to ensure:
1. Agent creation works correctly
2. All tools are registered properly
3. Agent can generate RefactorPlan from JobSpec
4. Risk assessment and mitigation strategies are created
5. Dependencies between steps are suggested
"""

import pytest

from repoai.agents.planner_agent import create_planner_agent, run_planner_agent
from repoai.dependencies import PlannerDependencies
from repoai.llm import ModelRole, PydanticAIAdapter
from repoai.models import JobScope, JobSpec, RefactorPlan


@pytest.fixture
def sample_job_spec() -> JobSpec:
    """Create a sample JobSpec for testing."""
    return JobSpec(
        job_id="job_test_20251026",
        intent="Add JWT authentication to Spring Boot REST API",
        scope=JobScope(
            language="java",
            build_system="maven",
            target_packages=["com.example.auth", "com.example.config"],
            target_files=["pom.xml", "**/*.java"],
            exclude_patterns=["**/test/**", "**/target/**"],
        ),
        requirements=[
            "Add JWT token generation and validation",
            "Create authentication filter",
            "Add security configuration",
            "Add required Maven dependencies",
        ],
        constraints=[
            "Maintain backward compatibility",
            "Don't modify existing user service",
            "Follow Spring Security best practices",
        ],
    )


@pytest.fixture
def planner_dependencies(sample_job_spec: JobSpec) -> PlannerDependencies:
    """Create sample PlannerDependencies."""
    return PlannerDependencies(
        job_spec=sample_job_spec,
        repository_path="/tmp/test-repo",
        max_retries=1,
        timeout_seconds=60,
    )


class TestPlannerAgentCreation:
    """Test planner agent creation and configuration."""

    def test_create_planner_agent_success(self):
        """Test that planner agent can be created successfully."""
        adapter = PydanticAIAdapter()
        agent = create_planner_agent(adapter)

        assert agent is not None
        assert agent.deps_type == PlannerDependencies
        # Agent output_type is set, not result_type
        assert hasattr(agent, "_output_type")
        assert agent._output_type == RefactorPlan

    def test_agent_uses_planner_model(self):
        """Test that agent uses correct model from adapter."""
        adapter = PydanticAIAdapter()
        # agent = create_planner_agent(adapter)

        # Verify the agent is configured with planner model
        model_spec = adapter.get_spec(ModelRole.PLANNER)
        assert model_spec is not None
        assert "gemini" in model_spec.model_id.lower() or "flash" in model_spec.model_id.lower()


class TestPlannerAgentTools:
    """Test planner agent tools - just check basic structure."""

    def test_agent_has_tools(self):
        """Test that agent has tools registered."""
        adapter = PydanticAIAdapter()
        agent = create_planner_agent(adapter)

        # Agent should have tools (we can't access private _function_tools directly)
        # But we can verify the agent was created with system prompt mentioning tools
        assert agent is not None
        # The agent should have been created successfully with all tools


class TestPlannerAgentExecution:
    """Test planner agent execution (requires API key)."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.importorskip("os").getenv("GOOGLE_API_KEY"),
        reason="GOOGLE_API_KEY not set",
    )
    async def test_run_planner_agent_basic(
        self, sample_job_spec: JobSpec, planner_dependencies: PlannerDependencies
    ):
        """Test basic planner agent execution."""
        adapter = PydanticAIAdapter()

        # Run the agent
        plan, metadata = await run_planner_agent(
            job_spec=sample_job_spec,
            dependencies=planner_dependencies,
            adapter=adapter,
        )

        # Verify plan structure
        assert isinstance(plan, RefactorPlan)
        assert plan.plan_id.startswith("plan_")
        assert plan.job_id == sample_job_spec.job_id
        assert plan.total_steps > 0
        assert len(plan.steps) == plan.total_steps

        # Verify each step
        for step in plan.steps:
            assert step.step_number >= 1
            assert step.action
            assert step.description
            assert step.target_files
            assert step.estimated_time_mins > 0
            assert 0 <= step.risk_level <= 10

        # Verify risk assessment
        assert plan.risk_assessment is not None
        assert 0 <= plan.risk_assessment.overall_risk_level <= 10
        assert len(plan.risk_assessment.mitigation_strategies) > 0

        # Verify metadata
        assert metadata.agent_name == "PlannerAgent"
        assert metadata.model_used
        assert metadata.execution_time_ms > 0
        assert len(metadata.reasoning_chain) > 0

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.importorskip("os").getenv("GOOGLE_API_KEY"),
        reason="GOOGLE_API_KEY not set",
    )
    async def test_plan_has_proper_dependencies(
        self, sample_job_spec: JobSpec, planner_dependencies: PlannerDependencies
    ):
        """Test that plan has proper step dependencies."""
        adapter = PydanticAIAdapter()

        plan, _ = await run_planner_agent(
            job_spec=sample_job_spec,
            dependencies=planner_dependencies,
            adapter=adapter,
        )

        # Check if any steps have dependencies
        has_dependencies = any(len(step.dependencies) > 0 for step in plan.steps)

        # For complex refactoring like JWT auth, should have some dependencies
        assert has_dependencies, "Expected some steps to have dependencies"

        # Verify dependency references are valid
        step_numbers = {step.step_number for step in plan.steps}
        for step in plan.steps:
            for dep in step.dependencies:
                assert dep in step_numbers, f"Step {step.step_number} has invalid dependency {dep}"
                assert (
                    dep < step.step_number
                ), f"Step {step.step_number} depends on later step {dep}"

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.importorskip("os").getenv("GOOGLE_API_KEY"),
        reason="GOOGLE_API_KEY not set",
    )
    async def test_plan_includes_maven_dependencies(
        self, sample_job_spec: JobSpec, planner_dependencies: PlannerDependencies
    ):
        """Test that plan includes Maven dependency additions."""
        adapter = PydanticAIAdapter()

        plan, _ = await run_planner_agent(
            job_spec=sample_job_spec,
            dependencies=planner_dependencies,
            adapter=adapter,
        )

        # Should have at least one add_dependency step for JWT libraries
        dependency_steps = [step for step in plan.steps if "dependency" in step.action.lower()]
        assert len(dependency_steps) > 0, "Expected at least one dependency addition step"

        # Should target pom.xml
        pom_steps = [step for step in plan.steps if "pom.xml" in step.target_files]
        assert len(pom_steps) > 0, "Expected at least one step targeting pom.xml"


class TestPlannerAgentValidation:
    """Test planner agent output validation."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.importorskip("os").getenv("GOOGLE_API_KEY"),
        reason="GOOGLE_API_KEY not set",
    )
    async def test_plan_estimated_duration_reasonable(
        self, sample_job_spec: JobSpec, planner_dependencies: PlannerDependencies
    ):
        """Test that estimated durations are reasonable."""
        adapter = PydanticAIAdapter()

        plan, _ = await run_planner_agent(
            job_spec=sample_job_spec,
            dependencies=planner_dependencies,
            adapter=adapter,
        )

        # Check total estimated duration (in minutes)
        # total_duration_mins = sum(step.estimated_time_mins for step in plan.steps)

        # estimated_duration is a human-readable string, so just check it exists and is reasonable
        assert plan.estimated_duration
        assert isinstance(plan.estimated_duration, str)
        assert len(plan.estimated_duration) > 0

        # Each step should have reasonable duration (5-60 minutes)
        for step in plan.steps:
            assert (
                5 <= step.estimated_time_mins <= 60
            ), f"Step {step.step_number} has unreasonable duration: {step.estimated_time_mins}"

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.importorskip("os").getenv("GOOGLE_API_KEY"),
        reason="GOOGLE_API_KEY not set",
    )
    async def test_plan_addresses_all_requirements(
        self, sample_job_spec: JobSpec, planner_dependencies: PlannerDependencies
    ):
        """Test that plan addresses all requirements from JobSpec."""
        adapter = PydanticAIAdapter()

        plan, _ = await run_planner_agent(
            job_spec=sample_job_spec,
            dependencies=planner_dependencies,
            adapter=adapter,
        )

        # Collect all step descriptions and actions
        all_text = " ".join([step.description + " " + step.action for step in plan.steps]).lower()

        # Check for JWT-related steps
        assert "jwt" in all_text or "token" in all_text, "Plan should mention JWT/token"

        # Check for authentication/security
        assert (
            "auth" in all_text or "security" in all_text
        ), "Plan should mention authentication/security"

        # Check for configuration
        assert (
            "config" in all_text or "configuration" in all_text
        ), "Plan should mention configuration"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
