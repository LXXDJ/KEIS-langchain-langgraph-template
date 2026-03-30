"""LangServe / Raw FastAPI 서버 진입점.

환경변수 LCDAF_SERVING 으로 서빙 모드를 선택합니다:
  - "langserve" (기본) : LangServe add_routes 기반 (playground 포함)
  - "raw"              : 직접 FastAPI 구성 (/invoke, /stream, /info)

Usage:
    python -m app.run
    uvicorn app.run:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os

import uvicorn

serving_mode = os.getenv("LCDAF_SERVING", "langserve")

if serving_mode == "raw":
    from app.utils.server_raw import create_raw_app

    app = create_raw_app()
else:
    from app.utils.server import create_app

    app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.run:app", host="0.0.0.0", port=port, reload=True)
