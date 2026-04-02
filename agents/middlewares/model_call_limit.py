"""미들웨어: 모델 호출 제한 — API 비용 및 무한루프 방지.

모델 API 호출 횟수를 제한하여 비용을 통제하고,
에이전트가 무한 루프에 빠지는 것을 방지합니다.

사용법:
    from agents.middlewares import create_model_call_limit_middleware

    agent = create_deep_agent(
        middleware=[create_model_call_limit_middleware(run_limit=10)],
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from langchain.agents.middleware.types import AgentMiddleware


def create_model_call_limit_middleware(
    *,
    thread_limit: int | None = None,
    run_limit: int | None = None,
    exit_behavior: Literal["end", "error"] = "end",
) -> AgentMiddleware:
    """모델 호출 제한 미들웨어를 생성합니다.

    Args:
        thread_limit: 스레드 전체에서 허용하는 최대 모델 호출 수.
        run_limit: 단일 실행(invoke)에서 허용하는 최대 모델 호출 수.
        exit_behavior: 제한 도달 시 동작.
            "end" → 마지막 응답을 반환하며 종료 (기본값).
            "error" → 예외 발생.

    적합한 경우:
        - API 비용 상한 설정
        - 테스트 환경에서 호출 수 제한
        - 에이전트 무한루프 방지
    """
    if thread_limit is None and run_limit is None:
        raise ValueError("thread_limit 또는 run_limit 중 하나는 반드시 지정해야 합니다.")

    # NOTE: 선택적 미들웨어의 heavy dependency 로딩을 사용 시점까지 지연
    from langchain.agents.middleware import ModelCallLimitMiddleware

    kwargs: dict[str, Any] = {"exit_behavior": exit_behavior}
    if thread_limit is not None:
        kwargs["thread_limit"] = thread_limit
    if run_limit is not None:
        kwargs["run_limit"] = run_limit

    return ModelCallLimitMiddleware(**kwargs)
