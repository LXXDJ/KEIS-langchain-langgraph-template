"""Worker 노드 — 노드 안에서 create_agent()를 서브 에이전트로 사용하는 패턴.

핵심 패턴:
  1. 노드 함수 안에서 create_agent()로 에이전트를 생성
  2. tools, system_prompt를 동적으로 구성
  3. state의 messages를 그대로 전달
"""

from __future__ import annotations

from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage

from agents.state import State


async def worker(state: State, **kwargs: Any) -> Dict[str, Any]:
    """기본 worker 노드 (LLM 없이 테스트용).

    실제 LLM 호출 없이 custom preset의 기본 동작을 확인할 때 사용합니다.
    LLM을 사용하는 worker는 worker_chat.py, worker_deep.py를 참고하세요.
    """
    messages = state.get("messages", [])
    last_content = ""
    if messages:
        last = messages[-1]
        last_content = last.content if hasattr(last, "content") else str(last)

    return {
        "_worker_outputs": [{
            "status": "success",
            "data": {"response": f"Processed: {last_content}"},
        }],
    }
