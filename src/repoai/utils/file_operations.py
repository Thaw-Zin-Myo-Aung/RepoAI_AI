"""
File operations for applying code changes to disk.

This module provides utilities for:
1. Applying code changes to cloned repositories
2. Backing up files before modification
3. Restoring from backups on errors
4. Validating file paths and permissions
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repoai.models import CodeChange, CodeChanges

from repoai.utils.logger import get_logger

logger = get_logger(__name__)


class FileOperationError(Exception):
    """Raised when file operations fail."""

    pass


async def apply_code_change(
    change: CodeChange,
    repo_path: str | Path,
    backup_dir: str | Path | None = None,
) -> Path:
    """
    Apply a single code change to the repository.

    Args:
        change: CodeChange to apply (CREATE, MODIFY, or DELETE)
        repo_path: Root path of the cloned repository
        backup_dir: Optional backup directory for modified/deleted files

    Returns:
        Path to the modified file

    Raises:
        FileOperationError: If the operation fails

    Example:
        change = CodeChange(
            file_path="src/main/java/com/example/Auth.java",
            change_type="CREATE",
            new_content="package com.example;\\n..."
        )
        file_path = await apply_code_change(change, "/tmp/repoai_xyz123")
    """
    repo_path = Path(repo_path)
    file_path = repo_path / change.file_path

    logger.debug(f"Applying {change.change_type} to {change.file_path}")

    try:
        change_type_lower = change.change_type.lower()

        if change_type_lower in ("create", "created"):
            return await _create_file(file_path, change.modified_content)

        elif change_type_lower in ("modify", "modified", "refactored", "moved"):
            if backup_dir:
                await _backup_file(file_path, Path(backup_dir), repo_path)
            return await _modify_file(file_path, change.modified_content)

        elif change_type_lower in ("delete", "deleted"):
            if backup_dir:
                await _backup_file(file_path, Path(backup_dir), repo_path)
            return await _delete_file(file_path)

        else:
            raise FileOperationError(f"Unknown change type: {change.change_type}")

    except Exception as e:
        logger.error(f"Failed to apply change to {change.file_path}: {e}")
        raise FileOperationError(
            f"Failed to apply {change.change_type} to {change.file_path}: {e}"
        ) from e


async def apply_code_changes(
    changes: CodeChanges,
    repo_path: str | Path,
    create_backup: bool = True,
) -> tuple[list[Path], Path | None]:
    """
    Apply multiple code changes to the repository.

    Args:
        changes: CodeChanges object with list of changes
        repo_path: Root path of the cloned repository
        create_backup: Whether to create backup before applying changes

    Returns:
        Tuple of (list of modified file paths, backup directory path)

    Raises:
        FileOperationError: If any operation fails

    Example:
        modified_files, backup_dir = await apply_code_changes(
            code_changes,
            "/tmp/repoai_xyz123",
            create_backup=True
        )
    """
    repo_path = Path(repo_path)

    if not repo_path.exists():
        raise FileOperationError(f"Repository path does not exist: {repo_path}")

    # Create backup directory if requested
    backup_dir = None
    if create_backup:
        backup_dir = await create_backup_directory(repo_path)
        logger.info(f"Created backup directory: {backup_dir}")

    modified_files: list[Path] = []
    failed_changes: list[tuple[CodeChange, Exception]] = []

    logger.info(f"Applying {len(changes.changes)} code changes to {repo_path}")

    for change in changes.changes:
        try:
            file_path = await apply_code_change(change, repo_path, backup_dir)
            modified_files.append(file_path)
            logger.debug(f"✓ Applied {change.change_type} to {change.file_path}")

        except Exception as e:
            logger.error(f"✗ Failed to apply change to {change.file_path}: {e}")
            failed_changes.append((change, e))

    if failed_changes:
        error_msg = f"Failed to apply {len(failed_changes)} changes:\n"
        for change, error in failed_changes[:5]:  # Limit to first 5 errors
            error_msg += f"  - {change.file_path}: {error}\n"

        if len(failed_changes) > 5:
            error_msg += f"  ... and {len(failed_changes) - 5} more"

        raise FileOperationError(error_msg)

    logger.info(f"Successfully applied {len(modified_files)} changes")
    return modified_files, backup_dir


async def _create_file(file_path: Path, content: str | None) -> Path:
    """
    Create a new file with content.

    Args:
        file_path: Path to the new file
        content: File content (can be None or empty)

    Returns:
        Path to created file
    """
    if file_path.exists():
        raise FileOperationError(f"File already exists: {file_path}")

    # Create parent directories if they don't exist
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Write content
    file_path.write_text(content or "", encoding="utf-8")

    logger.debug(f"Created file: {file_path} ({len(content or '')} bytes)")
    return file_path


async def _modify_file(file_path: Path, content: str | None) -> Path:
    """
    Modify an existing file with new content.

    Args:
        file_path: Path to the file to modify
        content: New file content

    Returns:
        Path to modified file
    """
    if not file_path.exists():
        logger.warning(f"File does not exist, creating: {file_path}")
        return await _create_file(file_path, content)

    # Write new content
    file_path.write_text(content or "", encoding="utf-8")

    logger.debug(f"Modified file: {file_path} ({len(content or '')} bytes)")
    return file_path


async def _delete_file(file_path: Path) -> Path:
    """
    Delete a file.

    Args:
        file_path: Path to the file to delete

    Returns:
        Path to deleted file
    """
    if not file_path.exists():
        logger.warning(f"File does not exist, skipping delete: {file_path}")
        return file_path

    file_path.unlink()

    logger.debug(f"Deleted file: {file_path}")
    return file_path


async def _backup_file(file_path: Path, backup_dir: Path, repo_path: Path) -> Path | None:
    """
    Backup a file before modification/deletion.

    Args:
        file_path: Path to file to backup
        backup_dir: Directory to store backup
        repo_path: Repository root path (for calculating relative paths)

    Returns:
        Path to backup file, or None if file doesn't exist
    """
    if not file_path.exists():
        return None

    # Preserve directory structure in backup relative to repo root
    relative_path = file_path.relative_to(repo_path)
    backup_path = backup_dir / relative_path

    # Create backup directory
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy file
    shutil.copy2(file_path, backup_path)

    logger.debug(f"Backed up {relative_path} to {backup_path}")
    return backup_path


async def create_backup_directory(repo_path: Path) -> Path:
    """
    Create a timestamped backup directory.

    Args:
        repo_path: Repository path

    Returns:
        Path to backup directory

    Example:
        backup_dir = await create_backup_directory(Path("/tmp/repoai_xyz123"))
        # Returns: /tmp/repoai_xyz123_backup_20251109_143022
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = repo_path.parent / f"{repo_path.name}_backup_{timestamp}"

    backup_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Created backup directory: {backup_dir}")
    return backup_dir


