"""Graph builder — 프로젝트 통합 진입점.

build_graph()는 preset 파라미터로 에이전트 유형을 선택합니다:
  - "chat"          : langchain create_agent() 기반 대화형 에이전트
  - "deep_research" : deepagents create_deep_agent() 기반 리서치 에이전트
  - "custom"        : 수동 StateGraph 노드 조합 (기존 방식)

모든 preset은 CompiledStateGraph를 반환하므로 LangServe에 바로 연결 가능합니다.

새 preset 추가 절차:
  1. `src/agents/presets/{name}.py` 에 `build_{name}()` 함수 생성
  2. 아래 `_BUILDERS` 에 한 줄 추가 + `Preset` Literal 에 이름 추가
"""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph.state import CompiledStateGraph

from agents.presets.chat import build_chat
from agents.presets.custom import build_custom
from agents.presets.deep_research import build_deep_research

# ── preset 등록 (단일 진실의 원천) ─────────────────────────────
# 새 preset을 추가할 때는 _BUILDERS 와 Preset Literal 두 곳을 함께 업데이트하세요.

_BUILDERS: dict[str, Any] = {
    "chat": build_chat,
    "deep_research": build_deep_research,
    "custom": build_custom,
}

Preset = Literal["chat", "deep_research", "custom"]


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
