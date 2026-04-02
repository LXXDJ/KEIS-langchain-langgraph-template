"""agents/middlewares 팩토리 함수 단위 테스트.

검증 항목
---------
1. 모듈 임포트 정상 여부
2. 기본 파라미터로 인스턴스 생성
3. AgentMiddleware 서브클래스 여부 (반환 타입 계약)
4. 필수 파라미터 누락 시 TypeError / ValueError
5. 커스텀 파라미터가 인스턴스에 반영되는지
"""

from __future__ import annotations

import pytest
from langchain.agents.middleware.types import AgentMiddleware

from agents.middlewares import (
    create_context_editing_middleware,
    create_hitl_middleware,
    create_model_call_limit_middleware,
    create_model_fallback_middleware,
    create_model_retry_middleware,
    create_pii_detection_middleware,
    create_summarization_middleware,
    create_todo_list_middleware,
    create_tool_call_limit_middleware,
    create_tool_emulator_middleware,
    create_tool_retry_middleware,
    create_tool_selector_middleware,
)


# ── 공통 헬퍼 ─────────────────────────────────────────────────


def _assert_is_middleware(obj: object) -> None:
    """AgentMiddleware 서브클래스인지 검증합니다."""
    assert isinstance(obj, AgentMiddleware), (
        f"{type(obj).__name__}은(는) AgentMiddleware의 인스턴스가 아닙니다."
    )


# ── Summarization ──────────────────────────────────────────────


class TestSummarizationMiddleware:
    """create_summarization_middleware 팩토리 테스트."""

    def test_default_params(self) -> None:
        mw = create_summarization_middleware()
        _assert_is_middleware(mw)

    def test_trigger_as_int_tokens(self) -> None:
        mw = create_summarization_middleware(trigger=8000)
        _assert_is_middleware(mw)

    def test_trigger_as_float_fraction(self) -> None:
        mw = create_summarization_middleware(trigger=0.8)
        _assert_is_middleware(mw)

    def test_trigger_as_tuple(self) -> None:
        mw = create_summarization_middleware(trigger=("messages", 10))
        _assert_is_middleware(mw)

    def test_keep_as_int(self) -> None:
        mw = create_summarization_middleware(keep=2000)
        _assert_is_middleware(mw)

    def test_custom_summary_prompt(self) -> None:
        mw = create_summarization_middleware(summary_prompt="요약: {messages}")
        _assert_is_middleware(mw)


# ── Context Editing ────────────────────────────────────────────


class TestContextEditingMiddleware:
    """create_context_editing_middleware 팩토리 테스트."""

    def test_default_params(self) -> None:
        mw = create_context_editing_middleware()
        _assert_is_middleware(mw)

    def test_custom_params(self) -> None:
        mw = create_context_editing_middleware(
            trigger=8000,
            keep=5,
            clear_tool_inputs=True,
            exclude_tools=["important_tool"],
            placeholder="[생략됨]",
        )
        _assert_is_middleware(mw)


# ── Human-in-the-Loop ─────────────────────────────────────────


class TestHitlMiddleware:
    """create_hitl_middleware 팩토리 테스트."""

    def test_with_bool_config(self) -> None:
        mw = create_hitl_middleware(interrupt_on={"execute_sql": True})
        _assert_is_middleware(mw)

    def test_with_detailed_config(self) -> None:
        mw = create_hitl_middleware(
            interrupt_on={
                "execute_sql": {
                    "allowed_decisions": ["approve", "edit", "reject"],
                },
                "send_email": True,
            },
        )
        _assert_is_middleware(mw)

    def test_missing_interrupt_on_raises(self) -> None:
        with pytest.raises(TypeError):
            create_hitl_middleware()  # type: ignore[call-arg]


# ── Model Call Limit ───────────────────────────────────────────


class TestModelCallLimitMiddleware:
    """create_model_call_limit_middleware 팩토리 테스트."""

    def test_no_limit_raises(self) -> None:
        """thread_limit과 run_limit 모두 None이면 ValueError."""
        with pytest.raises(ValueError, match="At least one limit"):
            create_model_call_limit_middleware()

    def test_run_limit(self) -> None:
        mw = create_model_call_limit_middleware(run_limit=10)
        _assert_is_middleware(mw)

    def test_thread_limit(self) -> None:
        mw = create_model_call_limit_middleware(thread_limit=100)
        _assert_is_middleware(mw)

    def test_exit_behavior_error(self) -> None:
        mw = create_model_call_limit_middleware(run_limit=5, exit_behavior="error")
        _assert_is_middleware(mw)


# ── Model Fallback ─────────────────────────────────────────────


class TestModelFallbackMiddleware:
    """create_model_fallback_middleware 팩토리 테스트."""

    def test_single_model(self) -> None:
        mw = create_model_fallback_middleware(models=["openai:gpt-4o"])
        _assert_is_middleware(mw)

    def test_multiple_models(self) -> None:
        mw = create_model_fallback_middleware(
            models=["openai:gpt-4o", "openai:gpt-4o-mini"],
        )
        _assert_is_middleware(mw)

    def test_empty_models_raises(self) -> None:
        with pytest.raises(ValueError, match="최소 하나의 대체 모델"):
            create_model_fallback_middleware(models=[])

    def test_keyword_only(self) -> None:
        """models는 keyword-only 파라미터여야 합니다."""
        with pytest.raises(TypeError):
            create_model_fallback_middleware(["openai:gpt-4o"])  # type: ignore[misc]


# ── Model Retry ────────────────────────────────────────────────


