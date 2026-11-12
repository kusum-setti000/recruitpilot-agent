"""The source interface. Every place candidates can come from implements CandidateSource.

Today: two local JSON files. Later: an ATS export, a licensed data provider, or a LinkedIn partner
API. The pipeline only ever calls .load() and gets back normalised Candidate objects, so swapping a
source never touches matching or LLM code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from agent.models import Candidate


class CandidateSource(ABC):
    name: str = "base"
    kind: Literal["internal", "external"] = "external"

    @abstractmethod
    def load(self) -> list[Candidate]:
        """Return every candidate this source can see, already normalised."""

    def describe(self) -> str:
        return f"{self.name} ({self.kind})"
