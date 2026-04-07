"""ai_search_summary preset 수동 테스트 스크립트.

서버 없이 그래프를 직접 invoke해서 결과를 보기 좋게 출력합니다.

사용법:
    uv run python scripts/try_search_summary.py "AI 직업훈련"
    uv run python scripts/try_search_summary.py "청년 취업 지원금"
    uv run python scripts/try_search_summary.py        # 기본 쿼리

사전 조건:
    .env 에 OPENAI_API_KEY 설정
"""

from __future__ import annotations

import asyncio
import json
import sys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from agents import build_graph

# Windows 콘솔에서 한글 출력이 깨지지 않도록 stdout을 utf-8로 강제.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


async def run(query: str) -> None:
    """주어진 query로 ai_search_summary 그래프를 호출하고 결과를 출력합니다."""
    print(f"검색어: {query}")
    print("=" * 60)

    graph = build_graph("ai_search_summary")
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=query)]}
    )

    last_message = result["messages"][-1]
    try:
        payload = json.loads(last_message.content)
    except (json.JSONDecodeError, TypeError):
        print("⚠️  응답이 JSON이 아닙니다:")
        print(last_message.content)
        return

    print()
    print("📝 요약:")
    print(f"  {payload.get('summary', '')}")
    print()
    print("🔗 1순위 결과:")
    primary = payload.get("primary") or {}
    if primary.get("url") or primary.get("title"):
        cat = primary.get("category", "")
        title = primary.get("title", "")
        url = primary.get("url", "")
        print(f"  - [{cat}] {title}")
        if url:
            print(f"    {url}")
    else:
        print("  (없음)")
    print()
    print("📂 추가 탐색 경로:")
    related_categories = payload.get("related_categories", [])
    if related_categories:
        for rc in related_categories:
            cat = rc.get("category", "")
            title = rc.get("title", "")
            url = rc.get("url", "")
            print(f"  - [{cat}] {title}")
            if url:
                print(f"    {url}")
    else:
        print("  (없음)")
    print()
    print("🔍 연관검색어:")
    related_queries = payload.get("related_queries", [])
    if related_queries:
        print(f"  {', '.join(related_queries)}")
    else:
        print("  (없음)")
    print()
    print("💼 연관직종:")
    related_jobs = payload.get("related_jobs", [])
    if related_jobs:
        for j in related_jobs:
            print(f"  - {j}")
    else:
        print("  (없음)")


def main() -> None:
    load_dotenv()
    query = " ".join(sys.argv[1:]).strip() or "AI 직업훈련"
    asyncio.run(run(query))


if __name__ == "__main__":
    main()
