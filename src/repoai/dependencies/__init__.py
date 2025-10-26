"""
Dependencies for RepoAI agents.

Implements dependency injection pattern following Pydantic AI's approach.
Each agent receives a dependencies object with all required data and services.
"""

from .base import IntakeDependencies, PlannerDependencies

__all__ = [
    "IntakeDependencies",
    "PlannerDependencies",
]
