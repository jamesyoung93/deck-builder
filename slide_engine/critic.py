"""
Consulting-quality scoring rubric for generated decks.

Scores on 12 dimensions weighted for consulting standards.
Produces actionable defect lists and improvement recommendations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from .schema import Deck, Slide, SlideType


@dataclass
class ScoreDimension:
    name: str
    score: float        # 0-10
    weight: float
    notes: str = ""


@dataclass
class DeckScore:
    dimensions: list[ScoreDimension] = field(default_factory=list)
    defects: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        if not self.dimensions:
            return 0.0
        weighted = sum(d.score * d.weight for d in self.dimensions)
        total_w = sum(d.weight for d in self.dimensions)
        return round(weighted / total_w, 2)

    @property
    def verdict(self) -> str:
        t = self.total
        if t >= 8.0:
            return "ship_it"
        elif t >= 6.0:
            return "refine"
        return "rework"

    def summary(self) -> str:
        lines = [f"Score: {self.total:.1f}/10 -- {self.verdict.upper()}"]
        lines.append("-" * 55)
        for d in sorted(self.dimensions, key=lambda x: x.score):
            bar = "#" * int(d.score) + "." * (10 - int(d.score))
            lines.append(f"  {d.name:<25} {d.score:>4.1f} ({d.weight:.1f}x) {bar}  {d.notes}")
        if self.defects:
            lines.append("\nDefects:")
            for d in self.defects:
                lines.append(f"  [X] {d}")
        if self.recommendations:
            lines.append("\nRecommendations:")
            for r in self.recommendations:
                lines.append(f"  --> {r}")
        return "\n".join(lines)


class DeckCritic:
    """Scores a Deck against consulting quality standards."""

    def score(self, deck: Deck) -> DeckScore:
        ds = DeckScore()

        ds.dimensions.append(self._score_action_titles(deck))
        ds.dimensions.append(self._score_narrative_flow(deck))
        ds.dimensions.append(self._score_mece(deck))
        ds.dimensions.append(self._score_visual_consistency(deck))
        ds.dimensions.append(self._score_slide_density(deck))
        ds.dimensions.append(self._score_data_presentation(deck))
        ds.dimensions.append(self._score_source_citations(deck))
        ds.dimensions.append(self._score_so_what(deck))
        ds.dimensions.append(self._score_white_space(deck))
        ds.dimensions.append(self._score_alignment(deck))
        ds.dimensions.append(self._score_typography(deck))
        ds.dimensions.append(self._score_slide_count(deck))

        self._collect_defects(deck, ds)
        return ds

    def _score_action_titles(self, deck: Deck) -> ScoreDimension:
        """Every title should be a complete sentence with a takeaway."""
        score = 10.0
        notes = []
        bad_titles = 0

        skip_types = {SlideType.COVER, SlideType.SECTION_DIVIDER, SlideType.CLOSING, SlideType.AGENDA}

        for s in deck.slides:
            if s.type in skip_types:
                continue
            title = s.title.strip()
            if not title:
                bad_titles += 1
                continue
            # Action title heuristics: should be >5 words, contain a verb-like structure
            words = title.split()
            if len(words) < 4:
                bad_titles += 1  # Too short to be an action title
            elif title.endswith("?"):
                pass  # Questions can be ok
            elif not any(c.isupper() for c in title[1:]) and len(words) < 6:
                bad_titles += 1  # Likely a topic label, not an action title

        content_slides = [s for s in deck.slides if s.type not in skip_types]
        if content_slides:
            pct_good = (len(content_slides) - bad_titles) / len(content_slides)
            score = round(pct_good * 10, 1)
            if bad_titles > 0:
                notes.append(f"{bad_titles} weak titles")
        else:
            notes.append("no content slides")

        return ScoreDimension("Action Titles", min(10, score), 2.0,
                            "; ".join(notes) if notes else "strong")

    def _score_narrative_flow(self, deck: Deck) -> ScoreDimension:
        """Title sequence should tell a coherent story."""
        score = 7.0
        notes = []
        titles = deck.title_sequence()

        if len(titles) < 3:
            return ScoreDimension("Narrative Flow", 5.0, 1.5, "too few slides")

        # Check for variety (not all starting the same way)
        first_words = [t.split()[0].lower() if t.split() else "" for t in titles]
        unique_starts = len(set(first_words))
        if unique_starts < len(first_words) * 0.5:
            score -= 2.0
            notes.append("repetitive title starts")

        # Check for logical connectors / progression
        has_structure = any(t.type in (SlideType.SECTION_DIVIDER, SlideType.AGENDA) for t in deck.slides)
        if has_structure:
            score += 1.5
            notes.append("has structural markers")

        # Reasonable title lengths
        avg_len = sum(len(t.split()) for t in titles) / max(1, len(titles))
        if 5 <= avg_len <= 15:
            score += 1.0
        elif avg_len < 4:
            score -= 1.0
            notes.append("titles too short")

        return ScoreDimension("Narrative Flow", max(0, min(10, score)), 1.5,
                            "; ".join(notes) if notes else "coherent")

    def _score_mece(self, deck: Deck) -> ScoreDimension:
        """Check for MECE structure: no obvious overlaps or gaps."""
        score = 7.0
        notes = []

        # Check bullet counts: exec summaries and action slides should have 3-5 bullets
        for s in deck.slides:
            if s.type in (SlideType.EXECUTIVE_SUMMARY, SlideType.ACTION_BULLETS):
                n = len(s.bullets)
                if n < 2:
                    score -= 1.0
                    notes.append(f"too few bullets on '{s.title[:30]}...'")
                elif n > 7:
                    score -= 0.5
                    notes.append(f"too many bullets ({n}) on '{s.title[:30]}...'")
                elif 3 <= n <= 5:
                    score += 0.3  # Sweet spot

        # Check data callouts: should have 2-4 items
        for s in deck.slides:
            if s.type == SlideType.DATA_CALLOUT:
                n = len(s.callouts)
                if n < 2 or n > 5:
                    score -= 0.5

        return ScoreDimension("MECE Structure", max(0, min(10, score)), 1.5,
                            "; ".join(notes) if notes else "balanced")

    def _score_visual_consistency(self, deck: Deck) -> ScoreDimension:
        """All slides should use the same style preset."""
        score = 9.0  # High baseline since we enforce via builder
        notes = []

        # Check slide type variety (should use multiple types)
        types_used = {s.type for s in deck.slides}
        if len(types_used) >= 4:
            score += 1.0
            notes.append(f"{len(types_used)} slide types")
        elif len(types_used) <= 2:
            score -= 2.0
            notes.append("monotone slide types")

        return ScoreDimension("Visual Consistency", max(0, min(10, score)), 1.5,
                            "; ".join(notes) if notes else "consistent")

    def _score_slide_density(self, deck: Deck) -> ScoreDimension:
        """Slides shouldn't be too sparse or too crowded."""
        score = 8.0
        notes = []
        issues = 0

        for s in deck.slides:
            # Count content elements
            elements = len(s.bullets) + len(s.callouts) + len(s.bars) + len(s.columns) + len(s.phases) + len(s.cells)
            if s.body:
                elements += 1
            if s.quote_text:
                elements += 1

            if s.type in (SlideType.COVER, SlideType.SECTION_DIVIDER, SlideType.CLOSING):
                continue

            if elements == 0 and s.type not in (SlideType.PROCESS_FLOW,):
                score -= 1.0
                issues += 1
                notes.append(f"empty: '{s.title[:25]}...'")
            elif elements > 8:
                score -= 0.5
                notes.append(f"crowded: '{s.title[:25]}...'")

        return ScoreDimension("Slide Density", max(0, min(10, score)), 1.0,
                            "; ".join(notes) if notes else "balanced")

    def _score_data_presentation(self, deck: Deck) -> ScoreDimension:
        """Data slides should have clean, labeled visuals."""
        score = 7.0
        notes = []

        data_slides = [s for s in deck.slides
                      if s.type in (SlideType.DATA_CALLOUT, SlideType.BAR_CHART, SlideType.FRAMEWORK)]

        if not data_slides:
            return ScoreDimension("Data Presentation", 6.0, 1.0, "no data slides")

        for s in data_slides:
            if s.type == SlideType.DATA_CALLOUT:
                for c in s.callouts:
                    if c.context:
                        score += 0.3  # Context is good
                    if not c.label:
                        score -= 0.5
            elif s.type == SlideType.BAR_CHART:
                highlighted = sum(1 for b in s.bars if b.highlight)
                if highlighted == 0 and len(s.bars) > 0:
                    score -= 1.0
                    notes.append("no bar highlighted")
                elif highlighted >= 1:
                    score += 0.5

        return ScoreDimension("Data Presentation", max(0, min(10, score)), 1.0,
                            "; ".join(notes) if notes else "clean")

    def _score_source_citations(self, deck: Deck) -> ScoreDimension:
        """Data claims should have sources."""
        score = 7.0
        notes = []

        data_slides = [s for s in deck.slides
                      if s.type in (SlideType.DATA_CALLOUT, SlideType.BAR_CHART)]
        if not data_slides:
            return ScoreDimension("Source Citations", 7.0, 1.0, "no data slides")

        sourced = sum(1 for s in data_slides if s.source)
        if data_slides:
            ratio = sourced / len(data_slides)
            score = 4.0 + ratio * 6.0
            if sourced < len(data_slides):
                notes.append(f"{len(data_slides) - sourced} data slides without source")

        return ScoreDimension("Source Citations", max(0, min(10, score)), 1.0,
                            "; ".join(notes) if notes else "cited")

    def _score_so_what(self, deck: Deck) -> ScoreDimension:
        """Every data point should have explicit implications."""
        score = 7.0
        notes = []

        for s in deck.slides:
            if s.type == SlideType.DATA_CALLOUT:
                for c in s.callouts:
                    if c.context:
                        score += 0.3
                    else:
                        score -= 0.3
                        notes.append(f"callout '{c.value}' lacks context")

        return ScoreDimension("So-What Clarity", max(0, min(10, score)), 1.5,
                            "; ".join(notes[:3]) if notes else "clear")

    def _score_white_space(self, deck: Deck) -> ScoreDimension:
        """Slides should have breathing room."""
        score = 8.0  # High baseline from grid system
        notes = []

        for s in deck.slides:
            total_items = len(s.bullets) + len(s.callouts) + len(s.bars)
            if total_items > 6:
                score -= 0.5

        return ScoreDimension("White Space", max(0, min(10, score)), 1.0,
                            "; ".join(notes) if notes else "adequate")

    def _score_alignment(self, deck: Deck) -> ScoreDimension:
        """Elements should align to grid."""
        # Since we use a grid system, this is inherently good
        return ScoreDimension("Alignment/Grid", 9.0, 1.0, "grid-enforced")

    def _score_typography(self, deck: Deck) -> ScoreDimension:
        """Clear hierarchy, readable sizes."""
        score = 8.0
        notes = []

        # Check for very long titles that might wrap badly
        for s in deck.slides:
            if len(s.title) > 100:
                score -= 0.5
                notes.append(f"long title: '{s.title[:40]}...'")

        return ScoreDimension("Typography", max(0, min(10, score)), 1.0,
                            "; ".join(notes) if notes else "hierarchical")

    def _score_slide_count(self, deck: Deck) -> ScoreDimension:
        """Appropriate depth."""
        n = len(deck.slides)
        if 8 <= n <= 20:
            score = 9.0
            notes = f"{n} slides (ideal range)"
        elif 5 <= n < 8 or 20 < n <= 30:
            score = 7.0
            notes = f"{n} slides (acceptable)"
        elif n < 5:
            score = 4.0
            notes = f"{n} slides (too few)"
        else:
            score = 5.0
            notes = f"{n} slides (too many)"

        return ScoreDimension("Slide Count", score, 0.5, notes)

    def _collect_defects(self, deck: Deck, ds: DeckScore):
        skip = {SlideType.COVER, SlideType.SECTION_DIVIDER, SlideType.CLOSING}

        for s in deck.slides:
            if s.type in skip:
                continue
            if not s.title:
                ds.defects.append(f"Slide {deck.slides.index(s)+1}: missing title")
            elif len(s.title.split()) < 4 and s.type not in (SlideType.AGENDA, SlideType.QUOTE):
                ds.defects.append(f"Slide {deck.slides.index(s)+1}: title too short to be actionable: '{s.title}'")

        if len(deck.slides) > 0 and deck.slides[0].type != SlideType.COVER:
            ds.defects.append("Deck doesn't start with a cover slide")

        if len(deck.slides) > 1 and deck.slides[-1].type not in (SlideType.CLOSING, SlideType.ACTION_BULLETS):
            ds.recommendations.append("Consider ending with a closing/next-steps slide")

        if ds.total < 8.0:
            worst = sorted(ds.dimensions, key=lambda d: d.score)[:3]
            for d in worst:
                if d.score < 7.0:
                    ds.recommendations.append(f"Improve {d.name} (score: {d.score:.1f}): {d.notes}")
