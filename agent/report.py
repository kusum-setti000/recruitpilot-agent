"""Markdown report writer."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from agent.pipeline import PipelineResult


def _reqs(reqs) -> str:
    return ", ".join(r.name + (f" ({' / '.join(r.alternatives)})" if r.alternatives else "") for r in reqs) or "none"


def _cell(text: str) -> str:
    return str(text).replace("|", "/").replace("\n", " ")


def build_report(r: PipelineResult) -> str:
    jd, f = r.jd, r.final
    pick = r.candidate(f.selected_id).candidate
    ev = r.evals_by_id
    L: list[str] = []
    add = L.append

    add(f"# Recruiting Report: {jd.job_title}\n")
    add(f"Generated {datetime.now():%Y-%m-%d %H:%M} with `{r.llm_label}`. "
        f"Screened {len(r.internal_checks)} past hires and {r.external_pool_size} external profiles.\n")
    if r.fallbacks_used:
        add(f"> Deterministic fallback used for: {', '.join(r.fallbacks_used)}\n")

    add(f"## Recommendation\n")
    add(f"**{pick.name} ({pick.id})**, {f.headline}. Confidence: **{f.confidence}**.\n")
    add(f"{f.why_selected}\n")

    add("## Funnel\n")
    add("| Stage | Count |\n|---|---|")
    add(f"| Profiles screened | {len(r.internal_checks) + r.external_pool_size} |")
    add(f"| Internal re-hire matches | {len(r.internal_matches)} |")
    add(f"| Shortlist | {len(r.shortlist)} |\n| Finalists | {len(r.finalists)} |\n| Selected | 1 |\n")

    add("## Step 1: JD analysis\n")
    add(f"Seniority **{jd.seniority}**, minimum **{jd.min_years_experience}** years. "
        f"Work arrangement: {jd.work_arrangement or 'not stated'}.\n")
    add(f"Must-have: {_reqs(jd.core_skills)}\n")
    add(f"Bonus: {_reqs(jd.bonus_skills)}\n")
    add(f"Domain: {', '.join(jd.domain_keywords) or 'none stated'}\n")
    add(f"Title variants: {', '.join(jd.title_variants)}\n")
    add("Boolean queries and hits in the external pool:\n")
    for i, (q, hits) in enumerate(r.query_hits, 1):
        add(f"{i}. `{q}` ({hits} hits)")
    add("")

    add("## Step 2: Internal warm-bench check\n")
    add("| ID | Name | Role | Rating | Contract end | Status | Reason / note |\n|---|---|---|---|---|---|---|")
    order = {"match": 0, "excluded": 1, "eligible_not_fit": 2}
    for c in sorted(r.internal_checks, key=lambda x: (order[x.status], -(x.scored.score if x.scored else 0))):
        k = c.candidate
        label = {"match": "Re-hire match", "excluded": "Excluded", "eligible_not_fit": "Not a fit"}[c.status]
        add(f"| {k.id} | {k.name} | {k.title} | {k.performance_rating} | {k.past_contract_end_date} | {label} | "
            f"{_cell(c.note or c.reason)} |")
    add("")

    add("## Step 3: Top 10 shortlist\n")
    add("| # | ID | Name | Origin | Title | Yrs | Score | Must-haves | Missing |\n|---|---|---|---|---|---|---|---|---|")
    for i, s in enumerate(r.shortlist, 1):
        c = s.candidate
        add(f"| {i} | {c.id} | {c.name} | {'Internal re-hire' if c.origin == 'internal' else c.source} | {c.title} | "
            f"{c.years_experience} | {s.score} | {len(s.matched_core)}/{len(jd.core_skills)} | "
            f"{', '.join(s.missing_core) or '-'} |")
    add("\nScore = core skills (45) + bonus skills (10) + experience (15) + BM25 relevance (15) + "
        "Boolean query hits (10) + title alignment (5) + warm-bench bonus (up to 5), capped at 100.\n")

    add("## Step 4: Evaluation and Top 3\n")
    add("| ID | Skills | Depth | Domain | Overall | Strengths | Concerns |\n|---|---|---|---|---|---|---|")
    for s in sorted(r.shortlist, key=lambda s: ev[s.candidate.id].overall, reverse=True):
        e = ev[s.candidate.id]
        mark = " (finalist)" if s.candidate.id in r.evaluation.top3_ids else ""
        add(f"| {s.candidate.id}{mark} | {e.skill_alignment} | {e.experience_depth} | {e.domain_fit} | {e.overall} | "
            f"{_cell('; '.join(e.strengths))} | {_cell('; '.join(e.concerns))} |")
    add(f"\n{r.evaluation.rationale}\n")

    add("## Step 5: Final selection and justification\n")
    add(f"### {pick.name} ({pick.id})\n")
    add(f"{f.why_selected}\n")
    add(f"**Requirements covered:** {', '.join(f.skill_overlap)}\n")
    add(f"**Experience edge:** {f.experience_edge}\n")
    add("**Why not the other finalists**\n")
    for x in f.comparison_to_finalists:
        add(f"- {r.candidate(x.candidate_id).candidate.name} ({x.candidate_id}): {x.why_not_selected}")
    add(f"\n**Versus the rest of the pool:** {f.comparison_to_pool}\n")
    add("**Gaps and risks**\n")
    add("\n".join(f"- {g}" for g in f.gaps_and_risks) + "\n")
    add("**Interview focus**\n")
    add("\n".join(f"- {q}" for q in f.interview_focus) + "\n")

    from agent.config import get_settings
    _s = get_settings()
    names_note = ("Candidate names were withheld from the LLM during evaluation; only job-relevant fields were shared."
                  if not _s.send_names_to_llm
                  else "Candidate names were shared with the LLM (SEND_NAMES_TO_LLM=true).")
    add(f"---\n*{names_note} All profiles in this demo are synthetic.*")
    return "\n".join(L)


def write_report(r: PipelineResult, path: Path) -> Path:
    path.write_text(build_report(r))
    return path
