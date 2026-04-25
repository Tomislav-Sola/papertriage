class PaperTriageError(Exception):
    """Base exception for all papertriage errors."""


class BudgetExceededError(PaperTriageError):
    """Raised when the per-run cost cap is exceeded."""

    def __init__(self, run_id: str, spent: float, cap: float) -> None:
        self.run_id = run_id
        self.spent = spent
        self.cap = cap
        super().__init__(f"Run {run_id!r} exceeded budget: ${spent:.4f} > ${cap:.2f}")


class LLMError(PaperTriageError):
    """Raised when an LLM call fails after all retries."""


class ExtractionError(PaperTriageError):
    """Raised when structured extraction cannot be completed."""


class IngestError(PaperTriageError):
    """Raised when a PDF cannot be read or yields too little text."""


class PipelineError(PaperTriageError):
    """Raised when the orchestration pipeline encounters an unrecoverable error."""
