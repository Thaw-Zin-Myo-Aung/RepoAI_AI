# RepoAI — Module Reference

This file is a compact reference mapping key modules, classes, and functions in the `RepoAI_AI` service to their responsibilities and how to use them. Use this as a quick lookup so you can tell me what to modify and I know where to implement changes.

---

## Top-level package

- `src/repoai` — main Python package for the AI service and agent orchestration.

## Orchestration

- `src/repoai/orchestrator/orchestrator_agent.py`
  - Key classes / functions:
    - `OrchestratorAgent(deps)` — main orchestrator class. Call `.run(user_prompt, mode)` to execute full pipeline.
    - Internal pipeline stages: `_run_intake_stage`, `_run_planning_stage`, `_run_transformation_stage_streaming`, `_run_validation_stage`, `_run_narration_stage`, `_run_git_operations_stage`.
  - Responsibilities: coordinate agents, stream progress via `deps.send_message`/progress callbacks, clone repo if needed, apply code changes, handle retries and interactive confirmations.
  - Usage example: instantiate with an `OrchestratorDependencies` object and call `await orchestrator.run("Refactor X")`.

- `src/repoai/orchestrator/chat_orchestrator.py`
  - Provides interactive/human-in-the-loop extension of `OrchestratorAgent` that requests confirmations during plan, validation, and push stages.

## Agents

- `src/repoai/agents/intake_agent.py`
  - Role: parse raw user prompt into a structured `JobSpec` (intent, scope, constraints).
  - Output: `JobSpec` model used by planner.

- `src/repoai/agents/planner_agent.py`
  - Role: generate `RefactorPlan` (steps, risk estimates, assignments).
  - Output: `RefactorPlan` model consumed by `Transformer` and `Orchestrator`.

- `src/repoai/agents/transformer_agent.py` and `src/repoai/agents/transformer_fix_agent.py`
  - Role: produce concrete `CodeChanges` (create/modify/delete files, diffs). Supports streaming generation.
  - Output: `CodeChanges` model (see `src/repoai/models/code_changes.py`).
  - Usage: The orchestrator calls the transformer stage; transformers expose agent APIs to run prompts and return `CodeChanges`.

- `src/repoai/agents/validator_agent.py` (detailed)
  - Key API functions / tools:
    - `create_validator_agent(adapter)` — constructs a Pydantic-AI `Agent` configured for validation tasks.
    - `run_validator_agent(code_changes, dependencies, adapter=None)` — convenience coroutine that runs the validator and returns `(ValidationResult, RefactorMetadata)`.
    - Agent tools (callable from the agent runtime):
      - `check_compilation(ctx)` — detects build tool and invokes real compilation via `compile_java_project`.
      - `run_unit_tests(ctx, test_pattern=None)` — runs JUnit tests via `run_java_tests` and returns structured `TestResult` data.
      - `check_code_quality(ctx, code)` — heuristic static checks (method length, naming, magic numbers).
      - `check_spring_conventions(ctx, code)` — Spring-specific convention checks (@Autowired, @Service, controllers).
      - `estimate_test_coverage(ctx, production_code, test_code="")` — heuristic coverage estimate.
      - `check_security_issues(ctx, code)` — simple heuristics for SQL injection, hard-coded credentials, weak crypto.
  - Responsibilities: run real compilation/tests (via subprocess), perform static & heuristic checks, assemble `ValidationResult` (`src/repoai/models/validation_result.py`).
  - Typical usage:
    - If you already have `CodeChanges` and a `ValidatorDependencies` object: `validation_result, metadata = await run_validator_agent(code_changes, deps)`.

- `src/repoai/agents/pr_narrator_agent.py`
  - Role: summarize changes and validation results into a PR description.

- `src/repoai/agents/gemini_agent.py` and `src/repoai/llm` package
  - Role: model adapters and routing. `PydanticAIAdapter` provides `get_model`, `get_model_settings`, and schema specs used by agents.

