from __future__ import annotations

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

from papertriage.cluster.clusterer import _make_label
from papertriage.cluster.schema import Cluster
from papertriage.extract.schema import Paper

_MODEL_NAME = "all-MiniLM-L6-v2"


class EmbeddingClusterer:
    name = "embedding"

    def __init__(self, model_name: str = _MODEL_NAME) -> None:
        self._model_name = model_name

    def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for EmbeddingClusterer. "
                'Install with: pip install -e ".[embeddings]"'
            ) from None
        return SentenceTransformer(self._model_name)

    def cluster(self, papers: list[Paper], n_clusters: int | None = None) -> list[Cluster]:
        if len(papers) < 4:
            return [Cluster(id=0, label="all", paper_ids=[p.id for p in papers], keywords=[])]

        n = n_clusters if n_clusters is not None else min(4, len(papers) // 2)
        n = max(1, min(n, len(papers)))

        corpus = [
            p.problem + " " + p.method + " " + " ".join(p.contributions)
            for p in papers
        ]

        model = self._load_model()
        embeddings: np.ndarray = model.encode(corpus, normalize_embeddings=True)
        embeddings_f32 = embeddings.astype(np.float32)

        # FAISS index stores embeddings; V3 will add persistence via IndexIVFFlat
        try:
            import faiss
        except ImportError:
            raise ImportError(
                "faiss-cpu is required for EmbeddingClusterer. "
                'Install with: pip install -e ".[embeddings]"'
            ) from None

        dim = embeddings_f32.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(embeddings_f32)
        # Vectors are stored flat in index.xb; retrieve for clustering
        vectors = np.array([index.reconstruct(i) for i in range(index.ntotal)])

        # Ward linkage on L2-normalized vectors approximates cosine distance
        agg = AgglomerativeClustering(n_clusters=n, metric="euclidean", linkage="ward")
        labels: np.ndarray = agg.fit_predict(vectors)

        # Keywords via TF-IDF on each cluster's subset (keeps labels interpretable)
        vec = TfidfVectorizer(stop_words="english", max_features=5000, ngram_range=(1, 2))
        X_tfidf: np.ndarray = vec.fit_transform(corpus).toarray()
        feature_names: np.ndarray = vec.get_feature_names_out()

        clusters: list[Cluster] = []
        for cid in range(n):
            mask = labels == cid
            paper_ids = [papers[i].id for i in range(len(papers)) if mask[i]]
            if not paper_ids:
                continue

            cluster_X = X_tfidf[mask]
            mean_scores: np.ndarray = cluster_X.mean(axis=0)
            top_indices = mean_scores.argsort()[-3:][::-1]
            keywords = [feature_names[i] for i in top_indices if mean_scores[i] > 0]

            label = _make_label(keywords, cid)

            clusters.append(Cluster(id=cid, label=label, paper_ids=paper_ids, keywords=keywords))

        clusters.sort(key=lambda c: len(c.paper_ids), reverse=True)
        return clusters
