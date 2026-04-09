"""ai_search_summary preset 테스트.

전략:
- 순수 함수(``_select_top_k_by_category``, ``_build_navigation``)는 직접 단위 테스트
- preset E2E는 I/O 경계(``fetch_work24_search``, ``_classify_intent``, ``_summarize``)를
  monkeypatch로 대체하여 LLM/HTTP 호출 없이 검증
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agents.presets.ai_search_summary import build_ai_search_summary

# 주의: ``agents.nodes`` 패키지의 ``__init__.py`` 가 ``worker_search_summary`` 라는
# 이름을 함수로 재노출하므로 ``import agents.nodes.worker_search_summary as wss`` 가
# 모듈이 아닌 함수에 바인딩된다. 모듈 객체를 얻으려면 importlib 를 사용한다.
wss = importlib.import_module("agents.nodes.worker_search_summary")

_FIXTURE_DIR = Path(__file__).parent / "fixtures"
_WORK24_FIXTURE = _FIXTURE_DIR / "work24_sample.html"


# ── 단위 테스트: _parse_work24_html ──────────────────────────────


@pytest.fixture(scope="module")
def work24_html() -> str:
    """실제 work24.go.kr 검색 결과 HTML (Phase 2 fixture)."""
    if not _WORK24_FIXTURE.exists():
        pytest.skip(f"fixture missing: {_WORK24_FIXTURE}")
    return _WORK24_FIXTURE.read_text(encoding="utf-8")


def test_parse_work24_html_returns_results(work24_html: str) -> None:
    results = wss._parse_work24_html(work24_html)
    assert results, "fixture에서 결과가 하나도 파싱되지 않음"


def test_parse_work24_html_results_have_required_fields(work24_html: str) -> None:
    results = wss._parse_work24_html(work24_html)
    for r in results:
        assert set(r.keys()) >= {"title", "snippet", "url", "category", "meta"}
        assert isinstance(r["title"], str)
        assert isinstance(r["snippet"], str)
        assert isinstance(r["url"], str)
        assert isinstance(r["category"], str)
        assert isinstance(r["meta"], dict)
        # title이나 url 중 하나는 반드시 있어야 한다 (placeholder 제외).
        assert r["title"] or r["url"]


def test_parse_work24_html_covers_multiple_categories(work24_html: str) -> None:
    results = wss._parse_work24_html(work24_html)
    categories = {r["category"] for r in results}
    # 검색어 'ai'에 대해 적어도 채용/훈련/뉴스·자료는 항상 보여야 한다.
    expected_subset = {"채용", "훈련", "뉴스·자료"}
    assert expected_subset.issubset(categories), f"missing: {expected_subset - categories}"


def test_parse_work24_html_absolutizes_relative_urls(work24_html: str) -> None:
    results = wss._parse_work24_html(work24_html)
    urls_with_value = [r["url"] for r in results if r["url"]]
    assert urls_with_value, "URL을 가진 결과가 하나도 없음"
    for url in urls_with_value:
        assert url.startswith("http://") or url.startswith("https://"), url


def test_parse_work24_html_empty_input_returns_empty() -> None:
    results = wss._parse_work24_html("")
    assert results == []


def test_parse_work24_html_garbage_input_returns_empty() -> None:
    """파싱 가능한 마크업이지만 work24 구조가 아니면 빈 결과."""
    results = wss._parse_work24_html(
        "<html><body><p>not work24</p></body></html>"
    )
    assert results == []


def test_parse_work24_html_truncated_input_does_not_raise() -> None:
    """잘린 HTML이어도 예외를 던지지 않아야 한다."""
    truncated = "<html><body><div class='stit_area'><span class='t2_sb'>채용</span"
    # 절대 raise하면 안 됨.
    results = wss._parse_work24_html(truncated)
    assert isinstance(results, list)


# ── 단위 테스트: _group_by_category ──────────────────────────────


def test_group_by_category_preserves_input_order() -> None:
    results = [
        {"category": "채용", "title": "r1"},
        {"category": "정책", "title": "p1"},
        {"category": "채용", "title": "r2"},
    ]
    grouped = wss._group_by_category(results)
    assert list(grouped["채용"][0].values()) == ["채용", "r1"] or grouped["채용"][0]["title"] == "r1"
    assert [it["title"] for it in grouped["채용"]] == ["r1", "r2"]
    assert [it["title"] for it in grouped["정책"]] == ["p1"]


def test_group_by_category_skips_blank_category() -> None:
    results = [
        {"category": "", "title": "x"},
        {"category": "정책", "title": "p"},
    ]
    grouped = wss._group_by_category(results)
    assert list(grouped.keys()) == ["정책"]


# ── 단위 테스트: 카드 빌더 ──────────────────────────────────────


def test_build_summary_card_shape() -> None:
    items = [
        {"title": "샘플 채용 1", "url": "https://example.com/1"},
        {"title": "샘플 채용 2", "url": "https://example.com/2"},
    ]
    card = wss._build_summary_card("채용", items, "테스트 요약 텍스트")
    assert card["category"] == "채용"
    assert card["type"] == "summary"
    assert card["summary"] == "테스트 요약 텍스트"
    assert card["top_result"] == {
        "title": "샘플 채용 1",
        "url": "https://example.com/1",
    }
    assert card["result_count"] == 2
    assert "more_url" not in card


def test_build_summary_card_top_result_none_when_empty_items() -> None:
    card = wss._build_summary_card("채용", [], "요약")
    assert card["top_result"] is None
    assert card["result_count"] == 0


def test_non_summary_categories_excluded_from_cards() -> None:
    """_SUMMARY_CATEGORIES 에 포함되지 않은 카테고리는 카드가 만들어지지 않아야 한다."""
    non_summary = {"신고·신청", "기업", "자격", "기타"}
    for cat in non_summary:
        assert cat not in wss._SUMMARY_CATEGORIES, f"{cat} should not be in _SUMMARY_CATEGORIES"


# ── 단위 테스트: _resolve_model_id ───────────────────────────────


def test_resolve_model_id_default_when_unset() -> None:
    assert wss._resolve_model_id(None) == wss._DEFAULT_MODEL_ID
    assert wss._resolve_model_id("") == wss._DEFAULT_MODEL_ID
    assert wss._resolve_model_id("   ") == wss._DEFAULT_MODEL_ID


def test_resolve_model_id_passes_through_valid_prefix() -> None:
    assert wss._resolve_model_id("openai:gpt-4o-mini") == "openai:gpt-4o-mini"
    assert (
        wss._resolve_model_id("anthropic:claude-haiku-4-5-20251001")
        == "anthropic:claude-haiku-4-5-20251001"
    )


def test_resolve_model_id_auto_prefixes_openai() -> None:
    """prefix 가 없으면 openai 로 자동 보정."""
    assert wss._resolve_model_id("gpt-4o-mini") == "openai:gpt-4o-mini"
    assert wss._resolve_model_id("gpt-4o") == "openai:gpt-4o"


def test_resolve_model_id_rejects_unknown_provider() -> None:
    with pytest.raises(wss._InvalidModelIdError):
        wss._resolve_model_id("madeup_provider:some-model")


def test_resolve_model_id_rejects_empty_model_part() -> None:
    with pytest.raises(wss._InvalidModelIdError):
        wss._resolve_model_id("openai:")


# ── 단위 테스트: _resolve_positive_int (count 환경변수) ─────────


def test_resolve_positive_int_default_when_unset() -> None:
    assert wss._resolve_positive_int("SEARCH_RESULT_COUNT", 20, raw=None) == 20
    assert wss._resolve_positive_int("SEARCH_RESULT_COUNT", 20, raw="") == 20
    assert wss._resolve_positive_int("SEARCH_RESULT_COUNT", 20, raw="   ") == 20


def test_resolve_positive_int_passes_through_valid() -> None:
    assert wss._resolve_positive_int("SEARCH_RESULT_COUNT", 20, raw="1") == 1
    assert wss._resolve_positive_int("SEARCH_RESULT_COUNT", 20, raw="42") == 42
    assert wss._resolve_positive_int("SEARCH_RESULT_COUNT", 20, raw="100") == 100


def test_resolve_positive_int_rejects_non_integer() -> None:
    with pytest.raises(wss._InvalidCountError):
        wss._resolve_positive_int("SEARCH_RESULT_COUNT", 20, raw="abc")
    with pytest.raises(wss._InvalidCountError):
        wss._resolve_positive_int("SEARCH_RESULT_COUNT", 20, raw="3.14")


def test_resolve_positive_int_rejects_zero_and_negative() -> None:
    with pytest.raises(wss._InvalidCountError):
        wss._resolve_positive_int("SEARCH_RESULT_COUNT", 20, raw="0")
    with pytest.raises(wss._InvalidCountError):
        wss._resolve_positive_int("SEARCH_RESULT_COUNT", 20, raw="-5")


def test_resolve_positive_int_rejects_above_max() -> None:
    with pytest.raises(wss._InvalidCountError):
        wss._resolve_positive_int("SEARCH_RESULT_COUNT", 20, raw="101")
    with pytest.raises(wss._InvalidCountError):
        wss._resolve_positive_int("SEARCH_RESULT_COUNT", 20, raw="9999")


# ── 단위 테스트: _summarize_for_category fallback ────────────────


async def test_summarize_for_category_fallback_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM 호출이 실패하면 top-1 결과의 title 을 반환해야 한다."""

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("simulated llm failure")

    monkeypatch.setattr(wss, "init_chat_model", _boom)
    out = await wss._summarize_for_category("q", "채용", [{"title": "fallback제목"}])
    assert out == "fallback제목"


