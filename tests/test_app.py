"""Offline tests for app.py callback functions. No server is started."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ["LLM_PROVIDER"] = "mock"
os.environ["AGENT_TODAY"] = "2026-11-11"

ROOT = Path(__file__).resolve().parents[1]
JD = (ROOT / "jd.txt").read_text()


def test_run_pipeline_yields_six_updates():
    """run_pipeline must yield exactly 6 updates: one per step (5) plus a final done."""
    from app import run_pipeline
    updates = list(run_pipeline(JD, None, "mock", False))
    assert len(updates) == 6
    # Each update is a 14-tuple: status, s1-s5, download, preview, stat_html, acc1-acc5
    assert all(len(u) == 14 for u in updates)


def test_run_pipeline_step_outputs_accumulate():
    """Each successive yield must carry more non-empty step outputs than the previous."""
    from app import run_pipeline
    updates = list(run_pipeline(JD, None, "mock", False))
    # updates[0]: after step 1 — only s1 non-empty; updates[4]: all s1–s5 non-empty
    filled = [sum(1 for s in u[1:6] if s) for u in updates]
    # Counts should be non-decreasing
    assert filled == sorted(filled)
    # All five step slots must be filled by the last substantive update
    assert filled[-1] == 5


def test_run_pipeline_final_status_says_done():
    """The last status update must contain 'Done'."""
    from app import run_pipeline
    updates = list(run_pipeline(JD, None, "mock", False))
    last_status = updates[-1][0]
    # gr.update returns a dict-like with a 'value' key in Gradio 5+
    status_text = last_status.get("value", "") if isinstance(last_status, dict) else str(last_status)
    assert "Done" in status_text


def test_run_pipeline_hide_names_omits_name_from_step5():
    """When hide_names=True the step 5 output must not contain candidate names."""
    from app import run_pipeline
    from agent.pipeline import RecruitingPipeline
    from agent.config import get_settings

    # Run once to get the actual selected name
    result = RecruitingPipeline(get_settings()).run(JD)
    selected_name = result.candidate(result.final.selected_id).candidate.name

    updates_hidden = list(run_pipeline(JD, None, "mock", True))
    s5_hidden = updates_hidden[-1][5]
    assert selected_name not in s5_hidden
    # The ID must still be present
    assert result.final.selected_id in s5_hidden


def test_run_pipeline_short_input_returns_single_error_update():
    """A JD shorter than 50 chars must produce exactly one error yield with no step content."""
    from app import run_pipeline
    updates = list(run_pipeline("too short", None, "mock", False))
    assert len(updates) == 1
    assert len(updates[0]) == 14
    # s1-s5 are at indices 1-5; all must be empty strings
    all_steps_empty = all(u == "" for u in updates[0][1:6])
    assert all_steps_empty


def test_load_history_after_run(tmp_path):
    """After a service run, storage must contain at least one row."""
    from agent.service import RecruitingService
    from agent.storage import RunStorage
    svc = RecruitingService(db_path=tmp_path / "test.db")
    svc.run(JD, provider="mock")
    storage = RunStorage(tmp_path / "test.db")
    runs = storage.list_runs()
    assert len(runs) >= 1
    assert runs[0].selected_id  # selected_id must be non-empty


def test_app_css_contains_theme_tokens():
    """The _CSS constant must declare the accent color and all three required font families."""
    from app import _CSS
    assert "#E5402E" in _CSS, "Accent color #E5402E missing from _CSS"
    assert "Saira Condensed" in _CSS, "Font 'Saira Condensed' missing from _CSS"
    assert "Manrope" in _CSS, "Font 'Manrope' missing from _CSS"
    assert "JetBrains Mono" in _CSS, "Font 'JetBrains Mono' missing from _CSS"


def test_view_run_returns_report(tmp_path, monkeypatch):
    """view_run_by_id must return the saved report markdown when given a valid run ID."""
    from agent.service import RecruitingService
    from agent.storage import RunStorage
    from agent.config import get_settings

    svc = RecruitingService(db_path=tmp_path / "test.db")
    svc.run(JD, provider="mock")
    storage = RunStorage(tmp_path / "test.db")
    runs = storage.list_runs()
    run_id = runs[0].run_id

    # Monkeypatch so view_run_by_id finds the tmp db via service.get_run()
    settings = get_settings()
    settings.history_db = tmp_path / "test.db"
    monkeypatch.setattr("agent.config.get_settings", lambda: settings)
    monkeypatch.setattr("agent.service.get_settings", lambda: settings)

    from app import view_run_by_id
    report = view_run_by_id(run_id)
    assert "## Step 1" in report
    assert runs[0].selected_id in report


def test_fmt_step5_blank_lines_after_div():
    """_fmt_step5 must have '\\n\\n' right after the opening rp-selected-card div."""
    from app import _fmt_step5
    from agent.pipeline import RecruitingPipeline
    from agent.config import get_settings
    result = RecruitingPipeline(get_settings()).run(JD)
    output = _fmt_step5(result, show_names=True)
    assert '<div class="rp-selected-card">\n\n' in output
