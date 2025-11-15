"""
Quick test for file operations module.

Tests:
1. Create file
2. Modify file
3. Delete file
4. Backup and restore
"""

import asyncio
import tempfile
from pathlib import Path

from repoai.models import CodeChange
from repoai.utils.file_operations import (
    apply_code_change,
    create_backup_directory,
    restore_from_backup,
)


async def test_file_operations():
    """Test basic file operations."""
    print("🧪 Testing File Operations...")

    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        print(f"📁 Test repo: {repo_path}")

        # Test 1: CREATE
        print("\n1️⃣  Testing CREATE...")
        create_change = CodeChange(
            file_path="src/main/java/com/example/Test.java",
            change_type="created",
            modified_content="""package com.example;

public class Test {
    public String hello() {
        return "Hello World!";
    }
}
""",
            diff="",
            lines_added=7,
            lines_removed=0,
        )

        file_path = await apply_code_change(create_change, repo_path)
        assert file_path.exists(), "File should be created"
        assert "Hello World!" in file_path.read_text(), "Content should match"
        print(f"   ✅ Created: {file_path.relative_to(repo_path)}")

        # Test 2: CREATE BACKUP
        print("\n2️⃣  Testing BACKUP...")
        backup_dir = await create_backup_directory(repo_path)
        print(f"   ✅ Backup created: {backup_dir.name}")

        # Test 3: MODIFY
        print("\n3️⃣  Testing MODIFY...")
        modify_change = CodeChange(
            file_path="src/main/java/com/example/Test.java",
            change_type="modified",
            original_content=create_change.modified_content,
            modified_content="""package com.example;

public class Test {
    public String hello() {
        return "Hello Modified World!";
    }
    
    public int add(int a, int b) {
        return a + b;
    }
}
""",
            diff="",
            lines_added=11,
            lines_removed=7,
        )

        file_path = await apply_code_change(modify_change, repo_path, backup_dir)
        content = file_path.read_text()
        assert "Modified World!" in content, "Content should be modified"
        assert "add(int a, int b)" in content, "New method should exist"
        print(f"   ✅ Modified: {file_path.relative_to(repo_path)}")

        # Test 4: RESTORE FROM BACKUP
        print("\n4️⃣  Testing RESTORE...")
        await restore_from_backup(backup_dir, repo_path)
        restored_content = file_path.read_text()
        assert "Hello World!" in restored_content, "Should be restored to original"
        assert "Modified World!" not in restored_content, "Modified content should be gone"
        print("   ✅ Restored from backup")

        # Test 5: DELETE
        print("\n5️⃣  Testing DELETE...")
        delete_change = CodeChange(
            file_path="src/main/java/com/example/Test.java",
            change_type="deleted",
            original_content=create_change.modified_content,
            modified_content=None,
            diff="",
            lines_added=0,
            lines_removed=7,
        )

        file_path = await apply_code_change(delete_change, repo_path)
        assert not file_path.exists(), "File should be deleted"
        print(f"   ✅ Deleted: {file_path.relative_to(repo_path)}")

    print("\n✅ All file operations tests passed!")


if __name__ == "__main__":
    asyncio.run(test_file_operations())
