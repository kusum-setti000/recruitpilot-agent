---
paths:
  - "**/*.py"
---
# Python conventions

- Python 3.13, `from __future__ import annotations` at the top of every module.
- Type hints on every public function. Pydantic v2 models for anything that crosses a module boundary or comes from an LLM.
- Keep modules single purpose: matching logic stays in `agent/matching.py`, prompt text stays in `agent/prompts.py`, model calls stay in `agent/llm.py`.
- No print statements in `agent/`; terminal output goes through `agent/display.py`, logging through `logging`.
- Configuration comes from `agent/config.py` (env vars). Do not read `os.environ` elsewhere.
- Prefer small pure functions that are easy to unit test. No hidden global state beyond the skill vocabulary.
- Line length 120. Module docstring explains *why* the module exists, not just what it does.
