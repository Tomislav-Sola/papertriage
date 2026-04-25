from pydantic import BaseModel


class Cluster(BaseModel):
    id: int
    label: str
    paper_ids: list[str]
    keywords: list[str]
