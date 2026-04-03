"""미들웨어: Human-in-the-Loop — 도구 실행 전 사람 승인.

고위험 도구 호출(DB 쓰기, 결제 등)을 실행하기 전에
사람의 승인·수정·거부를 받을 수 있습니다.

사용법:
    from agents.middlewares import create_hitl_middleware

    agent = create_deep_agent(
        middleware=[create_hitl_middleware(
            interrupt_on={
                "execute_sql": {"allowed_decisions": ["approve", "edit", "reject"]},
                "send_email": True,
            },
        )],
        checkpointer=MemorySaver(),  # 상태 유지 필수
    )
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from langchain.agents.middleware.types import AgentMiddleware


def create_hitl_middleware(
    *,
    interrupt_on: dict[str, bool | dict[str, Any]],
) -> AgentMiddleware:
    """Human-in-the-Loop 미들웨어를 생성합니다.

    Args:
        interrupt_on: 도구별 중단 설정 매핑.
            키 = 도구 이름.
            값 = ``True`` (기본 승인 요청) 또는 ``InterruptOnConfig`` dict.
            InterruptOnConfig 키:
                allowed_decisions — ``["approve", "edit", "reject"]`` 중 선택.
                description — (선택) 승인 요청 시 표시할 설명.
            이 파라미터는 필수입니다 — 중단 지점 없이 HITL은 동작하지 않습니다.

    Note:
        반드시 checkpointer와 함께 사용해야 합니다.
        checkpointer 없이는 중단된 상태를 복원할 수 없습니다.

    적합한 경우:
        - DB 쓰기, 외부 API 호출 등 되돌릴 수 없는 작업
        - 결제·송금 등 금전 관련 작업
    """
    # NOTE: 선택적 미들웨어의 heavy dependency 로딩을 사용 시점까지 지연
    from langchain.agents.middleware import HumanInTheLoopMiddleware

    return HumanInTheLoopMiddleware(interrupt_on=interrupt_on)
