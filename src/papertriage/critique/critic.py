from pathlib import Path

from papertriage.core.config import settings
from papertriage.critique.schema import Critique
from papertriage.extract.schema import Paper
from papertriage.llm.client import ClaudeClient, pydantic_to_tool
from papertriage.synthesize.schema import Report

_PROMPT_PATH = Path(__file__).parent.parent / "llm" / "prompts" / "critique_review.md"
_TOOL_NAME = "critique_review"
_TOOL_DESC = (
    "Return structured critique findings for the given literature review synthesis. "
    "Identify unsupported claims, overstated certainty, and missed nuance."
)


def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_papers_block(papers: list[Paper]) -> str:
    lines = ["=== PAPER LIBRARY ===\n"]
    for p in papers:
        lines.append(f"[{p.id}]")
        lines.append(f"Title: {p.title}")
        lines.append(f"Method: {p.method}")
        if p.contributions:
            lines.append("Contributions:")
            for c in p.contributions:
                lines.append(f"  - {c}")
        if p.key_results:
            lines.append("Key Results:")
            for r in p.key_results:
                lines.append(f"  - {r}")
        lines.append("")
    return "\n".join(lines)


def _single_pass(report: Report, papers: list[Paper], claude: ClaudeClient) -> Critique:
    system = _load_system_prompt()
    papers_block = _build_papers_block(papers)
    tool = pydantic_to_tool(_TOOL_NAME, _TOOL_DESC, Critique)
    messages = [{"role": "user", "content": report.markdown}]

    result = claude.call_tool(
        model=settings.model_synthesis,
        system=system,
        messages=messages,
        tool=tool,
        cached_blocks=[papers_block],
    )
    critique = Critique.model_validate(result)
    for f in critique.findings:
        f.source_critic = None  # single-pass has no per-agent provenance
    return critique


def critique(
    report: Report,
    papers: list[Paper],
    claude: ClaudeClient,
    mode: str = "multi",
) -> Critique:
    """Run critique stage.

    mode="multi"  — three specialized critic agents (default; ~3x cost of single)
    mode="single" — legacy single-pass critic for comparison or cost reduction
    """
    if mode == "single":
        return _single_pass(report, papers, claude)

    from papertriage.critique import aggregator
    return aggregator.run(report, papers, claude)
