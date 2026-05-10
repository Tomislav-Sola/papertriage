import json
from enum import Enum
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.status import Status

from papertriage.core.config import settings as _settings
from papertriage.llm.client import ClaudeClient

app = typer.Typer(name="papertriage", help="Triage academic PDFs with Claude.")
console = Console()


class ClustererChoice(str, Enum):
    tfidf = "tfidf"
    embedding = "embedding"


class CriticChoice(str, Enum):
    multi = "multi"
    single = "single"


@app.command()
def run(
    papers: Path | None = typer.Option(None, "--papers", help="Folder containing PDF files"),
    arxiv: list[str] | None = typer.Option(None, "--arxiv", help="arXiv ID to fetch (repeatable)"),
    arxiv_list: Path | None = typer.Option(
        None, "--arxiv-list", help="File with one arXiv ID per line"
    ),
    question: str = typer.Option(..., "--question", "-q", help="Research question"),
    max_papers: int | None = typer.Option(None, "--max-papers", help="Maximum papers to process"),
    out: Path | None = typer.Option(None, "--out", help="Override output directory"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass extraction cache"),
    clusterer: ClustererChoice = typer.Option(
        ClustererChoice.tfidf, "--clusterer", help="Clustering algorithm to use"
    ),
    critic: CriticChoice = typer.Option(
        CriticChoice.multi, "--critic", help="Critique mode: multi-agent (default) or single-pass"
    ),
    enable_graph: bool = typer.Option(
        False, "--enable-graph", help="Build knowledge graph (requires embeddings extra)"
    ),
    graph_threshold: float = typer.Option(
        0.6, "--graph-threshold", help="Cosine similarity threshold for graph edges (0–1)"
    ),
) -> None:
    """Run the full papertriage pipeline."""
    from papertriage.orchestration.pipeline import run_pipeline
    from papertriage.sources import ArxivSource, LocalSource

    cfg = _settings.model_copy(update={"output_dir": out}) if out else _settings

    sources = []
    if papers is not None:
        sources.append(LocalSource(papers))

    all_arxiv_ids = list(arxiv or [])
    if arxiv_list is not None:
        all_arxiv_ids.extend(
            line.strip() for line in arxiv_list.read_text().splitlines() if line.strip()
        )
    if all_arxiv_ids:
        sources.append(ArxivSource(all_arxiv_ids, cfg))

    if not sources:
        console.print("[bold red]Error:[/bold red] Provide at least one of --papers or --arxiv.")
        raise typer.Exit(code=1)

    claude = ClaudeClient(cfg)

    with Status("[bold green]Running pipeline...[/bold green]", console=console, spinner="dots"):
        try:
            ctx = run_pipeline(
                sources=sources,
                question=question,
                max_papers=max_papers,
                claude=claude,
                settings=cfg,
                no_cache=no_cache,
                clusterer_name=clusterer.value,
                critic_mode=critic.value,
                enable_graph=enable_graph,
                graph_threshold=graph_threshold,
            )
        except Exception as exc:
            console.print(f"[bold red]Pipeline failed:[/bold red] {exc}")
            raise typer.Exit(code=1)

    console.print(f"[bold]Run ID:[/bold]  {ctx.run_id}")
    console.print(f"[bold]Output:[/bold]   {ctx.output_dir}")
    console.print(f"[bold]Papers:[/bold]   {len(ctx.papers)}")
    console.print(f"[bold]Clusters:[/bold] {len(ctx.clusters)}")
    if ctx.report:
        console.print(f"[bold]Citations:[/bold] {len(ctx.report.citations)}")
    if ctx.critique:
        console.print(f"[bold]Findings:[/bold] {len(ctx.critique.findings)}")


@app.command()
def view(run_id: str = typer.Argument(..., help="Run ID to display")) -> None:
    """Print a run's synthesis report to stdout."""
    report_path = _settings.output_dir / run_id / "report.md"
    if not report_path.exists():
        console.print(f"[red]No report found for run '{run_id}'[/red]")
        raise typer.Exit(code=1)
    console.print(Markdown(report_path.read_text(encoding="utf-8")))


@app.command()
def cost(run_id: str = typer.Argument(..., help="Run ID to inspect")) -> None:
    """Print cost breakdown for a run."""
    cost_path = _settings.output_dir / run_id / "cost.json"
    if not cost_path.exists():
        console.print(f"[red]No cost data for run '{run_id}'[/red]")
        raise typer.Exit(code=1)
    data = json.loads(cost_path.read_text(encoding="utf-8"))
    console.print(f"[bold]Total:[/bold] ${data['total_usd']:.6f}")
    for stage, stage_cost in data.get("per_stage", {}).items():
        console.print(f"  {stage:<12} ${stage_cost:.6f}")


@app.command(name="regenerate")
def regenerate_run(
    run_id: str = typer.Argument(..., help="Run ID to regenerate from"),
    critic: CriticChoice = typer.Option(
        CriticChoice.multi, "--critic", help="Critique mode for regeneration"
    ),
) -> None:
    """Rerun synthesize + critique using review.json overrides for a prior run.

    Excluded papers and cluster label edits from the viewer (or review.json)
    are applied. Output is written to outputs/<run_id>/regenerated_<timestamp>/
    and the original run is never modified.
    """
    from papertriage.orchestration.regenerate import regenerate

    claude = ClaudeClient(_settings)

    with Status("[bold green]Regenerating...[/bold green]", console=console, spinner="dots"):
        try:
            ctx = regenerate(
                run_id=run_id,
                claude=claude,
                settings=_settings,
                critic_mode=critic.value,
            )
        except FileNotFoundError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(code=1)
        except Exception as exc:
            console.print(f"[bold red]Regeneration failed:[/bold red] {exc}")
            raise typer.Exit(code=1)

    console.print(f"[bold]Output:[/bold]   {ctx.output_dir}")
    if ctx.report:
        console.print(f"[bold]Citations:[/bold] {len(ctx.report.citations)}")
    if ctx.critique:
        console.print(f"[bold]Findings:[/bold] {len(ctx.critique.findings)}")


if __name__ == "__main__":
    app()
