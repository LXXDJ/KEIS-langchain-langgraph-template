"""Schema definitions for langgraph.json and app configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GraphConfig:
    """Single graph entry from langgraph.json 'graphs' field."""

    path: str
    name: str = "default"


@dataclass
class LanggraphJson:
    """Parsed representation of langgraph.json."""

    graphs: list[GraphConfig] = field(default_factory=list)
    extra_packages: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
