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

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from langchain.agents.middleware.types import AgentMiddleware

# ── trigger / keep 값 변환 ─────────────────────────────────────

_TriggerUnit = Literal["tokens", "messages", "fraction"]
_TriggerValue = tuple[_TriggerUnit, int | float]


def _parse_condition(raw: int | float | tuple[str, int | float]) -> _TriggerValue:
    """사용자 친화적 값을 라이브러리 튜플 형식으로 변환합니다.

    - ``int``  → ``("tokens", value)``
    - ``float`` (0~1) → ``("fraction", value)``
    - ``tuple``  → 그대로 통과
    """
    if isinstance(raw, tuple):
        return raw  # type: ignore[return-value]
    if isinstance(raw, float):
        return ("fraction", raw)
    return ("tokens", raw)


def create_summarization_middleware(
    *,
    model: str = "openai:gpt-4o-mini",
    trigger: int | float | tuple[str, int | float] | None = None,
    keep: int | float | tuple[str, int | float] = ("messages", 20),
    summary_prompt: str | None = None,
) -> AgentMiddleware:
    """대화 요약 미들웨어를 생성합니다.

    Args:
        model: 요약에 사용할 모델 식별자.
        trigger: 요약을 시작할 조건.
            int → 토큰 수 기준 (``("tokens", n)``).
            float (0~1) → 컨텍스트 윈도우 비율 (``("fraction", f)``).
            tuple → 직접 지정 (``("messages", 10)`` 등).
            None → 라이브러리 기본값 사용.
        keep: 요약 후 유지할 최근 컨텍스트 양.
            int → 토큰 수, float → 비율, tuple → 직접 지정.
            기본값: ``("messages", 20)``.
        summary_prompt: 커스텀 요약 프롬프트 템플릿.

    적합한 경우:
        - 장시간 대화 에이전트 (고객 상담, 리서치)
        - 컨텍스트 윈도우가 작은 모델 사용 시
    """
    # NOTE: 선택적 미들웨어의 heavy dependency 로딩을 사용 시점까지 지연
    from langchain.agents.middleware import SummarizationMiddleware

    kwargs: dict[str, object] = {
        "model": model,
        "keep": _parse_condition(keep),
    }
    if trigger is not None:
        kwargs["trigger"] = _parse_condition(trigger)
    if summary_prompt is not None:
        kwargs["summary_prompt"] = summary_prompt

    return SummarizationMiddleware(**kwargs)
