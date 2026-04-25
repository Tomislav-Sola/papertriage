import json
from contextlib import contextmanager
from pathlib import Path

import pytest

from papertriage.core.exceptions import BudgetExceededError
from papertriage.extract.schema import Paper
from papertriage.ingest.schema import RawPaper
from papertriage.orchestration.pipeline import run_pipeline

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

_GOLDEN_PAPER = {
    "id": "paper1",
    "title": "Test Paper",
    "authors": ["Alice"],
    "year": 2024,
    "problem": "test problem about retrieval augmented generation",
    "method": "retrieval augmented generation transformer",
    "contributions": ["improved retrieval", "better generation"],
    "limitations": [],
    "datasets": ["TestSet"],
    "key_results": ["+3 F1 on TestSet"],
}

_CRITIQUE_RESPONSE = {
    "findings": [],
    "overall_assessment": "The synthesis is accurate and well-supported.",
}

_REPORT_MARKDOWN = (
    "## Test Cluster\n\n"
    "Retrieval-augmented generation improves QA [paper1].\n\n"
    "## Open Questions\n\nFuture work should explore scaling.\n"
)


class _HappyFakeClaude:
    @contextmanager
    def run(self, run_id: str):
        yield

    def call_tool(self, model, system, messages, tool, cached_blocks=None):
        if tool["name"] == "critique_review":
            return dict(_CRITIQUE_RESPONSE)
        # extract_paper and any other tool → return paper dict
        return dict(_GOLDEN_PAPER)

    def call_text(self, model, system, messages, cached_blocks=None):
        return _REPORT_MARKDOWN

    def get_run_cost(self, run_id: str) -> float:
        return 0.0


class _BudgetFakeClaude:
    """Raises BudgetExceededError when synthesize (call_text) is called."""

    @contextmanager
    def run(self, run_id: str):
        yield

    def call_tool(self, model, system, messages, tool, cached_blocks=None):
        return dict(_GOLDEN_PAPER)

    def call_text(self, model, system, messages, cached_blocks=None):
        raise BudgetExceededError("test-run", 0.50, 0.20)

    def get_run_cost(self, run_id: str) -> float:
        return 0.0


@pytest.fixture()
def _fake_raw_paper() -> RawPaper:
    text = (FIXTURES_DIR / "sample_paper.txt").read_text()
    return RawPaper(id="paper1", path=Path("fake.pdf"), raw_text=text, char_count=len(text))


@pytest.fixture()
def _settings(tmp_path):
    from types import SimpleNamespace
    return SimpleNamespace(
        output_dir=tmp_path / "outputs",
        model_synthesis="claude-sonnet-4-6",
    )


def test_pipeline_writes_all_artifacts(tmp_path, monkeypatch, _fake_raw_paper, _settings):
    monkeypatch.setattr(
        "papertriage.ingest.pdf_reader.read_pdf",
        lambda path: _fake_raw_paper,
    )

    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    (papers_dir / "paper1.pdf").write_bytes(b"fake")

    ctx = run_pipeline(
        papers_dir=papers_dir,
        question="What retrieval methods work best?",
        max_papers=None,
        claude=_HappyFakeClaude(),
        settings=_settings,
    )

    out = ctx.output_dir
    assert (out / "papers.json").exists()
    assert (out / "report.md").exists()
    assert (out / "critique.md").exists()
    assert (out / "cost.json").exists()


def test_pipeline_papers_json_is_valid(tmp_path, monkeypatch, _fake_raw_paper, _settings):
    monkeypatch.setattr(
        "papertriage.ingest.pdf_reader.read_pdf",
        lambda path: _fake_raw_paper,
    )
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    (papers_dir / "paper1.pdf").write_bytes(b"fake")

    ctx = run_pipeline(
        papers_dir=papers_dir,
        question="test question",
        max_papers=None,
        claude=_HappyFakeClaude(),
        settings=_settings,
    )

    papers = json.loads((ctx.output_dir / "papers.json").read_text())
    assert isinstance(papers, list)
    assert len(papers) >= 1
    assert papers[0]["id"] == "paper1"


def test_pipeline_budget_exceeded_writes_partial_artifacts_and_reraises(
    tmp_path, monkeypatch, _fake_raw_paper, _settings
):
    monkeypatch.setattr(
        "papertriage.ingest.pdf_reader.read_pdf",
        lambda path: _fake_raw_paper,
    )
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    (papers_dir / "paper1.pdf").write_bytes(b"fake")

    with pytest.raises(BudgetExceededError):
        run_pipeline(
            papers_dir=papers_dir,
            question="test question",
            max_papers=None,
            claude=_BudgetFakeClaude(),
            settings=_settings,
        )

    # Partial artifacts from stages 1–3 must exist
    outputs = list((tmp_path / "outputs").iterdir())
    assert len(outputs) == 1, "expected exactly one run directory"
    run_dir = outputs[0]
    assert (run_dir / "papers.json").exists()
    assert (run_dir / "cost.json").exists()
