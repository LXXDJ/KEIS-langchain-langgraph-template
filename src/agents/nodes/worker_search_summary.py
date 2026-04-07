"""Worker 노드 — 고용24 검색 결과를 가져와 한국어 2~3줄로 요약합니다 (SVC-3).

선형 결정론 파이프라인을 단일 노드 안에서 순차 실행합니다:

    query 추출 → 의도 분류(LLM) → work24 검색(HTTP/HTML)
        → 카테고리별 top-k 선별 → 요약(LLM) → navigation 구성
        → JSON 직렬화 → _worker_outputs push

``preprocess`` / ``postprocessor`` 노드와 함께 사용됩니다. ``postprocessor`` 가
``_worker_outputs[0]["data"]["response"]`` 를 그대로 ``AIMessage.content`` 에
넣으므로 본 worker 는 그 자리에 JSON 문자열을 넣습니다.

NOTE: ``fetch_work24_search`` 는 공식 API 가 아니라 work24 통합검색 페이지의
HTML 스크래핑으로 결과를 가져옵니다. 공식 API 가 제공되면 그쪽으로 교체하는 것을
권장합니다. 자세한 동작과 디자인 결정은 README.md 의 "각 노드 상세" 섹션 참고.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from functools import lru_cache
from typing import Any

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agents.state import State

_log = logging.getLogger(__name__)

# 상대 URL을 절대 URL로 만들 때 사용.
_WORK24_BASE = "https://www.work24.go.kr"
_WORK24_SEARCH_PATH = "/cm/f/c/0100/selectUnifySearch.do"
_WORK24_HTTP_TIMEOUT = 5.0
# 기본 httpx UA가 차단될 가능성을 피하기 위해 명시.
_WORK24_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ── 상수 / 프롬프트 ──────────────────────────────────────────────

# 환경변수 LLM_MODEL 미설정 시 사용할 기본 모델.
_DEFAULT_MODEL_ID = "openai:gpt-4o-mini"

# init_chat_model 이 인식하는 provider prefix 들. LLM_MODEL 에 prefix 가 없으면
# openai 로 자동 보정한다 (auto-prefix).
_KNOWN_PROVIDERS: frozenset[str] = frozenset({
    "openai",
    "anthropic",
    "google_genai",
    "google_vertexai",
    "azure_openai",
    "bedrock",
    "cohere",
    "fireworks",
    "groq",
    "huggingface",
    "mistralai",
    "ollama",
    "together",
    "xai",
})


class _InvalidModelIdError(ValueError):
    """LLM_MODEL 환경변수 형식이 잘못되었을 때 발생."""


def _resolve_model_id(raw: str | None = None) -> str:
    """``LLM_MODEL`` 환경변수를 읽어 ``provider:model`` 형식 문자열을 반환합니다.

    동작:
    - 미설정/공백 → ``_DEFAULT_MODEL_ID``
    - ``"gpt-4o-mini"`` 처럼 prefix 가 없으면 ``"openai:"`` 자동 부착
    - ``"openai:gpt-4o-mini"`` 처럼 정상 형식이면 그대로 사용
    - 알 수 없는 provider prefix 면 ``_InvalidModelIdError``

    Args:
        raw: 테스트에서 직접 값을 주입할 때 사용. 기본은 ``os.getenv``.
    """
    value = (raw if raw is not None else os.getenv("LLM_MODEL", "")).strip()
    if not value:
        return _DEFAULT_MODEL_ID

    if ":" not in value:
        # auto-prefix: 그냥 모델명만 적은 경우 openai 로 가정.
        return f"openai:{value}"

    provider, _, model = value.partition(":")
    provider = provider.strip().lower()
    model = model.strip()
    if provider not in _KNOWN_PROVIDERS:
        raise _InvalidModelIdError(
            f"LLM_MODEL='{value}' 의 provider '{provider}' 를 인식할 수 없습니다. "
            f"알려진 provider: {', '.join(sorted(_KNOWN_PROVIDERS))}"
        )
    if not model:
        raise _InvalidModelIdError(
            f"LLM_MODEL='{value}' 에 모델 이름이 비어 있습니다 "
            "(예: 'openai:gpt-4o-mini')."
        )
    return f"{provider}:{model}"


@lru_cache(maxsize=1)
def _model_id() -> str:
    """``_resolve_model_id`` 결과를 프로세스 단위로 캐싱합니다.

    환경변수는 프로세스 기동 후 바뀌지 않는다고 가정하므로 한 번만 평가하면 됩니다.
    검증 실패는 첫 호출 시점에 즉시 raise 되어 운영 환경에서 빠르게 드러납니다.
    """
    return _resolve_model_id()

# 고용24 통합검색의 9개 결과 카테고리.
# work24의 "전체" 탭은 이들을 한 화면에 모은 필터일 뿐 별도 결과 섹션이 아니므로
# ranking 후보에서 제외한다 (포함하면 LLM이 의미 없는 안전선택으로 늘 1순위로 잡음).
_ALL_CATEGORIES: list[str] = [
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


# ── HTML 파서 ────────────────────────────────────────────────


def _is_meaningful_href(href: str | None) -> bool:
    """``javascript:`` / ``#`` / 빈 값 등을 걸러냅니다."""
    if not href:
        return False
    h = href.strip().lower()
    return not (
        h.startswith("javascript:")
        or h.startswith("#")
        or h == "void(0)"
        or h == ""
    )


