"""컴파일된 그래프 모듈 — langgraph.json에서 참조됩니다.

langgraph.json의 ``preset`` 필드를 읽어 해당 에이전트 그래프를 빌드합니다.
이 모듈의 ``graph`` 변수가 LangServe에 연결되는 최종 진입점입니다.

langgraph.json 예시::

    {
      "graphs": {"agent": "./src/graph.py:graph"},
      "preset": "deep_research"
    }
"""

from __future__ import annotations

import json

from agents import build_graph
from agents._utils import find_project_root


def _read_preset() -> str:
    """langgraph.json에서 preset 값을 읽습니다. 없으면 'custom'을 반환합니다."""
    config_path = find_project_root() / "langgraph.json"
    if not config_path.exists():
        return "custom"
    raw = json.loads(config_path.read_text())
    return raw.get("preset", "custom")


graph = build_graph(preset=_read_preset())  # type: ignore[arg-type]
