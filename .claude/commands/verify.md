---
description: Run the full health check (tests, CLI in mock mode, app import) and report results
---
Use the test-runner subagent to do a full health check of this project and report back briefly:

1. `python -m pytest -q` and the pass/fail count.
2. `python recruiting_agent.py --provider mock --hide-names` and confirm all five steps printed and `recruiting_report.md` was written. Name the selected candidate ID.
3. If `app.py` exists, `python -c "import app"` to confirm the app imports cleanly.
4. Whether a usable API key is configured, checked only with `agent.config.looks_like_real_key` (never print or read the key itself).

Do not edit any files unless something fails; if it does, explain the root cause and propose the fix before changing anything. $ARGUMENTS
