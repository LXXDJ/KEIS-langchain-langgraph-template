"""Schema definitions for langgraph.json configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GraphConfig:
    """Single graph entry from langgraph.json 'graphs' field.

    Example:
        "agent": "./src/graph.py:graph"
        → GraphConfig(name="agent", path="./src/graph.py:graph")
    """

    name: str
    path: str


@dataclass
class Maintainer:
    """Maintainer entry from langgraph.json."""

    name: str
    email: str = ""


@dataclass
class LanggraphJson:
    """Parsed representation of langgraph.json.

    Example:
        {
          "dependencies": ["."],
          "graphs": {"agent": "./src/graph.py:graph"},
          "type": "service",
          "name": "langchain-langgraph-template",
          "version": "v260331",
          "description": "...",
          "maintainers": [{"name": "NoName", "email": "example@atdev.co.kr"}]
        }
    """

    # 필수
    name: str = "default"
    version: str = "v0"
    graphs: list[GraphConfig] = field(default_factory=list)

    # 선택
    type: str = "service"
    description: str = ""
    dependencies: list[str] = field(default_factory=list)
    maintainers: list[Maintainer] = field(default_factory=list)

    # Dockerfile에서 사용
    extra_packages: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
