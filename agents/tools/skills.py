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

from pathlib import Path

from langchain_core.tools import tool

from agents.skills._resolver import resolve_skills_dir

# ── SKILL.md frontmatter 파싱 ──────────────────────────────────


def _parse_frontmatter(content: str) -> dict[str, str]:
    """SKILL.md의 YAML frontmatter를 파싱합니다.

    ``---`` 로 감싼 블록에서 ``key: value`` 쌍을 추출합니다.
    외부 YAML 라이브러리 없이 경량 파싱합니다.
    """
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}

    meta: dict[str, str] = {}
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            meta[key.strip()] = value.strip()
    return meta


def _scan_skills(skills_dir: str | None = None) -> list[dict[str, str]]:
    """스킬 디렉토리를 스캔하여 frontmatter 목록을 반환합니다.

    ``_`` 접두사 디렉토리(__pycache__, _resolver 등)는 건너뜁니다.
    개별 스킬 파일 읽기 실패 시 해당 스킬만 건너뜁니다.

    Note:
        매 호출마다 파일시스템을 스캔합니다. 스킬 수가 많아지면
        ``functools.lru_cache`` 또는 TTL 캐시 도입을 검토하세요.
    """
    root = Path(resolve_skills_dir(skills_dir))
    if not root.is_dir():
        return []

    skills: list[dict[str, str]] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        # _접두사 디렉토리(Python 내부 파일) 하위는 스킬이 아님
        rel = skill_md.relative_to(root)
        if any(part.startswith("_") for part in rel.parts):
            continue

        try:
            content = skill_md.read_text(encoding="utf-8")
        except OSError:
            continue  # 해당 스킬만 건너뜀

        meta = _parse_frontmatter(content)
        if "name" not in meta:
            meta["name"] = skill_md.parent.name
        meta["path"] = str(skill_md.parent.relative_to(root))
        meta["_absolute_path"] = str(skill_md)
        skills.append(meta)
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
        name = s.get("name", "unknown")
        desc = s.get("description", "(설명 없음)")
        lines.append(f"- {name}: {desc}")
    return "\n".join(lines)


@tool
def read_skill(skill_name: str) -> str:
    """특정 스킬의 전체 SKILL.md 내용을 읽습니다.

    Args:
        skill_name: 읽을 스킬의 이름 (list_skills에서 확인).
    """
    skills = _scan_skills()
    for s in skills:
        if s.get("name") == skill_name:
            skill_path = Path(s["_absolute_path"])
            if skill_path.is_file():
                return skill_path.read_text(encoding="utf-8")
            return f"스킬 파일을 찾을 수 없습니다: {skill_path}"

    available = ", ".join(s.get("name", "?") for s in skills) or "(없음)"
    return f"'{skill_name}' 스킬을 찾을 수 없습니다. 사용 가능: {available}"