async def test_summarize_for_category_fallback_on_empty_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("simulated llm failure")

    monkeypatch.setattr(wss, "init_chat_model", _boom)
    out = await wss._summarize_for_category("q", "채용", [])
    assert out == ""


def test_summary_system_prompt_includes_category_name() -> None:
    """카테고리 인지형 프롬프트가 카테고리 이름을 실제로 주입하는지 검증."""
    prompt_recruit = wss._summary_system_prompt("채용")
    prompt_policy = wss._summary_system_prompt("정책")
    assert "채용" in prompt_recruit
    assert "정책" in prompt_policy
    # 두 프롬프트는 카테고리 이름 외에는 같은 템플릿이어야 한다
    assert prompt_recruit != prompt_policy


# ── E2E: preset 통합 (LLM/HTTP 모두 mock) ────────────────────────


def _make_result(category: str, idx: int) -> dict[str, Any]:
    """E2E 테스트용 가짜 결과 항목 헬퍼."""
    return {
        "title": f"{category}-{idx}",
        "snippet": "",
        "url": f"https://example.com/{category}/{idx}",
        "category": category,
        "meta": {},
    }


async def test_preset_e2e_returns_categories_in_fixed_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """summary 카드는 _CATEGORY_DISPLAY_ORDER 의 고정 순서로 노출되어야 한다.

    fake_results 입력 순서를 일부러 뒤섞어도, 응답의 categories 배열은
    UI 탭 순서를 따른다. 비-summary 카테고리(신고·신청 등)는 제외된다.
    """
    fake_results = [
        _make_result("훈련", 1),       # summary, display order index 4
        _make_result("신고·신청", 1),   # non-summary → 카드에서 제외
        _make_result("채용", 1),       # summary, display order index 2
        _make_result("정책", 1),       # summary, display order index 1
        _make_result("기업", 1),       # non-summary → 카드에서 제외
    ]

    async def fake_fetch(
        query: str, *, list_count: int = 20
    ) -> list[dict[str, Any]]:
        return fake_results

    async def fake_summarize(
        query: str, category: str, selected: list[dict[str, Any]]
    ) -> str:
        return f"[{category}] 요약"

    monkeypatch.setattr(wss, "fetch_work24_search", fake_fetch)
    monkeypatch.setattr(wss, "_summarize_for_category", fake_summarize)

    graph = build_ai_search_summary()
    result = await graph.ainvoke({"messages": [HumanMessage(content="ai")]})

    payload = json.loads(result["messages"][-1].content)
    categories = [c["category"] for c in payload["categories"]]
    # summary 카테고리만 고정 순서로: 정책 → 채용 → 훈련
    assert categories == ["정책", "채용", "훈련"]
    # 비-summary 카테고리는 meta 에서만 건수 확인
    assert payload["meta"]["result_count_by_category"]["신고·신청"] == 1
    assert payload["meta"]["result_count_by_category"]["기업"] == 1


