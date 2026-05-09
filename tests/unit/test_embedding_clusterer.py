import pytest

from papertriage.extract.schema import Paper

sentence_transformers = pytest.importorskip(
    "sentence_transformers",
    reason="sentence-transformers not installed; install with pip install -e '.[embeddings]'",
)

from papertriage.cluster.embedding import EmbeddingClusterer  # noqa: E402


def _make_paper(pid: str, problem: str, method: str, contributions: list[str]) -> Paper:
    return Paper(id=pid, title=pid, problem=problem, method=method, contributions=contributions)


_RAG_PAPERS = [
    _make_paper(
        "rag1",
        "question answering over documents using retrieval augmented generation",
        "dense retrieval with FAISS index and reader model",
        ["retrieval augmented QA", "open domain question answering"],
    ),
    _make_paper(
        "rag2",
        "improving factuality in language models via retrieved context",
        "RAG pipeline with bi-encoder retrieval",
        ["hallucination reduction", "knowledge grounding"],
    ),
    _make_paper(
        "rag3",
        "document retrieval for knowledge-intensive NLP tasks",
        "sparse and dense hybrid retrieval augmented generation",
        ["knowledge intensive NLP", "retrieval augmented generation"],
    ),
]

_RL_PAPERS = [
    _make_paper(
        "rl1",
        "reinforcement learning from human feedback for language model alignment",
        "proximal policy optimisation with reward model",
        ["RLHF alignment", "policy gradient training"],
    ),
    _make_paper(
        "rl2",
        "reward shaping in deep reinforcement learning for sparse reward environments",
        "actor critic with intrinsic motivation reward signal",
        ["sparse reward", "intrinsic motivation", "policy optimisation"],
    ),
    _make_paper(
        "rl3",
        "multi agent reinforcement learning for cooperative tasks",
        "centralised critic decentralised actor MARL",
        ["multi agent RL", "cooperative policy learning"],
    ),
]


@pytest.mark.slow
def test_two_topic_groups_produce_multiple_clusters():
    papers = _RAG_PAPERS + _RL_PAPERS
    cl = EmbeddingClusterer()
    result = cl.cluster(papers)
    assert len(result) >= 2, f"Expected >=2 clusters, got {len(result)}"


@pytest.mark.slow
def test_single_paper_returns_one_cluster_labelled_all():
    papers = [_make_paper("solo", "some problem", "some method", ["contribution"])]
    cl = EmbeddingClusterer()
    result = cl.cluster(papers)
    assert len(result) == 1
    assert result[0].label == "all"
    assert result[0].paper_ids == ["solo"]
    assert result[0].keywords == []


@pytest.mark.slow
def test_deterministic_across_runs():
    papers = _RAG_PAPERS + _RL_PAPERS
    cl = EmbeddingClusterer()
    result_a = cl.cluster(papers)
    result_b = cl.cluster(papers)
    ids_a = [sorted(c.paper_ids) for c in result_a]
    ids_b = [sorted(c.paper_ids) for c in result_b]
    assert ids_a == ids_b, "EmbeddingClusterer output is not deterministic"
