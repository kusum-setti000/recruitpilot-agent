"""Deterministic fallbacks for each LLM step.

These run when LLM_PROVIDER=mock (offline demo and tests) and whenever a live model call fails
validation after retries. They are deliberately simple and transparent, so the pipeline always
produces a defensible answer and the LLM output can be compared against a known baseline.
"""
from __future__ import annotations

import re

from agent.models import (
    CandidateEvaluation, FinalistComparison, FinalSelection, InternalNote, InternalNotes, JDAnalysis,
    ScoredCandidate, ShortlistEvaluation, SkillRequirement,
)
from agent.skills_vocab import find_skills_in_text

_SECTION_PATTERNS = {
    "required": r"^(required|requirements|must have|minimum qualifications|basic qualifications|qualifications)\b",
    "bonus": r"^(preferred|nice to have|bonus|desired|plus|good to have)\b",
    "resp": r"^(responsibilities|what you.?ll do|the role|duties|key responsibilities)\b",
}
DOMAIN_TERMS = ["mortgage", "housing finance", "financial services", "banking", "insurance", "healthcare",
                "regulated", "compliance", "underwriting", "servicing", "retail", "e-commerce", "telecom",
                "pharma", "public sector", "fintech", "capital markets", "logistics", "saas"]
RESP_PHRASES = ["hybrid search", "reranking", "chunking", "embeddings", "tool calling", "human in the loop",
                "audit logging", "pii", "mentor", "evaluation", "golden datasets", "production", "deploy",
                "guardrails", "agentic workflows", "orchestration"]
TITLE_FAMILIES = [
    (("generative ai", "genai", "llm", " ai "), ["Generative AI Engineer", "LLM Engineer", "AI Engineer",
                                                  "Applied AI Engineer", "Machine Learning Engineer"]),
    (("machine learning", "ml engineer", "mlops"), ["Machine Learning Engineer", "MLOps Engineer",
                                                     "ML Platform Engineer", "AI Engineer"]),
    (("data scientist",), ["Data Scientist", "Machine Learning Scientist", "Applied Scientist"]),
    (("data engineer",), ["Data Engineer", "Analytics Engineer", "Big Data Engineer"]),
    (("backend", "python developer"), ["Backend Engineer", "Python Developer", "Software Engineer"]),
]


def _q(term: str) -> str:
    return f'"{term}"' if " " in term else term


def _req_clause(r: SkillRequirement) -> str:
    opts = [r.name, *r.alternatives]
    return _q(opts[0]) if len(opts) == 1 else "(" + " OR ".join(_q(o) for o in opts) + ")"


def _requirements_from_lines(lines: list[str]) -> list[SkillRequirement]:
    reqs: list[SkillRequirement] = []
    seen: set[str] = set()
    for line in lines:
        if re.search(r"\d+\+?\s*(years|yrs)", line, re.I):
            continue  # experience lines are handled separately
        skills = [s for s in find_skills_in_text(line) if s not in seen]
        if not skills:
            continue
        is_group = "(" in line or re.search(r"\bor\b|\bsuch as\b|\bsimilar\b|\bequivalent\b", line, re.I)
        if is_group and len(skills) > 1:
            reqs.append(SkillRequirement(name=skills[0], alternatives=skills[1:]))
        else:
            reqs.extend(SkillRequirement(name=s) for s in skills)
        seen.update(skills)
    return reqs


