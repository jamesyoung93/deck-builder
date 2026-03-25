"""
Dark-mode diagram rendering for slide embedding.

Optimized for 16:9 widescreen slides:
- Horizontal (LR) layout to fill wide slides
- Large fonts readable at slide scale
- High DPI output (300)
- Generous node padding
- Clean edge routing
"""

from __future__ import annotations
from pathlib import Path
import subprocess
import shutil

from ..schema import ProcessModel, NodeType, EdgeType, ViewMode
from .base import BaseRenderer, RenderResult

GROUP_COLORS = [
    ("#00A0DC", "#0A2A3D"),   # Blue
    ("#00B894", "#0A3D2D"),   # Teal/Green
    ("#8E44AD", "#1F0A3D"),   # Purple
    ("#E67E22", "#3D2210"),   # Orange
    ("#E74C3C", "#3D1212"),   # Red
    ("#3498DB", "#0A2640"),   # Light Blue
    ("#F1C40F", "#3D3510"),   # Gold
]

NODE_COLORS = {
    NodeType.PROCESS:    ("#1E88E5", "#FFFFFF"),
    NodeType.DECISION:   ("#F9A825", "#1A1A1A"),
    NodeType.START:      ("#43A047", "#FFFFFF"),
    NodeType.END:        ("#E53935", "#FFFFFF"),
    NodeType.GATE:       ("#FB8C00", "#FFFFFF"),
    NodeType.SUBPROCESS: ("#00ACC1", "#FFFFFF"),
    NodeType.DATA:       ("#7E57C2", "#FFFFFF"),
    NodeType.LATENT:     ("#78909C", "#FFFFFF"),
    NodeType.EXTERNAL:   ("#EC407A", "#FFFFFF"),
    NodeType.HUMAN:      ("#26A69A", "#FFFFFF"),
    NodeType.MONITOR:    ("#AB47BC", "#FFFFFF"),
    NodeType.VARIABLE:   ("#42A5F5", "#FFFFFF"),
}

EDGE_STYLES = {
    EdgeType.FLOW:         {"color": "#64B5F6", "style": "solid",  "penwidth": "2.0", "arrowhead": "vee", "arrowsize": "1.2"},
    EdgeType.CAUSAL:       {"color": "#4FC3F7", "style": "solid",  "penwidth": "2.5", "arrowhead": "vee", "arrowsize": "1.2"},
    EdgeType.FEEDBACK:     {"color": "#EF5350", "style": "dashed", "penwidth": "2.0", "arrowhead": "vee", "arrowsize": "1.0", "constraint": "false"},
    EdgeType.CONDITIONAL:  {"color": "#FFA726", "style": "dashed", "penwidth": "2.0", "arrowhead": "vee", "arrowsize": "1.0"},
    EdgeType.DATA_FLOW:    {"color": "#66BB6A", "style": "solid",  "penwidth": "2.0", "arrowhead": "vee", "arrowsize": "1.0"},
    EdgeType.ASSOCIATION:  {"color": "#90A4AE", "style": "dashed", "penwidth": "1.5", "arrowhead": "none", "dir": "none"},
    EdgeType.BIDIRECTIONAL:{"color": "#64B5F6", "style": "solid",  "penwidth": "2.0", "arrowhead": "vee", "dir": "both"},
    EdgeType.MODERATION:   {"color": "#CE93D8", "style": "dashed", "penwidth": "2.0", "arrowhead": "diamond"},
    EdgeType.MEDIATION:    {"color": "#4DB6AC", "style": "solid",  "penwidth": "2.5", "arrowhead": "vee"},
}


