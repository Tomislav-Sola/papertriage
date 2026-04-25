from pathlib import Path

from pydantic import ValidationError

from papertriage.core.config import settings
from papertriage.core.logging import get_logger
from papertriage.extract.schema import Paper
from papertriage.ingest.schema import RawPaper
from papertriage.llm.client import ClaudeClient, pydantic_to_tool

_log = get_logger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "llm" / "prompts" / "extract_paper.md"
_TRUNCATE_CHARS = 8000
_TOOL_NAME = "extract_paper"
_TOOL_DESC = (
    "Extract structured metadata from an academic paper. "
    "Return only information explicitly present in the text."
)


def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def extract(raw: RawPaper, claude: ClaudeClient) -> Paper:
    text = raw.raw_text
    if len(text) > _TRUNCATE_CHARS:
        _log.info("extractor_truncate", paper_id=raw.id, original=len(text), limit=_TRUNCATE_CHARS)
        text = text[:_TRUNCATE_CHARS]

    tool = pydantic_to_tool(_TOOL_NAME, _TOOL_DESC, Paper)
    # The tool schema includes 'id' but we don't want Claude to fill it — it's
    # an internal key. We strip it from the required list so the model won't
    # hallucinate paper IDs.
    tool["input_schema"].get("required", [None])  # ensure it exists
    if "required" in tool["input_schema"]:
        tool["input_schema"]["required"] = [
            f for f in tool["input_schema"]["required"] if f != "id"
        ]

    system = _load_system_prompt()
    messages = [{"role": "user", "content": text}]

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

    return paper
