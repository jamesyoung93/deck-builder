"""
Canonical intermediate schema for process/causal models.

This schema is the single source of truth. All renderers translate FROM this
representation. All parsers translate TO this representation.
"""

from __future__ import annotations

import json
import copy
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any
from pathlib import Path

import yaml


# ── Enums ────────────────────────────────────────────────────────────────────


class NodeType(str, Enum):
    PROCESS = "process"
    DECISION = "decision"
    START = "start"
    END = "end"
    GATE = "gate"             # checkpoint / approval
    SUBPROCESS = "subprocess"
    DATA = "data"
    LATENT = "latent"         # unobserved / conceptual construct
    EXTERNAL = "external"     # external system or actor
    HUMAN = "human"
    MONITOR = "monitor"
    VARIABLE = "variable"     # for SEM / causal models


class EdgeType(str, Enum):
    FLOW = "flow"             # sequential process flow
    CAUSAL = "causal"         # causal arrow
    FEEDBACK = "feedback"     # feedback loop
    CONDITIONAL = "conditional"
    DATA_FLOW = "data_flow"
    ASSOCIATION = "association"  # non-directional association
    BIDIRECTIONAL = "bidirectional"
    MODERATION = "moderation"   # moderator relationship
    MEDIATION = "mediation"     # mediator relationship


class CausalRole(str, Enum):
    CAUSE = "cause"
    EFFECT = "effect"
    MEDIATOR = "mediator"
    MODERATOR = "moderator"
    CONFOUNDER = "confounder"
    COLLIDER = "collider"
    INSTRUMENT = "instrument"


class ProcessRole(str, Enum):
    INPUT = "input"
    OUTPUT = "output"
    TRANSFORM = "transform"
    VALIDATE = "validate"
    APPROVE = "approve"
    STORE = "store"
    MONITOR = "monitor"
    DEPLOY = "deploy"


class ViewMode(str, Enum):
    PROCESS_FLOW = "process_flow"
    CAUSAL = "causal"
    MODULAR = "modular"
    EXECUTIVE_SUMMARY = "executive_summary"


# ── Data Classes ─────────────────────────────────────────────────────────────


@dataclass
class NodeStyle:
    fill_color: str | None = None
    border_color: str | None = None
    text_color: str | None = None
    shape: str | None = None       # rectangle, diamond, ellipse, cylinder, etc.
    border_style: str | None = None  # solid, dashed, dotted
    icon: str | None = None


@dataclass
class EdgeStyle:
    color: str | None = None
    stroke_width: float | None = None
    line_style: str | None = None    # solid, dashed, dotted
    arrow_head: str | None = None    # normal, diamond, dot, none
    arrow_tail: str | None = None


@dataclass
class Node:
    id: str
    label: str
    node_type: NodeType = NodeType.PROCESS
    description: str = ""
    group: str | None = None          # parent group/module id
    causal_role: CausalRole | None = None
    process_role: ProcessRole | None = None
    style: NodeStyle | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["node_type"] = self.node_type.value
        if self.causal_role:
            d["causal_role"] = self.causal_role.value
        if self.process_role:
            d["process_role"] = self.process_role.value
        return d


@dataclass
class Edge:
    source: str
    target: str
    edge_type: EdgeType = EdgeType.FLOW
    label: str = ""
    condition: str | None = None      # for conditional edges
    weight: float | None = None       # for causal strength
    style: EdgeStyle | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["edge_type"] = self.edge_type.value
        return d


