"""미들웨어: LLM 도구 선택기 — 관련 도구만 필터링.

에이전트에 등록된 도구가 많을 때, 매 호출마다 LLM이
질문과 관련된 도구만 선별하여 메인 모델에 전달합니다.

사용법:
    from agents.middlewares import create_tool_selector_middleware

    agent = create_deep_agent(
        middleware=[create_tool_selector_middleware(max_tools=5)],
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain.agents.middleware.types import AgentMiddleware


def create_tool_selector_middleware(
    *,
    model: str = "openai:gpt-4o-mini",
    max_tools: int = 5,
    always_include: list[str] | None = None,
    system_prompt: str | None = None,
) -> AgentMiddleware:
    """LLM 도구 선택기 미들웨어를 생성합니다.

    Args:
        model: 도구 선택에 사용할 모델 식별자.
        max_tools: 메인 모델에 전달할 최대 도구 수.
        always_include: 필터링에서 제외할 도구 이름 목록 (항상 포함).
        system_prompt: 도구 선택 기준에 대한 커스텀 프롬프트.

    적합한 경우:
        - 도구가 10개 이상인 에이전트
        - 질문마다 관련 도구가 달라지는 경우
        - 불필요한 도구가 모델 컨텍스트를 차지하는 문제 해결
    """
    # NOTE: 선택적 미들웨어의 heavy dependency 로딩을 사용 시점까지 지연
    from langchain.agents.middleware import LLMToolSelectorMiddleware

    kwargs: dict[str, Any] = {
        "model": model,
        "max_tools": max_tools,
    }
    if always_include is not None:
        kwargs["always_include"] = always_include
    if system_prompt is not None:
        kwargs["system_prompt"] = system_prompt

    return LLMToolSelectorMiddleware(**kwargs)
