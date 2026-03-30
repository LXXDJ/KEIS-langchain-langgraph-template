#!/usr/bin/env bash
# ── run-docker.sh ────────────────────────────────────────────
# Docker로 lcdaf 컨테이너를 빌드하고 실행합니다.
#
# 사용법:
#   ./scripts/run-docker.sh                  # 빌드 + 실행
#   ./scripts/run-docker.sh --build-only     # 빌드만
#   ./scripts/run-docker.sh --run-only       # 실행만 (이미 빌드된 이미지 사용)
#   PORT=9000 ./scripts/run-docker.sh        # 포트 변경
# ──────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

IMAGE_NAME="${IMAGE_NAME:-lcdaf}"
CONTAINER_NAME="${CONTAINER_NAME:-lcdaf-server}"
PORT="${PORT:-8000}"

DO_BUILD=true
DO_RUN=true

for arg in "$@"; do
    case $arg in
        --build-only) DO_RUN=false ;;
        --run-only)   DO_BUILD=false ;;
        --help|-h)
            echo "Usage: $0 [--build-only | --run-only]"
            echo ""
            echo "Environment variables:"
            echo "  IMAGE_NAME      Docker image name   (default: lcdaf)"
            echo "  CONTAINER_NAME  Container name      (default: lcdaf-server)"
            echo "  PORT            Host port           (default: 8000)"
            exit 0
            ;;
    esac
done

# ── 기존 컨테이너 정리 ───────────────────────────────────────
cleanup_container() {
    if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
        echo "Removing existing container: ${CONTAINER_NAME} ..."
        docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
    fi
}

# ── 빌드 ─────────────────────────────────────────────────────
if [ "$DO_BUILD" = true ]; then
    echo ""
    echo "Building image: ${IMAGE_NAME} ..."
    echo ""
    docker build -t "$IMAGE_NAME" "$PROJECT_ROOT"
    echo ""
    echo "Build complete: ${IMAGE_NAME}"
fi

# ── 실행 ─────────────────────────────────────────────────────
if [ "$DO_RUN" = true ]; then
    cleanup_container

    echo ""
    echo "Starting container: ${CONTAINER_NAME}"
    echo "  http://localhost:${PORT}"
    echo "  playground: http://localhost:${PORT}/default/playground/"
    echo "  docs:       http://localhost:${PORT}/docs"
    echo ""

    # .env 파일이 있으면 전달
    ENV_FILE_FLAG=""
    if [ -f "$PROJECT_ROOT/.env" ]; then
        ENV_FILE_FLAG="--env-file $PROJECT_ROOT/.env"
    fi

    exec docker run \
        --name "$CONTAINER_NAME" \
        -p "${PORT}:8000" \
        $ENV_FILE_FLAG \
        --rm \
        "$IMAGE_NAME"
fi
