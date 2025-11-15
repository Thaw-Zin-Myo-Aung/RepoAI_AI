#!/usr/bin/env python3
"""Smoke test for transformer batching and token-limit fallback.

This script monkeypatches `create_transformer_agent` to a fake agent that
produces deterministic `CodeChanges` or simulates a token limit error when
the prompt contains multiple steps (3+). It then calls
`run_transformer_agent` with different `batch_size` values to exercise
the adaptive fallback logic.
"""

import asyncio
import time
from typing import Any

from repoai.agents import transformer_agent as ta
from repoai.dependencies.base import TransformerDependencies
from repoai.models.code_changes import CodeChange, CodeChanges
from repoai.models.refactor_plan import RefactorPlan, RefactorStep, RiskAssessment


class FakeAgent:
    def __init__(self):
        pass

    class Result:
        def __init__(self, output: CodeChanges):
            self.output = output

    async def run(self, prompt: str, deps: Any = None, usage_limits: Any = None, **kwargs) -> Any:
        # Count number of steps by counting occurrences of 'Step Number:'
        count = prompt.count("Step Number:")
        # Simulate token limit if batch contains 3 or more steps
        if count >= 3 and "batch" in prompt.lower():
            raise RuntimeError("token limit exceeded for prompt")

        # Create synthetic CodeChanges: one file per step
        changes = []
        for i in range(max(1, count)):
            file_path = f"src/generated/Generated{i+1}.java"
            cc = CodeChange(
                file_path=file_path,
                change_type="created",
                class_name=f"com.example.Generated{i+1}",
                package_name="com.example",
                original_content=None,
                modified_content=f"package com.example;\n\npublic class Generated{i+1} {{}}\n",
                diff=f"--- /dev/null\n+++ b/{file_path}\n@@ -0,0 +1,3 @@\n+package com.example;\n+public class Generated{i+1} {{}}\n",
                lines_added=3,
                lines_removed=0,
            )
            changes.append(cc)

        code_changes = CodeChanges(
            plan_id=(deps.plan.plan_id if deps and getattr(deps, "plan", None) else "test"),
            changes=changes,
            files_modified=0,
            files_created=len(changes),
            files_deleted=0,
            lines_added=sum(c.lines_added for c in changes),
            lines_removed=0,
            classes_created=len(changes),
        )

        return FakeAgent.Result(code_changes)


def monkeypatch_create_agent() -> None:
    # Replace the real create_transformer_agent with a stub that returns FakeAgent
    ta.create_transformer_agent = lambda adapter: FakeAgent()  # type: ignore[assignment]


async def run_test(batch_size: int) -> None:
    print(f"\n=== Running test with batch_size={batch_size} ===")

    # Build a small RefactorPlan with 4 steps
    steps = []
    for i in range(1, 5):
        steps.append(
            RefactorStep(
                step_number=i,
                action="create_class",
                target_files=[f"src/main/java/com/example/Generated{i}.java"],
                target_classes=[f"com.example.Generated{i}"],
                description=f"Create Generated{i} class",
            )
        )

    risk = RiskAssessment(overall_risk_level=1, affected_modules=[])

    plan = RefactorPlan(
        plan_id="plan_smoke_1",
        job_id="job_smoke_1",
        steps=steps,
        risk_assessment=risk,
        estimated_duration="5 minutes",
    )

    deps = TransformerDependencies(plan=plan, write_to_disk=False)

    # Call run_transformer_agent and measure time
    start = time.time()
    try:
        code_changes, metadata = await ta.run_transformer_agent(plan, deps, batch_size=batch_size)
        elapsed = (time.time() - start) * 1000
        print(f"Success: generated {len(code_changes.changes)} changes in {elapsed:.0f}ms")
        for c in code_changes.changes:
            print(f" - {c.file_path} (+{c.lines_added})")
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        print(f"Failed (batch_size={batch_size}) after {elapsed:.0f}ms: {e}")


def main() -> None:
    monkeypatch_create_agent()

    for bs in [1, 2, 4]:
        asyncio.run(run_test(bs))


if __name__ == "__main__":
    main()
