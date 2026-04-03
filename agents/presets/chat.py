"""Preset: chat — langchain create_agent() 기반 대화형 에이전트."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langgraph.graph.state import CompiledStateGraph


def build_chat(
    *,
    model: str | Any = "openai:gpt-4o-mini",
    tools: Sequence[Any] | None = None,
    system_prompt: str | None = None,
    middleware: Sequence[Any] = (),
    include_skill_tools: bool = False,
    name: str | None = "chat",
    **kwargs: Any,
) -> CompiledStateGraph:
    """langchain.agents.create_agent() 래퍼.

    생태계 내장 기능(미들웨어, response_format 등)을 그대로 활용합니다.

    Args:
        tools: 에이전트에 전달할 도구 목록. None이면 빈 리스트.
            ``agents.tools.examples`` 에 즉시 사용 가능한 예시 도구가 있습니다::

                from agents.tools import get_current_time, search_database
                build_chat(tools=[get_current_time, search_database])

        include_skill_tools: True이면 list_skills, read_skill 도구를
            자동으로 tools에 추가합니다. 기본값 False (opt-in).
    """
    from langchain.agents import create_agent

    all_tools = list(tools or [])

    if include_skill_tools:
        from agents.tools import list_skills, read_skill

        all_tools.extend([list_skills, read_skill])

    return create_agent(
        model=model,
        tools=all_tools,
        system_prompt=system_prompt or "You are a helpful assistant.",
        middleware=middleware,
        name=name,
        **kwargs,
    )
