import pytest

from papertriage.extract.extractor import extract
from papertriage.extract.schema import Paper
from papertriage.ingest.schema import RawPaper


def test_extract_happy_path(sample_raw_paper: RawPaper, fake_client, golden_paper: Paper):
    result = extract(sample_raw_paper, fake_client)

    assert result.id == sample_raw_paper.id
    assert result.title == golden_paper.title
    assert result.authors == golden_paper.authors
    assert result.year == golden_paper.year
    assert result.method == golden_paper.method
    assert len(result.contributions) == len(golden_paper.contributions)
    assert result.datasets == golden_paper.datasets


def test_extract_sets_id_from_raw(sample_raw_paper: RawPaper, fake_client):
    result = extract(sample_raw_paper, fake_client)
    assert result.id == sample_raw_paper.id


def test_extract_failure_returns_sentinel(sample_raw_paper: RawPaper, fake_client_failing):
    result = extract(sample_raw_paper, fake_client_failing)

    assert isinstance(result, Paper)
    assert result.id == sample_raw_paper.id
    assert result.title == "<extraction failed>"
    assert result.authors == []
    assert result.year is None


def test_extract_truncates_long_text(fake_client):
    long_text = "word " * 5000  # well over 8000 chars
    raw = RawPaper(id="x", path=__file__, raw_text=long_text, char_count=len(long_text))
    # Should not raise; client will receive truncated content
    result = extract(raw, fake_client)
    assert result.id == "x"
    # The fake client returns the golden fixture regardless, so title should be set
    assert result.title != ""