def analyze_jd(jd_text: str) -> JDAnalysis:
    lines = [ln.strip(" -•*\t") for ln in jd_text.splitlines()]
    sections: dict[str, list[str]] = {"required": [], "bonus": [], "resp": [], "other": []}
    current = "other"
    title, location = "", ""
    for ln in lines:
        if not ln:
            continue
        low = ln.lower()
        if low.startswith("job title:"):
            title = ln.split(":", 1)[1].strip()
            continue
        if low.startswith("location:"):
            location = ln.split(":", 1)[1].strip()
            continue
        matched = next((k for k, p in _SECTION_PATTERNS.items() if re.match(p, low) and len(ln) < 60), None)
        if matched:
            current = matched
            continue
        sections[current].append(ln)
    if not title:
        title = next((ln for ln in lines if ln), "Unknown role")

    core = _requirements_from_lines(sections["required"])
    core_names = {r.name for r in core} | {a for r in core for a in r.alternatives}
    bonus = [r for r in _requirements_from_lines(sections["bonus"]) if r.name not in core_names]
    if not core:  # unstructured JD: treat every skill mentioned as core
        core = _requirements_from_lines([jd_text])

    years_src = " ".join(sections["required"]) or jd_text
    m = re.search(r"(\d+)\s*\+?\s*(?:years|yrs)", years_src, re.I)
    min_years = int(m.group(1)) if m else 0

    tl = title.lower()
    if any(w in tl for w in ("staff", "principal")):
        seniority = "Staff/Principal"
    elif any(w in tl for w in ("lead", "manager", "head of")):
        seniority = "Lead/Manager"
    elif "senior" in tl or "sr" in tl.split() or min_years >= 7:
        seniority = "Senior"
    elif "junior" in tl or min_years <= 2:
        seniority = "Junior"
    else:
        seniority = "Mid"

    low_text = jd_text.lower()
    domain = [d for d in DOMAIN_TERMS if d in low_text]
    resp_text = " ".join(sections["resp"]).lower()
    resp_kw = [p for p in RESP_PHRASES if p in resp_text]

    padded = f" {tl} "
    variants = next((v for keys, v in TITLE_FAMILIES if any(k in padded for k in keys)), [])
    base = re.sub(r"\b(senior|sr\.?|staff|principal|lead|junior)\b", "", title, flags=re.I).strip()
    variants = list(dict.fromkeys([base, *variants]))[:6]

    strict = " AND ".join(_req_clause(r) for r in core)
    broad = " AND ".join(_req_clause(r) for r in core[:4])
    titles = "(" + " OR ".join(_q(v) for v in variants[:4]) + ")"
    anchor = _req_clause(core[0]) if core else ""
    queries = [q for q in [strict, broad, f"{titles} AND {anchor}" if anchor else titles] if q]

    return JDAnalysis(
        job_title=title, seniority=seniority, min_years_experience=min_years, core_skills=core,
        bonus_skills=bonus, domain_keywords=domain, responsibilities_keywords=resp_kw,
        boolean_queries=list(dict.fromkeys(queries)), title_variants=variants, work_arrangement=location,
    )


# ---------------- internal notes ----------------

def internal_notes(matches: list[ScoredCandidate], jd: JDAnalysis) -> InternalNotes:
    notes = []
    for s in matches:
        c = s.candidate
        gap = f" Gap: {', '.join(s.missing_core)}." if s.missing_core else " Covers every must-have."
        notes.append(InternalNote(
            candidate_id=c.id,
            fit_note=(f"Past {c.title} with {c.years_experience} yrs, covers {len(s.matched_core)}/"
                      f"{len(jd.core_skills)} must-haves ({', '.join(s.matched_core[:5])}). Rated "
                      f"{c.performance_rating}/5 on the last contract ({c.last_project.rstrip('.')})."
                      f"{gap} Status: {c.availability_status}."),
        ))
    return InternalNotes(notes=notes)


# ---------------- shortlist evaluation ----------------

_US_HINT = re.compile(r",\s*(?!ON|BC|QC|AB)[A-Z]{2}$|\(US\)|\bDC\b")


def location_concern(location: str, jd: JDAnalysis) -> str | None:
    arr = jd.work_arrangement.lower()
    if ("us" in arr.split() or "united states" in arr or "within the us" in arr) and location:
        if not _US_HINT.search(location):
            return f"Based in {location}; JD requires US based work"
    return None


