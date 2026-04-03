"""미들웨어: 도구 재시도 — 도구 호출 실패 시 지수 백오프 재시도.

외부 API 도구 등에서 일시적 오류가 발생했을 때
자동으로 재시도합니다.

사용법:
    from agents.middlewares import create_tool_retry_middleware

    agent = create_deep_agent(
        middleware=[create_tool_retry_middleware(max_retries=3)],
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from langchain.agents.middleware.types import AgentMiddleware


def create_tool_retry_middleware(
    *,
    max_retries: int = 2,
    tools: list[str] | None = None,
    retry_on: list[type[Exception]] | None = None,
    on_failure: Literal["continue", "error"] = "continue",
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
) -> AgentMiddleware:
    """도구 재시도 미들웨어를 생성합니다.

    Args:
        max_retries: 최대 재시도 횟수.
        tools: 재시도를 적용할 도구 이름 목록. None이면 모든 도구에 적용.
        retry_on: 재시도를 트리거할 예외 타입 목록. None이면 기본 예외 사용.
        on_failure: 모든 재시도 실패 시 동작.
            "continue" → 에이전트가 오류 메시지와 함께 계속 실행 (기본값).
            "error" → 예외 발생.
        backoff_factor: 지수 백오프 배수.
        initial_delay: 첫 재시도까지 대기 시간(초).
        max_delay: 최대 대기 시간 상한(초).
        jitter: True면 랜덤 지터 추가.

    적합한 경우:
        - 외부 API 연동 도구의 네트워크 오류 대비
        - 불안정한 서드파티 서비스 호출
    """
    # NOTE: 선택적 미들웨어의 heavy dependency 로딩을 사용 시점까지 지연
    from langchain.agents.middleware import ToolRetryMiddleware

    kwargs: dict[str, Any] = {
        "max_retries": max_retries,
        "on_failure": on_failure,
        "backoff_factor": backoff_factor,
        "initial_delay": initial_delay,
        "max_delay": max_delay,
        "jitter": jitter,
    }
    if tools is not None:
        kwargs["tools"] = tools
    if retry_on is not None:
        kwargs["retry_on"] = retry_on

    return ToolRetryMiddleware(**kwargs)
