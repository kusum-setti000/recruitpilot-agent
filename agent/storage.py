"""SQLite run-history store. Uses only stdlib sqlite3.

Keeps a persistent record of every pipeline run so the web app History tab and
the CLI can show past results without re-running the pipeline.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from agent.pipeline import PipelineResult

log = logging.getLogger(__name__)


def _serialize_result(result: PipelineResult) -> dict:
    """Convert PipelineResult to a JSON-safe dict, handling Pydantic models properly."""

    def _ser(obj):
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return {f.name: _ser(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
        if isinstance(obj, list):
            return [_ser(item) for item in obj]
        if isinstance(obj, tuple):
            return [_ser(item) for item in obj]
        if isinstance(obj, dict):
            return {k: _ser(v) for k, v in obj.items()}
        return obj

    return _ser(result)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    provider TEXT NOT NULL,
    job_title TEXT NOT NULL,
    selected_id TEXT NOT NULL,
    report_md TEXT NOT NULL,
    result_json TEXT NOT NULL
)
"""


@dataclass
class RunSummary:
    run_id: str
    timestamp: str
    provider: str
    job_title: str
    selected_id: str


@dataclass
class RunRecord(RunSummary):
    report_md: str
    result_json: str


class RunStorage:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def save_run(self, result: PipelineResult, report_md: str) -> str:
        run_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        provider = result.llm_label
        job_title = result.jd.job_title if result.jd else ""
        selected_id = result.final.selected_id if result.final else ""
        result_json = json.dumps(_serialize_result(result))
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO runs (run_id, timestamp, provider, job_title, selected_id, report_md, result_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, timestamp, provider, job_title, selected_id, report_md, result_json),
            )
        log.info("Saved run %s (job=%s, selected=%s)", run_id, job_title, selected_id)
        return run_id

    def list_runs(self) -> list[RunSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT run_id, timestamp, provider, job_title, selected_id FROM runs ORDER BY timestamp DESC"
            ).fetchall()
        return [RunSummary(*row) for row in rows]

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT run_id, timestamp, provider, job_title, selected_id, report_md, result_json "
                "FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return RunRecord(*row)
