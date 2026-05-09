# Example: V2 Side-by-Side Comparison

Two runs on the same 6 papers — one with the V1 baseline (TF-IDF + single-pass critic)
and one with the V2 stack (embedding clusterer + multi-agent critic).

Papers: 3 RAG papers + 3 RLHF/alignment papers (see `arxiv_papers.txt`).

Question: *"What techniques beyond pre-training have been proposed to make large language
models more reliable, factual, and aligned with human intent?"*

---

## Run A — baseline (TF-IDF + single-pass critic)

Output directory: `tfidf_single/`

| Metric | Value |
|---|---|
| Clusters | 3 |
| Cluster labels | Retrieval (3 papers), Fine Tuning (2 papers), Ai Assistants (1 paper) |
| Critique findings | 7 — 4 medium, 3 low |
| Total cost | $0.1036 |
| Pipeline time | ~106 s |

## Run B — V2 (embedding clusterer + multi-agent critic)

Output directory: `embedding_multi/`

| Metric | Value |
|---|---|
| Clusters | 3 (identical grouping to Run A) |
| Cluster labels | Retrieval (3 papers), Fine Tuning (2 papers), Ai Assistants (1 paper) |
| Critique findings | 17 — 1 high, 9 medium, 7 low (factuality: 5, coverage: 6, novelty: 6) |
| Total cost | $0.1156 (extraction free — all 6 cache hits from Run A) |
| Pipeline time | ~147 s (extra time: embedding model inference + 2 extra LLM calls) |

---

## What to look for

**Clustering:** open `tfidf_single/clusters.json` and `embedding_multi/clusters.json` side-by-side.
Check whether the 3 RAG papers and 3 alignment papers land in the same cluster or different ones,
and whether the embedding clusterer separates them more cleanly.

**Critique:** open the Critique tab in the viewer for each run. Run B findings have a coloured
badge showing which agent flagged the issue (factuality / coverage / novelty). Compare total
finding count and whether multi-agent catches distinct issue types that the single pass missed.

**Cost:** `cost.json` in each run directory. Run B critique stage is ~3× Run A because it makes
three Claude calls instead of one.

---

## Notable observations

**Clustering — both methods agreed, which is itself informative.**
The 6 papers span lexically very distinct topics ("retrieval" vs "reinforcement learning from
human feedback" vs "constitutional AI"), so both TF-IDF and the embedding model landed on the
same 3 clusters. This matches the synthetic eval result: on clearly separable topics, TF-IDF
is competitive (ARI 0.72) and faster by ~250×. The embedding approach is expected to show its
advantage on topics that share surface vocabulary but differ semantically — the cluster eval
README gives an honest account of this.

Cluster labels now use bigram TF-IDF features (ngram_range=(1,2)), so multi-word phrases like
"Fine Tuning" and "Ai Assistants" surface instead of the uninformative single tokens "Fine"
and "Ai". The labelling strategy picks the highest-ranked bigram in each cluster's keyword
list, falling back to the top unigram when no bigram ranks highly enough (as for "Retrieval").

**Critique — multi-agent is more thorough but noisier.**
The single-pass critic returned 7 tightly argued findings, all clearly anchored to specific
claims in the synthesis. The multi-agent critic returned 17 findings (1 duplicate removed).
The factuality and coverage agents surfaced genuinely useful issues — notably that Llama 2's
explicitly stated limitations were absent from the synthesis, and that the CRAG
decompose-then-recompose algorithm was cited but never explained. The novelty agent was
significantly more sensitive, flagging 6 issues including some that are routine academic
hedging rather than actual overstatements. This precision/recall tradeoff is expected and
worth noting: the multi-agent approach is better at exhaustive coverage, while the single-pass
critic is better calibrated for a quick, high-signal review.

**Extraction — CRAG title.**
pypdf failed to extract the title from the CRAG PDF (2401.15884) in the original run.
The ArxivSource now queries the arXiv API (export.arxiv.org/api/query) when downloading
a paper and writes the authoritative title to a sidecar `.meta.json` file. pdf_reader
merges this before extraction, so future arXiv runs will always have a correct title
regardless of pypdf's layout parsing. The examples here have been patched with the correct
title "Corrective Retrieval Augmented Generation".

**Cost and caching.**
Run B's extraction stage cost $0.00 — all 6 PDFs were cache hits from Run A. The critique
stage cost $0.089 in Run B vs $0.041 in Run A (≈ 2.2× rather than 3× because the papers
block is shared across agent calls via prompt caching). Total run cost was within $0.12 for
both runs on 6 papers.
