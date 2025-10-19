from __future__ import annotations

from enum import Enum


class ModelRole(str, Enum):
    INTAKE = "INTAKE"
    PLANNER = "PLANNER"
    PR_NARRATOR = "PR_NARRATOR"
    CODER = "CODER"
    EMBEDDING = "EMBEDDING"
