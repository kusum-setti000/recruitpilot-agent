---
paths:
  - "app.py"
  - "agent/service.py"
  - "agent/storage.py"
  - "tests/test_app*.py"
  - "tests/test_service*.py"
---
# Web app and service layer rules

- The UI is Gradio (`app.py`). It only calls `agent/service.py::RecruitingService`; it never imports matching, heuristics or llm directly.
- `RecruitingService.stream(jd_text, provider)` is a generator that yields a typed update after each of the five steps, so the UI can show the funnel filling in live. The CLI uses the same service.
- Streaming comes from `RecruitingPipeline.iter_steps()`. `run()` must stay a thin wrapper over it so the CLI and existing tests keep working.
- The UI must show, in order: JD analysis, warm-bench results (matches and policy exclusions), Top 10 with score breakdown, Top 3 with ratings, and the final pick with the full justification. Every number on screen comes from the run result, nothing recomputed in the UI.
- Inputs: paste a JD or upload a .txt / .md file; provider selector (auto / anthropic / openai / mock); a "hide names" toggle. Show which provider actually ran and whether any step fell back.
- Outputs: a downloadable `recruiting_report.md` for each run, and a History tab listing past runs from SQLite (`runs/history.db`) that can be reopened.
- Never display or accept API keys in the UI. Keys come only from `.env`.
- Bind to 127.0.0.1 by default. No `share=True` unless the user explicitly asks.
- Errors in the UI are friendly sentences, never stack traces; details go to the log.
- Keep it fast in mock mode (the whole funnel should render in a few seconds) so it demos well without a key.
