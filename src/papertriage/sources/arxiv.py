import json
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from papertriage.core.config import Settings
from papertriage.core.logging import get_logger

_log = get_logger(__name__)
_ARXIV_PDF_URL = "https://arxiv.org/pdf/{}"
_ARXIV_API_URL = "https://export.arxiv.org/api/query?id_list={}"
_ATOM_NS = "http://www.w3.org/2005/Atom"


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
        meta_path = self._cache_dir / f"{arxiv_id}.meta.json"

        if not cache_path.exists():
            url = _ARXIV_PDF_URL.format(arxiv_id)
            try:
                response = httpx.get(url, follow_redirects=True, timeout=30.0)
                response.raise_for_status()
            except Exception as exc:
                _log.warning("arxiv_fetch_failed", arxiv_id=arxiv_id, error=str(exc))
                return None
            cache_path.write_bytes(response.content)
            _log.info("arxiv_downloaded", arxiv_id=arxiv_id, bytes=len(response.content))
        else:
            _log.info("arxiv_cache_hit", arxiv_id=arxiv_id)

        if not meta_path.exists():
            self._fetch_meta(arxiv_id, meta_path)

        return cache_path

    def _fetch_meta(self, arxiv_id: str, dest: Path) -> None:
        try:
            response = httpx.get(
                _ARXIV_API_URL.format(arxiv_id), follow_redirects=True, timeout=10.0
            )
            response.raise_for_status()
            root = ET.fromstring(response.text)
            entry = root.find(f"{{{_ATOM_NS}}}entry")
            if entry is None:
                return
            title_el = entry.find(f"{{{_ATOM_NS}}}title")
            title = title_el.text.strip().replace("\n", " ") if title_el is not None and title_el.text else ""
            if title:
                dest.write_text(json.dumps({"Title": title}), encoding="utf-8")
                _log.info("arxiv_meta_fetched", arxiv_id=arxiv_id, title=title)
        except Exception as exc:
            _log.warning("arxiv_meta_fetch_failed", arxiv_id=arxiv_id, error=str(exc))
