"""직접 FastAPI 구성 — LangServe 없이 /invoke, /stream, /info 엔드포인트 제공.

trino_retriever 등 실제 서비스에서 쓰이는 패턴:
- /invoke : 동기식 실행 후 JSON 응답
- /stream : astream_events 기반 SSE 스트리밍
- /info   : 그래프의 input/output 스키마 노출
- /health : 헬스체크

LangServe의 playground가 불필요하거나, SSE 이벤트를 세밀하게 제어해야 할 때 사용합니다.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agents import build_graph, list_presets


def create_raw_app() -> FastAPI:
    """LangServe 없이 직접 FastAPI 앱을 구성합니다."""

    preset = os.getenv("LCDAF_PRESET", "custom")
    graph = build_graph(preset=preset)  # type: ignore[arg-type]

    application = FastAPI(title="lcdaf-raw")

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── /info ─────────────────────────────────────────────────

    @application.get("/info")
    def info_endpoint() -> dict:
        """그래프의 input/output 스키마를 반환합니다."""
        return {
            "name": "lcdaf",
            "preset": preset,
            "input": graph.input_schema.model_json_schema(),
            "output": graph.output_schema.model_json_schema(),
        }

    # ── /health ───────────────────────────────────────────────

    @application.get("/health")
    def health_endpoint() -> dict:
        return {
            "name": "lcdaf-raw",
            "status": "ok",
            "preset": preset,
            "serving": "raw",
        }

    # ── /presets ──────────────────────────────────────────────

    @application.get("/presets")
    def presets_endpoint() -> list[dict]:
        return [
            {"name": p.name, "description": p.description, "factory": p.factory}
            for p in list_presets()
        ]

    # ── /invoke ───────────────────────────────────────────────

    @application.post("/invoke")
    async def invoke_endpoint(request: Request) -> Any:
        """그래프를 동기식으로 실행하고 결과를 반환합니다.

        Request body:
            {"input": {...}, "config": {...}}
        또는 input만:
            {"query": "...", ...}
        """
        payload = await request.json()
        input_data = payload.get("input", payload)
        config = _build_config(request, payload.get("config"))

        result = await graph.ainvoke(input_data, config=config)
        return result

    # ── /stream ───────────────────────────────────────────────

    @application.post("/stream")
    async def stream_endpoint(request: Request) -> StreamingResponse:
        """astream_events 기반 SSE 스트리밍.

        on_custom_event를 SSE data로 전달합니다.
        클라이언트에서 EventSource로 소비하면 됩니다.
        """
        payload = await request.json()
        input_data = payload.get("input", payload)
        config = _build_config(request, payload.get("config"))

        async def event_generator():
            async for event in graph.astream_events(input_data, config=config):
                kind = event["event"]

                # 커스텀 이벤트 전달
                if kind == "on_custom_event":
                    data = json.dumps(
                        {"name": event["name"], "data": event["data"]},
                        ensure_ascii=False,
                    )
                    yield f"event: custom\ndata: {data}\n\n"

                # 노드 완료 이벤트
                elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                    output = event.get("data", {}).get("output", {})
                    data = json.dumps(output, ensure_ascii=False)
                    yield f"event: end\ndata: {data}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
        )

    return application


def _build_config(request: Request, config_override: dict | None = None) -> dict:
    """요청 헤더에서 RunnableConfig를 구성합니다."""
    if config_override:
        return config_override

    graph_id = str(uuid.uuid4())
    headers = request.headers

    return {
        "recursion_limit": 100,
        "configurable": {
            "graph_id": graph_id,
            "x-employee-number": headers.get("x-employee-number"),
            "x-conversation-id": headers.get("x-conversation-id"),
        },
    }
