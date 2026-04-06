"""OpenSearch 검색 도구.

Airflow 데이터 파이프라인이 적재한 데이터를 OpenSearch에서 검색합니다.
연결 설정은 환경변수로 관리합니다:

- ``OPENSEARCH_HOST``: 호스트 (기본값: localhost)
- ``OPENSEARCH_PORT``: 포트 (기본값: 9200)
- ``OPENSEARCH_INDEX``: 기본 인덱스명
- ``OPENSEARCH_USER``, ``OPENSEARCH_PASSWORD``: 인증 (선택)

사용법:
    from agents.tools import search_opensearch

    agent = create_agent(
        tools=[search_opensearch, ...],
    )
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.tools import tool

_log = logging.getLogger(__name__)


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


# ── 공개 도구 ────────────────────────────────────────────────


@tool
def search_opensearch(
    query: str,
    index: str = "",
    top_k: int = 5,
) -> str:
    """OpenSearch에서 문서를 검색합니다.

    Args:
        query: 검색 쿼리.
        index: 검색할 인덱스명. 비어 있으면 환경변수 OPENSEARCH_INDEX 사용.
        top_k: 반환할 최대 문서 수 (기본값: 5).
    """
    target_index = index or os.getenv("OPENSEARCH_INDEX", "")
    if not target_index:
        return "검색할 인덱스가 지정되지 않았습니다. index 인자 또는 OPENSEARCH_INDEX 환경변수를 설정하세요."

    try:
        client = _get_client()
    except ImportError:
        return "opensearch-py 패키지가 설치되지 않았습니다: pip install opensearch-py"
    except Exception as e:
        _log.exception("OpenSearch 연결 실패")
        return f"OpenSearch 연결 실패: {e}"

    # TODO: 데이터 형식 확정 후 쿼리 구조를 조정하세요.
    # 현재는 multi_match 기본 쿼리를 사용합니다.
    body: dict[str, Any] = {
        "size": top_k,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["*"],
            },
        },
    }

    try:
        response = client.search(index=target_index, body=body)
    except Exception as e:
        _log.exception("OpenSearch 검색 실패: index=%s", target_index)
        return f"검색 실패: {e}"

    hits = response.get("hits", {}).get("hits", [])
    if not hits:
        return f"'{query}'에 대한 검색 결과가 없습니다. (index: {target_index})"

    lines: list[str] = []
    for i, hit in enumerate(hits, 1):
        source = hit.get("_source", {})
        score = hit.get("_score", 0)
        # TODO: 데이터 형식 확정 후 표시할 필드를 지정하세요.
        # 임베딩 벡터, 긴 본문 등이 컨텍스트를 오염시키지 않도록
        # 스칼라 필드만 추출하고 값 길이를 제한합니다.
        parts: list[str] = []
        for k, v in list(source.items())[:5]:
            if isinstance(v, (list, dict)):
                continue  # 벡터, 중첩 객체 제외
            text = str(v)
            if len(text) > 200:
                text = text[:200] + "…"
            parts.append(f"{k}: {text}")
        lines.append(f"{i}. [score={score:.2f}] {', '.join(parts)}")

    return "\n".join(lines)
