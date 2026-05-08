from pathlib import Path

import httpx

from papertriage.core.config import Settings
from papertriage.core.logging import get_logger

_log = get_logger(__name__)
_ARXIV_PDF_URL = "https://arxiv.org/pdf/{}"


class ArxivSource:
    name = "arxiv"

    def __init__(self, ids: list[str], settings: Settings) -> None:
        self._ids = ids
        self._cache_dir = settings.output_dir / ".arxiv_cache"

    def fetch(self) -> list[Path]:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for arxiv_id in self._ids:
            path = self._fetch_one(arxiv_id)
            if path is not None:
                paths.append(path)
        return paths

    def _fetch_one(self, arxiv_id: str) -> Path | None:
        cache_path = self._cache_dir / f"{arxiv_id}.pdf"
        if cache_path.exists():
            _log.info("arxiv_cache_hit", arxiv_id=arxiv_id)
            return cache_path

        url = _ARXIV_PDF_URL.format(arxiv_id)
        try:
            response = httpx.get(url, follow_redirects=True, timeout=30.0)
            response.raise_for_status()
        except Exception as exc:
            _log.warning("arxiv_fetch_failed", arxiv_id=arxiv_id, error=str(exc))
            return None

        cache_path.write_bytes(response.content)
        _log.info("arxiv_downloaded", arxiv_id=arxiv_id, bytes=len(response.content))
        return cache_path