def evaluate(s: ScoredCandidate, jd: JDAnalysis) -> CandidateEvaluation:
    c = s.candidate
    core_ratio = len(s.matched_core) / max(1, len(jd.core_skills))
    bonus_ratio = len(s.matched_bonus) / max(1, len(jd.bonus_skills))
    skill = max(1, min(10, round(8 * core_ratio + 2 * bonus_ratio)))
    mn = max(1, jd.min_years_experience)
    exp = (min(10, round(6 + (c.years_experience - mn) * 0.6)) if c.years_experience >= mn
           else max(1, round(6 * c.years_experience / mn)))
    text = c.search_text().lower()
    domain_hits = [d for d in jd.domain_keywords if d in text]
    domain = min(10, 4 + 3 * bool(domain_hits) + min(2, len(domain_hits) - 1 if domain_hits else 0)
                 + (1 if c.origin == "internal" else 0))
    overall = round(0.7 * s.score + skill + exp + domain)

    strengths = [f"Covers must-haves: {', '.join(s.matched_core)}"] if s.matched_core else []
    if s.matched_bonus:
        strengths.append(f"Bonus skills: {', '.join(s.matched_bonus)}")
    strengths.append(f"{c.years_experience} yrs experience vs {jd.min_years_experience}+ required")
    if domain_hits:
        strengths.append(f"Domain overlap: {', '.join(domain_hits)}")
    if c.origin == "internal":
        strengths.append(f"Proven with us: rated {c.performance_rating}/5, faster onboarding")

    concerns = []
    if s.missing_core:
        concerns.append(f"Missing must-haves: {', '.join(s.missing_core)}")
    if c.years_experience < jd.min_years_experience:
        concerns.append(f"Below the {jd.min_years_experience} year minimum")
    if c.open_to_work is False:
        concerns.append("Not marked open to work; may be harder to engage")
    if (loc := location_concern(c.location, jd)):
        concerns.append(loc)
        overall -= 10
    if c.availability_status and c.availability_status.lower().startswith("available from"):
        concerns.append(c.availability_status)
    return CandidateEvaluation(candidate_id=c.id, skill_alignment=skill, experience_depth=exp,
                               domain_fit=domain, overall=max(1, min(100, overall)),
                               strengths=strengths, concerns=concerns or ["No major gaps on paper"])


def shortlist_evaluation(shortlist: list[ScoredCandidate], jd: JDAnalysis) -> ShortlistEvaluation:
    evals = [evaluate(s, jd) for s in shortlist]
    ranked = sorted(evals, key=lambda e: e.overall, reverse=True)
    top3 = [e.candidate_id for e in ranked[:3]]
    cut = ranked[3] if len(ranked) > 3 else None
    rationale = (f"Finalists ranked by holistic score (screening score blended with skill, experience and domain "
                 f"ratings). {', '.join(top3)} lead on must-have coverage and depth"
                 + (f"; the next best ({cut.candidate_id}, {cut.overall}) "
                    f"{'ties' if cut.overall == ranked[2].overall else 'trails'} the third finalist "
                    f"({ranked[2].overall}) and loses on the tiebreak order." if cut else "."))
    return ShortlistEvaluation(evaluations=evals, top3_ids=top3, rationale=rationale)


# ---------------- final selection ----------------

