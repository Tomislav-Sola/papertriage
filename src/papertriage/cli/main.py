import typer

app = typer.Typer(name="papertriage", help="Triage academic PDFs with Claude.")


@app.command()
def run(
    folder: str = typer.Argument(..., help="Folder containing PDF files"),
    question: str = typer.Option(..., "--question", "-q", help="Research question"),
) -> None:
    """Run the full papertriage pipeline (Phase 2)."""
    typer.echo("Pipeline not yet implemented — coming in Phase 2.")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