class TestModelRetryMiddleware:
    """create_model_retry_middleware 팩토리 테스트."""

    def test_default_params(self) -> None:
        mw = create_model_retry_middleware()
        _assert_is_middleware(mw)

    def test_custom_retries(self) -> None:
        mw = create_model_retry_middleware(max_retries=5, backoff_factor=3.0)
        _assert_is_middleware(mw)

    def test_on_failure_error(self) -> None:
        mw = create_model_retry_middleware(on_failure="error")
        _assert_is_middleware(mw)

    def test_on_failure_default_is_continue(self) -> None:
        """on_failure 기본값이 'continue'인지 확인합니다."""
        mw = create_model_retry_middleware()
        assert str(mw.on_failure) == "continue"


# ── Tool Call Limit ────────────────────────────────────────────


class TestToolCallLimitMiddleware:
    """create_tool_call_limit_middleware 팩토리 테스트."""

    def test_no_limit_raises(self) -> None:
        """thread_limit과 run_limit 모두 None이면 ValueError."""
        with pytest.raises(ValueError, match="At least one limit"):
            create_tool_call_limit_middleware()

    def test_specific_tool(self) -> None:
        mw = create_tool_call_limit_middleware(tool_name="search_web", run_limit=5)
        _assert_is_middleware(mw)


# ── Tool Retry ─────────────────────────────────────────────────


class TestToolRetryMiddleware:
    """create_tool_retry_middleware 팩토리 테스트."""

    def test_default_params(self) -> None:
        mw = create_tool_retry_middleware()
        _assert_is_middleware(mw)

    def test_custom_params(self) -> None:
        mw = create_tool_retry_middleware(
            max_retries=5,
            tools=["search_web"],
            jitter=False,
        )
        _assert_is_middleware(mw)

    def test_on_failure_default_is_continue(self) -> None:
        """model_retry와 동일한 on_failure 기본값을 사용하는지 확인합니다."""
        mw = create_tool_retry_middleware()
        assert str(mw.on_failure) == "continue"


# ── PII Detection ──────────────────────────────────────────────


class TestPiiDetectionMiddleware:
    """create_pii_detection_middleware 팩토리 테스트."""

    def test_email_redact(self) -> None:
        mw = create_pii_detection_middleware(pii_type="email")
        _assert_is_middleware(mw)

    def test_credit_card_block(self) -> None:
        mw = create_pii_detection_middleware(pii_type="credit_card", strategy="block")
        _assert_is_middleware(mw)

    def test_missing_pii_type_raises(self) -> None:
        with pytest.raises(TypeError):
            create_pii_detection_middleware()  # type: ignore[call-arg]

    def test_selective_apply(self) -> None:
        mw = create_pii_detection_middleware(
            pii_type="ip",
            apply_to_input=False,
            apply_to_output=True,
            apply_to_tool_results=False,
        )
        _assert_is_middleware(mw)


# ── To-Do List ─────────────────────────────────────────────────


class TestTodoListMiddleware:
    """create_todo_list_middleware 팩토리 테스트."""

    def test_default_params(self) -> None:
        mw = create_todo_list_middleware()
        _assert_is_middleware(mw)

    def test_custom_prompts(self) -> None:
        mw = create_todo_list_middleware(
            system_prompt="작업을 단계별로 계획하세요.",
            tool_description="할 일 목록을 관리합니다.",
        )
        _assert_is_middleware(mw)


# ── Tool Selector ──────────────────────────────────────────────


class TestToolSelectorMiddleware:
    """create_tool_selector_middleware 팩토리 테스트."""

    def test_default_params(self) -> None:
        mw = create_tool_selector_middleware()
        _assert_is_middleware(mw)

    def test_custom_params(self) -> None:
        mw = create_tool_selector_middleware(
            max_tools=3,
            always_include=["critical_tool"],
        )
        _assert_is_middleware(mw)


# ── Tool Emulator ──────────────────────────────────────────────


class TestToolEmulatorMiddleware:
    """create_tool_emulator_middleware 팩토리 테스트."""

    def test_default_params(self) -> None:
        mw = create_tool_emulator_middleware()
        _assert_is_middleware(mw)

    def test_specific_tools(self) -> None:
        mw = create_tool_emulator_middleware(tools=["search_web", "execute_sql"])
        _assert_is_middleware(mw)


# ── __init__.py export 완전성 검증 ─────────────────────────────


class TestModuleExports:
    """agents.middlewares.__init__.py의 공개 API가 빠짐없이 export 되는지 검증합니다."""

    EXPECTED_FACTORIES = [
        "create_summarization_middleware",
        "create_context_editing_middleware",
        "create_hitl_middleware",
        "create_model_call_limit_middleware",
        "create_model_fallback_middleware",
        "create_model_retry_middleware",
        "create_tool_call_limit_middleware",
        "create_tool_retry_middleware",
        "create_pii_detection_middleware",
        "create_todo_list_middleware",
        "create_tool_selector_middleware",
        "create_tool_emulator_middleware",
    ]

    def test_all_factories_importable(self) -> None:
        import agents.middlewares as mod

        for name in self.EXPECTED_FACTORIES:
            assert hasattr(mod, name), f"{name}이(가) agents.middlewares에서 export 되지 않았습니다."

    def test_factory_count(self) -> None:
        import agents.middlewares as mod

        public = [n for n in dir(mod) if n.startswith("create_")]
        assert len(public) == len(self.EXPECTED_FACTORIES), (
            f"export된 팩토리 수가 기대값과 다릅니다: {public}"
        )
