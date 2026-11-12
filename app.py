"""Gradio web app for the AI Recruiting Agent.

Provides two tabs:
  - Run: paste or upload a JD, pick a provider, run the pipeline and watch
    the funnel fill in step-by-step.
  - History: browse past runs stored in SQLite and reopen any report.

Business logic lives exclusively in agent/service.py; this file only handles
presentation.
"""
from __future__ import annotations

import argparse
import logging
import os
import tempfile
from pathlib import Path
from typing import Generator

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent

# Prefill the JD textbox with the sample jd.txt if it exists
_jd_path = ROOT / "jd.txt"
_jd_default = _jd_path.read_text(encoding="utf-8") if _jd_path.exists() else ""

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Saira+Condensed:wght@500;600&family=Manrope:wght@400;500&family=JetBrains+Mono:wght@400&display=swap');

:root {
    --rp-bg: #0B0C0E;
    --rp-panel: #1D1F22;
    --rp-divider: #23262B;
    --rp-border: #33363C;
    --rp-text-primary: #F2F2F0;
    --rp-text-secondary: #C9C3B6;
    --rp-text-muted: #8A8D93;
    --rp-accent: #E5402E;
}

body, .gradio-container, .main {
    background: var(--rp-bg) !important;
    color: var(--rp-text-primary) !important;
    font-family: 'Manrope', sans-serif !important;
    font-size: 13px !important;
}

/* Panels and blocks */
.block, .gr-block, .gr-box, .gr-panel,
.gradio-container .block, div[class*="block"] {
    background: var(--rp-panel) !important;
    border: 1px solid var(--rp-border) !important;
    border-radius: 0 !important;
    box-shadow: none !important;
}

/* Text inputs and textareas */
input, textarea, select, .gr-input, .gr-textarea {
    background: var(--rp-bg) !important;
    border: 1px solid var(--rp-border) !important;
    border-radius: 0 !important;
    color: var(--rp-text-primary) !important;
    font-family: 'Manrope', sans-serif !important;
    font-size: 13px !important;
}
input:focus, textarea:focus {
    border-color: var(--rp-accent) !important;
    outline: none !important;
}

/* Labels */
label, .gr-label, span.svelte-1gfkn6j {
    color: var(--rp-text-muted) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}

/* Buttons — base */
button {
    border-radius: 0 !important;
    font-family: 'Saira Condensed', sans-serif !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    box-shadow: none !important;
    border: 1px solid var(--rp-border) !important;
    background: var(--rp-panel) !important;
    color: var(--rp-text-primary) !important;
}

/* Primary button (Run) — accent */
button.primary, .gr-button-primary, button[data-testid="Run"],
button[class*="primary"] {
    background: var(--rp-accent) !important;
    border-color: var(--rp-accent) !important;
    color: #fff !important;
}

/* Tab nav */
.tab-nav, [role="tablist"] {
    background: transparent !important;
    border-bottom: 1px solid var(--rp-divider) !important;
}
.tab-nav button, [role="tab"] {
    color: var(--rp-text-secondary) !important;
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    font-family: 'Saira Condensed', sans-serif !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.12em !important;
    padding-bottom: 8px !important;
}
.tab-nav button.selected, [role="tab"][aria-selected="true"] {
    color: var(--rp-text-primary) !important;
    border-bottom-color: var(--rp-accent) !important;
}

/* Accordions */
.accordion, details, summary {
    background: var(--rp-panel) !important;
    border: 1px solid var(--rp-border) !important;
    border-radius: 0 !important;
}
summary {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: var(--rp-text-muted) !important;
}

/* Dropdowns */
.gr-dropdown, [data-testid*="dropdown"] {
    background: var(--rp-bg) !important;
    border: 1px solid var(--rp-border) !important;
    border-radius: 0 !important;
    color: var(--rp-text-primary) !important;
}

/* Headings in markdown */
h1, h2, h3, h4 {
    font-family: 'Saira Condensed', sans-serif !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: var(--rp-text-primary) !important;
}

/* Code / monospace */
code, pre, .gr-monospace {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
    background: var(--rp-divider) !important;
    border: 1px solid var(--rp-border) !important;
    border-radius: 0 !important;
    color: var(--rp-text-secondary) !important;
}

