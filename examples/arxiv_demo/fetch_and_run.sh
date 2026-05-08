#!/usr/bin/env bash
# Demonstrates the arXiv source: two RAG papers fetched by ID, pipeline runs offline-cached on re-runs.
# Usage: bash examples/arxiv_demo/fetch_and_run.sh
set -euo pipefail

papertriage run \
    --arxiv 2401.15884 \
    --arxiv 2406.13249 \
    --question "What are the key advances in retrieval-augmented generation?" \
    --max-papers 5
