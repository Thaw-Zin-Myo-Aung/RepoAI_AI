"""
Git repository utilities for cloning and managing repositories.

Provides functions for:
- Cloning GitHub repositories with authentication
- Validating Java project structure
- Cleaning up temporary repositories
- Creating branches and committing changes
- Pushing changes to remote repositories
"""

import os
import shutil
import subprocess
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
        target_dir: Target directory (creates in cloned_repos/ if None)

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
        # Create directory in RepoAI_AI/cloned_repos if not specified
        if target_dir is None:
            # Get RepoAI_AI root directory (3 levels up from this file)
            repo_ai_root = Path(__file__).parent.parent.parent.parent
            cloned_repos_dir = repo_ai_root / "cloned_repos"
            cloned_repos_dir.mkdir(parents=True, exist_ok=True)

            # Extract repo name from URL for directory name
            repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
            import time

            timestamp = int(time.time())
            target_dir = str(cloned_repos_dir / f"{repo_name}_{timestamp}")

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


def create_branch(
    repo_path: Path,
    branch_name: str,
) -> None:
    """
    Create and checkout a new branch.

    Args:
        repo_path: Path to repository
        branch_name: Name of the new branch

    Raises:
        GitRepositoryError: If branch creation fails

    Example:
        create_branch(repo_path, "repoai/add-jwt-auth-20251112")
    """
    try:
        logger.info(f"Creating branch: {branch_name}")

        # Create and checkout new branch
        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise GitRepositoryError(f"Failed to create branch: {result.stderr}")

        logger.info(f"Branch created and checked out: {branch_name}")

    except subprocess.TimeoutExpired as exc:
        raise GitRepositoryError("Branch creation timeout") from exc
    except Exception as exc:
        raise GitRepositoryError(f"Failed to create branch: {exc}") from exc


def commit_changes(
    repo_path: Path,
    commit_message: str,
    author_name: str = "RepoAI Bot",
    author_email: str = "repoai@bot.com",
) -> str:
    """
    Stage all changes and create a commit.

    Args:
        repo_path: Path to repository
        commit_message: Commit message (can be multi-line)
        author_name: Git author name (default: RepoAI Bot)
        author_email: Git author email (default: repoai@bot.com)

    Returns:
        Commit hash (SHA)

    Raises:
        GitRepositoryError: If commit fails

    Example:
        commit_hash = commit_changes(
            repo_path,
            "feat: Add JWT authentication\\n\\nImplemented JWT service and security config",
            "John Doe",
            "john@example.com"
        )
        print(f"Committed: {commit_hash[:7]}")
    """
    try:
        logger.info(f"Committing changes: {commit_message[:50]}...")

        # Stage all changes
        result = subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise GitRepositoryError(f"Failed to stage changes: {result.stderr}")

        # Set git config for commit
        subprocess.run(
            ["git", "config", "user.name", author_name],
            cwd=repo_path,
            check=True,
            timeout=10,
        )
        subprocess.run(
            ["git", "config", "user.email", author_email],
            cwd=repo_path,
            check=True,
            timeout=10,
        )

        # Create commit
        result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            # Check if there are no changes to commit
            if "nothing to commit" in result.stdout.lower():
                logger.warning("No changes to commit")
                return ""
            raise GitRepositoryError(f"Failed to commit: {result.stderr}")

        # Get commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )

        commit_hash = result.stdout.strip()
        logger.info(f"Changes committed successfully: {commit_hash[:7]}")
        return commit_hash

    except subprocess.TimeoutExpired as exc:
        raise GitRepositoryError("Commit timeout") from exc
    except Exception as exc:
        raise GitRepositoryError(f"Failed to commit changes: {exc}") from exc


def push_to_remote(
    repo_path: Path,
    branch_name: str,
    access_token: str,
    repo_url: str,
) -> None:
    """
    Push branch to remote repository using access token for authentication.

    Args:
        repo_path: Path to repository
        branch_name: Name of branch to push
        access_token: GitHub personal access token
        repo_url: Repository URL (https://github.com/user/repo)

    Raises:
        GitRepositoryError: If push fails

    Example:
        push_to_remote(
            repo_path,
            "repoai/add-jwt-auth-20251112",
            "ghp_xxxxx",
            "https://github.com/user/repo"
        )
    """
    try:
        logger.info(f"Pushing branch to remote: {branch_name}")

        # Inject access token into URL for authentication
        # https://github.com/user/repo → https://token@github.com/user/repo
        if access_token and access_token != "mock_token_for_testing":
            auth_url = repo_url.replace("https://", f"https://{access_token}@")
        else:
            auth_url = repo_url
            logger.warning("Using mock token - push may fail")

        # Set remote URL with authentication
        subprocess.run(
            ["git", "remote", "set-url", "origin", auth_url],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Push branch to remote
        result = subprocess.run(
            ["git", "push", "-u", "origin", branch_name],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            raise GitRepositoryError(f"Failed to push: {result.stderr}")

        logger.info(f"Branch pushed successfully to remote: {branch_name}")

    except subprocess.TimeoutExpired as exc:
        raise GitRepositoryError("Push timeout (>5 minutes)") from exc
    except Exception as exc:
        raise GitRepositoryError(f"Failed to push to remote: {exc}") from exc
