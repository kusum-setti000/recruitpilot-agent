---
paths:
  - "tests/**/*.py"
  - "agent/**/*.py"
  - "app.py"
---
# Testing rules

- `pytest -q` must pass offline before any change is considered done. Tests force `LLM_PROVIDER=mock` and pin `AGENT_TODAY`.
- Never call a real LLM or network in tests. Fake `LLMClient._call` instead (see `test_llm_retry_then_fallback`).
- Service, storage and app tests must use a temporary database path and the mock provider; never start a real server in tests.
- When you change matching weights, aliases or the generator, check that the funnel tests still hold: INT-001 matches, INT-003 and INT-004 are excluded, Top 10 has 10 unique IDs, the final pick is a finalist.
- Add a test for every bug fix that reproduces the bug first.
