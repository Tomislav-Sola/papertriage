from pathlib import Path

import pytest

from papertriage.extract.cache import ExtractionCache
from papertriage.extract.schema import Paper
from papertriage.ingest.schema import RawPaper


class _FakeSettings:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir


def _make_cache(tmp_path: Path) -> ExtractionCache:
    return ExtractionCache(_FakeSettings(tmp_path))


def _sample_paper(paper_id: str = "abc123") -> Paper:
    return Paper(
        id=paper_id,
        title="Test Paper",
        authors=["Alice"],
        year=2024,
        method="transformer",
        problem="test problem",
        contributions=["contribution 1"],
    )


def test_cache_miss_returns_none(tmp_path):
    cache = _make_cache(tmp_path)
    assert cache.get("nonexistent") is None
    assert cache.misses == 1


def test_cache_set_and_get(tmp_path):
    cache = _make_cache(tmp_path)
    paper = _sample_paper()
    cache.set("abc123", paper)
    retrieved = cache.get("abc123")
    assert retrieved is not None
    assert retrieved.id == paper.id
    assert retrieved.title == paper.title
    assert cache.hits == 1


def test_cache_hit_skips_llm(tmp_path, fake_client):
    from papertriage.extract.extractor import extract

    cache = _make_cache(tmp_path)
    cached_paper = _sample_paper("paper-id")
    cache.set("paper-id", cached_paper)

    raw = RawPaper(id="paper-id", path=Path("fake.pdf"), raw_text="some text", char_count=9)
    result = extract(raw, fake_client, cache=cache)

    assert result.id == "paper-id"
    assert result.title == cached_paper.title
    assert len(fake_client.calls) == 0


def test_cache_miss_calls_llm_and_stores(tmp_path, fake_client):
    from papertriage.extract.extractor import extract

    cache = _make_cache(tmp_path)
    raw = RawPaper(id="new-paper", path=Path("fake.pdf"), raw_text="some text", char_count=9)

    extract(raw, fake_client, cache=cache)

    assert len(fake_client.calls) == 1
    assert cache.get("new-paper") is not None


def test_cache_clear_forces_miss(tmp_path, fake_client):
    from papertriage.extract.extractor import extract

    cache = _make_cache(tmp_path)
    cached_paper = _sample_paper("paper-id")
    cache.set("paper-id", cached_paper)
    cache.clear()

    raw = RawPaper(id="paper-id", path=Path("fake.pdf"), raw_text="some text", char_count=9)
    extract(raw, fake_client, cache=cache)

    assert len(fake_client.calls) == 1


def test_cache_files_survive_new_instance(tmp_path):
    cache1 = _make_cache(tmp_path)
    paper = _sample_paper("xyz")
    cache1.set("xyz", paper)

    cache2 = _make_cache(tmp_path)
    retrieved = cache2.get("xyz")
    assert retrieved is not None
    assert retrieved.title == paper.title
