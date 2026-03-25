"""
Quality scoring rubric for diagram outputs.

Scores diagrams on multiple dimensions, producing numeric scores
that enable objective comparison across toolchains and iterations.
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .schema import ProcessModel, EdgeType, NodeType, ViewMode, CausalRole


@dataclass
class ScoreDimension:
    name: str
    score: float          # 0.0 to 10.0
    weight: float = 1.0
    notes: str = ""


@dataclass
class QualityScore:
    dimensions: list[ScoreDimension] = field(default_factory=list)
    defects: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        if not self.dimensions:
            return 0.0
        weighted = sum(d.score * d.weight for d in self.dimensions)
        total_weight = sum(d.weight for d in self.dimensions)
        return round(weighted / total_weight, 2) if total_weight > 0 else 0.0

    @property
    def max_possible(self) -> float:
        return 10.0

    def summary(self) -> str:
        lines = [f"Overall Score: {self.total:.1f} / {self.max_possible:.1f}"]
        lines.append("-" * 50)
        for d in sorted(self.dimensions, key=lambda x: x.score):
            bar = "#" * int(d.score) + "." * (10 - int(d.score))
            lines.append(f"  {d.name:<30} {d.score:>4.1f}  {bar}  {d.notes}")
        if self.defects:
            lines.append("\nDefects:")
            for d in self.defects:
                lines.append(f"  [X] {d}")
        if self.warnings:
            lines.append("\nWarnings:")
            for w in self.warnings:
                lines.append(f"  [!] {w}")
        if self.recommendations:
            lines.append("\nRecommendations:")
            for r in self.recommendations:
                lines.append(f"  --> {r}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "dimensions": [
                {"name": d.name, "score": d.score, "weight": d.weight, "notes": d.notes}
                for d in self.dimensions
            ],
            "defects": self.defects,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
        }


class DiagramScorer:
    """Scores diagram quality across multiple dimensions."""

    def score(self, model: ProcessModel, source_code: str, svg_content: str | None = None,
              renderer_name: str = "") -> QualityScore:
        qs = QualityScore()

        qs.dimensions.append(self._score_semantic_correctness(model))
        qs.dimensions.append(self._score_structural_completeness(model))
        qs.dimensions.append(self._score_readability(model, source_code))
        qs.dimensions.append(self._score_visual_hierarchy(model))
        qs.dimensions.append(self._score_edge_clarity(model))
        qs.dimensions.append(self._score_text_fit(model, source_code))
        qs.dimensions.append(self._score_modularity(model))
        qs.dimensions.append(self._score_causal_expressiveness(model))
        qs.dimensions.append(self._score_loop_support(model))
        qs.dimensions.append(self._score_editability(source_code, renderer_name))
        qs.dimensions.append(self._score_consistency(model))
        qs.dimensions.append(self._score_generalizability(model))

        if svg_content:
            qs.dimensions.append(self._score_export_quality(svg_content))

        # Collect defects
        self._detect_defects(model, source_code, svg_content, qs)

        return qs

    def _score_semantic_correctness(self, model: ProcessModel) -> ScoreDimension:
        score = 10.0
        notes = []

        # Check for orphan nodes (no edges)
        connected = set()
        for e in model.edges:
            connected.add(e.source)
            connected.add(e.target)
        orphans = [n for n in model.nodes if n.id not in connected]
        if orphans and len(model.nodes) > 1:
            penalty = min(3.0, len(orphans) * 1.0)
            score -= penalty
            notes.append(f"{len(orphans)} orphan nodes")

        # Check for self-loops
        self_loops = [e for e in model.edges if e.source == e.target]
        if self_loops:
            score -= 1.0
            notes.append(f"{len(self_loops)} self-loops")

        # Check edge types match model semantics
        has_causal = any(e.edge_type in (EdgeType.CAUSAL, EdgeType.MEDIATION, EdgeType.MODERATION)
                       for e in model.edges)
        has_flow = any(e.edge_type == EdgeType.FLOW for e in model.edges)

        if has_causal and has_flow:
            notes.append("mixed causal+flow (ok if hybrid)")

        return ScoreDimension("Semantic Correctness", max(0, score), 1.5,
                            "; ".join(notes) if notes else "clean")

    def _score_structural_completeness(self, model: ProcessModel) -> ScoreDimension:
        score = 10.0
        notes = []

        if not model.nodes:
            return ScoreDimension("Structural Completeness", 0, 1.5, "no nodes")

        # Determine if this is a causal model (different expectations)
        is_causal = model.view_mode == ViewMode.CAUSAL or any(
            e.edge_type in (EdgeType.CAUSAL, EdgeType.MEDIATION, EdgeType.MODERATION)
            for e in model.edges
        )

        # Check start/end nodes (not required for causal models)
        if not is_causal:
            has_start = any(n.node_type == NodeType.START for n in model.nodes)
            has_end = any(n.node_type == NodeType.END for n in model.nodes)
            if not has_start:
                score -= 1.0
                notes.append("no start node")
            if not has_end:
                score -= 1.0
                notes.append("no end node")

        # Check edge coverage
        node_count = len(model.nodes)
        edge_count = len(model.edges)
        if node_count > 1 and edge_count < node_count - 1:
            score -= 2.0
            notes.append("potentially disconnected graph")

        # Check for dead ends (not penalized in causal models where effects have no outgoing)
        terminal_types = (NodeType.END,)
        if is_causal:
            terminal_types = (NodeType.END, NodeType.VARIABLE)
        for node in model.nodes:
            if node.node_type not in terminal_types:
                outgoing = model.get_edges_from(node.id)
                if not outgoing and len(model.nodes) > 1:
                    # In causal models, effect nodes are natural endpoints
                    if is_causal and node.causal_role in (CausalRole.EFFECT, CausalRole.COLLIDER):
                        continue
                    score -= 0.5
                    notes.append(f"dead end: {node.id}")

        return ScoreDimension("Structural Completeness", max(0, min(10, score)), 1.5,
                            "; ".join(notes) if notes else "complete")

    def _score_readability(self, model: ProcessModel, source_code: str) -> ScoreDimension:
        score = 10.0
        notes = []

        # Density check
        node_count = len(model.nodes)
        if node_count > 20:
            score -= min(3.0, (node_count - 20) * 0.3)
            notes.append(f"high density ({node_count} nodes)")

        # Label length check
        long_labels = [n for n in model.nodes if len(n.label) > 30]
        if long_labels:
            score -= min(2.0, len(long_labels) * 0.5)
            notes.append(f"{len(long_labels)} long labels")

        # Edge density
        edge_count = len(model.edges)
        if node_count > 0 and edge_count / max(1, node_count) > 3:
            score -= 2.0
            notes.append("high edge density")

        return ScoreDimension("Readability", max(0, score), 1.0,
                            "; ".join(notes) if notes else "good")

    def _score_visual_hierarchy(self, model: ProcessModel) -> ScoreDimension:
        score = 8.0  # Start slightly lower, earn points
        notes = []

        # Groups add hierarchy
        if model.groups:
            score += 1.0
            notes.append(f"{len(model.groups)} groups")

        # Node type diversity adds visual hierarchy
        types_used = {n.node_type for n in model.nodes}
        if len(types_used) >= 3:
            score += 1.0
            notes.append("good type diversity")
        elif len(types_used) == 1 and len(model.nodes) > 3:
            score -= 1.0
            notes.append("monotone node types")

        return ScoreDimension("Visual Hierarchy", max(0, min(10, score)), 1.0,
                            "; ".join(notes) if notes else "adequate")

    def _score_edge_clarity(self, model: ProcessModel) -> ScoreDimension:
        score = 10.0
        notes = []

        # Check for crossing potential (simplified heuristic)
        # Edges between non-adjacent layers suggest crossings
        edge_types_used = {e.edge_type for e in model.edges}
        if len(edge_types_used) > 1:
            notes.append("multiple edge types (visual distinction needed)")

        # Feedback edges are inherently harder
        feedback = [e for e in model.edges if e.edge_type == EdgeType.FEEDBACK]
        if feedback:
            score -= min(1.0, len(feedback) * 0.3)
            notes.append(f"{len(feedback)} feedback edges")

        # Bidirectional edges
        bidir = [e for e in model.edges if e.edge_type == EdgeType.BIDIRECTIONAL]
        if bidir:
            score -= min(1.0, len(bidir) * 0.3)
            notes.append(f"{len(bidir)} bidirectional edges")

        return ScoreDimension("Edge Clarity", max(0, score), 1.0,
                            "; ".join(notes) if notes else "clean")

    def _score_text_fit(self, model: ProcessModel, source_code: str) -> ScoreDimension:
        score = 10.0
        notes = []

        max_label = max((len(n.label) for n in model.nodes), default=0)
        if max_label > 40:
            score -= 3.0
            notes.append(f"max label {max_label} chars")
        elif max_label > 25:
            score -= 1.0
            notes.append(f"some labels >25 chars")

        # Check for word wrapping in source
        if "\\n" in source_code or "<br" in source_code.lower():
            score += 0.5  # Wrapping attempted
            notes.append("wrapping present")

        return ScoreDimension("Text Fit", max(0, min(10, score)), 1.0,
                            "; ".join(notes) if notes else "good")

    def _score_modularity(self, model: ProcessModel) -> ScoreDimension:
        score = 5.0  # Neutral start
        notes = []

        if model.groups:
            nodes_in_groups = sum(len(model.get_nodes_in_group(g.id)) for g in model.groups)
            coverage = nodes_in_groups / max(1, len(model.nodes))
            score = 5.0 + coverage * 5.0
            notes.append(f"{coverage:.0%} nodes grouped")

        # Subprocess nodes
        subprocesses = [n for n in model.nodes if n.node_type == NodeType.SUBPROCESS]
        if subprocesses:
            score = min(10, score + 1.0)
            notes.append(f"{len(subprocesses)} subprocesses")

        if not model.groups and not subprocesses and len(model.nodes) > 10:
            score -= 2.0
            notes.append("no grouping for large model")

        return ScoreDimension("Modularity", max(0, min(10, score)), 0.8,
                            "; ".join(notes) if notes else "flat")

    def _score_causal_expressiveness(self, model: ProcessModel) -> ScoreDimension:
        score = 5.0
        notes = []

        causal_edges = [e for e in model.edges if e.edge_type in
                       (EdgeType.CAUSAL, EdgeType.MEDIATION, EdgeType.MODERATION)]
        if causal_edges:
            score += 2.0
            notes.append(f"{len(causal_edges)} causal edges")

        colliders = model.find_colliders()
        if colliders:
            score += 1.0
            notes.append(f"{len(colliders)} colliders")

        mediators = model.find_mediators()
        if mediators:
            score += 1.0
            notes.append(f"{len(mediators)} mediators")

        # Causal roles assigned
        roles = [n for n in model.nodes if n.causal_role is not None]
        if roles:
            score += 1.0
            notes.append(f"{len(roles)} nodes with causal roles")

        return ScoreDimension("Causal Expressiveness", max(0, min(10, score)), 0.8,
                            "; ".join(notes) if notes else "basic flow only")

    def _score_loop_support(self, model: ProcessModel) -> ScoreDimension:
        score = 7.0
        notes = []

        has_cycles = model.has_cycles()
        feedback = [e for e in model.edges if e.edge_type == EdgeType.FEEDBACK]

        if has_cycles:
            score += 2.0
            notes.append("cycles present")
        if feedback:
            score += 1.0
            notes.append(f"{len(feedback)} feedback edges")

        if not has_cycles and not feedback:
            notes.append("no loops (ok for linear processes)")

        return ScoreDimension("Loop Support", max(0, min(10, score)), 0.7,
                            "; ".join(notes) if notes else "n/a")

    def _score_editability(self, source_code: str, renderer_name: str) -> ScoreDimension:
        score = 7.0
        notes = []

        # Text-based formats are more editable
        if renderer_name in ("graphviz", "mermaid", "plantuml"):
            score += 2.0
            notes.append(f"{renderer_name} text format")

        # Check source length (overly complex source is hard to edit)
        lines = source_code.count('\n')
        if lines > 200:
            score -= 2.0
            notes.append(f"{lines} lines (complex)")
        elif lines > 100:
            score -= 1.0
            notes.append(f"{lines} lines")

        # SVG source is harder to hand-edit
        if renderer_name == "svg_native":
            score -= 1.0
            notes.append("raw SVG (less editable)")

        return ScoreDimension("Editability", max(0, min(10, score)), 0.6,
                            "; ".join(notes) if notes else "ok")

    def _score_consistency(self, model: ProcessModel) -> ScoreDimension:
        score = 10.0
        notes = []

        # Check label style consistency
        labels = [n.label for n in model.nodes]
        if labels:
            starts_upper = sum(1 for l in labels if l[0].isupper()) / len(labels)
            if 0.2 < starts_upper < 0.8:
                score -= 2.0
                notes.append("inconsistent capitalization")

        return ScoreDimension("Consistency", max(0, score), 0.5,
                            "; ".join(notes) if notes else "consistent")

    def _score_generalizability(self, model: ProcessModel) -> ScoreDimension:
        """How well does this model template generalize?"""
        score = 7.0
        notes = []

        # Variety of node types
        types = {n.node_type for n in model.nodes}
        if len(types) >= 4:
            score += 2.0
            notes.append("diverse node types")

        # Edge type variety
        etypes = {e.edge_type for e in model.edges}
        if len(etypes) >= 3:
            score += 1.0
            notes.append("diverse edge types")

        return ScoreDimension("Generalizability", max(0, min(10, score)), 0.5,
                            "; ".join(notes) if notes else "standard")

    def _score_export_quality(self, svg_content: str) -> ScoreDimension:
        score = 8.0
        notes = []

        if not svg_content:
            return ScoreDimension("Export Quality", 0, 0.5, "no SVG content")

        # Check SVG has viewBox
        if 'viewBox' in svg_content:
            score += 1.0
            notes.append("has viewBox")

        # Check reasonable dimensions
        width_match = re.search(r'width="(\d+)', svg_content)
        height_match = re.search(r'height="(\d+)', svg_content)
        if width_match and height_match:
            w, h = int(width_match.group(1)), int(height_match.group(1))
            if w > 3000 or h > 3000:
                score -= 2.0
                notes.append(f"large dimensions ({w}x{h})")
            elif w < 100 or h < 100:
                score -= 2.0
                notes.append(f"small dimensions ({w}x{h})")

        # Check for font declarations
        if 'font-family' in svg_content:
            score += 0.5
            notes.append("explicit fonts")

        return ScoreDimension("Export Quality", max(0, min(10, score)), 0.5,
                            "; ".join(notes) if notes else "ok")

    def _detect_defects(self, model: ProcessModel, source_code: str,
                       svg_content: str | None, qs: QualityScore):
        """Detect specific defects and add to score."""

        # Text overflow potential
        for node in model.nodes:
            if len(node.label) > 50:
                qs.defects.append(f"Text overflow risk: '{node.label[:40]}...' ({len(node.label)} chars)")

        # Overlapping risk (high density)
        if len(model.nodes) > 30:
            qs.defects.append(f"Node density ({len(model.nodes)}) risks overlapping in compact layouts")
            qs.recommendations.append("Consider modular decomposition or layered views")

        # Tangled edges (high crossing potential)
        edge_count = len(model.edges)
        node_count = len(model.nodes)
        if node_count > 0 and edge_count / node_count > 2.5:
            qs.warnings.append(f"Edge density ({edge_count/node_count:.1f} edges/node) may cause tangling")

        # Poor hierarchy detection
        if not model.groups and node_count > 8:
            qs.recommendations.append("Add groups/modules to improve visual hierarchy")

        # Missing labels on conditional edges
        unlabeled_cond = [e for e in model.edges if e.edge_type == EdgeType.CONDITIONAL and not e.label]
        if unlabeled_cond:
            qs.defects.append(f"{len(unlabeled_cond)} conditional edges without labels")

        # Awkward collider representation
        colliders = model.find_colliders()
        if len(colliders) > 2:
            qs.warnings.append(f"{len(colliders)} colliders may need special layout attention")
