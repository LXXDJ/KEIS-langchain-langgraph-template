"""Worker 노드 예시 — create_agent() 활용.

create_agent()로 만든 대화형 에이전트를 서브에이전트로 사용하는 패턴입니다.
커스텀 도구(@tool)를 붙여서 DB 조회, API 호출 등을 수행할 수 있습니다.
스킬 도구(list_skills, read_skill)가 기본 포함되어 에이전트가
SKILL.md를 탐색·읽고, 지침에 따라 작업을 수행할 수 있습니다.

사용법:
    custom.py의 build_custom()에서 worker_type="chat"을 지정합니다.

    build_custom(worker_type="chat")
"""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain.tools import tool

from agents.state import State
from agents.tools import list_skills, read_skill

# ── 커스텀 도구 정의 ──────────────────────────────────────────


@tool
def get_current_time() -> str:
    """현재 시간을 반환합니다."""
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def search_database(query: str) -> str:
    """데이터베이스에서 정보를 검색합니다."""
    # 실제 서비스에서는 DB 쿼리로 교체
    return f"[DB 검색 결과] '{query}'에 대한 결과: 샘플 데이터"


# ── Worker 노드 ──────────────────────────────────────────────


async def worker_chat(state: State, **kwargs: Any) -> dict[str, Any]:
    """create_agent() 기반 worker 노드.

    특징:
    - @tool로 정의한 커스텀 도구를 에이전트에 전달
    - list_skills, read_skill 스킬 도구가 기본 포함
    - system_prompt로 에이전트의 역할 지정
    - middleware로 운영 정책 적용 가능 (요약, fallback 등)
    """
    messages = state.get("messages", [])

    agent = create_agent(
        model="openai:gpt-4o-mini",
        tools=[get_current_time, search_database, list_skills, read_skill],
        system_prompt=(
            "당신은 데이터 분석 어시스턴트입니다. "
            "사용자의 질문에 도구를 활용하여 정확하게 답변하세요. "
            "필요시 list_skills로 스킬을 조회하고, "
            "read_skill로 스킬의 지침을 읽어 활용하세요."
        ),
        # middleware=[...],  # 필요 시 미들웨어 추가
    )

    result = await agent.ainvoke({"messages": messages})

    result_messages = result.get("messages", [])
    if not result_messages:
        raise ValueError("에이전트가 빈 messages를 반환했습니다.")
    ai_message = result_messages[-1]
    response_text = ai_message.content if hasattr(ai_message, "content") else str(ai_message)

    return {
        "_worker_outputs": [{
            "status": "success",
            "data": {"response": response_text},
        }],
    }
