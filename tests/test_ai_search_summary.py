"""ai_search_summary preset 테스트.

전략:
- 순수 함수(``_select_top_k_by_category``, ``_build_navigation``)는 직접 단위 테스트
- preset E2E는 I/O 경계(``fetch_work24_search``, ``_classify_intent``, ``_summarize``)를
  monkeypatch로 대체하여 LLM/HTTP 호출 없이 검증
"""

from __future__ import annotations

import importlib
import json
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agents.presets.ai_search_summary import build_ai_search_summary

# 주의: ``agents.nodes`` 패키지의 ``__init__.py`` 가 ``worker_search_summary`` 라는
# 이름을 함수로 재노출하므로 ``import agents.nodes.worker_search_summary as wss`` 가
# 모듈이 아닌 함수에 바인딩된다. 모듈 객체를 얻으려면 importlib 를 사용한다.
wss = importlib.import_module("agents.nodes.worker_search_summary")


# ── 단위 테스트: _select_top_k_by_category ───────────────────────


def test_select_top_k_orders_by_ranking() -> None:
    results = [
        {"category": "기타", "title": "기타1"},
        {"category": "채용", "title": "채용1"},
        {"category": "정책", "title": "정책1"},
        {"category": "채용", "title": "채용2"},
    ]
    ranking = ["채용", "정책", "기타"]
    selected = wss._select_top_k_by_category(results, ranking, k=10)
    assert [r["title"] for r in selected] == ["채용1", "채용2", "정책1", "기타1"]


def test_select_top_k_truncates_to_k() -> None:
    results = [{"category": "정책", "title": f"p{i}"} for i in range(10)]
    ranking = ["정책"]
    selected = wss._select_top_k_by_category(results, ranking, k=3)
    assert len(selected) == 3


def test_select_top_k_unknown_category_goes_last() -> None:
    results = [
        {"category": "전혀모름", "title": "x"},
        {"category": "정책", "title": "p"},
    ]
    selected = wss._select_top_k_by_category(results, ["정책"], k=10)
    assert [r["title"] for r in selected] == ["p", "x"]


# ── 단위 테스트: _build_navigation ───────────────────────────────


def test_build_navigation_picks_primary_and_related() -> None:
    results = [
        {"category": "채용", "url": "u-recruit", "title": "t-recruit"},
        {"category": "정책", "url": "u-policy", "title": "t-policy"},
        {"category": "훈련", "url": "u-train", "title": "t-train"},
    ]
    ranking = ["채용", "정책", "훈련"]
    nav = wss._build_navigation(results, ranking, related_queries=["q1", "q2"])

    assert nav["primary_url"] == "u-recruit"
    assert nav["related_categories"] == [
        {"category": "정책", "url": "u-policy", "title": "t-policy"},
        {"category": "훈련", "url": "u-train", "title": "t-train"},
    ]
    assert nav["related_queries"] == ["q1", "q2"]


def test_build_navigation_handles_missing_categories() -> None:
    results = [{"category": "정책", "url": "u", "title": "t"}]
    ranking = ["채용", "정책", "훈련"]
    nav = wss._build_navigation(results, ranking, related_queries=[])
    # 1순위(채용) 결과 없음 → primary_url 빈 문자열
    assert nav["primary_url"] == ""
    # 2순위(정책)는 있음, 3순위(훈련)는 없음
    assert len(nav["related_categories"]) == 1
    assert nav["related_categories"][0]["category"] == "정책"


def test_build_navigation_caps_related_queries_at_5() -> None:
    nav = wss._build_navigation(
        results=[],
        ranking=[],
        related_queries=["a", "b", "c", "d", "e", "f", "g"],
    )
    assert nav["related_queries"] == ["a", "b", "c", "d", "e"]


# ── 단위 테스트: _classify_intent fallback ───────────────────────


async def test_classify_intent_fallback_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM 호출이 실패하면 기본 ranking을 반환해야 한다."""

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("simulated llm failure")

    monkeypatch.setattr(wss, "init_chat_model", _boom)
    ranking = await wss._classify_intent("아무 검색어")
    assert ranking == wss._DEFAULT_CATEGORY_RANKING


# ── 단위 테스트: _summarize fallback ─────────────────────────────


async def test_summarize_fallback_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("simulated llm failure")

    monkeypatch.setattr(wss, "init_chat_model", _boom)
    out = await wss._summarize("q", [{"title": "fallback제목"}])
    assert out == "fallback제목"


async def test_summarize_fallback_on_empty_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("simulated llm failure")

    monkeypatch.setattr(wss, "init_chat_model", _boom)
    out = await wss._summarize("q", [])
    assert out == ""


# ── E2E: preset 통합 (LLM/HTTP 모두 mock) ────────────────────────


async def test_preset_e2e_returns_json_ai_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_results = [
        {
            "title": "샘플 채용",
            "snippet": "...",
            "url": "https://example.com/recruit",
            "category": "채용",
            "meta": {},
        },
        {
            "title": "샘플 정책",
            "snippet": "...",
            "url": "https://example.com/policy",
            "category": "정책",
            "meta": {},
        },
    ]
    fake_related = ["연관1", "연관2"]

    async def fake_fetch(
        query: str, *, list_count: int = 5
    ) -> tuple[list[dict[str, Any]], list[str]]:
        return fake_results, fake_related

    async def fake_classify(query: str) -> list[str]:
        return ["채용", "정책", "훈련"]

    async def fake_summarize(query: str, selected: list[dict[str, Any]]) -> str:
        return "테스트 요약입니다. 두 줄짜리 짧은 한국어 요약."

    monkeypatch.setattr(wss, "fetch_work24_search", fake_fetch)
    monkeypatch.setattr(wss, "_classify_intent", fake_classify)
    monkeypatch.setattr(wss, "_summarize", fake_summarize)

    graph = build_ai_search_summary()
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="서울 카페 아르바이트")]}
    )

    messages = result["messages"]
    assert messages, "그래프가 messages를 반환해야 합니다"
    last = messages[-1]
    assert isinstance(last, AIMessage)

    payload = json.loads(last.content)
    assert payload["summary"].startswith("테스트 요약")
    assert payload["primary_url"] == "https://example.com/recruit"
    assert payload["related_categories"] == [
        {
            "category": "정책",
            "url": "https://example.com/policy",
            "title": "샘플 정책",
        }
    ]
    assert payload["related_queries"] == ["연관1", "연관2"]


async def test_preset_e2e_handles_empty_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """빈 query여도 그래프가 깨지지 않고 빈 payload를 반환해야 한다."""

    # fetch / llm은 호출되지 않아야 하지만 안전하게 stub해둔다.
    async def fake_fetch(
        query: str, *, list_count: int = 5
    ) -> tuple[list[dict[str, Any]], list[str]]:
        raise AssertionError("빈 query에서는 fetch가 호출되면 안 된다")

    monkeypatch.setattr(wss, "fetch_work24_search", fake_fetch)

    graph = build_ai_search_summary()
    result = await graph.ainvoke({"messages": [HumanMessage(content="   ")]})

    last = result["messages"][-1]
    assert isinstance(last, AIMessage)
    payload = json.loads(last.content)
    assert payload == {
        "summary": "",
        "primary_url": "",
        "related_categories": [],
        "related_queries": [],
    }