## Utilities

- `src/repoai/utils/java_build_utils.py` (detailed)
  - Key functions / dataclasses:
    - `BuildToolInfo` — dataclass describing maven/gradle and wrapper presence.
    - `detect_build_tool(repo_path)` — detects `pom.xml`/`build.gradle` and wrapper scripts.
    - `compile_java_project(repo_path, build_tool_info=None, clean=False, skip_tests=True, progress_callback=None)` — runs `mvn`/`gradle` compile; returns `CompilationResult` (see module).
    - `run_java_tests(repo_path, build_tool_info=None, test_pattern=None, progress_callback=None)` — runs `mvn test` / `gradle test`; returns `TestResult` with parsed failures.
    - Parsing helpers: `_parse_build_output`, `_parse_maven_output`, `_parse_gradle_output`, `_parse_test_output`.
  - Notes: These functions call external build tools via subprocess and support streaming output through an async `progress_callback` that the orchestrator typically provides.

- `src/repoai/utils/git_utils.py`
  - Role: clone repositories, create branches, commit, push. `clone_repository` is used by `OrchestratorAgent` when `deps.repository_url` is set.

- `src/repoai/utils/file_operations.py`
  - Key functions: `apply_code_change`, `create_backup_directory` — used to write generated code to the working tree and keep backups for rollback.

- `src/repoai/utils/file_writer.py`
  - Role: safe file writes and helpers for atomic operations.

- `src/repoai/utils/logger.py`
  - Wraps logging configuration used across modules. Use `get_logger(__name__)` in modules.

## Models (domain objects)

- `src/repoai/models/code_changes.py` — `CodeChanges`, `CodeChange` models describing file operations (created/modified/deleted), lines added/removed, plan id.
- `src/repoai/models/refactor_plan.py` — `RefactorPlan` and step definitions.
- `src/repoai/models/job_spec.py` — `JobSpec` produced by Intake Agent.
- `src/repoai/models/validation_result.py` — `ValidationResult`, `ValidationCheck`, `JUnitTestResults`, used to represent validator outputs.

## Explainability & metadata

- `src/repoai/explainability` — types for `RefactorMetadata` and `ConfidenceMetrics` attached to validation results for traceability.

## API & CLI

- `src/repoai/cli.py` — simple Typer CLI with `repoai` console entry (defined in `pyproject.toml`).
- `src/repoai/api` — (if present) contains FastAPI endpoints and SSE streaming handlers (used by backend integration). The orchestrator uses `deps.send_message` to send `ProgressUpdate` objects to the API layer for SSE clients.

## Tests

- `tests/` — unit and integration tests that exercise utilities, agents, and orchestrator flows. Run with `pytest` in the virtualenv.

---

## Quick lookup — common tasks and where to change them

- To change how Java compilation is invoked (timeouts, flags): edit `src/repoai/utils/java_build_utils.py` (`compile_java_project`).
- To change validation heuristics (naming, magic numbers): edit `src/repoai/agents/validator_agent.py` (functions `check_code_quality`, `check_spring_conventions`, `check_security_issues`).
- To change how files are written/applied: edit `src/repoai/utils/file_operations.py` and `src/repoai/utils/file_writer.py`.
- To modify orchestration flow (stage ordering, retries, confirmations): edit `src/repoai/orchestrator/orchestrator_agent.py` and `src/repoai/orchestrator/chat_orchestrator.py`.
- To change model routing or timeouts: edit `src/repoai/llm/*` and the adapter configuration (where `PydanticAIAdapter` provides `get_model` / `get_spec`).

---

If you'd like, I can:
- generate a per-file index (names + 1-line description) for every file under `src/repoai`;
- run the test suite in the venv to verify current status before making changes; or
- implement a small change now (tell me which module and what to change).

Reference: created automatically by assistant to map implementation responsibilities.
