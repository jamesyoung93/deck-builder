"""
Automatic process flow diagram generation for slide decks.

Analyzes a Deck's content and generates an appropriate architecture/workflow
diagram via sem_engine, then inserts it as a process_flow slide.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sem_engine.schema import (
    ProcessModel, Node, Edge, Group,
    NodeType, EdgeType, ViewMode,
)
from sem_engine.renderers.premium_renderer import PremiumRenderer
from sem_engine.renderers.dark_theme import DarkThemeRenderer
from .schema import Deck, Slide, SlideType


def auto_generate_flow(deck: Deck, output_dir: Path, bg_color: str = "#0D1B2A") -> Slide | None:
    """
    Analyze a deck and generate an appropriate process flow diagram.

    Scans the deck for:
    - Timeline phases -> sequential workflow
    - Three-column pillars -> parallel streams
    - Bullet points mentioning systems/tools -> architecture
    - Section dividers -> major stages

    Returns a Slide with flow_image_path set, or None if insufficient content.
    """
    # Extract structural signals from the deck
    phases = []
    pillars = []
    systems = []
    stages = []

    for s in deck.slides:
        if s.type == SlideType.TIMELINE and s.phases:
            phases = s.phases
        if s.type == SlideType.THREE_COLUMN and s.columns:
            if not pillars:  # Use first three-column as pillars
                pillars = s.columns
        if s.type == SlideType.SECTION_DIVIDER:
            stages.append(s.title)

    # Need at least some structure to generate from
    if not phases and not pillars and len(stages) < 2:
        return None

    model = ProcessModel(
        name=f"{deck.title} - Process Flow",
        view_mode=ViewMode.PROCESS_FLOW,
    )

    if phases:
        # Generate from timeline phases
        _build_from_phases(model, phases, pillars)
    elif pillars:
        # Generate from column pillars
        _build_from_pillars(model, pillars)
    elif stages:
        # Generate from section dividers
        _build_from_stages(model, stages)

    if len(model.nodes) < 3:
        return None

    # Store the model spec as a dict for native pptx rendering
    model_dict = model.to_dict()

    # Create the slide with flow_spec (will be rendered natively as PowerPoint shapes)
    slide = Slide(
        type=SlideType.PROCESS_FLOW,
        title=f"The overall approach follows a structured workflow across key phases",
        flow_spec=model_dict,
        source="Project team analysis",
    )

    return slide


def _build_from_phases(model: ProcessModel, phases, pillars):
    """Build a clean workflow from timeline phases — 1-2 key nodes per phase."""
    model.view_mode = ViewMode.PROCESS_FLOW

    prev_node = None
    for pi, phase in enumerate(phases):
        gid = f"phase_{pi}"
        model.add_group(Group(id=gid, label=phase.label))

        # Pick the 2 most important items: first real item + gate
        key_items = []
        gate_item = None
        for item in phase.items:
            if item.lower().startswith("gate:"):
                gate_item = item
            elif len(key_items) < 2:
                key_items.append(item)

        # Create nodes
        phase_nodes = []
        for ii, item in enumerate(key_items):
            nid = f"p{pi}_n{ii}"
            model.add_node(Node(id=nid, label=item, node_type=NodeType.PROCESS, group=gid))
            phase_nodes.append(nid)

        if gate_item:
            gid_node = f"gate_{pi}"
            model.add_node(Node(id=gid_node, label=gate_item, node_type=NodeType.GATE, group=gid))
            phase_nodes.append(gid_node)

        # Connect within phase
        for i in range(1, len(phase_nodes)):
            model.add_edge(Edge(source=phase_nodes[i-1], target=phase_nodes[i], edge_type=EdgeType.FLOW))

        # Connect from previous phase
        if prev_node and phase_nodes:
            model.add_edge(Edge(source=prev_node, target=phase_nodes[0], edge_type=EdgeType.FLOW))

        if phase_nodes:
            prev_node = phase_nodes[-1]


def _build_from_pillars(model: ProcessModel, pillars):
    """Build parallel streams from column pillars — clean, high-level."""
    model.view_mode = ViewMode.PROCESS_FLOW

    # Start node
    model.add_node(Node(id="start", label="Strategic\nInitiative", node_type=NodeType.START))

    for ci, col in enumerate(pillars):
        gid = f"pillar_{ci}"
        model.add_group(Group(id=gid, label=col.heading))

        # Just 2 nodes per pillar: the key action and the expected outcome
        # Pick first bullet as action, last as outcome
        action = col.bullets[0] if col.bullets else col.heading
        outcome = col.bullets[-1] if len(col.bullets) > 1 else "Deliver results"

        action_id = f"p{ci}_action"
        outcome_id = f"p{ci}_outcome"

        model.add_node(Node(id=action_id, label=action, node_type=NodeType.PROCESS, group=gid))
        model.add_node(Node(id=outcome_id, label=outcome, node_type=NodeType.GATE, group=gid))

        model.add_edge(Edge(source="start", target=action_id, edge_type=EdgeType.FLOW))
        model.add_edge(Edge(source=action_id, target=outcome_id, edge_type=EdgeType.FLOW))

    # End node
    model.add_node(Node(id="end", label="Integrated\nOutcome", node_type=NodeType.END))
    for ci in range(len(pillars)):
        outcome_id = f"p{ci}_outcome"
        if model.get_node(outcome_id):
            model.add_edge(Edge(source=outcome_id, target="end", edge_type=EdgeType.CAUSAL))


def _build_from_stages(model: ProcessModel, stages):
    """Build a simple sequential flow from section divider titles."""

    prev = None
    for si, stage in enumerate(stages):
        nid = f"stage_{si}"
        ntype = NodeType.START if si == 0 else (
            NodeType.END if si == len(stages) - 1 else NodeType.PROCESS
        )
        model.add_node(Node(id=nid, label=stage, node_type=ntype))
        if prev:
            model.add_edge(Edge(source=prev, target=nid, edge_type=EdgeType.FLOW))
        prev = nid


def insert_auto_flow(deck: Deck, output_dir: Path, bg_color: str = "#0D1B2A",
                     position: str = "after_first_section") -> bool:
    """
    Generate and insert a process flow slide into a deck.

    Args:
        deck: The deck to modify
        output_dir: Where to save the diagram image
        position: Where to insert:
            "after_first_section" - after the first section divider
            "before_timeline" - before the timeline slide
            "end" - before the closing slide

    Returns:
        True if a flow was inserted, False otherwise
    """
    flow_slide = auto_generate_flow(deck, output_dir, bg_color)
    if flow_slide is None:
        return False

    # Check if deck already has a process_flow slide
    if any(s.type == SlideType.PROCESS_FLOW for s in deck.slides):
        return False  # Don't duplicate

    # Find insertion point
    insert_idx = len(deck.slides) - 1  # Default: before last slide

    if position == "after_first_section":
        for i, s in enumerate(deck.slides):
            if s.type == SlideType.SECTION_DIVIDER:
                insert_idx = i + 1
                break
    elif position == "before_timeline":
        for i, s in enumerate(deck.slides):
            if s.type == SlideType.TIMELINE:
                insert_idx = i
                break
    elif position == "end":
        # Before closing slide
        for i in range(len(deck.slides) - 1, -1, -1):
            if deck.slides[i].type == SlideType.CLOSING:
                insert_idx = i
                break

    deck.slides.insert(insert_idx, flow_slide)
    return True
