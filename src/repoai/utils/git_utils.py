"""
Git repository utilities for cloning and managing repositories.

Provides functions for:
- Cloning GitHub repositories with authentication
- Validating Java project structure
- Cleaning up temporary repositories
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from repoai.utils.logger import get_logger

logger = get_logger(__name__)


class GitRepositoryError(Exception):
    """Git repository operation failed."""

    pass


def clone_repository(
    repo_url: str,
    access_token: str,
    branch: str = "main",
    target_dir: str | None = None,
) -> Path:
    """
    Clone a GitHub repository.

    Args:
        repo_url: Repository URL (https://github.com/user/repo)
        access_token: GitHub personal access token
        branch: Branch to checkout (default: main)
        target_dir: Target directory (creates temp if None)

    Returns:
        Path to cloned repository

    Raises:
        GitRepositoryError: If cloning fails

    Example:
        repo_path = clone_repository(
            repo_url="https://github.com/user/repo",
            access_token="ghp_xxxxx",
            branch="main"
        )
    """
    try:
        # Create temp directory if not specified
        if target_dir is None:
            target_dir = tempfile.mkdtemp(prefix="repoai_")

        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)

        # Inject access token into URL for authentication
        # https://github.com/user/repo → https://token@github.com/user/repo
        if access_token and access_token != "mock_token_for_testing":
            auth_url = repo_url.replace("https://", f"https://{access_token}@")
        else:
            auth_url = repo_url
            logger.warning("Using mock token - clone may fail for private repos")

        logger.info(f"Cloning repository: {repo_url} (branch: {branch})")

        # Clone repository with depth=1 for speed
        result = subprocess.run(
            [
                "git",
                "clone",
                "--branch",
                branch,
                "--depth",
                "1",
                auth_url,
                str(target_path),
            ],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            raise GitRepositoryError(f"Git clone failed: {result.stderr}")

        logger.info(f"Repository cloned to: {target_path}")
        return target_path

    except subprocess.TimeoutExpired as exc:
        raise GitRepositoryError("Git clone timeout (>5 minutes)") from exc
    except Exception as exc:
        raise GitRepositoryError(f"Failed to clone repository: {exc}") from exc


def cleanup_repository(repo_path: Path | str) -> None:
    """
    Clean up cloned repository.

    Args:
        repo_path: Path to repository to remove

    Example:
        cleanup_repository("/tmp/repoai_xyz123")
    """
    try:
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
            logger.info(f"Cleaned up repository: {repo_path}")
    except Exception as exc:
        logger.warning(f"Failed to cleanup repository: {exc}")


def validate_repository(repo_path: Path) -> bool:
    """
    Validate that the path contains a valid Java project.

    Checks for:
    - Maven (pom.xml)
    - Gradle (build.gradle or build.gradle.kts)
    - Java source files (*.java)

    Args:
        repo_path: Path to repository

    Returns:
        True if valid Java project, False otherwise

    Example:
        if validate_repository(repo_path):
            print("Valid Java project!")
    """
    # Check for Maven
    has_maven = (repo_path / "pom.xml").exists()

    # Check for Gradle
    has_gradle = (repo_path / "build.gradle").exists() or (repo_path / "build.gradle.kts").exists()

    # Check for Java source files
    src_dir = repo_path / "src"
    has_java = src_dir.exists() and any(src_dir.rglob("*.java"))

    is_valid = (has_maven or has_gradle) and has_java

    if is_valid:
        build_tool = "Maven" if has_maven else "Gradle"
        logger.info(f"Valid Java project detected: {build_tool}")
    else:
        logger.warning(f"Not a valid Java project: {repo_path}")
        if not (has_maven or has_gradle):
            logger.warning("  - No pom.xml or build.gradle found")
        if not has_java:
            logger.warning("  - No Java source files found")

    return is_valid


def get_repository_info(repo_path: Path) -> dict[str, object]:
    """
    Get information about the repository.

    Args:
        repo_path: Path to repository

    Returns:
        Dictionary with repository information

    Example:
        info = get_repository_info(repo_path)
        print(f"Build tool: {info['build_tool']}")
    """
    has_maven = (repo_path / "pom.xml").exists()
    has_gradle = (repo_path / "build.gradle").exists() or (repo_path / "build.gradle.kts").exists()

    # Count Java files
    src_dir = repo_path / "src"
    java_files = list(src_dir.rglob("*.java")) if src_dir.exists() else []

    return {
        "path": str(repo_path),
        "build_tool": "maven" if has_maven else "gradle" if has_gradle else "unknown",
        "has_maven": has_maven,
        "has_gradle": has_gradle,
        "java_file_count": len(java_files),
        "is_valid": validate_repository(repo_path),
    }
