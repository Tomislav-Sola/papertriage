import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import structlog
import structlog.processors
import structlog.stdlib

from papertriage.cluster import clusterer
from papertriage.core.config import Settings
from papertriage.core.exceptions import BudgetExceededError
from papertriage.core.logging import get_logger, reset_run_id, set_run_id
from papertriage.critique import critic
from papertriage.critique.schema import Critique
from papertriage.extract import extractor
from papertriage.ingest.pdf_reader import read_folder
from papertriage.llm.client import ClaudeClient
from papertriage.orchestration.context import RunContext
from papertriage.synthesize import synthesizer

_log = get_logger(__name__)


def _setup_file_logging(log_path: Path) -> logging.FileHandler:
    handler = logging.FileHandler(str(log_path), encoding="utf-8")
    fmt = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
        ],
    )
    handler.setFormatter(fmt)
    logging.getLogger().addHandler(handler)
    return handler


def _format_critique_md(crit: Critique) -> str:
    lines = [f"# Critique Report\n\n**Overall Assessment:** {crit.overall_assessment}\n"]
    if crit.findings:
        lines.append("## Findings\n")
        for i, f in enumerate(crit.findings, 1):
            lines.append(f"### Finding {i} ({f.severity.value.title()} Severity)")
            lines.append(f"**Claim:** {f.claim}")
            lines.append(f"**Reason:** {f.reason}")
            lines.append(f"**Suggested Fix:** {f.suggested_fix}\n")
    else:
        lines.append("*No issues found.*")
    return "\n".join(lines)


def _write_artifacts(ctx: RunContext, stage_costs: dict[str, float]) -> None:
    d = ctx.output_dir
    d.mkdir(parents=True, exist_ok=True)

    if ctx.papers:
        (d / "papers.json").write_text(
            json.dumps([p.model_dump() for p in ctx.papers], indent=2),
            encoding="utf-8",
        )
    if ctx.clusters:
        (d / "clusters.json").write_text(
            json.dumps([c.model_dump() for c in ctx.clusters], indent=2),
            encoding="utf-8",
        )
    if ctx.report:
        (d / "report.md").write_text(ctx.report.markdown, encoding="utf-8")
    if ctx.critique:
        (d / "critique.md").write_text(_format_critique_md(ctx.critique), encoding="utf-8")

    total_usd = round(sum(stage_costs.values()), 6)
    (d / "cost.json").write_text(
        json.dumps({"total_usd": total_usd, "per_stage": stage_costs}, indent=2),
        encoding="utf-8",
    )


def run_pipeline(
    papers_dir: Path,
    question: str,
    max_papers: int | None,
    claude: ClaudeClient,
    settings: Settings,
) -> RunContext:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8]
    output_dir = settings.output_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    ctx = RunContext(run_id=run_id, output_dir=output_dir, question=question)

    log_handler = _setup_file_logging(output_dir / "run.log")
    run_id_token = set_run_id(run_id)

    stage_costs: dict[str, float] = {}

    def _cost_snapshot() -> float:
        return claude.get_run_cost(run_id)

    try:
        with claude.run(run_id):
            _log.info("pipeline_start", run_id=run_id, papers_dir=str(papers_dir))

            # Stage 1: ingest
            cost_before = _cost_snapshot()
            ctx.raw_papers = read_folder(papers_dir, max_papers=max_papers)
            stage_costs["ingest"] = round(_cost_snapshot() - cost_before, 6)
            _log.info("stage_ingest_done", count=len(ctx.raw_papers))

            # Stage 2: extract (skip failed papers)
            cost_before = _cost_snapshot()
            for raw in ctx.raw_papers:
                paper = extractor.extract(raw, claude)
                ctx.papers.append(paper)
            stage_costs["extract"] = round(_cost_snapshot() - cost_before, 6)
            _log.info("stage_extract_done", count=len(ctx.papers))

            # Stage 3: cluster
            cost_before = _cost_snapshot()
            ctx.clusters = clusterer.cluster(ctx.papers)
            stage_costs["cluster"] = round(_cost_snapshot() - cost_before, 6)
            _log.info("stage_cluster_done", count=len(ctx.clusters))

            # Stage 4: synthesize
            cost_before = _cost_snapshot()
            ctx.report = synthesizer.synthesize(question, ctx.clusters, ctx.papers, claude)
            stage_costs["synthesize"] = round(_cost_snapshot() - cost_before, 6)
            _log.info("stage_synthesize_done", citations=len(ctx.report.citations))

            # Stage 5: critique
            cost_before = _cost_snapshot()
            ctx.critique = critic.critique(ctx.report, ctx.papers, claude)
            stage_costs["critique"] = round(_cost_snapshot() - cost_before, 6)
            _log.info("stage_critique_done", findings=len(ctx.critique.findings))

            _log.info("pipeline_done", run_id=run_id, output_dir=str(output_dir))

    except Exception as exc:
        ctx.errors.append(str(exc))
        _log.error("pipeline_error", run_id=run_id, error=str(exc))
        raise
    finally:
        _write_artifacts(ctx, stage_costs)
        reset_run_id(run_id_token)
        logging.getLogger().removeHandler(log_handler)
        log_handler.close()

    return ctx
