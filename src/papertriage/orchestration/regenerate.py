"""Partial pipeline rerun: synthesize + critique with review overrides applied."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from papertriage.cluster.schema import Cluster
from papertriage.core.config import Settings
from papertriage.core.logging import get_logger
from papertriage.critique import critic
from papertriage.extract.schema import Paper
from papertriage.llm.client import ClaudeClient
from papertriage.orchestration.context import RunContext
from papertriage.orchestration.pipeline import _format_critique_md, _write_artifacts
from papertriage.synthesize import synthesizer

_log = get_logger(__name__)


def _load_review(run_dir: Path) -> dict:
    review_path = run_dir / "review.json"
    if review_path.exists():
        return json.loads(review_path.read_text(encoding="utf-8"))
    return {"paper_overrides": {}, "cluster_overrides": {}}


def _apply_overrides(
    papers: list[Paper],
    clusters: list[Cluster],
    review: dict,
) -> tuple[list[Paper], list[Cluster]]:
    paper_overrides: dict[str, dict] = review.get("paper_overrides", {})
    cluster_overrides: dict[str, dict] = review.get("cluster_overrides", {})

    active_papers = [
        p for p in papers
        if paper_overrides.get(p.id, {}).get("included", True)
        and p.title != "<extraction failed>"
    ]
    active_ids = {p.id for p in active_papers}

    active_clusters: list[Cluster] = []
    for cluster in clusters:
        override = cluster_overrides.get(str(cluster.id), {})
        label = override.get("label", cluster.label)
        included_paper_ids = [pid for pid in cluster.paper_ids if pid in active_ids]
        if included_paper_ids:
            active_clusters.append(
                Cluster(
                    id=cluster.id,
                    label=label,
                    paper_ids=included_paper_ids,
                    keywords=cluster.keywords,
                )
            )

    return active_papers, active_clusters


def regenerate(
    run_id: str,
    claude: ClaudeClient,
    settings: Settings,
    critic_mode: str = "multi",
) -> RunContext:
    """Rerun synthesize + critique using review.json overrides for *run_id*.

    Writes output to outputs/<run_id>/regenerated_<timestamp>/ and never
    touches the original run's artifacts.
    """
    run_dir = settings.output_dir / run_id

    meta_path = run_dir / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"No meta.json for run '{run_id}' — was it created by V3?")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    question = meta["question"]
    if critic_mode == "multi":  # default — honour original run's mode unless caller overrides
        critic_mode = meta.get("critic_mode", "multi")

    papers = [
        Paper(**p)
        for p in json.loads((run_dir / "papers.json").read_text(encoding="utf-8"))
    ]
    clusters = [
        Cluster(**c)
        for c in json.loads((run_dir / "clusters.json").read_text(encoding="utf-8"))
    ]

    review = _load_review(run_dir)
    active_papers, active_clusters = _apply_overrides(papers, clusters, review)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    regen_dir = run_dir / f"regenerated_{ts}"
    regen_dir.mkdir(parents=True, exist_ok=True)

    regen_run_id = f"{run_id}_regen_{ts}"
    ctx = RunContext(
        run_id=regen_run_id,
        output_dir=regen_dir,
        question=question,
        papers=papers,
        clusters=active_clusters,
    )

    stage_costs: dict[str, float] = {}

    with claude.run(regen_run_id):
        _log.info("regenerate_start", source_run=run_id, papers=len(active_papers))

        cost_before = claude.get_run_cost(regen_run_id)
        ctx.report = synthesizer.synthesize(question, active_clusters, active_papers, claude)
        stage_costs["synthesize"] = round(claude.get_run_cost(regen_run_id) - cost_before, 6)

        cost_before = claude.get_run_cost(regen_run_id)
        ctx.critique = critic.critique(ctx.report, active_papers, claude, mode=critic_mode)
        stage_costs["critique"] = round(claude.get_run_cost(regen_run_id) - cost_before, 6)

        _log.info("regenerate_done", regen_dir=str(regen_dir))

    _write_artifacts(ctx, stage_costs)
    return ctx
