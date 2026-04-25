from pathlib import Path

from pydantic import BaseModel


class RawPaper(BaseModel):
    id: str          # sha1 of the file path
    path: Path
    raw_text: str
    char_count: int
