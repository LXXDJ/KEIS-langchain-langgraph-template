"""백엔드 공통 기본값."""

from __future__ import annotations

import os
from pathlib import Path

_OUTPUT_DIR_NAME = "outputs"
_ENV_KEY = "AGENT_OUTPUT_DIR"


def _find_project_root() -> Path:
    """langgraph.json이 위치한 디렉토리를 프로젝트 루트로 결정합니다.

    현재 디렉토리에서 상위로 올라가며 langgraph.json을 탐색합니다.
    찾지 못하면 CWD를 반환합니다.
    """
    current = Path.cwd().resolve()
    for parent in (current, *current.parents):
        if (parent / "langgraph.json").exists():
            return parent
    return current


def resolve_output_dir(root_dir: str | None = None) -> str:
    """백엔드가 사용할 출력 디렉토리 경로를 결정합니다.

    경로만 결정하며, 디렉토리를 즉시 생성하지 않습니다.
    실제 생성이 필요하면 ``ensure_output_dir()``를 사용하세요.

    우선순위:
        1. 인자로 명시한 root_dir
        2. 환경변수 AGENT_OUTPUT_DIR
        3. {프로젝트 루트}/outputs  (langgraph.json 기준)
    """
    if root_dir is not None:
        path = Path(root_dir)
    elif env := os.getenv(_ENV_KEY):
        path = Path(env)
    else:
        path = _find_project_root() / _OUTPUT_DIR_NAME

    return str(path)


def ensure_output_dir(path: str) -> None:
    """출력 디렉토리가 존재하지 않으면 생성합니다.

    백엔드가 실제로 파일 I/O를 수행하기 직전에 호출하세요.
    """
    Path(path).mkdir(parents=True, exist_ok=True)
