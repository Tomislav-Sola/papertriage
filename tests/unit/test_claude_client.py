"""Tests for ClaudeClient using a mocked anthropic.Anthropic."""
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import anthropic
import pytest

from papertriage.core.config import Settings
from papertriage.core.exceptions import BudgetExceededError, LLMError
from papertriage.llm.client import ClaudeClient


def _make_usage(input_tokens=10, output_tokens=5, cache_creation=0, cache_read=0):
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=cache_creation,
        cache_read_input_tokens=cache_read,
    )


def _make_tool_response(tool_name="extract_paper", tool_input=None):
    block = SimpleNamespace(
        type="tool_use",
        name=tool_name,
        input=tool_input or {"title": "Test", "id": "abc"},
    )
    resp = SimpleNamespace(content=[block], usage=_make_usage())
    return resp


def _make_text_response(text="hello"):
    block = SimpleNamespace(type="text", text=text)
    resp = SimpleNamespace(content=[block], usage=_make_usage())
    return resp


def _settings(budget: float = 1.0) -> Settings:
    return Settings(
        anthropic_api_key="test-key",
        run_budget_usd=budget,
        model_extraction="claude-haiku-4-5",
        model_synthesis="claude-sonnet-4-6",
    )


_TOOL = {
    "name": "extract_paper",
    "description": "test",
    "input_schema": {"type": "object", "properties": {"title": {"type": "string"}}},
}


class TestRetries:
    def test_retries_three_times_on_api_error(self):
        cfg = _settings()
        with patch("papertriage.llm.client.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.side_effect = anthropic.APIError(
                message="server error", request=MagicMock(), body=None
            )

            client = ClaudeClient(cfg)

            with patch("papertriage.llm.client.time.sleep"):
                with pytest.raises(LLMError):
                    client.call_tool("claude-haiku-4-5", "sys", [], _TOOL)

            assert mock_client.messages.create.call_count == 3

    def test_succeeds_after_transient_failure(self):
        cfg = _settings()
        with patch("papertriage.llm.client.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.side_effect = [
                anthropic.APIError(message="err", request=MagicMock(), body=None),
                _make_tool_response(),
            ]

            client = ClaudeClient(cfg)
            with patch("papertriage.llm.client.time.sleep"):
                result = client.call_tool("claude-haiku-4-5", "sys", [], _TOOL)

            assert result["title"] == "Test"
            assert mock_client.messages.create.call_count == 2


class TestBudgetTracking:
    def test_accumulates_cost_across_calls(self):
        cfg = _settings(budget=1.0)
        with patch("papertriage.llm.client.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _make_tool_response()

            client = ClaudeClient(cfg)
            with client.run("run-1"):
                client.call_tool("claude-haiku-4-5", "sys", [], _TOOL)
                client.call_tool("claude-haiku-4-5", "sys", [], _TOOL)

            cost = client.get_run_cost("run-1")
            assert cost > 0
            assert mock_client.messages.create.call_count == 2

    def test_budget_exceeded_raises(self):
        cfg = _settings(budget=0.0)  # zero budget → exceeded immediately
        with patch("papertriage.llm.client.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _make_tool_response()

            client = ClaudeClient(cfg)
            with client.run("run-tight"):
                with pytest.raises(BudgetExceededError) as exc_info:
                    client.call_tool("claude-haiku-4-5", "sys", [], _TOOL)

            assert exc_info.value.run_id == "run-tight"
            assert exc_info.value.cap == 0.0

    def test_costs_are_isolated_per_run(self):
        cfg = _settings(budget=1.0)
        with patch("papertriage.llm.client.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _make_tool_response()

            client = ClaudeClient(cfg)
            with client.run("run-a"):
                client.call_tool("claude-haiku-4-5", "sys", [], _TOOL)

            assert client.get_run_cost("run-b") == 0.0
            assert client.get_run_cost("run-a") > 0.0


class TestCachedBlocks:
    def test_cached_blocks_prepended_with_cache_control(self):
        cfg = _settings()
        with patch("papertriage.llm.client.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _make_tool_response()

            client = ClaudeClient(cfg)
            client.call_tool(
                "claude-haiku-4-5",
                "main system prompt",
                [],
                _TOOL,
                cached_blocks=["block one", "block two"],
            )

            _, kwargs = mock_client.messages.create.call_args
            system = kwargs["system"]

            assert isinstance(system, list)
            assert len(system) == 3  # 2 cached + 1 main

            assert system[0]["type"] == "text"
            assert system[0]["text"] == "block one"
            assert system[0]["cache_control"] == {"type": "ephemeral"}

            assert system[1]["text"] == "block two"
            assert system[1]["cache_control"] == {"type": "ephemeral"}

            assert system[2]["text"] == "main system prompt"
            assert "cache_control" not in system[2]

    def test_no_cached_blocks_passes_plain_string(self):
        cfg = _settings()
        with patch("papertriage.llm.client.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _make_tool_response()

            client = ClaudeClient(cfg)
            client.call_tool("claude-haiku-4-5", "plain system", [], _TOOL)

            _, kwargs = mock_client.messages.create.call_args
            assert kwargs["system"] == "plain system"
