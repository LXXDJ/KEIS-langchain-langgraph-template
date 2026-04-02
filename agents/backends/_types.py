"""백엔드 공통 타입 정의."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Union

from deepagents.backends.protocol import BackendProtocol

# rt: deepagents.runtime.ToolRuntime (서드파티 타입이 공개되지 않아 Any 사용)
BackendFactory = Callable[[Any], BackendProtocol]
"""런타임(ToolRuntime)을 받아 BackendProtocol 인스턴스를 반환하는 팩토리."""

Backend = Union[BackendProtocol, BackendFactory]
"""백엔드 팩토리 함수들의 반환 타입 유니언.

create_filesystem_backend(), create_local_shell_backend()는 BackendProtocol 인스턴스를,
create_composite_backend(), create_store_backend()는 BackendFactory를 반환합니다.
create_deep_agent(backend=...)는 두 타입 모두 허용합니다.
"""
