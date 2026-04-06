"""범용 도구(@tool) 모음.

특정 worker에 종속되지 않는 공용 도구를 이 패키지에 정의합니다.
worker 전용 도구는 해당 worker 파일 안에 정의하세요.

사용법:
    from agents.tools import list_skills, read_skill
    from agents.tools import search_web, search_database  # 예시 도구

Warning:
    ``agents.tools.examples`` 의 도구들은 **mock 구현**입니다.
    실제 서비스 배포 전에 반드시 실제 API 호출로 교체하세요.
    교체 방법: ``agents/tools/examples.py`` 내 각 함수의 본문을 수정합니다.
"""

from __future__ import annotations

from agents.tools.examples import (
    get_current_time,
    read_document,
    search_database,
    search_web,
)
from agents.tools.opensearch import search_opensearch
from agents.tools.skills import list_skills, read_skill

__all__: list[str] = [
    # 스킬 도구
    "list_skills",
    "read_skill",
    # OpenSearch 검색
    "search_opensearch",
    # 예시 도구 (mock — 실제 서비스에서 구현 교체)
    "get_current_time",
    "search_web",
    "search_database",
    "read_document",
]
