"""에이전트 스킬 모음.

SKILL.md 기반의 재사용 가능한 스킬을 정의합니다.
각 스킬은 하위 디렉토리에 SKILL.md 파일로 배치합니다.

사용법:
    from agents.skills import resolve_skills_dir
"""

from __future__ import annotations

from agents.skills._resolver import resolve_skills_dir

__all__: list[str] = [
    "resolve_skills_dir",
]
