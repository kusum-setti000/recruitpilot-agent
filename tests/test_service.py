"""Offline tests for the service and storage layers. All use mock provider and a tmp DB."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ["LLM_PROVIDER"] = "mock"
os.environ["AGENT_TODAY"] = "2026-11-11"

ROOT = Path(__file__).resolve().parents[1]
JD = (ROOT / "jd.txt").read_text()
JD2 = "We are hiring a Data Scientist with 5+ years experience in Python, pandas, scikit-learn, and SQL."


def test_streaming_order(tmp_path):
    from agent.service import RecruitingService
    svc = RecruitingService(db_path=tmp_path / "test.db")
    steps = [n for n, _ in svc.stream(JD, provider="mock")]
    assert steps == [1, 2, 3, 4, 5]


def test_storage_round_trip(tmp_path):
    from agent.service import RecruitingService
    from agent.storage import RunStorage
    svc = RecruitingService(db_path=tmp_path / "test.db")
    result = svc.run(JD, provider="mock")
    storage = RunStorage(tmp_path / "test.db")
    runs = storage.list_runs()
    assert len(runs) == 1
    record = storage.get_run(runs[0].run_id)
    assert record.selected_id == result.final.selected_id
    assert "## Step 1" in record.report_md


def test_service_run_mock(tmp_path):
    from agent.pipeline import PipelineResult
    from agent.service import RecruitingService
    svc = RecruitingService(db_path=tmp_path / "test.db")
    result = svc.run(JD, provider="mock")
    assert isinstance(result, PipelineResult)
    assert result.final is not None
    assert result.final.selected_id in result.evaluation.top3_ids


def test_provider_isolation(tmp_path):
    """Service must not leave LLM_PROVIDER changed in os.environ after a run."""
    before = os.environ.get("LLM_PROVIDER")
    from agent.service import RecruitingService
    svc = RecruitingService(db_path=tmp_path / "test.db")
    svc.run(JD, provider="mock")
    assert os.environ.get("LLM_PROVIDER") == before


def test_no_shared_state_between_runs(tmp_path):
    """Two runs with different JD texts must not share pipeline state (_jd_text)."""
    from agent.service import RecruitingService
    svc = RecruitingService(db_path=tmp_path / "test.db")
    r1 = svc.run(JD, provider="mock")
    r2 = svc.run(JD2, provider="mock")
    assert r1.jd_text == JD
    assert r2.jd_text == JD2
    assert r1.jd_text != r2.jd_text


def test_result_json_is_real_json(tmp_path):
    """result_json stored in SQLite must be valid JSON with the final selected_id and shortlist IDs."""
    import json
    from agent.service import RecruitingService
    from agent.storage import RunStorage
    svc = RecruitingService(db_path=tmp_path / "test.db")
    result = svc.run(JD, provider="mock")
    storage = RunStorage(tmp_path / "test.db")
    record = storage.get_run(storage.list_runs()[0].run_id)
    data = json.loads(record.result_json)
    assert data["final"]["selected_id"] == result.final.selected_id
    shortlist_ids = [entry["candidate"]["id"] for entry in data["shortlist"]]
    assert set(shortlist_ids) == {s.candidate.id for s in result.shortlist}


def test_list_runs(tmp_path):
    from agent.service import RecruitingService
    svc = RecruitingService(db_path=tmp_path / "test.db")
    svc.run(JD, provider="mock")
    svc.run(JD, provider="mock")
    assert len(svc.list_runs()) == 2
