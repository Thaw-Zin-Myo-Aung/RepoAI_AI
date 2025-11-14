"""
Transformer Fix Agent - Generates targeted fixes for validation errors.

This agent is specifically designed for retry scenarios where validation has failed.
Instead of regenerating all files, it generates ONLY fixes for the broken files.
"""

import time
from pathlib import Path

from repoai.dependencies import TransformerDependencies
from repoai.llm.pydantic_ai_adapter import PydanticAIAdapter
from repoai.models.code_changes import CodeChange, CodeChanges
from repoai.models.validation_result import ValidationResult
from repoai.utils.logger import get_logger

logger = get_logger(__name__)


async def generate_fixes_for_errors(
    validation_result: ValidationResult,
    fix_instructions: str,
    dependencies: TransformerDependencies,
    adapter: PydanticAIAdapter,
) -> list[CodeChange]:
    """
    Generate targeted fixes for specific compilation errors.

    Instead of regenerating all files, this function:
    1. Identifies which files have errors
    2. Reads current file content from disk
    3. Generates fixes for ONLY those files
    4. Returns CodeChange objects for the fixes

    Args:
        validation_result: Validation result with compilation errors
        fix_instructions: LLM-generated fix instructions
        dependencies: Transformer dependencies with repository path
        adapter: PydanticAIAdapter for LLM calls

    Returns:
        List of CodeChange objects with fixes

    Example:
        fixes = await generate_fixes_for_errors(
            validation_result, fix_instructions, deps, adapter
        )
        for fix in fixes:
            await apply_code_change(fix, repo_path, backup_dir)
    """
    from repoai.llm import ModelRole

    logger.info("Generating targeted fixes for validation errors...")

    # Extract files with errors from validation result
    error_files = _extract_error_files(validation_result)
    logger.info(f"Found {len(error_files)} files with errors")

    if not error_files:
        logger.warning("No error files found, returning empty list")
        return []

    # Read current content of error files
    if not dependencies.repository_path:
        raise ValueError("Repository path is required")
    repo_path = Path(dependencies.repository_path)
    file_contents = {}
    for file_path in error_files:
        full_path = repo_path / file_path
        if full_path.exists():
            file_contents[file_path] = full_path.read_text(encoding="utf-8")
        else:
            logger.warning(f"File not found: {file_path}")

    # Build fix prompt
    prompt = _build_fix_prompt(validation_result, fix_instructions, file_contents)

    # Call LLM to generate fixes
    logger.debug("Calling LLM to generate fixes...")
    start_time = time.time()

    # Use CODER role for fix generation
    response_str = await adapter.run_raw_async(
        role=ModelRole.CODER,
        messages=[{"content": prompt}],
        temperature=0.2,  # Low temperature for deterministic fixes
        max_output_tokens=8192,
    )

    # Parse response into CodeChanges
    import json

    response_data = json.loads(response_str)
    code_changes = CodeChanges(**response_data)

    duration_ms = (time.time() - start_time) * 1000
    logger.info(f"LLM generated {len(code_changes.changes)} fixes in {duration_ms:.0f}ms")

    # Return the fixes
    return code_changes.changes


def _extract_error_files(validation_result: ValidationResult) -> set[str]:
    """
    Extract unique file paths that have compilation errors.

    Args:
        validation_result: Validation result with errors

    Returns:
        Set of file paths with errors
    """
    error_files = set()

    # Extract from compilation_errors
    for check in validation_result.checks:
        if check.result.compilation_errors:
            for error_str in check.result.compilation_errors:
                # Parse file path from error string
                # Format: "[ERROR] /path/to/file.java:[line,col] message"
                # or: "src/main/java/File.java:[10,5] error message"
                parts = error_str.split(":")
                if parts:
                    file_part = parts[0]
                    # Remove [ERROR] prefix if present
                    file_part = file_part.replace("[ERROR]", "").strip()
                    # Extract relative path
                    if "src/" in file_part:
                        # Find src/ and take everything after it
                        src_index = file_part.find("src/")
                        if src_index >= 0:
                            relative_path = file_part[src_index:]
                            error_files.add(relative_path)

    return error_files


def _build_fix_prompt(
    validation_result: ValidationResult,
    fix_instructions: str,
    file_contents: dict[str, str],
) -> str:
    """
    Build prompt for LLM to generate fixes.

    Args:
        validation_result: Validation result with errors
        fix_instructions: LLM-generated fix instructions
        file_contents: Current content of files with errors

    Returns:
        Prompt string for LLM
    """
    prompt = f"""You are fixing compilation errors in a Java project.

**FIX INSTRUCTIONS FROM ANALYSIS:**
{fix_instructions}

**COMPILATION ERRORS:**
"""

    # Add compilation errors
    for check in validation_result.checks:
        if check.result.compilation_errors:
            prompt += "\n".join(check.result.compilation_errors[:10])  # Limit to 10 errors

    prompt += "\n\n**CURRENT FILE CONTENTS:**\n"

    # Add current file contents
    for file_path, content in file_contents.items():
        prompt += f"\n### {file_path}\n```java\n{content}\n```\n"

    prompt += """

**TASK:**
Generate fixes for the files above. For each file:
1. Identify the root cause of the error
2. Generate the corrected version
3. Include proper diffs

**OUTPUT:**
Return a CodeChanges object with ONLY the files that need fixes.
Each CodeChange should have:
- file_path: relative path (e.g., "src/main/java/...")
- change_type: "MODIFIED"
- original_content: current content
- modified_content: fixed content
- diff: unified diff
- All other required fields

**IMPORTANT:**
- Fix ONLY the specific errors mentioned
- Don't refactor unrelated code
- Maintain existing structure and style
- Include proper imports
"""

    return prompt
