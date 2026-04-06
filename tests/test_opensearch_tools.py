"""OpenSearch 도구 단위 테스트.

OpenSearch 연결 없이 DSL 빌더, 포맷터, 인덱스 해석 등 순수 함수를 검증합니다.
"""

from __future__ import annotations

import pytest

from agents.tools.opensearch import (
    _VALID_SORT,
    _build_query,
    _format_hit,
    _resolve_index,
)


# ── _resolve_index ────────────────────────────────────────────


class TestResolveIndex:
    """인덱스 해석 테스트."""

    def test_explicit_index(self) -> None:
        assert _resolve_index("my-index") == "my-index"

    def test_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENSEARCH_INDEX", "env-index")
        assert _resolve_index("") == "env-index"

    def test_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENSEARCH_INDEX", raising=False)
        assert _resolve_index("") == ""


# ── _build_query ──────────────────────────────────────────────


class TestBuildQuery:
    """DSL 빌더 테스트."""

    def test_basic_query(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENSEARCH_SORT_FIELD", "created_at")
        body = _build_query("검색어", "", "", "relevance", "", 5)
        assert body["size"] == 5
        assert body["query"]["multi_match"]["query"] == "검색어"
        assert body["query"]["multi_match"]["fields"] == ["*"]
        assert "sort" not in body

    def test_with_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENSEARCH_SORT_FIELD", "created_at")
        body = _build_query("test", "", "", "relevance", "title,body", 5)
        assert body["query"]["multi_match"]["fields"] == ["title", "body"]

    def test_with_filters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENSEARCH_SORT_FIELD", "created_at")
        body = _build_query("test", "status:완료;부서:구매팀", "", "relevance", "", 5)
        filters = body["query"]["bool"]["filter"]
        assert len(filters) == 2
        assert {"term": {"status": "완료"}} in filters
        assert {"term": {"부서": "구매팀"}} in filters

    def test_filter_with_comma_in_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """세미콜론 구분이므로 값에 쉼표가 포함되어도 안전합니다."""
        monkeypatch.setenv("OPENSEARCH_SORT_FIELD", "created_at")
        body = _build_query("test", "설명:구매팀, 2팀", "", "relevance", "", 5)
        filters = body["query"]["bool"]["filter"]
        assert {"term": {"설명": "구매팀, 2팀"}} in filters

    def test_with_date_range(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENSEARCH_SORT_FIELD", "created_at")
        body = _build_query("test", "", "created_at:2026-01-01~2026-03-31", "relevance", "", 5)
        filters = body["query"]["bool"]["filter"]
        assert len(filters) == 1
        assert filters[0] == {"range": {"created_at": {"gte": "2026-01-01", "lte": "2026-03-31"}}}

    def test_date_range_gte_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENSEARCH_SORT_FIELD", "created_at")
        body = _build_query("test", "", "created_at:2026-01-01~", "relevance", "", 5)
        range_filter = body["query"]["bool"]["filter"][0]
        assert range_filter == {"range": {"created_at": {"gte": "2026-01-01"}}}

    def test_sort_recent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENSEARCH_SORT_FIELD", "created_at")
        body = _build_query("test", "", "", "recent", "", 5)
        assert "sort" in body
        assert body["sort"][1]["created_at"]["order"] == "desc"

    def test_sort_oldest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENSEARCH_SORT_FIELD", "created_at")
        body = _build_query("test", "", "", "oldest", "", 5)
        assert body["sort"][0]["created_at"]["order"] == "asc"

    def test_sort_custom_field(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OPENSEARCH_SORT_FIELD로 정렬 필드를 변경할 수 있습니다."""
        monkeypatch.setenv("OPENSEARCH_SORT_FIELD", "updated_at")
        body = _build_query("test", "", "", "recent", "", 5)
        assert "updated_at" in body["sort"][1]

    def test_top_k_capped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENSEARCH_SORT_FIELD", "created_at")
        body = _build_query("test", "", "", "relevance", "", 100)
        assert body["size"] == 20

    def test_combined_filters_and_date(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENSEARCH_SORT_FIELD", "created_at")
        body = _build_query(
            "test", "status:완료", "created_at:2026-01-01~2026-12-31", "relevance", "", 5,
        )
        filters = body["query"]["bool"]["filter"]
        assert len(filters) == 2


# ── _format_hit ───────────────────────────────────────────────


class TestFormatHit:
    """결과 포맷 테스트."""

    def test_basic_format(self) -> None:
        hit = {"_score": 1.5, "_source": {"title": "제목", "body": "내용"}}
        result = _format_hit(1, hit)
        assert "1." in result
        assert "score=1.50" in result
        assert "title: 제목" in result

    def test_long_value_truncated(self) -> None:
        hit = {"_score": 1.0, "_source": {"body": "x" * 300}}
        result = _format_hit(1, hit)
        assert "…" in result
        assert len(result) < 350

    def test_nested_excluded(self) -> None:
        hit = {"_score": 1.0, "_source": {"title": "ok", "embedding": [0.1, 0.2], "meta": {"a": 1}}}
        result = _format_hit(1, hit)
        assert "title: ok" in result
        assert "embedding" not in result
        assert "meta" not in result

    def test_empty_source(self) -> None:
        hit = {"_score": 0.0, "_source": {}}
        result = _format_hit(1, hit)
        assert "score=0.00" in result

    def test_score_none(self) -> None:
        """sort=oldest 등에서 _score가 None으로 반환되는 경우."""
        hit = {"_score": None, "_source": {"title": "ok"}}
        result = _format_hit(1, hit)
        assert "score=0.00" in result
