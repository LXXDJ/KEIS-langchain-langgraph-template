"""Preset: deep_research — deepagents create_deep_agent() 기반 리서치 에이전트."""

from __future__ import annotations

from typing import Any, Sequence

from langgraph.graph.state import CompiledStateGraph


def build_deep_research(
    *,
    model: str | Any = "openai:gpt-4o-mini",
    tools: Sequence[Any] | None = None,
    system_prompt: str | None = None,
    middleware: Sequence[Any] = (),
    subagents: list[Any] | None = None,
    skills: list[str] | None = None,
    memory: list[str] | None = None,
    name: str | None = "lcdaf_deep_research",
    **kwargs: Any,
) -> CompiledStateGraph:
    """deepagents.create_deep_agent() 래퍼.

    planning, filesystem, subagent, summarization 등
    deep research에 필요한 미들웨어 스택이 자동 구성됩니다.
    """
    from deepagents import create_deep_agent

    return create_deep_agent(
        model=model,
        tools=list(tools or []),
        system_prompt=system_prompt or (
            "You are a deep research assistant. "
            "Plan carefully, use tools when useful, "
            "and produce structured answers."
        ),
        middleware=middleware,
        subagents=subagents,
        skills=skills,
        memory=memory,
        name=name,
        **kwargs,
    )
