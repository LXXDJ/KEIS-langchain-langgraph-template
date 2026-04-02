"""미들웨어: LLM 도구 에뮬레이터 — 실제 도구 대신 LLM으로 응답 생성.

도구 구현이 완료되지 않았거나, 테스트 환경에서
실제 외부 API를 호출하지 않고 에이전트 워크플로우를 검증할 때 사용합니다.

사용법:
    from agents.middlewares import create_tool_emulator_middleware

    agent = create_deep_agent(
        middleware=[create_tool_emulator_middleware(
            tools=["search_web", "execute_sql"],
        )],
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain.agents.middleware.types import AgentMiddleware


def create_tool_emulator_middleware(
    *,
    tools: list[str] | None = None,
    model: str = "openai:gpt-4o-mini",
) -> AgentMiddleware:
    """LLM 도구 에뮬레이터 미들웨어를 생성합니다.

    Args:
        tools: 에뮬레이션할 도구 이름 목록. None이면 모든 도구를 에뮬레이션.
        model: 에뮬레이션 응답 생성에 사용할 모델 식별자.

    적합한 경우:
        - 도구 구현 전 에이전트 워크플로우 프로토타이핑
        - 외부 API 비용 없이 통합 테스트
        - 에이전트의 도구 선택 로직 검증
    """
    # NOTE: 선택적 미들웨어의 heavy dependency 로딩을 사용 시점까지 지연
    from langchain.agents.middleware import LLMToolEmulator

    kwargs: dict[str, Any] = {"model": model}
    if tools is not None:
        kwargs["tools"] = tools

    return LLMToolEmulator(**kwargs)
