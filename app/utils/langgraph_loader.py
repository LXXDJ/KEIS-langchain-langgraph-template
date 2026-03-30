"""Load and parse langgraph.json configuration."""

from __future__ import annotations

import json
from pathlib import Path

from app.utils.schema import GraphConfig, LanggraphJson

_DEFAULT_CONFIG_PATH = Path("langgraph.json")


def load_langgraph_config(
    path: Path | str = _DEFAULT_CONFIG_PATH,
) -> LanggraphJson | None:
    """Read langgraph.json and return a typed config, or None if missing."""
    config_path = Path(path)
    if not config_path.exists():
        return None

    raw = json.loads(config_path.read_text())

    graphs: list[GraphConfig] = []
    for name, entry in (raw.get("graphs") or {}).items():
        graph_path = entry if isinstance(entry, str) else entry.get("path", "")
        graphs.append(GraphConfig(path=graph_path, name=name))

    return LanggraphJson(
        graphs=graphs,
        extra_packages=raw.get("extra_packages", []),
        commands=raw.get("commands", []),
        env=raw.get("env", {}),
    )
