"""agents/tools/skills 도구 및 agents/skills/_resolver 단위 테스트.

검증 항목
---------
1. resolve_skills_dir — 경로 해석 우선순위 (인자 > 환경변수 > langgraph.json 기준)
2. _parse_frontmatter — YAML frontmatter 파싱
3. _scan_skills — 디렉토리 스캔 및 메타데이터 수집
4. list_skills — 스킬 목록 조회 (도구 호출)
5. read_skill — 스킬 상세 내용 읽기 (도구 호출)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.skills._resolver import resolve_skills_dir
from agents.tools.skills import (
    _SkillMeta,
    _invalidate_cache,
    _parse_frontmatter,
    _scan_skills,
    list_skills,
    read_skill,
)


# ── 픽스처 ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_cache():
    """매 테스트 전후 스킬 스캔 캐시를 초기화합니다."""
    _invalidate_cache()
    yield
    _invalidate_cache()


@pytest.fixture()
def skills_dir(tmp_path: Path) -> Path:
    """테스트용 스킬 디렉토리를 생성합니다."""
    # 스킬 A
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: 알파 스킬입니다.\n---\n\n# Alpha\n\n상세 내용.",
        encoding="utf-8",
    )

    # 스킬 B (description 없음)
    (tmp_path / "beta").mkdir()
    (tmp_path / "beta" / "SKILL.md").write_text(
        "---\nname: beta\n---\n\n# Beta\n\n설명 없는 스킬.",
        encoding="utf-8",
    )

    # 스킬 C (frontmatter 없음 — name은 디렉토리명에서 유추)
    (tmp_path / "gamma").mkdir()
    (tmp_path / "gamma" / "SKILL.md").write_text(
        "# Gamma\n\nfrontmatter가 없는 스킬.",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture()
def empty_skills_dir(tmp_path: Path) -> Path:
    """빈 스킬 디렉토리를 생성하여 반환합니다."""
    d = tmp_path / "empty_skills"
    d.mkdir()
    return d


# ── resolve_skills_dir ─────────────────────────────────────────


class TestResolveSkillsDir:
    """resolve_skills_dir 경로 해석 테스트."""

    def test_explicit_arg(self) -> None:
        result = resolve_skills_dir("/custom/skills")
        assert result == str(Path("/custom/skills").resolve())

    def test_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENT_SKILLS_DIR", "/env/skills")
        result = resolve_skills_dir()
        assert result == str(Path("/env/skills").resolve())

    def test_env_var_overridden_by_arg(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENT_SKILLS_DIR", "/env/skills")
        result = resolve_skills_dir("/explicit/skills")
        assert result == str(Path("/explicit/skills").resolve())

    def test_default_uses_project_root(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AGENT_SKILLS_DIR", raising=False)
        result = resolve_skills_dir()
        assert result.endswith("skills")


# ── _parse_frontmatter ─────────────────────────────────────────


class TestParseFrontmatter:
    """YAML frontmatter 파서 테스트."""

    def test_basic(self) -> None:
        content = "---\nname: test\ndescription: 테스트\n---\n\nbody"
        meta = _parse_frontmatter(content)
        assert meta["name"] == "test"
        assert meta["description"] == "테스트"

    def test_no_frontmatter(self) -> None:
        content = "# No Frontmatter\n\nbody"
        meta = _parse_frontmatter(content)
        assert meta == {}

    def test_empty_string(self) -> None:
        assert _parse_frontmatter("") == {}

    def test_value_with_colon(self) -> None:
        content = "---\nname: my-skill\ndescription: 이것은: 콜론이 포함된 설명\n---\n"
        meta = _parse_frontmatter(content)
        assert meta["description"] == "이것은: 콜론이 포함된 설명"

    def test_unclosed_frontmatter(self) -> None:
        """닫는 --- 없으면 빈 dict를 반환합니다 (본문 오파싱 방지)."""
        content = "---\nname: broken\n# This is body\nnot: metadata"
        meta = _parse_frontmatter(content)
        assert meta == {}

    def test_unclosed_frontmatter_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """닫는 --- 없으면 경고 로그가 남습니다."""
        content = "---\nname: broken\n"
        with caplog.at_level("WARNING"):
            _parse_frontmatter(content)
        assert "닫히지 않았습니다" in caplog.text


# ── _scan_skills ───────────────────────────────────────────────


class TestScanSkills:
    """스킬 디렉토리 스캔 테스트."""

    def test_scan_finds_all(self, skills_dir: Path) -> None:
        skills = _scan_skills(str(skills_dir))
        names = {s.name for s in skills}
        assert names == {"alpha", "beta", "gamma"}

    def test_scan_returns_skill_meta(self, skills_dir: Path) -> None:
        """스캔 결과가 _SkillMeta dataclass인지 검증합니다."""
        skills = _scan_skills(str(skills_dir))
        for s in skills:
            assert isinstance(s, _SkillMeta)
            assert s.path  # 디렉토리명
            assert Path(s._absolute_path).is_absolute()  # noqa: SLF001

    def test_scan_ignores_nested_skill_md(self, skills_dir: Path) -> None:
        """glob("*/SKILL.md")로 1단계 깊이만 인식하고, 중첩된 SKILL.md는 무시합니다."""
        nested = skills_dir / "alpha" / "examples"
        nested.mkdir()
        (nested / "SKILL.md").write_text("---\nname: nested\n---\n")
        skills = _scan_skills(str(skills_dir))
        names = {s.name for s in skills}
        assert "nested" not in names

    def test_scan_empty_dir(self, empty_skills_dir: Path) -> None:
        skills = _scan_skills(str(empty_skills_dir))
        assert skills == []

    def test_scan_nonexistent_dir(self) -> None:
        skills = _scan_skills("/nonexistent/path")
        assert skills == []

    def test_no_frontmatter_uses_dirname(self, skills_dir: Path) -> None:
        """frontmatter에 name이 없으면 디렉토리명을 사용합니다."""
        skills = _scan_skills(str(skills_dir))
        gamma = next(s for s in skills if s.name == "gamma")
        assert gamma.path == "gamma"

    def test_scan_skips_underscore_dirs(self, skills_dir: Path) -> None:
        """_접두사 디렉토리는 건너뜁니다."""
        hidden = skills_dir / "_internal"
        hidden.mkdir()
        (hidden / "SKILL.md").write_text("---\nname: hidden\n---\n")
        skills = _scan_skills(str(skills_dir))
        names = {s.name for s in skills}
        assert "hidden" not in names

    def test_cache_reuses_result(self, skills_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """기본 경로 호출 시 캐시가 동작합니다."""
        monkeypatch.setenv("AGENT_SKILLS_DIR", str(skills_dir))
        first = _scan_skills()
        second = _scan_skills()
        assert first is second  # 동일 객체 (캐시)

    def test_cache_expires_after_ttl(
        self, skills_dir: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TTL 만료 후 재스캔이 동작합니다."""
        import agents.tools.skills as skills_mod

        monkeypatch.setenv("AGENT_SKILLS_DIR", str(skills_dir))
        monkeypatch.setattr(skills_mod, "_TTL_SECONDS", 0)
        first = _scan_skills()
        second = _scan_skills()
        assert first is not second  # TTL=0이므로 매번 새 스캔
        assert {s.name for s in first} == {s.name for s in second}


