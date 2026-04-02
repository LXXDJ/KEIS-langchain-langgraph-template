"""미들웨어: 모델 폴백 — 주 모델 실패 시 대체 모델 자동 전환.

주 모델이 장애·레이트 리밋 등으로 응답하지 않을 때,
사전에 설정한 대체 모델로 자동 전환합니다.

사용법:
    from agents.middlewares import create_model_fallback_middleware

    agent = create_deep_agent(
        middleware=[create_model_fallback_middleware(
            "anthropic:claude-3-5-sonnet",
            "openai:gpt-4o",
        )],
    )
"""

from __future__ import annotations

from typing import Any


def create_model_fallback_middleware(
    *models: str,
) -> Any:
    """모델 폴백 미들웨어를 생성합니다.

    Args:
        *models: 대체 모델 식별자 목록 (순서대로 시도).
            첫 번째 모델부터 시도하고, 실패 시 다음 모델로 전환합니다.

    적합한 경우:
        - 프로덕션 환경에서 모델 장애 대비
        - 멀티 프로바이더 구성 (OpenAI → Anthropic → 기타)
        - 레이트 리밋 초과 시 자동 우회
    """
    from langchain.middleware import ModelFallbackMiddleware

    if not models:
        raise ValueError("최소 하나의 대체 모델을 지정해야 합니다.")

    return ModelFallbackMiddleware(models[0], *models[1:])
