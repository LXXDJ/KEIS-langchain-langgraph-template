"""Graph builder — 프로젝트 통합 진입점.

build_graph()는 preset 파라미터로 에이전트 유형을 선택합니다:
  - "chat"          : langchain create_agent() 기반 대화형 에이전트
  - "deep_research" : deepagents create_deep_agent() 기반 리서치 에이전트
  - "custom"        : 수동 StateGraph 노드 조합 (기존 방식)

모든 preset은 CompiledStateGraph를 반환하므로 LangServe에 바로 연결 가능합니다.
"""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph.state import CompiledStateGraph

from agents.presets.ai_search_summary import build_ai_search_summary
from agents.presets.chat import build_chat
from agents.presets.custom import build_custom
from agents.presets.deep_research import build_deep_research

Preset = Literal["chat", "deep_research", "custom", "ai_search_summary"]

_BUILDERS: dict[str, Any] = {
    "chat": build_chat,
    "deep_research": build_deep_research,
    "custom": build_custom,
    "ai_search_summary": build_ai_search_summary,
}


def build_graph(
    preset: Preset = "custom",
    **kwargs: Any,
) -> CompiledStateGraph:
    """프로젝트 기본 진입점. preset으로 에이전트 유형을 선택합니다.

    Args:
        preset: 에이전트 유형 ("chat", "deep_research", "custom")
        **kwargs: 선택한 preset 빌더에 전달할 추가 인자

    Returns:
        CompiledStateGraph — LangServe add_routes()에 바로 연결 가능

    Examples:
        # 기본 (LLM 없이 테스트용)
        graph = build_graph()

        # LangChain create_agent 기반
        graph = build_graph("chat", model="openai:gpt-4o")

        # DeepAgents 기반 리서치 에이전트
        graph = build_graph("deep_research", model="openai:gpt-4o")
    """
    builder_fn = _BUILDERS.get(preset)
    if builder_fn is None:
        available = ", ".join(_BUILDERS.keys())
        raise ValueError(f"Unknown preset '{preset}'. Available: {available}")

    return builder_fn(**kwargs)