# ── list_skills (도구) ─────────────────────────────────────────


class TestListSkills:
    """list_skills 도구 테스트."""

    def test_returns_skill_list(self, skills_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENT_SKILLS_DIR", str(skills_dir))
        result = list_skills.invoke({})
        assert "alpha" in result
        assert "beta" in result
        assert "gamma" in result

    def test_includes_description(self, skills_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENT_SKILLS_DIR", str(skills_dir))
        result = list_skills.invoke({})
        assert "알파 스킬입니다" in result

    def test_no_description_fallback(
        self, skills_dir: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AGENT_SKILLS_DIR", str(skills_dir))
        result = list_skills.invoke({})
        assert "(설명 없음)" in result

    def test_empty_dir(self, empty_skills_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENT_SKILLS_DIR", str(empty_skills_dir))
        result = list_skills.invoke({})
        assert "등록된 스킬이 없습니다" in result


# ── read_skill (도구) ──────────────────────────────────────────


class TestReadSkill:
    """read_skill 도구 테스트."""

    def test_read_existing_skill(
        self, skills_dir: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AGENT_SKILLS_DIR", str(skills_dir))
        result = read_skill.invoke({"skill_name": "alpha"})
        assert "# Alpha" in result
        assert "상세 내용" in result

    def test_read_returns_full_content(
        self, skills_dir: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """frontmatter 포함 전체 내용이 반환되는지 확인합니다."""
        monkeypatch.setenv("AGENT_SKILLS_DIR", str(skills_dir))
        result = read_skill.invoke({"skill_name": "alpha"})
        assert "---" in result
        assert "name: alpha" in result

    def test_read_nonexistent_skill(
        self, skills_dir: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AGENT_SKILLS_DIR", str(skills_dir))
        result = read_skill.invoke({"skill_name": "nonexistent"})
        assert "찾을 수 없습니다" in result
        assert "alpha" in result  # 사용 가능한 스킬 이름 안내

    def test_read_no_frontmatter_skill(
        self, skills_dir: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AGENT_SKILLS_DIR", str(skills_dir))
        result = read_skill.invoke({"skill_name": "gamma"})
        assert "# Gamma" in result


# ── 도구 메타데이터 검증 ───────────────────────────────────────


class TestToolMetadata:
    """도구가 올바른 LangChain 도구 메타데이터를 갖는지 검증합니다."""

    def test_list_skills_is_tool(self) -> None:
        assert hasattr(list_skills, "invoke")
        assert list_skills.name == "list_skills"

    def test_read_skill_is_tool(self) -> None:
        assert hasattr(read_skill, "invoke")
        assert read_skill.name == "read_skill"

    def test_read_skill_has_args(self) -> None:
        schema = read_skill.args_schema
        assert "skill_name" in schema.model_fields
