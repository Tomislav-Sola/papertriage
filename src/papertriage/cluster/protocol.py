from typing import Protocol

from papertriage.cluster.schema import Cluster
from papertriage.extract.schema import Paper


class Clusterer(Protocol):
    name: str

    def cluster(self, papers: list[Paper], n_clusters: int | None = None) -> list[Cluster]: ...
