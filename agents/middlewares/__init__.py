"""커스텀 미들웨어 모음.

운영 정책(요약, fallback, 로깅 등)을 미들웨어로 정의합니다.
create_agent(), create_deep_agent()의 middleware 파라미터에 전달합니다.

사용법:
    from agents.middlewares import my_middleware
"""

from __future__ import annotations
