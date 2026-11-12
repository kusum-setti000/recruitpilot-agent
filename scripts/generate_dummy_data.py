"""Generate the dummy candidate databases.

Creates two files under data/:
  internal_past_hires.json   20 people we hired before (the "warm bench")
  external_talent_pool.json  100 people from an external portal / simulated LinkedIn dump

The generator is seeded, so re-running it gives the same data every time.
Every name, company and profile here is fictional.

Usage:
    python scripts/generate_dummy_data.py
    python scripts/generate_dummy_data.py --seed 7 --external 150
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
TODAY = date(2026, 11, 11)

FIRST_NAMES = [
    "Aarav", "Priya", "Daniel", "Mei", "Carlos", "Fatima", "Ethan", "Ananya", "Lucas", "Sofia",
    "Ravi", "Grace", "Omar", "Hannah", "Kenji", "Isabella", "Vikram", "Chloe", "Mateo", "Aisha",
    "Noah", "Divya", "Samuel", "Yuki", "Gabriel", "Leila", "Arjun", "Emily", "Tomas", "Nadia",
    "Rohan", "Olivia", "Jamal", "Sneha", "Liam", "Zara", "Kiran", "Ava", "Diego", "Meera",
    "Benjamin", "Lin", "Elena", "Siddharth", "Maya", "Hassan", "Julia", "Pranav", "Camila", "Wei",
]
LAST_NAMES = [
    "Reddy", "Thompson", "Nakamura", "Garcia", "Okafor", "Patel", "Kowalski", "Iyer", "Fischer",
    "Hernandez", "Chen", "Mensah", "Sharma", "Brennan", "Rahman", "Silva", "Novak", "Kapoor",
    "Andersen", "Ito", "Murphy", "Venkatesh", "Rossi", "Adeyemi", "Kim", "Dubois", "Rao", "Walsh",
    "Haddad", "Lindqvist", "Menon", "Ortiz", "Takahashi", "Nair", "Becker", "Alvarez", "Shah", "Park",
]
LOCATIONS = [
    "Reston, VA", "Washington, DC", "Arlington, VA", "New York, NY", "Austin, TX", "Dallas, TX",
    "Chicago, IL", "Seattle, WA", "San Francisco, CA", "Atlanta, GA", "Charlotte, NC", "Boston, MA",
    "Jacksonville, FL", "Denver, CO", "Remote (US)", "Remote (US)", "Toronto, ON", "Hyderabad, India",
]
INDUSTRIES = [
    "financial services", "mortgage and housing finance", "healthcare", "insurance", "retail",
    "e-commerce", "telecom", "logistics", "public sector", "SaaS", "banking", "pharma",
]
COMPANIES = [
    "Northbridge Financial", "Helix Health", "Crestline Insurance", "Bluewater Retail", "Orbital Telecom",
    "Summit Mortgage Group", "Keystone Bank", "Vantage Logistics", "Pioneer Pharma", "Lumen Analytics",
    "Atlas SaaS", "Federal Data Partners", "Meridian Capital", "Cobalt Commerce", "Granite Health Systems",
]
SOURCES = ["External Portal", "Simulated LinkedIn", "Simulated LinkedIn", "Job Board"]

# Each archetype: titles, the skills almost everyone in that role has, optional skills, and
# summary highlights. Generated people get all/most "core" plus a random sample of "optional".
ARCHETYPES: dict[str, dict] = {
    "genai": {
        "titles": ["Generative AI Engineer", "Senior Generative AI Engineer", "LLM Engineer",
                   "AI Engineer", "Staff AI Engineer", "Applied AI Engineer"],
        "core": ["Python", "LLMs", "RAG", "LangChain", "Prompt Engineering", "Vector Databases"],
        "optional": ["LangGraph", "LlamaIndex", "OpenAI API", "Anthropic Claude", "Hugging Face",
                     "FastAPI", "AWS Bedrock", "Azure OpenAI", "Pinecone", "pgvector", "FAISS",
                     "Docker", "Kubernetes", "MLflow", "LangSmith", "Fine-tuning", "LoRA",
                     "RAGAS", "PyTorch", "AI Agents", "Guardrails", "AWS", "Azure", "SQL"],
        "highlights": [
            "built a retrieval augmented generation assistant over {n}k internal policy documents",
            "shipped a multi-agent workflow that cut manual review time by {p}%",
            "designed LLM evaluation harnesses with golden datasets and regression gates",
            "moved prompt-based prototypes into production APIs serving {n}k requests a day",
            "reduced hallucination rates by {p}% with hybrid search and reranking",
            "led fine-tuning of open models for domain-specific document extraction",
        ],
    },
    "ml": {
        "titles": ["Machine Learning Engineer", "Senior Machine Learning Engineer", "MLOps Engineer",
                   "ML Platform Engineer"],
        "core": ["Python", "Machine Learning", "PyTorch", "Scikit-learn", "MLOps", "Docker"],
        "optional": ["TensorFlow", "Kubernetes", "MLflow", "Kubeflow", "AWS SageMaker", "Airflow",
                     "Feature Stores", "XGBoost", "Spark", "FastAPI", "LLMs", "Hugging Face",
                     "Azure ML", "CI/CD", "SQL", "AWS", "RAG", "LangChain"],
        "highlights": [
            "productionized {n} models with automated retraining and drift monitoring",
            "built a real-time fraud scoring service with p99 latency under {n}ms",
            "cut model training cost by {p}% by moving to spot instances and mixed precision",
            "stood up a feature store shared by {n} data science teams",
        ],
    },
    "ds": {
        "titles": ["Data Scientist", "Senior Data Scientist", "Lead Data Scientist"],
        "core": ["Python", "Machine Learning", "Statistics", "SQL", "Pandas"],
        "optional": ["Scikit-learn", "XGBoost", "NLP", "Time Series Forecasting", "A/B Testing",
                     "Tableau", "Spark", "PyTorch", "LLMs", "Causal Inference", "R", "Databricks",
                     "Hugging Face", "Prompt Engineering"],
        "highlights": [
            "built churn models that improved retention campaigns by {p}%",
            "delivered demand forecasting across {n} product lines",
            "ran experimentation programs covering {n} product launches",
            "applied NLP to classify {n}k customer complaints a month",
        ],
    },
    "de": {
        "titles": ["Data Engineer", "Senior Data Engineer", "Analytics Engineer"],
        "core": ["Python", "SQL", "Spark", "Airflow", "ETL"],
        "optional": ["Databricks", "Snowflake", "dbt", "Kafka", "AWS", "Azure", "Delta Lake",
                     "Terraform", "PostgreSQL", "Docker", "Data Modeling", "GCP", "BigQuery"],
        "highlights": [
            "migrated {n} legacy pipelines to a lakehouse architecture",
            "built streaming ingestion processing {n}M events a day",
            "cut warehouse spend by {p}% through partitioning and incremental models",
        ],
    },
    "backend_py": {
        "titles": ["Backend Engineer", "Senior Python Developer", "Software Engineer (Python)"],
        "core": ["Python", "FastAPI", "PostgreSQL", "REST APIs", "Docker"],
        "optional": ["Django", "Flask", "Redis", "Celery", "AWS", "Kubernetes", "SQLAlchemy",
                     "Pydantic", "GraphQL", "CI/CD", "OpenAI API", "Microservices", "pytest"],
        "highlights": [
            "designed APIs serving {n}k requests a minute",
            "broke a monolith into {n} services with zero downtime",
            "integrated LLM APIs into a customer support product",
        ],
    },
    "nlp": {
        "titles": ["NLP Engineer", "Senior NLP Scientist", "Research Engineer (NLP)"],
        "core": ["Python", "NLP", "PyTorch", "Hugging Face", "Transformers"],
        "optional": ["LLMs", "Fine-tuning", "LoRA", "spaCy", "RAG", "Information Extraction",
                     "Vector Databases", "Prompt Engineering", "LangChain", "Evaluation", "CUDA"],
        "highlights": [
            "published {n} papers on information extraction",
            "trained entity extraction models with {p}% F1 gains over baselines",
            "built multilingual classification for {n} languages",
        ],
    },
    "fullstack": {
        "titles": ["Full Stack Engineer", "Senior Full Stack Developer"],
        "core": ["TypeScript", "React", "Node.js", "REST APIs"],
        "optional": ["Next.js", "Python", "PostgreSQL", "AWS", "Docker", "GraphQL", "Tailwind CSS",
                     "FastAPI", "OpenAI API", "MongoDB"],
        "highlights": ["launched {n} customer-facing features end to end",
                       "built an internal AI chat interface on top of LLM APIs"],
    },
    "frontend": {
        "titles": ["Frontend Engineer", "Senior UI Engineer"],
        "core": ["JavaScript", "TypeScript", "React", "CSS"],
        "optional": ["Next.js", "Redux", "Tailwind CSS", "Accessibility", "Jest", "Figma", "Vue"],
        "highlights": ["rebuilt a design system used by {n} teams",
                       "improved page load times by {p}%"],
    },
    "devops": {
        "titles": ["DevOps Engineer", "Cloud Engineer", "Site Reliability Engineer", "Cloud Architect"],
        "core": ["AWS", "Terraform", "Kubernetes", "CI/CD", "Linux"],
        "optional": ["Azure", "GCP", "Docker", "Prometheus", "Grafana", "Python", "Ansible",
                     "Helm", "ArgoCD", "Security"],
        "highlights": ["ran platforms with {p}.9% uptime", "automated {n} environments with IaC"],
    },
    "java": {
        "titles": ["Java Developer", "Senior Java Engineer"],
        "core": ["Java", "Spring Boot", "Microservices", "SQL"],
        "optional": ["Kafka", "AWS", "Kubernetes", "Hibernate", "Oracle", "REST APIs", "Docker"],
        "highlights": ["modernized {n} core banking services", "built event-driven payment flows"],
    },
    "security": {
        "titles": ["Security Engineer", "Cloud Security Engineer"],
        "core": ["Security", "IAM", "Threat Modeling", "AWS"],
        "optional": ["SIEM", "Python", "Penetration Testing", "Zero Trust", "Compliance", "Azure"],
        "highlights": ["led SOC 2 readiness across {n} systems", "built automated threat detections"],
    },
    "pm": {
        "titles": ["AI Product Manager", "Technical Product Manager"],
        "core": ["Product Management", "Roadmapping", "Stakeholder Management"],
        "optional": ["LLMs", "Agile", "SQL", "A/B Testing", "Analytics", "Prompt Engineering"],
        "highlights": ["launched {n} AI features to production", "grew adoption by {p}%"],
    },
    "analyst": {
        "titles": ["Data Analyst", "Senior BI Analyst"],
        "core": ["SQL", "Excel", "Tableau", "Data Analysis"],
        "optional": ["Power BI", "Python", "Statistics", "Looker", "Snowflake"],
        "highlights": ["built {n} executive dashboards", "automated weekly reporting saving {n} hours"],
    },
    "qa": {
        "titles": ["QA Automation Engineer", "SDET"],
        "core": ["Test Automation", "Selenium", "Python"],
        "optional": ["pytest", "Playwright", "CI/CD", "API Testing", "Java"],
        "highlights": ["raised automated coverage to {p}%"],
    },
    "mobile": {
        "titles": ["Mobile Engineer", "iOS Developer"],
        "core": ["Swift", "iOS", "Mobile Development"],
        "optional": ["Kotlin", "React Native", "Firebase", "REST APIs"],
        "highlights": ["shipped apps with {n}k monthly users"],
    },
}

# How many external profiles of each archetype (sums to 100).
EXTERNAL_MIX = {
    "genai": 16, "ml": 12, "ds": 10, "de": 9, "backend_py": 8, "nlp": 5, "fullstack": 6,
    "frontend": 6, "devops": 7, "java": 5, "security": 4, "pm": 4, "analyst": 4, "qa": 2, "mobile": 2,
}


class NamePool:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.used: set[str] = set()

    def next(self) -> str:
        while True:
            name = f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}"
            if name not in self.used:
                self.used.add(name)
                return name


def _seniority_prefix(title: str, years: int) -> str:
    """Make the title's level consistent with years of experience."""
    base = title
    for word in ("Senior ", "Staff ", "Lead ", "Principal "):
        base = base.replace(word, "")
    if "Architect" in base:
        return base
    if years >= 12 and "Engineer" in base:
        return f"Staff {base}"
    if years >= 10 and "Data Scientist" in base:
        return f"Lead {base}"
    if years >= 6:
        return f"Senior {base}"
    return base


