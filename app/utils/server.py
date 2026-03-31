"""FastAPI application factory."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from langchain_core.messages import AnyMessage
from langserve import add_routes
from pydantic import BaseModel

from agents import build_graph, list_presets
from app.utils.langgraph_loader import load_langgraph_config


# ── LangServe용 Input/Output 스키마 ──────────────────────────
# 모든 preset이 messages 기반 입출력을 사용합니다.


class ChatInput(BaseModel):
    """messages 기반 입력 스키마."""

    messages: list[AnyMessage]


class ChatOutput(BaseModel):
    """messages 기반 출력 스키마."""

    messages: list[AnyMessage]


def create_app() -> FastAPI:
    """Build and return a configured FastAPI application.

    langgraph.json이 있으면 name, version을 읽어
    /{graph_name} 기반 URI를 구성합니다.
    """
    config = load_langgraph_config()

    service_name = config.name if config else "lcdaf"
    service_version = config.version if config else "v0"
    service_description = config.description if config else ""

    application = FastAPI(
        title=service_name,
        version=service_version,
        description=service_description,
    )

    preset = os.getenv("LCDAF_PRESET", "custom")

    # ── 그래프 빌드 ───────────────────────────────────────────
    graph = build_graph(preset=preset)  # type: ignore[arg-type]

    # ── URI 경로 구성 ─────────────────────────────────────────
    graph_name = config.graphs[0].name if config and config.graphs else "default"
    base_path = f"/{graph_name}"

    # ── add_routes ────────────────────────────────────────────
    add_routes(
        application,
        graph,
        path=base_path,
        input_type=ChatInput,
        output_type=ChatOutput,
    )

    # ── 엔드포인트 ────────────────────────────────────────────
    @application.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse(url=f"{base_path}/playground/")

    @application.get("/health")
    def health() -> dict:
        return {
            "name": service_name,
            "version": service_version,
            "status": "ok",
            "preset": preset,
            "graph": base_path,
            "playground": f"{base_path}/playground/",
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
