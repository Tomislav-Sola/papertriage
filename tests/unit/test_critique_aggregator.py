from contextlib import contextmanager

import pytest

from papertriage.critique.aggregator import deduplicate, run as aggregator_run
from papertriage.critique.schema import Finding, Severity
from papertriage.extract.schema import Paper
from papertriage.synthesize.schema import Citation, Report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _finding(claim: str, severity: str = "low", source: str = "factuality") -> Finding:
    return Finding(
        claim=claim,
        severity=Severity(severity),
        reason="test reason",
        suggested_fix="test fix",
        source_critic=source,
    )


def _make_report() -> Report:
    return Report(markdown="# Test\n\nSome synthesis text.", citations=[])


def _make_papers() -> list[Paper]:
    return [
        Paper(
            id="p1",
            title="Paper One",
            problem="some problem",
            method="some method",
            contributions=["contribution"],
        )
    ]


class _SequentialFake:
    """Returns a different dict response on each successive call_tool() call."""

    def __init__(self, responses: list[dict]) -> None:
        self._responses = responses
        self._idx = 0
        self.calls: list[str] = []

    @contextmanager
    def run(self, run_id: str):
        yield

    def call_tool(self, model, system, messages, tool, cached_blocks=None):
        self.calls.append(tool["name"])
        resp = self._responses[self._idx % len(self._responses)]
        self._idx += 1
        return resp

    def call_text(self, model, system, messages, cached_blocks=None):
        return ""

    def get_run_cost(self, run_id):
        return 0.0


# ---------------------------------------------------------------------------
# deduplicate() unit tests (pure logic, no LLM)
# ---------------------------------------------------------------------------

def test_dedup_removes_near_identical_claim():
    f1 = _finding("The paper claims that retrieval improves factual accuracy significantly")
    f2 = _finding("The paper claims that retrieval improves factual accuracy significantly")
    result = deduplicate([f1, f2])
    assert len(result) == 1


def test_dedup_keeps_highest_severity_on_collision():
    f_low = _finding("RAG method achieves state-of-the-art results on the benchmark", severity="low")
    f_high = _finding("RAG method achieves state-of-the-art results on the benchmark", severity="high")
    result = deduplicate([f_low, f_high])
    assert len(result) == 1
    assert result[0].severity == Severity.high


def test_dedup_highest_severity_wins_regardless_of_order():
    f_high = _finding("Transformer outperforms all prior models on every task", severity="high")
    f_medium = _finding("Transformer outperforms all prior models on every task", severity="medium")
    result = deduplicate([f_high, f_medium])
    assert len(result) == 1
    assert result[0].severity == Severity.high


def test_dedup_preserves_distinct_claims():
    f1 = _finding("The model achieves 95% accuracy on dataset X")
    f2 = _finding("Coverage of the limitations section is missing from the review")
    result = deduplicate([f1, f2])
    assert len(result) == 2


def test_dedup_empty_input():
    assert deduplicate([]) == []


# ---------------------------------------------------------------------------
# aggregator.run() integration test (three FakeClients, one per critic)
# ---------------------------------------------------------------------------

def test_all_three_critics_are_called():
    factuality_response = {
        "findings": [
            {
                "claim": "The paper reports 98% accuracy but no such figure appears in the source",
                "severity": "high",
                "reason": "Fabricated number",
                "suggested_fix": "Remove or verify the statistic",
                "source_critic": None,
            }
        ]
    }
    coverage_response = {
        "findings": [
            {
                "claim": "Paper p2 is cited but its contributions are never discussed",
                "severity": "medium",
                "reason": "Missing engagement",
                "suggested_fix": "Add a sentence about p2's contribution",
                "source_critic": None,
            }
        ]
    }
    novelty_response = {"findings": []}

    fake = _SequentialFake([factuality_response, coverage_response, novelty_response])

    with fake.run("test-run"):
        result = aggregator_run(_make_report(), _make_papers(), fake)

    assert len(fake.calls) == 3
    assert "factuality_findings" in fake.calls
    assert "coverage_findings" in fake.calls
    assert "novelty_findings" in fake.calls

    assert len(result.findings) == 2
    sources = {f.source_critic for f in result.findings}
    assert "factuality" in sources
    assert "coverage" in sources
    assert result.overall_assessment.startswith("Synthesized from 3 critic passes")


def test_aggregator_deduplicates_across_critics():
    duplicate_claim = "The paper claims retrieval improves factual accuracy"
    factuality_response = {
        "findings": [
            {
                "claim": duplicate_claim,
                "severity": "low",
                "reason": "reason",
                "suggested_fix": "fix",
                "source_critic": None,
            }
        ]
    }
    coverage_response = {
        "findings": [
            {
                "claim": duplicate_claim,
                "severity": "high",
                "reason": "reason",
                "suggested_fix": "fix",
                "source_critic": None,
            }
        ]
    }
    novelty_response = {"findings": []}

    fake = _SequentialFake([factuality_response, coverage_response, novelty_response])

    with fake.run("test-run"):
        result = aggregator_run(_make_report(), _make_papers(), fake)

    assert len(result.findings) == 1
    assert result.findings[0].severity == Severity.high