def _skills(rng: random.Random, arch: dict, years: int) -> list[str]:
    core = list(arch["core"])
    # Juniors and some mid-levels drop one or two core skills so the funnel has real gaps.
    drop = rng.choice([0, 0, 0, 1, 1, 2]) if years < 8 else rng.choice([0, 0, 0, 1])
    for _ in range(drop):
        if len(core) > 3:
            core.pop(rng.randrange(1, len(core)))  # never drop the first (anchor) skill
    k = min(len(arch["optional"]), rng.randint(3, 6) + years // 3)
    return core + rng.sample(arch["optional"], k)


def _summary(rng: random.Random, arch: dict, title: str, years: int, industry: str) -> str:
    picks = rng.sample(arch["highlights"], min(2, len(arch["highlights"])))
    filled = [h.format(n=rng.randint(3, 400), p=rng.randint(15, 60)) for h in picks]
    return (f"{title} with {years} years of experience in {industry}. "
            f"Recently {filled[0]}" + (f", and {filled[1]}." if len(filled) > 1 else "."))


def make_external(rng: random.Random, names: NamePool, n_total: int) -> list[dict]:
    kinds: list[str] = []
    for kind, count in EXTERNAL_MIX.items():
        kinds.extend([kind] * count)
    while len(kinds) < n_total:
        kinds.append(rng.choice(list(EXTERNAL_MIX)))
    kinds = kinds[:n_total]
    rng.shuffle(kinds)

    people = []
    for i, kind in enumerate(kinds, start=1):
        arch = ARCHETYPES[kind]
        years = rng.choice([2, 3, 4, 5, 5, 6, 6, 7, 8, 8, 9, 10, 11, 12, 14, 16])
        title = _seniority_prefix(rng.choice(arch["titles"]), years)
        industry = rng.choice(INDUSTRIES)
        people.append({
            "id": f"EXT-{i:03d}",
            "name": names.next(),
            "current_title": title,
            "current_company": rng.choice(COMPANIES),
            "skills": _skills(rng, arch, years),
            "years_experience": years,
            "summary": _summary(rng, arch, title, years, industry),
            "industry": industry,
            "location": rng.choice(LOCATIONS),
            "open_to_work": rng.random() < 0.7,
            "source": rng.choice(SOURCES),
        })
    return people


# A few hand-written warm-bench profiles so the internal check has meaningful cases:
# a strong available match, a decent partial match, one still under contract, one not rehire-eligible.
INTERNAL_FIXED = [
    {
        "role": "Senior Generative AI Engineer", "years_experience": 9,
        "skills": ["Python", "LLMs", "RAG", "LangChain", "LangGraph", "Prompt Engineering",
                   "Vector Databases", "pgvector", "FastAPI", "AWS Bedrock", "Docker", "RAGAS"],
        "contract_end_offset_days": -45, "performance_rating": 4.7, "availability_status": "Available",
        "rehire_eligible": True, "location": "Reston, VA",
        "last_project": "Built a RAG assistant over loan servicing guidelines for the underwriting team",
    },
    {
        "role": "Machine Learning Engineer", "years_experience": 7,
        "skills": ["Python", "Machine Learning", "PyTorch", "MLOps", "Docker", "Kubernetes",
                   "LLMs", "Hugging Face", "MLflow", "AWS SageMaker"],
        "contract_end_offset_days": -120, "performance_rating": 4.2,
        "availability_status": "Available from 2026-12-01", "rehire_eligible": True,
        "location": "Remote (US)",
        "last_project": "Productionized document classification models with automated retraining",
    },
    {
        "role": "LLM Engineer", "years_experience": 8,
        "skills": ["Python", "LLMs", "RAG", "LangChain", "LlamaIndex", "Prompt Engineering",
                   "Vector Databases", "Azure OpenAI", "FastAPI"],
        "contract_end_offset_days": 150, "performance_rating": 4.5,
        "availability_status": "On active contract", "rehire_eligible": True,
        "location": "Arlington, VA",
        "last_project": "Currently building an agentic claims triage workflow (contract runs into 2027)",
    },
    {
        "role": "AI Engineer", "years_experience": 6,
        "skills": ["Python", "LLMs", "RAG", "LangChain", "Prompt Engineering", "OpenAI API", "Pinecone"],
        "contract_end_offset_days": -300, "performance_rating": 2.6,
        "availability_status": "Available", "rehire_eligible": False,
        "location": "Dallas, TX",
        "last_project": "Chatbot prototype; contract closed early after missed delivery milestones",
    },
]
INTERNAL_RANDOM_KINDS = ["ml", "ds", "de", "backend_py", "devops", "fullstack", "java", "nlp",
                         "analyst", "security", "ds", "de", "backend_py", "qa", "genai", "frontend"]


def make_internal(rng: random.Random, names: NamePool, n_total: int) -> list[dict]:
    people = []
    for i, fixed in enumerate(INTERNAL_FIXED, start=1):
        rec = dict(fixed)
        offset = rec.pop("contract_end_offset_days")
        people.append({"id": f"INT-{i:03d}", "name": names.next(), **rec,
                       "past_contract_end_date": (TODAY + timedelta(days=offset)).isoformat()})

    for i in range(len(INTERNAL_FIXED) + 1, n_total + 1):
        kind = INTERNAL_RANDOM_KINDS[(i - len(INTERNAL_FIXED) - 1) % len(INTERNAL_RANDOM_KINDS)]
        arch = ARCHETYPES[kind]
        years = rng.randint(3, 15)
        role = _seniority_prefix(rng.choice(arch["titles"]), years)
        offset = rng.choice([-700, -400, -250, -150, -120, -90, -60, -30, 90, 200])
        ended = offset < 0
        status = (rng.choice(["Available", "Available", "Available", "Available from 2026-12-15",
                              "Not available", "Available from 2027-02-01"])
                  if ended else "On active contract")
        people.append({
            "id": f"INT-{i:03d}",
            "name": names.next(),
            "role": role,
            "skills": _skills(rng, arch, years),
            "years_experience": years,
            "past_contract_end_date": (TODAY + timedelta(days=offset)).isoformat(),
            "performance_rating": round(rng.uniform(3.3, 4.9), 1),
            "availability_status": status,
            "rehire_eligible": rng.random() > 0.1,
            "location": rng.choice(LOCATIONS),
            "last_project": _summary(rng, arch, role, years, rng.choice(INDUSTRIES)).split("Recently ")[-1].capitalize(),
        })
    return people


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=22)
    ap.add_argument("--internal", type=int, default=20)
    ap.add_argument("--external", type=int, default=100)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    names = NamePool(rng)
    internal = make_internal(rng, names, args.internal)
    external = make_external(rng, names, args.external)

    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "internal_past_hires.json").write_text(json.dumps(internal, indent=2))
    (DATA_DIR / "external_talent_pool.json").write_text(json.dumps(external, indent=2))
    print(f"Wrote {len(internal)} internal and {len(external)} external profiles to {DATA_DIR}")


if __name__ == "__main__":
    main()
