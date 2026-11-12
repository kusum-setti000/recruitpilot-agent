# AI Recruiting Agent

Paste a job description, get one recommended hire back with a recruiter-grade explanation of why that
person beat every other applicant. The agent works like a recruiter would: it reads the JD, checks the
people you have hired before, then searches the wider market, narrows 120 profiles to 10, then 3, then 1.

```
 jd.txt
   │
   ▼
 STEP 1  JD analysis (LLM)  ──►  must-haves (+ alternatives), bonus skills, min years, Boolean queries
   │
   ▼
 STEP 2  Internal warm bench FIRST   data/internal_past_hires.json (20)
   │      re-hire policy: contract ended, re-hire eligible, rating ≥ 3.5, available within 60 days
   │      then skill match  ──►  "Internal Re-hire Matches" + LLM fit notes
   ▼
 STEP 3  External pool               data/external_talent_pool.json (100)  [+ future APIs]
   │      Boolean search + hybrid score (skills, experience, BM25, title)  ──►  Top 10 (internal + external)
   ▼
 STEP 4  Deep evaluation (LLM)  ──►  skill / depth / domain / overall for all 10  ──►  Top 3
   ▼
 STEP 5  Final pick (LLM)  ──►  1 hire + why, vs each finalist, vs the pool, gaps, risks, interview focus
   ▼
 terminal funnel  +  recruiting_report.md
```

## Quick start (Windows PowerShell)

```powershell
cd ai-recruiting-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python recruiting_agent.py --provider mock     # offline run, no key needed
pytest -q                                      # 27 offline tests
```

To use a real model, copy `.env.example` to `.env` and paste ONE key:

```powershell
Copy-Item .env.example .env
notepad .env        # set ANTHROPIC_API_KEY=... (or OPENAI_API_KEY=...)
python recruiting_agent.py
```

Other CLI flags:

```powershell
python recruiting_agent.py --jd C:\path\to\another_jd.txt
python recruiting_agent.py --interactive        # paste a JD into the terminal
python recruiting_agent.py --hide-names         # IDs only on screen
python scripts/generate_dummy_data.py --seed 7  # new synthetic dataset
```

## Application (Gradio web UI)

RecruitPilot is the browser interface over the same five-step engine. Launch it with:

```powershell
python app.py --provider mock    # offline, no key needed
# then open http://127.0.0.1:7860
```

Or use the helper script (activates `.venv` automatically):

```powershell
.\run_app.ps1 --provider mock
```

### What you see

**Run tab** — paste or upload a job description, pick a provider, then click **Run**. Five accordion panels open one by one as the pipeline streams results:

| Panel | Opens when… | What it shows |
|---|---|---|
| 01 · JD Analysis | Step 1 completes | Must-have skills with alternatives, bonus skills, min years, Boolean queries |
| 02 · Warm Bench | Step 2 completes | Internal re-hire matches with LLM fit notes; excluded hires with policy reason |
| 03 · Top 10 Shortlist | Step 3 completes | All 10 candidates with origin, years, hybrid score, must-have coverage |
| 04 · Evaluation & Top 3 | Step 4 completes | LLM ratings (skill / depth / domain / overall); Top 3 highlighted |
| 05 · Selected | Step 5 completes | Final pick: headline, full justification, why-not-each-finalist, gaps, risks, interview focus |

A stat strip above the panels updates live (Profiles Screened → Warm Bench → Shortlisted → **Selected**). When done: the status bar shows the provider that ran and any fallback steps; a **Download Report** button saves the full markdown; the report preview appears below.

**History tab** — every completed run is saved to `runs/history.db`. A table shows past runs and a dropdown lets you reopen any saved report. Click **Refresh** after new runs.

### Demo run (under two minutes)

1. `.\run_app.ps1 --provider mock`
2. Open http://127.0.0.1:7860
3. The JD is prefilled — click **Run** (mock mode takes ~3 seconds)
4. Watch the five accordions open one by one; the stat strip fills in
5. Click **Download Report (.md)** to save the markdown
6. Click **History** → the run appears; select it from the dropdown to reopen the report

## How the LLM is used safely

