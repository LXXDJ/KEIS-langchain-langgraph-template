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

import asyncio
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


# ── 결과 개수 환경변수 ──────────────────────────────────────────

# work24 에서 카테고리당 받아올 결과 개수의 기본값.
_DEFAULT_SEARCH_RESULT_COUNT = 20
# 요약 LLM 에 입력으로 넘길 결과 개수의 기본값.
_DEFAULT_SUMMARY_INPUT_COUNT = 5
# 환경변수가 받을 수 있는 양의 정수 범위 (1 ~ MAX). work24 한 호출이
# 너무 무거워지거나 LLM 토큰이 폭증하는 것을 막기 위한 안전 상한.
_COUNT_MIN = 1
_COUNT_MAX = 100


class _InvalidCountError(ValueError):
    """결과 개수 환경변수가 정수가 아니거나 허용 범위를 벗어났을 때 발생."""


def _resolve_positive_int(
    env_name: str,
    default: int,
    *,
    raw: str | None = None,
) -> int:
    """양의 정수 환경변수를 읽어 검증한 값을 반환합니다.

    동작:
    - 미설정/공백 → ``default``
    - 정상 정수(``_COUNT_MIN`` ~ ``_COUNT_MAX``) → 그 값
    - 정수가 아니거나 범위를 벗어나면 ``_InvalidCountError``

    Args:
        env_name: 환경변수 이름 (에러 메시지에만 사용)
        default: 미설정 시 사용할 값
        raw: 테스트에서 직접 값을 주입할 때 사용. 기본은 ``os.getenv``.
    """
    value = (raw if raw is not None else os.getenv(env_name, "")).strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise _InvalidCountError(
            f"{env_name}='{value}' 를 정수로 해석할 수 없습니다."
        ) from exc
    if parsed < _COUNT_MIN or parsed > _COUNT_MAX:
        raise _InvalidCountError(
            f"{env_name}={parsed} 가 허용 범위를 벗어났습니다 "
            f"({_COUNT_MIN}~{_COUNT_MAX})."
        )
    return parsed


@lru_cache(maxsize=1)
def _search_result_count() -> int:
    """``SEARCH_RESULT_COUNT`` 를 한 번만 평가해 캐싱합니다."""
    return _resolve_positive_int(
        "SEARCH_RESULT_COUNT", _DEFAULT_SEARCH_RESULT_COUNT
    )


@lru_cache(maxsize=1)
def _summary_input_count() -> int:
    """``SUMMARY_INPUT_COUNT`` 를 한 번만 평가해 캐싱합니다."""
    return _resolve_positive_int(
        "SUMMARY_INPUT_COUNT", _DEFAULT_SUMMARY_INPUT_COUNT
    )


