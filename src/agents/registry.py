"""Registry for agent presets.

각 preset의 메타 정보를 제공합니다.
build_graph(preset=...) 로 실제 그래프를 생성할 수 있습니다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PresetInfo:
    name: str
    description: str
    factory: str  # 내부적으로 사용하는 팩토리 함수명

    def __str__(self) -> str:
        return f"{self.name}: {self.description}"


PRESETS: dict[str, PresetInfo] = {
    "chat": PresetInfo(
        name="chat",
        description="langchain create_agent() 기반 대화형 에이전트",
        factory="langchain.agents.create_agent",
    ),
    "deep_research": PresetInfo(
        name="deep_research",
        description="deepagents create_deep_agent() 기반 리서치 에이전트 (planning, filesystem, subagents)",
        factory="deepagents.create_deep_agent",
    ),
    "custom": PresetInfo(
        name="custom",
        description="수동 StateGraph 노드 조합 (LLM 없이 테스트/프로토타이핑용)",
        factory="agents.graph_builder._build_custom",
    ),
}


def list_presets() -> list[PresetInfo]:
    """등록된 모든 preset 목록을 반환합니다."""
    return list(PRESETS.values())


def get_preset(name: str) -> PresetInfo | None:
    """이름으로 preset 정보를 조회합니다."""
    return PRESETS.get(name)
