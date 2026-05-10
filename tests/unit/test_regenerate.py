"""Tests for orchestration/regenerate.py."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import pytest

from papertriage.cluster.schema import Cluster
from papertriage.extract.schema import Paper
from papertriage.orchestration.regenerate import _apply_overrides, regenerate

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_P1 = Paper(
    id="paper1",
    title="Alpha Paper",
    problem="some problem",
    method="some method",
    contributions=["contribution A"],
)
_P2 = Paper(
    id="paper2",
    title="Beta Paper",
    problem="another problem",
    method="another method",
    contributions=["contribution B"],
)
_P3_FAILED = Paper(
    id="paper3",
    title="<extraction failed>",
    problem="",
    method="",
    contributions=[],
)

_CLUSTERS = [
    Cluster(id=0, label="Cluster Zero", paper_ids=["paper1", "paper2", "paper3"], keywords=[]),
    Cluster(id=1, label="Cluster One", paper_ids=["paper1"], keywords=[]),
]

# ---------------------------------------------------------------------------
# _apply_overrides unit tests
# ---------------------------------------------------------------------------


def test_excluded_paper_removed_from_active_papers():
    review = {"paper_overrides": {"paper2": {"included": False}}, "cluster_overrides": {}}
    active_papers, _ = _apply_overrides([_P1, _P2], _CLUSTERS, review)
    assert all(p.id != "paper2" for p in active_papers)


def test_extraction_failed_papers_always_excluded():
    review = {"paper_overrides": {}, "cluster_overrides": {}}
    active_papers, _ = _apply_overrides([_P1, _P2, _P3_FAILED], _CLUSTERS, review)
    assert all(p.id != "paper3" for p in active_papers)


def test_excluded_paper_removed_from_cluster_paper_ids():
    review = {"paper_overrides": {"paper2": {"included": False}}, "cluster_overrides": {}}
    _, active_clusters = _apply_overrides([_P1, _P2], _CLUSTERS, review)
    cluster0 = next(c for c in active_clusters if c.id == 0)
    assert "paper2" not in cluster0.paper_ids


def test_cluster_becomes_empty_when_all_papers_excluded():
    review = {"paper_overrides": {"paper1": {"included": False}}, "cluster_overrides": {}}
    _, active_clusters = _apply_overrides([_P1], [_CLUSTERS[1]], review)
    # Cluster 1 only had paper1; with paper1 excluded it should vanish
    assert len(active_clusters) == 0


def test_cluster_label_override_applied():
    review = {
        "paper_overrides": {},
        "cluster_overrides": {"0": {"label": "Overridden Label"}},
    }
    _, active_clusters = _apply_overrides([_P1, _P2], _CLUSTERS, review)
    cluster0 = next(c for c in active_clusters if c.id == 0)
    assert cluster0.label == "Overridden Label"


def test_cluster_label_unchanged_without_override():
    review = {"paper_overrides": {}, "cluster_overrides": {}}
    _, active_clusters = _apply_overrides([_P1, _P2], _CLUSTERS, review)
    cluster0 = next(c for c in active_clusters if c.id == 0)
    assert cluster0.label == "Cluster Zero"


# ---------------------------------------------------------------------------
# regenerate() integration test (uses FakeClaudeClient)
# ---------------------------------------------------------------------------

_REPORT_MARKDOWN = "# Regenerated\n\nSome synthesis text [paper1].\n"
_CRITIQUE_RESPONSE = {
    "findings": [],
    "overall_assessment": "Looks good after regeneration.",
}


class _FakeClaude:
    _CRITIQUE_TOOLS = {
        "critique_review",
        "factuality_findings",
        "coverage_findings",
        "novelty_findings",
    }

    @contextmanager
    def run(self, run_id: str):
        yield

    def call_tool(self, model, system, messages, tool, cached_blocks=None):
        return dict(_CRITIQUE_RESPONSE)

    def call_text(self, model, system, messages, cached_blocks=None):
        return _REPORT_MARKDOWN

    def get_run_cost(self, run_id: str) -> float:
        return 0.0


@pytest.fixture()
def _settings(tmp_path):
    from types import SimpleNamespace
    return SimpleNamespace(output_dir=tmp_path / "outputs", model_synthesis="claude-sonnet-4-6")


@pytest.fixture()
def _run_dir(tmp_path):
    """Create a minimal existing run directory with all required artifacts."""
    run_dir = tmp_path / "outputs" / "20260510_120000_abc12345"
    run_dir.mkdir(parents=True)

    (run_dir / "papers.json").write_text(
        json.dumps([_P1.model_dump(), _P2.model_dump()]),
        encoding="utf-8",
    )
    (run_dir / "clusters.json").write_text(
        json.dumps([c.model_dump() for c in _CLUSTERS]),
        encoding="utf-8",
    )
    (run_dir / "meta.json").write_text(
        json.dumps({"question": "What methods work?", "run_id": "20260510_120000_abc12345"}),
        encoding="utf-8",
    )
    return run_dir


def test_regenerate_writes_to_subdir_not_original(_run_dir, _settings):
    run_id = _run_dir.name
    ctx = regenerate(run_id, _FakeClaude(), _settings)

    # Output must be inside a regenerated_* subdirectory
    assert ctx.output_dir.parent == _run_dir
    assert ctx.output_dir.name.startswith("regenerated_")


def test_regenerate_original_artifacts_unchanged(_run_dir, _settings):
    original_papers = (_run_dir / "papers.json").read_text(encoding="utf-8")
    original_clusters = (_run_dir / "clusters.json").read_text(encoding="utf-8")

    regenerate(_run_dir.name, _FakeClaude(), _settings)

    assert (_run_dir / "papers.json").read_text(encoding="utf-8") == original_papers
    assert (_run_dir / "clusters.json").read_text(encoding="utf-8") == original_clusters


def test_regenerate_excluded_paper_not_in_synthesis_input(_run_dir, _settings):
    (_run_dir / "review.json").write_text(
        json.dumps({"paper_overrides": {"paper2": {"included": False}}, "cluster_overrides": {}}),
        encoding="utf-8",
    )

    captured_papers: list = []
    original_synthesize = None

    import papertriage.synthesize.synthesizer as _synth_mod

    original_synthesize = _synth_mod.synthesize

    def _capturing_synthesize(question, clusters, papers, claude):
        captured_papers.extend(papers)
        from papertriage.synthesize.schema import Citation, Report
        return Report(markdown=_REPORT_MARKDOWN, citations=[])

    _synth_mod.synthesize = _capturing_synthesize
    try:
        regenerate(_run_dir.name, _FakeClaude(), _settings)
    finally:
        _synth_mod.synthesize = original_synthesize

    assert all(p.id != "paper2" for p in captured_papers)


def test_regenerate_cluster_label_override_reaches_synthesizer(_run_dir, _settings):
    (_run_dir / "review.json").write_text(
        json.dumps(
            {"paper_overrides": {}, "cluster_overrides": {"0": {"label": "My Custom Label"}}}
        ),
        encoding="utf-8",
    )

    captured_clusters: list = []
    import papertriage.synthesize.synthesizer as _synth_mod

    original_synthesize = _synth_mod.synthesize

    def _capturing_synthesize(question, clusters, papers, claude):
        captured_clusters.extend(clusters)
        from papertriage.synthesize.schema import Citation, Report
        return Report(markdown=_REPORT_MARKDOWN, citations=[])

    _synth_mod.synthesize = _capturing_synthesize
    try:
        regenerate(_run_dir.name, _FakeClaude(), _settings)
    finally:
        _synth_mod.synthesize = original_synthesize

    cluster0 = next(c for c in captured_clusters if c.id == 0)
    assert cluster0.label == "My Custom Label"
