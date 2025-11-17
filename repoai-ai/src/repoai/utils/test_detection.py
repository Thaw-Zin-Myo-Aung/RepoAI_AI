from pathlib import Path

from repoai.utils.logger import get_logger

logger = get_logger(__name__)


def has_java_tests(repo_path: str | Path) -> bool:
    """
    Returns True if the Java project contains any test files in standard locations.
    Checks for src/test/java or src/test/kotlin with .java/.kt files.
    """
    repo_path = Path(repo_path)
    test_dirs = [repo_path / "src/test/java", repo_path / "src/test/kotlin"]
    for test_dir in test_dirs:
        if test_dir.exists():
            for ext in (".java", ".kt"):
                if any(test_dir.rglob(f"*{ext}")):
                    return True
    return False


def find_test_files_for_class(repository_path: str, class_file_path: str) -> list[str]:
    """
    Find test files that correspond to a given main class file.

    Args:
        repository_path: Path to the repo root
        class_file_path: Path to the main class (e.g., "src/main/java/com/example/UserService.java")

    Returns:
        List of test file paths that test this class
    """
    import os

    if not repository_path:
        logger.warning("Repository path not set")
        return []

    class_name = os.path.basename(class_file_path).replace(".java", "")
    test_files = []
    test_patterns = [
        f"{class_name}Test.java",
        f"{class_name}Tests.java",
        f"Test{class_name}.java",
        f"{class_name}TestCase.java",
    ]
    test_dirs = [
        "src/test/java",
        "test",
        "tests",
        "src/test",
    ]
    for test_dir in test_dirs:
        test_dir_path = os.path.join(repository_path, test_dir)
        if not os.path.exists(test_dir_path):
            continue
        for root, _, files in os.walk(test_dir_path):
            for file in files:
                if any(pattern in file for pattern in test_patterns):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, repository_path)
                    test_files.append(rel_path)
    if test_files:
        logger.info(f"Found {len(test_files)} test file(s) for {class_name}")
    else:
        logger.debug(f"No test files found for {class_name}")
    return test_files
