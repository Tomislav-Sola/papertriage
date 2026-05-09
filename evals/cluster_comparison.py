"""Head-to-head eval: TF-IDF clusterer vs. Embedding clusterer.

Usage:
    python -m evals.cluster_comparison

Requires the [embeddings] optional extra for the embedding clusterer:
    pip install -e ".[embeddings]"

Outputs a Rich table comparing both clusterers on:
  - Adjusted Rand Index (vs. human-labelled grouping)
  - Number of clusters produced
  - Intra-cluster cohesion (mean pairwise cosine similarity, TF-IDF vectors)
  - Wall-clock run time
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from rich.console import Console
from rich.table import Table
from sklearn.metrics import adjusted_rand_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

from papertriage.extract.schema import Paper

DATASET_PATH = Path(__file__).parent / "datasets" / "cluster_eval" / "expected_clusters.json"


def _load_dataset() -> tuple[list[Paper], dict[str, str]]:
    data = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    papers = [
        Paper(
            id=p["id"],
            title=p["title"],
            problem=p["problem"],
            method=p["method"],
            contributions=p["contributions"],
        )
        for p in data["papers"]
    ]
    expected: dict[str, str] = data["expected"]
    return papers, expected


def _labels_to_int(paper_ids: list[str], assignment: dict[str, str]) -> list[int]:
    """Convert string cluster labels to integer array aligned to paper_ids order."""
    unique_labels = sorted(set(assignment.values()))
    label_to_int = {label: i for i, label in enumerate(unique_labels)}
    return [label_to_int[assignment[pid]] for pid in paper_ids]


def _clusterer_to_assignment(papers: list[Paper], clusters) -> dict[str, str]:
    """Convert a list[Cluster] to paper_id → cluster_label mapping."""
    return {pid: cluster.label for cluster in clusters for pid in cluster.paper_ids}


def _intra_cohesion(papers: list[Paper], clusters) -> float:
    """Mean intra-cluster pairwise cosine similarity using TF-IDF vectors."""
    corpus = [p.problem + " " + p.method + " " + " ".join(p.contributions) for p in papers]
    vec = TfidfVectorizer(stop_words="english", max_features=5000)
    X = vec.fit_transform(corpus).toarray()
    id_to_idx = {p.id: i for i, p in enumerate(papers)}

    sims: list[float] = []
    for cluster in clusters:
        indices = [id_to_idx[pid] for pid in cluster.paper_ids if pid in id_to_idx]
        if len(indices) < 2:
            continue
        sub = X[indices]
        sim_matrix = cosine_similarity(sub)
        # Upper triangle only (no self-similarity)
        n = len(indices)
        upper = [sim_matrix[i, j] for i in range(n) for j in range(i + 1, n)]
        sims.extend(upper)

    return float(np.mean(sims)) if sims else 0.0


def _run_clusterer(name: str, papers: list[Paper], n_clusters: int | None = None) -> tuple[list, float]:
    if name == "tfidf":
        from papertriage.cluster.clusterer import TfidfClusterer
        cl = TfidfClusterer()
    else:
        from papertriage.cluster.embedding import EmbeddingClusterer
        cl = EmbeddingClusterer()

    t0 = time.perf_counter()
    clusters = cl.cluster(papers, n_clusters=n_clusters)
    elapsed = time.perf_counter() - t0
    return clusters, elapsed


def main() -> None:
    console = Console()
    console.print("[bold]Loading cluster eval dataset…[/bold]")
    papers, expected = _load_dataset()
    paper_ids = [p.id for p in papers]
    true_labels = _labels_to_int(paper_ids, expected)

    table = Table(title="Clusterer Comparison", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("TF-IDF", justify="right")
    table.add_column("Embedding", justify="right")

    n_expected = len(set(expected.values()))
    console.print(f"Human-labelled clusters: [bold]{n_expected}[/bold]\n")

    results: dict[str, dict] = {}
    for name in ("tfidf", "embedding"):
        console.print(f"Running [cyan]{name}[/cyan] clusterer…")
        try:
            clusters, elapsed = _run_clusterer(name, papers, n_clusters=n_expected)
        except ImportError as exc:
            console.print(f"[yellow]Skipping {name}: {exc}[/yellow]")
            results[name] = None
            continue

        assignment = _clusterer_to_assignment(papers, clusters)
        pred_labels = _labels_to_int(paper_ids, assignment)
        ari = adjusted_rand_score(true_labels, pred_labels)
        cohesion = _intra_cohesion(papers, clusters)

        results[name] = {
            "ari": ari,
            "n_clusters": len(clusters),
            "cohesion": cohesion,
            "elapsed_s": elapsed,
        }

    def _fmt(name: str, key: str, fmt: str) -> str:
        if results.get(name) is None:
            return "[dim]n/a[/dim]"
        return format(results[name][key], fmt)

    table.add_row("Adjusted Rand Index ↑", _fmt("tfidf", "ari", ".3f"), _fmt("embedding", "ari", ".3f"))
    table.add_row("Clusters produced", _fmt("tfidf", "n_clusters", "d"), _fmt("embedding", "n_clusters", "d"))
    table.add_row("Intra-cluster cohesion ↑", _fmt("tfidf", "cohesion", ".3f"), _fmt("embedding", "cohesion", ".3f"))
    table.add_row("Wall-clock time (s)", _fmt("tfidf", "elapsed_s", ".2f"), _fmt("embedding", "elapsed_s", ".2f"))

    console.print(table)
    console.print(
        "\n[dim]ARI = 1.0 means perfect agreement with human labels. "
        "See evals/datasets/cluster_eval/README.md for methodology notes.[/dim]"
    )


if __name__ == "__main__":
    main()
