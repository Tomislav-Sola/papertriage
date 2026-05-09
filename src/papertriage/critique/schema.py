from enum import Enum

from pydantic import BaseModel


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Finding(BaseModel):
    claim: str
    severity: Severity
    reason: str
    suggested_fix: str
    source_critic: str | None = None


class FindingList(BaseModel):
    """Tool-use wrapper for extracting a list of findings from a single critic agent."""
    findings: list[Finding]


class Critique(BaseModel):
    findings: list[Finding]
    overall_assessment: str
