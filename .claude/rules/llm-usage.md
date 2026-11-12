---
paths:
  - "agent/llm.py"
  - "agent/prompts.py"
  - "agent/pipeline.py"
  - "agent/models.py"
  - "agent/heuristics.py"
---
# LLM usage rules

- Every model call goes through `LLMClient.structured(step=..., schema=..., system=..., user=..., fallback=..., validator=...)`.
- Every new LLM step needs three things in the same change: a Pydantic output schema in `models.py`, a business-rule validator, and a deterministic fallback in `heuristics.py`.
- Validators must reject IDs that were not in the input. Models will invent IDs if allowed to.
- Prompts live in `prompts.py` and start from `RECRUITER_PERSONA`. Keep the fairness clause: judge only job-relevant evidence, never protected characteristics, never invent facts.
- Send candidates to the model through `Candidate.llm_view()` only. Do not pass raw dicts or names.
- Default model is configured in `.env` (`ANTHROPIC_MODEL`, `OPENAI_MODEL`). Never hard-code a model string in step code.
- When changing a prompt, run the pipeline in both mock and live mode and compare the Top 3 against the deterministic baseline. Note large disagreements in the PR.
