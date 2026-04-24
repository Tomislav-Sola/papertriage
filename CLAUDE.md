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
