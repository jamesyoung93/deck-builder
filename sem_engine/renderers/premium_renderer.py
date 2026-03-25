"""
Premium diagram renderer — custom SVG with consulting-quality visuals.

Uses Graphviz only for layout computation (node positions),
then draws everything custom in SVG for pixel-perfect control:
- Pill/rounded-rect nodes with gradient fills
- Icons inside nodes
- Curved bezier edge routing
- Labeled edges with background pills
- Subtle glow/shadow effects
- Dark or light backgrounds
- 16:9 optimized proportions
"""

from __future__ import annotations

import json
import math
import subprocess
import shutil
from pathlib import Path

from ..schema import ProcessModel, Node, Edge, Group, NodeType, EdgeType, ViewMode
from .base import BaseRenderer, RenderResult

# ── Color system ─────────────────────────────────────────────────────────

GROUP_PALETTES = [
    {"fill": "#0E3854", "border": "#00A0DC", "label": "#00A0DC"},  # Blue
    {"fill": "#0E3828", "border": "#00B894", "label": "#00B894"},  # Teal
    {"fill": "#1F0E38", "border": "#9B59B6", "label": "#9B59B6"},  # Purple
    {"fill": "#381E0E", "border": "#E67E22", "label": "#E67E22"},  # Orange
    {"fill": "#380E0E", "border": "#E74C3C", "label": "#E74C3C"},  # Red
    {"fill": "#0E2838", "border": "#3498DB", "label": "#3498DB"},  # Sky
]

NODE_STYLES = {
    NodeType.PROCESS:    {"fill": "#1565C0", "text": "#FFFFFF", "glow": "#1565C044"},
    NodeType.SUBPROCESS: {"fill": "#00838F", "text": "#FFFFFF", "glow": "#00838F44"},
    NodeType.DATA:       {"fill": "#6A1B9A", "text": "#FFFFFF", "glow": "#6A1B9A44"},
    NodeType.GATE:       {"fill": "#EF6C00", "text": "#FFFFFF", "glow": "#EF6C0044"},
    NodeType.START:      {"fill": "#2E7D32", "text": "#FFFFFF", "glow": "#2E7D3244"},
    NodeType.END:        {"fill": "#C62828", "text": "#FFFFFF", "glow": "#C6282844"},
    NodeType.EXTERNAL:   {"fill": "#AD1457", "text": "#FFFFFF", "glow": "#AD145744"},
    NodeType.HUMAN:      {"fill": "#00695C", "text": "#FFFFFF", "glow": "#00695C44"},
    NodeType.MONITOR:    {"fill": "#7B1FA2", "text": "#FFFFFF", "glow": "#7B1FA244"},
    NodeType.DECISION:   {"fill": "#F57F17", "text": "#1A1A1A", "glow": "#F57F1744"},
    NodeType.LATENT:     {"fill": "#546E7A", "text": "#FFFFFF", "glow": "#546E7A44"},
    NodeType.VARIABLE:   {"fill": "#1976D2", "text": "#FFFFFF", "glow": "#1976D244"},
}

EDGE_COLORS = {
    EdgeType.FLOW:         "#64B5F6",
    EdgeType.CAUSAL:       "#4FC3F7",
    EdgeType.FEEDBACK:     "#EF5350",
    EdgeType.CONDITIONAL:  "#FFA726",
    EdgeType.DATA_FLOW:    "#66BB6A",
    EdgeType.ASSOCIATION:  "#90A4AE",
    EdgeType.BIDIRECTIONAL:"#64B5F6",
    EdgeType.MODERATION:   "#CE93D8",
    EdgeType.MEDIATION:    "#4DB6AC",
}