def final_selection(finalists: list[ScoredCandidate], evals: dict[str, CandidateEvaluation],
                    jd: JDAnalysis, rest: list[ScoredCandidate], pool_size: int,
                    tie_margin: int = 3) -> FinalSelection:
    ordered = sorted(finalists, key=lambda s: evals[s.candidate.id].overall, reverse=True)
    pick = ordered[0]
    # Recruiter policy: a proven warm-bench re-hire wins a near tie — but only when
    # the internal candidate covers at least as many must-haves as the current pick.
    for s in ordered[1:]:
        if (s.candidate.origin == "internal" and pick.candidate.origin != "internal"
                and evals[pick.candidate.id].overall - evals[s.candidate.id].overall <= tie_margin
                and len(s.missing_core) <= len(pick.missing_core)):
            pick = s
            break
    pc, pe = pick.candidate, evals[pick.candidate.id]
    others = [s for s in ordered if s.candidate.id != pc.id]

    comparisons = []
    for s in others:
        e = evals[s.candidate.id]
        reasons = []
        if len(s.missing_core) > len(pick.missing_core):
            reasons.append(f"misses {', '.join(s.missing_core)}")
        if s.candidate.years_experience < pc.years_experience:
            reasons.append(f"{s.candidate.years_experience} vs {pc.years_experience} yrs")
        if e.domain_fit < pe.domain_fit:
            reasons.append("weaker domain fit")
        if len(s.matched_bonus) < len(pick.matched_bonus):
            reasons.append(f"fewer bonus skills ({len(s.matched_bonus)} vs {len(pick.matched_bonus)})")
        loc = location_concern(s.candidate.location, jd)
        if loc:
            reasons.append(loc[0].lower() + loc[1:])
        if not reasons:
            reasons.append("very close overall; lost on the combined score" +
                           (" and the warm-bench tiebreak" if pc.origin == "internal" else ""))
        comparisons.append(FinalistComparison(
            candidate_id=s.candidate.id,
            why_not_selected=f"Strong option (overall {e.overall} vs {pe.overall}) but {'; '.join(reasons)}."))

    gap_vs_next = pe.overall - evals[others[0].candidate.id].overall if others else 99
    confidence = "High" if gap_vs_next >= 8 else "Low" if gap_vs_next < 0 else "Medium"
    if pick.missing_core:
        confidence = "Medium" if confidence == "High" else "Low"

    origin_txt = (f"an internal re-hire rated {pc.performance_rating}/5 on a previous contract, which removes "
                  f"most of the usual hiring risk and shortens onboarding"
                  if pc.origin == "internal" else f"sourced from {pc.source}")
    why = (f"{pc.id} is the strongest match for the {jd.job_title} role. They cover "
           f"{len(pick.matched_core)} of {len(jd.core_skills)} must-have requirements "
           f"({', '.join(pick.matched_core)}) and {len(pick.matched_bonus)} of {len(jd.bonus_skills)} preferred "
           f"skills, with {pc.years_experience} years of experience against a {jd.min_years_experience}+ year bar. "
           f"Their background ({pc.summary.rstrip('.')}) maps directly onto the JD's focus areas. They are "
           f"{origin_txt}. Screening score {pick.score}/100 and holistic score {pe.overall}/100, the best balance "
           f"of skills, depth and domain fit among the finalists.")
    risks = [f"Not evidenced on profile: {', '.join(pick.missing_core)}"] if pick.missing_core else []
    unmatched_bonus = [r.name for r in jd.bonus_skills if r.name not in pick.matched_bonus]
    if unmatched_bonus:
        risks.append(f"Preferred skills not shown: {', '.join(unmatched_bonus)}")
    risks += [c for c in pe.concerns if c != "No major gaps on paper"]
    risks.append("All evidence is self-reported profile data; verify depth in technical interviews")

    focus = [f"Walk through a production {jd.core_skills[0].name if jd.core_skills else 'project'} "
             f"system they owned end to end: design choices, scale, failure modes"]
    focus += [f"Probe hands-on depth in {r}" for r in pick.missing_core[:2]]
    focus += ["Ask how they evaluated quality and handled regressions before release",
              "Confirm availability, rate expectations and work arrangement fit"]

    return FinalSelection(
        selected_id=pc.id,
        headline=f"{pc.title}, {pc.years_experience} yrs, {len(pick.matched_core)}/{len(jd.core_skills)} "
                 f"must-haves, {'warm-bench re-hire' if pc.origin == 'internal' else pc.source}",
        why_selected=why,
        skill_overlap=pick.matched_core + pick.matched_bonus,
        experience_edge=(f"{pc.years_experience} years vs {jd.min_years_experience}+ required; "
                         f"experience depth rated {pe.experience_depth}/10"),
        comparison_to_finalists=comparisons,
        comparison_to_pool=(f"Out of {pool_size} profiles screened, {len(rest)} other shortlisted candidates scored "
                            f"lower on must-have coverage or depth; the best of them reached a screening score of "
                            f"{rest[0].score if rest else 'n/a'} vs {pick.score}."),
        gaps_and_risks=risks,
        interview_focus=focus,
        confidence=confidence,
    )
