"""
Unit tests for git_utils module.

Tests repository cloning, validation, and cleanup functionality.
"""

import tempfile
from pathlib import Path

import pytest

from repoai.utils.git_utils import (
    GitRepositoryError,
    cleanup_repository,
    clone_repository,
    get_repository_info,
    validate_repository,
)


def test_clone_public_repository():
    """Test cloning a public Java repository."""
    repo_url = "https://github.com/spring-projects/spring-petclinic"
    access_token = "mock_token_for_testing"  # Public repo doesn't need real token

    try:
        # Clone repository
        repo_path = clone_repository(repo_url=repo_url, access_token=access_token, branch="main")

        # Verify repository exists
        assert repo_path.exists()
        assert repo_path.is_dir()

        # Verify .git directory exists
        assert (repo_path / ".git").exists()

        # Verify it's a valid Java project
        assert validate_repository(repo_path)

        # Get repository info
        info = get_repository_info(repo_path)
        assert info["is_valid"] is True
        assert info["build_tool"] == "maven"
        assert info["has_maven"] is True
        assert isinstance(info["java_file_count"], int)
        assert info["java_file_count"] > 0

    finally:
        # Cleanup
        if "repo_path" in locals():
            cleanup_repository(repo_path)
            assert not repo_path.exists()


def test_clone_invalid_url():
    """Test that cloning an invalid URL raises GitRepositoryError."""
    with pytest.raises(GitRepositoryError):
        clone_repository(
            repo_url="https://github.com/invalid/nonexistent-repo-xyz123",
            access_token="mock_token",
            branch="main",
        )


def test_validate_non_java_repository():
    """Test validation fails for non-Java repositories."""
    # Create a temporary directory without Java files
    temp_dir = Path(tempfile.mkdtemp())

    try:
        # Should fail validation (no Java files or build files)
        assert validate_repository(temp_dir) is False

        # Add a pom.xml but no Java files
        (temp_dir / "pom.xml").touch()
        assert validate_repository(temp_dir) is False  # Still invalid (no Java files)

        # Add src directory with a Java file
        src_dir = temp_dir / "src" / "main" / "java"
        src_dir.mkdir(parents=True)
        (src_dir / "Test.java").write_text("public class Test {}")

        # Now should be valid
        assert validate_repository(temp_dir) is True

    finally:
        cleanup_repository(temp_dir)


def test_cleanup_nonexistent_path():
    """Test cleanup handles non-existent paths gracefully."""
    nonexistent = Path("/tmp/nonexistent_repo_xyz123")
    cleanup_repository(nonexistent)  # Should not raise


def test_get_repository_info_gradle():
    """Test repository info for Gradle projects."""
    temp_dir = Path(tempfile.mkdtemp())

    try:
        # Create Gradle project structure
        (temp_dir / "build.gradle").write_text("// Gradle build file")
        src_dir = temp_dir / "src" / "main" / "java"
        src_dir.mkdir(parents=True)
        (src_dir / "App.java").write_text("public class App {}")
        (src_dir / "Utils.java").write_text("public class Utils {}")

        info = get_repository_info(temp_dir)
        assert info["is_valid"] is True
        assert info["build_tool"] == "gradle"
        assert info["has_gradle"] is True
        assert info["has_maven"] is False
        assert isinstance(info["java_file_count"], int)
        assert info["java_file_count"] == 2

    finally:
        cleanup_repository(temp_dir)


if __name__ == "__main__":
    # Run basic smoke test
    print("Running git_utils smoke test...")
    test_clone_public_repository()
    print("✅ Smoke test passed!")
