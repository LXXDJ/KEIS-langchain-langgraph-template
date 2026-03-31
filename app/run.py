"""LangServe 서버 진입점.

Usage:
    python -m app.run
    uvicorn app.run:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os

import uvicorn

from app.utils.server import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.run:app", host="0.0.0.0", port=port, reload=True)
