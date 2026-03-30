ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# ── 시스템 의존성 ──────────────────────────────────────────
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc git jq && \
    rm -rf /var/lib/apt/lists/*

# ── 프로젝트 소스코드 복사 ────────────────────────────────
COPY . /app
WORKDIR /app

# ── langgraph.json extra_packages 설치 (있을 경우) ────────
RUN if [ -f "langgraph.json" ]; then \
        echo "Found langgraph.json"; \
        EXTRA_PKGS=$(jq -r '.extra_packages // [] | join(" ")' langgraph.json); \
        if [ -n "$EXTRA_PKGS" ]; then \
            echo "Installing extra_packages: ${EXTRA_PKGS}"; \
            apt-get update && apt-get install -y --no-install-recommends ${EXTRA_PKGS} && \
            rm -rf /var/lib/apt/lists/*; \
        else \
            echo "No extra_packages defined in langgraph.json"; \
        fi; \
    else \
        echo "No langgraph.json found, skipping extra_packages"; \
    fi

# ── Python 의존성 설치 ────────────────────────────────────
RUN if [ -f "pyproject.toml" ]; then \
        echo "Installing from pyproject.toml"; \
        pip install --no-cache-dir .; \
    elif [ -f "requirements.txt" ]; then \
        echo "Installing from requirements.txt"; \
        pip install --no-cache-dir -r requirements.txt; \
    else \
        echo "No pyproject.toml or requirements.txt found, skipping pip install"; \
    fi

# ── langgraph.json commands → 시작 스크립트 생성 ──────────
RUN echo '#!/bin/sh' > /app/project_commands.sh && \
    if [ -f "langgraph.json" ]; then \
        echo "Generating project_commands.sh from langgraph.json commands..."; \
        jq -r '.commands // [] | .[]' langgraph.json >> /app/project_commands.sh; \
    fi && \
    chmod +x /app/project_commands.sh

# ── 포트 노출 ─────────────────────────────────────────────
EXPOSE 8000

# ── 서버 실행 ─────────────────────────────────────────────
# 1) langgraph.json commands 실행 (실패해도 계속)
# 2) uvicorn으로 LangServe 앱 기동
CMD ["/bin/sh", "-c", "/app/project_commands.sh || true; python app/run.py"]
