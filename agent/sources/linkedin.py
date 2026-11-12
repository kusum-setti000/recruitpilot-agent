"""Placeholder for a live LinkedIn (or licensed profile data) source.

Why this is a stub: LinkedIn's profile search APIs are only open to approved partners (Talent
Solutions / Recruiter System Connect), and scraping profiles breaks their terms. The realistic routes
are:
  1. LinkedIn RSC through your ATS, if your company is a partner.
  2. A licensed data provider (for example Bright Data datasets, People Data Labs, Coresignal), where
     the vendor owns the compliance burden.
  3. Candidates who applied or opted in through your own portal.

To plug one in: implement load() to call the provider, map each record onto Candidate (origin
"external", source set to the provider name), register it in agent/sources/__init__.py, and add its
name to EXTERNAL_SOURCES in .env. Nothing else in the pipeline needs to change.
"""
from __future__ import annotations

import os

from agent.models import Candidate
from agent.sources.base import CandidateSource


class LinkedInSource(CandidateSource):
    name = "linkedin"
    kind = "external"

    def __init__(self) -> None:
        self.api_key = os.getenv("LINKEDIN_API_KEY")

    def load(self) -> list[Candidate]:
        if not self.api_key:
            raise RuntimeError(
                "LinkedIn source is not configured (no LINKEDIN_API_KEY). "
                "Remove 'linkedin' from EXTERNAL_SOURCES or implement this adapter."
            )
        raise NotImplementedError("Map the provider's response onto Candidate here.")
