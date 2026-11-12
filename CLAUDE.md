# AI Recruiting Agent

JD in, one recommended hire with a recruiter-grade justification out. Python 3.13.
Two front doors over one engine: a CLI (`recruiting_agent.py`) and a web app (`app.py`, Gradio).
Developed on Windows with PowerShell in VS Code; commands below are PowerShell-friendly.

## The funnel (do not reorder these steps)
1. JD analysis: LLM turns the JD into `JDAnalysis` (must-haves with alternatives, bonus skills, min years, Boolean queries).
2. Internal warm bench FIRST: `data/internal_past_hires.json`, filtered by re-hire policy, then matched.
3. External pool: Boolean search plus hybrid score over every external source, combined with internal matches into a Top 10.
4. LLM deep evaluation of the 10, picks Top 3.
5. LLM final pick with comparison to the other finalists and the pool, gaps, risks, interview focus.

## Architecture (layers only call downward)
- Interfaces: `recruiting_agent.py` (CLI) and `app.py` (Gradio web app). No business logic here.
- Service: `agent/service.py` (`RecruitingService`) starts runs, streams step updates, saves run history. Both interfaces use it.
- Engine: `agent/pipeline.py` orchestrates the five steps; `RecruitingPipeline.iter_steps()` yields after each step and `run()` consumes it.
- Logic: `agent/matching.py`, `agent/heuristics.py`, `agent/skills_vocab.py`.
- Model access: `agent/llm.py` is the only place that talks to a model (`LLMClient.structured(...)`: schema, validator, fallback).
- Data: `agent/sources/` adapters (`CandidateSource.load()`), `agent/storage.py` SQLite run history in `runs/history.db`.
- Prompts and schemas: `agent/prompts.py`, `agent/models.py`. Reports: `agent/report.py` (markdown), `agent/display.py` (terminal).

## Commands
- Tests: `python -m pytest -q` (must stay green, runs offline)
- CLI offline: `python recruiting_agent.py --provider mock`
- CLI live: key in `.env`, then `python recruiting_agent.py`
- Web app: `python app.py` then open http://127.0.0.1:7860 (add `--provider mock` to force offline)
- Regenerate data: `python scripts/generate_dummy_data.py`
- Quick health check: `/verify`

## Non-negotiables
- Internal warm bench is always checked before any external source.
- Candidate names never go to the LLM unless `SEND_NAMES_TO_LLM=true`. Use `Candidate.llm_view()`.
- Every LLM output is validated against its schema AND business rules (IDs must come from the input list).
- The pipeline, CLI and app must all work with no API key (mock provider). Never break the fallback path.
- Never read, print or log `.env` or key values. Check key presence with `agent.config.looks_like_real_key`.
- No scraping of LinkedIn or any site. Live sources go through licensed APIs only (see `agent/sources/linkedin.py`).
- Never commit `.env`, `runs/`, or real candidate data.
- Keep the CLI working whenever the app changes, and vice versa.

## How to work in this repo
- Plan before multi-file changes and wait for approval; then make surgical edits. Do not restyle code you were not asked to touch.
- After every change: run the tests, then the mock pipeline. Report results honestly, including failures.
- Delegate: `test-runner` for verification, `code-reviewer` before finishing a phase, `app-builder` for UI and service work,
  `prompt-engineer` for prompts and schemas, `source-integrator` for new data sources, `fairness-auditor` before demos.

## Progress log and GitHub (do this at the end of every phase or task)
- `docs/PROGRESS.md` is the single source of truth for project status. A reviewer reads it from GitHub to decide the next step.
- After each phase or task: update `docs/PROGRESS.md` (move items between Done / In progress / Next, add a dated entry to the
  log with what changed, test count, and anything unverified or blocked), then commit and push.
- Commit messages: `Phase N: <short summary>` for master-prompt phases, otherwise `<area>: <short summary>`.
- Run `git status` before committing and make sure `.env`, `.venv/`, `runs/` and `__pycache__/` are not staged.
- Push to `origin main` only after tests pass. If tests fail, commit to a branch named `wip/<topic>` instead and say so in the log.
- Never force push, rewrite history, or delete branches without asking.

Detailed conventions are in `.claude/rules/`. Specialised helpers are in `.claude/agents/`.
