import re
from pathlib import Path

from papertriage.cluster.schema import Cluster
from papertriage.core.config import settings
from papertriage.extract.schema import Paper
from papertriage.llm.client import ClaudeClient
from papertriage.synthesize.schema import Citation, Report

_PROMPT_PATH = Path(__file__).parent.parent / "llm" / "prompts" / "synthesize_review.md"


def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_papers_block(papers: list[Paper]) -> str:
    lines = ["=== PAPER LIBRARY ===\n"]
    for p in papers:
        lines.append(f"[{p.id[:8]}]")
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


def _build_clusters_block(clusters: list[Cluster]) -> str:
    lines = ["=== CLUSTERS ===\n"]
    for c in clusters:
        kw = ", ".join(c.keywords) if c.keywords else "N/A"
        paper_ids = ", ".join(c.paper_ids)
        lines.append(f'Cluster {c.id}: "{c.label}" (keywords: {kw})')
        lines.append(f"Papers: {paper_ids}\n")
    return "\n".join(lines)


def _extract_citations(text: str) -> list[Citation]:
    # Split on sentence boundaries; collect (paper_id, sentence) pairs
    sentences = re.split(r"(?<=[.!?])\s+", text)
    citations: list[Citation] = []
    seen: set[tuple[str, str]] = set()
    for sentence in sentences:
        for match in re.finditer(r"\[([a-zA-Z0-9_-]+)\]", sentence):
            paper_id = match.group(1)
            key = (paper_id, sentence.strip())
            if key not in seen:
                seen.add(key)
                citations.append(Citation(paper_id=paper_id, claim=sentence.strip()))
    return citations


def synthesize(
    question: str,
    clusters: list[Cluster],
    papers: list[Paper],
    claude: ClaudeClient,
) -> Report:
    """Synthesise a literature review from clustered papers.

    Citation.paper_id holds the 8-char short form of the SHA1; Paper.id is the full hash.
    """
    system = _load_system_prompt()
    papers_block = _build_papers_block(papers)
    clusters_block = _build_clusters_block(clusters)

    user_message = f"Research question: {question}\n\n{clusters_block}"
    messages = [{"role": "user", "content": user_message}]

    markdown = claude.call_text(
        model=settings.model_synthesis,
        system=system,
        messages=messages,
        cached_blocks=[papers_block],
    )

    citations = _extract_citations(markdown)
    return Report(markdown=markdown, citations=citations)
