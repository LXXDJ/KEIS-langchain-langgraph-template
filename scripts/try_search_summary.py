"""ai_search_summary preset 수동 테스트 스크립트.

서버 없이 그래프를 직접 invoke 해서 결과를 보기 좋게 출력합니다.

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
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from agents import build_graph

# Windows 콘솔에서 한글 출력이 깨지지 않도록 stdout 을 utf-8 로 강제.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _print_card(card: dict[str, Any]) -> None:
    """카테고리 카드 한 개를 type 별로 보기 좋게 출력합니다."""
    category = card.get("category", "")
    ctype = card.get("type", "")
    count = card.get("result_count", 0)
    print(f"[{category}] ({ctype}, {count}건)")

    if ctype == "summary":
        summary = card.get("summary", "")
        if summary:
            print(f"  {summary}")
        top = card.get("top_result")
        if top:
            print(f"  ↳ 최상위: {top.get('title', '')}")
            url = top.get("url", "")
            if url:
                print(f"    {url}")
    elif ctype == "list":
        items = card.get("items", [])
        for item in items:
            title = item.get("title", "")
            url = item.get("url", "")
            print(f"  - {title}")
            if url:
                print(f"    {url}")
    # link type 은 별도 출력 없음 (more_url 만 있음)

    more_url = card.get("more_url", "")
    if more_url:
        print(f"  ↳ 더 보기: {more_url}")
    print()


async def run(query: str) -> None:
    """주어진 query 로 ai_search_summary 그래프를 호출하고 결과를 출력합니다."""
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
        print("⚠️  응답이 JSON 이 아닙니다:")
        print(last_message.content)
        return

    print()
    cards = payload.get("categories", [])
    print(f"📊 카테고리 카드 ({len(cards)})")
    print()
    if cards:
        for card in cards:
            _print_card(card)
    else:
        print("  (결과 있는 카테고리 없음)")
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
    print()

    meta = payload.get("meta", {})
    total = meta.get("result_count_total", 0)
    by_cat = meta.get("result_count_by_category", {})
    print(f"ℹ️  전체 결과 수: {total}건")
    if by_cat:
        breakdown = ", ".join(f"{k}={v}" for k, v in by_cat.items())
        print(f"   카테고리별: {breakdown}")


def main() -> None:
    load_dotenv()
    query = " ".join(sys.argv[1:]).strip() or "AI 직업훈련"
    asyncio.run(run(query))


if __name__ == "__main__":
    main()
