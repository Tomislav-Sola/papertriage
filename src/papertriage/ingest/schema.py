from pathlib import Path

from pydantic import BaseModel, Field


class RawPaper(BaseModel):
    id: str          # sha1 of PDF bytes
    path: Path
    raw_text: str
    char_count: int
    metadata: dict[str, str] = Field(default_factory=dict)
