"""State 정의 — messages 기반 통합 인터페이스.

모든 preset(chat, deep_research, custom)이 동일한 messages 입출력을 사용합니다.

Usage:
    graph_builder = StateGraph(
        state_schema=State,
        input_schema=InputState,
        output_schema=OutputState,
        context_schema=Context,
    )
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import TypedDict

# ══════════════════════════════════════════════════════════════
# Part 1: Runtime TypedDict (실제 그래프 실행)
# ══════════════════════════════════════════════════════════════


class InputState(TypedDict, total=False):
    """그래프 외부에서 들어오는 입력 필드."""

    messages: Annotated[list[AnyMessage], add_messages]


class InternalState(TypedDict, total=False):
    """그래프 내부에서만 사용하는 필드.

    _prefix로 시작하는 필드는 외부에 노출되지 않습니다.
    Annotated[..., add]를 사용하면 여러 노드의 출력이 자동 병합됩니다.
    """

    _worker_outputs: Annotated[list[dict[str, Any]], add]


class OutputState(TypedDict, total=False):
    """그래프 최종 출력 필드."""

    messages: Annotated[list[AnyMessage], add_messages]


class State(InputState, InternalState, OutputState, total=False):
    """전체 상태 = Input + Internal + Output.

    StateGraph(state_schema=State) 에 전달합니다.
    """

    pass


class Context(TypedDict, total=False):
    """런타임 컨텍스트 (RunnableConfig.context로 전달).

    노드 간 공유하지만 state에는 포함되지 않는 설정값.
    """

    debug: bool
