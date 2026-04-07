"""Preset: ai_search_summary — 고용24 AI 검색 결과 요약 (SVC-3).

선형 결정론 파이프라인:

    START → preprocess → worker_search_summary → postprocessor → END

- preprocess: 기존 노드 재사용 (마지막 HumanMessage strip)
- worker_search_summary: 의도 분류 → 검색 → 선별 → 요약 → navigation → JSON 직렬화
- postprocessor: 기존 노드 재사용 (``_worker_outputs[0]["data"]["response"]`` → AIMessage)

이 preset은 그 자체로 ``CompiledStateGraph`` 를 반환하므로,
LangServe에 직접 연결하거나 더 큰 멀티에이전트 그래프의 서브그래프로
임베드할 수 있습니다 (SVC-1 등 향후 확장 시).
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.nodes import postprocessor, preprocess, worker_search_summary
from agents.state import Context, InputState, OutputState, State


def build_ai_search_summary(**_kwargs: Any) -> CompiledStateGraph:
    """ai_search_summary preset 빌더.

    그래프 구조:
        START → preprocess → worker_search_summary → postprocessor → END

    State 분리:
        - state_schema=State
        - input_schema=InputState
        - output_schema=OutputState
        - context_schema=Context
    """
    builder = StateGraph(
        state_schema=State,
        input_schema=InputState,
        output_schema=OutputState,
        context_schema=Context,
    )

    builder.add_node("preprocess", preprocess)
    builder.add_node("worker_search_summary", worker_search_summary)
    builder.add_node("postprocessor", postprocessor)

    builder.add_edge(START, "preprocess")
    builder.add_edge("preprocess", "worker_search_summary")
    builder.add_edge("worker_search_summary", "postprocessor")
    builder.add_edge("postprocessor", END)

    return builder.compile(name="ai_search_summary")
