"""Rendering backend adapters."""

from .base import BaseRenderer, RenderResult
from .mermaid import MermaidRenderer
from .graphviz_renderer import GraphvizRenderer
from .plantuml import PlantUMLRenderer
from .svg_native import SVGNativeRenderer

RENDERERS = {
    "mermaid": MermaidRenderer,
    "graphviz": GraphvizRenderer,
    "plantuml": PlantUMLRenderer,
    "svg_native": SVGNativeRenderer,
}


def get_renderer(name: str, **kwargs) -> BaseRenderer:
    """Get a renderer by name."""
    if name not in RENDERERS:
        raise ValueError(f"Unknown renderer: {name}. Available: {list(RENDERERS.keys())}")
    return RENDERERS[name](**kwargs)


def list_renderers() -> list[str]:
    return list(RENDERERS.keys())
