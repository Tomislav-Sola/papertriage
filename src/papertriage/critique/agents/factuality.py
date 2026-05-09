from pathlib import Path

from papertriage.core.config import settings
from papertriage.critique.schema import Finding, FindingList
from papertriage.extract.schema import Paper
from papertriage.llm.client import ClaudeClient, pydantic_to_tool
from papertriage.synthesize.schema import Report

_PROMPT_PATH = Path(__file__).parent.parent.parent / "llm" / "prompts" / "critique_factuality.md"
_TOOL_NAME = "factuality_findings"
_TOOL_DESC = (
    "Return factuality findings for the literature review: fabricated numbers, "
    "misattributed methods, unsupported assertions, and contradicted claims."
)
_SOURCE = "factuality"


def _papers_block(papers: list[Paper]) -> str:
    lines = ["=== PAPER LIBRARY ===\n"]
    for p in papers:
        lines.append(f"[{p.id}]")
        lines.append(f"Title: {p.title}")
        lines.append(f"Method: {p.method}")
        if p.key_results:
            lines.append("Key Results:")
            for r in p.key_results:
                lines.append(f"  - {r}")
        lines.append("")
    return "\n".join(lines)


def run(report: Report, papers: list[Paper], claude: ClaudeClient) -> list[Finding]:
    system = _PROMPT_PATH.read_text(encoding="utf-8")
    tool = pydantic_to_tool(_TOOL_NAME, _TOOL_DESC, FindingList)
    messages = [{"role": "user", "content": report.markdown}]

    result = claude.call_tool(
        model=settings.model_synthesis,
        system=system,
        messages=messages,
        tool=tool,
        cached_blocks=[_papers_block(papers)],
    )

    raw = FindingList.model_validate(result)
    return [
        Finding(
            claim=f.claim,
            severity=f.severity,
            reason=f.reason,
            suggested_fix=f.suggested_fix,
            source_critic=_SOURCE,
        )
        for f in raw.findings
    ]