async def restore_from_backup(backup_dir: Path, repo_path: Path) -> None:
    """
    Restore files from backup directory.

    Args:
        backup_dir: Backup directory path
        repo_path: Repository path to restore to

    Raises:
        FileOperationError: If restore fails
    """
    if not backup_dir.exists():
        raise FileOperationError(f"Backup directory does not exist: {backup_dir}")

    logger.info(f"Restoring from backup: {backup_dir} -> {repo_path}")

    try:
        # Copy all files from backup
        for backup_file in backup_dir.rglob("*"):
            if backup_file.is_file():
                # Calculate relative path
                relative_path = backup_file.relative_to(backup_dir)
                target_path = repo_path / relative_path

                # Create parent directories
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Restore file
                shutil.copy2(backup_file, target_path)
                logger.debug(f"Restored {relative_path}")

        logger.info("Successfully restored from backup")

    except Exception as e:
        logger.error(f"Failed to restore from backup: {e}")
        raise FileOperationError(f"Failed to restore from backup: {e}") from e


async def validate_file_paths(changes: CodeChanges, repo_path: Path) -> list[str]:
    """
    Validate that file paths are safe and within repository.

    Args:
        changes: CodeChanges to validate
        repo_path: Repository root path

    Returns:
        List of validation errors (empty if all valid)

    Example:
        errors = await validate_file_paths(changes, Path("/tmp/repoai_xyz123"))
        if errors:
            print(f"Invalid paths: {errors}")
    """
    errors: list[str] = []
    repo_path = repo_path.resolve()

    for change in changes.changes:
        # Check for path traversal attempts
        if ".." in change.file_path:
            errors.append(f"Path traversal detected: {change.file_path}")
            continue

        # Check if path is within repository
        full_path = (repo_path / change.file_path).resolve()
        try:
            full_path.relative_to(repo_path)
        except ValueError:
            errors.append(f"Path outside repository: {change.file_path}")
            continue

        # Check for absolute paths
        if Path(change.file_path).is_absolute():
            errors.append(f"Absolute path not allowed: {change.file_path}")
            continue

    if errors:
        logger.warning(f"Found {len(errors)} invalid file paths")

    return errors


async def cleanup_backup(backup_dir: Path) -> None:
    """
    Remove backup directory and all its contents.

    Args:
        backup_dir: Backup directory to remove

    Example:
        await cleanup_backup(Path("/tmp/repoai_xyz123_backup_20251109_143022"))
    """
    if not backup_dir.exists():
        logger.warning(f"Backup directory does not exist: {backup_dir}")
        return

    try:
        shutil.rmtree(backup_dir)
        logger.info(f"Cleaned up backup directory: {backup_dir}")
    except Exception as e:
        logger.error(f"Failed to cleanup backup: {e}")
        # Don't raise exception for cleanup failures
