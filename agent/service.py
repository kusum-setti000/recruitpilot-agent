"""RecruitingService: the single entry point for both the CLI and the web app.

Wraps RecruitingPipeline so neither the CLI nor the web UI needs to know about
the pipeline's internal structure. A new pipeline instance is created for every
run, keeping per-run state isolated.
"""
from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import Iterator, Optional

from agent.config import Settings, get_settings
from agent.pipeline import PipelineResult, RecruitingPipeline
from agent.report import build_report
from agent.storage import RunRecord, RunStorage, RunSummary

log = logging.getLogger(__name__)


class RecruitingService:
    def __init__(self, db_path: Optional[Path] = None, default_provider: Optional[str] = None) -> None:
        # db_path is optional; defaults to settings.history_db so tests can use a temp file
        self._default_db_path = db_path
        self._default_provider = default_provider
        self._last_run_id: Optional[str] = None

    def _storage(self, settings: Settings) -> RunStorage:
        path = self._default_db_path or settings.history_db
        return RunStorage(path)

    def _make_settings(self, provider: Optional[str]) -> Settings:
        """Return Settings with an optional provider override. Never touches os.environ."""
        settings = get_settings()
        effective = provider if (provider and provider != "auto") else self._default_provider
        if effective and effective != "auto":
            settings = dataclasses.replace(settings, llm_provider=effective)
        return settings

    def stream(
        self,
        jd_text: str,
        provider: Optional[str] = None,
    ) -> Iterator[tuple[int, PipelineResult]]:
        """Yield (step_number, PipelineResult) after each of the five steps."""
        settings = self._make_settings(provider)
        pipeline = RecruitingPipeline(settings)  # NEW pipeline every call
        result = None
        for step_num, result in pipeline.iter_steps(jd_text):
            yield step_num, result
        if result is not None and result.final is not None:
            storage = self._storage(settings)
            self._last_run_id = storage.save_run(result, build_report(result))

    def run(
        self,
        jd_text: str,
        provider: Optional[str] = None,
    ) -> PipelineResult:
        """Run the full pipeline and return the final result."""
        result = None
        for _, result in self.stream(jd_text, provider=provider):
            pass
        return result

    def list_runs(self) -> list[RunSummary]:
        settings = get_settings()
        return self._storage(settings).list_runs()

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        """Return the full RunRecord for the given run ID, or None if not found."""
        settings = get_settings()
        return self._storage(settings).get_run(run_id)