def _absolutize(href: str) -> str:
    """상대 URL이면 work24 base를 prepend합니다."""
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("/"):
        return _WORK24_BASE + href
    return href


def _extract_li_url(li: Tag) -> str:
    """``<li>`` 안에서 의미있는 첫 URL을 찾아 반환합니다."""
    for a in li.find_all("a", href=True):
        href = a.get("href", "")
        if _is_meaningful_href(href):
            return _absolutize(href)
    return ""


def _extract_li_title(li: Tag) -> str:
    """``<li>`` 안에서 가장 그럴듯한 제목 텍스트를 반환합니다.

    "사이트 가기" 같은 보조 텍스트는 건너뛰고, 충분히 긴 첫 번째 링크
    텍스트를 우선합니다. 적절한 링크 텍스트가 없으면 ``<strong>`` 텍스트로 fallback.
    """
    skip_tokens = {"사이트가기", "사이트 가기", "바로가기"}

    candidates: list[str] = []
    for a in li.find_all("a"):
        text = " ".join(a.get_text(" ", strip=True).split())
        if not text:
            continue
        normalized = text.replace(" ", "")
        if normalized in {t.replace(" ", "") for t in skip_tokens}:
            continue
        candidates.append(text)

    if candidates:
        # 너무 짧은 후보(URL 텍스트 등)보다 의미있는 길이의 첫 번째를 선호.
        for c in candidates:
            if len(c) >= 4:
                return c
        return candidates[0]

    strong = li.find("strong")
    if strong:
        return " ".join(strong.get_text(" ", strip=True).split())
    return ""


def _extract_li_snippet(li: Tag) -> str:
    """``span.item`` 들과 ``<strong>`` 의 텍스트를 합쳐 짧은 설명을 만듭니다."""
    parts: list[str] = []
    strong = li.find("strong")
    if strong:
        text = " ".join(strong.get_text(" ", strip=True).split())
        if text:
            parts.append(text)
    for span in li.find_all("span", class_="item"):
        text = " ".join(span.get_text(" ", strip=True).split())
        if text:
            parts.append(text)
    snippet = " | ".join(parts)
    if len(snippet) > 300:
        snippet = snippet[:297] + "..."
    return snippet


def _extract_li_meta(li: Tag) -> dict[str, Any]:
    """카테고리에 무관한 부가 정보 dict.

    상세한 분류 대신 ``items`` 라는 단일 키에 ``span.item`` 텍스트 리스트를 담아
    LLM이 직접 해석하도록 위임합니다.
    """
    items: list[str] = []
    for span in li.find_all("span", class_="item"):
        text = " ".join(span.get_text(" ", strip=True).split())
        if text:
            items.append(text)
    return {"items": items} if items else {}


def _is_placeholder_title(title: str) -> bool:
    """결과 카운트("9", "0") 같은 placeholder li의 title 패턴인지 판단."""
    if not title:
        return True
    # 숫자 + 단위만 있는 경우 (예: "0", "9", "62,370")
    bare = title.replace(",", "").replace(".", "").strip()
    return bare.isdigit()


def _parse_li(li: Tag, category: str) -> dict[str, Any] | None:
    """``<li>`` 하나를 정규화된 결과 dict로 변환합니다.

    URL과 title 둘 다 비어있거나 title이 placeholder(숫자만)인 경우
    None을 반환합니다.
    """
    url = _extract_li_url(li)
    title = _extract_li_title(li)
    if not url and (not title or _is_placeholder_title(title)):
        return None
    return {
        "title": title,
        "snippet": _extract_li_snippet(li),
        "url": url,
        "category": category,
        "meta": _extract_li_meta(li),
    }


def _parse_related_queries(soup: BeautifulSoup) -> list[str]:
    """``form_keyword1`` 탭의 ``_btn_recommend`` 버튼에서 연관검색어를 추출합니다."""
    container = soup.find("div", id="form_keyword1")
    if not container or not isinstance(container, Tag):
        return []
    out: list[str] = []
    for btn in container.find_all("button", attrs={"name": "_btn_recommend"}):
        text = " ".join(btn.get_text(" ", strip=True).split())
        if text and text not in out:
            out.append(text)
    return out[:5]


