#!/usr/bin/env python3
"""Smoke test: orchestrator validation streaming reasoning.

Creates an OrchestratorAgent with a FakeAdapter that streams partial
OrchestratorDecision objects (reasoning text). It also monkeypatches
`run_validator_agent` to return a failing ValidationResult so the
orchestrator invokes its retry-decision logic.

Run: `uv run scripts/smoke_orchestrator_validation_stream.py`
"""

import asyncio
from pathlib import Path

from repoai.dependencies.base import OrchestratorDependencies
from repoai.explainability.confidence import ConfidenceMetrics
from repoai.llm.pydantic_ai_adapter import PydanticAIAdapter
from repoai.models.code_changes import CodeChanges
from repoai.models.refactor_plan import RefactorPlan, RiskAssessment
from repoai.models.validation_result import ValidationCheck, ValidationCheckResult, ValidationResult
from repoai.orchestrator.models import OrchestratorDecision
from repoai.orchestrator.orchestrator_agent import OrchestratorAgent


# Monkeypatch the validator to avoid running real compilation/tests
async def fake_run_validator_agent(
    code_changes, validator_deps, adapter=None
) -> tuple[ValidationResult, None]:
    print("[fake_validator] called")
    # Build a failing ValidationResult
    check = ValidationCheck(
        check_name="maven_compile",
        passed=False,
        issues=[],
        compilation_errors=["src/main/java/com/example/Fixed.java:[10,5] error: something broke"],
    )
    vcr = ValidationCheckResult(name="maven_compile", result=check)
    validation_result = ValidationResult(
        plan_id=(
            validator_deps.code_changes.plan_id
            if validator_deps and validator_deps.code_changes
            else "plan"
        ),
        passed=False,
        compilation_passed=False,
        checks=[vcr],
        test_coverage=0.0,
        confidence=ConfidenceMetrics(
            overall_confidence=0.5, reasoning_quality=0.5, code_safety=0.5, test_coverage=0.0
        ),
    )
    metadata = None
    await asyncio.sleep(0.1)
    return validation_result, metadata


class FakeAdapter(PydanticAIAdapter):
    """Fake adapter that streams partial OrchestratorDecision objects."""

    async def stream_json_async(
        self, role, schema, messages, temperature=0.2, max_output_tokens=4096, use_fallback=True
    ):
        # First partial reasoning
        partial1 = OrchestratorDecision(
            action="pending",
            reasoning="Analyzing compilation errors: missing imports and mismatched constructors...",
            confidence=0.25,
            modifications=None,
            next_step=None,
            estimated_success_probability=0.2,
        )
        yield partial1
        await asyncio.sleep(0.2)

        # Second partial
        partial2 = OrchestratorDecision(
            action="pending",
            reasoning="Detected missing class com.example.Fixed; tests failing due to constructor signature change.",
            confidence=0.4,
            modifications=None,
            next_step=None,
            estimated_success_probability=0.35,
        )
        yield partial2

        await asyncio.sleep(0.2)
        # Final decision: abort (so orchestrator will stop retrying)
        final = OrchestratorDecision(
            action="abort",
            reasoning="Recommendation: abort automatic retry; escalate for human review due to low confidence.",
            confidence=0.45,
            modifications=None,
            next_step=None,
            estimated_success_probability=0.15,
        )
        yield final

    async def run_json_async(
        self, role, schema, messages, temperature=0.2, max_output_tokens=4096, use_fallback=True
    ):
        # Fallback non-streaming return
        return OrchestratorDecision(
            action="abort",
            reasoning="Fallback decision: abort",
            confidence=0.5,
            modifications=None,
            next_step=None,
            estimated_success_probability=0.1,
        )


async def run_smoke() -> None:
    # Simple send_message that prints progress updates
    def send_message(msg):
        print(f"[send_message] {msg}")

    deps = OrchestratorDependencies(
        user_id="smoke_user",
        session_id="smoke_session",
        repository_path=str(Path(".").resolve()),
        repository_url=None,
        send_message=send_message,
        enable_progress_updates=True,
        auto_fix_enabled=True,
    )

    orchestrator = OrchestratorAgent(deps)

    # Replace adapter with fake streaming adapter
    orchestrator.adapter = FakeAdapter()

    # Monkeypatch validator runner to our fake
    import repoai.agents.validator_agent as va

    va.run_validator_agent = fake_run_validator_agent

    # Ensure state has code_changes and plan required by _run_validation_stage
    orchestrator.state.code_changes = CodeChanges(
        plan_id="plan_smoke",
        changes=[],
        files_modified=0,
        files_created=0,
        files_deleted=0,
        lines_added=0,
        lines_removed=0,
        classes_created=0,
    )
    risk = RiskAssessment(
        overall_risk_level=3,
        breaking_changes=False,
        affected_modules=["com.example"],
        compilation_risk=True,
        dependency_conflicts=False,
    )
    orchestrator.state.plan = RefactorPlan(
        plan_id="plan_smoke", job_id="job", steps=[], risk_assessment=risk, estimated_duration="1m"
    )

    # Run only the validation stage (this will invoke our fake validator and then stream LLM reasoning)
    print("Starting validation stage smoke run...")
    await orchestrator._run_validation_stage(skip_tests=False)
    print("Validation stage completed")


if __name__ == "__main__":
    asyncio.run(run_smoke())
