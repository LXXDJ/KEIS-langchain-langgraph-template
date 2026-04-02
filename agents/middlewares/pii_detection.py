"""미들웨어: PII 탐지 — 개인정보 탐지·마스킹·차단.

이메일, 신용카드, IP 주소 등 개인식별정보(PII)를
입력·출력·도구 결과에서 탐지하고 처리합니다.

사용법:
    from agents.middlewares import create_pii_detection_middleware

    agent = create_deep_agent(
        middleware=[create_pii_detection_middleware(
            pii_type="email",
            strategy="redact",
        )],
    )
"""

from __future__ import annotations

from typing import Any, Literal


def create_pii_detection_middleware(
    *,
    pii_type: Literal["email", "credit_card", "ip", "mac_address", "url"] | str,
    strategy: Literal["block", "redact", "mask", "hash"] = "redact",
    detector: Any | None = None,
    apply_to_input: bool = True,
    apply_to_output: bool = True,
    apply_to_tool_results: bool = True,
) -> Any:
    """PII 탐지 미들웨어를 생성합니다.

    Args:
        pii_type: 탐지할 PII 유형.
            빌트인: "email", "credit_card", "ip", "mac_address", "url".
            커스텀 문자열도 가능 (detector와 함께 사용).
        strategy: PII 발견 시 처리 전략.
            "block" → 메시지 전체 차단.
            "redact" → PII 부분 삭제 (기본값).
            "mask" → PII를 마스킹 문자로 대체.
            "hash" → PII를 해시값으로 대체.
        detector: 커스텀 탐지기 (정규식 또는 callable).
        apply_to_input: 입력 메시지에 적용 여부.
        apply_to_output: 출력 메시지에 적용 여부.
        apply_to_tool_results: 도구 결과에 적용 여부.

    적합한 경우:
        - 의료·금융 분야 컴플라이언스 요구사항
        - 개인정보 유출 방지가 필요한 서비스
    """
    from langchain.middleware import PIIDetectionMiddleware

    kwargs: dict[str, Any] = {
        "pii_type": pii_type,
        "strategy": strategy,
        "apply_to_input": apply_to_input,
        "apply_to_output": apply_to_output,
        "apply_to_tool_results": apply_to_tool_results,
    }
    if detector is not None:
        kwargs["detector"] = detector

    return PIIDetectionMiddleware(**kwargs)
