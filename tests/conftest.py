"""테스트 공통 픽스처."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _fake_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenAI API 키가 없어도 그래프 빌드/노드 생성이 가능하도록 더미 키를 설정합니다."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")
