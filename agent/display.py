"""Live terminal view of the funnel (rich)."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent.pipeline import PipelineResult

console = Console()
WIDE = 110  # below this many columns, tables drop or move the long text columns


def _reqs(reqs) -> str:
    return ", ".join(r.name + (f" ({' / '.join(r.alternatives)})" if r.alternatives else "") for r in reqs) or "none"


class TerminalObserver:
    def __init__(self, show_names: bool = True):
        self.show_names = show_names

    def _name(self, c) -> str:
        return f"{c.name} ({c.id})" if self.show_names else c.id

    def step(self, n: int, r: PipelineResult) -> None:
        getattr(self, f"_step{n}")(r)

    def _step1(self, r: PipelineResult) -> None:
        jd = r.jd
        console.rule("[bold cyan]STEP 1  JD analysis and keyword extraction")
        t = Table.grid(padding=(0, 2))
        t.add_column(style="bold")
        t.add_column()
        t.add_row("Role", f"{jd.job_title}  |  {jd.seniority}  |  {jd.min_years_experience}+ yrs")
        t.add_row("Must-have", _reqs(jd.core_skills))
        t.add_row("Bonus", _reqs(jd.bonus_skills))
        t.add_row("Domain", ", ".join(jd.domain_keywords) or "none stated")
        t.add_row("Title variants", ", ".join(jd.title_variants))
        t.add_row("Work arrangement", jd.work_arrangement or "not stated")
        console.print(t)
        console.print("[bold]Boolean search queries[/]")
        for i, q in enumerate(jd.boolean_queries, 1):
            console.print(f"  Q{i}: [green]{q}[/]")

    def _step2(self, r: PipelineResult) -> None:
        console.rule("[bold cyan]STEP 2  Internal database first (warm bench check)")
        n = len(r.internal_checks)
        excl = [c for c in r.internal_checks if c.status == "excluded"]
        console.print(f"Checked {n} past hires: [green]{len(r.internal_matches)} re-hire matches[/], "
                      f"{len(excl)} excluded by policy, "
                      f"{n - len(excl) - len(r.internal_matches)} eligible but not a fit for this JD")
        if r.internal_matches:
            wide = console.width >= WIDE
            t = Table(title="Internal Re-hire Matches", header_style="bold green")
            cols = ["Candidate", "Role", "Yrs", "Rating", "Score"] + (["Why they fit"] if wide else [])
            for col in cols:
                t.add_column(col, overflow="fold")
            for m in r.internal_matches:
                c = m.candidate
                row = [self._name(c), c.title, str(c.years_experience), f"{c.performance_rating}", f"{m.scored.score}"]
                t.add_row(*(row + ([m.note] if wide else [])))
            console.print(t)
            if not wide:
                for m in r.internal_matches:
                    console.print(f"  [green]{m.candidate.id}[/] {m.note}")
        else:
            console.print("[yellow]No warm-bench match for this JD, moving to the external pool.[/]")
        near = [c for c in excl if c.scored and len(c.scored.matched_core) / max(1, len(r.jd.core_skills)) >= 0.7]
        for c in near:
            console.print(f"  [dim]Skill match but excluded: {self._name(c.candidate)}, {c.reason}[/]")

    def _step3(self, r: PipelineResult) -> None:
        console.rule("[bold cyan]STEP 3  External pool search and Top 10")
        console.print(f"Searched {r.external_pool_size} external profiles.")
        for i, (q, hits) in enumerate(r.query_hits, 1):
            console.print(f"  Q{i} matched [bold]{hits}[/] profiles")
        wide = console.width >= WIDE
        t = Table(title=f"Top {len(r.shortlist)} shortlist (internal + external)", header_style="bold")
        cols = ["#", "Candidate", "Origin"] + (["Title"] if wide else []) + ["Yrs", "Score", "Must", "Missing"]
        for col in cols:
            t.add_column(col, overflow="fold")
        for i, s in enumerate(r.shortlist, 1):
            c = s.candidate
            origin = ("[green]internal[/]" if c.origin == "internal"
                      else c.source if wide else c.source.replace("Simulated ", "").replace("External ", ""))
            name = self._name(c) if wide else c.id
            row = [str(i), name, origin] + ([c.title] if wide else []) + [
                str(c.years_experience), f"{s.score}", f"{len(s.matched_core)}/{len(r.jd.core_skills)}",
                ", ".join(s.missing_core) or "-"]
            t.add_row(*row)
        console.print(t)

    def _step4(self, r: PipelineResult) -> None:
        console.rule("[bold cyan]STEP 4  Deep evaluation, Top 3 finalists")
        ev = r.evals_by_id
        t = Table(header_style="bold")
        for col in ("Rank", "Candidate", "Skills", "Depth", "Domain", "Overall", "Key concern"):
            t.add_column(col, overflow="fold", min_width=8 if col == "Key concern" else None)
        for i, f in enumerate(r.finalists, 1):
            e = ev[f.candidate.id]
            t.add_row(str(i), self._name(f.candidate), f"{e.skill_alignment}/10", f"{e.experience_depth}/10",
                      f"{e.domain_fit}/10", f"[bold]{e.overall}[/]", e.concerns[0])
        console.print(t)
        console.print(f"[dim]{r.evaluation.rationale}[/]")

    def _step5(self, r: PipelineResult) -> None:
        console.rule("[bold cyan]STEP 5  Final selection")
        f = r.final
        c = r.candidate(f.selected_id).candidate
        body = (f"[bold]{self._name(c)}[/]  {f.headline}\nConfidence: {f.confidence}\n\n{f.why_selected}\n\n"
                f"[bold]Experience edge:[/] {f.experience_edge}\n\n[bold]Versus the other finalists[/]\n" +
                "\n".join(f"  {x.candidate_id}: {x.why_not_selected}" for x in f.comparison_to_finalists) +
                f"\n\n[bold]Versus the pool:[/] {f.comparison_to_pool}\n\n[bold]Gaps and risks[/]\n" +
                "\n".join(f"  {g}" for g in f.gaps_and_risks))
        console.print(Panel(body, title="Selected candidate", border_style="green"))
        if r.llm_disabled_reason:
            console.print(f"[red]{r.llm_disabled_reason}[/]")
        if r.fallbacks_used:
            console.print(f"[yellow]Deterministic fallback used for: {', '.join(r.fallbacks_used)}[/]")
