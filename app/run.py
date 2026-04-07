"""LangServe 서버 진입점.

환경변수(``HOST``, ``PORT``, ``RELOAD``)는 ``.env`` 또는 셸에서 주입할 수 있으며,
미설정 시 아래 기본값으로 동작합니다.

Usage:
    python -m app.run
    uvicorn app.run:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os

import uvicorn
from dotenv import load_dotenv

from app.utils.server import create_app

load_dotenv()

app = create_app()


def _env_bool(name: str, default: bool) -> bool:
    """환경변수를 bool로 해석합니다 (true/1/yes → True)."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = _env_bool("RELOAD", default=True)
    uvicorn.run("app.run:app", host=host, port=port, reload=reload)
