# Cluster Eval Dataset

10 hand-written synthetic Paper objects across three topic groups:

- **RAG** (4 papers): retrieval-augmented generation, open-domain QA, factuality
- **RL** (4 papers): RLHF, sparse rewards, MARL, offline RL
- **Multimodal** (2 papers): vision-language pre-training, multimodal instruction following

The topic boundaries are deliberately obvious so that both clusterers are expected
to achieve high ARI scores. This is a sanity check and methodology demonstration,
not a rigorous benchmark.

## Honest disclaimer

This is a small synthetic test designed to illustrate the comparison methodology,
not a rigorous benchmark. A real comparison would need 100+ papers with diverse
topics and independent human cluster annotations. The synthetic papers are
constructed so that both TF-IDF and embedding clusterers should perform well;
the value here is the infrastructure for repeatable measurement, not the absolute
scores.
