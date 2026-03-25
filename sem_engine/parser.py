"""
Parser / intake module.

Converts structured or semi-structured process descriptions into
the canonical ProcessModel schema.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from .schema import (
    ProcessModel, Node, Edge, Group,
    NodeType, EdgeType, CausalRole, ProcessRole, ViewMode,
)


def load_yaml(path: str | Path) -> ProcessModel:
    """Load a ProcessModel from a YAML file."""
    return ProcessModel.load(path)


def load_json(path: str | Path) -> ProcessModel:
    """Load a ProcessModel from a JSON file."""
    return ProcessModel.load(path)


def parse_dict(data: dict) -> ProcessModel:
    """Parse a dictionary into a ProcessModel."""
    return ProcessModel.from_dict(data)


def parse_simple_list(name: str, steps: list[str], description: str = "") -> ProcessModel:
    """
    Parse a simple ordered list of steps into a linear ProcessModel.

    Example: ["Collect data", "Clean data", "Analyze", "Report"]
    """
    model = ProcessModel(name=name, description=description)

    for i, step in enumerate(steps):
        node_id = f"step_{i}"
        node_type = NodeType.START if i == 0 else (
            NodeType.END if i == len(steps) - 1 else NodeType.PROCESS
        )
        model.add_node(Node(id=node_id, label=step, node_type=node_type))
        if i > 0:
            model.add_edge(Edge(source=f"step_{i-1}", target=node_id))

    return model


def parse_markdown_steps(name: str, markdown: str) -> ProcessModel:
    """
    Parse a markdown-formatted process description.

    Supports:
    - Numbered lists for sequential steps
    - Indented items for sub-steps (grouped)
    - Lines starting with '?' for decision nodes
    - Lines starting with '!' for gates/checkpoints
    - Lines containing '->' for explicit edges
    - Lines starting with '[group:NAME]' for grouping
    """
    model = ProcessModel(name=name)
    lines = markdown.strip().split("\n")

    current_group = None
    prev_node_id = None
    node_counter = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Group marker
        group_match = re.match(r'\[group:(.+?)\]', line)
        if group_match:
            current_group = group_match.group(1).strip()
            gid = re.sub(r'\W+', '_', current_group.lower())
            model.add_group(Group(id=gid, label=current_group))
            current_group = gid
            continue

        # Explicit edge
        if '->' in line and not line.startswith(('- ', '* ', '1')):
            parts = line.split('->')
            if len(parts) == 2:
                src = re.sub(r'\W+', '_', parts[0].strip().lower())
                tgt = re.sub(r'\W+', '_', parts[1].strip().lower())
                label = ""
                if '|' in parts[1]:
                    tgt_parts = parts[1].split('|')
                    tgt = re.sub(r'\W+', '_', tgt_parts[0].strip().lower())
                    label = tgt_parts[1].strip()
                try:
                    model.add_edge(Edge(source=src, target=tgt, label=label))
                except ValueError:
                    pass  # Skip edges with missing nodes
                continue

        # Strip list markers
        label = re.sub(r'^[\d]+[\.\)]\s*', '', line)
        label = re.sub(r'^[-\*]\s*', '', label)

        # Determine node type
        if label.startswith('?'):
            node_type = NodeType.DECISION
            label = label[1:].strip()
        elif label.startswith('!'):
            node_type = NodeType.GATE
            label = label[1:].strip()
        elif label.lower().startswith('start'):
            node_type = NodeType.START
        elif label.lower().startswith('end') or label.lower().startswith('finish'):
            node_type = NodeType.END
        else:
            node_type = NodeType.PROCESS

        node_id = re.sub(r'\W+', '_', label.lower())[:40]
        if not node_id:
            node_id = f"node_{node_counter}"

        # Ensure unique id
        while model.get_node(node_id):
            node_counter += 1
            node_id = f"{node_id}_{node_counter}"

        model.add_node(Node(
            id=node_id,
            label=label,
            node_type=node_type,
            group=current_group,
        ))

        if prev_node_id:
            model.add_edge(Edge(source=prev_node_id, target=node_id))

        prev_node_id = node_id
        node_counter += 1

    return model


def auto_detect_and_load(path: str | Path) -> ProcessModel:
    """Auto-detect format and load a ProcessModel from file."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        return load_yaml(path)
    elif suffix == ".json":
        return load_json(path)
    elif suffix in (".md", ".txt"):
        text = path.read_text(encoding="utf-8")
        return parse_markdown_steps(path.stem, text)
    else:
        # Try YAML, then JSON
        text = path.read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(text)
            if isinstance(data, dict):
                return parse_dict(data)
        except Exception:
            pass
        try:
            data = json.loads(text)
            return parse_dict(data)
        except Exception:
            pass
        raise ValueError(f"Cannot parse file: {path}")
