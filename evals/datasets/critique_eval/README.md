# Critique Eval Dataset

A deliberately flawed ~500-word synthesis about Retrieval-Augmented Generation with 5 intentionally
planted issues:

| # | Type | Severity | Description |
|---|------|----------|-------------|
| 1 | Fabricated number | High | "98.7% accuracy on NaturalQuestions" — not in any source paper |
| 2 | Unsupported generalization | High | "all RAG approaches achieve >90% accuracy" — false universal claim |
| 3 | Overstated novelty | Medium | "first application of retrieval to language model generation" — not claimed by the paper |
| 4 | Fabricated deployment claim | High | "deployed by over 50 Fortune 500 companies" — not in any source paper |
| 5 | Missed cluster | Medium | Multi-modal retrieval papers referenced in the library but never addressed in the synthesis |

## How scoring works

A finding is counted as a **true positive** if it mentions at least one keyword associated with a
planted issue. Findings that do not match any planted issue are counted as **false positives**. This
is a rough keyword-match heuristic, not semantic evaluation.

## Honest disclaimer

Single seeded synthesis is illustrative, not a benchmark. A real eval would need 20+ seeded
examples with diverse issue types, multiple annotators to confirm which findings are correct, and
semantic rather than keyword-based matching. The value here is the repeatable measurement
infrastructure and the demonstration that multi-agent critique catches more distinct issue types than
single-pass critique.
