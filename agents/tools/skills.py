"""스킬 도구 — 에이전트가 SKILL.md를 탐색하고 읽을 수 있는 도구.

Progressive disclosure 패턴으로 동작합니다:
1. ``list_skills`` — frontmatter(이름, 설명)만 반환하여 토큰 절약
2. ``read_skill`` — 특정 스킬의 전체 내용을 반환

모든 preset(custom, chat, deep_research)에서 범용으로 사용 가능합니다.

사용법:
    from agents.tools import list_skills, read_skill

    agent = create_agent(
        tools=[list_skills, read_skill, ...],
    )
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.tools import BaseTool, tool

from agents.skills._resolver import resolve_skills_dir

_log = logging.getLogger(__name__)
_MAX_SKILL_BYTES = 64 * 1024

# ── 스킬 메타데이터 ──────────────────────────────────────────


@dataclass(frozen=True)
class _SkillMeta:
    """스킬 메타데이터. 공개 정보와 내부 경로를 분리합니다."""

    name: str
    description: str
    path: str
    _absolute_path: str = field(repr=False)

    def exists(self) -> bool:
        """SKILL.md 파일이 존재하는지 확인합니다."""
        return Path(self._absolute_path).is_file()

    def read_content(self) -> str:
        """SKILL.md 파일 전체 내용을 반환합니다.

        64KB를 초과하면 경고 로그를 남깁니다.
        """
        content = Path(self._absolute_path).read_text(encoding="utf-8")
        if len(content.encode()) > _MAX_SKILL_BYTES:
            _log.warning(
                "SKILL.md가 %d bytes를 초과합니다: %s",
                _MAX_SKILL_BYTES, self.path,
            )
        return content


# ── SKILL.md frontmatter 파싱 ──────────────────────────────────


def _parse_frontmatter(content: str) -> dict[str, str]:
    """SKILL.md의 YAML frontmatter를 파싱합니다.

    ``---`` 로 감싼 블록에서 ``key: value`` 쌍을 추출합니다.
    외부 YAML 라이브러리 없이 경량 파싱합니다.
    닫는 ``---`` 가 없으면 경고 로그를 남깁니다.
    """
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}

    meta: dict[str, str] = {}
    closed = False
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            closed = True
            break
        if ":" in stripped and not stripped.startswith("#"):
            key, _, value = stripped.partition(":")
            meta[key.strip()] = value.strip()

    if not closed and meta:
        _log.warning(
            "frontmatter가 닫히지 않았습니다: "
            "일부 내용이 메타데이터로 파싱될 수 있습니다. keys=%s",
            list(meta),
        )

    return meta


# ── TTL 캐시 ─────────────────────────────────────────────────

_TTL_SECONDS = 60
_cache: tuple[float, str, list[_SkillMeta]] | None = None
# NOTE: 현재 asyncio 단일 스레드 환경을 전제합니다.
# 멀티스레드 워커(gunicorn 등) 도입 시 threading.Lock 추가를 검토하세요.


def _invalidate_cache() -> None:
    """테스트 등에서 캐시를 수동으로 초기화합니다."""
    global _cache  # noqa: PLW0603
    _cache = None


# ── 스킬 스캔 ────────────────────────────────────────────────


def _scan_skills(skills_dir: str | None = None) -> list[_SkillMeta]:
    """스킬 디렉토리를 스캔하여 메타데이터 목록을 반환합니다.

    ``skills/{skill-name}/SKILL.md`` 구조(1단계 깊이)만 인식합니다.
    ``_`` 접두사 디렉토리(__pycache__ 등)는 건너뜁니다.
    개별 스킬 파일 읽기 실패 시 해당 스킬만 건너뜁니다.
    symlink로 root 밖을 가리키는 경로는 건너뜁니다.

    기본 경로(skills_dir=None)로 호출 시 결과를 60초간 캐싱합니다.
    """
    global _cache  # noqa: PLW0603

    resolved_dir = resolve_skills_dir(skills_dir)

    # TTL 캐시 — 기본 경로일 때만 적용
    # 환경변수 변경 등으로 resolved_dir이 달라지면 cached_dir 비교에서
    # 캐시 미스가 발생하여 자동으로 재스캔됩니다.
    now = time.monotonic()
    if skills_dir is None and _cache is not None:
        cached_time, cached_dir, cached_result = _cache
        if cached_dir == resolved_dir and now - cached_time < _TTL_SECONDS:
            return cached_result

    root = Path(resolved_dir)
    if not root.is_dir():
        return []

    skills: list[_SkillMeta] = []

    # 1단계 깊이만 탐색: skills/{skill-name}/SKILL.md
    for skill_md in sorted(root.glob("*/SKILL.md")):
        # _접두사 디렉토리(__pycache__ 등)는 스킬이 아님
        if skill_md.parent.name.startswith("_"):
            continue

        # symlink 등으로 root 밖을 가리키는 경우 건너뜀
        if not skill_md.resolve().is_relative_to(root.resolve()):
            continue

        try:
            content = skill_md.read_text(encoding="utf-8")
        except OSError:
            continue  # 해당 스킬만 건너뜀

        meta = _parse_frontmatter(content)
        skills.append(_SkillMeta(
            name=meta.get("name", skill_md.parent.name),
            description=meta.get("description", "(설명 없음)"),
            path=skill_md.parent.name,
            _absolute_path=str(skill_md),
        ))

    # 캐시 저장 — 기본 경로일 때만
    if skills_dir is None:
        _cache = (now, resolved_dir, skills)

    return skills


# ── 공개 도구 ─────────────────────────────────────────────────


@tool
def list_skills() -> str:
    """사용 가능한 스킬 목록을 조회합니다.

    각 스킬의 이름과 설명만 반환합니다 (경량 조회).
    상세 내용이 필요하면 read_skill을 호출하세요.
    """
    skills = _scan_skills()
    if not skills:
        return "등록된 스킬이 없습니다."

    lines: list[str] = []
    for s in skills:
        lines.append(f"- {s.name}: {s.description}")
    return "\n".join(lines)


@tool
def read_skill(skill_name: str) -> str:
    """특정 스킬의 전체 SKILL.md 내용을 읽습니다.

    Args:
        skill_name: 읽을 스킬의 이름 (list_skills에서 확인).
    """
    # skill_name은 _scan_skills()가 반환한 목록에서만 매칭되므로
    # 경로 순회(../) 공격은 불가능합니다 (symlink 검증은 _scan_skills 내부에서 수행).
    skills = _scan_skills()
    for s in skills:
        if s.name == skill_name:
            if s.exists():
                return s.read_content()
            return f"스킬 파일을 찾을 수 없습니다: {s.path}"

    available = ", ".join(s.name for s in skills) or "(없음)"
    return f"'{skill_name}' 스킬을 찾을 수 없습니다. 사용 가능: {available}"
