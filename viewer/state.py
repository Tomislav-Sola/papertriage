"""Manages per-run review state stored at outputs/<run_id>/review.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict


class PaperOverride(TypedDict, total=False):
    included: bool
    notes: str


class ClusterOverride(TypedDict, total=False):
    label: str


class ReviewState(TypedDict):
    paper_overrides: dict[str, PaperOverride]
    cluster_overrides: dict[str, ClusterOverride]


def load_review(run_dir: Path) -> ReviewState:
    review_path = run_dir / "review.json"
    if review_path.exists():
        return json.loads(review_path.read_text(encoding="utf-8"))
    return {"paper_overrides": {}, "cluster_overrides": {}}


def save_review(run_dir: Path, review: ReviewState) -> None:
    (run_dir / "review.json").write_text(
        json.dumps(review, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
