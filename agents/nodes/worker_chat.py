"""Worker 노드 예시 — create_react_agent() 활용.

langgraph.prebuilt.create_react_agent()로 만든 대화형 에이전트를
서브에이전트로 사용하는 패턴입니다.
커스텀 도구(@tool)를 붙여서 DB 조회, API 호출 등을 수행할 수 있습니다.

사용법:
    custom.py의 build_custom()에서 worker_type="chat"을 지정합니다.

    build_custom(worker_type="chat")
"""

from __future__ import annotations

from typing import Any, Dict

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from agents.state import State


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


async def worker_chat(state: State, **kwargs: Any) -> Dict[str, Any]:
    """create_react_agent() 기반 worker 노드.

    특징:
    - @tool로 정의한 커스텀 도구를 에이전트에 전달
    - system_prompt로 에이전트의 역할 지정
    - LangGraph의 create_react_agent()는 ReAct 패턴으로 동작
    """
    messages = state.get("messages", [])

    model = ChatOpenAI(model="gpt-4o-mini")

    agent = create_react_agent(
        model=model,
        tools=[get_current_time, search_database],
        prompt=(
            "당신은 데이터 분석 어시스턴트입니다. "
            "사용자의 질문에 도구를 활용하여 정확하게 답변하세요."
        ),
    )

    result = await agent.ainvoke({"messages": messages})

    ai_message = result["messages"][-1]
    response_text = ai_message.content if hasattr(ai_message, "content") else str(ai_message)

    return {
        "_worker_outputs": [{
            "status": "success",
            "data": {"response": response_text},
        }],
    }
