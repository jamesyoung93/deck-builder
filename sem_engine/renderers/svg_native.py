"""
Native SVG rendering backend.

Generates SVG directly without external tools.
Uses a simple force-directed-ish layout algorithm.
Good for environments without Graphviz/Mermaid installed.
"""

from __future__ import annotations

import math
from pathlib import Path

from ..schema import ProcessModel, NodeType, EdgeType, ViewMode
from .base import BaseRenderer, RenderResult


# Color palette
COLORS = {
    NodeType.PROCESS: ("#EBF5FB", "#2C3E50"),
    NodeType.DECISION: ("#F9E79F", "#7D6608"),
    NodeType.START: ("#27AE60", "#FFFFFF"),
    NodeType.END: ("#C0392B", "#FFFFFF"),
    NodeType.GATE: ("#FAD7A0", "#7E5109"),
    NodeType.SUBPROCESS: ("#D6EAF8", "#1B4F72"),
    NodeType.DATA: ("#D5F5E3", "#1E8449"),
    NodeType.LATENT: ("#E8DAEF", "#6C3483"),
    NodeType.EXTERNAL: ("#FADBD8", "#922B21"),
    NodeType.HUMAN: ("#FCF3CF", "#7D6608"),
    NodeType.MONITOR: ("#E8DAEF", "#6C3483"),
    NodeType.VARIABLE: ("#D5F5E3", "#1E8449"),
}

EDGE_COLORS = {
    EdgeType.FLOW: "#7F8C8D",
    EdgeType.CAUSAL: "#2E86C1",
    EdgeType.FEEDBACK: "#E74C3C",
    EdgeType.CONDITIONAL: "#F39C12",
    EdgeType.DATA_FLOW: "#27AE60",
    EdgeType.ASSOCIATION: "#95A5A6",
    EdgeType.BIDIRECTIONAL: "#2C3E50",
    EdgeType.MODERATION: "#8E44AD",
    EdgeType.MEDIATION: "#16A085",
}


