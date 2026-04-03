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

from agents import build_graph
from app.utils.langgraph_loader import load_langgraph_config

_config = load_langgraph_config()
_preset = _config.preset if _config else "custom"

graph = build_graph(preset=_preset)  # type: ignore[arg-type]
