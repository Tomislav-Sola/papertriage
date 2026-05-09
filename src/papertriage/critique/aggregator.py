from papertriage.critique.agents import coverage, factuality, novelty
from papertriage.critique.schema import Critique, Finding, Severity
from papertriage.extract.schema import Paper
from papertriage.llm.client import ClaudeClient
from papertriage.synthesize.schema import Report

_SEVERITY_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2}


def _jaccard(a: str, b: str) -> float:
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a and not tokens_b:
        return 1.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def deduplicate(findings: list[Finding]) -> list[Finding]:
    """Remove near-duplicate findings (Jaccard > 0.8 on claim text), keeping highest severity."""
    kept: list[Finding] = []
    for candidate in findings:
        dupe_idx: int | None = None
        for i, existing in enumerate(kept):
            if _jaccard(candidate.claim, existing.claim) > 0.8:
                dupe_idx = i
                break
        if dupe_idx is None:
            kept.append(candidate)
        else:
            existing = kept[dupe_idx]
            if _SEVERITY_ORDER[candidate.severity.value] > _SEVERITY_ORDER[existing.severity.value]:
                kept[dupe_idx] = candidate
    return kept


def run(report: Report, papers: list[Paper], claude: ClaudeClient) -> Critique:
    factuality_findings = factuality.run(report, papers, claude)
    coverage_findings = coverage.run(report, papers, claude)
    novelty_findings = novelty.run(report, papers, claude)

    all_findings = factuality_findings + coverage_findings + novelty_findings
    deduped = deduplicate(all_findings)

    n_factuality = len(factuality_findings)
    n_coverage = len(coverage_findings)
    n_novelty = len(novelty_findings)
    n_deduped = len(all_findings) - len(deduped)

    overall_assessment = (
        f"Synthesized from 3 critic passes — "
        f"factuality: {n_factuality} finding(s), "
        f"coverage: {n_coverage} finding(s), "
        f"novelty: {n_novelty} finding(s). "
        f"{n_deduped} duplicate(s) removed."
    )

    return Critique(findings=deduped, overall_assessment=overall_assessment)
