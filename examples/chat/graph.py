"""Example: official LangChain create_agent() usage."""

from __future__ import annotations

from langchain.agents import create_agent


def build_graph(*, model, tools=None, system_prompt: str | None = None, **kwargs):
    return create_agent(
        model=model,
        tools=list(tools or []),
        system_prompt=system_prompt or "You are a practical chat assistant.",
        **kwargs,
    )