/* Dividers */
hr { border-color: var(--rp-divider) !important; border-style: solid !important; }

/* App header */
.rp-header {
    font-family: 'Saira Condensed', sans-serif;
    font-size: 30px;
    font-weight: 600;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--rp-text-primary);
    padding: 20px 0 8px 0;
    border-bottom: 1px solid var(--rp-divider);
    margin-bottom: 0;
}

/* Hero stat strip */
.rp-stat-strip {
    display: flex;
    border: 1px solid var(--rp-border);
    margin: 12px 0 16px 0;
}
.rp-stat-cell {
    flex: 1;
    padding: 12px 16px;
    border-right: 1px solid var(--rp-border);
    text-align: center;
}
.rp-stat-cell:last-child { border-right: none; }
.rp-stat-num {
    font-family: 'Saira Condensed', sans-serif;
    font-size: 34px;
    font-weight: 600;
    color: var(--rp-text-primary);
    line-height: 1;
}
.rp-stat-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--rp-text-muted);
    margin-top: 4px;
}
.rp-stat-cell.rp-selected .rp-stat-num { color: var(--rp-accent); }

/* Selected candidate card */
.rp-selected-card {
    border-left: 3px solid var(--rp-accent) !important;
    padding-left: 12px !important;
    margin-top: 8px;
}