def _parse_related_jobs(soup: BeautifulSoup) -> list[str]:
    """``form_keyword2`` 탭의 ``_btn_jobsCategor`` 버튼에서 연관직종을 추출합니다.

    work24의 연관직종은 보통 "대분류 > 중분류 > 소분류" 형식으로 노출되며,
    현재 시스템 명세상 최대 2개까지 표시한다.
    """
    container = soup.find("div", id="form_keyword2")
    if not container or not isinstance(container, Tag):
        return []
    out: list[str] = []
    for btn in container.find_all("button", attrs={"name": "_btn_jobsCategor"}):
        text = " ".join(btn.get_text(" ", strip=True).split())
        if text and text not in out:
            out.append(text)
    return out[:2]


def _parse_work24_html(
    html: str,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """고용24 통합검색 결과 HTML을 정규화된 결과 + 연관검색어 + 연관직종으로 파싱합니다.

    Returns:
        (results, related_queries, related_jobs)
        results: ``{"title", "snippet", "url", "category", "meta"}`` dict의 리스트
        related_queries: 연관검색어 문자열 리스트 (최대 5개)
        related_jobs: 연관직종 문자열 리스트 (최대 2개)

    파싱 실패 시 빈 튜플 ``([], [], [])`` 을 반환합니다 (caller가 graceful degradation).
    """
    if not html:
        return [], [], []
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        _log.exception("BeautifulSoup parsing failed")
        return [], [], []

    results: list[dict[str, Any]] = []
    for stit in soup.select("div.stit_area"):
        cat_span = stit.select_one("span.t2_sb")
        if not cat_span:
            continue
        category = " ".join(cat_span.get_text(" ", strip=True).split())
        if not category:
            continue

        header = stit.parent
        if not isinstance(header, Tag):
            continue
        section = header.find_next_sibling("div", class_="result_view")
        if not isinstance(section, Tag):
            continue
        ul = section.select_one("ul.srch_list_default")
        if not isinstance(ul, Tag):
            continue

        for li in ul.find_all("li", recursive=False):
            parsed = _parse_li(li, category)
            if parsed is not None:
                results.append(parsed)

    related_queries = _parse_related_queries(soup)
    related_jobs = _parse_related_jobs(soup)
    return results, related_queries, related_jobs


# ── Fetcher (work24 통합검색 HTTP 호출) ──────────────────────────


async def fetch_work24_search(
    query: str,
    *,
    list_count: int = 20,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """고용24 통합검색을 호출해 정규화된 결과 + 연관검색어 + 연관직종을 반환합니다.

    실패 시 빈 리스트 + 경고 로그 (요약 파이프라인이 멈추지 않게).

    work24의 통합검색 페이지는 카테고리별로 별도의 정렬 옵션 파라미터를 받는다.
    브라우저에서 실제로 보내는 파라미터셋을 그대로 흉내내어 사용자가 보는 화면과
    동일한 결과를 받도록 한다.

    NOTE: 공식 API가 아니라 공개 페이지의 HTML 스크래핑입니다.
    work24가 API를 제공하면 그쪽으로 교체하는 것을 권장합니다.
    """
    if not query:
        return [], [], []

    # work24 통합검색 페이지가 실제로 보내는 파라미터셋과 동일하게 구성.
    # 카테고리별 정렬 옵션을 명시해야 사용자가 브라우저에서 보는 결과와
    # 일치한다 (특히 훈련은 DATE, 보고서는 TITLE, 나머지는 RANK).
    params = {
        "topQuerySearchArea": "all",
        "topQueryData": query,
        "startDate": "",
        "endDate": "",
        "sortField": "rank",
        "includedQuery": "",
        "excludedQuery": "",
        "startCount": "1",
        "listCount": str(list_count),
        "reportSort": "TITLE",
        "workinfoSort": "RANK",
        "residentSort": "RANK",
        "policySort": "RANK",
        "newsSort": "RANK",
        "bizinfoSort": "RANK",
        "trainingSort": "DATE",
        "jobCourseSort": "RANK",
        "qualSort": "RANK",
        "etcSort": "RANK",
        "rdo": "",
    }
    headers = {"User-Agent": _WORK24_USER_AGENT}

    try:
        async with httpx.AsyncClient(
            base_url=_WORK24_BASE,
            timeout=_WORK24_HTTP_TIMEOUT,
            headers=headers,
            follow_redirects=True,
        ) as client:
            response = await client.get(_WORK24_SEARCH_PATH, params=params)
            response.raise_for_status()
            html = response.text
    except httpx.HTTPError:
        _log.exception("work24 fetch failed for query=%r", query)
        return [], [], []
    except Exception:
        _log.exception("unexpected error while fetching work24 query=%r", query)
        return [], [], []

    return _parse_work24_html(html)


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


_EMPTY_NAVIGATION_ITEM: dict[str, Any] = {"category": "", "url": "", "title": ""}


def _build_navigation(
    results: list[dict[str, Any]],
    ranking: list[str],
    related_queries: list[str],
    related_jobs: list[str],
) -> dict[str, Any]:
    """navigation dict 구성.

    primary 와 related_categories 는 모두 ``{category, url, title}`` 형태로
    동일한 모양을 가진다 (UI 가 같은 카드 컴포넌트로 처리할 수 있도록).

    - primary: 1순위 카테고리의 첫 번째 결과
    - related_categories: 2·3순위 카테고리에서 각 1개씩
    - related_queries: 연관검색어 (최대 5개)
    - related_jobs: 연관직종 (최대 2개)
    """
    by_category: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        by_category.setdefault(r.get("category", ""), []).append(r)

    def _card(category: str) -> dict[str, Any] | None:
        items = by_category.get(category, [])
        if not items:
            return None
        item = items[0]
        return {
            "category": category,
            "url": item.get("url", ""),
            "title": item.get("title", ""),
        }

    primary: dict[str, Any] = dict(_EMPTY_NAVIGATION_ITEM)
    if ranking:
        top = _card(ranking[0])
        if top:
            primary = top

    related_categories: list[dict[str, Any]] = []
    for cat in ranking[1:3]:
        card = _card(cat)
        if card:
            related_categories.append(card)

    return {
        "primary": primary,
        "related_categories": related_categories,
        "related_queries": related_queries[:5],
        "related_jobs": related_jobs[:2],
    }


# ── LLM 호출 헬퍼 (테스트에서 monkeypatch) ──────────────────────


async def _classify_intent(query: str) -> list[str]:
    """검색어 의도를 분류해 카테고리 우선순위 리스트를 반환합니다.

    LLM 호출이 실패하면 ``_DEFAULT_CATEGORY_RANKING`` 을 반환합니다. 단,
    ``LLM_MODEL`` 환경변수 형식이 잘못된 ``_InvalidModelIdError`` 는 운영자가
    즉시 인지해야 하는 설정 오류이므로 fallback 하지 않고 그대로 raise 합니다.
    """
    model = _model_id()  # _InvalidModelIdError 는 여기서 raise (fallback 안 함)
    try:
        llm = init_chat_model(model).with_structured_output(_IntentResult)
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

    LLM 호출이 실패하면 top-1 결과의 title을 fallback으로 반환합니다. 단,
    ``LLM_MODEL`` 환경변수 형식이 잘못된 ``_InvalidModelIdError`` 는 설정 오류
    이므로 fallback 하지 않고 그대로 raise 합니다.
    """
    model = _model_id()  # _InvalidModelIdError 는 여기서 raise (fallback 안 함)
    try:
        llm = init_chat_model(model)
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


def _now_iso() -> str:
    """현재 시각을 UTC ISO 8601 (초 단위) 문자열로 반환합니다."""
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


async def worker_search_summary(state: State, **kwargs: Any) -> dict[str, Any]:
    """SVC-3 worker — 고용24 검색 결과를 한국어 2~3줄로 요약합니다.

    출력은 ``_worker_outputs`` 에 단일 dict로 push되며,
    ``data["response"]`` 필드에 최종 JSON 문자열이 담깁니다.
    기존 ``postprocessor`` 가 이를 ``AIMessage.content`` 로 그대로 변환합니다.
    """
    query = _extract_query(state)
    if not query:
        empty_payload = {
            "query": "",
            "summary": "",
            "primary": dict(_EMPTY_NAVIGATION_ITEM),
            "related_categories": [],
            "related_queries": [],
            "related_jobs": [],
            "meta": {
                "ranking": [],
                "result_count": 0,
                "fetched_at": _now_iso(),
            },
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
    results, related_queries, related_jobs = await fetch_work24_search(query)
    selected = _select_top_k_by_category(results, ranking, k=5)
    summary = await _summarize(query, selected)
    navigation = _build_navigation(results, ranking, related_queries, related_jobs)

    payload = {
        "query": query,
        "summary": summary,
        "primary": navigation["primary"],
        "related_categories": navigation["related_categories"],
        "related_queries": navigation["related_queries"],
        "related_jobs": navigation["related_jobs"],
        "meta": {
            "ranking": ranking,
            "result_count": len(results),
            "fetched_at": _now_iso(),
        },
    }

    return {
        "_worker_outputs": [
            {
                "status": "success",
                "data": {"response": json.dumps(payload, ensure_ascii=False)},
            }
        ]
    }
