from pathlib import Path
from typing import Protocol


class PdfSource(Protocol):
    name: str

    def fetch(self) -> list[Path]: ...
