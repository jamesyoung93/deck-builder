"""
Discriminator / Critic module.

Inspects candidate diagram artifacts, scores them against the rubric,
identifies concrete defects, and recommends targeted revisions.
Compares candidates side by side.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .schema import ProcessModel
from .scorer import DiagramScorer, QualityScore
from .renderers.base import RenderResult


@dataclass
class CandidateArtifact:
    """A rendered diagram candidate for evaluation."""
    model: ProcessModel
    render_result: RenderResult
    score: QualityScore | None = None
    rank: int = 0
    verdict: str = ""          # keep / reject / refine
    revision_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "renderer": self.render_result.renderer_name,
            "success": self.render_result.success,
            "score": self.score.to_dict() if self.score else None,
            "rank": self.rank,
            "verdict": self.verdict,
            "revision_notes": self.revision_notes,
            "source_path": str(self.render_result.source_path) if self.render_result.source_path else None,
            "output_path": str(self.render_result.output_path) if self.render_result.output_path else None,
        }


@dataclass
class ComparisonReport:
    """Side-by-side comparison of multiple candidates."""
    case_name: str
    candidates: list[CandidateArtifact] = field(default_factory=list)
    best_candidate: CandidateArtifact | None = None
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "case_name": self.case_name,
            "candidates": [c.to_dict() for c in self.candidates],
            "best_renderer": self.best_candidate.render_result.renderer_name if self.best_candidate else None,
            "best_score": self.best_candidate.score.total if self.best_candidate and self.best_candidate.score else 0,
            "summary": self.summary,
        }


class Discriminator:
    """
    Evaluates and compares diagram candidates.

    Responsibilities:
    - Score candidates against rubric
    - Identify concrete defects
    - Recommend targeted revisions
    - Compare candidates side by side
    - Produce actionable criticism
    """

    def __init__(self):
        self.scorer = DiagramScorer()

    def evaluate(self, model: ProcessModel, render_result: RenderResult) -> CandidateArtifact:
        """Evaluate a single rendered candidate."""
        candidate = CandidateArtifact(model=model, render_result=render_result)

        if not render_result.success:
            candidate.score = QualityScore(
                defects=[f"Render failed: {'; '.join(render_result.errors)}"],
            )
            candidate.verdict = "reject"
            candidate.revision_notes = [f"Fix render: {e}" for e in render_result.errors]
            return candidate

        # Load SVG content if available
        svg_content = None
        if render_result.output_path and render_result.output_path.exists():
            try:
                svg_content = render_result.output_path.read_text(encoding="utf-8")
            except Exception:
                pass

        candidate.score = self.scorer.score(
            model, render_result.source_code, svg_content, render_result.renderer_name
        )

        # Determine verdict
        total = candidate.score.total
        if total >= 7.5:
            candidate.verdict = "keep"
        elif total >= 5.0:
            candidate.verdict = "refine"
        else:
            candidate.verdict = "reject"

        # Generate revision notes from defects and recommendations
        candidate.revision_notes = list(candidate.score.defects) + list(candidate.score.recommendations)

        return candidate

    def compare(self, case_name: str, candidates: list[CandidateArtifact]) -> ComparisonReport:
        """Compare multiple candidates and produce a ranked report."""
        report = ComparisonReport(case_name=case_name)

        # Sort by score
        scored = [c for c in candidates if c.score is not None]
        scored.sort(key=lambda c: c.score.total, reverse=True)

        for i, c in enumerate(scored):
            c.rank = i + 1

        report.candidates = scored

        if scored:
            report.best_candidate = scored[0]

        # Build summary
        lines = [f"Comparison for '{case_name}':"]
        for c in scored:
            status = "+" if c.verdict == "keep" else ("~" if c.verdict == "refine" else "x")
            lines.append(
                f"  {c.rank}. [{status}] {c.render_result.renderer_name}: "
                f"{c.score.total:.1f}/10 - {c.verdict}"
            )
            if c.revision_notes:
                for note in c.revision_notes[:3]:  # Top 3 notes
                    lines.append(f"       -> {note}")

        report.summary = "\n".join(lines)
        return report

    def generate_improvement_plan(self, candidate: CandidateArtifact) -> list[str]:
        """Generate a prioritized list of improvements for a candidate."""
        if not candidate.score:
            return ["Score the candidate first"]

        improvements = []

        # Sort dimensions by score (worst first)
        worst = sorted(candidate.score.dimensions, key=lambda d: d.score)

        for dim in worst[:3]:  # Focus on worst 3
            if dim.score < 5.0:
                improvements.append(f"CRITICAL: Improve {dim.name} (score: {dim.score:.1f}) - {dim.notes}")
            elif dim.score < 7.0:
                improvements.append(f"IMPROVE: {dim.name} (score: {dim.score:.1f}) - {dim.notes}")

        # Add defect-specific improvements
        for defect in candidate.score.defects:
            improvements.append(f"FIX: {defect}")

        return improvements
