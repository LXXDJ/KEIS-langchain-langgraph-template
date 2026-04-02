"""백엔드 공통 타입 정의."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from deepagents.backends.protocol import BackendProtocol

BackendFactory = Callable[[Any], BackendProtocol]
"""런타임(ToolRuntime)을 받아 BackendProtocol 인스턴스를 반환하는 팩토리."""
