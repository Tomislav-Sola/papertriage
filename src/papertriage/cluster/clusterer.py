import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

from papertriage.cluster.schema import Cluster
from papertriage.extract.schema import Paper


def cluster(papers: list[Paper], n_clusters: int | None = None) -> list[Cluster]:
    if len(papers) < 4:
        return [Cluster(id=0, label="all", paper_ids=[p.id for p in papers], keywords=[])]

    n = n_clusters if n_clusters is not None else min(4, len(papers) // 2)
    n = max(1, min(n, len(papers)))

    corpus = [
        p.problem + " " + p.method + " " + " ".join(p.contributions)
        for p in papers
    ]

    vec = TfidfVectorizer(stop_words="english", max_features=5000)
    X: np.ndarray = vec.fit_transform(corpus).toarray()
    feature_names: np.ndarray = vec.get_feature_names_out()

    model = AgglomerativeClustering(n_clusters=n, metric="cosine", linkage="average")
    labels: np.ndarray = model.fit_predict(X)

    clusters: list[Cluster] = []
    for cid in range(n):
        mask = labels == cid
        paper_ids = [papers[i].id for i in range(len(papers)) if mask[i]]
        if not paper_ids:
            continue

        cluster_X = X[mask]
        mean_scores: np.ndarray = cluster_X.mean(axis=0)
        top_indices = mean_scores.argsort()[-5:][::-1]
        keywords = [feature_names[i] for i in top_indices if mean_scores[i] > 0]

        label = keywords[0].title() if keywords else f"Cluster {cid}"

        clusters.append(Cluster(id=cid, label=label, paper_ids=paper_ids, keywords=keywords))

    clusters.sort(key=lambda c: len(c.paper_ids), reverse=True)
    return clusters
