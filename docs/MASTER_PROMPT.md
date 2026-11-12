You are working in my AI Recruiting Agent project. I want you to connect everything that is already set up here, prove the engine works, and then turn it into an application I can open in a browser and use, while keeping the CLI working.

CONTEXT YOU MUST LOAD FIRST
Read CLAUDE.md, every file in .claude/rules, every file in .claude/agents, .claude/commands/verify.md, README.md, and the code under agent/ plus recruiting_agent.py. Treat CLAUDE.md and the rules as binding. Do not read .env and never print or log any key; to know whether a usable key exists, call agent.config.looks_like_real_key on the environment values and report only yes or no per provider.

WHAT THE PRODUCT DOES (do not change this behaviour)
A recruiter pastes a job description. The agent analyses it and extracts must-have skills (with acceptable alternatives), bonus skills, minimum years, seniority, domain terms and Boolean search queries. It checks our internal database of past hires FIRST (contract ended, re-hire eligible, rating at least 3.5, available within 60 days), then searches the external talent pool (simulated LinkedIn and portal data, because we have no LinkedIn API access), combines them into a Top 10, evaluates those deeply to pick a Top 3, and selects one hire with a recruiter-grade justification: why this person, why not each other finalist, why not the rest of the pool, gaps, risks and interview focus. Names are hidden from the model, every LLM answer is schema-validated with business-rule checks, and every step has a deterministic fallback so it works with no key.

TARGET APPLICATION
A local web app built with Gradio in app.py, on top of a new service layer, with SQLite run history. Layers only call downward: app.py and recruiting_agent.py call agent/service.py (RecruitingService), which calls agent/pipeline.py, which uses matching, heuristics, llm and sources. Gradio is my choice for this project on purpose, because my earlier projects used Next.js and Streamlit.

HOW TO WORK
Use plan mode first. Give me one consolidated plan covering all phases below (files to add or change, new dependencies, risks, how you will test), then stop and wait for my approval. After I approve, execute the phases in order without stopping, except when a phase's tests fail and you cannot fix them, a decision is genuinely mine, or you need a package installed (ask me before installing). At the end of each phase print a short status block with the phase name, what changed, test results, and anything not verified, then update docs/PROGRESS.md and commit and push exactly as the "Progress log and GitHub" section of CLAUDE.md says, so the status is visible on GitHub. Make surgical changes only and do not restyle or refactor code that the phase does not require. Delegate to the subagents named in each phase and tell me when you do.

PHASE 0, CONNECT AND ORIENT
Run /agents mentally against .claude/agents and confirm all six subagents are valid (code-reviewer, test-runner, prompt-engineer, source-integrator, fairness-auditor, app-builder) and that their tool lists and descriptions are sensible. Check that CLAUDE.md, the rules and the agents agree with the actual code (file names, function names, commands). If anything is inconsistent, propose the exact md edits in your plan rather than guessing. Explain the five-step funnel back to me in a short paragraph naming the file and function for each step.

PHASE 1, VERIFY THE BASELINE
Run /verify (it uses the test-runner subagent). Expected: all tests pass offline, the mock CLI prints all five steps, writes recruiting_report.md, and selects a finalist. If anything fails, find the root cause, fix it minimally, and add a test that reproduces it.

PHASE 2, LIVE MODEL RUN
If a usable key is configured, use the prompt-engineer subagent to run the CLI once in mock mode and once live on jd.txt, then compare the JD analysis, the Top 3 and the final pick. Report differences, which result is more defensible, and whether any live step fell back (the run output says which). Do not change prompts in this phase; just give recommendations. If no key is configured, say so in one line and skip to Phase 3.

PHASE 3, STREAMING ENGINE AND SERVICE LAYER
Delegate to the app-builder subagent. Add RecruitingPipeline.iter_steps(jd_text) that yields (step_number, PipelineResult) after each of the five steps, and make run() a thin wrapper around it so existing behaviour and tests are unchanged. Create agent/service.py with RecruitingService exposing stream(jd_text, provider, hide_names), run(jd_text, provider), and access to history, with provider overrides applied without mutating global state between runs. Create agent/storage.py using the standard library sqlite3 with the database at runs/history.db (path configurable through config so tests can use a temp file); store run id, timestamp, provider label, job title, selected candidate id, the report markdown, and the full result as JSON; provide save_run, list_runs and get_run. Switch recruiting_agent.py to use the service while keeping every current flag and the same terminal output. Add offline tests for streaming order (steps 1 to 5 in order), storage round trip, and the service with the mock provider.

PHASE 4, THE WEB APP
Still with app-builder, and following .claude/rules/app-ui.md exactly. Build app.py with Gradio Blocks:
an input area with a large JD text box prefilled from jd.txt, a .txt or .md upload that fills the box, a provider dropdown (auto, anthropic, openai, mock) defaulting to auto, a hide-names toggle, and a Run button;
a results area that fills in live as each step finishes: Step 1 JD analysis (must-haves with alternatives, bonus skills, years, seniority, domain, Boolean queries with hit counts), Step 2 warm bench (re-hire matches with fit notes, plus a collapsible list of exclusions with reasons), Step 3 Top 10 table with origin and score breakdown, Step 4 Top 3 with skill, depth, domain and overall ratings plus the rationale, Step 5 final pick card with the full justification, comparisons, gaps, risks and interview focus;
a status line showing which provider ran and whether any step used the deterministic fallback;
a download for the run's markdown report;
a History tab listing past runs (time, job title, provider, selected candidate) that can be reopened to show the saved report.
Support python app.py --provider mock and --port, bind to 127.0.0.1, port 7860 by default, no share link. Add gradio to requirements.txt (ask me before installing). Test the callback functions directly offline; do not launch a server inside tests. Finally start the app in mock mode, confirm it serves, and stop it.

PHASE 5, REVIEW AND HARDEN
Run the code-reviewer subagent on everything changed in Phases 3 and 4 and fix blockers and should-fix items. Then run the fairness-auditor subagent and report its summary; fix only High findings, list the rest. Re-run /verify.

PHASE 6, DOCUMENT AND HAND OVER
Update README.md with an Application section (what it is, how to launch on Windows PowerShell, screenshot description of each step, how history works) and update CLAUDE.md and the rules only where the code now differs from what they say. Add run_app.ps1 that activates .venv if present and starts the app. Then give me a final summary: how to launch the app, the exact commands, the test count, what I should click to demo it end to end in under two minutes, and the three most valuable next improvements.

DEFINITION OF DONE
python -m pytest -q passes offline; python recruiting_agent.py --provider mock works exactly as before; python app.py --provider mock opens at http://127.0.0.1:7860 and a run shows all five steps filling in, produces a downloadable report, and appears in History; nothing reads or exposes .env; no LinkedIn scraping anywhere; names never reach the model unless SEND_NAMES_TO_LLM is true.

Start now with Phase 0 and the consolidated plan, then wait for my approval.
