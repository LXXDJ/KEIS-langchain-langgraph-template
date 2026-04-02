"""백엔드: StateBackend(기본) + FilesystemBackend(파일 영역) 조합.

CompositeBackend로 경로 prefix에 따라 백엔드를 라우팅합니다.

사용법:
    from agents.backends import create_composite_backend

    agent = create_deep_agent(backend=create_composite_backend())
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from deepagents.backends.protocol import BackendProtocol

from agents.backends._defaults import resolve_output_dir

# ── 타입 정의 ────────────────────────────────────────────────

BackendFactory = Callable[[Any], BackendProtocol]


def create_composite_backend(
    root_dir: str | None = None,
    memory_prefix: str = "/memories/",
) -> BackendFactory:
    """StateBackend + FilesystemBackend 조합 백엔드를 생성합니다.

    경로 prefix에 따라 백엔드를 라우팅합니다:
        - memory_prefix 경로 → FilesystemBackend (파일 기반 메모리)
        - 그 외 → StateBackend (에이전트 실행 상태)

    Args:
        root_dir: FilesystemBackend 루트 디렉토리. None이면 AGENT_OUTPUT_DIR 또는 ./outputs 사용.
        memory_prefix: 파일시스템으로 라우팅할 경로 접두사.

    지원 연산 (라우팅된 백엔드에 따라 다름):
        FilesystemBackend 영역 — ls, read_file, write_file, edit_file, glob, grep
        StateBackend 영역    — 동일 연산이지만 LangGraph 상태(메모리) 안에서 동작

    ※ 파일 업로드·다운로드는 지원하지 않습니다.
      원격 전송이 필요하면 커스텀 도구(@tool)를 추가하세요.

    적합한 경우:
        - 에이전트가 파일을 읽고 쓰면서, 실행 상태도 유지해야 할 때
        - AGENTS.md 기반 메모리를 사용할 때

    Returns:
        BackendFactory (런타임을 받는 callable).
    """
    resolved = resolve_output_dir(root_dir)

    def factory(rt: Any) -> BackendProtocol:
        return CompositeBackend(
            default=StateBackend(rt),
            routes={
                memory_prefix: FilesystemBackend(
                    root_dir=resolved,
                    virtual_mode=True,
                ),
            },
        )

    return factory