@dataclass
class Group:
    id: str
    label: str
    parent: str | None = None       # nested groups
    description: str = ""
    style: NodeStyle | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProcessModel:
    """The canonical intermediate representation for any process/causal model."""

    name: str
    description: str = ""
    version: str = "1.0"
    view_mode: ViewMode = ViewMode.PROCESS_FLOW
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Node/Edge management ─────────────────────────────────────────────

    def add_node(self, node: Node) -> None:
        if any(n.id == node.id for n in self.nodes):
            raise ValueError(f"Duplicate node id: {node.id}")
        self.nodes.append(node)

    def add_edge(self, edge: Edge) -> None:
        src_ids = {n.id for n in self.nodes}
        if edge.source not in src_ids:
            raise ValueError(f"Edge source '{edge.source}' not in nodes")
        if edge.target not in src_ids:
            raise ValueError(f"Edge target '{edge.target}' not in nodes")
        self.edges.append(edge)

    def add_group(self, group: Group) -> None:
        self.groups.append(group)

    def get_node(self, node_id: str) -> Node | None:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def get_nodes_in_group(self, group_id: str) -> list[Node]:
        return [n for n in self.nodes if n.group == group_id]

    def get_edges_from(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.source == node_id]

    def get_edges_to(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.target == node_id]

    def has_cycles(self) -> bool:
        """Detect if the model contains cycles (feedback loops)."""
        visited = set()
        rec_stack = set()

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            for edge in self.get_edges_from(node_id):
                if edge.target not in visited:
                    if dfs(edge.target):
                        return True
                elif edge.target in rec_stack:
                    return True
            rec_stack.discard(node_id)
            return False

        for node in self.nodes:
            if node.id not in visited:
                if dfs(node.id):
                    return True
        return False

    def find_colliders(self) -> list[str]:
        """Find nodes that are colliders (multiple incoming causal edges)."""
        colliders = []
        for node in self.nodes:
            incoming_causal = [
                e for e in self.get_edges_to(node.id)
                if e.edge_type == EdgeType.CAUSAL
            ]
            if len(incoming_causal) >= 2:
                colliders.append(node.id)
        return colliders

    def find_mediators(self) -> list[str]:
        """Find nodes that mediate between others (single in, single out causal)."""
        mediators = []
        for node in self.nodes:
            incoming = [e for e in self.get_edges_to(node.id) if e.edge_type == EdgeType.CAUSAL]
            outgoing = [e for e in self.get_edges_from(node.id) if e.edge_type == EdgeType.CAUSAL]
            if len(incoming) == 1 and len(outgoing) == 1:
                mediators.append(node.id)
        return mediators

    def get_submodel(self, group_id: str) -> "ProcessModel":
        """Extract a submodel for a specific group."""
        nodes = self.get_nodes_in_group(group_id)
        node_ids = {n.id for n in nodes}
        edges = [e for e in self.edges if e.source in node_ids and e.target in node_ids]
        group = next((g for g in self.groups if g.id == group_id), None)
        return ProcessModel(
            name=f"{self.name} - {group.label if group else group_id}",
            description=f"Submodel of {self.name}",
            nodes=copy.deepcopy(nodes),
            edges=copy.deepcopy(edges),
            groups=[copy.deepcopy(group)] if group else [],
        )

    # ── Serialization ────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "view_mode": self.view_mode.value,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "groups": [g.to_dict() for g in self.groups],
            "metadata": self.metadata,
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: str | Path, fmt: str = "yaml") -> None:
        path = Path(path)
        if fmt == "yaml":
            path.write_text(self.to_yaml(), encoding="utf-8")
        else:
            path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict) -> "ProcessModel":
        model = cls(
            name=data["name"],
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            view_mode=ViewMode(data.get("view_mode", "process_flow")),
            metadata=data.get("metadata", {}),
        )
        for g in data.get("groups", []):
            model.add_group(Group(
                id=g["id"],
                label=g["label"],
                parent=g.get("parent"),
                description=g.get("description", ""),
            ))
        for n in data.get("nodes", []):
            style = None
            if n.get("style"):
                style = NodeStyle(**{k: v for k, v in n["style"].items() if v is not None})
            model.add_node(Node(
                id=n["id"],
                label=n["label"],
                node_type=NodeType(n.get("node_type", "process")),
                description=n.get("description", ""),
                group=n.get("group"),
                causal_role=CausalRole(n["causal_role"]) if n.get("causal_role") else None,
                process_role=ProcessRole(n["process_role"]) if n.get("process_role") else None,
                style=style,
                metadata=n.get("metadata", {}),
            ))
        for e in data.get("edges", []):
            style = None
            if e.get("style"):
                style = EdgeStyle(**{k: v for k, v in e["style"].items() if v is not None})
            model.add_edge(Edge(
                source=e["source"],
                target=e["target"],
                edge_type=EdgeType(e.get("edge_type", "flow")),
                label=e.get("label", ""),
                condition=e.get("condition"),
                weight=e.get("weight"),
                style=style,
                metadata=e.get("metadata", {}),
            ))
        return model

    @classmethod
    def load(cls, path: str | Path) -> "ProcessModel":
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
        return cls.from_dict(data)
