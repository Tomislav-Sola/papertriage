from pathlib import Path

from pydantic import BaseModel, Field

from papertriage.cluster.schema import Cluster
from papertriage.critique.schema import Critique
from papertriage.extract.schema import Paper
from papertriage.ingest.schema import RawPaper
from papertriage.synthesize.schema import Report


class RunContext(BaseModel):
    run_id: str
    output_dir: Path
    question: str
    critic_mode: str = "multi"
    raw_papers: list[RawPaper] = Field(default_factory=list)
    papers: list[Paper] = Field(default_factory=list)
    clusters: list[Cluster] = Field(default_factory=list)
    report: Report | None = None
    critique: Critique | None = None
    errors: list[str] = Field(default_factory=list)
