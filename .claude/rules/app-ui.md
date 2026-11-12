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

## Visual theme

Aerospace mission-control aesthetic. No logos, names or imagery from real companies.

**Colors** (define as CSS custom properties on `:root`):
- `--rp-bg: #0B0C0E` — page background
- `--rp-panel: #1D1F22` — component panels
- `--rp-divider: #23262B` — divider lines
- `--rp-border: #33363C` — borders
- `--rp-text-primary: #F2F2F0` — body text (WCAG AA against `--rp-bg`)
- `--rp-text-secondary: #C9C3B6` — secondary text
- `--rp-text-muted: #8A8D93` — muted labels
- `--rp-accent: #E5402E` — used ONLY for: Run button, active-tab underline, selected-candidate card left border, "Selected" stat value. No other uses.

**Fonts** (load from Google Fonts via `@import`):
- `"Saira Condensed"` weight 500–600, uppercase, letter-spacing 0.06–0.22em → headings, app name, accordion labels
- `"Manrope"` weight 400–500, 13–14px → all body text
- `"JetBrains Mono"` weight 400, 11–12px, uppercase, 0.08em spacing → labels, IDs, scores, stat labels

**Sizes**: page title 30px, stat numbers 34px, section headings 14px.

**Component style**: border-radius 0 (square corners), 1px hairline borders on panels, no shadows, no gradients. Skill chips are `code`-styled (outlined, not filled). Sections separated by `<hr>` divider lines, not nested cards.

**Layout**:
- Top bar: app name `RECRUIT PILOT` in Saira Condensed spaced caps, then Run / History tabs with accent underline on the active tab.
- Hero stat strip (4 cells, row below the title): "Profiles Screened", "Warm Bench", "Shortlisted", "Selected". Updates live as the pipeline streams. "Selected" cell value uses `--rp-accent`.
- Inputs in a `scale=1` left column; five numbered step sections (`01 · JD Analysis` … `05 · Selected`) stacked in a `scale=2` right column.
- Selected-candidate card: 3px `--rp-accent` left border, `padding-left: 12px`.

**CSS test**: `tests/test_app.py` must assert that `app._CSS` contains `#E5402E`, `Saira Condensed`, `Manrope`, and `JetBrains Mono`.
