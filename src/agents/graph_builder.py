"""Graph builder — 프로젝트 통합 진입점.

이 레포는 SVC-3 (고용24 검색 결과 요약) 전용으로 정리된 상태이며,
유일한 preset은 ``ai_search_summary`` 입니다.

향후 다른 에이전트(예: SVC-1)를 추가하려면:
  1. ``src/agents/presets/`` 에 새 ``build_{name}()`` 함수 추가
  2. 이 파일의 ``Preset`` Literal 과 ``_BUILDERS`` dict 에 등록
  3. ``src/agents/registry.py`` 에 PresetInfo 등록
"""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph.state import CompiledStateGraph

from agents.presets.ai_search_summary import build_ai_search_summary

Preset = Literal["ai_search_summary"]

_BUILDERS: dict[str, Any] = {
    "ai_search_summary": build_ai_search_summary,
}


def build_graph(
    preset: Preset = "ai_search_summary",
    **kwargs: Any,
) -> CompiledStateGraph:
    """프로젝트 기본 진입점. preset으로 에이전트 유형을 선택합니다.

    현재 등록된 preset은 ``ai_search_summary`` 하나입니다.

    Args:
        preset: 에이전트 유형 (현재는 ``"ai_search_summary"`` 만 지원)
        **kwargs: 선택한 preset 빌더에 전달할 추가 인자

    Returns:
        CompiledStateGraph — LangServe add_routes()에 바로 연결 가능

    Examples:
        >>> graph = build_graph()
        >>> graph = build_graph("ai_search_summary")
    """
    builder_fn = _BUILDERS.get(preset)
    if builder_fn is None:
        available = ", ".join(_BUILDERS.keys())
        raise ValueError(f"Unknown preset '{preset}'. Available: {available}")

    return builder_fn(**kwargs)
