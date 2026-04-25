import contextvars
import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Generator

import anthropic
from pydantic import BaseModel

from papertriage.core.config import Settings, settings as _default_settings
from papertriage.core.exceptions import BudgetExceededError, LLMError
from papertriage.core.logging import get_logger
from papertriage.llm.cost import estimate

_run_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "claude_run_id", default=None
)

_log = get_logger(__name__)


def pydantic_to_tool(name: str, description: str, model: type[BaseModel]) -> dict:
    """Convert a Pydantic model into an Anthropic tool definition."""
    raw_schema = model.model_json_schema()
    defs = raw_schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            ref_name = node["$ref"].split("/")[-1]
            return resolve(defs.get(ref_name, node))
        return {k: resolve(v) for k, v in node.items() if k not in ("title", "$schema")}

    schema = resolve(raw_schema)
    schema.pop("title", None)

    return {
        "name": name,
        "description": description,
        "input_schema": schema,
    }


class ClaudeClient:
    def __init__(self, cfg: Settings | None = None) -> None:
        self._cfg = cfg or _default_settings
        self._client = anthropic.Anthropic(api_key=self._cfg.anthropic_api_key)
        self._costs: dict[str, float] = defaultdict(float)
        self._log = get_logger(__name__)

    @contextmanager
    def run(self, run_id: str) -> Generator[None, None, None]:
        token = _run_id_var.set(run_id)
        try:
            yield
        finally:
            _run_id_var.reset(token)

    def _current_run_id(self) -> str:
        return _run_id_var.get() or "__default__"

    def _check_budget(self, run_id: str, added: float) -> None:
        self._costs[run_id] += added
        if self._costs[run_id] > self._cfg.run_budget_usd:
            raise BudgetExceededError(run_id, self._costs[run_id], self._cfg.run_budget_usd)

    def _build_system_with_cache(
        self, system: str, cached_blocks: list[str] | None
    ) -> list[dict] | str:
        if not cached_blocks:
            return system
        blocks: list[dict] = []
        for block_text in cached_blocks:
            blocks.append(
                {
                    "type": "text",
                    "text": block_text,
                    "cache_control": {"type": "ephemeral"},
                }
            )
        blocks.append({"type": "text", "text": system})
        return blocks

    def call_tool(
        self,
        model: str,
        system: str,
        messages: list[dict],
        tool: dict,
        cached_blocks: list[str] | None = None,
    ) -> dict:
        run_id = self._current_run_id()
        system_payload = self._build_system_with_cache(system, cached_blocks)

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                t0 = time.monotonic()
                response = self._client.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=system_payload,
                    messages=messages,
                    tools=[tool],
                    tool_choice={"type": "tool", "name": tool["name"]},
                )
                duration_ms = int((time.monotonic() - t0) * 1000)
                break
            except anthropic.APIError as exc:
                last_exc = exc
                wait = 2**attempt
                self._log.warning(
                    "llm_retry",
                    attempt=attempt + 1,
                    error=str(exc),
                    wait_seconds=wait,
                )
                time.sleep(wait)
        else:
            raise LLMError("LLM call failed after 3 attempts") from last_exc

        cost = estimate(model, response.usage)
        self._check_budget(run_id, cost)

        self._log.info(
            "llm_call",
            run_id=run_id,
            model=model,
            tool_name=tool["name"],
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_creation_tokens=getattr(response.usage, "cache_creation_input_tokens", 0),
            cache_read_tokens=getattr(response.usage, "cache_read_input_tokens", 0),
            cost_usd=round(cost, 6),
            duration_ms=duration_ms,
        )

        for block in response.content:
            if block.type == "tool_use":
                return block.input  # type: ignore[return-value]

        raise LLMError("No tool_use block in response")

    def call_text(
        self,
        model: str,
        system: str,
        messages: list[dict],
        cached_blocks: list[str] | None = None,
    ) -> str:
        run_id = self._current_run_id()
        system_payload = self._build_system_with_cache(system, cached_blocks)

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                t0 = time.monotonic()
                response = self._client.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=system_payload,
                    messages=messages,
                )
                duration_ms = int((time.monotonic() - t0) * 1000)
                break
            except anthropic.APIError as exc:
                last_exc = exc
                wait = 2**attempt
                self._log.warning(
                    "llm_retry",
                    attempt=attempt + 1,
                    error=str(exc),
                    wait_seconds=wait,
                )
                time.sleep(wait)
        else:
            raise LLMError("LLM call failed after 3 attempts") from last_exc

        cost = estimate(model, response.usage)
        self._check_budget(run_id, cost)

        self._log.info(
            "llm_call",
            run_id=run_id,
            model=model,
            tool_name=None,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_creation_tokens=getattr(response.usage, "cache_creation_input_tokens", 0),
            cache_read_tokens=getattr(response.usage, "cache_read_input_tokens", 0),
            cost_usd=round(cost, 6),
            duration_ms=duration_ms,
        )

        return "".join(
            block.text for block in response.content if hasattr(block, "text")
        )

    def get_run_cost(self, run_id: str) -> float:
        return self._costs.get(run_id, 0.0)
