"""Head-to-head eval: single-pass critique vs. multi-agent critique.

Usage:
    python -m evals.critique_comparison                # real Claude API (needs ANTHROPIC_API_KEY)
    python -m evals.critique_comparison --fake         # offline stub (structure demo only)

Outputs a Rich table comparing both critique modes on:
  - True positives caught (planted issues found)
  - False positives (findings not matching any planted issue)
  - Wall-clock time
  - Estimated API cost

See evals/datasets/critique_eval/README.md for methodology notes.
"""
from __future__ import annotations

import argparse
import json
import time
from contextlib import contextmanager
from pathlib import Path

from rich.console import Console
from rich.table import Table

from papertriage.critique.schema import Critique, Finding, Severity
from papertriage.extract.schema import Paper
from papertriage.synthesize.schema import Citation, Report

DATASET_DIR = Path(__file__).parent / "datasets" / "critique_eval"
SYNTHESIS_PATH = DATASET_DIR / "seeded_synthesis.md"
EXPECTED_PATH = DATASET_DIR / "expected_findings.json"


def _load_dataset() -> tuple[str, list[Paper], list[dict]]:
    synthesis_md = SYNTHESIS_PATH.read_text(encoding="utf-8")
    data = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))

    papers = [
        Paper(
            id=p["id"],
            title=p["title"],
            problem=p["problem"],
            method=p["method"],
            contributions=p["contributions"],
            limitations=p.get("limitations", []),
            key_results=p.get("key_results", []),
        )
        for p in data["papers"]
    ]
    planted = data["planted_issues"]
    return synthesis_md, papers, planted


def _score(findings: list[Finding], planted: list[dict]) -> tuple[int, int]:
    """Return (true_positives, false_positives) using keyword-match heuristic."""
    matched_issues: set[str] = set()
    fp_count = 0

    for finding in findings:
        text = (finding.claim + " " + finding.reason).lower()
        matched = False
        for issue in planted:
            if issue["id"] in matched_issues:
                continue
            for kw in issue["keywords"]:
                if kw.lower() in text:
                    matched_issues.add(issue["id"])
                    matched = True
                    break
        if not matched:
            fp_count += 1

    return len(matched_issues), fp_count


class _FakeClaude:
    """Returns canned critique findings for offline demo."""

    _FACTUALITY_FINDINGS = {
        "findings": [
            {
                "claim": "The synthesis states '98.7% accuracy on the NaturalQuestions benchmark' but DPR reports top-20 retrieval accuracy, not end-to-end QA accuracy at that figure.",
                "severity": "high",
                "reason": "Fabricated statistic not present in rag-dpr source paper",
                "suggested_fix": "Remove the specific figure or cite the actual DPR retrieval accuracy of 79.4% top-20.",
                "source_critic": None,
            },
            {
                "claim": "'All RAG approaches now consistently achieving over 90% accuracy' is an unsupported universal claim.",
                "severity": "high",
                "reason": "No source paper makes this claim; it is a fabricated generalization.",
                "suggested_fix": "Remove or hedge: 'some RAG approaches report competitive accuracy on specific benchmarks'.",
                "source_critic": None,
            },
            {
                "claim": "'Deployed in production by over 50 Fortune 500 companies' has no basis in any cited paper.",
                "severity": "high",
                "reason": "Production deployment figures are not reported in any source paper.",
                "suggested_fix": "Remove the deployment claim entirely.",
                "source_critic": None,
            },
        ]
    }
    _COVERAGE_FINDINGS: dict = {"findings": []}
    _NOVELTY_FINDINGS = {
        "findings": [
            {
                "claim": "'First application of retrieval to language model generation' overstates novelty.",
                "severity": "medium",
                "reason": "Lewis et al. does not claim to be the first; retrieval-augmented approaches predate this work.",
                "suggested_fix": "Remove 'first' and describe it as 'a prominent application'.",
                "source_critic": None,
            }
        ]
    }
    _SINGLE_FINDINGS = {
        "findings": [
            {
                "claim": "The synthesis states '98.7% accuracy on the NaturalQuestions benchmark'.",
                "severity": "high",
                "reason": "This figure does not appear in any cited paper.",
                "suggested_fix": "Remove or verify the statistic.",
                "source_critic": None,
            },
            {
                "claim": "'First application of retrieval to language model generation' overstates novelty.",
                "severity": "medium",
                "reason": "The source paper does not make this claim.",
                "suggested_fix": "Remove 'first'.",
                "source_critic": None,
            },
        ],
        "overall_assessment": "Two issues found: one fabricated statistic and one unwarranted novelty claim.",
    }

    def __init__(self) -> None:
        self._call_count = 0

    @contextmanager
    def run(self, run_id: str):
        yield

    def call_tool(self, model, system, messages, tool, cached_blocks=None):
        name = tool["name"]
        self._call_count += 1
        if name == "critique_review":
            return dict(self._SINGLE_FINDINGS)
        if name == "factuality_findings":
            return dict(self._FACTUALITY_FINDINGS)
        if name == "coverage_findings":
            return dict(self._COVERAGE_FINDINGS)
        if name == "novelty_findings":
            return dict(self._NOVELTY_FINDINGS)
        return {"findings": [], "overall_assessment": ""}

    def call_text(self, model, system, messages, cached_blocks=None):
        return ""

    def get_run_cost(self, run_id: str) -> float:
        return 0.0


