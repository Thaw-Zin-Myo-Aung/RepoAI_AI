"""
Validation result models - output from Validator Agent.
Represents quality checks and test results.

Note: Uses list-based structures instead of dicts to avoid Gemini's
"additionalProperties not supported" limitation.
"""

from pydantic import BaseModel, ConfigDict, Field

from repoai.explainability.confidence import ConfidenceMetrics
from repoai.explainability.metadata import RefactorMetadata


class CheckDetails(BaseModel):
    """
    Additional details about a validation check.
    Flexible structure for check-specific information.
    """

    tests_run: int | None = Field(default=None, description="Number of tests executed")
    tests_passed: int | None = Field(default=None, description="Number of tests passed")
    tests_failed: int | None = Field(default=None, description="Number of tests failed")
    tests_skipped: int | None = Field(default=None, description="Number of tests skipped")
    coverage_percentage: float | None = Field(default=None, description="Code coverage percentage")
    duration_ms: float | None = Field(
        default=None, description="Execution duration in milliseconds"
    )
    violations_count: int | None = Field(default=None, description="Number of violations found")
    custom_info: str | None = Field(default=None, description="Any other information as a string")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tests_run": 45,
                "tests_passed": 42,
                "tests_failed": 3,
                "coverage_percentage": 87.5,
                "duration_ms": 2340,
            }
        }
    )


class JUnitTestResults(BaseModel):
    """JUnit test execution results."""

    tests_run: int = Field(ge=0, description="Total number of tests executed")
    tests_passed: int = Field(ge=0, description="Number of tests that passed")
    tests_failed: int = Field(ge=0, description="Number of tests that failed")
    tests_skipped: int = Field(ge=0, description="Number of tests skipped")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tests_run": 45,
                "tests_passed": 42,
                "tests_failed": 3,
                "tests_skipped": 0,
            }
        }
    )


class StaticAnalysisViolation(BaseModel):
    """A single category of static analysis violations."""

    severity: str = Field(description="Violation severity (e.g., BLOCKER, CRITICAL, MAJOR, MINOR)")
    count: int = Field(ge=0, description="Number of violations of this severity")

    model_config = ConfigDict(json_schema_extra={"example": {"severity": "MAJOR", "count": 5}})


class ValidationCheckResult(BaseModel):
    """A named validation check with its result."""

    name: str = Field(description="Name of the check (e.g., maven_compile, junit_tests)")
    result: "ValidationCheck" = Field(description="The validation check result")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "junit_tests",
                "result": {
                    "check_name": "junit_tests",
                    "passed": True,
                    "issues": [],
                    "compilation_errors": [],
                },
            }
        }
    )


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

    details: CheckDetails | None = Field(
        default=None, description="Additional details about the check results"
    )

    model_config = ConfigDict(
        json_schema_extra={
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
    )


class ValidationResult(BaseModel):
    """
    Complete validation results from Validator Agent.

    Represents all quality checks performed on the refactored code.
    This is the output of the Validator Agent.
    Includes language-specific validation (Java compilation, JUnit tests, etc.).

    Note: Uses list-based structures instead of dicts to work with Gemini
    (which doesn't support additionalProperties in JSON schemas).

    Example:
        result = ValidationResult(
            passed=True,
            compilation_passed=True,
            checks=[
                ValidationCheckResult(name="maven_compile", result=ValidationCheck(...)),
                ValidationCheckResult(name="junit_tests", result=ValidationCheck(...)),
            ],
            test_coverage=0.875,
            confidence=ConfidenceMetrics(...)
        )
    """

    plan_id: str = Field(description="Plan ID that was validated")

    passed: bool = Field(description="Whether all validations passed")

    compilation_passed: bool = Field(
        default=True, description="Whether code compiles successfully (critical for Java)"
    )

    checks: list[ValidationCheckResult] = Field(
        default_factory=list, description="Results of individual validation checks"
    )

    test_coverage: float = Field(
        ge=0.0, le=1.0, description="Test coverage percentage (0.0 to 1.0)"
    )

    junit_test_results: JUnitTestResults | None = Field(
        default=None,
        description="JUnit test execution details",
    )

    static_analysis_violations: list[StaticAnalysisViolation] = Field(
        default_factory=list,
        description="Static analysis violations by severity",
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
        return [check.name for check in self.checks if not check.result.passed]

    @property
    def all_issues(self) -> list[str]:
        """All issues from all checks."""
        issues = []
        for check in self.checks:
            issues.extend(check.result.issues)
            issues.extend(check.result.compilation_errors)
        return issues

    @property
    def has_critical_issues(self) -> bool:
        """Whether there are critical issues (compilation failures or security vulnerabilities)."""
        blocker_count = sum(
            v.count for v in self.static_analysis_violations if v.severity == "BLOCKER"
        )
        return (
            not self.compilation_passed
            or len(self.security_vulnerabilities) > 0
            or blocker_count > 0
        )

    def get_check(self, name: str) -> ValidationCheck | None:
        """Get a specific check by name."""
        for check in self.checks:
            if check.name == name:
                return check.result
        return None

    def get_violation_count(self, severity: str) -> int:
        """Get the count of violations for a specific severity level."""
        for v in self.static_analysis_violations:
            if v.severity == severity:
                return v.count
        return 0

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "plan_id": "plan_20250115_103100",
                "passed": True,
                "compilation_passed": True,
                "checks": [
                    {
                        "name": "maven_compile",
                        "result": {
                            "check_name": "maven_compile",
                            "passed": True,
                            "issues": [],
                            "compilation_errors": [],
                        },
                    },
                    {
                        "name": "junit_tests",
                        "result": {
                            "check_name": "junit_tests",
                            "passed": True,
                            "issues": [],
                            "details": {"tests_run": 45, "tests_passed": 45},
                        },
                    },
                ],
                "test_coverage": 0.875,
                "junit_test_results": {
                    "tests_run": 45,
                    "tests_passed": 45,
                    "tests_failed": 0,
                    "tests_skipped": 0,
                },
                "static_analysis_violations": [
                    {"severity": "BLOCKER", "count": 0},
                    {"severity": "CRITICAL", "count": 0},
                    {"severity": "MAJOR", "count": 2},
                ],
                "security_vulnerabilities": [],
                "confidence": {
                    "overall_confidence": 0.85,
                    "reasoning_quality": 0.90,
                    "code_safety": 0.95,
                    "test_coverage": 0.875,
                },
            }
        }
    )
