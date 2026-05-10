from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

from papertriage.core.config import settings
from papertriage.core.logging import get_logger
from papertriage.extract.schema import Paper
from papertriage.ingest.schema import RawPaper
from papertriage.llm.client import ClaudeClient, pydantic_to_tool

if TYPE_CHECKING:
    from papertriage.extract.cache import ExtractionCache

_log = get_logger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "llm" / "prompts" / "extract_paper.md"
_HEAD_CHARS = 4000
_TAIL_CHARS = 4000
_SEPARATOR = "\n...[middle elided]...\n"
_TOOL_NAME = "extract_paper"
_TOOL_DESC = (
    "Extract structured metadata from an academic paper. "
    "Return only information explicitly present in the text."
)


def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_user_message(raw: RawPaper, text: str) -> str:
    parts: list[str] = []

    # First page with line breaks intact — the title is on its own line here
    first_page = raw.metadata.get("_first_page", "").strip()
    if first_page:
        parts.append(
            "First page (original layout — the title is typically the first prominent "
            "line(s) before the author list):\n" + first_page
        )

    # pypdf document metadata, excluding internal keys
    meta_public = {k: v for k, v in raw.metadata.items() if not k.startswith("_")}
    if meta_public:
        parts.append(f"PDF document metadata: {json.dumps(meta_public)}")

    parts.append(f"Full paper text (may be truncated):\n{text}")
    return "\n\n".join(parts)


def extract(
    raw: RawPaper,
    claude: ClaudeClient,
    cache: ExtractionCache | None = None,
) -> Paper:
    if cache is not None:
        cached = cache.get(raw.id)
        if cached is not None:
            _log.info("extract_cache_hit", paper_id=raw.id)
            return cached

    text = raw.raw_text
    if len(text) > _HEAD_CHARS + _TAIL_CHARS:
        _log.info("extractor_truncate", paper_id=raw.id, original=len(text))
        text = text[:_HEAD_CHARS] + _SEPARATOR + text[-_TAIL_CHARS:]

    tool = pydantic_to_tool(_TOOL_NAME, _TOOL_DESC, Paper)
    # Remove id (assigned by us). Ensure title is required so Claude
    # can't silently omit it even though Pydantic gives it a default of "".
    required = [f for f in tool["input_schema"].get("required", []) if f != "id"]
    if "title" not in required:
        required.append("title")
    tool["input_schema"]["required"] = required

    system = _load_system_prompt()
    messages = [{"role": "user", "content": _build_user_message(raw, text)}]

    try:
        raw_result = claude.call_tool(
            model=settings.model_extraction,
            system=system,
            messages=messages,
            tool=tool,
        )
        raw_result["id"] = raw.id
        paper = Paper.model_validate(raw_result)
    except ValidationError as exc:
        _log.error("extractor_validation_failed", paper_id=raw.id, error=str(exc))
        return Paper(id=raw.id, title="<extraction failed>")
    except Exception as exc:
        _log.error("extractor_failed", paper_id=raw.id, error=str(exc))
        return Paper(id=raw.id, title="<extraction failed>")

    # Fallback chain: PDF metadata → Python heuristic candidate
    if not paper.title:
        for key in ("Title", "_title_candidate"):
            val = raw.metadata.get(key, "")
            if val:
                paper = paper.model_copy(update={"title": val})
                _log.info("title_fallback", paper_id=raw.id, source=key)
                break

    # Only cache complete extractions — an empty title means the LLM skipped it
    # and the arXiv sidecar may not have existed yet; retry next run.
    if cache is not None and paper.title and paper.title != "<extraction failed>":
        cache.set(raw.id, paper)

    return paper
