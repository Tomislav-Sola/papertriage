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

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def _make_source(tmp_path: Path, ids: list[str]) -> ArxivSource:
    return ArxivSource(ids, _FakeSettings(tmp_path))


def test_arxiv_happy_path(tmp_path):
    fake_pdf = b"%PDF-1.4 fake content"

    with patch("papertriage.sources.arxiv.httpx.get") as mock_get:
        mock_get.return_value = _FakeResponse(fake_pdf)
        paths = _make_source(tmp_path, ["2401.15884"]).fetch()

    assert len(paths) == 1
    assert paths[0].exists()
    assert paths[0].read_bytes() == fake_pdf
    mock_get.assert_called_once()


def test_arxiv_cache_hit(tmp_path):
    fake_pdf = b"%PDF-1.4 cached"

    cache_dir = tmp_path / ".arxiv_cache"
    cache_dir.mkdir()
    (cache_dir / "2401.15884.pdf").write_bytes(fake_pdf)

    with patch("papertriage.sources.arxiv.httpx.get") as mock_get:
        paths = _make_source(tmp_path, ["2401.15884"]).fetch()

    mock_get.assert_not_called()
    assert len(paths) == 1
    assert paths[0].read_bytes() == fake_pdf


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
    fake_pdf = b"%PDF-1.4 real"

    def _side_effect(url, **kwargs):
        if "9999.99999" in url:
            raise ConnectionError("bad")
        return _FakeResponse(fake_pdf)

    with patch("papertriage.sources.arxiv.httpx.get", side_effect=_side_effect):
        paths = _make_source(tmp_path, ["9999.99999", "2401.15884"]).fetch()

    assert len(paths) == 1
    assert paths[0].name == "2401.15884.pdf"
