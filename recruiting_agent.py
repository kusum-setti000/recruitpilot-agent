"""AI Recruiting Agent: JD in, one recommended hire (with justification) out.

Usage:
    python recruiting_agent.py                     # reads jd.txt
    python recruiting_agent.py --jd path/to/jd.txt
    python recruiting_agent.py --interactive       # paste a JD, finish with an empty line twice
    python recruiting_agent.py --provider mock     # offline run, no API key needed
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read_jd(args) -> str:
    if args.interactive:
        print("Paste the job description. Press Enter twice on an empty line to finish:\n")
        lines, blanks = [], 0
        for line in sys.stdin:
            blanks = blanks + 1 if not line.strip() else 0
            if blanks >= 2:
                break
            lines.append(line.rstrip("\n"))
        text = "\n".join(lines).strip()
    else:
        text = Path(args.jd).read_text().strip()
    if len(text) < 50:
        sys.exit("The job description looks empty or too short.")
    return text


def main() -> None:
    ap = argparse.ArgumentParser(description="AI Recruiting Agent")
    ap.add_argument("--jd", default=str(ROOT / "jd.txt"), help="Path to a job description file")
    ap.add_argument("--interactive", action="store_true", help="Paste the JD into the terminal")
    ap.add_argument("--provider", choices=["auto", "anthropic", "openai", "mock"], help="Override LLM_PROVIDER")
    ap.add_argument("--out", default=str(ROOT / "recruiting_report.md"), help="Markdown report path")
    ap.add_argument("--hide-names", action="store_true", help="Show candidate IDs only in the terminal")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
    logging.basicConfig(level=logging.INFO if args.verbose else logging.ERROR, format="%(levelname)s %(message)s")

    from agent.config import get_settings
    from agent.display import TerminalObserver, console
    from agent.pipeline import RecruitingPipeline
    from agent.report import write_report

    settings = get_settings()
    jd_text = read_jd(args)
    pipeline = RecruitingPipeline(settings, observer=TerminalObserver(show_names=not args.hide_names))
    console.print(f"[bold]AI Recruiting Agent[/]  model: [cyan]{pipeline.llm.label}[/]")
    if settings.llm_provider == "mock":
        from agent.config import looks_like_real_key
        placeholders = [k for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")
                        if os.getenv(k) and not looks_like_real_key(os.getenv(k))]
        if placeholders:
            console.print(f"[yellow]Ignoring {', '.join(placeholders)}: the value looks like a placeholder, "
                          "not a real key.[/]")
        console.print("[yellow]No API key found, running offline with deterministic logic. "
                      "Add ANTHROPIC_API_KEY or OPENAI_API_KEY to .env for live LLM reasoning.[/]")

    result = pipeline.run(jd_text)
    out = write_report(result, Path(args.out))
    console.print(f"\n[bold green]Report saved to {out}[/]")


if __name__ == "__main__":
    main()
