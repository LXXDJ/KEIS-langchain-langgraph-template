"""Worker 노드 — 고용24 검색 결과를 가져와 한국어 2~3줄로 요약합니다 (SVC-3).

선형 결정론 파이프라인을 단일 노드 안에서 순차 실행합니다:

    query 추출 → 의도 분류(LLM) → work24 검색(HTTP/HTML)
        → 카테고리별 top-k 선별 → 요약(LLM) → navigation 구성
        → JSON 직렬화 → _worker_outputs push

기존 ``preprocess`` / ``postprocessor`` 노드와 함께 사용됩니다.
``postprocessor``가 ``_worker_outputs[0]["data"]["response"]`` 를 그대로
``AIMessage.content`` 에 넣으므로 본 worker는 그 자리에 JSON 문자열을 넣습니다.

NOTE: ``fetch_work24_search`` 는 Phase 1 단계에서 하드코딩된 stub 데이터를 반환합니다.
Phase 2(파서) / Phase 3(실제 HTTP) 에서 점진적으로 교체됩니다.
공식 API가 제공되면 HTML 스크래핑을 그쪽으로 교체하는 것을 권장합니다.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agents.state import State

_log = logging.getLogger(__name__)


# ── 상수 / 프롬프트 ──────────────────────────────────────────────

_MODEL_ID = "openai:gpt-4o-mini"

# 고용24 통합검색 카테고리 (전체 + 9개 분류).
_ALL_CATEGORIES: list[str] = [
    "전체",
    "신고·신청",
    "정책",
    "채용",
    "기업",
    "훈련",
    "뉴스·자료",
    "직업·진로",
    "자격",
    "기타",
]

# 분류 LLM 실패 시 사용할 중립 기본 우선순위.
_DEFAULT_CATEGORY_RANKING: list[str] = list(_ALL_CATEGORIES)

_INTENT_SYSTEM_PROMPT = (
    "당신은 고용24(work24.go.kr) 통합검색의 의도 분류 어시스턴트입니다. "
    "사용자의 검색어를 보고, 어떤 카테고리의 결과가 가장 핵심인지 우선순위를 매기세요. "
    f"카테고리 후보: {', '.join(_ALL_CATEGORIES)}. "
    "반드시 모든 카테고리를 정확히 한 번씩 우선순위 순서대로 나열하세요."
)

_SUMMARY_SYSTEM_PROMPT = (
    "당신은 고용24 검색 결과 요약 어시스턴트입니다. "
    "사용자의 질의와 검색 결과(JSON)를 받아 한국어로 2~3줄 요약을 생성합니다. "
    "규칙: "
    "(1) 핵심 정보만 담을 것, "
    "(2) 과장·추측 금지, 제공된 결과에 근거할 것, "
    "(3) 2~3개 문장으로 총 길이는 200자 이내, "
    "(4) 마크다운/특수문자 없이 평문으로."
)


class _IntentResult(BaseModel):
    """의도 분류 LLM의 구조화된 출력."""

    category_ranking: list[str] = Field(
        ...,
        description="카테고리 우선순위 (중복 없이 모든 카테고리를 포함).",
    )


# ── HTML 파서 (Phase 2에서 구현) ─────────────────────────────────


def _parse_work24_html(html: str) -> tuple[list[dict[str, Any]], list[str]]:
    """고용24 통합검색 결과 HTML을 정규화된 결과 리스트 + 연관검색어로 파싱합니다.

    Phase 2 단계에서 구현됩니다. 현재는 빈 결과를 반환합니다.

    Returns:
        (results, related_queries)
        results: ``{"title", "snippet", "url", "category", "meta"}`` dict의 리스트
        related_queries: 연관검색어 문자열 리스트 (최대 5개)
    """
    return [], []


# ── Fetcher (Phase 1: stub, Phase 3: 실제 HTTP) ──────────────────


async def fetch_work24_search(
    query: str,
    *,
    list_count: int = 5,
) -> tuple[list[dict[str, Any]], list[str]]:
    """고용24 통합검색을 호출해 정규화된 결과 + 연관검색어를 반환합니다.

    실패 시 빈 리스트를 반환합니다 (요약 파이프라인이 멈추지 않게).

    Phase 1: 하드코딩된 stub 데이터 반환.
    Phase 3에서 ``httpx.AsyncClient`` + ``_parse_work24_html`` 로 교체됩니다.
    """
    _log.info("fetch_work24_search(stub) query=%r list_count=%d", query, list_count)

    stub_results: list[dict[str, Any]] = [
        {
            "title": f"[채용] {query} 관련 채용공고 샘플",
            "snippet": "샘플 채용 공고 설명입니다.",
            "url": "https://www.work24.go.kr/sample/recruit/1",
            "category": "채용",
            "meta": {"company": "샘플회사", "location": "서울"},
        },
        {
            "title": f"[정책] {query} 지원 정책 안내",
            "snippet": "샘플 정책 설명입니다.",
            "url": "https://www.work24.go.kr/sample/policy/1",
            "category": "정책",
            "meta": {},
        },
        {
            "title": f"[훈련] {query} 직업훈련 과정",
            "snippet": "샘플 훈련 과정 설명입니다.",
            "url": "https://www.work24.go.kr/sample/training/1",
            "category": "훈련",
            "meta": {"institution": "샘플훈련원"},
        },
        {
            "title": f"[뉴스·자료] {query} 관련 뉴스",
            "snippet": "샘플 뉴스 설명입니다.",
            "url": "https://www.work24.go.kr/sample/news/1",
            "category": "뉴스·자료",
            "meta": {"published_at": "2026-04-01"},
        },
    ][:list_count]
    stub_related = [f"{query} 지원금", f"{query} 자격증", f"{query} 후기"]
    return stub_results, stub_related


# ── 결정론 헬퍼 ─────────────────────────────────────────────────


def _select_top_k_by_category(
    results: list[dict[str, Any]],
    ranking: list[str],
    *,
    k: int = 5,
) -> list[dict[str, Any]]:
    """카테고리 우선순위에 따라 결과를 정렬한 뒤 상위 k개를 반환합니다.

    같은 카테고리 내에서는 입력 순서를 유지합니다(stable sort).
    ranking에 없는 카테고리는 맨 뒤로 밀립니다.
    """
    rank_index = {cat: idx for idx, cat in enumerate(ranking)}
    fallback = len(ranking)
    sorted_results = sorted(
        results,
        key=lambda r: rank_index.get(r.get("category", ""), fallback),
    )
    return sorted_results[:k]


def _build_navigation(
    results: list[dict[str, Any]],
    ranking: list[str],
    related_queries: list[str],
) -> dict[str, Any]:
    """navigation dict 구성.

    - primary_url: 1순위 카테고리에서 첫 번째 결과의 URL
    - related_categories: 2·3순위 카테고리에서 각 1개씩
    - related_queries: 연관검색어 (최대 5개)
    """
    by_category: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        by_category.setdefault(r.get("category", ""), []).append(r)

    def _first(category: str) -> dict[str, Any] | None:
        items = by_category.get(category, [])
        return items[0] if items else None

    primary_url = ""
    if ranking:
        top = _first(ranking[0])
        if top:
            primary_url = top.get("url", "")

    related_categories: list[dict[str, Any]] = []
    for cat in ranking[1:3]:
        item = _first(cat)
        if item:
            related_categories.append(
                {
                    "category": cat,
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                }
            )

    return {
        "primary_url": primary_url,
        "related_categories": related_categories,
        "related_queries": related_queries[:5],
    }


# ── LLM 호출 헬퍼 (테스트에서 monkeypatch) ──────────────────────


async def _classify_intent(query: str) -> list[str]:
    """검색어 의도를 분류해 카테고리 우선순위 리스트를 반환합니다.

    실패 시 ``_DEFAULT_CATEGORY_RANKING`` 을 반환합니다.
    """
    try:
        llm = init_chat_model(_MODEL_ID).with_structured_output(_IntentResult)
        result = await llm.ainvoke(
            [
                SystemMessage(content=_INTENT_SYSTEM_PROMPT),
                HumanMessage(content=query),
            ]
        )
        ranking = list(result.category_ranking) if result else []
        # 누락된 카테고리 보정 (LLM이 일부를 빼먹는 경우).
        seen = set(ranking)
        for cat in _ALL_CATEGORIES:
            if cat not in seen:
                ranking.append(cat)
        return ranking
    except Exception:
        _log.exception("intent classification failed; using default ranking")
        return list(_DEFAULT_CATEGORY_RANKING)


async def _summarize(query: str, selected: list[dict[str, Any]]) -> str:
    """선별된 결과로 한국어 2~3줄 요약을 생성합니다.

    실패 시 top-1 결과의 title을 fallback으로 반환합니다.
    """
    try:
        llm = init_chat_model(_MODEL_ID)
        payload = json.dumps(selected, ensure_ascii=False)
        result = await llm.ainvoke(
            [
                SystemMessage(content=_SUMMARY_SYSTEM_PROMPT),
                HumanMessage(content=f"질의: {query}\n검색결과: {payload}"),
            ]
        )
        text = result.content if hasattr(result, "content") else str(result)
        return text.strip() if isinstance(text, str) else str(text)
    except Exception:
        _log.exception("summarization failed; using fallback title echo")
        if selected:
            return str(selected[0].get("title", ""))
        return ""


# ── Worker 노드 ──────────────────────────────────────────────


def _extract_query(state: State) -> str:
    """messages의 마지막 HumanMessage에서 query 텍스트를 추출합니다."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) and isinstance(msg.content, str):
            return msg.content.strip()
    return ""


