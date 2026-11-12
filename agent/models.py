"""Pydantic models shared across the pipeline.

Two groups:
  Data models (Candidate, ScoreBreakdown, ScoredCandidate) used by sources and the matcher.
  LLM output schemas (JDAnalysis, InternalNotes, ShortlistEvaluation, FinalSelection). These are sent
  to the model as JSON schema, and every response is validated against them before it is used.
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------- data models ----------

class Candidate(BaseModel):
    """One person, normalised from any source (internal DB, external pool, future APIs)."""
    id: str
    name: str
    title: str
    skills: list[str]
    years_experience: int
    summary: str = ""
    location: str = ""
    source: str
    origin: Literal["internal", "external"]
    # external only
    current_company: Optional[str] = None
    industry: Optional[str] = None
    open_to_work: Optional[bool] = None
    # internal (warm bench) only
    past_contract_end_date: Optional[date] = None
    performance_rating: Optional[float] = None
    availability_status: Optional[str] = None
    rehire_eligible: Optional[bool] = None
    last_project: Optional[str] = None

    def search_text(self) -> str:
        parts = [self.title, " ".join(self.skills), self.summary, self.last_project or "", self.industry or ""]
        return " ".join(parts)

    def llm_view(self, include_name: bool = False) -> dict:
        """What the LLM gets to see. Names are left out by default to reduce bias."""
        view = {
            "candidate_id": self.id,
            "title": self.title,
            "years_experience": self.years_experience,
            "skills": self.skills,
            "summary": self.summary or self.last_project,
            "industry": self.industry,
            "location": self.location,
            "origin": "internal re-hire (warm bench)" if self.origin == "internal" else f"external ({self.source})",
        }
        if self.origin == "internal":
            view["past_performance_rating_out_of_5"] = self.performance_rating
            view["availability"] = self.availability_status
        if include_name:
            view["name"] = self.name
        return {k: v for k, v in view.items() if v not in (None, "")}


class ScoreBreakdown(BaseModel):
    core_skills: float
    bonus_skills: float
    experience: float
    text_relevance: float
    boolean_hits: float
    title_alignment: float
    warm_bench_bonus: float = 0.0

    @property
    def total(self) -> float:
        return round(min(100.0, sum(self.model_dump().values())), 1)


class ScoredCandidate(BaseModel):
    candidate: Candidate
    breakdown: ScoreBreakdown
    matched_core: list[str]
    missing_core: list[str]
    matched_bonus: list[str]
    queries_hit: list[int] = Field(default_factory=list)

    @property
    def score(self) -> float:
        return self.breakdown.total


# ---------- LLM output schemas ----------

class SkillRequirement(BaseModel):
    name: str = Field(description="Canonical skill name, e.g. 'Vector Databases'")
    alternatives: list[str] = Field(default_factory=list,
                                    description="Skills that also satisfy this requirement, e.g. ['pgvector','Pinecone']")


class JDAnalysis(BaseModel):
    job_title: str
    seniority: Literal["Junior", "Mid", "Senior", "Staff/Principal", "Lead/Manager"]
    min_years_experience: int = Field(ge=0, le=40)
    core_skills: list[SkillRequirement] = Field(description="Must-have skills")
    bonus_skills: list[SkillRequirement] = Field(description="Nice-to-have skills")
    domain_keywords: list[str] = Field(description="Industry or domain terms, e.g. 'mortgage', 'financial services'")
    responsibilities_keywords: list[str] = Field(description="Short phrases for what the person will do")
    boolean_queries: list[str] = Field(
        min_length=1, max_length=5,
        description='Boolean search strings using AND, OR, NOT, parentheses and "quoted phrases". '
                    "Order from strictest to broadest.")
    title_variants: list[str] = Field(description="Job titles that describe the same role")
    work_arrangement: str = Field(default="", description="Location / remote / hybrid requirement, if stated")


class InternalNote(BaseModel):
    candidate_id: str
    fit_note: str = Field(description="One or two sentences: why this past hire fits, and any gap")


class InternalNotes(BaseModel):
    notes: list[InternalNote]


class CandidateEvaluation(BaseModel):
    candidate_id: str
    skill_alignment: int = Field(ge=1, le=10)
    experience_depth: int = Field(ge=1, le=10)
    domain_fit: int = Field(ge=1, le=10)
    overall: int = Field(ge=1, le=100)
    strengths: list[str]
    concerns: list[str]


class ShortlistEvaluation(BaseModel):
    evaluations: list[CandidateEvaluation] = Field(description="One entry for every shortlisted candidate")
    top3_ids: list[str] = Field(min_length=3, max_length=3, description="Finalist IDs, best first")
    rationale: str = Field(description="Why these three advanced and the others did not")


class FinalistComparison(BaseModel):
    candidate_id: str
    why_not_selected: str


class FinalSelection(BaseModel):
    selected_id: str
    headline: str = Field(description="One line recruiter summary of the pick")
    why_selected: str = Field(description="A full paragraph of justification")
    skill_overlap: list[str] = Field(description="JD requirements this person clearly covers")
    experience_edge: str
    comparison_to_finalists: list[FinalistComparison]
    comparison_to_pool: str = Field(description="Why this person beats the wider shortlist and pool")
    gaps_and_risks: list[str]
    interview_focus: list[str] = Field(description="What to probe in interviews to de-risk the hire")
    confidence: Literal["High", "Medium", "Low"]
