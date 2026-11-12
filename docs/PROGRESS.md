# Project progress

Single source of truth for where this project stands. Claude Code updates this at the end of every phase or task, then commits and pushes.

## Current status
Phase 3 complete. Streaming engine, service layer, and SQLite history built and tested. 18 tests pass offline, mock CLI still works. Ready for Phase 4 (Gradio web app).

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

## In progress
- Nothing yet

## Next (from docs/MASTER_PROMPT.md)
- Phase 2: live model run and comparison — SKIPPED (no API key configured)
- Phase 4: Gradio web app (`app.py`)
- Phase 4: Gradio web app (`app.py`) — pending gradio install approval
- Phase 5: review and harden (code-reviewer, fairness-auditor)
- Phase 6: README, run_app.ps1, hand-over summary

## Known issues / decisions
- No LinkedIn API access: external pool is simulated; real sources plug in via agent/sources (no scraping)
- OPENAI_MODEL default is a placeholder; confirm the model name before live runs
- README.md says "9 offline tests" — stale; actual count is 11; will fix in Phase 6

## Log
- 2026-11-11: Project scaffolded, engine and CLI built, 11 offline tests passing, Claude Code setup files added.
- 2026-11-11: Phase 0 — orientation complete; all 6 subagents valid; code/rules/CLAUDE.md consistent; five-step funnel documented.
- 2026-11-11: Phase 1 — 11 tests pass offline; mock CLI runs all five steps, writes recruiting_report.md, selects INT-001; no API keys present; Phase 2 skipped.
- 2026-11-11: Phase 3 — added iter_steps() to pipeline; created agent/service.py (RecruitingService; new pipeline per run; no os.environ mutation; Pydantic-safe Settings.replace); created agent/storage.py (SQLite, proper JSON serialization of Pydantic models); updated recruiting_agent.py to use service; added tests/test_service.py (7 tests); 18 total pass.
