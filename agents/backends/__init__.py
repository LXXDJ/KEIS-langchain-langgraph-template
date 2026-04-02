"""백엔드 팩토리 모음.

자주 쓰는 백엔드 조합을 async 팩토리 함수로 제공합니다.
create_deep_agent(backend=create_*_backend()) 형태로 사용합니다.

사용법:
    from agents.backends import create_filesystem_backend, create_composite_backend
"""

from __future__ import annotations

from agents.backends.composite import create_composite_backend
from agents.backends.filesystem import create_filesystem_backend
from agents.backends.local_shell import create_local_shell_backend
from agents.backends.store import create_store_backend

__all__: list[str] = [
    "create_composite_backend",
    "create_filesystem_backend",
    "create_local_shell_backend",
    "create_store_backend",
]
