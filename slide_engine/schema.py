"""
Deck and Slide intermediate representation.

This schema defines the structure before rendering to .pptx.
All slide types, content models, and deck metadata live here.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import json, yaml
from pathlib import Path


class SlideType(str, Enum):
    COVER = "cover"
    AGENDA = "agenda"
    SECTION_DIVIDER = "section_divider"
    EXECUTIVE_SUMMARY = "executive_summary"
    ACTION_BULLETS = "action_bullets"
    TWO_COLUMN = "two_column"
    THREE_COLUMN = "three_column"
    DATA_CALLOUT = "data_callout"
    BAR_CHART = "bar_chart"
    PROCESS_FLOW = "process_flow"
    FRAMEWORK = "framework"
    TIMELINE = "timeline"
    QUOTE = "quote"
    CLOSING = "closing"


class StylePreset(str, Enum):
    EXECUTIVE_DARK = "executive_dark"
    CORPORATE_CLEAN = "corporate_clean"
    ACCENT_GREEN = "accent_green"
    NEUTRAL = "neutral"


# ── Content data classes ─────────────────────────────────────────────────


@dataclass
class BulletPoint:
    lead: str              # Bold lead-in phrase
    detail: str = ""       # Supporting detail


@dataclass
class DataCallout:
    value: str             # e.g. "42%", "$1.2B", "3.7x"
    label: str             # e.g. "Revenue growth"
    context: str = ""      # e.g. "vs. 28% industry avg"
    color: str | None = None  # override accent color


@dataclass
class BarItem:
    label: str
    value: float
    highlight: bool = False
    annotation: str = ""


@dataclass
class ColumnContent:
    heading: str
    bullets: list[str] = field(default_factory=list)
    icon: str | None = None   # placeholder icon name


@dataclass
class TimelinePhase:
    label: str
    duration: str = ""
    items: list[str] = field(default_factory=list)
    color: str | None = None


@dataclass
class FrameworkCell:
    label: str
    description: str = ""
    row: int = 0
    col: int = 0


# ── Slide definition ─────────────────────────────────────────────────────


@dataclass
class Slide:
    type: SlideType
    title: str = ""
    subtitle: str = ""
    body: str = ""
    bullets: list[BulletPoint] = field(default_factory=list)
    callouts: list[DataCallout] = field(default_factory=list)
    bars: list[BarItem] = field(default_factory=list)
    columns: list[ColumnContent] = field(default_factory=list)
    phases: list[TimelinePhase] = field(default_factory=list)
    cells: list[FrameworkCell] = field(default_factory=list)
    quote_text: str = ""
    quote_attribution: str = ""
    source: str = ""
    notes: str = ""
    # For process_flow type — passed to sem_engine
    flow_spec: dict | None = None
    flow_image_path: str | None = None
    # Framework axes
    x_axis: str = ""
    y_axis: str = ""
    # Agenda items
    agenda_items: list[str] = field(default_factory=list)
    current_section: int = -1  # highlight active section in agenda


# ── Deck definition ──────────────────────────────────────────────────────


@dataclass
class Deck:
    title: str
    subtitle: str = ""
    date: str = ""
    author: str = ""
    style: StylePreset = StylePreset.NEUTRAL
    slides: list[Slide] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_slide(self, slide: Slide) -> None:
        self.slides.append(slide)

    def title_sequence(self) -> list[str]:
        """Extract just the titles - should read as a coherent story."""
        return [s.title for s in self.slides if s.title]

    def to_dict(self) -> dict:
        def _enum_val(v):
            return v.value if isinstance(v, Enum) else v

        def _dc_dict(obj):
            if hasattr(obj, '__dataclass_fields__'):
                d = {}
                for k in obj.__dataclass_fields__:
                    v = getattr(obj, k)
                    if v is None or v == "" or v == [] or v == {} or v == -1:
                        continue
                    if isinstance(v, list):
                        d[k] = [_dc_dict(i) if hasattr(i, '__dataclass_fields__') else _enum_val(i) for i in v]
                    elif isinstance(v, Enum):
                        d[k] = v.value
                    elif hasattr(v, '__dataclass_fields__'):
                        d[k] = _dc_dict(v)
                    else:
                        d[k] = v
                return d
            return obj

        return _dc_dict(self)

    def to_yaml(self) -> str:
        return yaml.dump({"deck": self.to_dict()}, default_flow_style=False, sort_keys=False)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_yaml(), encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict) -> "Deck":
        d = data.get("deck", data)
        deck = cls(
            title=d["title"],
            subtitle=d.get("subtitle", ""),
            date=d.get("date", ""),
            author=d.get("author", ""),
            style=StylePreset(d.get("style", "neutral")),
        )
        for s in d.get("slides", []):
            slide = Slide(type=SlideType(s["type"]))
            slide.title = s.get("title", "")
            slide.subtitle = s.get("subtitle", "")
            slide.body = s.get("body", "")
            slide.source = s.get("source", "")
            slide.notes = s.get("notes", "")
            slide.quote_text = s.get("quote_text", "")
            slide.quote_attribution = s.get("quote_attribution", "")
            slide.x_axis = s.get("x_axis", "")
            slide.y_axis = s.get("y_axis", "")
            slide.flow_spec = s.get("flow_spec")
            slide.flow_image_path = s.get("flow_image_path")
            slide.agenda_items = s.get("agenda_items", [])
            slide.current_section = s.get("current_section", -1)

            for b in s.get("bullets", []):
                if isinstance(b, dict):
                    slide.bullets.append(BulletPoint(lead=b.get("lead", ""), detail=b.get("detail", "")))
                else:
                    slide.bullets.append(BulletPoint(lead=str(b)))

            for c in s.get("callouts", []):
                slide.callouts.append(DataCallout(
                    value=c["value"], label=c.get("label", ""),
                    context=c.get("context", ""), color=c.get("color")))

            for bar in s.get("bars", []):
                slide.bars.append(BarItem(
                    label=bar["label"], value=bar["value"],
                    highlight=bar.get("highlight", False),
                    annotation=bar.get("annotation", "")))

            for col in s.get("columns", []):
                slide.columns.append(ColumnContent(
                    heading=col["heading"],
                    bullets=col.get("bullets", []),
                    icon=col.get("icon")))

            for ph in s.get("phases", []):
                slide.phases.append(TimelinePhase(
                    label=ph["label"], duration=ph.get("duration", ""),
                    items=ph.get("items", []), color=ph.get("color")))

            for cell in s.get("cells", []):
                slide.cells.append(FrameworkCell(
                    label=cell["label"], description=cell.get("description", ""),
                    row=cell.get("row", 0), col=cell.get("col", 0)))

            deck.add_slide(slide)
        return deck

    @classmethod
    def load(cls, path: str | Path) -> "Deck":
        text = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        return cls.from_dict(data)