async def worker_search_summary(state: State, **kwargs: Any) -> dict[str, Any]:
    """SVC-3 worker — 고용24 검색 결과를 한국어 2~3줄로 요약합니다.

    출력은 ``_worker_outputs`` 에 단일 dict로 push되며,
    ``data["response"]`` 필드에 최종 JSON 문자열이 담깁니다.
    기존 ``postprocessor`` 가 이를 ``AIMessage.content`` 로 그대로 변환합니다.
    """
    query = _extract_query(state)
    if not query:
        empty_payload = {
            "summary": "",
            "primary_url": "",
            "related_categories": [],
            "related_queries": [],
        }
        return {
            "_worker_outputs": [
                {
                    "status": "empty_query",
                    "data": {"response": json.dumps(empty_payload, ensure_ascii=False)},
                }
            ]
        }

    ranking = await _classify_intent(query)
    results, related_queries = await fetch_work24_search(query)
    selected = _select_top_k_by_category(results, ranking, k=5)
    summary = await _summarize(query, selected)
    navigation = _build_navigation(results, ranking, related_queries)

    payload = {
        "summary": summary,
        "primary_url": navigation["primary_url"],
        "related_categories": navigation["related_categories"],
        "related_queries": navigation["related_queries"],
    }

    return {
        "_worker_outputs": [
            {
                "status": "success",
                "data": {"response": json.dumps(payload, ensure_ascii=False)},
            }
        ]
    }