def _run_mode(
    mode: str,
    report: Report,
    papers: list[Paper],
    claude,
    run_id: str,
) -> tuple[Critique, float, float]:
    from papertriage.critique.critic import critique

    with claude.run(run_id):
        t0 = time.perf_counter()
        result = critique(report, papers, claude, mode=mode)
        elapsed = time.perf_counter() - t0

    cost = claude.get_run_cost(run_id)
    return result, elapsed, cost


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare single-pass vs multi-agent critique")
    parser.add_argument("--fake", action="store_true", help="Use offline stub (no API calls)")
    args = parser.parse_args()

    console = Console()
    console.print("[bold]Loading critique eval dataset…[/bold]")
    synthesis_md, papers, planted = _load_dataset()

    report = Report(markdown=synthesis_md, citations=[Citation(paper_id=p.id, claim="") for p in papers])

    if args.fake:
        console.print("[yellow]Running in --fake mode (canned responses, no API calls)[/yellow]\n")
        single_claude = _FakeClaude()
        multi_claude = _FakeClaude()
    else:
        from papertriage.core.config import settings
        from papertriage.llm.client import ClaudeClient
        single_claude = ClaudeClient(settings)
        multi_claude = ClaudeClient(settings)

    console.print("Running [cyan]single-pass[/cyan] critic…")
    single_result, single_time, single_cost = _run_mode("single", report, papers, single_claude, "eval_single")

    console.print("Running [cyan]multi-agent[/cyan] critic…")
    multi_result, multi_time, multi_cost = _run_mode("multi", report, papers, multi_claude, "eval_multi")

    single_tp, single_fp = _score(single_result.findings, planted)
    multi_tp, multi_fp = _score(multi_result.findings, planted)

    table = Table(title="Critique Mode Comparison", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Single-pass", justify="right")
    table.add_column("Multi-agent", justify="right")

    total_planted = len(planted)
    table.add_row(
        f"True positives caught (/{total_planted} planted) ↑",
        f"{single_tp}/{total_planted}",
        f"{multi_tp}/{total_planted}",
    )
    table.add_row("False positives ↓", str(single_fp), str(multi_fp))
    table.add_row("Total findings", str(len(single_result.findings)), str(len(multi_result.findings)))
    table.add_row("Wall-clock time (s)", f"{single_time:.1f}", f"{multi_time:.1f}")
    table.add_row("Estimated cost (USD)", f"${single_cost:.4f}", f"${multi_cost:.4f}")

    console.print(table)

    console.print("\n[bold]Multi-agent findings by critic:[/bold]")
    from collections import Counter
    by_critic = Counter(f.source_critic or "legacy" for f in multi_result.findings)
    for critic_name, count in sorted(by_critic.items()):
        console.print(f"  {critic_name:<14} {count} finding(s)")

    console.print(
        "\n[dim]Scoring uses keyword matching — see "
        "evals/datasets/critique_eval/README.md for methodology notes.[/dim]"
    )


if __name__ == "__main__":
    main()
