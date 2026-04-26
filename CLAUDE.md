# CLAUDE.md

## Project ground rules
- Python 3.11+. Use `pip` with `pyproject.toml`. Not Poetry.
- Before running any shell command that installs packages or touches the network, explain what it does and wait for approval.
- Never commit `.env`, `data/`, `outputs/`, `*.db`.
- Prefer small, reviewable commits. After each phase, stop and summarize so I can commit.
- If about to create more than 10 files, pause and list them first.
- Do not run `git push`. I push manually.
- If a dependency needs a system library, call it out — do not assume it's installed.
- All LLM calls go through a single client wrapper. No scattered `anthropic.Anthropic()` calls.

## My environment
- Windows 11 + WSL2 (Ubuntu), Claude Code from WSL.
- Editing in PyCharm over the WSL filesystem.
- Python venv at `.venv` in project root.

## How this project is organized

- **Architecture diagram**: see `README.md` for a full diagram of the 5-stage pipeline and
  how data flows from PDFs to the final report, including which model handles each stage.

- **Adding a new pipeline stage**: create `src/papertriage/<stage>/` containing:
  - `schema.py` — Pydantic models for the stage's input and output types
  - `<stage>.py` — the stage module with a single public function
  Then wire the stage into `src/papertriage/orchestration/pipeline.py` (add the call in
  sequence) and `src/papertriage/orchestration/context.py` (add an output field to
  `RunContext`).

- **LLM call rule**: every LLM call must go through `ClaudeClient`
  (`src/papertriage/llm/client.py`). No `anthropic.Anthropic()` calls anywhere else in
  the codebase. This is enforced by convention; grep for `anthropic.Anthropic(` to audit.

- **Adding a new prompt**: create a versioned `.md` file under
  `src/papertriage/llm/prompts/` (e.g., `my_stage_v1.md`). Load it with
  `Path(__file__).parent.parent / "llm" / "prompts" / "my_stage_v1.md"`. Never inline
  prompt strings inside stage modules.
