import json
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.status import Status

from papertriage.core.config import settings as _settings
from papertriage.llm.client import ClaudeClient

app = typer.Typer(name="papertriage", help="Triage academic PDFs with Claude.")
console = Console()


@app.command()
def run(
    papers: Path = typer.Option(..., "--papers", help="Folder containing PDF files"),
    question: str = typer.Option(..., "--question", "-q", help="Research question"),
    max_papers: int | None = typer.Option(None, "--max-papers", help="Maximum papers to process"),
    out: Path | None = typer.Option(None, "--out", help="Override output directory"),
) -> None:
    """Run the full papertriage pipeline."""
    from papertriage.orchestration.pipeline import run_pipeline

    cfg = _settings
    if out is not None:
        from papertriage.core.config import Settings
        cfg = Settings(output_dir=out)

    claude = ClaudeClient(cfg)

    with Status("[bold green]Running pipeline...[/bold green]", console=console, spinner="dots"):
        try:
            ctx = run_pipeline(
                papers_dir=papers,
                question=question,
                max_papers=max_papers,
                claude=claude,
                settings=cfg,
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


if __name__ == "__main__":
    app()
