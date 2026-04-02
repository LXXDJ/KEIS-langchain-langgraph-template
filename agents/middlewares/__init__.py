"""범용 미들웨어 팩토리 모음.

에이전트 실행 정책(요약, 재시도, 제한, 보안 등)을 미들웨어로 정의합니다.
create_agent(), create_deep_agent()의 middleware 파라미터에 전달합니다.

사용법:
    from agents.middlewares import create_summarization_middleware

    agent = create_deep_agent(
        middleware=[create_summarization_middleware()],
    )
"""

from __future__ import annotations

from agents.middlewares.context_editing import create_context_editing_middleware
from agents.middlewares.human_in_the_loop import create_hitl_middleware
from agents.middlewares.model_call_limit import create_model_call_limit_middleware
from agents.middlewares.model_fallback import create_model_fallback_middleware
from agents.middlewares.model_retry import create_model_retry_middleware
from agents.middlewares.pii_detection import create_pii_detection_middleware
from agents.middlewares.summarization import create_summarization_middleware
from agents.middlewares.todo_list import create_todo_list_middleware
from agents.middlewares.tool_call_limit import create_tool_call_limit_middleware
from agents.middlewares.tool_emulator import create_tool_emulator_middleware
from agents.middlewares.tool_retry import create_tool_retry_middleware
from agents.middlewares.tool_selector import create_tool_selector_middleware

__all__: list[str] = [
    "create_context_editing_middleware",
    "create_hitl_middleware",
    "create_model_call_limit_middleware",
    "create_model_fallback_middleware",
    "create_model_retry_middleware",
    "create_pii_detection_middleware",
    "create_summarization_middleware",
    "create_todo_list_middleware",
    "create_tool_call_limit_middleware",
    "create_tool_emulator_middleware",
    "create_tool_retry_middleware",
    "create_tool_selector_middleware",
]
