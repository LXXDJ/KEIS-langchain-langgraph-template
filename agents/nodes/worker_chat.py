"""Worker 노드 예시 — create_agent() 활용.

create_agent()로 만든 대화형 에이전트를 서브에이전트로 사용하는 패턴입니다.
agents/tools/에 정의된 도구를 import하여 에이전트에 전달합니다.

사용법:
    custom.py의 build_custom()에서 worker_type="chat"을 지정합니다.

    build_custom(worker_type="chat")
"""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent

from agents.state import State
from agents.tools import get_current_time, list_skills, read_skill, search_database

_SKILL_TOOLS: list[Any] = [list_skills, read_skill]


# ── Worker 노드 ──────────────────────────────────────────────


async def worker_chat(state: State, **kwargs: Any) -> dict[str, Any]:
    """create_agent() 기반 worker 노드.

    특징:
    - @tool로 정의한 커스텀 도구를 에이전트에 전달
    - system_prompt로 에이전트의 역할 지정
    - middleware로 운영 정책 적용 가능 (요약, fallback 등)

    스킬 도구 포함 여부:
        모듈 상단의 ``_SKILL_TOOLS`` 리스트로 제어합니다.
        스킬이 불필요하면 빈 리스트로 변경하세요.
        preset의 ``include_skill_tools`` opt-in 방식과는 독립적입니다.
    """
    messages = state.get("messages", [])

    agent = create_agent(
        model="openai:gpt-4o-mini",
        tools=[get_current_time, search_database, *_SKILL_TOOLS],
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
