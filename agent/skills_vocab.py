"""Skill vocabulary: canonical names, aliases and implications.

This is what lets "Retrieval Augmented Generation", "RAG" and "rag" count as the same skill, and lets
someone who lists "pgvector" satisfy a "Vector Databases" requirement. Extend ALIASES and IMPLIES as
new roles come in; the LLM's JD analysis can also add aliases at runtime (see expand_aliases).
"""
from __future__ import annotations

import re
from functools import lru_cache

# canonical display name -> aliases (lowercase). The display name itself is always an alias.
ALIASES: dict[str, list[str]] = {
    "Python": ["python3"],
    "LLMs": ["llm", "large language model", "large language models", "generative ai", "genai", "gen ai"],
    "RAG": ["retrieval augmented generation", "retrieval-augmented generation"],
    "LangChain": [], "LangGraph": [], "LlamaIndex": ["llama index", "llama-index"],
    "Prompt Engineering": ["prompting", "prompt design"],
    "Vector Databases": ["vector database", "vector db", "vector store", "vector stores", "vector search"],
    "pgvector": [], "Pinecone": [], "FAISS": [], "Weaviate": [], "ChromaDB": ["chroma"],
    "OpenAI API": ["openai"], "Anthropic Claude": ["claude", "anthropic"], "Azure OpenAI": [],
    "AWS Bedrock": ["bedrock", "amazon bedrock"], "AWS SageMaker": ["sagemaker", "amazon sagemaker"],
    "AWS Lambda": ["lambda"], "AWS ECS": ["ecs"],
    "AWS": ["amazon web services"], "Azure": ["microsoft azure"], "GCP": ["google cloud"],
    "Hugging Face": ["huggingface", "hf transformers"], "Transformers": [],
    "FastAPI": ["fast api"], "Flask": [], "Django": [], "REST APIs": ["rest api", "restful"],
    "Docker": [], "Kubernetes": ["k8s", "eks", "aks"],
    "MLflow": [], "Kubeflow": [], "LangSmith": [], "RAGAS": [],
    "LLM Evaluation": ["llm evaluation", "llm evaluation frameworks", "llm evals", "evaluation frameworks", "groundedness metrics"],
    "Fine-tuning": ["fine tuning", "finetuning", "fine-tune"], "LoRA": ["qlora", "peft"],
    "AI Agents": ["agentic", "agentic workflows", "multi-agent", "tool calling"],
    "Guardrails": ["guardrail"], "PyTorch": ["torch"], "TensorFlow": [],
    "Machine Learning": ["ml"], "MLOps": ["ml ops", "llm ops", "llmops"], "NLP": ["natural language processing"],
    "Scikit-learn": ["sklearn", "scikit learn"], "XGBoost": [], "Statistics": [], "SQL": [],
    "Pandas": [], "Spark": ["pyspark", "apache spark"], "Airflow": [], "ETL": [], "Databricks": [],
    "Snowflake": [], "BigQuery": ["big query"], "Redshift": [], "dbt": [],
    "Cloud Data Warehouse": ["cloud data warehouse", "data warehouse", "data warehousing"], "Kafka": [], "Terraform": [], "PostgreSQL": ["postgres"],
    "CI/CD": ["ci cd", "cicd"], "Linux": [], "TypeScript": [], "JavaScript": [], "React": [],
    "Node.js": ["nodejs"], "Next.js": ["nextjs"], "Java": [], "Spring Boot": [],
    "Microservices": [], "Security": [], "Data Science": [], "Pydantic": [], "SQLAlchemy": [],
    "Redis": [], "pytest": [], "Time Series Forecasting": ["forecasting"],
}

# having the key skill implies having these too
IMPLIES: dict[str, list[str]] = {
    "pgvector": ["Vector Databases", "PostgreSQL"], "Pinecone": ["Vector Databases"],
    "FAISS": ["Vector Databases"], "Weaviate": ["Vector Databases"], "ChromaDB": ["Vector Databases"],
    "AWS Bedrock": ["AWS", "LLMs"], "AWS SageMaker": ["AWS"], "AWS Lambda": ["AWS"], "AWS ECS": ["AWS"],
    "Azure OpenAI": ["Azure", "LLMs"], "OpenAI API": ["LLMs"], "Anthropic Claude": ["LLMs"],
    "RAGAS": ["LLM Evaluation"], "LangSmith": ["LLM Evaluation"], "LoRA": ["Fine-tuning"],
    "FastAPI": ["REST APIs"], "Flask": ["REST APIs"], "Django": ["REST APIs"],
    "LangGraph": ["AI Agents"], "RAG": ["LLMs"], "LangChain": ["LLMs"], "LlamaIndex": ["LLMs", "RAG"],
    "Kubernetes": ["Docker"], "Snowflake": ["Cloud Data Warehouse"], "BigQuery": ["Cloud Data Warehouse", "GCP"],
    "Redshift": ["Cloud Data Warehouse", "AWS"], "Databricks": ["Cloud Data Warehouse"], "Transformers": ["Hugging Face"], "NLP": ["Machine Learning"],
}

_CANON_BY_LOWER = {c.lower(): c for c in ALIASES}


@lru_cache(maxsize=1)
def _alias_index() -> dict[str, str]:
    idx: dict[str, str] = {}
    for canon, aliases in ALIASES.items():
        idx[canon.lower()] = canon
        for a in aliases:
            idx[a.lower()] = canon
    return idx


def expand_aliases(extra: dict[str, list[str]]) -> None:
    """Add runtime aliases (for example from the LLM). Unknown canonicals become new skills."""
    for canon, aliases in extra.items():
        canon_disp = _CANON_BY_LOWER.get(canon.lower(), canon)
        ALIASES.setdefault(canon_disp, [])
        _CANON_BY_LOWER[canon_disp.lower()] = canon_disp
        for a in aliases:
            if a.lower() not in ALIASES[canon_disp]:
                ALIASES[canon_disp].append(a.lower())
    _alias_index.cache_clear()


def canonical(skill: str) -> str:
    """Map any spelling to its canonical name (unknown skills come back unchanged)."""
    return _alias_index().get(skill.strip().lower(), skill.strip())


def skill_closure(skills: list[str]) -> set[str]:
    """Canonical skills a person has, including implied ones (lowercased for comparison)."""
    out: set[str] = set()
    stack = [canonical(s) for s in skills]
    while stack:
        s = stack.pop()
        if s.lower() in out:
            continue
        out.add(s.lower())
        stack.extend(IMPLIES.get(s, []))
    return out


def find_skills_in_text(text: str) -> list[str]:
    """Return canonical skills mentioned in free text, in order of first appearance.

    Longest aliases are matched first, and matched spans are blanked out, so "Azure OpenAI" does not
    also count as "Azure" and "OpenAI API".
    """
    idx = _alias_index()
    lowered = text.lower()
    found: list[tuple[int, str]] = []
    for alias in sorted(idx, key=len, reverse=True):
        if len(alias) <= 2 and alias not in {"ml", "r"}:
            continue  # avoid tiny aliases matching inside words
        pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
        for m in re.finditer(pattern, lowered):
            found.append((m.start(), idx[alias]))
            lowered = lowered[: m.start()] + " " * (m.end() - m.start()) + lowered[m.end():]
    seen, ordered = set(), []
    for _, canon in sorted(found):
        if canon not in seen:
            seen.add(canon)
            ordered.append(canon)
    return ordered


def aliases_for(skill: str) -> list[str]:
    canon = canonical(skill)
    return [canon] + ALIASES.get(canon, [])
