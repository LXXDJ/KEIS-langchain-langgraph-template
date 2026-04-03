"""예시 도구 모음 — 실제 서비스에서는 구현을 교체하세요.

보일러플레이트 템플릿에서 도구 사용 패턴을 보여주기 위한 mock 구현입니다.
실제 서비스에서는 각 도구의 본문을 실제 API 호출로 교체하세요.

사용법:
    from agents.tools import get_current_time, search_database

    agent = create_agent(tools=[get_current_time, search_database])
"""

from __future__ import annotations

from langchain_core.tools import tool


# ── 유틸리티 도구 ────────────────────────────────────────────


@tool
def get_current_time() -> str:
    """현재 시간을 반환합니다."""
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── 검색 도구 ────────────────────────────────────────────────


@tool
def search_web(query: str) -> str:
    """웹에서 정보를 검색합니다."""
    # TODO: Tavily, SerpAPI 등 실제 검색 API로 교체
    return f"[웹 검색 결과] '{query}'에 대한 검색 결과: 샘플 데이터"


@tool
def search_database(query: str) -> str:
    """데이터베이스에서 정보를 검색합니다."""
    # TODO: 실제 DB 쿼리로 교체
    return f"[DB 검색 결과] '{query}'에 대한 결과: 샘플 데이터"


# ── 문서 도구 ────────────────────────────────────────────────


@tool
def read_document(path: str) -> str:
    """문서를 읽어서 내용을 반환합니다."""
    # TODO: 파일시스템, S3 등 실제 읽기로 교체
    return f"[문서 내용] '{path}' 파일의 내용: 샘플 문서 텍스트"