async def test_preset_e2e_skips_empty_and_non_summary_categories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """결과 0건 카테고리와 비-summary 카테고리는 카드에서 제외."""
    fake_results = [
        _make_result("채용", 1),     # summary
        _make_result("훈련", 1),     # summary
        _make_result("자격", 1),     # non-summary → 제외
    ]

    async def fake_fetch(
        query: str, *, list_count: int = 20
    ) -> list[dict[str, Any]]:
        return fake_results

    async def fake_summarize(
        query: str, category: str, selected: list[dict[str, Any]]
    ) -> str:
        return "요약"

    monkeypatch.setattr(wss, "fetch_work24_search", fake_fetch)
    monkeypatch.setattr(wss, "_summarize_for_category", fake_summarize)

    graph = build_ai_search_summary()
    result = await graph.ainvoke({"messages": [HumanMessage(content="ai")]})

    payload = json.loads(result["messages"][-1].content)
    categories = [c["category"] for c in payload["categories"]]
    assert categories == ["채용", "훈련"]  # summary 만, 자격 제외
    # 모든 카테고리 건수는 meta 에서 그대로 노출
    assert payload["meta"]["result_count_by_category"] == {"채용": 1, "훈련": 1, "자격": 1}


async def test_preset_e2e_only_includes_summary_categories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """9 카테고리 모두 결과가 있어도 summary 카테고리만 카드에 포함된다."""
    fake_results = [
        _make_result("신고·신청", 1),
        _make_result("정책", 1),
        _make_result("채용", 1),
        _make_result("기업", 1),
        _make_result("훈련", 1),
        _make_result("뉴스·자료", 1),
        _make_result("직업·진로", 1),
        _make_result("자격", 1),
        _make_result("기타", 1),
    ]

    async def fake_fetch(
        query: str, *, list_count: int = 20
    ) -> list[dict[str, Any]]:
        return fake_results

    async def fake_summarize(
        query: str, category: str, selected: list[dict[str, Any]]
    ) -> str:
        return f"[{category}] 요약"

    monkeypatch.setattr(wss, "fetch_work24_search", fake_fetch)
    monkeypatch.setattr(wss, "_summarize_for_category", fake_summarize)

    graph = build_ai_search_summary()
    result = await graph.ainvoke({"messages": [HumanMessage(content="ai")]})

    payload = json.loads(result["messages"][-1].content)
    card_categories = {c["category"] for c in payload["categories"]}
    # summary 카테고리만 카드에 포함
    assert card_categories == {"정책", "채용", "훈련", "뉴스·자료", "직업·진로"}
    # 모든 카드의 type 은 summary
    for card in payload["categories"]:
        assert card["type"] == "summary"
    # 비-summary 카테고리도 meta 건수에는 포함
    assert "신고·신청" in payload["meta"]["result_count_by_category"]
    assert "기업" in payload["meta"]["result_count_by_category"]
    assert "자격" in payload["meta"]["result_count_by_category"]
    assert "기타" in payload["meta"]["result_count_by_category"]


