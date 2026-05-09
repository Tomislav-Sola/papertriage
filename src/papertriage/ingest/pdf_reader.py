import hashlib
import io
import re
from collections import Counter
from pathlib import Path

import pypdf

from papertriage.core.exceptions import IngestError
from papertriage.core.logging import get_logger
from papertriage.ingest.schema import RawPaper

_log = get_logger(__name__)

_MIN_CHARS = 500

# Patterns that disqualify a line from being a paper title
_NOT_TITLE_RE = re.compile(
    r"arXiv:|https?://|@|\d{4}\.\d{4,5}|"
    r"\b(University|Institute|Department|Laboratory|Lab|School|"
    r"College|Center|Centre|Preprint|Submitted|Under review|"
    r"Proceedings|Published at|Advances in Neural)\b",
    re.IGNORECASE,
)


def _guess_title(pages: list[str]) -> str:
    """Return the first plausible title line from the first two pages."""
    for page_text in pages[:2]:
        for raw_line in page_text.splitlines():
            line = raw_line.strip()
            if len(line) < 10 or len(line) > 250:
                continue
            if _NOT_TITLE_RE.search(line):
                continue
            if re.fullmatch(r"[\d\W\s]+", line):
                continue
            return line
    return ""


def _clean_text(text: str) -> str:
    lines = text.splitlines()

    counts = Counter(line.strip() for line in lines if line.strip())

    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.fullmatch(r"\d+", stripped):
            continue
        if counts[stripped] > 3:
            continue
        cleaned.append(stripped)

    result = " ".join(cleaned)
    result = re.sub(r"\s+", " ", result).strip()
    return result


def _extract_metadata(reader: pypdf.PdfReader) -> dict[str, str]:
    metadata: dict[str, str] = {}
    raw_meta = reader.metadata
    if not raw_meta:
        return metadata

    # Dict iteration gets all fields but may miss encoding edge-cases
    for key, val in raw_meta.items():
        if val:
            metadata[key.lstrip("/")] = str(val)

    # Explicit attribute access as a more-reliable override for common fields
    for attr, field in (("title", "Title"), ("author", "Author")):
        try:
            val = getattr(raw_meta, attr, None)
            if val:
                metadata[field] = str(val)
        except Exception:
            pass

    return metadata


def read_pdf(path: Path) -> RawPaper:
    try:
        pdf_bytes = path.read_bytes()
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise IngestError(f"Cannot read PDF {path}: {exc}") from exc

    metadata = _extract_metadata(reader)

    # Merge sidecar metadata written by ArxivSource (authoritative title etc.)
    sidecar = path.with_suffix(".meta.json")
    if sidecar.exists():
        try:
            import json as _json
            metadata.update(_json.loads(sidecar.read_text(encoding="utf-8")))
        except Exception:
            pass

    # Preserve the raw first page (line breaks intact) so the extractor can
    # show Claude the structural layout where the title appears on its own line.
    if pages and pages[0].strip():
        metadata["_first_page"] = pages[0][:2000]

    # Python-level title candidate — used as final fallback if the LLM returns empty.
    candidate = _guess_title(pages)
    if candidate:
        metadata["_title_candidate"] = candidate

    raw_text = _clean_text("\n".join(pages))

    if len(raw_text) < _MIN_CHARS:
        raise IngestError(
            f"PDF {path} yielded only {len(raw_text)} chars (minimum {_MIN_CHARS})"
        )

    paper_id = hashlib.sha1(pdf_bytes).hexdigest()
    return RawPaper(
        id=paper_id,
        path=path,
        raw_text=raw_text,
        char_count=len(raw_text),
        metadata=metadata,
    )


def read_folder(folder: Path, max_papers: int | None = None) -> list[RawPaper]:
    pdfs = sorted(folder.glob("*.pdf"))
    if max_papers is not None:
        pdfs = pdfs[:max_papers]

    papers: list[RawPaper] = []
    for pdf_path in pdfs:
        try:
            papers.append(read_pdf(pdf_path))
        except IngestError as exc:
            _log.warning("ingest_skip", path=str(pdf_path), reason=str(exc))

    return papers
