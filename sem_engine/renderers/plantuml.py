"""PlantUML rendering backend."""

from __future__ import annotations

import subprocess
import shutil
import urllib.request
from pathlib import Path

from ..schema import ProcessModel, NodeType, EdgeType, ViewMode
from .base import BaseRenderer, RenderResult

PLANTUML_JAR_URL = "https://github.com/plantuml/plantuml/releases/download/v1.2024.8/plantuml-1.2024.8.jar"


class PlantUMLRenderer(BaseRenderer):
    name = "plantuml"

    def __init__(self, jar_path: str | None = None, **kwargs):
        self.jar_path = Path(jar_path) if jar_path else Path(__file__).parent.parent.parent / "tools" / "plantuml.jar"

    def check_available(self) -> bool:
        if not self.jar_path.exists():
            return False
        return shutil.which("java") is not None

    def ensure_jar(self) -> bool:
        """Download PlantUML jar if not present."""
        if self.jar_path.exists():
            return True
        self.jar_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            urllib.request.urlretrieve(PLANTUML_JAR_URL, str(self.jar_path))
            return True
        except Exception:
            return False

    def get_capabilities(self) -> dict[str, bool]:
        return {
            "subgraphs": True,
            "cycles": True,
            "bidirectional": True,
            "styling": True,
            "labels_on_edges": True,
            "svg_output": True,
            "png_output": True,
        }

    def _edge_str(self, edge) -> str:
        """Build the full arrow string with optional color."""
        color_map = {
            EdgeType.CAUSAL: "#2E86C1",
            EdgeType.FEEDBACK: "#E74C3C",
            EdgeType.CONDITIONAL: "#F39C12",
            EdgeType.DATA_FLOW: "#27AE60",
            EdgeType.MODERATION: "#8E44AD",
            EdgeType.MEDIATION: "#16A085",
        }
        color = color_map.get(edge.edge_type, "")
        color_part = f"[{color}]" if color else ""

        style_map = {
            EdgeType.FLOW: f"-{color_part}->",
            EdgeType.CAUSAL: f"-{color_part}->",
            EdgeType.FEEDBACK: f".{color_part}.>",
            EdgeType.CONDITIONAL: f"-{color_part}->",
            EdgeType.DATA_FLOW: f".{color_part}.>",
            EdgeType.ASSOCIATION: f"-{color_part}-",
            EdgeType.BIDIRECTIONAL: f"<-{color_part}->",
            EdgeType.MODERATION: f".{color_part}.>",
            EdgeType.MEDIATION: f"-{color_part}->",
        }
        return style_map.get(edge.edge_type, f"-{color_part}->")

    def generate_source(self, model: ProcessModel) -> str:
        lines = ["@startuml"]
        lines.append("skinparam defaultFontName Helvetica")
        lines.append("skinparam defaultFontSize 11")
        lines.append("skinparam ActivityBorderColor #2C3E50")
        lines.append("skinparam ActivityBackgroundColor #EBF5FB")
        lines.append("skinparam ArrowColor #7F8C8D")
        lines.append("skinparam RoundCorner 8")

        if model.view_mode in (ViewMode.PROCESS_FLOW, ViewMode.EXECUTIVE_SUMMARY):
            lines.append("top to bottom direction")
        else:
            lines.append("left to right direction")

        lines.append("")

        # Groups as packages/rectangles
        grouped = set()
        for group in model.groups:
            nodes_in_group = model.get_nodes_in_group(group.id)
            if nodes_in_group:
                lines.append(f'package "{group.label}" {{')
                for node in nodes_in_group:
                    self._write_node(lines, node)
                    grouped.add(node.id)
                lines.append("}")
                lines.append("")

        # Ungrouped nodes
        for node in model.nodes:
            if node.id not in grouped:
                self._write_node(lines, node)

        lines.append("")

        # Edges
        for edge in model.edges:
            arrow = self._edge_str(edge)
            label = f" : {edge.label}" if edge.label else ""
            lines.append(f'{edge.source} {arrow} {edge.target}{label}')

        lines.append("@enduml")
        return "\n".join(lines)

    def _write_node(self, lines: list[str], node):
        # PlantUML uses different syntax depending on diagram type
        # For activity/general diagrams, we use rectangle/usecase etc.
        shape_map = {
            NodeType.PROCESS: "rectangle",
            NodeType.DECISION: "hexagon",
            NodeType.START: "usecase",
            NodeType.END: "usecase",
            NodeType.GATE: "rectangle",
            NodeType.SUBPROCESS: "rectangle",
            NodeType.DATA: "storage",
            NodeType.LATENT: "cloud",
            NodeType.EXTERNAL: "component",
            NodeType.HUMAN: "actor",
            NodeType.MONITOR: "rectangle",
            NodeType.VARIABLE: "usecase",
        }
        shape = shape_map.get(node.node_type, "rectangle")
        color = ""
        if node.node_type == NodeType.START:
            color = " #27AE60"
        elif node.node_type == NodeType.END:
            color = " #C0392B"
        elif node.node_type == NodeType.DECISION:
            color = " #F9E79F"
        elif node.node_type == NodeType.GATE:
            color = " #FAD7A0"
        elif node.node_type == NodeType.LATENT:
            color = " #D5F5E3"

        lines.append(f'{shape} "{node.label}" as {node.id}{color}')

    def render(self, model: ProcessModel, output_dir: Path, base_name: str = "diagram") -> RenderResult:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        source = self.generate_source(model)
        source_path = output_dir / f"{base_name}.puml"
        source_path.write_text(source, encoding="utf-8")

        result = RenderResult(
            success=False,
            source_code=source,
            source_path=source_path,
            renderer_name=self.name,
        )

        if not self.ensure_jar():
            result.errors.append("PlantUML jar not available and could not download")
            return result

        if not shutil.which("java"):
            result.errors.append("Java not found in PATH")
            return result

        svg_path = output_dir / f"{base_name}.svg"
        try:
            proc = subprocess.run(
                ["java", "-jar", str(self.jar_path), "-tsvg", str(source_path), "-o", str(output_dir)],
                capture_output=True, text=True, timeout=60,
            )
            if proc.returncode != 0:
                result.errors.append(f"PlantUML stderr: {proc.stderr.strip()}")
                return result

            result.success = True
            result.output_path = svg_path
            result.output_format = "svg"
        except Exception as e:
            result.errors.append(str(e))

        return result
