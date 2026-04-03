"""스킬 경로 해석 유틸리티."""

from __future__ import annotations

import os
from pathlib import Path

from agents._utils import find_project_root

_SKILLS_DIR_NAME = os.path.join("agents", "skills")
_ENV_KEY = "AGENT_SKILLS_DIR"


def resolve_skills_dir(skills_dir: str | None = None) -> str:
    """스킬 디렉토리 경로를 결정합니다.

    우선순위:
        1. 인자로 명시한 skills_dir
        2. 환경변수 AGENT_SKILLS_DIR
        3. {프로젝트 루트}/agents/skills  (langgraph.json 기준)
    """
    if skills_dir is not None:
        path = Path(skills_dir)
    elif env := os.getenv(_ENV_KEY):
        path = Path(env)
    else:
        path = find_project_root() / _SKILLS_DIR_NAME

    return str(path.resolve())
