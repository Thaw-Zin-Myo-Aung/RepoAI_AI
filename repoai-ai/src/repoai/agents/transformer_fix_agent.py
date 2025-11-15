"""Cleaned Transformer Fix Agent implementation (AST-excerpting, conservative budgets)."""

from pathlib import Path

from repoai.dependencies import TransformerDependencies
from repoai.llm.pydantic_ai_adapter import PydanticAIAdapter
from repoai.models.code_changes import CodeChange, CodeChanges
from repoai.models.validation_result import ValidationResult
from repoai.parsers.java_ast_parser import extract_relevant_context
from repoai.utils.logger import get_logger

logger = get_logger(__name__)


async def generate_fixes_for_errors(
    validation_result: ValidationResult,
    fix_instructions: str,
    dependencies: TransformerDependencies,
    adapter: PydanticAIAdapter,
) -> list[CodeChange]:
    from repoai.llm import ModelRole

    logger.info("Generating targeted fixes for validation errors...")

    error_files = _extract_error_files(validation_result)
    if not error_files:
        logger.warning("No error files found, returning empty list")
        return []

    if not dependencies.repository_path:
        raise ValueError("Repository path is required")
    repo_path = Path(dependencies.repository_path)

    file_contents: dict[str, str] = {}
    for file_path in error_files:
        full_path = repo_path / file_path
        if full_path.exists():
            file_contents[file_path] = full_path.read_text(encoding="utf-8")
        else:
            logger.warning(f"File not found: {file_path}")

    # AST-based excerpting for large files
    processed_file_contents: dict[str, str] = {}
    excerpt_line_threshold = 200
    excerpt_char_threshold = 8000
    intent = getattr(getattr(dependencies, "plan", None), "job_id", "fix")
    intent = intent.split("_")[-1] if isinstance(intent, str) else "fix"

    for fp, content in file_contents.items():
        try:
            if (
                len(content) > excerpt_char_threshold
                or len(content.splitlines()) > excerpt_line_threshold
            ):
                try:
                    excerpt = extract_relevant_context(content, intent)
                    processed_file_contents[fp] = (
                        f"// EXCERPTED CONTEXT for {fp} (excerpted - full file available on disk)\n"
                        + excerpt
                    )
                except Exception as e:
                    logger.warning(f"AST excerpt failed for {fp}: {e}")
                    processed_file_contents[fp] = content
            else:
                processed_file_contents[fp] = content
        except Exception:
            processed_file_contents[fp] = content

    prompt = _build_fix_prompt(validation_result, fix_instructions, processed_file_contents)

    total_chars = sum(len(c) for c in processed_file_contents.values())
    max_single_call_chars = 12_000

    aggregated_changes: list[CodeChange] = []
    if total_chars > max_single_call_chars or len(processed_file_contents) > 3:
        # per-file generation
        for file_path, content in processed_file_contents.items():
            per_prompt = _build_fix_prompt(
                validation_result, fix_instructions, {file_path: content}
            )
            try:
                per_code_changes: CodeChanges = await adapter.run_json_async(
                    role=ModelRole.CODER,
                    schema=CodeChanges,
                    messages=[{"content": per_prompt}],
                    temperature=0.15,
                    max_output_tokens=8000,
                    use_fallback=True,
                )
                aggregated_changes.extend(per_code_changes.changes)
            except Exception as e:
                logger.error(f"Per-file generation failed for {file_path}: {e}")
                continue
        return aggregated_changes

    try:
        code_changes: CodeChanges = await adapter.run_json_async(
            role=ModelRole.CODER,
            schema=CodeChanges,
            messages=[{"content": prompt}],
            temperature=0.2,
            max_output_tokens=16000,
            use_fallback=True,
        )
        return code_changes.changes
    except Exception as e:
        logger.error(f"Single-call fix generation failed: {e}")
        # fallback to per-file
        for file_path, content in processed_file_contents.items():
            per_prompt = _build_fix_prompt(
                validation_result, fix_instructions, {file_path: content}
            )
            try:
                fallback_code_changes: CodeChanges = await adapter.run_json_async(
                    role=ModelRole.CODER,
                    schema=CodeChanges,
                    messages=[{"content": per_prompt}],
                    temperature=0.2,
                    max_output_tokens=8000,
                    use_fallback=True,
                )
                aggregated_changes.extend(fallback_code_changes.changes)
            except Exception as ex:
                logger.error(f"Fallback per-file generation failed for {file_path}: {ex}")
                continue
        return aggregated_changes


def _extract_error_files(validation_result: ValidationResult) -> set[str]:
    error_files = set()
    for check in validation_result.checks:
        if check.result.compilation_errors:
            for error_str in check.result.compilation_errors:
                parts = error_str.split(":")
                if parts:
                    file_part = parts[0].replace("[ERROR]", "").strip()
                    if "src/" in file_part:
                        src_index = file_part.find("src/")
                        if src_index >= 0:
                            error_files.add(file_part[src_index:])
    return error_files


def _build_fix_prompt(
    validation_result: ValidationResult,
    fix_instructions: str,
    file_contents: dict[str, str],
) -> str:
    parts = [
        "You are fixing compilation errors in a Java project.",
        "\n**FIX INSTRUCTIONS FROM ANALYSIS:**\n",
        fix_instructions,
        "\n**COMPILATION ERRORS:**\n",
    ]
    for check in validation_result.checks:
        if check.result.compilation_errors:
            parts.append("\n".join(check.result.compilation_errors[:10]))
    parts.append("\n\n**CURRENT FILE CONTENTS (excerpted when large):**\n")
    for fp, content in file_contents.items():
        parts.append(f"\n### {fp}\n```java\n{content}\n```\n")
    parts.append(
        "\n**TASK:**\nFor each file above: identify the root cause, provide corrected file content, and include a unified diff.\n"
    )
    parts.append(
        "\nSpecial rules: prefer updating call sites/tests when signatures changed; avoid unrelated refactors.\n"
    )
    parts.append("\nReturn a JSON CodeChanges structure containing only fixed files.\n")
    return "\n".join(parts)
