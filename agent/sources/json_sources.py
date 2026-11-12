"""Local JSON sources: the warm bench (past hires) and the simulated external pool."""
from __future__ import annotations

import json
from pathlib import Path

from agent.models import Candidate
from agent.sources.base import CandidateSource


class InternalPastHiresSource(CandidateSource):
    name = "internal_past_hires"
    kind = "internal"

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> list[Candidate]:
        rows = json.loads(self.path.read_text())
        return [
            Candidate(
                id=r["id"], name=r["name"], title=r["role"], skills=r["skills"],
                years_experience=r["years_experience"], location=r.get("location", ""),
                summary=r.get("last_project", ""), source="Internal Past Hires", origin="internal",
                past_contract_end_date=r["past_contract_end_date"],
                performance_rating=r.get("performance_rating"),
                availability_status=r.get("availability_status"),
                rehire_eligible=r.get("rehire_eligible", True), last_project=r.get("last_project"),
            )
            for r in rows
        ]


class ExternalTalentPoolSource(CandidateSource):
    name = "json_external"
    kind = "external"

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> list[Candidate]:
        rows = json.loads(self.path.read_text())
        return [
            Candidate(
                id=r["id"], name=r["name"], title=r["current_title"], skills=r["skills"],
                years_experience=r["years_experience"], summary=r.get("summary", ""),
                location=r.get("location", ""), source=r.get("source", "External Portal"),
                origin="external", current_company=r.get("current_company"),
                industry=r.get("industry"), open_to_work=r.get("open_to_work"),
            )
            for r in rows
        ]
