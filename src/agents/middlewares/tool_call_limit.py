"""미들웨어: 도구 호출 제한 — 전체 또는 특정 도구별 횟수 제한.

특정 도구의 과도한 호출을 방지하거나,
전체 도구 호출 횟수를 제한합니다.

사용법:
    from agents.middlewares import create_tool_call_limit_middleware

    agent = create_deep_agent(
        middleware=[create_tool_call_limit_middleware(
            tool_name="search_web",
            run_limit=5,
        )],
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from langchain.agents.middleware.types import AgentMiddleware


def create_tool_call_limit_middleware(
    *,
    tool_name: str | None = None,
    thread_limit: int | None = None,
    run_limit: int | None = None,
    exit_behavior: Literal["continue", "error", "end"] = "continue",
) -> AgentMiddleware:
    """도구 호출 제한 미들웨어를 생성합니다.

    Args:
        tool_name: 제한할 특정 도구 이름. None이면 모든 도구에 적용.
        thread_limit: 스레드 전체에서 허용하는 최대 호출 수.
        run_limit: 단일 실행에서 허용하는 최대 호출 수.
        exit_behavior: 제한 도달 시 동작.
            "continue" → 해당 도구만 비활성화, 에이전트 계속 실행 (기본값).
            "end" → 마지막 응답 반환 후 종료.
            "error" → 예외 발생.

    적합한 경우:
        - 비용이 높은 외부 API 도구의 호출 횟수 제한
        - 특정 도구의 남용 방지
    """
    if thread_limit is None and run_limit is None:
        raise ValueError("thread_limit 또는 run_limit 중 하나는 반드시 지정해야 합니다.")

    # NOTE: 선택적 미들웨어의 heavy dependency 로딩을 사용 시점까지 지연
    from langchain.agents.middleware import ToolCallLimitMiddleware

    kwargs: dict[str, Any] = {"exit_behavior": exit_behavior}
    if tool_name is not None:
        kwargs["tool_name"] = tool_name
    if thread_limit is not None:
        kwargs["thread_limit"] = thread_limit
    if run_limit is not None:
        kwargs["run_limit"] = run_limit

    return ToolCallLimitMiddleware(**kwargs)
