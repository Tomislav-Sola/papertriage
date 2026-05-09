import json
from pathlib import Path
from unittest.mock import patch

import pytest

from papertriage.sources.arxiv import ArxivSource


class _FakeSettings:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir


class _FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


_FAKE_PDF = b"%PDF-1.4 fake content"
_FAKE_META_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<feed xmlns="http://www.w3.org/2005/Atom">'
    "<entry><title>Corrective Retrieval Augmented Generation</title></entry>"
    "</feed>"
).encode()


def _make_source(tmp_path: Path, ids: list[str]) -> ArxivSource:
    return ArxivSource(ids, _FakeSettings(tmp_path))


def _pdf_then_meta(url, **kwargs):
    if "api/query" in url:
        return _FakeResponse(_FAKE_META_XML)
    return _FakeResponse(_FAKE_PDF)


def test_arxiv_happy_path(tmp_path):
    with patch("papertriage.sources.arxiv.httpx.get", side_effect=_pdf_then_meta) as mock_get:
        paths = _make_source(tmp_path, ["2401.15884"]).fetch()

    assert len(paths) == 1
    assert paths[0].exists()
    assert paths[0].read_bytes() == _FAKE_PDF
    assert mock_get.call_count == 2  # PDF download + metadata API

    meta = json.loads((paths[0].parent / "2401.15884.meta.json").read_text())
    assert meta["Title"] == "Corrective Retrieval Augmented Generation"


def test_arxiv_cache_hit(tmp_path):
    cache_dir = tmp_path / ".arxiv_cache"
    cache_dir.mkdir()
    (cache_dir / "2401.15884.pdf").write_bytes(_FAKE_PDF)
    (cache_dir / "2401.15884.meta.json").write_text('{"Title": "Cached Title"}')

    with patch("papertriage.sources.arxiv.httpx.get") as mock_get:
        paths = _make_source(tmp_path, ["2401.15884"]).fetch()

    mock_get.assert_not_called()
    assert len(paths) == 1
    assert paths[0].read_bytes() == _FAKE_PDF


def test_arxiv_404_skipped(tmp_path):
    with patch("papertriage.sources.arxiv.httpx.get") as mock_get:
        mock_get.return_value = _FakeResponse(b"not found", status_code=404)
        paths = _make_source(tmp_path, ["9999.99999"]).fetch()

    assert paths == []


def test_arxiv_network_error_skipped(tmp_path):
    with patch("papertriage.sources.arxiv.httpx.get") as mock_get:
        mock_get.side_effect = ConnectionError("network unreachable")
        paths = _make_source(tmp_path, ["2401.15884"]).fetch()

    assert paths == []


def test_arxiv_partial_failure(tmp_path):
    """One bad ID is skipped; the good ID is still returned."""
    def _side_effect(url, **kwargs):
        if "9999.99999" in url:
            raise ConnectionError("bad")
        if "api/query" in url:
            return _FakeResponse(_FAKE_META_XML)
        return _FakeResponse(_FAKE_PDF)

    with patch("papertriage.sources.arxiv.httpx.get", side_effect=_side_effect):
        paths = _make_source(tmp_path, ["9999.99999", "2401.15884"]).fetch()

    assert len(paths) == 1
    assert paths[0].name == "2401.15884.pdf"
