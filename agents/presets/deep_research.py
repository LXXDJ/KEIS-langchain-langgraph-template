"""Preset: deep_research — deepagents create_deep_agent() 기반 리서치 에이전트."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from agents.backends import create_filesystem_backend


def build_deep_research(
    *,
    model: str | Any = "openai:gpt-4o-mini",
    tools: Sequence[Any] | None = None,
    system_prompt: str | None = None,
    middleware: Sequence[Any] = (),
    backend: Any | None = None,
    subagents: list[Any] | None = None,
    skills: list[str] | None = None,
    memory: list[str] | None = None,
    name: str | None = "deep_research",
    **kwargs: Any,
) -> CompiledStateGraph:
    """deepagents.create_deep_agent() 래퍼.

    planning, filesystem, subagent, summarization 등
    deep research에 필요한 미들웨어 스택이 자동 구성됩니다.

    Args:
        backend: 백엔드 인스턴스 또는 팩토리 함수.
            None이면 create_filesystem_backend() 사용 (→ {프로젝트루트}/outputs/).
            다른 백엔드로 교체 시:
                from agents.backends import create_composite_backend, create_store_backend
                build_deep_research(backend=create_composite_backend())
                build_deep_research(backend=create_store_backend())
    """
    # NOTE: 지연 임포트 — deepagents는 무거운 서드파티이므로 호출 시점에 로드
    from deepagents import create_deep_agent

    build_kwargs: dict[str, Any] = {
        "model": model,
        "tools": list(tools or []),
        "system_prompt": system_prompt or (
            "You are a deep research assistant. "
            "Plan carefully, use tools when useful, "
            "and produce structured answers."
        ),
        "middleware": middleware,
        "subagents": subagents,
        "skills": skills,
        "memory": memory,
        "name": name,
        **kwargs,
    }

    if backend is None:
        backend = create_filesystem_backend()

    build_kwargs["backend"] = backend

    return create_deep_agent(**build_kwargs)
