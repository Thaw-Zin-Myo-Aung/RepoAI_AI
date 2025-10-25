"""
Validation result models - output from Validator Agent.
Represents quality checks and test results.
"""

from pydantic import BaseModel, Field

from repoai.explainability.confidence import ConfidenceMetrics
from repoai.explainability.metadata import RefactorMetadata


class ValidationCheck(BaseModel):
    """
    Result of a single validation check.

    Represents one quality gate (e.g., linting, tests, security scan).
    Supports language-specific checks (Java compilation, Maven build, JUnit, etc.).
    """

    check_name: str = Field(
        description="""Name of the validation check. Examples:
        
        Java-specific:
        - 'maven_compile' / 'gradle_build' - compilation check
        - 'checkstyle' / 'pmd' / 'spotbugs' - static analysis
        - 'junit_tests' / 'integration_tests' - test execution
        - 'sonarqube_analysis' - code quality
        - 'owasp_dependency_check' - security vulnerabilities
        - 'jacoco_coverage' - code coverage
        
        Python-specific:
        - 'pylint' / 'flake8' / 'mypy' - static analysis
        - 'pytest' / 'unittest' - test execution
        - 'coverage' - code coverage
        """
    )

    passed: bool = Field(description="Whether this check passed")

    issues: list[str] = Field(default_factory=list, description="List of issues found (if any)")

    compilation_errors: list[str] = Field(
        default_factory=list, description="Compilation error messages (Java-specific)"
    )

    code_quality_score: float | None = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="Code quality score from static analysis (0-10, where 10 is best)",
    )

    details: dict[str, object] = Field(
        default_factory=dict, description="Additional details about the check results"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "check_name": "junit_tests",
                "passed": True,
                "issues": [],
                "compilation_errors": [],
                "code_quality_score": 8.5,
                "details": {
                    "tests_run": 45,
                    "tests_passed": 45,
                    "tests_failed": 0,
                    "tests_skipped": 0,
                    "coverage_percentage": 87.5,
                    "duration_ms": 2340,
                },
            }
        }


class ValidationResult(BaseModel):
    """
    Complete validation results from Validator Agent.

    Represents all quality checks performed on the refactored code.
    This is the output of the Validator Agent.
    Includes language-specific validation (Java compilation, JUnit tests, etc.).

    Example:
        result = ValidationResult(
            passed=True,
            compilation_passed=True,
            checks={
                "maven_compile": ValidationCheck(...),
                "junit_tests": ValidationCheck(...),
                "checkstyle": ValidationCheck(...)
            },
            test_coverage=0.875,
            confidence=ConfidenceMetrics(...)
        )
    """

    plan_id: str = Field(description="Plan ID that was validated")

    passed: bool = Field(description="Whether all validations passed")

    compilation_passed: bool = Field(
        default=True, description="Whether code compiles successfully (critical for Java)"
    )

    checks: dict[str, ValidationCheck] = Field(
        description="Results of individual validation checks"
    )

    test_coverage: float = Field(
        ge=0.0, le=1.0, description="Test coverage percentage (0.0 to 1.0)"
    )

    junit_test_results: dict[str, int] | None = Field(
        default=None,
        description="JUnit test execution details (tests run, passed, failed, skipped, duration)",
    )

    static_analysis_violations: dict[str, int] = Field(
        default_factory=dict,
        description="Static analysis violations by severity (e.g., {'BLOCKER': 0, 'CRITICAL': 2, 'MAJOR': 5})",
    )

    security_vulnerabilities: list[str] = Field(
        default_factory=list,
        description="Security vulnerabilities found in dependencies (OWASP dependency check)",
    )

    confidence: ConfidenceMetrics = Field(description="Confidence metrics for the refactoring")

    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations for improvement"
    )

    metadata: RefactorMetadata | None = Field(
        default=None, description="Metadata about the validation process"
    )

    @property
    def failed_checks(self) -> list[str]:
        """Names of checks that failed."""
        return [name for name, check in self.checks.items() if not check.passed]

    @property
    def all_issues(self) -> list[str]:
        """All issues from all checks."""
        issues = []
        for check in self.checks.values():
            issues.extend(check.issues)
            issues.extend(check.compilation_errors)
        return issues

    @property
    def has_critical_issues(self) -> bool:
        """Whether there are critical issues (compilation failures or security vulnerabilities)."""
        return (
            not self.compilation_passed
            or len(self.security_vulnerabilities) > 0
            or self.static_analysis_violations.get("BLOCKER", 0) > 0
        )

    class Config:
        json_schema_extra = {
            "example": {
                "plan_id": "plan_20250115_103100",
                "passed": True,
                "compilation_passed": True,
                "checks": {
                    "maven_compile": {
                        "check_name": "maven_compile",
                        "passed": True,
                        "issues": [],
                        "compilation_errors": [],
                    },
                    "junit_tests": {
                        "check_name": "junit_tests",
                        "passed": True,
                        "issues": [],
                        "details": {"tests_run": 45, "tests_passed": 45},
                    },
                },
                "test_coverage": 0.875,
                "junit_test_results": {
                    "tests_run": 45,
                    "tests_passed": 45,
                    "tests_failed": 0,
                    "tests_skipped": 0,
                },
                "static_analysis_violations": {"BLOCKER": 0, "CRITICAL": 0, "MAJOR": 2},
                "security_vulnerabilities": [],
                "confidence": {
                    "overall_confidence": 0.85,
                    "reasoning_quality": 0.90,
                    "code_safety": 0.95,
                    "test_coverage": 0.875,
                },
            }
        }
