"""Preset: custom — 수동 StateGraph 노드 조합 방식.

State 분리 패턴(InputState / InternalState / OutputState / Context)과
노드 안에서 create_agent()를 서브 에이전트로 쓰는 패턴을 보여줍니다.

그래프 흐름:
    START → preprocess → worker → postprocessor → END
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.nodes import worker_chat, worker_deep
from agents.nodes.postprocessor import postprocessor
from agents.nodes.preprocess import preprocess
from agents.nodes.worker import worker
from agents.state import Context, InputState, OutputState, State


# ── 그래프 빌더 ───────────────────────────────────────────────


def build_custom(**_kwargs: Any) -> CompiledStateGraph:
    """수동 StateGraph 노드 조합으로 그래프를 빌드합니다.

    그래프 구조:
        START → preprocess → worker → postprocessor → END

    State 분리:
        - state_schema=State     : 전체 (Input + Internal + Output)
        - input_schema=InputState: 외부에서 받는 필드만
        - output_schema=OutputState: 외부에 반환하는 필드만
        - context_schema=Context : 런타임 설정 (state에 포함 안 됨)
    """
    builder = StateGraph(
        state_schema=State,
        input_schema=InputState,
        output_schema=OutputState,
        context_schema=Context,
    )

    builder.add_node("preprocess", preprocess)

    # builder.add_node("worker", worker) # 기본 NODE
    # builder.add_node("worker", worker_chat) # create_agent 활용 NODE
    builder.add_node("worker", worker_deep) # create_deep_agent 활용 NODE

    builder.add_node("postprocessor", postprocessor)

    builder.add_edge(START, "preprocess")
    builder.add_edge("preprocess", "worker")
    builder.add_edge("worker", "postprocessor")
    builder.add_edge("postprocessor", END)

    return builder.compile(name="lcdaf_custom_graph")