class SVGNativeRenderer(BaseRenderer):
    name = "svg_native"

    def __init__(self, node_width: int = 160, node_height: int = 50,
                 h_spacing: int = 60, v_spacing: int = 80, padding: int = 60, **kwargs):
        self.node_width = node_width
        self.node_height = node_height
        self.h_spacing = h_spacing
        self.v_spacing = v_spacing
        self.padding = padding

    def check_available(self) -> bool:
        return True  # Always available, no external deps

    def get_capabilities(self) -> dict[str, bool]:
        return {
            "subgraphs": True,
            "cycles": True,
            "bidirectional": True,
            "styling": True,
            "labels_on_edges": True,
            "svg_output": True,
            "png_output": False,
        }

    def _compute_layout(self, model: ProcessModel) -> dict[str, tuple[float, float]]:
        """Simple layered layout using topological ordering."""
        positions = {}
        if not model.nodes:
            return positions

        # Build adjacency
        adj: dict[str, list[str]] = {n.id: [] for n in model.nodes}
        in_degree: dict[str, int] = {n.id: 0 for n in model.nodes}
        for e in model.edges:
            if e.source in adj:
                adj[e.source].append(e.target)
            if e.target in in_degree:
                in_degree[e.target] += 1

        # Topological sort with layers
        layers: list[list[str]] = []
        remaining = dict(in_degree)
        visited = set()

        while remaining:
            layer = [n for n, d in remaining.items() if d == 0 and n not in visited]
            if not layer:
                # Cycle detected, just add remaining nodes
                layer = list(remaining.keys())
                for n in layer:
                    visited.add(n)
                layers.append(layer)
                break
            layers.append(layer)
            for n in layer:
                visited.add(n)
                del remaining[n]
                for tgt in adj.get(n, []):
                    if tgt in remaining:
                        remaining[tgt] -= 1

        # Assign positions
        for layer_idx, layer in enumerate(layers):
            total_width = len(layer) * (self.node_width + self.h_spacing) - self.h_spacing
            start_x = -total_width / 2
            for node_idx, node_id in enumerate(layer):
                x = start_x + node_idx * (self.node_width + self.h_spacing) + self.node_width / 2
                y = layer_idx * (self.node_height + self.v_spacing) + self.node_height / 2
                positions[node_id] = (x, y)

        return positions

    def _wrap_text(self, text: str, max_chars: int = 22) -> list[str]:
        if len(text) <= max_chars:
            return [text]
        words = text.split()
        lines = []
        current = ""
        for word in words:
            if current and len(current) + len(word) + 1 > max_chars:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}" if current else word
        if current:
            lines.append(current)
        return lines

    def generate_source(self, model: ProcessModel) -> str:
        return self._generate_svg(model)

    def _generate_svg(self, model: ProcessModel) -> str:
        positions = self._compute_layout(model)
        if not positions:
            return '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><text x="10" y="50">Empty model</text></svg>'

        # Calculate canvas bounds
        min_x = min(x for x, y in positions.values()) - self.node_width / 2 - self.padding
        max_x = max(x for x, y in positions.values()) + self.node_width / 2 + self.padding
        min_y = min(y for x, y in positions.values()) - self.node_height / 2 - self.padding
        max_y = max(y for x, y in positions.values()) + self.node_height / 2 + self.padding

        width = max_x - min_x
        height = max_y - min_y

        svg = []
        svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="{min_x:.0f} {min_y:.0f} {width:.0f} {height:.0f}">')
        svg.append('<defs>')
        svg.append('  <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">')
        svg.append('    <polygon points="0 0, 10 3.5, 0 7" fill="#7F8C8D" />')
        svg.append('  </marker>')
        svg.append('  <marker id="arrowhead-causal" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">')
        svg.append('    <polygon points="0 0, 10 3.5, 0 7" fill="#2E86C1" />')
        svg.append('  </marker>')
        svg.append('  <marker id="arrowhead-feedback" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">')
        svg.append('    <polygon points="0 0, 10 3.5, 0 7" fill="#E74C3C" />')
        svg.append('  </marker>')
        svg.append('</defs>')
        svg.append(f'<rect x="{min_x:.0f}" y="{min_y:.0f}" width="{width:.0f}" height="{height:.0f}" fill="white"/>')

        # Draw groups (background rectangles)
        for group in model.groups:
            group_nodes = model.get_nodes_in_group(group.id)
            if not group_nodes:
                continue
            gpositions = [positions[n.id] for n in group_nodes if n.id in positions]
            if not gpositions:
                continue
            gx1 = min(x for x, y in gpositions) - self.node_width / 2 - 15
            gy1 = min(y for x, y in gpositions) - self.node_height / 2 - 30
            gx2 = max(x for x, y in gpositions) + self.node_width / 2 + 15
            gy2 = max(y for x, y in gpositions) + self.node_height / 2 + 15
            svg.append(f'<rect x="{gx1:.0f}" y="{gy1:.0f}" width="{gx2-gx1:.0f}" height="{gy2-gy1:.0f}" rx="8" fill="#FAFAFA" stroke="#85929E" stroke-dasharray="5,5"/>')
            svg.append(f'<text x="{gx1+8:.0f}" y="{gy1+16:.0f}" font-family="Helvetica,Arial,sans-serif" font-size="11" fill="#5D6D7E">{self._esc(group.label)}</text>')

        # Draw edges
        for edge in model.edges:
            if edge.source not in positions or edge.target not in positions:
                continue
            sx, sy = positions[edge.source]
            tx, ty = positions[edge.target]

            color = EDGE_COLORS.get(edge.edge_type, "#7F8C8D")
            dash = ""
            if edge.edge_type in (EdgeType.FEEDBACK, EdgeType.CONDITIONAL, EdgeType.DATA_FLOW):
                dash = ' stroke-dasharray="6,3"'
            elif edge.edge_type == EdgeType.ASSOCIATION:
                dash = ' stroke-dasharray="4,4"'

            marker = "arrowhead"
            if edge.edge_type == EdgeType.CAUSAL:
                marker = "arrowhead-causal"
            elif edge.edge_type == EdgeType.FEEDBACK:
                marker = "arrowhead-feedback"

            # Adjust start/end to node borders
            sy_end = sy + self.node_height / 2
            ty_start = ty - self.node_height / 2

            if abs(ty - sy) < self.node_height:
                # Horizontal-ish edge
                sx_end = sx + self.node_width / 2
                tx_start = tx - self.node_width / 2
                svg.append(f'<line x1="{sx_end:.0f}" y1="{sy:.0f}" x2="{tx_start:.0f}" y2="{ty:.0f}" stroke="{color}" stroke-width="1.5"{dash} marker-end="url(#{marker})"/>')
            else:
                svg.append(f'<line x1="{sx:.0f}" y1="{sy_end:.0f}" x2="{tx:.0f}" y2="{ty_start:.0f}" stroke="{color}" stroke-width="1.5"{dash} marker-end="url(#{marker})"/>')

            if edge.label:
                mx, my = (sx + tx) / 2, (sy_end + ty_start) / 2 - 5
                svg.append(f'<text x="{mx:.0f}" y="{my:.0f}" font-family="Helvetica,Arial,sans-serif" font-size="9" fill="{color}" text-anchor="middle">{self._esc(edge.label)}</text>')

        # Draw nodes
        for node in model.nodes:
            if node.id not in positions:
                continue
            x, y = positions[node.id]
            fill, text_color = COLORS.get(node.node_type, ("#EBF5FB", "#2C3E50"))

            rx = x - self.node_width / 2
            ry = y - self.node_height / 2

            if node.node_type == NodeType.DECISION:
                # Diamond shape
                cx, cy = x, y
                hw, hh = self.node_width / 2, self.node_height / 2
                points = f"{cx},{cy-hh} {cx+hw},{cy} {cx},{cy+hh} {cx-hw},{cy}"
                svg.append(f'<polygon points="{points}" fill="{fill}" stroke="#2C3E50" stroke-width="1.5"/>')
            elif node.node_type in (NodeType.START, NodeType.END, NodeType.LATENT, NodeType.VARIABLE):
                # Ellipse
                svg.append(f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{self.node_width/2:.0f}" ry="{self.node_height/2:.0f}" fill="{fill}" stroke="#2C3E50" stroke-width="1.5"/>')
            elif node.node_type == NodeType.DATA:
                # Cylinder approximation
                svg.append(f'<rect x="{rx:.0f}" y="{ry+5:.0f}" width="{self.node_width:.0f}" height="{self.node_height-10:.0f}" fill="{fill}" stroke="#2C3E50" stroke-width="1.5" rx="3"/>')
                svg.append(f'<ellipse cx="{x:.0f}" cy="{ry+5:.0f}" rx="{self.node_width/2:.0f}" ry="5" fill="{fill}" stroke="#2C3E50" stroke-width="1.5"/>')
            else:
                # Rectangle
                svg.append(f'<rect x="{rx:.0f}" y="{ry:.0f}" width="{self.node_width:.0f}" height="{self.node_height:.0f}" rx="6" fill="{fill}" stroke="#2C3E50" stroke-width="1.5"/>')

            # Label text
            lines = self._wrap_text(node.label)
            line_height = 14
            start_y = y - (len(lines) - 1) * line_height / 2
            for i, line in enumerate(lines):
                ty = start_y + i * line_height
                svg.append(f'<text x="{x:.0f}" y="{ty:.0f}" font-family="Helvetica,Arial,sans-serif" font-size="10" fill="{text_color}" text-anchor="middle" dominant-baseline="middle">{self._esc(line)}</text>')

        svg.append('</svg>')
        return '\n'.join(svg)

    def _esc(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def render(self, model: ProcessModel, output_dir: Path, base_name: str = "diagram") -> RenderResult:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        source = self._generate_svg(model)
        svg_path = output_dir / f"{base_name}.svg"
        svg_path.write_text(source, encoding="utf-8")

        return RenderResult(
            success=True,
            source_code=source,
            source_path=svg_path,
            output_path=svg_path,
            output_format="svg",
            renderer_name=self.name,
        )
