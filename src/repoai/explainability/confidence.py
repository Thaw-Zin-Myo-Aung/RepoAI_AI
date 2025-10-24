"""
Confidence scoring models for validation and quality assessment.
Confidence-based human review triggering.
"""

from pydantic import BaseModel, Field


class ConfidenceMetrics(BaseModel):
    """
    Multi-dimensional confidence scoring for refactoring quality.

    Used by Validator Agent to determine if human review is needed.
    Example:
        confidence = ConfidenceMetrics(
                overall_confidence=0.85,
                reasoning_quality=0.90,
                code_safety=0.95,
                test_coverage=0.75
            )

            if confidence.requires_human_review:
                print("Human review required!")
    """

    overall_confidence: float = Field(
        ge=0.0, le=1.0, description="Overall confidence in the refactoring (0.0 - 1.0)"
    )

    reasoning_quality: float = Field(
        ge=0.0, le=1.0, description="Quality of reasoning and decision-making"
    )

    code_safety: float = Field(
        ge=0.0,
        le=1.0,
        description="Safety of code changes (no breaking changes, security issues, etc.)",
    )

    test_coverage: float = Field(ge=0.0, le=1.0, description="Test Coverage Adequacy (0.0 - 1.0)")

    @property
    def quality_level(self) -> str:
        """
        Get quality level description based on overall confidence score.

        Returns:
            str: "Excellent", "Good", "Fair", "Poor"
        """
        if self.overall_confidence >= 0.9:
            return "Excellent"
        elif self.overall_confidence >= 0.8:
            return "Good"
        elif self.overall_confidence >= 0.7:
            return "Fair"
        else:
            return "Poor"

    class Config:
        json_schema_extra = {
            "example": {
                "overall_confidence": 0.85,
                "reasoning_quality": 0.90,
                "code_safety": 0.95,
                "test_coverage": 0.75,
            }
        }
