"""Preprocessing node — messages 전처리."""

from __future__ import annotations

from typing import Any, Dict

from langchain_core.messages import HumanMessage

from agents.state import State


def preprocess(state: State, **kwargs: Any) -> Dict[str, Any]:
    """입력 messages의 마지막 HumanMessage를 정규화합니다.

    현재는 strip만 수행합니다.
    실제 서비스에서는 입력 검증, 필터링, 언어 감지 등을 추가합니다.
    """
    messages = state.get("messages", [])
    if not messages:
        return {}

    last_message = messages[-1]
    if isinstance(last_message, HumanMessage) and isinstance(last_message.content, str):
        cleaned = last_message.content.strip()
        if cleaned != last_message.content:
            return {"messages": [HumanMessage(content=cleaned)]}

    return {}
