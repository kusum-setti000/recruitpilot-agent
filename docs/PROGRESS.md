# Project progress

Single source of truth for where this project stands. Claude Code updates this at the end of every phase or task, then commits and pushes.

## Current status
Engine and CLI complete and tested offline (11 tests). Claude Code setup in place (CLAUDE.md, 4 rules, 6 subagents, /verify). Web app not started.

## Done
- Five-step funnel: JD analysis, internal warm bench first, external search to Top 10, Top 3, final pick with justification
- Synthetic data: 20 internal past hires, 100 external profiles (seeded generator)
- LLM layer: Anthropic / OpenAI / mock, schema-validated with retries and deterministic fallback; names hidden from the model
- Placeholder-key detection and fail-fast on rejected API keys
- Terminal funnel view (narrow-terminal friendly) and markdown report
- Claude Code configuration: CLAUDE.md, rules (python-style, llm-usage, data-and-privacy, testing, app-ui), subagents (code-reviewer, test-runner, prompt-engineer, source-integrator, fairness-auditor, app-builder), /verify command

## In progress
- Nothing yet

## Next (from docs/MASTER_PROMPT.md)
- Phase 0: connect and orient
- Phase 1: verify baseline
- Phase 2: live model run and comparison (needs a key in .env)
- Phase 3: streaming engine, service layer, SQLite run history
- Phase 4: Gradio web app
- Phase 5: review and harden (code-reviewer, fairness-auditor)
- Phase 6: README, run_app.ps1, hand-over summary

## Known issues / decisions
- No LinkedIn API access: external pool is simulated; real sources plug in via agent/sources (no scraping)
- OPENAI_MODEL default is a placeholder; confirm the model name before live runs

## Log
- 2026-11-11: Project scaffolded, engine and CLI built, 11 offline tests passing, Claude Code setup files added.
