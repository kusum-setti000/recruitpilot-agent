"""Offline tests: run with `pytest -q`. No API key needed (LLM_PROVIDER=mock)."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ["LLM_PROVIDER"] = "mock"
os.environ["AGENT_TODAY"] = "2026-11-11"

from agent.config import get_settings  # noqa: E402
from agent.heuristics import analyze_jd  # noqa: E402
from agent.llm import LLMClient  # noqa: E402
from agent.matching import BooleanQuery, requirement_coverage  # noqa: E402
from agent.models import Candidate, JDAnalysis, SkillRequirement  # noqa: E402
from agent.pipeline import RecruitingPipeline  # noqa: E402
from agent.report import build_report  # noqa: E402
from agent.skills_vocab import canonical, find_skills_in_text  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
JD = (ROOT / "jd.txt").read_text()


def cand(skills, **kw) -> Candidate:
    base = dict(id="X-1", name="Test Person", title="AI Engineer", skills=skills, years_experience=8,
                source="test", origin="external")
    return Candidate(**{**base, **kw})


@pytest.fixture(scope="module")
def result():
    return RecruitingPipeline(get_settings()).run(JD)


def test_aliases_and_text_extraction():
    assert canonical("retrieval augmented generation") == "RAG"
    assert canonical("k8s") == "Kubernetes"
    found = find_skills_in_text("Azure OpenAI exposure and FastAPI")
    assert found == ["Azure OpenAI", "FastAPI"]  # Azure OpenAI must not also count as Azure


def test_alternatives_and_implications():
    req = [SkillRequirement(name="Vector Databases", alternatives=["pgvector", "Pinecone"])]
    assert requirement_coverage(req, cand(["pgvector"]))[0] == ["Vector Databases"]
    assert requirement_coverage([SkillRequirement(name="AWS")], cand(["AWS Bedrock"]))[0] == ["AWS"]
    assert requirement_coverage([SkillRequirement(name="Strong Python")], cand(["Python"]))[0] == ["Strong Python"]


def test_boolean_query():
    c = cand(["Python", "RAG", "LangChain"], summary="built a chatbot")
    assert BooleanQuery('Python AND (RAG OR "retrieval augmented generation")').matches(c)
    assert not BooleanQuery("Python AND NOT LangChain").matches(c)
    assert BooleanQuery('"AI Engineer" AND chatbot').matches(c)


def test_jd_analysis_heuristic():
    jd = analyze_jd(JD)
    core = {r.name for r in jd.core_skills}
    assert {"Python", "LLMs", "RAG", "LangChain", "LangGraph", "Vector Databases", "FastAPI", "AWS"} <= core
    assert jd.min_years_experience == 7 and jd.seniority == "Senior"
    vec = next(r for r in jd.core_skills if r.name == "Vector Databases")
    assert {"pgvector", "Pinecone", "FAISS"} <= set(vec.alternatives)
    assert "Docker" in {r.name for r in jd.bonus_skills}


def test_internal_policy(result):
    status = {c.candidate.id: c for c in result.internal_checks}
    assert status["INT-001"].status == "match"
    assert status["INT-003"].status == "excluded" and "active" in status["INT-003"].reason
    assert status["INT-004"].status == "excluded" and "re-hire" in status["INT-004"].reason


def test_funnel_shape(result):
    ids = [s.candidate.id for s in result.shortlist]
    assert len(ids) == 10 and len(set(ids)) == 10
    assert all(m.candidate.id in ids for m in result.internal_matches)  # warm bench guaranteed a slot
    assert len(result.finalists) == 3 and set(result.evaluation.top3_ids) <= set(ids)
    assert result.final.selected_id in result.evaluation.top3_ids
    others = {f.candidate.id for f in result.finalists} - {result.final.selected_id}
    assert {c.candidate_id for c in result.final.comparison_to_finalists} == others


def test_report(result):
    md = build_report(result)
    for heading in ("## Step 1", "## Step 2", "## Step 3", "## Step 4", "## Step 5", "Why not the other finalists"):
        assert heading in md


def test_llm_retry_then_fallback():
    """A model that keeps returning an invalid finalist ID is retried, then the fallback is used."""
    s = get_settings()
    s.llm_provider, s.llm_max_retries = "mock", 1
    client = LLMClient(s)
    client.provider = "anthropic"  # pretend to be live
    calls = []

    def fake_call(schema, system, user, max_tokens):
        calls.append(user)
        return {"job_title": "x", "seniority": "Senior", "min_years_experience": 5, "core_skills": [],
                "bonus_skills": [], "domain_keywords": [], "responsibilities_keywords": [],
                "boolean_queries": ["x"], "title_variants": []}

    client._call = fake_call

    def must_have_core(jd: JDAnalysis):
        if not jd.core_skills:
            raise ValueError("core_skills is empty")

    out = client.structured(step="t", schema=JDAnalysis, system="s", user="u",
                            fallback=lambda: analyze_jd(JD), validator=must_have_core)
    assert len(calls) == 2 and "rejected" in calls[1]
    assert out.core_skills and client.history[-1].used_fallback


def test_names_hidden_from_llm():
    view = cand(["Python"]).llm_view()
    assert "name" not in view


def test_placeholder_keys_are_ignored():
    from agent.config import looks_like_real_key
    assert not looks_like_real_key("your-api-key")
    assert not looks_like_real_key("sk-your-api-key-here-xxxxxxxxxxxx")
    assert not looks_like_real_key("")
    assert looks_like_real_key("sk-proj-" + "a1B2c3D4" * 6)


def test_bad_key_fails_fast_once():
    """A 401 on step 1 must not be retried on steps 2 to 5: one API call, then deterministic fallbacks."""
    s = get_settings()
    s.llm_provider = "mock"
    llm = LLMClient(s)
    llm.provider, llm.model = "openai", "test-model"
    calls = []

    class AuthenticationError(Exception):
        status_code = 401

    def fake_call(*a, **k):
        calls.append(1)
        raise AuthenticationError("Incorrect API key provided: your-api-key")

    llm._client = object()
    llm._call = fake_call
    r = RecruitingPipeline(s, llm=llm).run(JD)
    assert len(calls) == 1
    assert r.llm_disabled_reason and "rejected the API key" in r.llm_disabled_reason
    assert r.final.selected_id in r.evaluation.top3_ids
