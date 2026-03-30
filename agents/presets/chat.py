"""Preset: chat — langchain create_agent() 기반 대화형 에이전트."""

from __future__ import annotations

from typing import Any, Sequence

from langgraph.graph.state import CompiledStateGraph


def build_chat(
    *,
    model: str | Any = "openai:gpt-4o-mini",
    tools: Sequence[Any] | None = None,
    system_prompt: str | None = None,
    middleware: Sequence[Any] = (),
    name: str | None = "lcdaf_chat",
    **kwargs: Any,
) -> CompiledStateGraph:
    """langchain.agents.create_agent() 래퍼.

    생태계 내장 기능(미들웨어, response_format 등)을 그대로 활용합니다.
    """
    from langchain.agents import create_agent

    return create_agent(
        model=model,
        tools=list(tools or []),
        system_prompt=system_prompt or "You are a helpful assistant.",
        middleware=middleware,
        name=name,
        **kwargs,
    )