class PremiumRenderer(BaseRenderer):
    """Custom SVG renderer for premium diagram quality."""

    name = "premium"

    def __init__(self, bg_color: str = "#0D1B2A", width: int = 1920, height: int = 1080,
                 node_w: int = 190, node_h: int = 65, font_size: int = 14, **kwargs):
        self.bg_color = bg_color
        self.width = width
        self.height = height
        self.node_w = node_w
        self.node_h = node_h
        self.font_size = font_size
        # Detect light mode
        r = int(bg_color[1:3], 16) if bg_color.startswith('#') else 0
        g = int(bg_color[3:5], 16) if bg_color.startswith('#') else 0
        b = int(bg_color[5:7], 16) if bg_color.startswith('#') else 0
        self.light_mode = (r + g + b) / 3 > 128

    def check_available(self) -> bool:
        return shutil.which("dot") is not None

    def get_capabilities(self) -> dict[str, bool]:
        return {"subgraphs": True, "cycles": True, "bidirectional": True,
                "styling": True, "labels_on_edges": True,
                "svg_output": True, "png_output": True}

    def _get_layout(self, model: ProcessModel) -> dict:
        """Use Graphviz to compute node positions, then draw custom."""
        dot = self._make_layout_dot(model)
        try:
            proc = subprocess.run(
                ["dot", "-Tjson"],
                input=dot, capture_output=True, text=True, timeout=15
            )
            if proc.returncode != 0:
                return {}
            return json.loads(proc.stdout)
        except Exception:
            return {}

    def _make_layout_dot(self, model: ProcessModel) -> str:
        """Minimal DOT just for position computation."""
        direction = "LR"
        lines = [f'digraph layout {{',
                 f'  rankdir={direction};',
                 f'  nodesep=1.2; ranksep=1.5;',
                 f'  node [width=2.2, height=0.8, fixedsize=true];']

        # Groups
        for group in model.groups:
            nodes = model.get_nodes_in_group(group.id)
            if nodes:
                lines.append(f'  subgraph "cluster_{group.id}" {{')
                lines.append(f'    margin=30;')
                for n in nodes:
                    lines.append(f'    "{n.id}";')
                lines.append('  }')

        # Ungrouped nodes
        grouped_ids = {n.id for g in model.groups for n in model.get_nodes_in_group(g.id)}
        for n in model.nodes:
            if n.id not in grouped_ids:
                lines.append(f'  "{n.id}";')

        # Edges
        for e in model.edges:
            constraint = "true"
            if e.edge_type == EdgeType.FEEDBACK:
                constraint = "false"
            lines.append(f'  "{e.source}" -> "{e.target}" [constraint={constraint}];')

        lines.append('}')
        return '\n'.join(lines)

    def _parse_positions(self, layout_data: dict) -> tuple[dict, dict, float, float]:
        """Extract node positions and bounding box from Graphviz JSON output."""
        if not layout_data:
            return {}, {}, self.width, self.height

        positions = {}
        clusters = {}

        # Parse bounding box
        bb = layout_data.get("bb", "0,0,1920,1080")
        bb_parts = [float(x) for x in bb.split(",")]
        gv_w = bb_parts[2] - bb_parts[0]
        gv_h = bb_parts[3] - bb_parts[1]

        # Scale to our output dimensions with padding
        pad = 80
        sx = (self.width - 2 * pad) / max(gv_w, 1)
        sy = (self.height - 2 * pad) / max(gv_h, 1)
        scale = min(sx, sy)

        for obj in layout_data.get("objects", []):
            if "nodes" in obj:
                # This is a cluster/subgraph
                name = obj.get("name", "").replace("cluster_", "")
                if "bb" in obj:
                    cbb = [float(x) for x in obj["bb"].split(",")]
                    clusters[name] = {
                        "x": pad + (cbb[0] - bb_parts[0]) * scale,
                        "y": pad + (gv_h - cbb[3] + bb_parts[1]) * scale,
                        "w": (cbb[2] - cbb[0]) * scale,
                        "h": (cbb[3] - cbb[1]) * scale,
                    }
                for node_obj in obj.get("nodes", []):
                    if "pos" in layout_data.get("objects", [{}])[0]:
                        pass  # handled below

        # Parse node positions
        for obj in layout_data.get("objects", []):
            self._extract_nodes(obj, positions, bb_parts, gv_h, scale, pad)

        return positions, clusters, gv_w * scale + 2 * pad, gv_h * scale + 2 * pad

    def _extract_nodes(self, obj, positions, bb_parts, gv_h, scale, pad):
        if "_gvid" in obj and "pos" in obj:
            name = obj.get("name", "")
            pos = obj["pos"].split(",")
            x = pad + (float(pos[0]) - bb_parts[0]) * scale
            y = pad + (gv_h - float(pos[1]) + bb_parts[1]) * scale
            positions[name] = (x, y)

        for sub in obj.get("objects", []):
            self._extract_nodes(sub, positions, bb_parts, gv_h, scale, pad)

        for node in obj.get("nodes", []):
            if isinstance(node, dict) and "pos" in node:
                name = node.get("name", "")
                pos = node["pos"].split(",")
                x = pad + (float(pos[0]) - bb_parts[0]) * scale
                y = pad + (gv_h - float(pos[1]) + bb_parts[1]) * scale
                positions[name] = (x, y)

    def generate_source(self, model: ProcessModel) -> str:
        """Generate premium SVG."""
        layout = self._get_layout(model)
        positions, clusters, canvas_w, canvas_h = self._parse_positions(layout)

        # If layout failed, use simple grid
        if not positions:
            positions = self._grid_layout(model)
            canvas_w, canvas_h = self.width, self.height

        svg = []
        w, h = int(canvas_w), int(canvas_h)
        svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">')

        svg.append('<defs></defs>')

        # Background
        svg.append(f'<rect width="{w}" height="{h}" fill="{self.bg_color}"/>')

        # Draw groups
        group_map = {g.id: g for g in model.groups}
        for gi, group in enumerate(model.groups):
            nodes_in = model.get_nodes_in_group(group.id)
            if not nodes_in:
                continue
            node_positions = [positions[n.id] for n in nodes_in if n.id in positions]
            if not node_positions:
                continue

            palette = GROUP_PALETTES[gi % len(GROUP_PALETTES)]
            min_x = min(p[0] for p in node_positions) - self.node_w * 0.7
            min_y = min(p[1] for p in node_positions) - self.node_h * 1.2
            max_x = max(p[0] for p in node_positions) + self.node_w * 0.7
            max_y = max(p[1] for p in node_positions) + self.node_h * 0.8

            gw = max_x - min_x
            gh = max_y - min_y

            if self.light_mode:
                # Light mode: light fill, darker border
                LIGHT_GROUP_FILLS = ["#E8F4FD", "#E8F8F0", "#F0E8F8", "#FDF0E8", "#FDE8E8", "#E8F0FD"]
                gfill = LIGHT_GROUP_FILLS[gi % len(LIGHT_GROUP_FILLS)]
                svg.append(f'<rect x="{min_x:.0f}" y="{min_y:.0f}" width="{gw:.0f}" height="{gh:.0f}" '
                           f'rx="12" fill="{gfill}" stroke="{palette["border"]}" '
                           f'stroke-width="1.5" opacity="0.9"/>')
            else:
                svg.append(f'<rect x="{min_x:.0f}" y="{min_y:.0f}" width="{gw:.0f}" height="{gh:.0f}" '
                           f'rx="12" fill="{palette["fill"]}" stroke="{palette["border"]}" '
                           f'stroke-width="2" opacity="0.85"/>')

            svg.append(f'<text x="{min_x + 15:.0f}" y="{min_y + 22:.0f}" '
                       f'font-family="Calibri,Helvetica,sans-serif" font-size="14" '
                       f'fill="{palette["label"]}" font-weight="600">{self._esc(group.label)}</text>')

        # Draw edges
        for edge in model.edges:
            self._draw_edge(svg, edge, positions)

        # Draw nodes
        for node in model.nodes:
            if node.id in positions:
                self._draw_node(svg, node, positions[node.id])

        svg.append('</svg>')
        return '\n'.join(svg)

    def _draw_node(self, svg, node: Node, pos: tuple[float, float]):
        x, y = pos
        nw, nh = self.node_w, self.node_h
        rx, ry = x - nw/2, y - nh/2
        style = NODE_STYLES.get(node.node_type, NODE_STYLES[NodeType.PROCESS])

        # Soft glow behind node (simple expanded rect, no filter)
        svg.append(f'<rect x="{rx-4:.0f}" y="{ry-4:.0f}" width="{nw+8:.0f}" height="{nh+8:.0f}" '
                   f'rx="{nh//2+4}" fill="{style["glow"]}" opacity="0.5"/>')

        # Node body — pill shape
        svg.append(f'<rect x="{rx:.0f}" y="{ry:.0f}" width="{nw:.0f}" height="{nh:.0f}" '
                   f'rx="{nh//2}" fill="{style["fill"]}"/>')

        # Subtle border for definition
        svg.append(f'<rect x="{rx:.0f}" y="{ry:.0f}" width="{nw:.0f}" height="{nh:.0f}" '
                   f'rx="{nh//2}" fill="none" stroke="white" stroke-width="0.5" opacity="0.15"/>')

        # Subtle top highlight
        svg.append(f'<rect x="{rx+2:.0f}" y="{ry+1:.0f}" width="{nw-4:.0f}" height="{nh//3:.0f}" '
                   f'rx="{nh//3}" fill="white" opacity="0.1"/>')

        # Label
        label = node.label.replace("\\n", " ")
        lines = self._wrap_text(label, 20)
        line_h = self.font_size + 4
        start_y = y - (len(lines) - 1) * line_h / 2

        for i, line in enumerate(lines):
            ty = start_y + i * line_h
            svg.append(f'<text x="{x:.0f}" y="{ty + 4:.0f}" '
                       f'font-family="Calibri,Helvetica,sans-serif" font-size="{self.font_size}" '
                       f'fill="{style["text"]}" text-anchor="middle" '
                       f'font-weight="600">{self._esc(line)}</text>')

    def _draw_edge(self, svg, edge: Edge, positions: dict):
        if edge.source not in positions or edge.target not in positions:
            return

        sx, sy = positions[edge.source]
        tx, ty = positions[edge.target]
        color = EDGE_COLORS.get(edge.edge_type, "#64B5F6")

        # Adjust start/end to node borders
        dx = tx - sx
        dy = ty - sy
        dist = math.sqrt(dx*dx + dy*dy) or 1
        nx, ny = dx/dist, dy/dist

        # Start from edge of source node
        sx2 = sx + nx * self.node_w * 0.5
        sy2 = sy + ny * self.node_h * 0.5
        # End at edge of target node
        tx2 = tx - nx * self.node_w * 0.5
        ty2 = ty - ny * self.node_h * 0.5

        # Dashed for feedback
        dash = ' stroke-dasharray="8,5"' if edge.edge_type in (EdgeType.FEEDBACK, EdgeType.CONDITIONAL) else ''

        # Bezier curve for non-straight connections
        if abs(dy) > 30 and abs(dx) > 30:
            # Curved path
            mx = (sx2 + tx2) / 2
            my = (sy2 + ty2) / 2
            cx1 = sx2 + dx * 0.3
            cy1 = sy2
            cx2 = tx2 - dx * 0.3
            cy2 = ty2
            svg.append(f'<path d="M{sx2:.0f},{sy2:.0f} C{cx1:.0f},{cy1:.0f} {cx2:.0f},{cy2:.0f} {tx2:.0f},{ty2:.0f}" '
                       f'fill="none" stroke="{color}" stroke-width="2"{dash} opacity="0.8"/>')
        else:
            svg.append(f'<line x1="{sx2:.0f}" y1="{sy2:.0f}" x2="{tx2:.0f}" y2="{ty2:.0f}" '
                       f'stroke="{color}" stroke-width="2"{dash} opacity="0.8"/>')

        # Arrowhead
        angle = math.atan2(ty2 - sy2, tx2 - sx2)
        a1 = angle + 2.7
        a2 = angle - 2.7
        ax1 = tx2 + 12 * math.cos(a1)
        ay1 = ty2 + 12 * math.sin(a1)
        ax2 = tx2 + 12 * math.cos(a2)
        ay2 = ty2 + 12 * math.sin(a2)
        svg.append(f'<polygon points="{tx2:.0f},{ty2:.0f} {ax1:.0f},{ay1:.0f} {ax2:.0f},{ay2:.0f}" '
                   f'fill="{color}" opacity="0.9"/>')

        # Edge label in a pill
        if edge.label:
            label = edge.label.replace("\\n", " ")
            mx = (sx2 + tx2) / 2
            my = (sy2 + ty2) / 2 - 8
            tw = len(label) * 6.5 + 20
            pill_fill = self.bg_color if not self.light_mode else "#FFFFFF"
            svg.append(f'<rect x="{mx - tw/2:.0f}" y="{my - 11:.0f}" width="{tw:.0f}" height="20" '
                       f'rx="10" fill="{pill_fill}" stroke="{color}" stroke-width="1" opacity="0.95"/>')
            svg.append(f'<text x="{mx:.0f}" y="{my + 4:.0f}" '
                       f'font-family="Calibri,Helvetica,sans-serif" font-size="11" '
                       f'fill="{color}" text-anchor="middle" font-weight="500">{self._esc(label)}</text>')

    def _wrap_text(self, text: str, max_chars: int = 20) -> list[str]:
        if len(text) <= max_chars:
            return [text]
        words = text.split()
        lines, cur = [], ""
        for w in words:
            if cur and len(cur) + len(w) + 1 > max_chars:
                lines.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}" if cur else w
        if cur:
            lines.append(cur)
        return lines

    def _esc(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def _grid_layout(self, model: ProcessModel) -> dict:
        """Fallback grid layout if Graphviz fails."""
        positions = {}
        n = len(model.nodes)
        cols = max(int(math.sqrt(n * 2)), 3)
        for i, node in enumerate(model.nodes):
            col = i % cols
            row = i // cols
            x = 120 + col * (self.node_w + 60)
            y = 120 + row * (self.node_h + 80)
            positions[node.id] = (x, y)
        return positions

    def render(self, model: ProcessModel, output_dir: Path, base_name: str = "diagram") -> RenderResult:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        svg_content = self.generate_source(model)
        svg_path = output_dir / f"{base_name}.svg"
        svg_path.write_text(svg_content, encoding="utf-8")

        result = RenderResult(
            success=True,
            source_code=svg_content,
            source_path=svg_path,
            output_path=svg_path,
            output_format="svg",
            renderer_name=self.name,
        )

        # Convert SVG to PNG
        png_path = output_dir / f"{base_name}.png"
        converted = False

        # Try LibreOffice (most reliable on Windows)
        lo_path = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")
        if lo_path.exists():
            try:
                proc = subprocess.run(
                    [str(lo_path), "--headless", "--convert-to", "png",
                     "--outdir", str(output_dir), str(svg_path)],
                    capture_output=True, text=True, timeout=30,
                )
                # LibreOffice outputs to the same dir with .png extension
                lo_png = output_dir / f"{base_name}.png"
                if lo_png.exists() and lo_png.stat().st_size > 1000:
                    converted = True
            except Exception:
                pass

        # Try rsvg-convert
        if not converted and shutil.which("rsvg-convert"):
            try:
                subprocess.run(
                    ["rsvg-convert", "-w", "3840", str(svg_path), "-o", str(png_path)],
                    capture_output=True, timeout=15
                )
                converted = png_path.exists() and png_path.stat().st_size > 1000
            except Exception:
                pass

        # Fallback: Graphviz dark theme for PNG
        if not converted:
            from .dark_theme import DarkThemeRenderer
            dt = DarkThemeRenderer(bg_color=self.bg_color, dpi=300)
            dt_result = dt.render(model, output_dir, f"{base_name}_fallback")
            if dt_result.success and dt_result.output_path:
                import shutil as sh
                sh.copy2(str(dt_result.output_path), str(png_path))
                converted = True

        if converted:
            result.output_path = png_path
            result.output_format = "png"

        return result
