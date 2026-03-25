"""Base renderer interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..schema import ProcessModel


@dataclass
class RenderResult:
    """Result of a rendering operation."""
    success: bool
    source_code: str = ""            # editable source (DOT, mermaid, etc.)
    source_path: Path | None = None  # path to saved source file
    output_path: Path | None = None  # path to rendered output (SVG/PNG)
    output_format: str = "svg"
    renderer_name: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "source_path": str(self.source_path) if self.source_path else None,
            "output_path": str(self.output_path) if self.output_path else None,
            "output_format": self.output_format,
            "renderer_name": self.renderer_name,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


class BaseRenderer(ABC):
    """Abstract base for all rendering backends."""

    name: str = "base"

    @abstractmethod
    def render(self, model: ProcessModel, output_dir: Path, base_name: str = "diagram") -> RenderResult:
        """
        Render a ProcessModel to diagram output.

        Args:
            model: The process model to render
            output_dir: Directory to write output files
            base_name: Base filename (without extension)

        Returns:
            RenderResult with paths to source and output files
        """
        ...

    @abstractmethod
    def generate_source(self, model: ProcessModel) -> str:
        """Generate the backend-specific source code (DOT, mermaid, etc.)."""
        ...

    def check_available(self) -> bool:
        """Check if this renderer's backend tools are available."""
        return True

    def get_capabilities(self) -> dict[str, bool]:
        """Report what this renderer supports."""
        return {
            "subgraphs": False,
            "cycles": False,
            "bidirectional": False,
            "styling": False,
            "labels_on_edges": False,
            "svg_output": False,
            "png_output": False,
        }
