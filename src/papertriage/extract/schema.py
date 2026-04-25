from pydantic import BaseModel, Field


class Paper(BaseModel):
    id: str
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    problem: str = ""
    method: str = ""
    contributions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    key_results: list[str] = Field(default_factory=list)
