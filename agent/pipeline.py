"""The five-step recruiting funnel.

  Step 1  JD analysis and keyword extraction           (LLM, structured output)
  Step 2  Internal warm-bench check (past hires first) (policy rules + matcher + LLM fit notes)
  Step 3  External pool search, combine, Top 10        (Boolean search + hybrid score)
  Step 4  Deep evaluation, Top 3                       (LLM)
  Step 5  Final pick and justification                 (LLM)

Each step's output is a typed object stored on PipelineResult, and an optional `observer` is told
when each step finishes, which is how the terminal view prints the funnel live.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterator, Optional, Protocol

from agent import heuristics, prompts
from agent.config import Settings
from agent.llm import LLMClient
from agent.matching import boolean_hit_counts, score_candidates
from agent.models import (
    Candidate, CandidateEvaluation, FinalSelection, InternalNotes, JDAnalysis, ScoredCandidate,
    ShortlistEvaluation,
)
from agent.sources import external_sources, internal_source


class Observer(Protocol):
    def step(self, number: int, result: "PipelineResult") -> None: ...


@dataclass
class InternalCheck:
    candidate: Candidate
    status: str  # "match", "eligible_not_fit", "excluded"
    reason: str
    scored: Optional[ScoredCandidate] = None
    note: str = ""


@dataclass
class PipelineResult:
    jd_text: str
    llm_label: str
    jd: Optional[JDAnalysis] = None
    internal_checks: list[InternalCheck] = field(default_factory=list)
    external_pool_size: int = 0
    query_hits: list[tuple[str, int]] = field(default_factory=list)
    shortlist: list[ScoredCandidate] = field(default_factory=list)
    evaluation: Optional[ShortlistEvaluation] = None
    finalists: list[ScoredCandidate] = field(default_factory=list)
    final: Optional[FinalSelection] = None
    fallbacks_used: list[str] = field(default_factory=list)
    llm_disabled_reason: Optional[str] = None

    @property
    def internal_matches(self) -> list[InternalCheck]:
        return [c for c in self.internal_checks if c.status == "match"]

    @property
    def evals_by_id(self) -> dict[str, CandidateEvaluation]:
        return {e.candidate_id: e for e in (self.evaluation.evaluations if self.evaluation else [])}

    def candidate(self, cid: str) -> ScoredCandidate:
        return next(s for s in self.shortlist if s.candidate.id == cid)


def _dump(obj) -> str:
    return json.dumps(obj, indent=2, default=str)


class RecruitingPipeline:
    def __init__(self, settings: Settings, llm: Optional[LLMClient] = None, observer: Optional[Observer] = None):
        self.s = settings
        self.llm = llm or LLMClient(settings)
        self.observer = observer

    def _notify(self, n: int, r: PipelineResult) -> None:
        if self.observer:
            self.observer.step(n, r)

    # ---------------- Step 1 ----------------
    def analyze_jd(self, jd_text: str) -> JDAnalysis:
        def validate(jd: JDAnalysis) -> None:
            if not jd.core_skills:
                raise ValueError("core_skills is empty")

        jd = self.llm.structured(
            step="jd_analysis", schema=JDAnalysis, system=prompts.JD_ANALYSIS_SYSTEM,
            user=f"Job description:\n<<<\n{jd_text}\n>>>",
            fallback=lambda: heuristics.analyze_jd(jd_text), validator=validate, max_tokens=2500,
        )
        return jd

    # ---------------- Step 2 ----------------
    def _eligibility(self, c: Candidate) -> tuple[bool, str]:
        today = self.s.today
        if c.past_contract_end_date and c.past_contract_end_date >= today:
            return False, f"Contract still active until {c.past_contract_end_date}"
        if c.rehire_eligible is False:
            return False, "Not eligible for re-hire"
        if c.performance_rating is not None and c.performance_rating < self.s.min_internal_rating:
            return False, f"Past rating {c.performance_rating}/5 below {self.s.min_internal_rating} threshold"
        status = (c.availability_status or "").lower()
        if "not available" in status or "active contract" in status:
            return False, c.availability_status or "Unavailable"
        m = re.search(r"(\d{4}-\d{2}-\d{2})", status)
        if m and date.fromisoformat(m.group(1)) > today + timedelta(days=self.s.available_soon_days):
            return False, f"Not available until {m.group(1)}"
        return True, "Eligible for re-hire"

    def internal_check(self, jd: JDAnalysis) -> list[InternalCheck]:
        people = internal_source(self.s).load()
        scored = {s.candidate.id: s for s in score_candidates(people, jd)}
        checks: list[InternalCheck] = []
        for c in people:
            sc = scored[c.id]
            ok, reason = self._eligibility(c)
            coverage = len(sc.matched_core) / max(1, len(jd.core_skills))
            fits = coverage >= 0.7 and c.years_experience >= jd.min_years_experience - 2
            if not ok:
                checks.append(InternalCheck(c, "excluded", reason, sc))
            elif fits:
                checks.append(InternalCheck(c, "match", f"Covers {len(sc.matched_core)}/{len(jd.core_skills)} must-haves", sc))
            else:
                checks.append(InternalCheck(c, "eligible_not_fit",
                                            f"Eligible but covers only {len(sc.matched_core)}/{len(jd.core_skills)} must-haves", sc))

        matches = [c for c in checks if c.status == "match"]
        if matches:
            ids = {m.candidate.id for m in matches}

            def validate(n: InternalNotes) -> None:
                bad = {x.candidate_id for x in n.notes} - ids
                if bad:
                    raise ValueError(f"Unknown candidate_id(s) {bad}; allowed: {sorted(ids)}")

            payload = [{**m.candidate.llm_view(self.s.send_names_to_llm),
                        "matched_must_haves": m.scored.matched_core, "missing_must_haves": m.scored.missing_core}
                       for m in matches]
            notes = self.llm.structured(
                step="internal_notes", schema=InternalNotes, system=prompts.INTERNAL_NOTES_SYSTEM,
                user=f"JD brief:\n{jd.model_dump_json(indent=2)}\n\nPast hires:\n{_dump(payload)}",
                fallback=lambda: heuristics.internal_notes([m.scored for m in matches], jd), validator=validate,
            )
            by_id = {n.candidate_id: n.fit_note for n in notes.notes}
            fallback_notes = {n.candidate_id: n.fit_note
                              for n in heuristics.internal_notes([m.scored for m in matches], jd).notes}
            for m in matches:
                m.note = by_id.get(m.candidate.id) or fallback_notes[m.candidate.id]
        return checks

    # ---------------- Step 3 ----------------
    def build_shortlist(self, jd: JDAnalysis, checks: list[InternalCheck]) -> tuple[list[ScoredCandidate], int, list]:
        pool: list[Candidate] = []
        for src in external_sources(self.s):
            pool.extend(src.load())
        query_hits = boolean_hit_counts(pool, jd)
        external_scored = score_candidates(pool, jd)
        internal_scored = [c.scored for c in checks if c.status == "match"]

        k = self.s.shortlist_size
        if self.s.warm_bench_guaranteed:
            reserved = sorted(internal_scored, key=lambda s: s.score, reverse=True)[:k]
            shortlist = reserved + external_scored[: k - len(reserved)]
        else:
            shortlist = sorted(internal_scored + external_scored, key=lambda s: s.score, reverse=True)[:k]
        shortlist.sort(key=lambda s: s.score, reverse=True)
        return shortlist, len(pool), query_hits

    # ---------------- Step 4 ----------------
    def evaluate_shortlist(self, jd: JDAnalysis, shortlist: list[ScoredCandidate]) -> ShortlistEvaluation:
        ids = [s.candidate.id for s in shortlist]

        def validate(ev: ShortlistEvaluation) -> None:
            got = [e.candidate_id for e in ev.evaluations]
            if set(got) != set(ids):
                raise ValueError(f"evaluations must cover exactly these IDs once each: {ids}; got {got}")
            if len(set(ev.top3_ids)) != 3 or not set(ev.top3_ids) <= set(ids):
                raise ValueError(f"top3_ids must be 3 distinct IDs from {ids}; got {ev.top3_ids}")

        payload = [{**s.candidate.llm_view(self.s.send_names_to_llm),
                    "screening_score": s.score, "matched_must_haves": s.matched_core,
                    "missing_must_haves": s.missing_core, "matched_bonus": s.matched_bonus} for s in shortlist]
        n = min(3, len(shortlist))
        if n < 3:
            return heuristics.shortlist_evaluation(shortlist, jd)
        return self.llm.structured(
            step="shortlist_evaluation", schema=ShortlistEvaluation, system=prompts.SHORTLIST_SYSTEM,
            user=f"JD:\n<<<\n{self._jd_text}\n>>>\n\nJD brief:\n{jd.model_dump_json(indent=2)}\n\n"
                 f"Shortlist ({len(shortlist)} candidates):\n{_dump(payload)}",
            fallback=lambda: heuristics.shortlist_evaluation(shortlist, jd), validator=validate, max_tokens=6000,
        )

    # ---------------- Step 5 ----------------
    def select_final(self, jd: JDAnalysis, finalists: list[ScoredCandidate], evals: dict[str, CandidateEvaluation],
                     rest: list[ScoredCandidate], pool_size: int) -> FinalSelection:
        ids = [f.candidate.id for f in finalists]

        def validate(fs: FinalSelection) -> None:
            if fs.selected_id not in ids:
                raise ValueError(f"selected_id must be one of {ids}")
            others = set(ids) - {fs.selected_id}
            if {c.candidate_id for c in fs.comparison_to_finalists} != others:
                raise ValueError(f"comparison_to_finalists must cover exactly {sorted(others)}")

        payload = [{**f.candidate.llm_view(self.s.send_names_to_llm), "screening_score": f.score,
                    "evaluation": evals[f.candidate.id].model_dump()} for f in finalists]
        rest_brief = [{"candidate_id": s.candidate.id, "title": s.candidate.title, "years": s.candidate.years_experience,
                       "screening_score": s.score, "missing_must_haves": s.missing_core} for s in rest]
        return self.llm.structured(
            step="final_selection", schema=FinalSelection, system=prompts.FINAL_SYSTEM,
            user=f"JD:\n<<<\n{self._jd_text}\n>>>\n\nFinalists:\n{_dump(payload)}\n\n"
                 f"Rest of the shortlist:\n{_dump(rest_brief)}\n\nTotal profiles screened: {pool_size}",
            fallback=lambda: heuristics.final_selection(finalists, evals, jd, rest, pool_size),
            validator=validate, max_tokens=4000,
        )

    # ---------------- iter_steps ----------------
    def iter_steps(self, jd_text: str) -> Iterator[tuple[int, PipelineResult]]:
        self._jd_text = jd_text
        r = PipelineResult(jd_text=jd_text, llm_label=self.llm.label)

        r.jd = self.analyze_jd(jd_text)
        self._notify(1, r)
        yield 1, r

        r.internal_checks = self.internal_check(r.jd)
        self._notify(2, r)
        yield 2, r

        r.shortlist, r.external_pool_size, r.query_hits = self.build_shortlist(r.jd, r.internal_checks)
        self._notify(3, r)
        if not r.shortlist:
            raise RuntimeError("No candidates found in any source")
        yield 3, r

        r.evaluation = self.evaluate_shortlist(r.jd, r.shortlist)
        evals = r.evals_by_id
        r.finalists = [r.candidate(cid) for cid in r.evaluation.top3_ids]
        self._notify(4, r)
        yield 4, r

        rest = [s for s in r.shortlist if s.candidate.id not in set(r.evaluation.top3_ids)]
        total = r.external_pool_size + len(r.internal_checks)
        r.final = self.select_final(r.jd, r.finalists, evals, rest, total)
        r.fallbacks_used = [h.step for h in self.llm.history if h.used_fallback]
        r.llm_disabled_reason = self.llm.disabled_reason
        self._notify(5, r)
        yield 5, r

    # ---------------- run ----------------
    def run(self, jd_text: str) -> PipelineResult:
        r = None
        for _, r in self.iter_steps(jd_text):
            pass
        return r
