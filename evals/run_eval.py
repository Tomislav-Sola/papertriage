"""Extraction eval: compare extracted Paper fields against hand-labelled golden entries.

Usage:
    python -m evals.run_eval           # real ClaudeClient (needs ANTHROPIC_API_KEY)
    python -m evals.run_eval --fake    # offline, FakeClaudeClient returns golden fields

Expand evals/dataset/golden.json to at least 5 entries before treating scores as meaningful.
"""
from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

DATASET_DIR = Path(__file__).parent / "dataset"
GOLDEN_PATH = DATASET_DIR / "golden.json"
PAPERS_DIR = DATASET_DIR / "papers"


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _jaccard(a: list[str], b: list[str]) -> float:
    sa = {t.lower() for item in a for t in item.split()}
    sb = {t.lower() for item in b for t in item.split()}
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def _score_field(
    field: str, expected: Any, got: Any
) -> tuple[str, str, bool | float]:
    """Return (expected_display, got_display, score)."""
    if field in ("title", "method"):
        exp_s = str(expected)
        got_s = str(got) if got else ""
        return exp_s, got_s, exp_s.lower() in got_s.lower()
    if field == "year":
        exp_s = str(expected)
        got_s = str(got) if got is not None else ""
        return exp_s, got_s, exp_s == got_s
    if field in ("datasets", "contributions"):
        exp_l = expected if isinstance(expected, list) else []
        got_l = got if isinstance(got, list) else []
        score = _jaccard(exp_l, got_l)
        return ", ".join(exp_l) or "(none)", ", ".join(got_l) or "(none)", score
    return str(expected), str(got), False


# ---------------------------------------------------------------------------
# Fake client for offline iteration
# ---------------------------------------------------------------------------

class _GoldenFakeClient:
    """Returns primed golden-field dicts as extraction responses — no API calls."""

    def __init__(self) -> None:
        self._current_entry: dict = {}

    def prime(self, expected_fields: dict) -> None:
        """Set fields that call_tool() will return on the next extraction call."""
        self._current_entry = dict(expected_fields)

    @contextmanager
    def run(self, run_id: str):
        yield

    def call_tool(
        self,
        model: str,
        system: str,
        messages: list[dict],
        tool: dict,
        cached_blocks: list[str] | None = None,
    ) -> dict:
        return dict(self._current_entry)

    def call_text(
        self,
        model: str,
        system: str,
        messages: list[dict],
        cached_blocks: list[str] | None = None,
    ) -> str:
        return ""

    def get_run_cost(self, run_id: str) -> float:
        return 0.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Run extraction evals")
    parser.add_argument(
        "--fake", action="store_true", help="Use offline fake client (no API calls)"
    )
    args = parser.parse_args()

    console = Console()

    if not GOLDEN_PATH.exists():
        console.print("[red]golden.json not found at evals/dataset/golden.json[/red]")
        sys.exit(0)

    golden: list[dict] = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    if not golden:
        console.print("[yellow]golden.json is empty — add entries to run evals.[/yellow]")
        sys.exit(0)

    runnable = [(e, PAPERS_DIR / e["paper_filename"]) for e in golden]
    runnable = [(e, p) for e, p in runnable if p.exists()]

    if not runnable:
        console.print(
            "[yellow]No matching PDFs in evals/dataset/papers/. "
            "Drop PDFs there with filenames matching golden.json entries.[/yellow]"
        )
        sys.exit(0)

    run_id = "eval_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if args.fake:
        client: Any = _GoldenFakeClient()
    else:
        from papertriage.core.config import settings
        from papertriage.llm.client import ClaudeClient
        client = ClaudeClient(settings)

    from papertriage.extract import extractor
    from papertriage.ingest.pdf_reader import read_pdf

    fields_to_check = ["title", "year", "method", "datasets", "contributions"]
    rows: list[tuple] = []
    field_scores: dict[str, list[float]] = {f: [] for f in fields_to_check}

    with client.run(run_id):
        for entry, pdf_path in runnable:
            filename = entry["paper_filename"]
            expected = entry["expected_fields"]
            console.print(f"Processing [bold]{filename}[/bold]…")

            try:
                raw = read_pdf(pdf_path)
            except Exception as exc:
                console.print(f"  [red]Ingest failed: {exc}[/red]")
                continue

            if args.fake:
                client.prime(expected)

            paper = extractor.extract(raw, client)

            for field in fields_to_check:
                exp_val = expected.get(field)
                if exp_val is None:
                    continue
                got_val = getattr(paper, field, None)
                exp_s, got_s, score = _score_field(field, exp_val, got_val)
                rows.append((filename, field, exp_s[:45], got_s[:45], score))
                field_scores[field].append(float(score))

    total_cost = client.get_run_cost(run_id)

    # Results table
    table = Table(title=f"Eval Results — {run_id}", show_lines=True)
    table.add_column("paper_filename", style="cyan", no_wrap=True)
    table.add_column("field")
    table.add_column("expected", max_width=45)
    table.add_column("got", max_width=45)
    table.add_column("score", justify="right")

    for filename, field, exp_s, got_s, score in rows:
        if isinstance(score, bool):
            score_str = "✓" if score else "✗"
            style = "green" if score else "red"
        else:
            score_str = f"{score:.2f}"
            style = "green" if score >= 0.5 else "red"
        table.add_row(filename, field, exp_s, got_s, f"[{style}]{score_str}[/{style}]")

    console.print(table)

    console.print("\n[bold]Per-field mean scores:[/bold]")
    for field, scores in field_scores.items():
        if scores:
            mean = sum(scores) / len(scores)
            console.print(f"  {field:<18} {mean:.2f}")

    console.print(f"\n[bold]Total cost:[/bold] ${total_cost:.6f}")
    console.print(f"[dim]Run ID: {run_id}[/dim]")


if __name__ == "__main__":
    main()
