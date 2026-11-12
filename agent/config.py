"""Runtime settings, read from environment variables (and a local .env file if present)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_provider() -> str:
    explicit = os.getenv("LLM_PROVIDER", "auto").strip().lower()
    if explicit != "auto":
        return explicit
    if looks_like_real_key(os.getenv("ANTHROPIC_API_KEY")):
        return "anthropic"
    if looks_like_real_key(os.getenv("OPENAI_API_KEY")):
        return "openai"
    return "mock"


_PLACEHOLDER_HINTS = ("your", "changeme", "replace", "xxx", "<", "placeholder", "api-key", "api_key")


def looks_like_real_key(value: str | None) -> bool:
    """True for something shaped like a real key; False for empty values and template placeholders."""
    if not value:
        return False
    v = value.strip().strip('"').strip("'")
    return len(v) >= 20 and not any(h in v.lower() for h in _PLACEHOLDER_HINTS)


@dataclass
class Settings:
    llm_provider: str = field(default_factory=_resolve_provider)
    anthropic_model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    llm_max_retries: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_RETRIES", "2")))
    llm_temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.2")))

    internal_db: Path = field(default_factory=lambda: ROOT / os.getenv("INTERNAL_DB", "data/internal_past_hires.json"))
    external_db: Path = field(default_factory=lambda: ROOT / os.getenv("EXTERNAL_DB", "data/external_talent_pool.json"))
    # Comma separated source names, see agent/sources/__init__.py
    external_sources: list[str] = field(
        default_factory=lambda: [s.strip() for s in os.getenv("EXTERNAL_SOURCES", "json_external").split(",") if s.strip()]
    )

    shortlist_size: int = field(default_factory=lambda: int(os.getenv("SHORTLIST_SIZE", "10")))
    finalist_count: int = 3
    # Recruiter policy: a qualified warm-bench re-hire always gets a shortlist slot.
    warm_bench_guaranteed: bool = field(default_factory=lambda: _bool("WARM_BENCH_GUARANTEED", True))
    # A re-hire whose availability date is within this many days still counts as available.
    available_soon_days: int = field(default_factory=lambda: int(os.getenv("AVAILABLE_SOON_DAYS", "60")))
    min_internal_rating: float = field(default_factory=lambda: float(os.getenv("MIN_INTERNAL_RATING", "3.5")))
    # Send names to the LLM? Off by default: the evaluation steps see candidate IDs only.
    send_names_to_llm: bool = field(default_factory=lambda: _bool("SEND_NAMES_TO_LLM", False))

    today: date = field(default_factory=lambda: date.fromisoformat(os.getenv("AGENT_TODAY", date.today().isoformat())))

    history_db: Path = field(default_factory=lambda: ROOT / os.getenv("HISTORY_DB", "runs/history.db"))


def get_settings() -> Settings:
    return Settings()