Every model call goes through `LLMClient.structured()` in `agent/llm.py`. The model must answer in a
Pydantic schema (Anthropic: forced tool use; OpenAI: JSON mode), the answer is checked against business
rules (for example "the 3 finalists must be IDs from the shortlist"), invalid answers are retried with
the error fed back, and if the model still fails the step falls back to the deterministic logic in
`agent/heuristics.py`. That is also what runs in mock mode, so the pipeline always produces a result and
you always have a baseline to compare the LLM against.

Names are never sent to the model (`Candidate.llm_view()`); it sees IDs and job-relevant fields only.

## The LinkedIn barrier

LinkedIn's profile search API is only available to approved partners, and scraping breaks their terms.
So the data layer is an interface: `agent/sources/base.py::CandidateSource`. Today two JSON adapters
implement it. `agent/sources/linkedin.py` is the documented stub for a real provider (LinkedIn RSC via an
ATS, or a licensed vendor such as Bright Data, People Data Labs or Coresignal). Add the adapter, register
it, set `EXTERNAL_SOURCES=json_external,<name>` and nothing else changes.

## Project layout

```
recruitpilot-agent/
├── app.py                       Gradio web app (browser UI)
├── recruiting_agent.py          CLI entry point
├── run_app.ps1                  helper: activate .venv then start app.py
├── jd.txt                       sample JD (Senior Generative AI Engineer)
├── agent/
│   ├── config.py                env settings and recruiter policy knobs
│   ├── models.py                Candidate + LLM output schemas
│   ├── llm.py                   provider-agnostic structured calls, retry, fallback
│   ├── prompts.py               prompt text and recruiter persona
│   ├── pipeline.py              the five steps + iter_steps() streaming generator
│   ├── service.py               RecruitingService: stream, run, list_runs, get_run
│   ├── storage.py               SQLite run history (runs/history.db)
│   ├── heuristics.py            deterministic version of each LLM step
│   ├── matching.py              requirement checks, BM25, Boolean parser, hybrid score
│   ├── skills_vocab.py          aliases + implications (pgvector ⇒ Vector Databases)
│   ├── display.py / report.py   terminal funnel and markdown report
│   └── sources/                 CandidateSource interface + adapters
├── data/                        20 internal + 100 external synthetic profiles
├── scripts/generate_dummy_data.py
├── tests/
│   ├── test_pipeline.py         11 offline funnel tests
│   ├── test_service.py          7 service + storage tests
│   └── test_app.py              9 app callback tests
├── docs/PROGRESS.md             project status (single source of truth)
├── CLAUDE.md                    project memory for Claude Code
└── .claude/
    ├── settings.json            allowed commands, .env read-blocked
    ├── rules/                   python-style, llm-usage, data-and-privacy, testing, app-ui
    └── agents/                  code-reviewer, test-runner, prompt-engineer, source-integrator,
                                 fairness-auditor, app-builder
```

## Recommended stack for the next iterations (kept distinct from HireSphere-AI)

| Need | HireSphere-AI used | Recommended here | Why |
|---|---|---|---|
| Orchestration | LangChain, LangGraph | Plain typed pipeline now; PydanticAI or the Claude Agent SDK if it grows | Shows a second, framework-light pattern |
| Structured output | Structured interfaces | Pydantic schemas + forced tool use (done) | Validated, retryable, provider-agnostic |
| Storage | PostgreSQL, SQLAlchemy, Alembic | SQLite (via `sqlite-utils`) | Zero setup, good for a CLI agent |
| Vector search | pgvector (planned) | LanceDB or Chroma + local `bge-small` embeddings | Embedded, no server |
| Observability | LangSmith | Langfuse (open source, self-hostable) | Different tool, same value |
| LLM evals | — | promptfoo or DeepEval on a set of JDs with expected Top 3 | Regression gate for prompt changes |
| UI | Next.js, React | Gradio or Chainlit | Fast demo UI in Python |
| Tooling | pip | uv + ruff | Faster installs, one linter/formatter |

## Claude Code setup

`CLAUDE.md` loads every session and holds the project overview and non-negotiables. `.claude/rules/*.md`
hold detailed conventions; files with `paths:` frontmatter only apply when Claude works on matching
files. `.claude/agents/*.md` are subagents Claude can delegate to; call them by name, for example
"use the code-reviewer subagent on my last change". `docs/user-CLAUDE.md.template` is a personal file to
copy into `~/.claude/CLAUDE.md` so your working preferences apply in every project.

All candidate data in this repository is synthetic.
