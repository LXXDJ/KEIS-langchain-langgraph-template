"""OpenSearch 검색 도구.

Airflow 데이터 파이프라인이 적재한 데이터를 OpenSearch에서 검색합니다.
연결 설정은 환경변수로 관리합니다:

- ``OPENSEARCH_HOST``: 호스트 (기본값: localhost)
- ``OPENSEARCH_PORT``: 포트 (기본값: 9200)
- ``OPENSEARCH_INDEX``: 기본 인덱스명
- ``OPENSEARCH_USER``, ``OPENSEARCH_PASSWORD``: 인증 (선택)
- ``OPENSEARCH_USE_SSL``, ``OPENSEARCH_VERIFY_CERTS``, ``OPENSEARCH_CA_CERTS``: TLS 설정

도구 구성:
    - ``search_opensearch`` — 의도 기반 파라미터로 검색 (기본 도구)
    - ``describe_opensearch_index`` — 인덱스 매핑/필드 조회 (스키마 탐색)

사용법:
    from agents.tools import search_opensearch, describe_opensearch_index

    agent = create_agent(
        tools=[search_opensearch, describe_opensearch_index, ...],
    )
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from langchain_core.tools import tool

_log = logging.getLogger(__name__)

# ── 결과 포맷 제한 ──────────────────────────────────────────

_MAX_FIELD_LENGTH = 200
_MAX_SOURCE_FIELDS = 8


# ── 클라이언트 ───────────────────────────────────────────────


def _get_client() -> Any:
    """OpenSearch 클라이언트를 생성합니다.

    ``opensearchpy`` 가 설치되지 않으면 ImportError를 발생시킵니다.
    """
    from opensearchpy import OpenSearch

    host = os.getenv("OPENSEARCH_HOST", "localhost")
    port = int(os.getenv("OPENSEARCH_PORT", "9200"))
    user = os.getenv("OPENSEARCH_USER", "")
    password = os.getenv("OPENSEARCH_PASSWORD", "")

    auth = (user, password) if user else None
    use_ssl = os.getenv("OPENSEARCH_USE_SSL", "false").lower() == "true"
    verify_certs = os.getenv("OPENSEARCH_VERIFY_CERTS", "true").lower() == "true"
    ca_certs = os.getenv("OPENSEARCH_CA_CERTS", "") or None

    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_auth=auth,
        use_ssl=use_ssl,
        verify_certs=verify_certs if use_ssl else False,
        ca_certs=ca_certs,
        ssl_show_warn=False,
    )


def _resolve_index(index: str) -> str:
    """인덱스명을 결정합니다. 비어 있으면 환경변수에서 읽습니다."""
    return index or os.getenv("OPENSEARCH_INDEX", "")


def _format_hit(rank: int, hit: dict[str, Any]) -> str:
    """검색 결과 한 건을 안전하게 포맷합니다."""
    source = hit.get("_source", {})
    score = hit.get("_score", 0)

    parts: list[str] = []
    for k, v in list(source.items())[:_MAX_SOURCE_FIELDS]:
        if isinstance(v, (list, dict)):
            continue
        text = str(v)
        if len(text) > _MAX_FIELD_LENGTH:
            text = text[:_MAX_FIELD_LENGTH] + "…"
        parts.append(f"{k}: {text}")

    return f"{rank}. [score={score:.2f}] {', '.join(parts)}"


# ── DSL 빌더 ────────────────────────────────────────────────


def _build_query(
    query: str,
    filters: str,
    date_range: str,
    sort: str,
    fields: str,
    top_k: int,
) -> dict[str, Any]:
    """의도 기반 파라미터에서 OpenSearch DSL을 조립합니다."""
    # ── must: 검색 쿼리 ───────────────────────────────────────
    search_fields = [f.strip() for f in fields.split(",") if f.strip()] if fields else ["*"]
    must_clause: dict[str, Any] = {
        "multi_match": {
            "query": query,
            "fields": search_fields,
        },
    }

    # ── filter 절 ─────────────────────────────────────────────
    filter_clauses: list[dict[str, Any]] = []

    # filters 파싱: "key1:val1,key2:val2" 형식
    if filters:
        for pair in filters.split(","):
            pair = pair.strip()
            if ":" not in pair:
                continue
            key, _, value = pair.partition(":")
            filter_clauses.append({"term": {key.strip(): value.strip()}})

    # date_range 파싱: "field:gte~lte" 형식 (예: "created_at:2026-01-01~2026-03-31")
    if date_range:
        parts = date_range.split(":")
        if len(parts) == 2:
            field_name = parts[0].strip()
            dates = parts[1].strip().split("~")
            range_clause: dict[str, str] = {}
            if len(dates) >= 1 and dates[0]:
                range_clause["gte"] = dates[0].strip()
            if len(dates) >= 2 and dates[1]:
                range_clause["lte"] = dates[1].strip()
            if range_clause:
                filter_clauses.append({"range": {field_name: range_clause}})

    # ── bool 쿼리 조립 ────────────────────────────────────────
    if filter_clauses:
        query_dsl: dict[str, Any] = {
            "bool": {
                "must": [must_clause],
                "filter": filter_clauses,
            },
        }
    else:
        query_dsl = must_clause

    # ── sort ──────────────────────────────────────────────────
    sort_clause: list[Any] | None = None
    if sort == "recent":
        sort_clause = [{"_score": "desc"}, {"created_at": {"order": "desc", "unmapped_type": "date"}}]
    elif sort == "oldest":
        sort_clause = [{"created_at": {"order": "asc", "unmapped_type": "date"}}]
    # "relevance" (기본값)은 sort 없이 _score 기준

    body: dict[str, Any] = {
        "size": min(top_k, 20),
        "query": query_dsl,
    }
    if sort_clause:
        body["sort"] = sort_clause

    return body


# ── 공개 도구 ────────────────────────────────────────────────


@tool
def search_opensearch(
    query: str,
    index: str = "",
    filters: str = "",
    date_range: str = "",
    sort: str = "relevance",
    fields: str = "",
    top_k: int = 5,
) -> str:
    """OpenSearch에서 문서를 검색합니다.

    Args:
        query: 검색 쿼리.
        index: 검색할 인덱스명. 비어 있으면 환경변수 OPENSEARCH_INDEX 사용.
        filters: 필터 조건. "key:value" 쌍을 쉼표로 구분 (예: "status:완료,부서:구매팀").
        date_range: 날짜 범위. "필드명:시작~끝" 형식 (예: "created_at:2026-01-01~2026-03-31").
        sort: 정렬 기준. "relevance" (기본), "recent", "oldest".
        fields: 검색 대상 필드. 쉼표 구분 (예: "title,body"). 비어 있으면 전체 필드.
        top_k: 반환할 최대 문서 수 (기본값: 5, 최대: 20).
    """
    target_index = _resolve_index(index)
    if not target_index:
        return "검색할 인덱스가 지정되지 않았습니다. index 인자 또는 OPENSEARCH_INDEX 환경변수를 설정하세요."

    try:
        client = _get_client()
    except ImportError:
        return "opensearch-py 패키지가 설치되지 않았습니다: pip install opensearch-py"
    except Exception as e:
        _log.exception("OpenSearch 연결 실패")
        return f"OpenSearch 연결 실패: {e}"

    body = _build_query(query, filters, date_range, sort, fields, top_k)

    try:
        response = client.search(index=target_index, body=body)
    except Exception as e:
        _log.exception("OpenSearch 검색 실패: index=%s", target_index)
        return f"검색 실패: {e}"

    hits = response.get("hits", {}).get("hits", [])
    if not hits:
        return f"'{query}'에 대한 검색 결과가 없습니다. (index: {target_index})"

    lines = [_format_hit(i, hit) for i, hit in enumerate(hits, 1)]
    return "\n".join(lines)


@tool
def describe_opensearch_index(index: str = "") -> str:
    """OpenSearch 인덱스의 매핑 정보를 조회합니다.

    검색 전에 어떤 필드가 있는지, 필터/정렬 가능한 필드가 무엇인지 파악할 때 사용합니다.

    Args:
        index: 조회할 인덱스명. 비어 있으면 환경변수 OPENSEARCH_INDEX 사용.
    """
    target_index = _resolve_index(index)
    if not target_index:
        return "인덱스가 지정되지 않았습니다. index 인자 또는 OPENSEARCH_INDEX 환경변수를 설정하세요."

    try:
        client = _get_client()
    except ImportError:
        return "opensearch-py 패키지가 설치되지 않았습니다: pip install opensearch-py"
    except Exception as e:
        _log.exception("OpenSearch 연결 실패")
        return f"OpenSearch 연결 실패: {e}"

    try:
        mapping = client.indices.get_mapping(index=target_index)
    except Exception as e:
        _log.exception("매핑 조회 실패: index=%s", target_index)
        return f"매핑 조회 실패: {e}"

    # 첫 번째 인덱스의 매핑 추출 (alias일 수 있으므로)
    index_name = next(iter(mapping), target_index)
    properties = mapping.get(index_name, {}).get("mappings", {}).get("properties", {})

    if not properties:
        return f"인덱스 '{target_index}'에 매핑 정보가 없습니다."

    # 필드별 타입 정리
    lines: list[str] = [f"인덱스: {target_index}", f"필드 수: {len(properties)}", ""]

    keyword_fields: list[str] = []
    text_fields: list[str] = []
    date_fields: list[str] = []
    numeric_fields: list[str] = []
    other_fields: list[str] = []

    for field_name, field_info in sorted(properties.items()):
        field_type = field_info.get("type", "object")

        if field_type == "keyword":
            keyword_fields.append(field_name)
        elif field_type == "text":
            text_fields.append(field_name)
        elif field_type == "date":
            date_fields.append(field_name)
        elif field_type in ("integer", "long", "float", "double"):
            numeric_fields.append(field_name)
        else:
            other_fields.append(field_name)

    if text_fields:
        lines.append(f"검색 가능 (text): {', '.join(text_fields)}")
    if keyword_fields:
        lines.append(f"필터/정렬 가능 (keyword): {', '.join(keyword_fields)}")
    if date_fields:
        lines.append(f"날짜 필드: {', '.join(date_fields)}")
    if numeric_fields:
        lines.append(f"숫자 필드: {', '.join(numeric_fields)}")
    if other_fields:
        lines.append(f"기타: {', '.join(other_fields)}")

    return "\n".join(lines)
