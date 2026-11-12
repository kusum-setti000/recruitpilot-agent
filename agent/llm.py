"""Provider-agnostic structured LLM calls.

Every LLM step goes through LLMClient.structured(), which:
  1. sends the system and user prompt plus the Pydantic schema,
  2. validates the reply against the schema and an optional business-rule validator
     (for example "top3_ids must all be on the shortlist"),
  3. retries with the validation error fed back to the model,
  4. falls back to the step's deterministic implementation if the model still fails.

Providers: anthropic (tool use forced to the schema), openai (JSON mode), mock (offline, runs the
deterministic fallback directly so the whole pipeline works without a key).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional, TypeVar

from pydantic import BaseModel, ValidationError

from agent.config import Settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


def _inline_refs(schema: dict) -> dict:
    """Resolve $ref/$defs so the schema is self-contained (friendlier for tool-use input schemas)."""
    defs = schema.get("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            return {k: walk(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


def _is_auth_error(e: Exception) -> bool:
    status = getattr(e, "status_code", None)
    return status in (401, 403) or type(e).__name__ in {"AuthenticationError", "PermissionDeniedError"}


@dataclass
class CallRecord:
    step: str
    provider: str
    used_fallback: bool
    attempts: int
    error: Optional[str] = None


@dataclass
class LLMClient:
    settings: Settings
    history: list[CallRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.provider = self.settings.llm_provider
        self._client = None
        self.disabled_reason: Optional[str] = None
        if self.provider == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic()
            self.model = self.settings.anthropic_model
        elif self.provider == "openai":
            import openai
            self._client = openai.OpenAI()
            self.model = self.settings.openai_model
        elif self.provider == "mock":
            self.model = "deterministic-fallback"
        else:
            raise ValueError(f"Unknown LLM_PROVIDER '{self.provider}' (use anthropic, openai, mock or auto)")

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"

    # ---- public ----
    def structured(
        self,
        *,
        step: str,
        schema: type[T],
        system: str,
        user: str,
        fallback: Callable[[], T],
        validator: Optional[Callable[[T], None]] = None,
        max_tokens: int = 4000,
    ) -> T:
        if self.provider == "mock" or self.disabled_reason:
            self.history.append(CallRecord(step, self.provider, used_fallback=True, attempts=0,
                                           error=self.disabled_reason))
            return fallback()

        last_err: Optional[str] = None
        prompt = user
        for attempt in range(1, self.settings.llm_max_retries + 2):
            try:
                raw = self._call(schema, system, prompt, max_tokens)
                obj = schema.model_validate(raw)
                if validator:
                    validator(obj)
                self.history.append(CallRecord(step, self.provider, False, attempt))
                return obj
            except (ValidationError, ValueError, KeyError, json.JSONDecodeError) as e:
                last_err = str(e)[:800]
                log.warning("%s attempt %d failed validation: %s", step, attempt, last_err)
                prompt = (f"{user}\n\nYour previous answer was rejected for this reason:\n{last_err}\n"
                          "Fix it and answer again using only the allowed candidate IDs and the exact schema.")
            except Exception as e:  # network, auth, rate limit: no point retrying the prompt
                last_err = f"{type(e).__name__}: {e}"[:800]
                if _is_auth_error(e):
                    # A bad key will fail every step the same way, so stop calling the API for this run.
                    self.disabled_reason = (f"{self.provider} rejected the API key ({type(e).__name__}). "
                                            "Check the key in .env and any system-wide environment variable.")
                    log.error(self.disabled_reason)
                else:
                    log.error("%s LLM call failed: %s", step, last_err)
                break

        self.history.append(CallRecord(step, self.provider, True, attempt, last_err))
        return fallback()

    # ---- providers ----
    def _call(self, schema: type[BaseModel], system: str, user: str, max_tokens: int) -> dict:
        json_schema = _inline_refs(schema.model_json_schema())
        if self.provider == "anthropic":
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=self.settings.llm_temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
                tools=[{"name": "submit", "description": f"Submit the {schema.__name__} result.",
                        "input_schema": json_schema}],
                tool_choice={"type": "tool", "name": "submit"},
            )
            for block in resp.content:
                if getattr(block, "type", None) == "tool_use":
                    return block.input
            raise ValueError("Model did not return a tool_use block")

        # openai
        resp = self._client.chat.completions.create(
            model=self.model,
            temperature=self.settings.llm_temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": f"{system}\n\nReturn only a JSON object matching this JSON schema:\n"
                                              f"{json.dumps(json_schema)}"},
                {"role": "user", "content": user},
            ],
        )
        return json.loads(resp.choices[0].message.content)
