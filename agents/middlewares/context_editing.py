"""미들웨어: 컨텍스트 편집 — 오래된 도구 출력 정리.

도구 호출이 많아질수록 컨텍스트가 불어나는데,
오래된 도구 결과를 자동으로 정리해서 토큰을 절약합니다.

사용법:
    from agents.middlewares import create_context_editing_middleware

    agent = create_deep_agent(
        middleware=[create_context_editing_middleware()],
    )
"""

from __future__ import annotations

from typing import Any


def create_context_editing_middleware(
    *,
    trigger: int = 4000,
    keep: int = 3,
    clear_tool_inputs: bool = False,
    exclude_tools: list[str] | None = None,
    placeholder: str = "[이전 도구 출력 생략]",
    token_count_method: str = "approximate",
) -> Any:
    """컨텍스트 편집 미들웨어를 생성합니다.

    Args:
        trigger: 정리를 시작할 토큰 수 임계값.
        keep: 유지할 최근 도구 결과 개수.
        clear_tool_inputs: True면 도구 입력 파라미터도 제거.
        exclude_tools: 정리 대상에서 제외할 도구 이름 목록.
        placeholder: 제거된 도구 출력 대체 텍스트.
        token_count_method: 토큰 계산 방식 ("approximate" 또는 "model").

    적합한 경우:
        - 도구를 빈번하게 호출하는 에이전트
        - Summarization과 조합하여 컨텍스트 이중 관리
    """
    from langchain.middleware import ContextEditingMiddleware
    from langchain.middleware.context_editing import ClearToolUsesEdit

    edit = ClearToolUsesEdit(
        trigger=trigger,
        keep=keep,
        clear_tool_inputs=clear_tool_inputs,
        exclude_tools=exclude_tools or [],
        placeholder=placeholder,
    )

    return ContextEditingMiddleware(
        edits=[edit],
        token_count_method=token_count_method,
    )
