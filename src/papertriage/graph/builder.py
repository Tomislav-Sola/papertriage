"""Build and render a paper-paper similarity graph from precomputed embeddings."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from papertriage.cluster.schema import Cluster
from papertriage.extract.schema import Paper

# Distinct palette for up to 8 clusters; extras fall back to grey.
_CLUSTER_COLORS = [
    "#4e79a7", "#f28e2b", "#59a14f", "#e15759",
    "#76b7b2", "#edc948", "#b07aa1", "#ff9da7",
]
_FALLBACK_COLOR = "#aaaaaa"


def _cluster_color(cluster_id: int) -> str:
    if 0 <= cluster_id < len(_CLUSTER_COLORS):
        return _CLUSTER_COLORS[cluster_id]
    return _FALLBACK_COLOR


def build_graph(
    papers: list[Paper],
    embeddings: np.ndarray,
    clusters: list[Cluster],
    threshold: float = 0.6,
) -> "networkx.Graph":  # type: ignore[name-defined]  # noqa: F821
    """Return a NetworkX graph with cosine-similarity edges above *threshold*.

    Embeddings must be L2-normalised (EmbeddingClusterer already does this),
    so cosine similarity reduces to the dot product.
    """
    import networkx as nx

    paper_to_cluster: dict[str, int] = {}
    for cluster in clusters:
        for pid in cluster.paper_ids:
            paper_to_cluster[pid] = cluster.id

    G: nx.Graph = nx.Graph()
    for paper in papers:
        cid = paper_to_cluster.get(paper.id, -1)
        first_contrib = paper.contributions[0] if paper.contributions else ""
        G.add_node(
            paper.id,
            label=paper.title[:60] or paper.id[:8],
            cluster=cid,
            color=_cluster_color(cid),
            title=f"{paper.title}\n{first_contrib}",
        )

    n = len(papers)
    if n > 1:
        # Cosine similarity matrix (embeddings are already normalised)
        sim: np.ndarray = embeddings @ embeddings.T
        for i in range(n):
            for j in range(i + 1, n):
                score = float(sim[i, j])
                if score >= threshold:
                    G.add_edge(papers[i].id, papers[j].id, weight=round(score, 4))

    return G


_GRAPH_OPTIONS = """
{
  "physics": {
    "barnesHut": {
      "gravitationalConstant": -4000,
      "centralGravity": 1.2,
      "springLength": 180,
      "springConstant": 0.04,
      "damping": 0.15
    },
    "stabilization": {
      "iterations": 300,
      "updateInterval": 10,
      "fit": true
    },
    "minVelocity": 0.5
  },
  "nodes": {
    "shape": "dot",
    "borderWidth": 2,
    "borderWidthSelected": 3,
    "shadow": {"enabled": true, "color": "rgba(0,0,0,0.12)", "size": 8, "x": 2, "y": 3},
    "font": {"size": 13, "face": "system-ui, -apple-system, Arial, sans-serif", "strokeWidth": 3, "strokeColor": "#ffffff"}
  },
  "edges": {
    "smooth": {"type": "continuous", "roundness": 0.3},
    "color": {"opacity": 0.55},
    "hoverWidth": 2,
    "selectionWidth": 2
  },
  "interaction": {
    "hover": true,
    "tooltipDelay": 80,
    "zoomView": true,
    "dragView": true
  }
}
"""

# Injected after vis.Network is created — disables physics once layout settles,
# then fits the entire graph into the viewport with a short animation.
_STABILIZE_JS = """
    network.once("stabilizationIterationsDone", function () {
        network.setOptions({ physics: { enabled: false } });
        network.fit({ animation: { duration: 600, easingFunction: "easeInOutQuad" } });
    });
"""


def render_pyvis(
    G: "networkx.Graph",  # type: ignore[name-defined]  # noqa: F821
    output_path: Path,
) -> None:
    """Render *G* as a self-contained pyvis HTML file at *output_path*."""
    from pyvis.network import Network

    net = Network(height="580px", width="100%", bgcolor="#f7f8fa", font_color="#222222")
    net.set_options(_GRAPH_OPTIONS)

    degrees = dict(G.degree())
    max_deg = max(degrees.values(), default=1)

    for node, attrs in G.nodes(data=True):
        size = 14 + 22 * (degrees.get(node, 0) / max(max_deg, 1))
        tooltip = attrs.get("title", "").replace("\n", "<br>")
        color = attrs.get("color", _FALLBACK_COLOR)
        net.add_node(
            node,
            label=attrs.get("label", node[:8]),
            color={"background": color, "border": color, "highlight": {"background": color, "border": "#222222"}},
            size=size,
            title=tooltip,
        )

    for u, v, data in G.edges(data=True):
        weight = data.get("weight", 1.0)
        net.add_edge(u, v, value=weight, title=f"similarity: {weight:.2f}")

    net.save_graph(str(output_path))

    # Post-process: inject stabilization + fit handler right after network creation
    html = output_path.read_text(encoding="utf-8")
    html = html.replace(
        "network = new vis.Network(",
        "network = new vis.Network(",
        1,
    )
    # Find the closing of the Network constructor call and append our handler
    marker = "network = new vis.Network(container, data, options);"
    if marker in html:
        html = html.replace(marker, marker + _STABILIZE_JS, 1)
    output_path.write_text(html, encoding="utf-8")
