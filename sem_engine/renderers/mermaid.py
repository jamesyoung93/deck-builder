"""Mermaid rendering backend."""

from __future__ import annotations

import subprocess
import shutil
import json
from pathlib import Path

from ..schema import ProcessModel, NodeType, EdgeType, ViewMode
from .base import BaseRenderer, RenderResult


class MermaidRenderer(BaseRenderer):
    name = "mermaid"

    def check_available(self) -> bool:
        return shutil.which("mmdc") is not None

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

    def _sanitize_id(self, node_id: str) -> str:
        return node_id.replace("-", "_").replace(" ", "_")

    def _escape_label(self, label: str) -> str:
        return label.replace('"', "'").replace("<", "&lt;").replace(">", "&gt;")

    def _node_shape(self, node) -> tuple[str, str]:
        """Return open/close bracket pair for mermaid node shape."""
        shapes = {
            NodeType.PROCESS: ("[", "]"),
            NodeType.DECISION: ("{", "}"),
            NodeType.START: ("([", "])"),
            NodeType.END: ("[[", "]]"),
            NodeType.GATE: ("{{", "}}"),
            NodeType.SUBPROCESS: ("[[", "]]"),
            NodeType.DATA: ("[(", ")]"),
            NodeType.LATENT: ("(", ")"),
            NodeType.EXTERNAL: ("[/", "/]"),
            NodeType.HUMAN: ("(", ")"),
            NodeType.MONITOR: ("{{", "}}"),
            NodeType.VARIABLE: ("(", ")"),
        }
        return shapes.get(node.node_type, ("[", "]"))

    def _edge_arrow(self, edge) -> str:
        """Return mermaid arrow syntax."""
        arrows = {
            EdgeType.FLOW: "-->",
            EdgeType.CAUSAL: "==>",
            EdgeType.FEEDBACK: "-.->",
            EdgeType.CONDITIONAL: "-.->",
            EdgeType.DATA_FLOW: "-.->",
            EdgeType.ASSOCIATION: "---",
            EdgeType.BIDIRECTIONAL: "<-->",
            EdgeType.MODERATION: "-.->",
            EdgeType.MEDIATION: "==>",
        }
        return arrows.get(edge.edge_type, "-->")

    def generate_source(self, model: ProcessModel) -> str:
        lines = []
        direction = "TB" if model.view_mode in (ViewMode.PROCESS_FLOW, ViewMode.EXECUTIVE_SUMMARY) else "LR"
        lines.append(f"flowchart {direction}")

        # Group nodes into subgraphs
        grouped = set()
        for group in model.groups:
            nodes_in_group = model.get_nodes_in_group(group.id)
            if nodes_in_group:
                lines.append(f"    subgraph {self._sanitize_id(group.id)}[\"{self._escape_label(group.label)}\"]")
                for node in nodes_in_group:
                    sid = self._sanitize_id(node.id)
                    op, cl = self._node_shape(node)
                    lines.append(f"        {sid}{op}\"{self._escape_label(node.label)}\"{cl}")
                    grouped.add(node.id)
                lines.append("    end")

        # Ungrouped nodes
        for node in model.nodes:
            if node.id not in grouped:
                sid = self._sanitize_id(node.id)
                op, cl = self._node_shape(node)
                lines.append(f"    {sid}{op}\"{self._escape_label(node.label)}\"{cl}")

        # Edges
        for edge in model.edges:
            src = self._sanitize_id(edge.source)
            tgt = self._sanitize_id(edge.target)
            arrow = self._edge_arrow(edge)
            if edge.label:
                lines.append(f"    {src} {arrow}|{self._escape_label(edge.label)}| {tgt}")
            else:
                lines.append(f"    {src} {arrow} {tgt}")

        # Styling
        lines.append("")
        for node in model.nodes:
            sid = self._sanitize_id(node.id)
            if node.node_type == NodeType.START:
                lines.append(f"    style {sid} fill:#27AE60,color:#fff,stroke:#1E8449")
            elif node.node_type == NodeType.END:
                lines.append(f"    style {sid} fill:#C0392B,color:#fff,stroke:#922B21")
            elif node.node_type == NodeType.DECISION:
                lines.append(f"    style {sid} fill:#F9E79F,stroke:#F1C40F")
            elif node.node_type == NodeType.GATE:
                lines.append(f"    style {sid} fill:#FAD7A0,stroke:#E67E22")
            elif node.node_type == NodeType.LATENT:
                lines.append(f"    style {sid} fill:#D5F5E3,stroke:#27AE60,stroke-dasharray: 5 5")

        return "\n".join(lines)

    def render(self, model: ProcessModel, output_dir: Path, base_name: str = "diagram") -> RenderResult:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        source = self.generate_source(model)
        source_path = output_dir / f"{base_name}.mmd"
        source_path.write_text(source, encoding="utf-8")

        result = RenderResult(
            success=False,
            source_code=source,
            source_path=source_path,
            renderer_name=self.name,
        )

        if not self.check_available():
            result.errors.append("Mermaid CLI (mmdc) not found in PATH")
            return result

        svg_path = output_dir / f"{base_name}.svg"

        # Write puppeteer config to avoid sandbox issues on Windows
        puppet_cfg = output_dir / "puppeteer-config.json"
        puppet_cfg.write_text(json.dumps({
            "args": ["--no-sandbox", "--disable-setuid-sandbox"]
        }), encoding="utf-8")

        try:
            # On Windows, mmdc is a .CMD wrapper; use shell=True
            import sys
            use_shell = sys.platform == "win32"
            proc = subprocess.run(
                ["mmdc", "-i", str(source_path), "-o", str(svg_path),
                 "-p", str(puppet_cfg), "--quiet"],
                capture_output=True, text=True, timeout=60, shell=use_shell,
            )
            if proc.returncode != 0:
                result.errors.append(f"mmdc stderr: {proc.stderr.strip()}")
                # Still might have succeeded with warnings
                if svg_path.exists():
                    result.success = True
                    result.output_path = svg_path
                    result.output_format = "svg"
                    result.warnings.append(proc.stderr.strip())
                return result

            result.success = True
            result.output_path = svg_path
            result.output_format = "svg"
        except Exception as e:
            result.errors.append(str(e))

        return result
