"""Postprocessor 노드 — worker 결과를 최종 출력 형태로 변환."""

from __future__ import annotations

from typing import Any, Dict

from agents.state import State


def postprocessor(state: State, **kwargs: Any) -> Dict[str, Any]:
    """_worker_outputs에서 최종 결과를 추출하여 OutputState에 매핑합니다."""
    worker_outputs = state.get("_worker_outputs", [])

    if not worker_outputs:
        return {
            "status": "error",
            "data": {"message": "No worker output received"},
        }

    # 첫 번째 worker output 사용 (multi-worker 시 확장 가능)
    worker_output = worker_outputs[0]

    return {
        "status": worker_output.get("status", "error"),
        "data": worker_output.get("data", {}),
    }
