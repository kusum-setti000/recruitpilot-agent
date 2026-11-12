# Project progress

Single source of truth for where this project stands. Claude Code updates this at the end of every phase or task, then commits and pushes.

## Current status
Phase 5 complete. Code-reviewer (4 SHOULD-FIX, 5 LOW) and fairness-auditor (0 BLOCKER, 9 SHOULD-FIX, 6 LOW) run; all SHOULD-FIX and selected fairness HIGH findings fixed. 27 tests pass. Ready for Phase 6 (docs and hand-over).

## Done
- Five-step funnel: JD analysis, internal warm bench first, external search to Top 10, Top 3, final pick with justification
- Synthetic data: 20 internal past hires, 100 external profiles (seeded generator)
- LLM layer: Anthropic / OpenAI / mock, schema-validated with retries and deterministic fallback; names hidden from the model
- Placeholder-key detection and fail-fast on rejected API keys
- Terminal funnel view (narrow-terminal friendly) and markdown report
- Claude Code configuration: CLAUDE.md, rules (python-style, llm-usage, data-and-privacy, testing, app-ui), subagents (code-reviewer, test-runner, prompt-engineer, source-integrator, fairness-auditor, app-builder), /verify command
- **Phase 0**: subagent and rules/code consistency check; five-step funnel documented; one stale README test count noted (fix in Phase 6)
- **Phase 1**: 11 tests pass; mock CLI all five steps; `recruiting_report.md` written; selected INT-001; no API keys configured
- **Phase 3**: `iter_steps()` added to pipeline; `agent/service.py` (RecruitingService, new pipeline per run, no os.environ mutation); `agent/storage.py` (SQLite, proper Pydantic serialization); `recruiting_agent.py` switched to service; 7 new service tests; 18 total pass
- **Phase 4**: `app.py` Gradio web app; dark mission-control theme; live stat strip; numbered step accordions 01–05 (auto-open step by step); History tab with dropdown; `gradio>=6,<7` pinned (6.31.0 installed); 27 total pass (9 app tests incl. blank-line and 14-tuple checks)
- **Phase 5**: code-reviewer (SF-1–SF-4 fixed) + fairness-auditor (0 BLOCKERs; S3, S7, L5 fixed; 7 items in backlog); 27 total pass

## In progress
- Nothing

## Next (from docs/MASTER_PROMPT.md)
- Phase 2: live model run and comparison — SKIPPED (no API key configured)
- Phase 6: complete (see Done)

## Known issues / decisions
- No LinkedIn API access: external pool is simulated; real sources plug in via agent/sources (no scraping)
- OPENAI_MODEL default is a placeholder; confirm the model name before live runs
- Fairness SHOULD-FIX backlog: location check inconsistency (S1), triple internal preference (S2), uncapped years-of-experience score (S4), raw location sent to LLM (S6), one-sided rejection reasons (S5), score breakdown not shown on screen (S8), LLM schemas lack mandatory explanations (S9) — documented for next sprint

## Log
- 2026-11-11: Project scaffolded, engine and CLI built, 11 offline tests passing, Claude Code setup files added.
- 2026-11-11: Phase 0 — orientation complete; all 6 subagents valid; code/rules/CLAUDE.md consistent; five-step funnel documented.
- 2026-11-11: Phase 1 — 11 tests pass offline; mock CLI runs all five steps, writes recruiting_report.md, selects INT-001; no API keys present; Phase 2 skipped.
- 2026-11-11: Phase 3 — added iter_steps() to pipeline; created agent/service.py (RecruitingService; new pipeline per run; no os.environ mutation; Pydantic-safe Settings.replace); created agent/storage.py (SQLite, proper JSON serialization of Pydantic models); updated recruiting_agent.py to use service; added tests/test_service.py (7 tests); 18 total pass.
- 2026-11-11: Phase 4 — built app.py (Gradio Blocks, dark mission-control theme, stat strip, numbered steps, History with reopen); added tests/test_app.py (8 tests); pinned gradio>=6,<7 (6.31.0 installed); 26 total pass. Applied corrections: JD prefill, hide_names in step5, fallback info in status, stat strip output, yield count fixes, CSS theme per app-ui.md visual theme spec.
- 2026-11-11: Phase 4 review fixes — _fmt_step5 blank lines (markdown renders); accordions auto-open step-by-step (14-tuple yields); CSS via gr.HTML style tag (no deprecation warning); friendly error messages in UI; RecruitingService.get_run() added; History tab dropdown replaces textbox+button; app.py no longer imports agent.storage; test_fmt_step5_blank_lines_after_div added; 27 total pass.
- 2026-11-11: Phase 4: moved CSS to launch() — css=_CSS on demo.launch() instead of gr.Blocks(); no deprecation warning confirmed.
- 2026-11-11: Phase 5 — code-reviewer: removed misleading hide_names from service API (SF-1); fixed os.environ mutation with _DEFAULT_PROVIDER module var (SF-2); fixed dead test code in test_list_runs (SF-3); app.py now uses stored report from SQLite instead of rebuilding (SF-4). Fairness-auditor: no BLOCKERs; warm-bench tiebreak now requires missing_core ≤ pick's (S3); confidence dead code fixed (L5); report footer accurate when SEND_NAMES_TO_LLM=true (S7); test uses dataclasses.replace (L-5). 27 total pass.
