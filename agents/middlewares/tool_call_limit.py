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

from typing import Any, Literal


def create_tool_call_limit_middleware(
    *,
    tool_name: str | None = None,
    thread_limit: int | None = None,
    run_limit: int | None = None,
    exit_behavior: Literal["continue", "error", "end"] = "continue",
) -> Any:
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
    from langchain.middleware import ToolCallLimitMiddleware

    kwargs: dict[str, Any] = {"exit_behavior": exit_behavior}
    if tool_name is not None:
        kwargs["tool_name"] = tool_name
    if thread_limit is not None:
        kwargs["thread_limit"] = thread_limit
    if run_limit is not None:
        kwargs["run_limit"] = run_limit

    return ToolCallLimitMiddleware(**kwargs)
