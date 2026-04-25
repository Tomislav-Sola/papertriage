from papertriage.cluster.clusterer import cluster
from papertriage.extract.schema import Paper


def _make_paper(pid: str, problem: str, method: str, contributions: list[str]) -> Paper:
    return Paper(id=pid, title=pid, problem=problem, method=method, contributions=contributions)


def test_single_paper_returns_one_cluster_labelled_all():
    papers = [_make_paper("p1", "question answering", "retrieval", ["fast QA"])]
    result = cluster(papers)
    assert len(result) == 1
    assert result[0].label == "all"
    assert result[0].paper_ids == ["p1"]
    assert result[0].keywords == []


def test_three_papers_returns_one_cluster_labelled_all():
    papers = [
        _make_paper("p1", "machine translation", "seq2seq", ["encoder decoder"]),
        _make_paper("p2", "language modelling", "transformer", ["attention mechanism"]),
        _make_paper("p3", "text classification", "bert", ["fine tuning"]),
    ]
    result = cluster(papers)
    assert len(result) == 1
    assert result[0].label == "all"


def test_six_distinct_papers_produce_multiple_clusters():
    nlp_papers = [
        _make_paper(
            f"nlp{i}",
            "natural language processing text understanding semantics",
            "transformer bert language model attention",
            ["language representation", "text classification", "semantic similarity"],
        )
        for i in range(3)
    ]
    vision_papers = [
        _make_paper(
            f"vis{i}",
            "image recognition convolutional neural network visual features",
            "resnet convolutional pooling batch normalisation",
            ["image classification", "object detection", "feature extraction"],
        )
        for i in range(3)
    ]
    papers = nlp_papers + vision_papers
    result = cluster(papers)
    assert len(result) >= 2


def test_clusters_sorted_by_size_descending():
    # 4 papers in one topic, 4 in another → n_clusters defaults to min(4, 8//2) = 4
    # but we just need the largest cluster first regardless of n
    papers = [
        _make_paper(
            f"nlp{i}",
            "natural language text corpus vocabulary token",
            "bert transformer encoder",
            ["text classification", "sentence embedding"],
        )
        for i in range(6)
    ] + [
        _make_paper(
            "vis0",
            "image pixel convolutional visual recognition",
            "resnet cnn pooling",
            ["object detection"],
        )
    ]
    result = cluster(papers)
    sizes = [len(c.paper_ids) for c in result]
    assert sizes == sorted(sizes, reverse=True)
