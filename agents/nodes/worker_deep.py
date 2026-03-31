"""Worker 노드 예시 — create_deep_agent() 활용.

create_deep_agent()로 만든 리서치 에이전트를 서브에이전트로 사용하는 패턴입니다.
planning, filesystem, subagent, summarization 미들웨어가 자동 구성되어,
복잡한 질문에 대해 계획을 세우고 단계별로 처리합니다.

사용법:
    custom.py의 build_custom()에서 worker 노드를 이 함수로 교체합니다.

    # agents/presets/custom.py
    from agents.nodes.worker_deep import worker_deep
    builder.add_node("worker", worker_deep)
"""

from __future__ import annotations

from typing import Any

from deepagents import create_deep_agent
from langchain.tools import tool

from agents.state import State

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
    """
    messages = state.get("messages", [])

    agent = create_deep_agent(
        model="openai:gpt-4o-mini",
        tools=[search_web, read_document],
        system_prompt=(
            "당신은 심층 리서치 에이전트입니다. "
            "복잡한 질문에 대해 계획을 세우고, "
            "도구를 활용하여 단계별로 조사한 뒤, "
            "구조화된 답변을 작성하세요."
        ),
        # subagents=[...],  # 필요 시 서브에이전트 추가
        # skills=[...],     # 필요 시 스킬 추가
        # memory=[...],     # 필요 시 메모리 추가
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
