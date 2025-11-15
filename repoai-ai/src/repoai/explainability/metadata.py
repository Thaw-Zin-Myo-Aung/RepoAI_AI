"""
Metada for explainability
Capture information about agent decisions for transparency and debugging.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RefactorMetadata(BaseModel):
    """
    Metadata for explainability and audit trail

    Captures information about how and why an agent made its decisions,

    Example:
        metadata = RefactorMetadata(
            timestamp=datetime.now(),
            agent_name="IntakeAgent",
            model_used="deepseek/deepseek-chat-v3.1",
            confidence_score=0.95,
            reasoning_chain=[
                "Identified intent: add_authentication",
                "Detected JWT keyword in prompt",
                "Scoped to auth module based on context"
            ],
            data_sources=["user_prompt", "repository_structure"],
            execution_time_ms=1234.56
        )
    """

    timestamp: datetime = Field(
        default_factory=datetime.now, description="When this decision was made"
    )

    agent_name: str = Field(description="Name of the agent that made this decision")

    model_used: str = Field(description="LLM model identifier used for this decision")

    confidence_score: float = Field(
        ge=0.0, le=1.0, default=1.0, description="Confidence score of the decision (0.0 - 1.0)"
    )

    reasoning_chain: list[str] = Field(
        default_factory=list, description="Step-by-step reasoning leading to the decision"
    )

    data_sources: list[str] = Field(default_factory=list, description="Sources of information used")

    alternatives_considered: list[str] = Field(
        default_factory=list, description="Other options that were considered but not chosen"
    )

    risk_factors: list[str] = Field(
        default_factory=list, description="Potential risks identified during decision-making"
    )

    execution_time_ms: float = Field(
        default=0.0, description="Time taken to reach the decision in milliseconds"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-01-15T10:30:00",
                "agent_name": "PlannerAgent",
                "model_used": "deepseek/deepseek-reasoner-v3.1",
                "confidence_score": 0.92,
                "reasoning_chain": [
                    "Analyzed repository structure",
                    "Identified authentication module location",
                    "Planned JWT integration approach",
                ],
                "data_sources": ["src/auth/", "package.json"],
                "execution_time_ms": 2500.0,
            }
        }
    )
