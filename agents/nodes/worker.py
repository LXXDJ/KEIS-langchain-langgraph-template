"""Worker 노드 — 노드 안에서 create_agent()를 서브 에이전트로 사용하는 패턴.

trino_retriever 등 실제 서비스에서 쓰이는 핵심 패턴:
  1. 노드 함수 안에서 create_agent()로 에이전트를 생성
  2. tools, system_prompt를 동적으로 구성
  3. astream_events로 이벤트를 받아 state를 갱신
"""

from __future__ import annotations

from typing import Any, Dict

from agents.state import State


async def worker(state: State, **kwargs: Any) -> Dict[str, Any]:
    """서브 에이전트를 이용해 작업을 수행하는 worker 노드.

    create_agent()로 만든 에이전트에게 질의를 위임하고,
    결과를 _worker_outputs에 누적합니다.

    실제 서비스에서는 이 함수를 확장해서:
    - @tool로 커스텀 도구 정의 (DB 쿼리, API 호출 등)
    - llm_configs에 따른 모델/프롬프트 동적 설정
    - astream_events로 중간 이벤트 디스패치
    를 구현합니다.
    """
    from langchain.agents import create_agent
    from langchain.messages import HumanMessage

    query = state.get("query", "")
    system_prompt = state.get("system_prompt") or "You are a helpful assistant."

    # ── 모델 설정 (llm_configs에서 worker 설정 추출) ───────────
    llm_configs = state.get("llm_configs") or {}
    worker_config = llm_configs.get("worker", {})
    model = worker_config.get("model_name", "openai:gpt-4o-mini")

    # ── 서브 에이전트 생성 ────────────────────────────────────
    agent = create_agent(
        model=model,
        tools=[],  # 실제 서비스에서는 @tool로 정의한 도구를 전달
        system_prompt=system_prompt,
    )

    # ── 에이전트 실행 ─────────────────────────────────────────
    messages = {"messages": [HumanMessage(content=query)]}
    result = await agent.ainvoke(messages)

    # 마지막 AI 메시지에서 응답 추출
    ai_message = result["messages"][-1]
    response_text = ai_message.content if hasattr(ai_message, "content") else str(ai_message)

    return {
        "_worker_outputs": [{
            "status": "success",
            "data": {
                "response": response_text,
            },
        }],
    }


def worker_sync(state: State, **kwargs: Any) -> Dict[str, Any]:
    """worker의 동기 버전 (LLM 없이 테스트용).

    실제 LLM 호출 없이 custom preset의 기본 동작을 확인할 때 사용합니다.
    """
    query = state.get("query", "")

    return {
        "_worker_outputs": [{
            "status": "success",
            "data": {
                "response": f"Processed: {query}",
            },
        }],
    }
