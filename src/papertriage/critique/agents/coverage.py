from pathlib import Path

from papertriage.core.config import settings
from papertriage.critique.schema import Finding, FindingList
from papertriage.extract.schema import Paper
from papertriage.llm.client import ClaudeClient, pydantic_to_tool
from papertriage.synthesize.schema import Report

_PROMPT_PATH = Path(__file__).parent.parent.parent / "llm" / "prompts" / "critique_coverage.md"
_TOOL_NAME = "coverage_findings"
_TOOL_DESC = (
    "Return coverage findings for the literature review: papers mentioned but not engaged, "
    "key contributions omitted, uncovered clusters, and missing limitations."
)
_SOURCE = "coverage"


def _papers_block(papers: list[Paper]) -> str:
    lines = ["=== PAPER LIBRARY ===\n"]
    for p in papers:
        lines.append(f"[{p.id}]")
        lines.append(f"Title: {p.title}")
        if p.contributions:
            lines.append("Contributions:")
            for c in p.contributions:
                lines.append(f"  - {c}")
        if p.limitations:
            lines.append("Limitations:")
            for lim in p.limitations:
                lines.append(f"  - {lim}")
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
