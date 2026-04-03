"""Worker 노드 예시 — create_deep_agent() 활용.

create_deep_agent()로 만든 리서치 에이전트를 서브에이전트로 사용하는 패턴입니다.
planning, filesystem, subagent, summarization 미들웨어가 자동 구성되어,
복잡한 질문에 대해 계획을 세우고 단계별로 처리합니다.
스킬 도구(list_skills, read_skill)가 기본 포함되어 에이전트가
SKILL.md를 탐색·읽고, 지침에 따라 작업을 수행할 수 있습니다.

사용법:
    custom.py의 build_custom()에서 worker_type="deep"을 지정합니다.

    build_custom(worker_type="deep")
"""

from __future__ import annotations

from typing import Any

from deepagents import create_deep_agent
from langchain.tools import tool

from agents.backends import create_filesystem_backend
from agents.state import State
from agents.tools import list_skills, read_skill

# ── 커스텀 도구 정의 ──────────────────────────────────────────


@tool
def search_web(query: str) -> str:
    """웹에서 정보를 검색합니다."""
    # 실제 서비스에서는 검색 API로 교체
    return f"[웹 검색 결과] '{query}'에 대한 검색 결과: 샘플 데이터"


@tool
def read_document(path: str) -> str:
    """문서를 읽어서 내용을 반환합니다."""
    # 실제 서비스에서는 파일 시스템이나 S3 등에서 읽기
    return f"[문서 내용] '{path}' 파일의 내용: 샘플 문서 텍스트"


# ── Worker 노드 ──────────────────────────────────────────────


async def worker_deep(state: State, **kwargs: Any) -> dict[str, Any]:
    """create_deep_agent() 기반 worker 노드.

    특징:
    - planning: 복잡한 질문을 하위 작업으로 분해
    - subagent: 하위 작업을 서브에이전트에게 위임
    - summarization: 결과를 요약하여 최종 응답 생성
    - filesystem: 가상 파일시스템으로 중간 결과 관리
    - list_skills, read_skill 스킬 도구가 기본 포함

    Note:
        에이전트를 매 호출마다 생성합니다. API 서빙 환경(SSE 등)에서
        동시 요청 간 백엔드 상태 격리를 보장하기 위한 의도적 설계입니다.
    """
    messages = state.get("messages", [])

    agent = create_deep_agent(
        model="openai:gpt-4o-mini",
        tools=[search_web, read_document, list_skills, read_skill],
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
