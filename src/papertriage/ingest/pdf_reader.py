import hashlib
import re
from collections import Counter
from pathlib import Path

import pypdf

from papertriage.core.exceptions import IngestError
from papertriage.core.logging import get_logger
from papertriage.ingest.schema import RawPaper

_log = get_logger(__name__)

_MIN_CHARS = 500


def _clean_text(text: str) -> str:
    lines = text.splitlines()

    # Count line occurrences to detect repeated headers/footers
    counts = Counter(line.strip() for line in lines if line.strip())

    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Drop lines that are purely page numbers (digits only, optionally with whitespace)
        if re.fullmatch(r"\d+", stripped):
            continue
        # Drop lines repeated more than 3 times (headers/footers)
        if counts[stripped] > 3:
            continue
        cleaned.append(stripped)

    result = " ".join(cleaned)
    # Collapse runs of whitespace
    result = re.sub(r"\s+", " ", result).strip()
    return result


def read_pdf(path: Path) -> RawPaper:
    try:
        reader = pypdf.PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise IngestError(f"Cannot read PDF {path}: {exc}") from exc

    raw_text = _clean_text("\n".join(pages))

    if len(raw_text) < _MIN_CHARS:
        raise IngestError(
            f"PDF {path} yielded only {len(raw_text)} chars (minimum {_MIN_CHARS})"
        )

    paper_id = hashlib.sha1(str(path).encode()).hexdigest()
    return RawPaper(id=paper_id, path=path, raw_text=raw_text, char_count=len(raw_text))


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
