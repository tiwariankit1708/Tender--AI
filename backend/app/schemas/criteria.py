from enum import Enum
from pydantic import BaseModel, Field, field_validator


class Category(str, Enum):
    """Broad categories for tender eligibility criteria."""
    ELIGIBILITY = "eligibility"
    TECHNICAL = "technical"
    FINANCIAL = "financial"
    DOCUMENTATION = "documentation"
    OTHER = "other"


class Criterion(BaseModel):
    """A single checkable requirement extracted from a tender document."""
    criterion_id: str = ""            # assigned by code, not by the LLM
    category: Category
    requirement: str = Field(min_length=5)
    source_page: int | None = None
    mandatory: bool = True

    @field_validator("category", mode="before")
    @classmethod
    def normalise_category(cls, v):
        """Map unknown category strings to ``other`` instead of failing."""
        v = str(v).strip().lower()
        return v if v in Category._value2member_map_ else "other"


class CriteriaResult(BaseModel):
    """Wrapper for a list of extracted criteria."""
    criteria: list[Criterion]
