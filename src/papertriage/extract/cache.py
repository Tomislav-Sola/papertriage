from pathlib import Path

from papertriage.core.config import Settings
from papertriage.core.logging import get_logger
from papertriage.extract.schema import Paper

_log = get_logger(__name__)


class ExtractionCache:
    def __init__(self, settings: Settings) -> None:
        self._dir = settings.output_dir / ".extract_cache"
        self._dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    def _path(self, content_hash: str) -> Path:
        return self._dir / f"{content_hash}.json"

    def get(self, content_hash: str) -> Paper | None:
        p = self._path(content_hash)
        if not p.exists():
            self.misses += 1
            return None
        try:
            paper = Paper.model_validate_json(p.read_text(encoding="utf-8"))
            self.hits += 1
            return paper
        except Exception as exc:
            _log.warning("extract_cache_corrupt", hash=content_hash, error=str(exc))
            self.misses += 1
            return None

    def set(self, content_hash: str, paper: Paper) -> None:
        self._path(content_hash).write_text(paper.model_dump_json(), encoding="utf-8")

    def clear(self) -> None:
        for f in self._dir.glob("*.json"):
            f.unlink()
