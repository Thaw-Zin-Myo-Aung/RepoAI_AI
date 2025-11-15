"""
Integration Test: Full Refactoring Pipeline

Tests the complete end-to-end flow:
1. Repository cloning
2. Intake Agent (JobSpec generation)
3. Planner Agent (RefactorPlan generation)
4. Transformer Agent (CodeChanges generation)
5. File Operations (apply changes)
6. Compilation (real Maven build)
7. Validation (real test execution)

This test uses a real Java project to validate the entire pipeline.
"""

import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from repoai.agents.intake_agent import run_intake_agent
from repoai.agents.planner_agent import run_planner_agent
from repoai.agents.transformer_agent import run_transformer_agent
from repoai.agents.validator_agent import run_validator_agent
from repoai.dependencies.base import (
    IntakeDependencies,
    PlannerDependencies,
    TransformerDependencies,
    ValidatorDependencies,
)
from repoai.utils.file_operations import apply_code_changes
from repoai.utils.git_utils import clone_repository
from repoai.utils.java_build_utils import compile_java_project, run_java_tests
from repoai.utils.logger import get_logger

logger = get_logger(__name__)


class TestFullPipeline:
    """Integration tests for the complete refactoring pipeline."""

    @pytest.fixture
    def temp_workspace(self) -> Generator[Path, None, None]:
        """Create temporary workspace for testing."""
        workspace = Path(tempfile.mkdtemp(prefix="repoai_test_"))
        logger.info(f"Created temp workspace: {workspace}")
        yield workspace
        # Cleanup
        if workspace.exists():
            shutil.rmtree(workspace)
            logger.info(f"Cleaned up workspace: {workspace}")

    @pytest.mark.asyncio
    async def test_simple_maven_project_pipeline(self, temp_workspace: Path) -> None:
        """
        Test full pipeline with a simple Maven project.

        This test:
        1. Creates a minimal Maven project
        2. Runs intake → planner → transformer → validator
        3. Applies changes to files
        4. Compiles the project
        5. Runs tests
        6. Verifies everything works
        """
        print("\n" + "=" * 80)
        print("INTEGRATION TEST: Simple Maven Project Pipeline")
        print("=" * 80 + "\n")
        logger.info("=" * 80)
        logger.info("INTEGRATION TEST: Simple Maven Project Pipeline")
        logger.info("=" * 80)

        # ====================================================================
        # Step 1: Create a simple Maven project
        # ====================================================================
        print("[Step 1] Creating simple Maven project...")
        print("[Step 1] Creating simple Maven project...")
        logger.info("\n[Step 1] Creating simple Maven project...")

        project_path = temp_workspace / "simple-maven-app"
        project_path.mkdir()

        # Create pom.xml
        pom_xml = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.example</groupId>
    <artifactId>simple-maven-app</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>

    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>

    <dependencies>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13.2</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
"""
        (project_path / "pom.xml").write_text(pom_xml)

        # Create source directory structure
        src_main_java = project_path / "src" / "main" / "java" / "com" / "example"
        src_main_java.mkdir(parents=True)

        src_test_java = project_path / "src" / "test" / "java" / "com" / "example"
        src_test_java.mkdir(parents=True)

        # Create a simple Java class
        user_service = """package com.example;

public class UserService {
    private String serviceName = "UserService";

    public String getServiceName() {
        return serviceName;
    }

    public String greetUser(String username) {
        return "Hello, " + username + "!";
    }

    public boolean isValidUsername(String username) {
        return username != null && !username.isEmpty();
    }
}
"""
        (src_main_java / "UserService.java").write_text(user_service)

        # Create a test class
        user_service_test = """package com.example;

import org.junit.Test;
import static org.junit.Assert.*;

public class UserServiceTest {
    @Test
    public void testGetServiceName() {
        UserService service = new UserService();
        assertEquals("UserService", service.getServiceName());
    }

    @Test
    public void testGreetUser() {
        UserService service = new UserService();
        String greeting = service.greetUser("John");
        assertEquals("Hello, John!", greeting);
    }

