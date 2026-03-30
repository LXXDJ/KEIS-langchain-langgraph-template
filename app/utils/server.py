"""FastAPI application factory."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from langchain_core.messages import AnyMessage
from langserve import add_routes
from pydantic import BaseModel

from agents import build_graph, list_presets


# ── LangServe용 Input/Output 스키마 ──────────────────────────
# deepagents 내부 state에 NotRequired + OmitFromSchema 같은
# 복잡한 어노테이션이 있어서, LangServe의 자동 pydantic 스키마
# 생성이 실패합니다.
# LangChain의 AnyMessage 타입을 사용해서 chat playground가
# 메시지 기반 에이전트를 올바르게 인식하도록 합니다.


class ChatInput(BaseModel):
    """messages 기반 preset (chat, deep_research)용 입력 스키마."""

    messages: list[AnyMessage]


class ChatOutput(BaseModel):
    """messages 기반 preset 출력 스키마."""

    messages: list[AnyMessage]


def create_app() -> FastAPI:
    """Build and return a configured FastAPI application.

    환경변수 LCDAF_PRESET 으로 기본 preset을 지정할 수 있습니다.
    기본값은 "custom" (LLM 불필요) 입니다.
    """
    application = FastAPI(title="lcdaf-langserve")

    preset = os.getenv("LCDAF_PRESET", "custom")

    # ── 그래프 빌드 ───────────────────────────────────────────
    graph = build_graph(preset=preset)  # type: ignore[arg-type]

    # ── add_routes 설정 ───────────────────────────────────────
    if preset == "chat":
        # create_agent() → LangServe가 자동으로 스키마 인식 가능
        add_routes(
            application,
            graph,
            path="/default",
        )
    elif preset == "deep_research":
        # create_deep_agent() → 내부 state에 NotRequired + OmitFromSchema
        # 어노테이션이 있어서 자동 스키마 생성 시 pydantic 에러 발생.
        # input/output_type을 명시해서 우회하되, chat playground는
        # 커스텀 스키마를 인식 못하므로 default playground 사용.
        add_routes(
            application,
            graph,
            path="/default",
            input_type=ChatInput,
            output_type=ChatOutput,
        )
    else:
        add_routes(
            application,
            graph,
            path="/default",
        )

    # ── 엔드포인트 ────────────────────────────────────────────
    @application.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse(url="/default/playground/")

    @application.get("/health")
    def health() -> dict:
        return {
            "name": "lcdaf-langserve",
            "status": "ok",
            "preset": preset,
            "graph": "/default",
            "playground": "/default/playground/",
            "docs": "/docs",
        }

    @application.get("/presets")
    def presets() -> list[dict]:
        return [
            {
                "name": p.name,
                "description": p.description,
                "factory": p.factory,
            }
            for p in list_presets()
        ]

    return application
