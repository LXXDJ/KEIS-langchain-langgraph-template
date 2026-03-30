"""State 정의 — InputState / InternalState / OutputState / Context 분리 패턴.

LangGraph StateGraph에서 사용하는 런타임 TypedDict와,
API 문서화용 Pydantic 스키마를 함께 정의합니다.

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
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from typing_extensions import Annotated, TypedDict


# ══════════════════════════════════════════════════════════════
# Part 1: Runtime TypedDict (실제 그래프 실행)
# ══════════════════════════════════════════════════════════════


class InputState(TypedDict, total=False):
    """그래프 외부에서 들어오는 입력 필드."""

    query: str
    system_prompt: Optional[str]
    llm_configs: Optional[Dict[str, Any]]


class InternalState(TypedDict, total=False):
    """그래프 내부에서만 사용하는 필드.

    _prefix로 시작하는 필드는 외부에 노출되지 않습니다.
    Annotated[..., add]를 사용하면 여러 노드의 출력이 자동 병합됩니다.
    """

    _worker_outputs: Annotated[List[Dict[str, Any]], add]


class OutputState(TypedDict, total=False):
    """그래프 최종 출력 필드."""

    status: Literal["success", "error"]
    data: Dict[str, Any]


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


# ══════════════════════════════════════════════════════════════
# Part 2: Pydantic 스키마 (API 문서화 / Info 엔드포인트)
# ══════════════════════════════════════════════════════════════


class InputStateSchema(BaseModel):
    """입력 스키마 — API 문서화 및 /info 엔드포인트에 사용."""

    query: str = Field(
        description="사용자 질의",
        examples=["최근 매출 데이터를 알려주세요."],
    )

    system_prompt: Optional[str] = Field(
        default=None,
        description="시스템 프롬프트 오버라이드",
    )

    llm_configs: Optional[Dict[str, Any]] = Field(
        default=None,
        description="LLM 사용 지점별 개별 설정 (예: {'worker': {'model_name': 'gpt-4o'}})",
    )


class OutputDataSchema(BaseModel):
    """출력 데이터 상세 스키마."""

    output: Optional[List[Dict]] = Field(
        default=None,
        description="처리 결과 데이터",
    )

    message: Optional[str] = Field(
        default=None,
        description="에러 메시지 또는 비고",
    )


class OutputStateSchema(BaseModel):
    """출력 스키마 — API 문서화용."""

    status: Literal["success", "error"] = Field(
        description="실행 상태",
    )

    data: OutputDataSchema = Field(
        description="실행 결과 데이터",
    )
