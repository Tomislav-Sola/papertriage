from pydantic import BaseModel


class Citation(BaseModel):
    paper_id: str
    claim: str


class Report(BaseModel):
    markdown: str
    citations: list[Citation]
