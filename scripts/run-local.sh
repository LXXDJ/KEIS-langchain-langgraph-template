#!/usr/bin/env bash
# ── run-local.sh ─────────────────────────────────────────────
# 로컬 환경에서 LangServe 개발 서버를 실행합니다.
#
# 사용법:
#   ./scripts/run-local.sh          # 기본 (host=0.0.0.0, port=8000)
#   PORT=8080 ./scripts/run-local.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
RELOAD="${RELOAD:-true}"

# ── uv 확인 ─────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo "Error: uv가 설치되어 있지 않습니다."
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  또는 https://docs.astral.sh/uv/getting-started/installation/ 참고"
    exit 1
fi

# ── .env 로드 (있을 경우) ─────────────────────────────────────
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "Loading .env ..."
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
fi

# ── 서버 실행 ─────────────────────────────────────────────────
echo ""
echo "  lcdaf LangServe"
echo "  http://${HOST}:${PORT}"
echo "  docs: http://${HOST}:${PORT}/docs"
echo ""

cd "$PROJECT_ROOT"

RELOAD_FLAG=""
if [ "$RELOAD" = "true" ]; then
    RELOAD_FLAG="--reload"
fi

exec uv run uvicorn app.run:app \
    --host "$HOST" \
    --port "$PORT" \
    $RELOAD_FLAG
