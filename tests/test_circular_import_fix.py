"""Test to verify circular import is fixed."""


def test_import_agents():
    """Verify that importing agents doesn't cause circular import."""
    from repoai.agents.intake_agent import run_intake_agent
    from repoai.agents.planner_agent import run_planner_agent
    from repoai.agents.transformer_agent import run_transformer_agent
    from repoai.agents.validator_agent import run_validator_agent

    # If we get here, circular import is fixed
    assert run_intake_agent is not None
    assert run_planner_agent is not None
    assert run_transformer_agent is not None
    assert run_validator_agent is not None


def test_import_dependencies():
    """Verify that importing dependencies works."""
    from repoai.dependencies.base import (
        IntakeDependencies,
        PlannerDependencies,
        TransformerDependencies,
        ValidatorDependencies,
    )

    assert IntakeDependencies is not None
    assert PlannerDependencies is not None
    assert TransformerDependencies is not None
    assert ValidatorDependencies is not None


def test_import_orchestrator():
    """Verify that importing orchestrator works."""
    from repoai.orchestrator.chat_orchestrator import ChatOrchestrator
    from repoai.orchestrator.orchestrator_agent import OrchestratorAgent

    assert ChatOrchestrator is not None
    assert OrchestratorAgent is not None
