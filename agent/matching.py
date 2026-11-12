"""Deterministic matching: requirement checks, BM25 relevance, Boolean search, and the hybrid score.

This layer does the recall work over the whole pool cheaply and explainably, so the LLM only has to
reason about a short list. Every point in a score can be traced to a component in ScoreBreakdown.

Score components (max 100, plus a small warm-bench bonus, capped at 100):
  core_skills      45  share of must-have requirements satisfied
  bonus_skills     10  share of nice-to-have requirements satisfied
  experience       15  full marks at or above the JD minimum, scaled down below it
  text_relevance   15  BM25 of JD keywords against title, skills and summary (normalised to the pool)
  boolean_hits     10  share of the JD's Boolean queries this profile satisfies
  title_alignment   5  title matches a JD title variant / seniority
  warm_bench_bonus 0-5 internal re-hires with a strong past rating
"""
from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache

from agent.models import Candidate, JDAnalysis, ScoreBreakdown, ScoredCandidate, SkillRequirement
from agent.skills_vocab import aliases_for, canonical, find_skills_in_text, skill_closure

WEIGHTS = {"core": 45.0, "bonus": 10.0, "experience": 15.0, "text": 15.0, "boolean": 10.0, "title": 5.0}

_TOKEN = re.compile(r"[a-z0-9+#./-]+")
_STOP = {"and", "or", "the", "a", "an", "of", "with", "in", "for", "to", "on", "at", "years", "experience"}


def tokenize(text: str) -> list[str]:
    return [t.strip(".-/") for t in _TOKEN.findall(text.lower()) if t.strip(".-/") and t not in _STOP]


# ---------------- requirement checks ----------------

@lru_cache(maxsize=2048)
def _option_keys(option: str) -> frozenset[str]:
    """Canonical keys for a requirement option. Free text like "Strong Python" still maps to Python."""
    return frozenset({canonical(option).lower(), *(s.lower() for s in find_skills_in_text(option))})


def satisfies(req: SkillRequirement, closure: set[str]) -> bool:
    return any(_option_keys(o) & closure for o in [req.name, *req.alternatives])


def requirement_coverage(reqs: list[SkillRequirement], cand: Candidate) -> tuple[list[str], list[str]]:
    closure = skill_closure(cand.skills)
    matched = [r.name for r in reqs if satisfies(r, closure)]
    missing = [r.name for r in reqs if r.name not in matched]
    return matched, missing


# ---------------- BM25 ----------------

