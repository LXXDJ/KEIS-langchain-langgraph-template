"""Load and parse langgraph.json configuration."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from app.utils.schema import GraphConfig, LanggraphJson, Maintainer

_ROOT_MARKERS = ("pyproject.toml", "setup.py", "setup.cfg")


def _find_project_root(start: Path | None = None) -> Path | None:
    """프로젝트 루트 마커 파일을 기준으로 루트 디렉토리를 탐색합니다."""
    current = (start or Path(__file__)).resolve().parent
    for parent in (current, *current.parents):
        if any((parent / marker).exists() for marker in _ROOT_MARKERS):
            return parent
    return None


def load_langgraph_config(
    path: Path | str | None = None,
) -> LanggraphJson | None:
    """Read langgraph.json and return a typed config, or None if missing."""
    if path is not None:
        config_path = Path(path)
    else:
        root = _find_project_root()
        config_path = root / "langgraph.json" if root else Path("langgraph.json")

    if not config_path.exists():
        return None

    raw = json.loads(config_path.read_text())

    # ── graphs ────────────────────────────────────────────────
    graphs: list[GraphConfig] = []
    for name, entry in (raw.get("graphs") or {}).items():
        graph_path = entry if isinstance(entry, str) else entry.get("path", "")
        graphs.append(GraphConfig(name=name, path=graph_path))

    # ── maintainers ───────────────────────────────────────────
    maintainers: list[Maintainer] = [
        Maintainer(name=m.get("name", ""), email=m.get("email", ""))
        for m in (raw.get("maintainers") or [])
    ]

    return LanggraphJson(
        name=raw.get("name", "default"),
        version=raw.get("version", "v0"),
        graphs=graphs,
        preset=raw.get("preset", "custom"),
        type=raw.get("type", "service"),
        description=raw.get("description", ""),
        dependencies=raw.get("dependencies", []),
        maintainers=maintainers,
        extra_packages=raw.get("extra_packages", []),
        commands=raw.get("commands", []),
        env=raw.get("env", {}),
    )


def load_graph(graph_path: str) -> Any:
    """``module_path:attribute`` 형식의 경로에서 그래프 객체를 동적 로드합니다.

    Args:
        graph_path: ``./src/graph.py:graph`` 형식의 경로.

    Returns:
        로드된 그래프 객체 (CompiledStateGraph).

    Raises:
        ValueError: 경로 형식이 잘못된 경우.
        ImportError: 모듈을 찾을 수 없는 경우.
        AttributeError: 모듈에 해당 속성이 없는 경우.
    """
    if ":" not in graph_path:
        raise ValueError(
            f"그래프 경로 형식이 잘못되었습니다: '{graph_path}'. "
            "'module_path:attribute' 형식이어야 합니다 (예: ./src/graph.py:graph)."
        )

    module_path, attr_name = graph_path.rsplit(":", 1)
    module_name = module_path.lstrip("./").replace("/", ".").removesuffix(".py")

    module = importlib.import_module(module_name)
    return getattr(module, attr_name)
