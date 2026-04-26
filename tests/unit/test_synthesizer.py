from contextlib import contextmanager

from papertriage.cluster.schema import Cluster
from papertriage.extract.schema import Paper
from papertriage.synthesize.synthesizer import synthesize


class _FakeTextClient:
    def __init__(self, text: str) -> None:
        self._text = text

    @contextmanager
    def run(self, run_id: str):
        yield

    def call_text(self, model, system, messages, cached_blocks=None) -> str:
        return self._text

    def get_run_cost(self, run_id: str) -> float:
        return 0.0


def test_synthesize_returns_report_with_markdown_and_citations():
    paper1 = Paper(id="abcdef0123456789abcdef0123456789abcdef01", title="Paper A", method="method A")
    paper2 = Paper(id="deadbeef99887766deadbeef99887766deadbeef", title="Paper B", method="method B")
    cluster = Cluster(id=0, label="Group 1", paper_ids=["abcdef01", "deadbeef"], keywords=["ml"])

    # 8-char short IDs match what _build_papers_block emits after Fix 2
    canned = (
        "This survey covers [abcdef01] as a key contribution. "
        "Secondary work [deadbeef] also applies."
    )
    client = _FakeTextClient(canned)

    report = synthesize("What are recent methods?", [cluster], [paper1, paper2], client)

    assert report.markdown == canned
    assert len(report.citations) >= 1
    assert any(c.paper_id == "abcdef01" for c in report.citations)


def test_synthesize_no_citations_when_no_brackets():
    paper = Paper(id="aaaa0000bbbb1111aaaa0000bbbb1111aaaa0000", title="Paper X", method="svm")
    cluster = Cluster(id=0, label="Group", paper_ids=["aaaa0000"], keywords=[])

    client = _FakeTextClient("A plain narrative with no inline citations.")

    report = synthesize("Question?", [cluster], [paper], client)

    assert report.markdown != ""
    assert report.citations == []
