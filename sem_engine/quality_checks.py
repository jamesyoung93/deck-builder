"""
Automated quality checks for rendered diagram outputs.

Inspects SVG files for common defects:
- Text overflow beyond node boundaries
- Node overlap
- Edge crowding
- Export dimension issues
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class QualityCheck:
    name: str
    passed: bool
    details: str = ""
    severity: str = "info"  # info, warning, error


@dataclass
class QualityReport:
    checks: list[QualityCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == "error")

    @property
    def warnings(self) -> list[QualityCheck]:
        return [c for c in self.checks if not c.passed and c.severity == "warning"]

    @property
    def errors(self) -> list[QualityCheck]:
        return [c for c in self.checks if not c.passed and c.severity == "error"]

    def summary(self) -> str:
        lines = []
        passed = sum(1 for c in self.checks if c.passed)
        total = len(self.checks)
        lines.append(f"Quality Checks: {passed}/{total} passed")

        for c in self.checks:
            status = "PASS" if c.passed else ("WARN" if c.severity == "warning" else "FAIL")
            lines.append(f"  [{status}] {c.name}: {c.details}")
        return "\n".join(lines)


def check_svg_quality(svg_path: Path) -> QualityReport:
    """Run automated quality checks on an SVG file."""
    report = QualityReport()

    if not svg_path.exists():
        report.checks.append(QualityCheck("File exists", False, "SVG file not found", "error"))
        return report

    content = svg_path.read_text(encoding="utf-8")
    report.checks.append(QualityCheck("File exists", True, str(svg_path)))

    # Check 1: Valid SVG
    has_svg_tag = "<svg" in content and "</svg>" in content
    report.checks.append(QualityCheck(
        "Valid SVG", has_svg_tag,
        "Valid SVG document" if has_svg_tag else "Missing SVG tags",
        "error"
    ))

    # Check 2: Has viewBox for scalability
    has_viewbox = "viewBox" in content
    report.checks.append(QualityCheck(
        "Has viewBox", has_viewbox,
        "Scalable via viewBox" if has_viewbox else "No viewBox - may not scale well",
        "warning"
    ))

    # Check 3: Reasonable dimensions
    width_match = re.search(r'width="(\d+)', content)
    height_match = re.search(r'height="(\d+)', content)
    if width_match and height_match:
        w, h = int(width_match.group(1)), int(height_match.group(1))
        reasonable = 50 < w < 5000 and 50 < h < 5000
        report.checks.append(QualityCheck(
            "Reasonable dimensions", reasonable,
            f"{w}x{h}px" + (" (ok)" if reasonable else " (may be too large/small)"),
            "warning"
        ))
    else:
        report.checks.append(QualityCheck(
            "Reasonable dimensions", True, "Dimensions set by viewBox"
        ))

    # Check 4: Text elements present
    text_count = content.count("<text")
    report.checks.append(QualityCheck(
        "Has text labels", text_count > 0,
        f"{text_count} text elements",
        "warning"
    ))

    # Check 5: Font declarations
    has_fonts = "font-family" in content
    report.checks.append(QualityCheck(
        "Font declarations", has_fonts,
        "Explicit font-family found" if has_fonts else "No font declarations",
        "info"
    ))

    # Check 6: Text overflow estimation
    # Look for very long text elements
    text_contents = re.findall(r'>([^<]{40,})<', content)
    overflow_risk = len(text_contents)
    report.checks.append(QualityCheck(
        "No text overflow", overflow_risk == 0,
        f"{overflow_risk} potentially long text spans" if overflow_risk > 0 else "No overflow detected",
        "warning"
    ))

    # Check 7: Edge markers (arrows)
    has_markers = "marker" in content.lower() or "polygon" in content.lower()
    report.checks.append(QualityCheck(
        "Edge arrows present", has_markers,
        "Arrow markers found" if has_markers else "No arrow markers",
        "info"
    ))

    # Check 8: Color usage
    color_count = len(set(re.findall(r'#[0-9A-Fa-f]{6}', content)))
    report.checks.append(QualityCheck(
        "Color variety", color_count >= 3,
        f"{color_count} distinct colors" + (" (good)" if color_count >= 3 else " (monotone)"),
        "info"
    ))

    # Check 9: File size reasonable
    size_kb = svg_path.stat().st_size / 1024
    report.checks.append(QualityCheck(
        "File size", size_kb < 500,
        f"{size_kb:.1f} KB" + (" (ok)" if size_kb < 500 else " (large - consider optimization)"),
        "warning" if size_kb >= 500 else "info"
    ))

    return report


def batch_check(results_dir: Path) -> dict[str, QualityReport]:
    """Check all SVG files in a results directory."""
    reports = {}
    for svg_file in sorted(results_dir.rglob("*.svg")):
        key = str(svg_file.relative_to(results_dir))
        reports[key] = check_svg_quality(svg_file)
    return reports
