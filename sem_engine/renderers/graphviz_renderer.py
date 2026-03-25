"""Graphviz / DOT rendering backend."""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

from ..schema import ProcessModel, NodeType, EdgeType, ViewMode
from .base import BaseRenderer, RenderResult


# Shape mapping
NODE_SHAPES = {
    NodeType.PROCESS: "box",
    NodeType.DECISION: "diamond",
    NodeType.START: "oval",
    NodeType.END: "doubleoctagon",
    NodeType.GATE: "house",
    NodeType.SUBPROCESS: "box3d",
    NodeType.DATA: "cylinder",
    NodeType.LATENT: "ellipse",
    NodeType.EXTERNAL: "component",
    NodeType.HUMAN: "tab",
    NodeType.MONITOR: "hexagon",
    NodeType.VARIABLE: "ellipse",
}

EDGE_STYLES = {
    EdgeType.FLOW: {"style": "solid", "arrowhead": "normal"},
    EdgeType.CAUSAL: {"style": "bold", "arrowhead": "vee", "color": "#2E86C1"},
    EdgeType.FEEDBACK: {"style": "dashed", "arrowhead": "normal", "color": "#E74C3C", "constraint": "false"},
    EdgeType.CONDITIONAL: {"style": "dashed", "arrowhead": "normal", "color": "#F39C12"},
    EdgeType.DATA_FLOW: {"style": "dotted", "arrowhead": "normal", "color": "#27AE60"},
    EdgeType.ASSOCIATION: {"style": "dashed", "arrowhead": "none", "dir": "none"},
    EdgeType.BIDIRECTIONAL: {"style": "solid", "arrowhead": "normal", "dir": "both"},
    EdgeType.MODERATION: {"style": "dashed", "arrowhead": "diamond", "color": "#8E44AD"},
    EdgeType.MEDIATION: {"style": "bold", "arrowhead": "vee", "color": "#16A085"},
}


class GraphvizRenderer(BaseRenderer):
    name = "graphviz"

    def __init__(self, engine: str = "dot", **kwargs):
        self.engine = engine  # dot, neato, fdp, sfdp, circo, twopi

    def check_available(self) -> bool:
        return shutil.which("dot") is not None

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

    def _wrap_label(self, label: str, max_len: int = 25) -> str:
        """Wrap long labels for better readability."""
        if len(label) <= max_len:
            return label
        words = label.split()
        lines = []
        current = ""
        for word in words:
            if current and len(current) + len(word) + 1 > max_len:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}" if current else word
        if current:
            lines.append(current)
        return "\\n".join(lines)

    def generate_source(self, model: ProcessModel) -> str:
        lines = []
        direction = "TB" if model.view_mode in (ViewMode.PROCESS_FLOW, ViewMode.EXECUTIVE_SUMMARY) else "LR"

        lines.append(f'digraph "{model.name}" {{')
        lines.append(f'    rankdir={direction};')
        lines.append('    graph [fontname="Helvetica", fontsize=12, pad="0.5", nodesep=0.6, ranksep=0.8];')
        lines.append('    node [fontname="Helvetica", fontsize=10, style="filled,rounded", fillcolor="#EBF5FB", color="#2C3E50", penwidth=1.5];')
        lines.append('    edge [fontname="Helvetica", fontsize=9, color="#7F8C8D"];')
        lines.append('')

        # Groups as subgraphs
        grouped_nodes = set()
        for group in model.groups:
            nodes_in_group = model.get_nodes_in_group(group.id)
            if nodes_in_group:
                lines.append(f'    subgraph "cluster_{group.id}" {{')
                lines.append(f'        label="{self._wrap_label(group.label)}";')
                lines.append('        style="rounded,dashed";')
                lines.append('        color="#85929E";')
                lines.append('        bgcolor="#FAFAFA";')
                lines.append('        fontsize=11;')
                for node in nodes_in_group:
                    self._write_node(lines, node, indent=8)
                    grouped_nodes.add(node.id)
                lines.append('    }')
                lines.append('')

        # Ungrouped nodes
        for node in model.nodes:
            if node.id not in grouped_nodes:
                self._write_node(lines, node, indent=4)

        lines.append('')

        # Edges
        for edge in model.edges:
            self._write_edge(lines, edge)

        lines.append('}')
        return '\n'.join(lines)

    def _write_node(self, lines: list[str], node, indent: int = 4):
        shape = NODE_SHAPES.get(node.node_type, "box")
        attrs = [f'shape={shape}']
        attrs.append(f'label="{self._wrap_label(node.label)}"')

        # Type-specific styling
        if node.node_type == NodeType.START:
            attrs.append('fillcolor="#27AE60"')
            attrs.append('fontcolor="white"')
        elif node.node_type == NodeType.END:
            attrs.append('fillcolor="#C0392B"')
            attrs.append('fontcolor="white"')
        elif node.node_type == NodeType.DECISION:
            attrs.append('fillcolor="#F9E79F"')
        elif node.node_type == NodeType.GATE:
            attrs.append('fillcolor="#FAD7A0"')
        elif node.node_type == NodeType.LATENT:
            attrs.append('style="filled,dashed"')
            attrs.append('fillcolor="#D5F5E3"')
        elif node.node_type == NodeType.SUBPROCESS:
            attrs.append('fillcolor="#D6EAF8"')
        elif node.node_type == NodeType.HUMAN:
            attrs.append('fillcolor="#FADBD8"')
        elif node.node_type == NodeType.MONITOR:
            attrs.append('fillcolor="#E8DAEF"')

        if node.style:
            if node.style.fill_color:
                attrs.append(f'fillcolor="{node.style.fill_color}"')
            if node.style.border_color:
                attrs.append(f'color="{node.style.border_color}"')

        pad = ' ' * indent
        lines.append(f'{pad}"{node.id}" [{", ".join(attrs)}];')

    def _write_edge(self, lines: list[str], edge):
        style_attrs = EDGE_STYLES.get(edge.edge_type, {}).copy()
        attrs = []

        for k, v in style_attrs.items():
            attrs.append(f'{k}="{v}"')

        if edge.label:
            attrs.append(f'label="{self._wrap_label(edge.label, 20)}"')

        if edge.style:
            if edge.style.color:
                attrs.append(f'color="{edge.style.color}"')
            if edge.style.line_style:
                attrs.append(f'style="{edge.style.line_style}"')

        attr_str = f' [{", ".join(attrs)}]' if attrs else ''
        lines.append(f'    "{edge.source}" -> "{edge.target}"{attr_str};')

    def render(self, model: ProcessModel, output_dir: Path, base_name: str = "diagram") -> RenderResult:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        source = self.generate_source(model)
        source_path = output_dir / f"{base_name}.dot"
        source_path.write_text(source, encoding="utf-8")

        result = RenderResult(
            success=False,
            source_code=source,
            source_path=source_path,
            renderer_name=self.name,
        )

        if not self.check_available():
            result.errors.append("Graphviz 'dot' not found in PATH")
            return result

        # Render SVG
        svg_path = output_dir / f"{base_name}.svg"
        try:
            proc = subprocess.run(
                ["dot", f"-K{self.engine}", "-Tsvg", str(source_path), "-o", str(svg_path)],
                capture_output=True, text=True, timeout=30,
            )
            if proc.returncode != 0:
                result.errors.append(f"dot stderr: {proc.stderr.strip()}")
                return result

            result.success = True
            result.output_path = svg_path
            result.output_format = "svg"
        except Exception as e:
            result.errors.append(str(e))

        return result
