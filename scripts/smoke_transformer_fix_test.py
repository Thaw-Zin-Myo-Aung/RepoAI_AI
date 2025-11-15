#!/usr/bin/env python3
"""Smoke test for Transformer Fix Agent using structured JSON path.

This script simulates a ValidationResult with compilation errors and provides a
FakeAdapter that implements `run_json_async` returning a CodeChanges object.
It then calls `generate_fixes_for_errors` to verify the structured path works.
"""

import asyncio

from repoai.agents.transformer_fix_agent import generate_fixes_for_errors
from repoai.dependencies.base import TransformerDependencies
from repoai.explainability.confidence import ConfidenceMetrics
from repoai.llm.pydantic_ai_adapter import PydanticAIAdapter
from repoai.models.code_changes import CodeChange, CodeChanges
from repoai.models.refactor_plan import RefactorPlan, RefactorStep, RiskAssessment
from repoai.models.validation_result import ValidationCheck, ValidationCheckResult, ValidationResult


class FakeAdapter(PydanticAIAdapter):
    async def run_json_async(
        self, role, schema, messages, temperature=0.2, max_output_tokens=8192, use_fallback=True
    ):
        # Return a CodeChanges instance matching the expected schema
        changes = [
            CodeChange(
                file_path="src/main/java/com/example/Fixed.java",
                change_type="modified",
                class_name="com.example.Fixed",
                package_name="com.example",
                original_content="package com.example;\n\npublic class Fixed { int x; }\n",
                modified_content="package com.example;\n\npublic class Fixed { int x = 0; }\n",
                diff="--- a/src/main/java/com/example/Fixed.java\n+++ b/src/main/java/com/example/Fixed.java\n@@ -1,3 +1,3 @@\n-package com.example;\n-\n-public class Fixed { int x; }\n+package com.example;\n+\n+public class Fixed { int x = 0; }\n",
                lines_added=1,
                lines_removed=0,
            )
        ]

        return CodeChanges(
            plan_id="plan_smoke_fix",
            changes=changes,
            files_modified=1,
            files_created=0,
            files_deleted=0,
            lines_added=1,
            lines_removed=0,
            classes_created=0,
        )


async def run_smoke() -> None:
    # Build a fake RefactorPlan (required by TransformerDependencies)
    steps = [
        RefactorStep(
            step_number=1,
            action="modify_class",
            target_files=["src/main/java/com/example/Fixed.java"],
            target_classes=["com.example.Fixed"],
            description="Fix initialization",
        )
    ]
    risk = RiskAssessment(
        overall_risk_level=3, affected_modules=["com.example"], test_coverage_required=0.5
    )
    plan = RefactorPlan(
        plan_id="plan_smoke_fix",
        job_id="job",
        steps=steps,
        risk_assessment=risk,
        estimated_duration="5 minutes",
    )

    # Build a fake ValidationResult indicating a compilation error in a file
    check = ValidationCheck(
        check_name="maven_compile",
        passed=False,
        issues=[],
        compilation_errors=["src/main/java/com/example/Fixed.java:[10,5] error: something broke"],
    )
    vcr = ValidationCheckResult(name="maven_compile", result=check)
    validation_result = ValidationResult(
        plan_id="plan_smoke_fix",
        passed=False,
        compilation_passed=False,
        checks=[vcr],
        test_coverage=0.0,
        confidence=ConfidenceMetrics(
            overall_confidence=0.5, reasoning_quality=0.5, code_safety=0.5, test_coverage=0.0
        ),
    )

    # Fix instructions (as if produced by planner)
    fix_instructions = "1. Fix null pointer in Fixed.java by initializing x to 0"

    deps = TransformerDependencies(plan=plan, repository_path=".", write_to_disk=False)

    # Call the generator with the fake adapter
    fixes = await generate_fixes_for_errors(
        validation_result, fix_instructions, deps, FakeAdapter()
    )
    print(f"Generated {len(fixes)} fixes")
    for f in fixes:
        print(f" - {f.file_path} (+{f.lines_added}/-{f.lines_removed})")


if __name__ == "__main__":
    asyncio.run(run_smoke())
