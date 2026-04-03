"""agents 패키지 내부 공통 유틸리티.

여러 하위 모듈(backends, skills 등)에서 공유하는 헬퍼 함수를 정의합니다.
"""

from __future__ import annotations

from pathlib import Path


def find_project_root() -> Path:
    """langgraph.json이 위치한 디렉토리를 프로젝트 루트로 결정합니다.

    현재 디렉토리에서 상위로 올라가며 langgraph.json을 탐색합니다.
    찾지 못하면 CWD를 반환합니다.
    """
    current = Path.cwd().resolve()
    for parent in (current, *current.parents):
        if (parent / "langgraph.json").exists():
            return parent
    return current