# 고용24 통합검색의 9개 결과 카테고리. work24의 "전체" 탭은 이들을 한 화면에 모은
# 필터일 뿐 별도 결과 섹션이 아니므로 여기서는 제외한다.
#
# 이 리스트의 순서가 곧 응답에서 카드가 노출되는 고정 순서이며, work24 사이트
# 통합검색 결과 페이지의 탭 순서(왼쪽 → 오른쪽)와 동일하게 맞췄다.
_CATEGORY_DISPLAY_ORDER: list[str] = [
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

# 요약 카드를 생성할 카테고리 집합. 여기에 포함되지 않은 카테고리는 응답의
# ``categories`` 배열에 아예 포함되지 않는다 (건수는 ``meta.result_count_by_category``
# 에서 확인 가능).
#
# 요약 대상이 아닌 카테고리를 제외하는 이유:
#   - 신고·신청: 양식 파일명/메뉴 경로만 있어 LLM 요약이 무의미
#   - 기업: 기업명/주소만 있어 요약보다 리스트가 자연스러우나,
#     work24 가 이미 보여주므로 중복
#   - 자격: 자격증명만 있고 work24 키워드 매칭 품질이 낮아 노이즈
#   - 기타: catch-all, 콘텐츠 종류가 통일되지 않아 요약 부적합
#
# 각 카테고리별 판정 근거는 README.md 의 "카테고리별 응답 type" 섹션 참고.
_SUMMARY_CATEGORIES: frozenset[str] = frozenset({
    "정책",
    "채용",
    "훈련",
    "뉴스·자료",
    "직업·진로",
})

# 카테고리별 전용 시스템 프롬프트.
# 공통 규칙은 _SUMMARY_RULES 로 분리하고, 카테고리별 강조점만 달리한다.
_SUMMARY_RULES = (
    "규칙: "
    "(1) 핵심 정보만 담을 것, "
    "(2) 과장·추측 금지, 제공된 결과에 근거할 것, "
    "(3) 2~3개 문장으로 총 길이는 200자 이내, "
    "(4) 마크다운/특수문자 없이 평문으로."
)

_CATEGORY_PROMPTS: dict[str, str] = {
    "채용": (
        "당신은 고용24 채용공고 요약 어시스턴트입니다. "
        "검색 결과 JSON 의 meta 필드에 회사명(company), 고용형태(employment_type), "
        "경력(experience), 임금(salary), 근무지(location), 마감(deadline_badge/deadline_date) "
        "정보가 포함되어 있습니다. "
        "요약에 반드시 포함할 것: (a) 채용 건수, (b) 대표 직무/채용 분야, "
        "(c) 지역 분포, (d) 마감 임박 건수(D-7 이내). "
        + _SUMMARY_RULES
    ),
    "훈련": (
        "당신은 고용24 직업훈련 요약 어시스턴트입니다. "
        "검색 결과 JSON 의 meta 필드에 기관명(institution), 훈련기간(period), "
        "훈련비용(cost), 자기부담금(self_payment), NCS직종/취업률(ncs_employment_rate) "
        "정보가 포함되어 있습니다. "
        "요약에 반드시 포함할 것: (a) 과정 수, (b) 국비지원(자기부담금 0) vs 유료 비율, "
        "(c) 주요 과정 분야, (d) 평균적인 훈련기간. "
        + _SUMMARY_RULES
    ),
    "정책": (
        "당신은 고용24 정책 요약 어시스턴트입니다. "
        "검색 결과 JSON 의 meta.description 필드에 각 정책의 지원대상과 신청방법이 "
        "포함되어 있습니다. "
        "요약에 반드시 포함할 것: (a) 정책 건수, (b) 주요 대상자 그룹 "
        "(예: 장애인/고령자/청년/사업주 등), (c) 핵심 지원 내용 1~2개. "
        "단순 정책명 나열이 아니라 '누가, 무엇을 지원받을 수 있는지' 를 중심으로 요약하세요. "
        + _SUMMARY_RULES
    ),
    "뉴스·자료": (
        "당신은 고용24 뉴스·자료 요약 어시스턴트입니다. "
        "검색 결과 JSON 의 meta 필드에 발행일(published_date), 출처(source), "
        "본문발췌(excerpt), 주제어(tags) 정보가 포함되어 있습니다. "
        "요약에 반드시 포함할 것: (a) 자료 수, (b) 주요 주제 1~2개, "
        "(c) 가장 최근 자료의 핵심 내용. "
        + _SUMMARY_RULES
    ),
    "직업·진로": (
        "당신은 고용24 직업·진로 요약 어시스턴트입니다. "
        "검색 결과 JSON 의 meta 필드에 발행일(published_date), 출처(source), "
        "본문발췌(excerpt), 주제어(tags) 정보가 포함되어 있습니다. "
        "요약에 반드시 포함할 것: (a) 자료 수, (b) 주요 직업/진로 관련 주제 1~2개, "
        "(c) 가장 관련성 높은 자료의 핵심 내용. "
        + _SUMMARY_RULES
    ),
}


def _summary_system_prompt(category: str) -> str:
    """카테고리별 전용 프롬프트가 있으면 사용, 없으면 generic 프롬프트."""
    if category in _CATEGORY_PROMPTS:
        return _CATEGORY_PROMPTS[category]
    return (
        "당신은 고용24(work24.go.kr) 검색 결과 요약 어시스턴트입니다. "
        f"이번 결과는 '{category}' 카테고리에 속합니다. "
        "사용자의 질의와 검색 결과(JSON)를 받아 한국어로 2~3줄 요약을 생성합니다. "
        f"'{category}' 카테고리에서 사용자가 가장 알고 싶을 만한 핵심 정보를 우선적으로 다루세요. "
        + _SUMMARY_RULES
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


def _parse_recruit_li(li: Tag) -> dict[str, Any] | None:
    """채용 카테고리 전용 파서.

    채용 li 에서 추출하는 필드:
    - company: dt 에서 a 태그 텍스트를 제외한 나머지
    - title: dd 의 전체 텍스트에서 D-day/마감일 뱃지를 제외한 공고 제목
    - deadline_badge: ``span.tbl_label.gray`` 의 텍스트 (예: "D-8")
    - deadline_date: ``span.s1_r`` 의 텍스트 (예: "(2026.04.17 마감)")
    - employment_type / experience / education / salary / location: vline_group 의
      span.item 들 (순서 기반)
    """
    dl = li.find("dl", class_="dl_list")
    if not dl:
        return None

    # 회사명 + 제목
    dt = dl.find("dt")
    dd = dl.find("dd")
    if not dt or not dd:
        return None

    dt_a = dt.find("a")
    full_dt = " ".join(dt.get_text(" ", strip=True).split())
    a_text = " ".join(dt_a.get_text(" ", strip=True).split()) if dt_a else ""
    company = full_dt.replace(a_text, "").strip() if a_text else full_dt

    url = ""
    if dt_a and _is_meaningful_href(dt_a.get("href", "")):
        url = _absolutize(dt_a["href"])

    # dd 에서 공고 제목 + 마감 뱃지
    dd_text = " ".join(dd.get_text(" ", strip=True).split())
    deadline_badge = ""
    deadline_date = ""
    for span in dd.find_all("span"):
        cls = span.get("class", [])
        text = span.get_text(strip=True)
        if "tbl_label" in cls:
            deadline_badge = text  # "D-8"
        elif "s1_r" in cls:
            deadline_date = text  # "(2026.04.17 마감)"

    # vline_group 의 span.item 들
    vline_groups = li.select("div.vline_group")
    items: list[str] = []
    for vg in vline_groups:
        for span in vg.find_all("span", class_="item"):
            items.append(" ".join(span.get_text(" ", strip=True).split()))

    # 순서 기반 매핑 (첫 번째 vline_group: 고용형태, 경력, 학력, 임금, 근무지, 제공처)
    employment_type = items[0] if len(items) > 0 else ""
    experience = items[1] if len(items) > 1 else ""
    education = items[2] if len(items) > 2 else ""
    salary = items[3] if len(items) > 3 else ""
    location = items[4] if len(items) > 4 else ""

    title = dd_text
    # 뱃지 텍스트를 제거해서 순수 제목만 남김
    for badge_text in [deadline_badge, deadline_date]:
        if badge_text:
            title = title.replace(badge_text, "")
    title = " ".join(title.split()).strip()

    if not url and not title:
        return None

    return {
        "title": title,
        "snippet": "",
        "url": url,
        "category": "채용",
        "meta": {
            "company": company,
            "employment_type": employment_type,
            "experience": experience,
            "education": education,
            "salary": salary,
            "location": location,
            "deadline_badge": deadline_badge,
            "deadline_date": deadline_date,
        },
    }


def _parse_training_li(li: Tag) -> dict[str, Any] | None:
    """훈련 카테고리 전용 파서.

    훈련 li 에서 추출하는 필드:
    - institution: dt 에서 a 태그 텍스트를 제외한 나머지 (기관명)
    - title: dd 의 첫 텍스트 라인 (과정명)
    - period / hours / ncs_employment_rate: vline_group 의 span.item 중 라벨 매칭
    - cost / self_payment: div.price 텍스트
    """
    dl = li.find("dl", class_="dl_list")
    if not dl:
        return None

    dt = dl.find("dt")
    dd = dl.find("dd")
    if not dt or not dd:
        return None

    # 기관명
    dt_a = dt.find("a")
    full_dt = " ".join(dt.get_text(" ", strip=True).split())
    a_text = " ".join(dt_a.get_text(" ", strip=True).split()) if dt_a else ""
    institution = full_dt.replace(a_text, "").strip() if a_text else full_dt
    # "과정 바로가기" 같은 뱃지 텍스트 제거
    for badge_text in ["과정 바로가기", "국민내일배움카드"]:
        institution = institution.replace(badge_text, "").strip()

    url = ""
    if dt_a and _is_meaningful_href(dt_a.get("href", "")):
        url = _absolutize(dt_a["href"])

    # 과정명 — dd 의 직접 텍스트 자식만 (vline_group 등 하위 태그 내용 제외)
    from bs4.element import NavigableString
    direct_parts: list[str] = []
    for child in dd.children:
        if isinstance(child, NavigableString):
            t = child.strip()
            if t:
                direct_parts.append(t)
        elif isinstance(child, Tag) and child.name in ("a", "strong", "em", "span"):
            if "vline_group" not in child.get("class", []):
                t = child.get_text(" ", strip=True)
                if t:
                    direct_parts.append(t)
    title = " ".join(" ".join(direct_parts).split()) if direct_parts else ""

    # vline_group span.item 들에서 라벨 기반 추출
    period = ""
    hours = ""
    ncs_employment_rate = ""
    training_type = ""
    for span in li.select("div.vline_group span.item"):
        text = " ".join(span.get_text(" ", strip=True).split())
        if not text:
            continue
        if "훈련기간" in text or "기간" in text:
            period = text.replace("훈련기간 :", "").replace("훈련기간:", "").strip()
        elif "훈련시간" in text or "시간" in text:
            hours = text.replace("훈련시간 :", "").replace("훈련시간:", "").strip()
        elif "NCS" in text or "취업률" in text:
            ncs_employment_rate = text
        elif "훈련" in text and len(text) < 10:
            training_type = text  # "원격훈련", "집체훈련" 등

    # 비용 (div.price)
    cost = ""
    self_payment = ""
    price_div = li.select_one("div.price")
    if price_div:
        price_text = " ".join(price_div.get_text(" ", strip=True).split())
        # "68,310 원 자부 0" 또는 "95,040 원 자부 23,910" 패턴
        cost = price_text
        import re
        # 첫 번째 숫자 = 훈련비, "자부" 뒤의 숫자 = 자기부담금
        cost_match = re.match(r"([\d,]+)", price_text.replace(" ", ""))
        if cost_match:
            cost = cost_match.group(1)
        self_match = re.search(r"자부?\s*([\d,]+)", price_text)
        if not self_match:
            self_match = re.search(r"원\s*([\d,]+)", price_text)
        if self_match:
            self_payment = self_match.group(1)

    if not url and not title:
        return None

    return {
        "title": title,
        "snippet": "",
        "url": url,
        "category": "훈련",
        "meta": {
            "institution": institution,
            "training_type": training_type,
            "period": period,
            "hours": hours,
            "cost": cost,
            "self_payment": self_payment,
            "ncs_employment_rate": ncs_employment_rate,
        },
    }


def _parse_policy_li(li: Tag) -> dict[str, Any] | None:
    """정책 카테고리 전용 파서.

    정책 li 에서 추출하는 필드:
    - title: dt 텍스트 (정책명)
    - description: div.flex_box 의 텍스트 (지원대상/신청방법 등 풍부한 설명)
    """
    dl = li.find("dl", class_="dl_list")
    if not dl:
        return None
    dt = dl.find("dt")
    if not dt:
        return None

    # 정책명 — dt 의 첫 번째 a 가 곧 정책명 링크.
    # (정책 dt 에는 직접 텍스트가 없고 a 태그 자체가 제목)
    dt_a = dt.find("a")
    url = ""
    if dt_a and _is_meaningful_href(dt_a.get("href", "")):
        url = _absolutize(dt_a["href"])
    title = " ".join(dt_a.get_text(" ", strip=True).split()) if dt_a else ""
    if not title:
        title = " ".join(dt.get_text(" ", strip=True).split())

    # 지원대상/신청방법 설명 (div.flex_box 또는 div.item2repet)
    description = ""
    for div in li.select("div.flex_box, div.item2repet"):
        text = " ".join(div.get_text(" ", strip=True).split())
        if text and len(text) > len(description):
            description = text

    if not url and not title:
        return None

    return {
        "title": title,
        "snippet": description[:300] if description else "",
        "url": url,
        "category": "정책",
        "meta": {
            "description": description,
        },
    }


def _parse_news_li(li: Tag, category: str) -> dict[str, Any] | None:
    """뉴스·자료 / 직업·진로 카테고리 전용 파서.

    두 카테고리는 HTML 구조가 동일합니다:
    - dt: 제목 + 등록일 (등록일:2025-09-09)
    - dd: 본문 발췌 (풍부)
    - vline_group: 출처, 주제어
    """
    dl = li.find("dl", class_="dl_list")
    if not dl:
        return None
    dt = dl.find("dt")
    dd = dl.find("dd")
    if not dt:
        return None

    # 제목 + URL — dt 에 a 태그가 2개: 첫 번째(btn_txt)가 실제 제목,
    # 두 번째(btn_link)가 "사이트 가기". 첫 번째에서 제목과 URL 을 추출.
    all_a = dt.find_all("a")
    title_a = None
    for a in all_a:
        cls = a.get("class", [])
        text = a.get_text(" ", strip=True)
        # "사이트 가기" / "바로가기" 는 건너뜀
        if "btn_link" in cls or "사이트" in text or "바로가기" in text:
            continue
        title_a = a
        break
    if not title_a and all_a:
        title_a = all_a[0]

    url = ""
    if title_a and _is_meaningful_href(title_a.get("href", "")):
        url = _absolutize(title_a["href"])
    title = " ".join(title_a.get_text(" ", strip=True).split()) if title_a else ""

    # 등록일 추출 — dt 전체 텍스트에서 (등록일:2025-09-09) 또는 (등록일2025.02.24)
    import re
    full_dt = " ".join(dt.get_text(" ", strip=True).split())
    published_date = ""
    date_match = re.search(r"\(등록일[:\s]*([\d.\-]+)\)", full_dt)
    if date_match:
        published_date = date_match.group(1)
    # 제목에서 등록일 괄호 제거
    date_in_title = re.search(r"\(등록일[:\s]*[\d.\-]+\)", title)
    if date_in_title:
        title = title[:date_in_title.start()].strip()

    # 본문 발췌
    excerpt = ""
    if dd:
        excerpt = " ".join(dd.get_text(" ", strip=True).split())

    # vline_group: 출처, 주제어
    source = ""
    tags = ""
    for span in li.select("div.vline_group span.item"):
        text = " ".join(span.get_text(" ", strip=True).split())
        if not text:
            continue
        if "출처" in text or ":" in text and not tags:
            source = text.replace("출처 :", "").replace("출처:", "").strip()
        elif "주제어" in text or "," in text:
            tags = text.replace("주제어 :", "").replace("주제어:", "").strip()

    if not url and not title:
        return None

    return {
        "title": title,
        "snippet": excerpt[:300] if excerpt else "",
        "url": url,
        "category": category,
        "meta": {
            "published_date": published_date,
            "source": source,
            "excerpt": excerpt,
            "tags": tags,
        },
    }


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


def _parse_report_section(section: Tag, category: str) -> list[dict[str, Any]]:
    """신고·신청 카테고리 전용 파서.

    신고·신청 섹션은 다른 카테고리와 HTML 구조가 다릅니다:
    - ``ul.srch_list_default > li`` 가 1개뿐이고
    - 그 안에 ``div.box_border_type`` 서브섹션들(개인/기업)이 들어 있고
    - 각 서브섹션 안에 ``p.b1_r`` 로 메뉴 경로가 나열됩니다.

    일반 파서(``_parse_li``)로는 1건만 나오므로 별도로 처리합니다.
    """
    items: list[dict[str, Any]] = []
    for box in section.select("div.box_border_type"):
        # 서브섹션 라벨 (예: "- 개인", "- 기업")
        label_span = box.select_one("span.b1_sb")
        sub_label = ""
        if label_span:
            sub_label = " ".join(label_span.get_text(" ", strip=True).split())
            sub_label = sub_label.lstrip("- ").strip()

        for p in box.select("p.b1_r"):
            title = " ".join(p.get_text(" ", strip=True).split())
            if not title or _is_placeholder_title(title):
                continue
            # p 안에 <a> 가 있으면 URL 추출, 없으면 빈 문자열
            url = ""
            a_tag = p.find("a", href=True)
            if a_tag and _is_meaningful_href(a_tag.get("href", "")):
                url = _absolutize(a_tag["href"])
            items.append({
                "title": title,
                "snippet": sub_label,
                "url": url,
                "category": category,
                "meta": {"sub_section": sub_label} if sub_label else {},
            })
    return items


def _parse_work24_html(
    html: str,
) -> list[dict[str, Any]]:
    """고용24 통합검색 결과 HTML을 정규화된 결과 리스트로 파싱합니다.

    Returns:
        results: ``{"title", "snippet", "url", "category", "meta"}`` dict 의 리스트

    파싱 실패 시 빈 리스트 ``[]`` 를 반환합니다 (caller 가 graceful degradation).
    """
    if not html:
        return []
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        _log.exception("BeautifulSoup parsing failed")
        return []

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

        # 카테고리별 전용 파서가 있으면 사용, 없으면 범용 _parse_li.
        if category == "신고·신청":
            results.extend(_parse_report_section(section, category))
            continue

        ul = section.select_one("ul.srch_list_default")
        if not isinstance(ul, Tag):
            continue

        for li in ul.find_all("li", recursive=False):
            if category == "채용":
                parsed = _parse_recruit_li(li)
            elif category == "훈련":
                parsed = _parse_training_li(li)
            elif category == "정책":
                parsed = _parse_policy_li(li)
            elif category in ("뉴스·자료", "직업·진로"):
                parsed = _parse_news_li(li, category)
            else:
                parsed = _parse_li(li, category)
            if parsed is not None:
                results.append(parsed)

    return results


# ── Fetcher (work24 통합검색 HTTP 호출) ──────────────────────────


async def fetch_work24_search(
    query: str,
    *,
    list_count: int = _DEFAULT_SEARCH_RESULT_COUNT,
) -> list[dict[str, Any]]:
    """고용24 통합검색을 호출해 정규화된 결과 리스트를 반환합니다.

    실패 시 빈 리스트 + 경고 로그 (요약 파이프라인이 멈추지 않게).

    NOTE: 공식 API가 아니라 공개 페이지의 HTML 스크래핑입니다.
    work24가 API를 제공하면 그쪽으로 교체하는 것을 권장합니다.
    """
    if not query:
        return []

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
        "reportSort": "RANK",
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
        return []
    except Exception:
        _log.exception("unexpected error while fetching work24 query=%r", query)
        return []

    return _parse_work24_html(html)


# ── 카드 빌더 (결정론 헬퍼) ─────────────────────────────────────


def _group_by_category(
    results: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """결과 리스트를 카테고리별 dict 로 그룹화합니다 (입력 순서 유지)."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        cat = r.get("category", "")
        if not cat:
            continue
        grouped.setdefault(cat, []).append(r)
    return grouped


def _build_summary_card(
    category: str,
    items: list[dict[str, Any]],
    summary_text: str,
) -> dict[str, Any]:
    """summary type 카드를 생성합니다."""
    top = items[0] if items else None
    return {
        "category": category,
        "type": "summary",
        "summary": summary_text,
        "top_result": (
            {"title": top.get("title", ""), "url": top.get("url", "")}
            if top
            else None
        ),
        "result_count": len(items),
    }




# ── LLM 호출 헬퍼 (테스트에서 monkeypatch) ──────────────────────


async def _summarize_for_category(
    query: str, category: str, selected: list[dict[str, Any]]
) -> str:
    """카테고리별 한국어 2~3줄 요약을 생성합니다.

    카테고리 인지형 시스템 프롬프트를 사용하여 LLM 이 해당 카테고리에 맞는
    톤/강조점을 스스로 조정하도록 합니다.

    LLM 호출이 실패하면 top-1 결과의 title 을 fallback 으로 반환합니다. 단,
    ``LLM_MODEL`` 환경변수 형식이 잘못된 ``_InvalidModelIdError`` 는 설정 오류
    이므로 fallback 하지 않고 그대로 raise 합니다.
    """
    model = _model_id()  # _InvalidModelIdError 는 여기서 raise (fallback 안 함)
    try:
        llm = init_chat_model(model)
        payload = json.dumps(selected, ensure_ascii=False)
        result = await llm.ainvoke(
            [
                SystemMessage(content=_summary_system_prompt(category)),
                HumanMessage(content=f"질의: {query}\n검색결과: {payload}"),
            ]
        )
        text = result.content if hasattr(result, "content") else str(result)
        return text.strip() if isinstance(text, str) else str(text)
    except Exception:
        _log.exception(
            "summarization failed for category=%s; using fallback title echo",
            category,
        )
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


async def _build_category_cards(
    query: str,
    by_category: dict[str, list[dict[str, Any]]],
    summary_input_count: int,
) -> list[dict[str, Any]]:
    """요약 가능한 카테고리에 대해서만 카드를 고정 순서로 생성합니다.

    동작:
    - ``_CATEGORY_DISPLAY_ORDER`` 순서대로 순회
    - ``_SUMMARY_CATEGORIES`` 에 포함되지 않은 카테고리는 건너뜀
      (건수는 ``meta.result_count_by_category`` 에서 확인 가능)
    - 결과 0건 카테고리도 건너뜀
    - ``asyncio.gather`` 로 병렬 LLM 호출
      (검색 1건당 최대 5 회의 요약 호출이 동시에 발생)
    """
    summary_inputs: list[tuple[int, str, list[dict[str, Any]]]] = []
    cards: list[dict[str, Any] | None] = []

    for category in _CATEGORY_DISPLAY_ORDER:
        if category not in _SUMMARY_CATEGORIES:
            continue
        items = by_category.get(category, [])
        if not items:
            continue

        selected = items[:summary_input_count]
        summary_inputs.append((len(cards), category, selected))
        cards.append(None)  # placeholder

    if summary_inputs:
        summaries = await asyncio.gather(
            *(
                _summarize_for_category(query, category, selected)
                for _, category, selected in summary_inputs
            )
        )
        for (idx, category, _), summary_text in zip(summary_inputs, summaries):
            full_items = by_category.get(category, [])
            cards[idx] = _build_summary_card(
                category, full_items, summary_text
            )

    return [c for c in cards if c is not None]


async def worker_search_summary(state: State, **kwargs: Any) -> dict[str, Any]:
    """SVC-3 worker — 고용24 검색 결과를 카테고리별로 카드화합니다.

    동작 흐름:

        query 추출 → work24 검색 (HTTP/HTML)
            → 카테고리별 그룹화 → 카테고리별 카드 생성 (summary/list/link)
            → summary 카드는 병렬 LLM 호출 → 응답 payload 직렬화

    출력은 ``_worker_outputs`` 에 단일 dict 로 push 되며, ``data["response"]``
    필드에 최종 JSON 문자열이 담깁니다. ``postprocessor`` 가 이를
    ``AIMessage.content`` 로 그대로 변환합니다.

    Phase 1 (현재): 의도 분류 LLM 호출 제거. 모든 카테고리는 work24 의 자체
    분류를 그대로 신뢰하고, 결과 있는 카테고리만 카드화한다. 자세한 설계
    배경은 README.md 의 "카테고리별 응답 type" 섹션 참고.
    """
    query = _extract_query(state)
    if not query:
        empty_payload = {
            "query": "",
            "categories": [],
            "meta": {
                "result_count_total": 0,
                "result_count_by_category": {},
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

    # 결과 개수 환경변수는 첫 호출 시점에 검증 → 잘못된 값이면 _InvalidCountError
    # 가 raise 되어 운영자가 즉시 인지하도록 한다 (LLM_MODEL 과 동일 패턴).
    search_result_count = _search_result_count()
    summary_input_count = _summary_input_count()

    results = await fetch_work24_search(query, list_count=search_result_count)
    by_category = _group_by_category(results)
    cards = await _build_category_cards(query, by_category, summary_input_count)

    payload = {
        "query": query,
        "categories": cards,
        "meta": {
            "result_count_total": len(results),
            "result_count_by_category": {
                cat: len(items) for cat, items in by_category.items()
            },
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
