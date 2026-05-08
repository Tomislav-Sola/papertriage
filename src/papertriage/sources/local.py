from pathlib import Path

from papertriage.core.logging import get_logger

_log = get_logger(__name__)


class LocalSource:
    name = "local"

    def __init__(self, folder: Path) -> None:
        self._folder = folder

    def fetch(self) -> list[Path]:
        return sorted(self._folder.glob("*.pdf"))