class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.4, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.avgdl = sum(map(len, docs)) / max(1, len(docs))
        df: Counter[str] = Counter()
        for d in docs:
            df.update(set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tfs = [Counter(d) for d in docs]

    def score(self, query: list[str], i: int) -> float:
        tf, dl, s = self.tfs[i], len(self.docs[i]), 0.0
        for q in query:
            if q in tf:
                f = tf[q]
                s += self.idf.get(q, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return s


# ---------------- Boolean search ----------------

class BooleanQuery:
    """Small Boolean parser: AND, OR, NOT, parentheses, "quoted phrases", bare terms.

    Adjacent terms with no operator are treated as AND. A term matches when the candidate has the
    skill (via aliases and implications) or the phrase appears in their profile text.
    """

    _tok = re.compile(r'\(|\)|"[^"]+"|[^\s()]+')

    def __init__(self, query: str):
        self.query = query
        self.tokens = self._tok.findall(query)
        self.pos = 0
        self.tree = self._parse_or() if self.tokens else ("TRUE",)

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _next(self):
        tok = self._peek()
        self.pos += 1
        return tok

    def _parse_or(self):
        node = self._parse_and()
        while (self._peek() or "").upper() == "OR":
            self._next()
            node = ("OR", node, self._parse_and())
        return node

    def _parse_and(self):
        node = self._parse_not()
        while self._peek() is not None and self._peek() != ")" and self._peek().upper() != "OR":
            if self._peek().upper() == "AND":
                self._next()
            node = ("AND", node, self._parse_not())
        return node

    def _parse_not(self):
        if (self._peek() or "").upper() == "NOT":
            self._next()
            return ("NOT", self._parse_not())
        return self._parse_atom()

    def _parse_atom(self):
        tok = self._next()
        if tok is None:
            return ("TRUE",)
        if tok == "(":
            node = self._parse_or()
            if self._peek() == ")":
                self._next()
            return node
        return ("TERM", tok.strip('"'))

    def matches(self, cand: Candidate) -> bool:
        closure = skill_closure(cand.skills)
        text = " " + " ".join(tokenize(cand.search_text())) + " "
        return self._eval(self.tree, closure, text)

    def _eval(self, node, closure, text) -> bool:
        op = node[0]
        if op == "TRUE":
            return True
        if op == "TERM":
            term = node[1]
            if canonical(term).lower() in closure:
                return True
            return any(f" {' '.join(tokenize(a))} " in text for a in aliases_for(term) if tokenize(a))
        if op == "NOT":
            return not self._eval(node[1], closure, text)
        left = self._eval(node[1], closure, text)
        if op == "AND":
            return left and self._eval(node[2], closure, text)
        return left or self._eval(node[2], closure, text)


# ---------------- hybrid scoring ----------------

def _query_terms(jd: JDAnalysis) -> list[str]:
    terms: list[str] = []
    for r in jd.core_skills + jd.core_skills + jd.bonus_skills:  # core counted twice on purpose
        for opt in [r.name, *r.alternatives]:
            terms += tokenize(opt)
    for kw in jd.domain_keywords + jd.responsibilities_keywords + jd.title_variants:
        terms += tokenize(kw)
    return terms


def _experience_points(years: int, min_years: int) -> float:
    if min_years <= 0 or years >= min_years:
        return WEIGHTS["experience"]
    return WEIGHTS["experience"] * max(0.0, years / min_years) ** 1.5


def _title_points(cand: Candidate, jd: JDAnalysis) -> float:
    title = cand.title.lower()
    variants = [jd.job_title, *jd.title_variants]
    core_words = {w for v in variants for w in tokenize(v)} - {"senior", "staff", "lead", "principal", "junior"}
    overlap = len(core_words & set(tokenize(title))) / max(1, len(core_words))
    seniority_word = jd.seniority.split("/")[0].lower()
    senior_bonus = 1.0 if seniority_word in title or jd.seniority in ("Junior", "Mid") else 0.0
    return WEIGHTS["title"] * min(1.0, 0.7 * min(1.0, overlap * 2) + 0.3 * senior_bonus)


def score_candidates(cands: list[Candidate], jd: JDAnalysis, warm_bench_bonus: bool = True) -> list[ScoredCandidate]:
    if not cands:
        return []
    docs = [tokenize(c.search_text()) for c in cands]
    bm25 = BM25(docs)
    q = _query_terms(jd)
    raw = [bm25.score(q, i) for i in range(len(cands))]
    top_raw = max(raw) or 1.0
    queries = [BooleanQuery(s) for s in jd.boolean_queries]

    scored: list[ScoredCandidate] = []
    for c, r in zip(cands, raw):
        m_core, miss_core = requirement_coverage(jd.core_skills, c)
        m_bonus, _ = requirement_coverage(jd.bonus_skills, c)
        hits = [i for i, bq in enumerate(queries) if bq.matches(c)]
        bonus = 0.0
        if warm_bench_bonus and c.origin == "internal" and (c.performance_rating or 0) >= 4.0:
            bonus = round(min(5.0, (c.performance_rating - 4.0) * 5 + 2.0), 1)
        breakdown = ScoreBreakdown(
            core_skills=round(WEIGHTS["core"] * len(m_core) / max(1, len(jd.core_skills)), 1),
            bonus_skills=round(WEIGHTS["bonus"] * len(m_bonus) / max(1, len(jd.bonus_skills)), 1),
            experience=round(_experience_points(c.years_experience, jd.min_years_experience), 1),
            text_relevance=round(WEIGHTS["text"] * r / top_raw, 1),
            boolean_hits=round(WEIGHTS["boolean"] * len(hits) / max(1, len(queries)), 1),
            title_alignment=round(_title_points(c, jd), 1),
            warm_bench_bonus=bonus,
        )
        scored.append(ScoredCandidate(candidate=c, breakdown=breakdown, matched_core=m_core,
                                      missing_core=miss_core, matched_bonus=m_bonus, queries_hit=hits))
    scored.sort(key=lambda s: (s.score, s.candidate.years_experience), reverse=True)
    return scored


def boolean_hit_counts(cands: list[Candidate], jd: JDAnalysis) -> list[tuple[str, int]]:
    return [(q, sum(BooleanQuery(q).matches(c) for c in cands)) for q in jd.boolean_queries]