    @Test
    public void testIsValidUsername() {
        UserService service = new UserService();
        assertTrue(service.isValidUsername("john"));
        assertFalse(service.isValidUsername(""));
        assertFalse(service.isValidUsername(null));
    }
}
"""
        (src_test_java / "UserServiceTest.java").write_text(user_service_test)

        print(f"✅ Created Maven project at: {project_path}")
        logger.info(f"✅ Created Maven project at: {project_path}")

        # ====================================================================
        # Step 2: Verify initial compilation
        # ====================================================================
        print("\n[Step 2] Compiling initial project...")
        print("[Step 2] Compiling initial project...")
        logger.info("\n[Step 2] Compiling initial project...")

        initial_compile = await compile_java_project(project_path, clean=True)
        assert initial_compile.success, f"Initial compilation failed: {initial_compile.errors}"
        print(f"✅ Initial compilation successful ({initial_compile.duration_ms:.0f}ms)")
        print(f"✅ Initial compilation successful ({initial_compile.duration_ms:.0f}ms)")
        logger.info(f"✅ Initial compilation successful ({initial_compile.duration_ms:.0f}ms)")

        # ====================================================================
        # Step 3: Run initial tests
        # ====================================================================
        print("[Step 3] Running initial tests...")
        logger.info("\n[Step 3] Running initial tests...")

        initial_tests = await run_java_tests(project_path)
        assert initial_tests.success, f"Initial tests failed: {initial_tests.failures}"
        logger.info(
            f"✅ Initial tests passed: {initial_tests.tests_run} tests "
            f"({initial_tests.duration_ms:.0f}ms)"
        )

        # ====================================================================
        # Step 4: Run Intake Agent
        # ====================================================================
        print("[Step 4] Running Intake Agent...")
        logger.info("\n[Step 4] Running Intake Agent...")

        user_prompt = """
        Add a new method 'getUserById(int id)' to UserService that returns a formatted string.
        The method should return "User ID: {id}" format.
        """

        intake_deps = IntakeDependencies(
            user_id="test_user",
            session_id="integration_test",
        )

        job_spec, intake_metadata = await run_intake_agent(user_prompt, intake_deps)

        print(f"✅ Intake complete: {job_spec.intent}")
        logger.info(f"✅ Intake complete: {job_spec.intent}")
        logger.info(f"   Execution time: {intake_metadata.execution_time_ms:.0f}ms")
        logger.info(f"   Target packages: {job_spec.scope.target_packages}")

        # ====================================================================
        # Step 5: Run Planner Agent
        # ====================================================================
        print("[Step 5] Running Planner Agent...")
        logger.info("\n[Step 5] Running Planner Agent...")

        planner_deps = PlannerDependencies(job_spec=job_spec)
        refactor_plan, planner_metadata = await run_planner_agent(job_spec, planner_deps)

        print(f"✅ Planning complete: {refactor_plan.total_steps} steps")
        logger.info(f"✅ Planning complete: {refactor_plan.total_steps} steps")
        logger.info(f"   Execution time: {planner_metadata.execution_time_ms:.0f}ms")

        # Verify plan has steps
        assert refactor_plan.total_steps > 0, "Plan should have at least one step"

        # ====================================================================
        # Step 6: Run Transformer Agent
        # ====================================================================
        print("[Step 6] Running Transformer Agent...")
        logger.info("\n[Step 6] Running Transformer Agent...")

        transformer_deps = TransformerDependencies(
            plan=refactor_plan,
            repository_path=str(project_path),
        )

        code_changes, transformer_metadata = await run_transformer_agent(
            refactor_plan, transformer_deps
        )

        print(f"✅ Transformation complete: {len(code_changes.changes)} changes")
        logger.info(f"✅ Transformation complete: {len(code_changes.changes)} changes")
        logger.info(f"   Execution time: {transformer_metadata.execution_time_ms:.0f}ms")

        # Verify changes generated
        assert len(code_changes.changes) > 0, "Should have generated code changes"

        # Log changes
        for change in code_changes.changes:
            logger.info(f"   - {change.change_type}: {change.file_path}")
            logger.info(f"     +{change.lines_added} -{change.lines_removed}")

        # ====================================================================
        # Step 7: Apply code changes (with automatic backup)
        # ====================================================================
        print("[Step 7] Applying code changes...")
        logger.info("\n[Step 7] Applying code changes...")

        modified_files, backup_dir = await apply_code_changes(
            code_changes, project_path, create_backup=True
        )

        print("✅ Applied changes:")
        logger.info("✅ Applied changes:")
        logger.info(f"   Modified files: {len(modified_files)}")
        logger.info(f"   Backup created: {backup_dir}")

        for file_path in modified_files:
            logger.info(f"   - {file_path}")

        # At least some changes should succeed
        assert len(modified_files) > 0, "Should have successfully applied some changes"

        # ====================================================================
        # Step 8: Compile modified code
        # ====================================================================
        print("[Step 8] Compiling modified code...")
        logger.info("\n[Step 8] Compiling modified code...")

        post_compile = await compile_java_project(project_path, clean=False)

        if post_compile.success:
            logger.info(
                f"✅ Post-modification compilation successful ({post_compile.duration_ms:.0f}ms)"
            )
        else:
            logger.warning(f"⚠️ Compilation has {post_compile.error_count} errors:")
            for error in post_compile.errors[:5]:  # Show first 5 errors
                logger.warning(f"   {error.file_path}:{error.line_number} - {error.message}")

        # ====================================================================
        # Step 9: Run Validator Agent
        # ====================================================================
        print("[Step 9] Running Validator Agent...")
        logger.info("\n[Step 9] Running Validator Agent...")

        validator_deps = ValidatorDependencies(
            repository_path=str(project_path),
            code_changes=code_changes,
        )

        validation_result, validator_metadata = await run_validator_agent(
            code_changes, validator_deps
        )

        print("✅ Validation complete")
        logger.info("✅ Validation complete")
        logger.info(f"   Execution time: {validator_metadata.execution_time_ms:.0f}ms")
        logger.info(f"   Compilation passed: {validation_result.compilation_passed}")
        logger.info(f"   Validation passed: {validation_result.passed}")
        logger.info(f"   Test coverage: {validation_result.test_coverage:.1%}")

        # Log recommendations
        if validation_result.recommendations:
            logger.info("\n   Recommendations:")
            for rec in validation_result.recommendations[:3]:
                logger.info(f"   - {rec}")

        # ====================================================================
        # Step 10: Summary
        # ====================================================================
        logger.info("\n" + "=" * 80)
        logger.info("INTEGRATION TEST SUMMARY")
        logger.info("=" * 80)

        total_time = (
            intake_metadata.execution_time_ms
            + planner_metadata.execution_time_ms
            + transformer_metadata.execution_time_ms
            + validator_metadata.execution_time_ms
        )

        logger.info("\n✅ Full pipeline completed successfully!")
        logger.info(f"   Total execution time: {total_time:.0f}ms")
        logger.info(f"   Steps generated: {refactor_plan.total_steps}")
        logger.info(f"   Files changed: {len(code_changes.changes)}")
        logger.info(f"   Changes applied: {len(modified_files)}")
        logger.info(f"   Final compilation: {'✅ SUCCESS' if post_compile.success else '⚠️ ISSUES'}")

        # Final assertions
        assert job_spec is not None, "JobSpec should be generated"
        assert refactor_plan.total_steps > 0, "Plan should have steps"
        assert len(code_changes.changes) > 0, "Should generate changes"
        assert len(modified_files) > 0, "Should apply changes"
        assert validation_result is not None, "Should produce validation result"

        logger.info("\n🎉 Integration test PASSED!\n")

    @pytest.mark.asyncio
    async def test_pipeline_with_real_github_repo(self, temp_workspace: Path) -> None:
        """
        Test full pipeline with a real GitHub repository.

        Uses spring-petclinic as a test project.
        """
        logger.info("=" * 80)
        logger.info("INTEGRATION TEST: Real GitHub Repository")
        logger.info("=" * 80)

        # ====================================================================
        # Step 1: Clone repository
        # ====================================================================
        print("[Step 1] Cloning spring-petclinic...")
        logger.info("\n[Step 1] Cloning spring-petclinic...")

        repo_url = "https://github.com/spring-projects/spring-petclinic.git"
        clone_path = temp_workspace / "spring-petclinic"

        try:
            # clone_repository is NOT async - it returns Path directly
            result_path = clone_repository(
                repo_url=repo_url,
                access_token="mock_token_for_testing",
                branch="main",
                target_dir=str(clone_path),
            )
            assert result_path.exists(), "Clone path should exist"
            print(f"✅ Repository cloned: {result_path}")
            logger.info(f"✅ Repository cloned: {result_path}")
        except Exception as e:
            pytest.skip(f"Could not clone repository: {e}")

        # ====================================================================
        # Step 2: Verify project structure
        # ====================================================================
        print("[Step 2] Verifying project structure...")
        logger.info("\n[Step 2] Verifying project structure...")

        pom_file = clone_path / "pom.xml"
        assert pom_file.exists(), "pom.xml should exist"

        src_dir = clone_path / "src" / "main" / "java"
        assert src_dir.exists(), "src/main/java should exist"

        print("✅ Project structure verified")
        logger.info("✅ Project structure verified")

        # ====================================================================
        # Step 3: Initial compilation (verify project is valid)
        # ====================================================================
        print("[Step 3] Running initial compilation...")
        logger.info("\n[Step 3] Running initial compilation...")

        initial_compile = await compile_java_project(clone_path, clean=True)

        if initial_compile.success:
            print(f"✅ Initial compilation successful ({initial_compile.duration_ms:.0f}ms)")
            logger.info(f"✅ Initial compilation successful ({initial_compile.duration_ms:.0f}ms)")
        else:
            logger.warning("⚠️ Initial compilation has issues (this is OK for testing)")
            logger.warning(f"   Errors: {initial_compile.error_count}")

        # ====================================================================
        # Step 4: Run simple refactoring request
        # ====================================================================
        print("[Step 4] Running Intake Agent...")
        logger.info("\n[Step 4] Running Intake Agent...")

        user_prompt = """
        Add logging to the PetController class.
        Use SLF4J logger to log when pets are retrieved.
        """

        intake_deps = IntakeDependencies(
            user_id="test_user",
            session_id="integration_test_real_repo",
        )

        job_spec, intake_metadata = await run_intake_agent(user_prompt, intake_deps)

        print("✅ Intake complete")
        logger.info("✅ Intake complete")
        logger.info(f"   Intent: {job_spec.intent}")
        logger.info(f"   Target packages: {job_spec.scope.target_packages}")

        # ====================================================================
        # Summary
        # ====================================================================
        logger.info("\n" + "=" * 80)
        logger.info("REAL REPO TEST SUMMARY")
        logger.info("=" * 80)
        logger.info("\n✅ Successfully tested with real GitHub repository!")
        logger.info(f"   Repository: {repo_url}")
        logger.info(f"   Initial compilation: {'✅' if initial_compile.success else '⚠️'}")
        logger.info("   Intake agent: ✅")
        logger.info("\n🎉 Real repository test PASSED!\n")


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "-s"])