class DarkThemeRenderer(BaseRenderer):
    name = "dark_theme"

    def __init__(self, bg_color: str = "#0D1B2A", engine: str = "dot",
                 dpi: int = 300, direction: str = "LR", **kwargs):
        self.bg_color = bg_color
        self.engine = engine
        self.dpi = dpi
        self.direction = direction

    def check_available(self) -> bool:
        return shutil.which("dot") is not None

    def get_capabilities(self) -> dict[str, bool]:
        return {"subgraphs": True, "cycles": True, "bidirectional": True,
                "styling": True, "labels_on_edges": True,
                "svg_output": True, "png_output": True}

    def _wrap(self, label: str, max_len: int = 22) -> str:
        if len(label) <= max_len:
            return label
        words = label.split()
        lines, cur = [], ""
        for w in words:
            if cur and len(cur) + len(w) + 1 > max_len:
                lines.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}" if cur else w
        if cur:
            lines.append(cur)
        return "\\n".join(lines)

    def generate_source(self, model: ProcessModel) -> str:
        lines = []
        lines.append(f'digraph "{model.name}" {{')
        lines.append(f'    rankdir={self.direction};')
        lines.append(f'    bgcolor="{self.bg_color}";')
        lines.append(f'    graph [fontname="Calibri,Helvetica,sans-serif", fontsize=16, fontcolor="#B0BEC5",'
                     f' pad="0.6", nodesep=0.8, ranksep=1.0, newrank=true];')
        lines.append(f'    node [fontname="Calibri,Helvetica,sans-serif", fontsize=14, style="filled,rounded",'
                     f' shape=box, penwidth=0, margin="0.25,0.12", height=0.6];')
        lines.append(f'    edge [fontname="Calibri,Helvetica,sans-serif", fontsize=11, fontcolor="#90CAF9"];')
        lines.append('')

        grouped = set()
        for gi, group in enumerate(model.groups):
            nodes_in_group = model.get_nodes_in_group(group.id)
            if not nodes_in_group:
                continue
            accent, bg = GROUP_COLORS[gi % len(GROUP_COLORS)]
            lines.append(f'    subgraph "cluster_{group.id}" {{')
            lines.append(f'        label="{self._wrap(group.label, 28)}";')
            lines.append(f'        style="rounded";')
            lines.append(f'        color="{accent}";')
            lines.append(f'        bgcolor="{bg}";')
            lines.append(f'        fontsize=15;')
            lines.append(f'        fontcolor="{accent}";')
            lines.append(f'        penwidth=2.0;')
            lines.append(f'        margin=20;')
            for node in nodes_in_group:
                self._node(lines, node, 8)
                grouped.add(node.id)
            lines.append('    }')
            lines.append('')

        for node in model.nodes:
            if node.id not in grouped:
                self._node(lines, node, 4)

        lines.append('')
        for edge in model.edges:
            self._edge(lines, edge)

        lines.append('}')
        return '\n'.join(lines)

    def _node(self, lines, node, indent):
        fill, text_color = NODE_COLORS.get(node.node_type, ("#1E88E5", "#FFFFFF"))
        label = self._wrap(node.label, 22)
        attrs = [
            f'label="{label}"',
            f'fillcolor="{fill}"',
            f'fontcolor="{text_color}"',
        ]

        shape_map = {
            NodeType.DECISION: "diamond",
            NodeType.DATA: "cylinder",
            NodeType.START: "oval",
            NodeType.END: "doubleoctagon",
            NodeType.GATE: "hexagon",
            NodeType.SUBPROCESS: "box3d",
            NodeType.EXTERNAL: "component",
            NodeType.HUMAN: "tab",
            NodeType.MONITOR: "hexagon",
            NodeType.LATENT: "ellipse",
        }
        if node.node_type in shape_map:
            attrs.append(f'shape={shape_map[node.node_type]}')
        if node.node_type == NodeType.LATENT:
            attrs.append('style="filled,dashed,rounded"')

        pad = ' ' * indent
        lines.append(f'{pad}"{node.id}" [{", ".join(attrs)}];')

    def _edge(self, lines, edge):
        style = EDGE_STYLES.get(edge.edge_type, EDGE_STYLES[EdgeType.FLOW]).copy()
        attrs = [f'{k}="{v}"' for k, v in style.items()]
        if edge.label:
            attrs.append(f'label="  {self._wrap(edge.label, 18)}  "')
        attr_str = f' [{", ".join(attrs)}]' if attrs else ''
        lines.append(f'    "{edge.source}" -> "{edge.target}"{attr_str};')

    def render(self, model: ProcessModel, output_dir: Path, base_name: str = "diagram") -> RenderResult:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        source = self.generate_source(model)
        dot_path = output_dir / f"{base_name}.dot"
        dot_path.write_text(source, encoding="utf-8")

        result = RenderResult(
            success=False, source_code=source,
            source_path=dot_path, renderer_name=self.name,
        )

        if not self.check_available():
            result.errors.append("Graphviz not found")
            return result

        png_path = output_dir / f"{base_name}.png"
        try:
            proc = subprocess.run(
                ["dot", f"-K{self.engine}", "-Tpng", f"-Gdpi={self.dpi}",
                 str(dot_path), "-o", str(png_path)],
                capture_output=True, text=True, timeout=30,
            )
            if proc.returncode != 0:
                result.errors.append(proc.stderr.strip())
                return result
            result.success = True
            result.output_path = png_path
            result.output_format = "png"
        except Exception as e:
            result.errors.append(str(e))

        # Also SVG
        svg_path = output_dir / f"{base_name}.svg"
        try:
            subprocess.run(
                ["dot", f"-K{self.engine}", "-Tsvg", str(dot_path), "-o", str(svg_path)],
                capture_output=True, text=True, timeout=30,
            )
        except Exception:
            pass

        return result
