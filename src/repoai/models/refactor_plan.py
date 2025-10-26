"""
Refactor plan models - output from Planner Agent.
Defines how the refactoring will be executed step-by-step.
"""

from pydantic import BaseModel, ConfigDict, Field

from repoai.explainability.metadata import RefactorMetadata


class RefactorStep(BaseModel):
    """
    Single step in the refactoring plan.

    Represents one atomic refactoring operation with its dependencies.
    Supports language-specific operations (Java, Python, etc.).
    """

    step_number: int = Field(ge=1, description="Order of execution (1-indexed)")

    action: str = Field(
        description="""Action to perform. Language-specific examples:
        
        Java:
        - 'create_class', 'create_interface', 'create_enum', 'create_annotation'
        - 'add_method', 'extract_method', 'inline_method', 'rename_method'
        - 'add_annotation' (e.g., @Service, @Autowired, @Override)
        - 'implement_interface', 'extend_class', 'add_implements'
        - 'add_dependency' (pom.xml/build.gradle modification)
        - 'refactor_package_structure', 'move_class'
        - 'add_spring_configuration', 'add_rest_controller'
        
        Python:
        - 'create_file', 'modify_function', 'add_import'
        - 'extract_function', 'inline_function'
        - 'add_decorator', 'refactor_class'
        """
    )

    target_classes: list[str] = Field(
        default_factory=list,
        description="Fully qualified class names for Java (e.g., 'com.example.auth.JwtService')",
    )

    target_files: list[str] = Field(
        description="Files affected by this step (e.g., 'src/main/java/com/example/Auth.java', 'pom.xml')"
    )
    description: str = Field(description="Human-readable description of what this step does")

    dependencies: list[int] = Field(
        default_factory=list, description="Step numbers that must complete before this step"
    )

    risk_level: int = Field(
        ge=0, le=10, default=5, description="Risk level (0=safe, 10=very risky)"
    )

    estimated_time_mins: int = Field(
        default=5, ge=1, description="Estimated time to complete this step (minutes)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "step_number": 1,
                "action": "create_class",
                "target_classes": ["com.example.auth.JwtService"],
                "target_files": ["src/main/java/com/example/auth/JwtService.java"],
                "description": "Create JWT service class with token generation and validation methods",
                "dependencies": [],
                "risk_level": 3,
                "estimated_time_mins": 15,
            }
        }
    )


class RiskAssessment(BaseModel):
    """
    Overall risk assessment for the refactoring plan.
    Includes language-specific risk factors (Java compilation, Spring Framework impacts, etc.).
    """

    overall_risk_level: int = Field(ge=0, le=10, description="Overall risk (0=safe, 10=very risky)")

    breaking_changes: bool = Field(
        default=False, description="Whether this refactoring includes breaking changes"
    )

    affected_modules: list[str] = Field(description="Modules/packages that will be affected")

    compilation_risk: bool = Field(
        default=False, description="Whether changes might cause compilation errors (Java-specific)"
    )

    dependency_conflicts: bool = Field(
        default=False, description="Whether dependency changes might cause conflicts (Maven/Gradle)"
    )

    runtime_exceptions: list[str] = Field(
        default_factory=list,
        description="Potential runtime exceptions to watch for (e.g., 'NullPointerException', 'ClassCastException')",
    )

    framework_impacts: list[str] = Field(
        default_factory=list,
        description="Frameworks affected by changes (e.g., ['spring', 'hibernate', 'junit'])",
    )

    mitigation_strategies: list[str] = Field(
        default_factory=list, description="Strategies to mitigate identified risks"
    )

    test_coverage_required: float = Field(
        ge=0.0, le=1.0, default=0.8, description="Minimum test coverage required (0.0 to 1.0)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "overall_risk_level": 5,
                "breaking_changes": False,
                "affected_modules": ["com.example.auth", "com.example.user", "com.example.api"],
                "compilation_risk": True,
                "dependency_conflicts": False,
                "runtime_exceptions": ["NullPointerException", "IllegalArgumentException"],
                "framework_impacts": ["spring", "spring-security"],
                "mitigation_strategies": [
                    "Add comprehensive unit tests for all new methods",
                    "Ensure backward compatibility with @Deprecated annotations",
                    "Deploy with feature flag for gradual rollout",
                    "Run full integration test suite before merge",
                ],
                "test_coverage_required": 0.85,
            }
        }
    )


class RefactorPlan(BaseModel):
    """
    Complete refactoring plan from Planner Agent.

    Defines the step-by-step execution plan with dependencies and risk assessment.
    This is the output of the Planner Agent and input to the Transformer Agent.

    Example:
        plan = RefactorPlan(
            plan_id="plan_abc123",
            job_id="job_abc123",
            steps=[...],
            risk_assessment=RiskAssessment(...),
            estimated_duration="45 minutes"
        )
    """

    plan_id: str = Field(description="Unique identifier for this plan")

    job_id: str = Field(description="Job ID this plan corresponds to")

    steps: list[RefactorStep] = Field(description="Ordered list of refactoring steps")

    risk_assessment: RiskAssessment = Field(description="Overall risk assessment and mitigation")

    estimated_duration: str = Field(
        description="Human-readable estimated duration (e.g., '30 minutes', '2 hours')"
    )

    metadata: RefactorMetadata | None = Field(
        default=None, description="Metadata about how this plan was created"
    )

    @property
    def total_steps(self) -> int:
        """Total number of steps in the plan."""
        return len(self.steps)

    @property
    def high_risk_steps(self) -> list[RefactorStep]:
        """Steps with risk level >= 7."""
        return [step for step in self.steps if step.risk_level >= 7]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "plan_id": "plan_20250115_103100",
                "job_id": "job_20250115_103045",
                "steps": [
                    {
                        "step_number": 1,
                        "action": "create_jwt_utils",
                        "target_files": ["src/auth/jwt_utils.py"],
                        "description": "Create JWT utility module",
                        "dependencies": [],
                        "risk_level": 2,
                    }
                ],
                "risk_assessment": {
                    "overall_risk_level": 4,
                    "breaking_changes": False,
                    "affected_modules": ["auth"],
                    "test_coverage_required": 0.85,
                },
                "estimated_duration": "45 minutes",
            }
        }
    )
