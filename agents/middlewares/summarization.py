"""미들웨어: 대화 요약 — 토큰 초과 시 자동 압축.

긴 대화가 컨텍스트 윈도우를 초과하지 않도록,
이전 메시지를 자동 요약하고 최근 컨텍스트만 유지합니다.

사용법:
    from agents.middlewares import create_summarization_middleware

    agent = create_deep_agent(
        middleware=[create_summarization_middleware()],
    )
"""

from __future__ import annotations

from typing import Any


def create_summarization_middleware(
    *,
    model: str = "openai:gpt-4o-mini",
    trigger: int | str = 4000,
    keep: int | str = 1000,
    summary_prompt: str | None = None,
) -> Any:
    """대화 요약 미들웨어를 생성합니다.

    Args:
        model: 요약에 사용할 모델 식별자.
        trigger: 요약을 시작할 조건.
            int → 토큰 수 기준, str → "10 messages" 등 메시지 수.
        keep: 요약 후 유지할 최근 컨텍스트 양.
            int → 토큰 수, str → "3 messages" 등.
        summary_prompt: 커스텀 요약 프롬프트 템플릿.

    적합한 경우:
        - 장시간 대화 에이전트 (고객 상담, 리서치)
        - 컨텍스트 윈도우가 작은 모델 사용 시
    """
    from langchain.middleware import SummarizationMiddleware

    kwargs: dict[str, Any] = {
        "model": model,
        "trigger": trigger,
        "keep": keep,
    }
    if summary_prompt is not None:
        kwargs["summary_prompt"] = summary_prompt

    return SummarizationMiddleware(**kwargs)
