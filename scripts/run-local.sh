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

# ── .env 로드 (있을 경우) ─────────────────────────────────────
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "Loading .env ..."
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
fi

# ── Python 버전 확인 ──────────────────────────────────────────
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 12 ]; }; then
    echo "Error: Python >= 3.12 required (found $PYTHON_VERSION)"
    exit 1
fi

# ── 의존성 설치 확인 ──────────────────────────────────────────
if ! python3 -c "import langgraph" 2>/dev/null; then
    echo "Dependencies not found. Installing ..."
    pip install -e "$PROJECT_ROOT"
fi

# ── 서버 실행 ─────────────────────────────────────────────────
echo ""
echo "  lcdaf LangServe"
echo "  http://${HOST}:${PORT}"
echo "  playground: http://${HOST}:${PORT}/default/playground/"
echo "  docs:       http://${HOST}:${PORT}/docs"
echo ""

cd "$PROJECT_ROOT"

RELOAD_FLAG=""
if [ "$RELOAD" = "true" ]; then
    RELOAD_FLAG="--reload"
fi

exec python3 -m uvicorn app.run:app \
    --host "$HOST" \
    --port "$PORT" \
    $RELOAD_FLAG