/* Tables */
table { border-collapse: collapse !important; width: 100%; }
th, td {
    border: 1px solid var(--rp-border) !important;
    padding: 6px 10px !important;
    font-family: 'Manrope', sans-serif !important;
    font-size: 13px !important;
    color: var(--rp-text-primary) !important;
}
th {
    background: var(--rp-divider) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    color: var(--rp-text-muted) !important;
}
"""


# ---------------------------------------------------------------------------
# Helpers that build HTML/Markdown for each pipeline step
# ---------------------------------------------------------------------------

def _fmt_step1(r) -> str:
    jd = r.jd
    if jd is None:
        return ""
    core = ", ".join(
        sk.name + (f" ({' / '.join(sk.alternatives)})" if sk.alternatives else "")
        for sk in jd.core_skills
    )
    bonus = ", ".join(
        sk.name + (f" ({' / '.join(sk.alternatives)})" if sk.alternatives else "")
        for sk in jd.bonus_skills
    )
    lines = [
        f"**Role:** {jd.job_title} | {jd.seniority} | {jd.min_years_experience}+ yrs",
        f"**Work arrangement:** {jd.work_arrangement or 'not stated'}",
        f"**Must-have:** {core}",
        f"**Bonus:** {bonus}",
        f"**Domain:** {', '.join(jd.domain_keywords) or 'none stated'}",
        f"**Title variants:** {', '.join(jd.title_variants)}",
    ]
    if r.query_hits:
        lines.append("\n**Boolean query hits:**")
        for i, (q, hits) in enumerate(r.query_hits, 1):
            lines.append(f"{i}. `{q}` — {hits} hits")
    return "\n".join(lines)


def _fmt_step2(r) -> str:
    checks = r.internal_checks
    if not checks:
        return ""
    matches = [c for c in checks if c.status == "match"]
    excluded = [c for c in checks if c.status == "excluded"]
    not_fit = [c for c in checks if c.status == "eligible_not_fit"]
    rows = ["| ID | Role | Rating | Status | Note |", "|---|---|---|---|---|"]
    order = {"match": 0, "excluded": 1, "eligible_not_fit": 2}
    for c in sorted(checks, key=lambda x: (order[x.status], -(x.scored.score if x.scored else 0))):
        label = {"match": "Re-hire match", "excluded": "Excluded", "eligible_not_fit": "Not a fit"}[c.status]
        note = (c.note or c.reason or "").replace("|", "/").replace("\n", " ")
        rows.append(f"| {c.candidate.id} | {c.candidate.title} | {c.candidate.performance_rating} | {label} | {note} |")
    summary = f"Checked {len(checks)} past hires: **{len(matches)} re-hire matches**, {len(excluded)} excluded by policy, {len(not_fit)} eligible but not a fit."
    return summary + "\n\n" + "\n".join(rows)


def _fmt_step3(r) -> str:
    if not r.shortlist:
        return ""
    jd = r.jd
    rows = ["| # | ID | Origin | Yrs | Score | Must-haves | Missing |", "|---|---|---|---|---|---|---|"]
    for i, s in enumerate(r.shortlist, 1):
        c = s.candidate
        origin = "Internal re-hire" if c.origin == "internal" else c.source
        missing = ", ".join(s.missing_core) or "-"
        rows.append(
            f"| {i} | {c.id} | {origin} | {c.years_experience} | {s.score} "
            f"| {len(s.matched_core)}/{len(jd.core_skills) if jd else '?'} | {missing} |"
        )
    return (
        f"Searched **{r.external_pool_size}** external profiles.\n\n"
        + "\n".join(rows)
    )


def _fmt_step4(r) -> str:
    if r.evaluation is None:
        return ""
    ev = r.evals_by_id
    rows = ["| ID | Skills | Depth | Domain | Overall | Finalist |", "|---|---|---|---|---|---|"]
    for s in sorted(r.shortlist, key=lambda s: ev[s.candidate.id].overall, reverse=True):
        e = ev[s.candidate.id]
        finalist = "Yes" if s.candidate.id in r.evaluation.top3_ids else ""
        rows.append(
            f"| {s.candidate.id} | {e.skill_alignment} | {e.experience_depth} | {e.domain_fit} | {e.overall} | {finalist} |"
        )
    return "\n".join(rows) + f"\n\n{r.evaluation.rationale}"


def _fmt_stat_strip(r) -> str:
    """HTML hero stat strip — updates live as steps complete."""
    screened = len(r.internal_checks) + r.external_pool_size if r.internal_checks else "—"
    warm = len([c for c in r.internal_checks if c.status == "match"]) if r.internal_checks else "—"
    shortlisted = len(r.shortlist) if r.shortlist else "—"
    selected = r.final.selected_id if r.final else "—"
    sel_cls = "rp-stat-cell rp-selected" if r.final else "rp-stat-cell"
    return (
        '<div class="rp-stat-strip">'
        f'<div class="rp-stat-cell"><div class="rp-stat-num">{screened}</div>'
        '<div class="rp-stat-label">Profiles Screened</div></div>'
        f'<div class="rp-stat-cell"><div class="rp-stat-num">{warm}</div>'
        '<div class="rp-stat-label">Warm Bench</div></div>'
        f'<div class="rp-stat-cell"><div class="rp-stat-num">{shortlisted}</div>'
        '<div class="rp-stat-label">Shortlisted</div></div>'
        f'<div class="{sel_cls}"><div class="rp-stat-num">{selected}</div>'
        '<div class="rp-stat-label">Selected</div></div>'
        '</div>'
    )


def _fmt_step5(r, show_names: bool = True) -> str:
    if r.final is None:
        return ""
    f = r.final
    pick = r.candidate(f.selected_id).candidate
    pick_label = f"{pick.name} ({pick.id})" if show_names else pick.id
    lines = [
        '<div class="rp-selected-card">',
        "",
        f"### Selected: {pick_label}",
        f"**{f.headline}** | Confidence: **{f.confidence}**",
        "",
        f.why_selected,
        "",
        f"**Requirements covered:** {', '.join(f.skill_overlap)}",
        f"**Experience edge:** {f.experience_edge}",
        "",
        "**Why not the other finalists:**",
    ]
    for x in f.comparison_to_finalists:
        finalist = r.candidate(x.candidate_id).candidate
        flabel = f"{finalist.name} ({x.candidate_id})" if show_names else x.candidate_id
        lines.append(f"- {flabel}: {x.why_not_selected}")
    lines += [
        "",
        f"**Versus the rest of the pool:** {f.comparison_to_pool}",
        "",
        "**Gaps and risks:**",
    ]
    lines += [f"- {g}" for g in f.gaps_and_risks]
    lines += ["", "**Interview focus:**"]
    lines += [f"- {q}" for q in f.interview_focus]
    if r.fallbacks_used:
        lines += ["", f"> Deterministic fallback used for: {', '.join(r.fallbacks_used)}"]
    lines += ["", "</div>"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Gradio callback: runs the pipeline and streams step outputs
# ---------------------------------------------------------------------------

def run_pipeline(
    jd_text: str,
    jd_file,
    provider: str,
    hide_names: bool,
) -> Generator:
    """Generator that yields updated step outputs as the pipeline progresses."""
    import gradio as gr
    from agent.service import RecruitingService

    # Resolve JD text: file upload takes priority
    if jd_file is not None:
        try:
            text = Path(jd_file).read_text(encoding="utf-8")
        except Exception as exc:
            log.warning("Could not read uploaded file: %s", exc)
            text = jd_text
    else:
        text = jd_text

    if not text or len(text.strip()) < 50:
        yield (
            gr.update(value="Please enter or upload a job description (at least 50 characters)."),
            "", "", "", "", "", gr.update(visible=False), gr.update(visible=False), "",
            gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
        )
        return

    # Map UI provider label to service provider arg
    provider_arg = None if provider == "auto" else provider

    svc = RecruitingService()
    s1 = s2 = s3 = s4 = s5 = ""
    stat_html = ""
    result = None

    try:
        for step_num, result in svc.stream(text, provider=provider_arg, hide_names=hide_names):
            if step_num == 1:
                s1 = _fmt_step1(result)
            elif step_num == 2:
                s2 = _fmt_step2(result)
            elif step_num == 3:
                s3 = _fmt_step3(result)
            elif step_num == 4:
                s4 = _fmt_step4(result)
            elif step_num == 5:
                s5 = _fmt_step5(result, show_names=not hide_names)
            stat_html = _fmt_stat_strip(result)
            acc_updates = tuple(gr.update(open=True) if i == step_num else gr.update() for i in range(1, 6))
            yield (
                gr.update(value=f"Running… step {step_num}/5  ·  {result.llm_label}"),
                s1, s2, s3, s4, s5,
                gr.update(visible=False), gr.update(visible=False), stat_html,
                *acc_updates,
            )
    except Exception as exc:
        log.exception("Pipeline error")
        yield (
            gr.update(value="Something went wrong running the funnel. Check the terminal log for details."),
            s1, s2, s3, s4, s5,
            gr.update(visible=False), gr.update(visible=False), stat_html,
            gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
        )
        return

    # Write report to a temp file for download
    if result is not None and result.final is not None:
        from agent.report import build_report
        report_md = build_report(result)
        tmp = tempfile.NamedTemporaryFile(
            suffix=".md", prefix="recruiting_report_", delete=False, mode="w", encoding="utf-8"
        )
        tmp.write(report_md)
        tmp.close()
        fallback_note = (f"  ·  fallbacks: {', '.join(result.fallbacks_used)}"
                         if result.fallbacks_used else "")
        yield (
            gr.update(value=f"Done  ·  {result.llm_label}{fallback_note}"),
            s1, s2, s3, s4, s5,
            gr.update(value=tmp.name, visible=True),
            gr.update(value=report_md, visible=True),
            _fmt_stat_strip(result),
            gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
        )
    else:
        yield (
            gr.update(value="Pipeline completed with no final result."),
            s1, s2, s3, s4, s5,
            gr.update(visible=False), gr.update(visible=False), stat_html,
            gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
        )


def view_run_by_id(run_id: str) -> str:
    """Return the saved report markdown for the given run ID."""
    if not run_id:
        return ""
    try:
        from agent.service import RecruitingService
        svc = RecruitingService()
        record = svc.get_run(run_id)
        if record is None:
            return "_Run not found._"
        return record.report_md
    except Exception as exc:
        log.exception("Could not load run")
        return "_Could not load this run. Check the terminal log for details._"


def load_history() -> str:
    """Return a Markdown table of past runs from storage."""
    try:
        from agent.service import RecruitingService
        svc = RecruitingService()
        runs = svc.list_runs()
        if not runs:
            return "_No runs recorded yet._"
        rows = ["| Run ID | Timestamp | Provider | Job Title | Selected |", "|---|---|---|---|---|"]
        for run in runs:
            rows.append(
                f"| {run.run_id[:8]}… | {run.timestamp[:19]} | {run.provider} "
                f"| {run.job_title} | {run.selected_id} |"
            )
        return "\n".join(rows)
    except Exception as exc:
        log.exception("Could not load history")
        return "_Could not load history. Check the terminal log for details._"


def load_history_choices() -> list:
    """Return (label, run_id) pairs for the past-runs dropdown."""
    try:
        from agent.service import RecruitingService
        svc = RecruitingService()
        runs = svc.list_runs()
        return [(f"{r.timestamp[:16]} · {r.job_title} · {r.selected_id}", r.run_id) for r in runs]
    except Exception as exc:
        log.warning("Could not load history choices: %s", exc)
        return []


def build_app() -> "gr.Blocks":
    import gradio as gr

    with gr.Blocks(title="RecruitPilot") as demo:
        gr.HTML(f"<style>{_CSS}</style>")
        gr.HTML('<div class="rp-header">Recruit&nbsp;&nbsp;Pilot</div>')

        with gr.Tabs():
            # ----------------------------------------------------------------
            # Tab 1: Run
            # ----------------------------------------------------------------
            with gr.Tab("Run"):
                with gr.Row():
                    with gr.Column(scale=1):
                        jd_input = gr.Textbox(
                            label="Job Description",
                            value=_jd_default,
                            placeholder="Paste the job description here…",
                            lines=12,
                        )
                        jd_file = gr.File(
                            label="Or upload a .txt / .md file",
                            file_types=[".txt", ".md"],
                        )
                        provider_dd = gr.Dropdown(
                            choices=["auto", "anthropic", "openai", "mock"],
                            value="auto",
                            label="Provider",
                        )
                        hide_names_toggle = gr.Checkbox(label="Hide candidate names", value=False)
                        run_btn = gr.Button("Run", variant="primary")

                    with gr.Column(scale=2):
                        status_box = gr.Textbox(label="Status", interactive=False, lines=1)
                        stat_strip = gr.HTML(value="")

                        with gr.Accordion("01 · JD Analysis", open=True) as acc1:
                            step1_out = gr.Markdown()
                        with gr.Accordion("02 · Warm Bench", open=False) as acc2:
                            step2_out = gr.Markdown()
                        with gr.Accordion("03 · Top 10 Shortlist", open=False) as acc3:
                            step3_out = gr.Markdown()
                        with gr.Accordion("04 · Evaluation & Top 3", open=False) as acc4:
                            step4_out = gr.Markdown()
                        with gr.Accordion("05 · Selected", open=False) as acc5:
                            step5_out = gr.Markdown()

                        report_download = gr.File(
                            label="Download Report (.md)",
                            visible=False,
                            interactive=False,
                        )
                        report_preview = gr.Markdown(visible=False)

                run_btn.click(
                    fn=run_pipeline,
                    inputs=[jd_input, jd_file, provider_dd, hide_names_toggle],
                    outputs=[
                        status_box,
                        step1_out, step2_out, step3_out, step4_out, step5_out,
                        report_download, report_preview, stat_strip,
                        acc1, acc2, acc3, acc4, acc5,
                    ],
                )

            # ----------------------------------------------------------------
            # Tab 2: History
            # ----------------------------------------------------------------
            with gr.Tab("History"):
                refresh_btn = gr.Button("Refresh")
                history_md = gr.Markdown(value=load_history())
                run_dropdown = gr.Dropdown(
                    choices=load_history_choices(),
                    label="Open a past run",
                    interactive=True,
                    value=None,
                )
                report_view = gr.Markdown(value="")

                def _refresh():
                    return load_history(), gr.update(choices=load_history_choices())

                refresh_btn.click(fn=_refresh, inputs=[], outputs=[history_md, run_dropdown])
                run_dropdown.change(fn=view_run_by_id, inputs=[run_dropdown], outputs=[report_view])

    return demo


def main() -> None:
    ap = argparse.ArgumentParser(description="AI Recruiting Agent web app")
    ap.add_argument("--provider", choices=["auto", "anthropic", "openai", "mock"],
                    help="Override LLM_PROVIDER for all runs")
    ap.add_argument("--port", type=int, default=7860)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.ERROR,
        format="%(levelname)s %(message)s",
    )

    demo = build_app()
    demo.launch(server_name="127.0.0.1", server_port=args.port, share=False)


if __name__ == "__main__":
    main()
