"""Postprocessor 노드 — worker 결과를 messages 출력으로 변환."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from agents.state import State


async def postprocessor(state: State, **kwargs: Any) -> dict[str, Any]:
    """_worker_outputs에서 응답을 추출하여 AIMessage로 반환합니다."""
    worker_outputs = state.get("_worker_outputs", [])

    if not worker_outputs:
        return {
            "messages": [AIMessage(content="No worker output received.")],
        }

    # 첫 번째 worker output 사용 (multi-worker 시 확장 가능)
    worker_output = worker_outputs[0]
    response = worker_output.get("data", {}).get("response", "")

    return {
        "messages": [AIMessage(content=response)],
    }
