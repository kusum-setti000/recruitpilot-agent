"""Source registry. Add new adapters to EXTERNAL_REGISTRY and list them in EXTERNAL_SOURCES."""
from __future__ import annotations

from typing import Callable

from agent.config import Settings
from agent.sources.base import CandidateSource
from agent.sources.json_sources import ExternalTalentPoolSource, InternalPastHiresSource
from agent.sources.linkedin import LinkedInSource

EXTERNAL_REGISTRY: dict[str, Callable[[Settings], CandidateSource]] = {
    "json_external": lambda s: ExternalTalentPoolSource(s.external_db),
    "linkedin": lambda s: LinkedInSource(),
}


def internal_source(settings: Settings) -> CandidateSource:
    return InternalPastHiresSource(settings.internal_db)


def external_sources(settings: Settings) -> list[CandidateSource]:
    unknown = [n for n in settings.external_sources if n not in EXTERNAL_REGISTRY]
    if unknown:
        raise ValueError(f"Unknown EXTERNAL_SOURCES: {unknown}. Known: {list(EXTERNAL_REGISTRY)}")
    return [EXTERNAL_REGISTRY[n](settings) for n in settings.external_sources]


__all__ = ["CandidateSource", "internal_source", "external_sources", "EXTERNAL_REGISTRY"]
