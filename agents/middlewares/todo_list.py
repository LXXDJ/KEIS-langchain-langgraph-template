"""미들웨어: To-Do 리스트 — 에이전트에게 작업 계획 능력 부여.

에이전트가 복잡한 작업을 하위 단계로 분해하고,
진행 상황을 추적할 수 있는 write_todos 도구를 제공합니다.

사용법:
    from agents.middlewares import create_todo_list_middleware

    agent = create_deep_agent(
        middleware=[create_todo_list_middleware()],
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain.agents.middleware.types import AgentMiddleware


def create_todo_list_middleware(
    *,
    system_prompt: str | None = None,
    tool_description: str | None = None,
) -> AgentMiddleware:
    """To-Do 리스트 미들웨어를 생성합니다.

    Args:
        system_prompt: 작업 계획에 대한 커스텀 시스템 프롬프트.
        tool_description: write_todos 도구의 커스텀 설명.

    적합한 경우:
        - 복잡한 멀티스텝 워크플로우
        - 에이전트가 계획을 세우고 단계별로 실행해야 할 때
        - 작업 진행률 추적이 필요한 경우
    """
    # NOTE: 선택적 미들웨어의 heavy dependency 로딩을 사용 시점까지 지연
    from langchain.agents.middleware import TodoListMiddleware

    kwargs: dict[str, object] = {}
    if system_prompt is not None:
        kwargs["system_prompt"] = system_prompt
    if tool_description is not None:
        kwargs["tool_description"] = tool_description

    return TodoListMiddleware(**kwargs)
