"""
Style presets and visual constants.

Defines color palettes, typography, spacing, and grid for each preset.
All measurements in EMU (English Metric Units) or Pt for fonts.
1 inch = 914400 EMU. Standard slide = 13.333" x 7.5" (widescreen 16:9).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor


@dataclass
class ColorPalette:
    primary: str           # Main brand/accent color
    secondary: str         # Secondary accent
    background: str        # Slide background
    title_bg: str          # Title bar background (if distinct)
    title_text: str        # Title text color
    body_text: str         # Body text color
    subtitle_text: str     # Secondary/muted text
    accent_positive: str   # Green/positive
    accent_negative: str   # Red/negative
    accent_neutral: str    # Amber/neutral
    divider_bg: str        # Section divider background
    divider_text: str      # Section divider text
    footer_text: str       # Footer/source text
    border: str            # Lines, borders

    def rgb(self, color_name: str) -> RGBColor:
        hex_str = getattr(self, color_name).lstrip('#')
        return RGBColor(int(hex_str[:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))

    def rgb_hex(self, hex_str: str) -> RGBColor:
        hex_str = hex_str.lstrip('#')
        return RGBColor(int(hex_str[:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))


@dataclass
class Typography:
    title_font: str = "Calibri"
    body_font: str = "Calibri"
    title_size: int = 24          # Pt
    subtitle_size: int = 16
    body_size: int = 12
    bullet_size: int = 11
    callout_value_size: int = 48
    callout_label_size: int = 11
    source_size: int = 8
    footer_size: int = 8
    section_divider_size: int = 36
    quote_size: int = 22
    title_bold: bool = True
    bullet_lead_bold: bool = True


@dataclass
class Grid:
    """Defines the layout grid for consistent alignment."""
    # Slide dimensions (widescreen 16:9)
    slide_width: int = Inches(13.333)
    slide_height: int = Inches(7.5)

    # Margins
    margin_left: int = Inches(0.6)
    margin_right: int = Inches(0.6)
    margin_top: int = Inches(0.4)
    margin_bottom: int = Inches(0.5)

    # Title bar
    title_top: int = Inches(0.3)
    title_left: int = Inches(0.6)
    title_height: int = Inches(0.85)

    # Content area (below title)
    content_top: int = Inches(1.4)
    content_bottom: int = Inches(6.8)

    # Footer
    footer_top: int = Inches(7.0)
    footer_height: int = Inches(0.3)

    @property
    def content_width(self) -> int:
        return self.slide_width - self.margin_left - self.margin_right

    @property
    def content_height(self) -> int:
        return self.content_bottom - self.content_top

    @property
    def title_width(self) -> int:
        return self.slide_width - self.title_left - self.margin_right

    def col_width(self, n_cols: int, gap: int = Inches(0.3)) -> int:
        total_gaps = gap * (n_cols - 1)
        return int((self.content_width - total_gaps) / n_cols)

    def col_left(self, col_index: int, n_cols: int, gap: int = Inches(0.3)) -> int:
        w = self.col_width(n_cols, gap)
        return int(self.margin_left + col_index * (w + gap))


@dataclass
class Style:
    name: str
    colors: ColorPalette
    typography: Typography
    grid: Grid
    # Title bar accent line
    title_accent_line: bool = True
    title_accent_color: str | None = None
    # Dark background mode
    dark_mode: bool = False


# ── Preset definitions ───────────────────────────────────────────────────

EXECUTIVE_DARK = Style(
    name="executive_dark",
    dark_mode=True,
    title_accent_line=False,
    colors=ColorPalette(
        primary="#00A0DC",
        secondary="#1A3A5C",
        background="#0D1B2A",
        title_bg="#0D1B2A",
        title_text="#C8D6E5",
        body_text="#E0E0E0",
        subtitle_text="#7A9CC6",
        accent_positive="#00B894",
        accent_negative="#E74C3C",
        accent_neutral="#FFB81C",
        divider_bg="#0D1B2A",
        divider_text="#00A0DC",
        footer_text="#5A7A9A",
        border="#1E3A5F",
    ),
    typography=Typography(
        title_font="Calibri",
        body_font="Calibri",
        title_size=22,
        body_size=11,
        bullet_size=11,
        subtitle_size=14,
    ),
    grid=Grid(),
)

CORPORATE_CLEAN = Style(
    name="corporate_clean",
    dark_mode=False,
    title_accent_line=True,
    title_accent_color="#CC0000",
    colors=ColorPalette(
        primary="#CC0000",
        secondary="#333333",
        background="#FFFFFF",
        title_bg="#FFFFFF",
        title_text="#333333",
        body_text="#333333",
        subtitle_text="#666666",
        accent_positive="#006B3F",
        accent_negative="#CC0000",
        accent_neutral="#F39C12",
        divider_bg="#CC0000",
        divider_text="#FFFFFF",
        footer_text="#999999",
        border="#CC0000",
    ),
    typography=Typography(
        title_font="Calibri",
        body_font="Calibri",
        title_size=24,
        body_size=12,
    ),
    grid=Grid(),
)

ACCENT_GREEN = Style(
    name="accent_green",
    dark_mode=False,
    title_accent_line=True,
    title_accent_color="#006341",
    colors=ColorPalette(
        primary="#006341",
        secondary="#333333",
        background="#FFFFFF",
        title_bg="#FFFFFF",
        title_text="#333333",
        body_text="#333333",
        subtitle_text="#666666",
        accent_positive="#84BD00",
        accent_negative="#CC0000",
        accent_neutral="#F39C12",
        divider_bg="#006341",
        divider_text="#FFFFFF",
        footer_text="#999999",
        border="#006341",
    ),
    typography=Typography(title_font="Calibri", body_font="Calibri"),
    grid=Grid(),
)

NEUTRAL = Style(
    name="neutral",
    dark_mode=False,
    title_accent_line=True,
    title_accent_color="#2E86C1",
    colors=ColorPalette(
        primary="#1B3A5C",
        secondary="#2E86C1",
        background="#FFFFFF",
        title_bg="#FFFFFF",
        title_text="#2C3E50",
        body_text="#2C3E50",
        subtitle_text="#7F8C8D",
        accent_positive="#27AE60",
        accent_negative="#E74C3C",
        accent_neutral="#F39C12",
        divider_bg="#1B3A5C",
        divider_text="#FFFFFF",
        footer_text="#95A5A6",
        border="#2E86C1",
    ),
    typography=Typography(title_font="Calibri", body_font="Calibri"),
    grid=Grid(),
)

PRESETS = {
    "executive_dark": EXECUTIVE_DARK,
    "corporate_clean": CORPORATE_CLEAN,
    "accent_green": ACCENT_GREEN,
    "neutral": NEUTRAL,
}


def get_style(name: str) -> Style:
    if name not in PRESETS:
        raise ValueError(f"Unknown style: {name}. Available: {list(PRESETS.keys())}")
    return PRESETS[name]
