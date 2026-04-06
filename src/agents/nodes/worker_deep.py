"""Worker 노드 예시 — create_deep_agent() 활용.

create_deep_agent()로 만든 리서치 에이전트를 서브에이전트로 사용하는 패턴입니다.
planning, filesystem, subagent, summarization 미들웨어가 자동 구성되어,
복잡한 질문에 대해 계획을 세우고 단계별로 처리합니다.
agents/tools/에 정의된 도구를 import하여 에이전트에 전달합니다.

사용법:
    custom.py에서 이 모듈을 worker로 import합니다::

        from agents.nodes import worker_deep as worker
"""

from __future__ import annotations

from typing import Any

from deepagents import create_deep_agent
from langchain_core.tools import BaseTool

from agents.backends import create_filesystem_backend
from agents.state import State
from agents.tools import list_skills, read_document, read_skill, search_web

_SKILL_TOOLS: list[BaseTool] = [list_skills, read_skill]


# ── Worker 노드 ──────────────────────────────────────────────


async def worker_deep(state: State, **kwargs: Any) -> dict[str, Any]:
    """create_deep_agent() 기반 worker 노드.

    특징:
    - planning: 복잡한 질문을 하위 작업으로 분해
    - subagent: 하위 작업을 서브에이전트에게 위임
    - summarization: 결과를 요약하여 최종 응답 생성
    - filesystem: 가상 파일시스템으로 중간 결과 관리

    스킬 도구 포함 여부:
        모듈 상단의 ``_SKILL_TOOLS`` 리스트로 제어합니다.
        스킬이 불필요하면 빈 리스트로 변경하세요.
        preset의 ``include_skill_tools`` opt-in 방식과는 독립적이므로,
        여기서 이미 스킬 도구를 추가한 경우 preset에서 중복 지정하지 마세요.

    Note:
        에이전트를 매 호출마다 생성합니다. API 서빙 환경(SSE 등)에서
        동시 요청 간 백엔드 상태 격리를 보장하기 위한 의도적 설계입니다.
    """
    messages = state.get("messages", [])

    agent = create_deep_agent(
        model="openai:gpt-4o-mini",
        tools=[search_web, read_document, *_SKILL_TOOLS],
        backend=create_filesystem_backend(),
        system_prompt=(
            "당신은 심층 리서치 에이전트입니다. "
            "복잡한 질문에 대해 계획을 세우고, "
            "도구를 활용하여 단계별로 조사한 뒤, "
            "구조화된 답변을 작성하세요. "
            "필요시 list_skills로 스킬을 조회하고, "
            "read_skill로 스킬의 지침을 읽어 활용하세요."
        ),
        # subagents=[...],  # 필요 시 서브에이전트 추가
        # skills=[...],     # 필요 시 네이티브 스킬 추가
        # memory=[...],     # 필요 시 메모리 추가
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
