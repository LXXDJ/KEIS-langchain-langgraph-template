"""미들웨어: Human-in-the-Loop — 도구 실행 전 사람 승인.

고위험 도구 호출(DB 쓰기, 결제 등)을 실행하기 전에
사람의 승인·수정·거부를 받을 수 있습니다.

사용법:
    from agents.middlewares import create_hitl_middleware

    agent = create_deep_agent(
        middleware=[create_hitl_middleware(
            interrupt_on={"execute_sql": ["approve", "edit", "reject"]},
        )],
        checkpointer=MemorySaver(),  # 상태 유지 필수
    )
"""

from __future__ import annotations

from typing import Any


def create_hitl_middleware(
    *,
    interrupt_on: dict[str, list[str]],
) -> Any:
    """Human-in-the-Loop 미들웨어를 생성합니다.

    Args:
        interrupt_on: 도구별 중단 옵션 매핑.
            키 = 도구 이름, 값 = 허용 옵션 리스트.
            옵션: "approve" (승인), "edit" (수정), "reject" (거부).

    Note:
        반드시 checkpointer와 함께 사용해야 합니다.
        checkpointer 없이는 중단된 상태를 복원할 수 없습니다.

    적합한 경우:
        - DB 쓰기, 외부 API 호출 등 되돌릴 수 없는 작업
        - 결제·송금 등 금전 관련 작업
    """
    from langchain.middleware import HumanInTheLoopMiddleware

    return HumanInTheLoopMiddleware(interrupt_on=interrupt_on)
