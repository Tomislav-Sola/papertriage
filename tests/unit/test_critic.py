from contextlib import contextmanager

from papertriage.critique.critic import critique
from papertriage.critique.schema import Critique, Severity
from papertriage.extract.schema import Paper
from papertriage.synthesize.schema import Report


class _FakeToolClient:
    def __init__(self, response: dict) -> None:
        self._response = response

    @contextmanager
    def run(self, run_id: str):
        yield

    def call_tool(self, model, system, messages, tool, cached_blocks=None) -> dict:
        return dict(self._response)

    def get_run_cost(self, run_id: str) -> float:
        return 0.0


_CANNED_CRITIQUE = {
    "findings": [
        {
            "claim": "Method A strictly outperforms all baselines",
            "severity": "medium",
            "reason": "No statistical significance tests are reported",
            "suggested_fix": "Add p-values or confidence intervals",
        }
    ],
    "overall_assessment": "Mostly sound with one unsupported comparative claim.",
}


def test_critique_returns_critique_with_expected_structure():
    paper1 = Paper(id="abc123", title="Paper A", method="method A")
    paper2 = Paper(id="def456", title="Paper B", method="method B")
    report = Report(
        markdown="Method A [abc123] outperforms all baselines [def456].",
        citations=[],
    )

    result = critique(report, [paper1, paper2], _FakeToolClient(_CANNED_CRITIQUE))

    assert isinstance(result, Critique)
    assert isinstance(result.findings, list)
    assert isinstance(result.overall_assessment, str)
    assert result.overall_assessment != ""
    assert len(result.findings) == 1
    assert result.findings[0].severity == Severity.medium


def test_critique_handles_empty_findings():
    paper = Paper(id="abc123", title="Paper A", method="method A")
    report = Report(markdown="Well-supported synthesis.", citations=[])
    # Use single-pass mode to exercise the legacy path with its exact overall_assessment
    canned = {"findings": [], "overall_assessment": "No issues found."}

    result = critique(report, [paper], _FakeToolClient(canned), mode="single")

    assert isinstance(result, Critique)
    assert result.findings == []
    assert result.overall_assessment == "No issues found."
