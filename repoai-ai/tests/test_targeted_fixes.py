"""
Test targeted fix generation for validation errors.
"""

import pytest

from repoai.agents.transformer_fix_agent import _build_fix_prompt, _extract_error_files
from repoai.explainability.confidence import ConfidenceMetrics
from repoai.models.validation_result import (
    ValidationCheck,
    ValidationCheckResult,
    ValidationResult,
)


def test_extract_error_files_from_validation_result():
    """Test extracting file paths from compilation errors."""
    # Create mock validation result with compilation errors
    validation_result = ValidationResult(
        plan_id="test_plan_123",
        passed=False,
        compilation_passed=False,
        test_coverage=0.0,
        checks=[
            ValidationCheckResult(
                name="maven_compile",
                result=ValidationCheck(
                    check_name="maven_compile",
                    passed=False,
                    compilation_errors=[
                        "[ERROR] /path/to/project/src/main/java/com/example/BookService.java:[15,10] cannot find symbol",
                        "[ERROR] src/main/java/com/example/Main.java:[20,5] incompatible types",
                        "[ERROR] src/test/java/com/example/BookServiceTest.java:[30,15] method not found",
                    ],
                    issues=[],
                ),
            )
        ],
        security_vulnerabilities=[],
        confidence=ConfidenceMetrics(
            overall_confidence=0.5,
            reasoning_quality=0.5,
            code_safety=0.5,
            test_coverage=0.0,
        ),
    )

    # Extract error files
    error_files = _extract_error_files(validation_result)

    # Verify we extracted the correct files
    assert len(error_files) == 3
    assert "src/main/java/com/example/BookService.java" in error_files
    assert "src/main/java/com/example/Main.java" in error_files
    assert "src/test/java/com/example/BookServiceTest.java" in error_files


def test_extract_error_files_no_errors():
    """Test extracting files when no compilation errors exist."""
    validation_result = ValidationResult(
        plan_id="test_plan_no_errors",
        passed=True,
        compilation_passed=True,
        test_coverage=1.0,
        checks=[],
        security_vulnerabilities=[],
        confidence=ConfidenceMetrics(
            overall_confidence=0.9,
            reasoning_quality=0.9,
            code_safety=0.95,
            test_coverage=1.0,
        ),
    )

    error_files = _extract_error_files(validation_result)
    assert len(error_files) == 0


def test_build_fix_prompt():
    """Test building fix prompt with errors and file contents."""
    validation_result = ValidationResult(
        plan_id="test_plan_fix_prompt",
        passed=False,
        compilation_passed=False,
        test_coverage=0.0,
        checks=[
            ValidationCheckResult(
                name="maven_compile",
                result=ValidationCheck(
                    check_name="maven_compile",
                    passed=False,
                    compilation_errors=[
                        "[ERROR] src/main/java/com/example/BookService.java:[15,10] cannot find symbol: method addBook"
                    ],
                    issues=[],
                ),
            )
        ],
        security_vulnerabilities=[],
        confidence=ConfidenceMetrics(
            overall_confidence=0.3,
            reasoning_quality=0.5,
            code_safety=0.4,
            test_coverage=0.0,
        ),
    )

    fix_instructions = "Fix the missing addBook method in BookService"
    file_contents = {
        "src/main/java/com/example/BookService.java": "package com.example;\n\npublic class BookService {\n    // Missing addBook method\n}"
    }

    prompt = _build_fix_prompt(validation_result, fix_instructions, file_contents)

    # Verify prompt contains key elements
    assert "Fix the missing addBook method in BookService" in prompt
    assert "cannot find symbol: method addBook" in prompt
    assert "package com.example;" in prompt
    assert "BookService" in prompt
    assert "COMPILATION ERRORS:" in prompt
    assert "CURRENT FILE CONTENTS:" in prompt


def test_build_fix_prompt_multiple_files():
    def test_extract_error_files_from_test_failures():
        """Test extracting error files from test failures (output mismatch)."""
        from repoai.models.validation_result import (
            ValidationCheck,
            ValidationCheckResult,
            ValidationResult,
        )
        from repoai.explainability.confidence import ConfidenceMetrics

        validation_result = ValidationResult(
            plan_id="plan_test_failures",
            passed=False,
            compilation_passed=True,
            test_coverage=0.0,
            checks=[
                ValidationCheckResult(
                    name="junit_tests",
                    result=ValidationCheck(
                        check_name="junit_tests",
                        passed=False,
                        issues=[],
                        compilation_errors=[],
                        details=type(
                            "Details",
                            (),
                            {
                                "failed_tests": [
                                    {
                                        "test_class": "BookServiceTest",
                                        "test_method": "testPrintNumbers",
                                        "error_type": "AssertionError",
                                        "message": "expected: <1> but was: <Num: 1>",
                                    }
                                ]
                            },
                        )(),
                    ),
                )
            ],
            security_vulnerabilities=[],
            confidence=ConfidenceMetrics(
                overall_confidence=0.5,
                reasoning_quality=0.5,
                code_safety=0.5,
                test_coverage=0.0,
            ),
        )

        from repoai.agents.transformer_fix_agent import _extract_error_files, _build_fix_prompt

        error_files = _extract_error_files(validation_result)
        assert "src/test/java/BookServiceTest.java" in error_files

        file_contents = {
            "src/test/java/BookServiceTest.java": "public class BookServiceTest { /* ... */ }"
        }
        fix_instructions = "Fix output mismatch in testPrintNumbers"
        prompt = _build_fix_prompt(validation_result, fix_instructions, file_contents)
        assert "testPrintNumbers" in prompt
        assert "expected: <1> but was: <Num: 1>" in prompt

    """Test building fix prompt with multiple files."""
    validation_result = ValidationResult(
        plan_id="test_plan_multi_files",
        passed=False,
        compilation_passed=False,
        test_coverage=0.0,
        checks=[
            ValidationCheckResult(
                name="maven_compile",
                result=ValidationCheck(
                    check_name="maven_compile",
                    passed=False,
                    compilation_errors=[
                        "[ERROR] src/main/java/com/example/BookService.java:[15,10] error1",
                        "[ERROR] src/main/java/com/example/Main.java:[20,5] error2",
                    ],
                    issues=[],
                ),
            )
        ],
        security_vulnerabilities=[],
        confidence=ConfidenceMetrics(
            overall_confidence=0.3,
            reasoning_quality=0.4,
            code_safety=0.3,
            test_coverage=0.0,
        ),
    )

    fix_instructions = "Fix compilation errors"
    file_contents = {
        "src/main/java/com/example/BookService.java": "class BookService {}",
        "src/main/java/com/example/Main.java": "class Main {}",
    }

    prompt = _build_fix_prompt(validation_result, fix_instructions, file_contents)

    # Verify both files are in prompt
    assert "BookService" in prompt
    assert "Main" in prompt
    assert "error1" in prompt
    assert "error2" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
