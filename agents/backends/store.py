"""백엔드: LangGraph BaseStore 기반 크로스스레드 영속 저장.

langgraph의 InMemoryStore 또는 외부 스토어와 함께 사용합니다.

사용법:
    from agents.backends import create_store_backend
    from langgraph.store.memory import InMemoryStore

    agent = create_deep_agent(
        backend=create_store_backend(),
        store=InMemoryStore(),
    )
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from deepagents.backends import StoreBackend
from deepagents.backends.protocol import BackendProtocol

# ── 타입 정의 ────────────────────────────────────────────────

BackendFactory = Callable[[Any], BackendProtocol]


def create_store_backend(
    namespace: Any | None = None,
) -> BackendFactory:
    """LangGraph BaseStore 기반 크로스스레드 영속 백엔드를 생성합니다.

    langgraph의 InMemoryStore 또는 외부 스토어와 함께 사용합니다.
    create_deep_agent(store=InMemoryStore()) 와 함께 전달하세요.

    Args:
        namespace: 네임스페이스 팩토리 함수. None이면 기본 네임스페이스 사용.

    적합한 경우:
        - 대화 간 데이터가 유지되어야 할 때
        - 멀티 스레드 환경에서 상태 공유가 필요할 때

    Returns:
        BackendFactory (런타임을 받는 callable).
    """

    def factory(rt: Any) -> BackendProtocol:
        kwargs: dict[str, Any] = {}
        if namespace is not None:
            kwargs["namespace"] = namespace
        return StoreBackend(rt, **kwargs)

    return factory
