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


class Critique(BaseModel):
    findings: list[Finding]
    overall_assessment: str
