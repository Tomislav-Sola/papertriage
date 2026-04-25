import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from papertriage.core.exceptions import LLMError
from papertriage.extract.schema import Paper
from papertriage.ingest.schema import RawPaper

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class FakeClaudeClient:
    """Offline test double for ClaudeClient. Returns canned fixture responses."""

    def __init__(self, fixture_file: Path | None = None, raises: Exception | None = None) -> None:
        self._raises = raises
        self._fixture: dict[str, Any] = {}
        if fixture_file is not None:
            self._fixture = json.loads(fixture_file.read_text())
        self._calls: list[dict] = []

    @contextmanager
    def run(self, run_id: str):
        yield

    def call_tool(
        self,
        model: str,
        system: str,
        messages: list[dict],
        tool: dict,
        cached_blocks: list[str] | None = None,
    ) -> dict:
        self._calls.append({"model": model, "tool": tool["name"], "cached_blocks": cached_blocks})
        if self._raises is not None:
            raise self._raises
        return dict(self._fixture)

    def call_text(
        self,
        model: str,
        system: str,
        messages: list[dict],
        cached_blocks: list[str] | None = None,
    ) -> str:
        self._calls.append({"model": model, "tool": None, "cached_blocks": cached_blocks})
        if self._raises is not None:
            raise self._raises
        return self._fixture.get("text", "")

    def get_run_cost(self, run_id: str) -> float:
        return 0.0

    @property
    def calls(self) -> list[dict]:
        return self._calls


@pytest.fixture()
def sample_raw_paper() -> RawPaper:
    text = (FIXTURES_DIR / "sample_paper.txt").read_text()
    return RawPaper(id="test-paper-id", path=Path("sample.pdf"), raw_text=text, char_count=len(text))


@pytest.fixture()
def golden_paper() -> Paper:
    data = json.loads((FIXTURES_DIR / "golden_extraction.json").read_text())
    return Paper.model_validate(data)


@pytest.fixture()
def fake_client() -> FakeClaudeClient:
    return FakeClaudeClient(fixture_file=FIXTURES_DIR / "golden_extraction.json")


@pytest.fixture()
def fake_client_failing() -> FakeClaudeClient:
    return FakeClaudeClient(raises=LLMError("simulated failure"))
