"""Example: official deepagents create_deep_agent() usage."""

from __future__ import annotations

from deepagents import create_deep_agent


def build_graph(*, model, tools=None, system_prompt: str | None = None, **kwargs):
    return create_deep_agent(
        model=model,
        tools=list(tools or []),
        system_prompt=system_prompt or (
            "You are a deep research assistant. Plan carefully, use tools when "
            "useful, and produce structured answers."
        ),
        **kwargs,
    )