async def test_preset_e2e_summary_card_has_top_result_and_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """summary 카드에 LLM 요약, top_result 이 들어가야 한다."""
    fake_results = [
        _make_result("채용", 1),
        _make_result("채용", 2),
    ]

    async def fake_fetch(
        query: str, *, list_count: int = 20
    ) -> list[dict[str, Any]]:
        return fake_results

    async def fake_summarize(
        query: str, category: str, selected: list[dict[str, Any]]
    ) -> str:
        return "테스트 요약입니다."

    monkeypatch.setattr(wss, "fetch_work24_search", fake_fetch)
    monkeypatch.setattr(wss, "_summarize_for_category", fake_summarize)

    graph = build_ai_search_summary()
    result = await graph.ainvoke({"messages": [HumanMessage(content="서울 카페")]})

    payload = json.loads(result["messages"][-1].content)
    assert payload["query"] == "서울 카페"

    [card] = payload["categories"]
    assert card["category"] == "채용"
    assert card["type"] == "summary"
    assert card["summary"] == "테스트 요약입니다."
    assert card["top_result"] == {
        "title": "채용-1",
        "url": "https://example.com/채용/1",
    }
    assert card["result_count"] == 2
    assert "more_url" not in card

    meta = payload["meta"]
    assert meta["result_count_total"] == 2
    assert meta["result_count_by_category"] == {"채용": 2}
    assert isinstance(meta["fetched_at"], str)
    assert meta["fetched_at"].endswith("+00:00")


async def test_preset_e2e_handles_empty_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """빈 query 여도 그래프가 깨지지 않고 빈 payload 를 반환해야 한다."""

    # fetch 는 호출되지 않아야 하지만 안전하게 stub 해둔다.
    async def fake_fetch(
        query: str, *, list_count: int = 20
    ) -> list[dict[str, Any]]:
        raise AssertionError("빈 query 에서는 fetch 가 호출되면 안 된다")

    monkeypatch.setattr(wss, "fetch_work24_search", fake_fetch)

    graph = build_ai_search_summary()
    result = await graph.ainvoke({"messages": [HumanMessage(content="   ")]})

    last = result["messages"][-1]
    assert isinstance(last, AIMessage)
    payload = json.loads(last.content)
    # 결정론적 필드는 정확히, meta.fetched_at 만 형태 검증.
    fetched_at = payload["meta"].pop("fetched_at")
    assert isinstance(fetched_at, str)
    assert fetched_at.endswith("+00:00")
    assert payload == {
        "query": "",
        "categories": [],
        "meta": {
            "result_count_total": 0,
            "result_count_by_category": {},
        },
    }
