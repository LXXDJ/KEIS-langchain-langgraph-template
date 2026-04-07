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
    "ai_search_summary": PresetInfo(
        name="ai_search_summary",
        description="고용24 검색 결과를 한국어 2~3줄로 요약하는 SVC-3 에이전트",
        factory="agents.presets.ai_search_summary.build_ai_search_summary",
    ),
}


def list_presets() -> list[PresetInfo]:
    """등록된 모든 preset 목록을 반환합니다."""
    return list(PRESETS.values())


def get_preset(name: str) -> PresetInfo | None:
    """이름으로 preset 정보를 조회합니다."""
    return PRESETS.get(name)
