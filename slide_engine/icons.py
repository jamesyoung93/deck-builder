"""
Icon library for slide elements.

Maps semantic icon names to PNG files rendered from FontAwesome.
Provides helper to get the right icon file for a given context.
"""

from pathlib import Path

ICON_DIR = Path(__file__).parent / "tools" / "icons"

# Available icons and their semantic categories
ICON_CATALOG = {
    # Strategy & business
    "target": "target",
    "bullseye": "target",
    "strategy": "compass",
    "compass": "compass",
    "trophy": "trophy",
    "star": "star",
    "flag": "flag",
    "rocket": "rocket",
    "bolt": "bolt",
    "growth": "chart_line",

    # Data & analytics
    "chart": "chart_bar",
    "chart_bar": "chart_bar",
    "chart_line": "chart_line",
    "chart_pie": "chart_pie",
    "data": "database",
    "database": "database",
    "search": "search",
    "analytics": "chart_line",
    "dashboard": "chart_bar",

    # Technology
    "cloud": "cloud",
    "cog": "cog",
    "settings": "cog",
    "wrench": "wrench",
    "network": "network",
    "ai": "brain",
    "brain": "brain",
    "sync": "sync",
    "layers": "layers",
    "platform": "layers",

    # People & organization
    "users": "users",
    "people": "people",
    "team": "users",
    "handshake": "handshake",
    "building": "building",
    "graduation": "graduation",
    "training": "graduation",

    # Process & operations
    "check": "check",
    "clipboard": "clipboard",
    "sitemap": "sitemap",
    "process": "sitemap",
    "truck": "truck",
    "logistics": "truck",
    "flask": "flask",
    "experiment": "flask",

    # Finance
    "dollar": "dollar",
    "money": "dollar",
    "finance": "dollar",
    "percentage": "percentage",
    "roi": "percentage",

    # Security & compliance
    "shield": "shield",
    "lock": "lock",
    "security": "shield",
    "key": "key",

    # Communication
    "globe": "globe",
    "global": "globe",
    "eye": "eye",
    "visibility": "eye",
    "lightbulb": "lightbulb",
    "idea": "lightbulb",
    "insight": "lightbulb",
    "comment": "comment",
    "heartbeat": "heartbeat",
    "health": "heartbeat",

    # Arrows & navigation
    "arrow_right": "arrow_right",
    "next": "arrow_right",
}


def get_icon_path(name: str, color: str = "white") -> Path | None:
    """
    Get path to an icon PNG file.

    Args:
        name: Semantic icon name (e.g., "rocket", "data", "team")
        color: "white", "blue", or "navy"

    Returns:
        Path to PNG file, or None if not found
    """
    # Resolve alias
    file_stem = ICON_CATALOG.get(name.lower(), name.lower())
    path = ICON_DIR / f"{file_stem}_{color}.png"
    if path.exists():
        return path
    return None


def list_icons() -> list[str]:
    """List all available semantic icon names."""
    return sorted(set(ICON_CATALOG.keys()))


def auto_icon(text: str) -> str | None:
    """
    Auto-detect an appropriate icon based on text content.
    Returns icon name or None.
    """
    text_lower = text.lower()

    # Order matters: more specific phrases first
    keyword_map = {
        "field force": "people",
        "change management": "sync",
        "change readiness": "sync",
        "operating model": "sitemap",
        "customer intelligence": "brain",
        "customer engagement": "users",
        "customer": "users",
        "omnichannel": "network",
        "channel": "network",
        "digital maturity": "chart_bar",
        "digital": "cloud",
        "data platform": "database",
        "data layer": "database",
        "data foundation": "database",
        "data": "database",
        "ai-powered": "brain",
        "ai-driven": "brain",
        "artificial intelligence": "brain",
        "machine learning": "brain",
        "ai": "brain",
        "analytics": "chart_line",
        "dashboard": "chart_bar",
        "capability": "graduation",
        "training": "graduation",
        "academy": "graduation",
        "platform": "layers",
        "infrastructure": "layers",
        "architecture": "sitemap",
        "investment": "dollar",
        "revenue": "dollar",
        "budget": "dollar",
        "cost": "dollar",
        "pricing": "dollar",
        "financial": "dollar",
        "roi": "percentage",
        "margin": "percentage",
        "growth": "chart_line",
        "market entry": "globe",
        "market": "globe",
        "global": "globe",
        "regional": "globe",
        "security": "shield",
        "compliance": "shield",
        "regulatory": "shield",
        "innovation": "lightbulb",
        "insight": "lightbulb",
        "vision": "lightbulb",
        "strategy": "compass",
        "roadmap": "compass",
        "performance": "chart_bar",
        "benchmark": "chart_bar",
        "operational": "cog",
        "efficiency": "cog",
        "technology": "cog",
        "vendor": "search",
        "selection": "search",
        "partner": "handshake",
        "jv": "handshake",
        "stakeholder": "handshake",
        "steering": "handshake",
        "transform": "rocket",
        "launch": "rocket",
        "deploy": "rocket",
        "scale": "rocket",
        "approve": "check",
        "authorize": "check",
        "endorse": "check",
        "decision": "check",
        "monitor": "eye",
        "tracking": "eye",
        "health": "heartbeat",
        "pharma": "heartbeat",
        "clinical": "heartbeat",
        "research": "flask",
        "experiment": "flask",
        "pilot": "flask",
        "process": "sitemap",
        "workflow": "sitemap",
        "logistics": "truck",
        "supply chain": "truck",
        "target": "target",
        "goal": "target",
        "objective": "target",
        "team": "users",
        "hiring": "users",
        "talent": "users",
        "organization": "building",
        "enterprise": "building",
    }

    for keyword, icon in keyword_map.items():
        if keyword in text_lower:
            return icon

    return None
