# CLAUDE.md

이 프로젝트에서 Claude를 사용하여 코드를 작성할 때 반드시 따라야 하는 규칙입니다.

## 프로젝트 개요

LangChain, LangGraph, Deep Agents 기반 에이전트 개발 보일러플레이트 템플릿.
preset 시스템으로 에이전트 유형을 선택하고, 모든 preset은 동일한 messages 기반 입출력을 사용합니다.

## 실행 방법

```bash
cp .env.example .env   # AGENT_PRESET, OPENAI_API_KEY 설정
./scripts/run-local.sh # uv 기반 로컬 실행
./scripts/run-docker.sh # Docker 실행
```

## 폴더 구조 규칙

```
agents/              # 에이전트 구현 (그래프, 노드, 상태, 프리셋)
  ├─ presets/        # 그래프 빌더 함수 (build_custom, build_chat, build_deep_research)
  ├─ nodes/          # 개별 노드 함수 (async only)
  ├─ tools/          # 범용 도구 (@tool). worker 전용 도구는 해당 worker 파일 안에 정의
  ├─ skills/         # Deep Agents 스킬 (재사용 가능한 능력 단위)
  ├─ backends/       # 백엔드 구현 (파일시스템, 스토리지, 메모리 등)
  ├─ middlewares/    # 커스텀 미들웨어 (운영 정책: 요약, fallback, 로깅 등)
  ├─ state.py        # State 정의 (이 파일 하나에서만 관리)
  └─ registry.py     # preset 메타 정보
app/                 # 서빙 레이어 (FastAPI + LangServe)
  └─ utils/          # 서버 팩토리, langgraph.json 로더, 스키마
docs/ko/             # 한국어 문서
scripts/             # 실행 스크립트
examples/            # preset별 사용 예시
```

### 새 파일 위치 규칙

- 새 노드 → `agents/nodes/` 에 추가하고 `agents/nodes/__init__.py`에 export
- 새 preset → `agents/presets/` 에 추가하고 `agents/presets/__init__.py`에 export, `agents/registry.py`에 메타 등록
- 새 도구(@tool) → 특정 worker 전용이면 해당 worker 파일 안에 정의, 범용이면 `agents/tools/`
- 새 스킬 → `agents/skills/` 에 추가하고 `__init__.py`에 export
- 새 백엔드 → `agents/backends/` 에 추가하고 `__init__.py`에 export
- 새 미들웨어 → `agents/middlewares/` 에 추가하고 `__init__.py`에 export
- 서빙 관련 유틸 → `app/utils/`
- 문서 → `docs/ko/`

### 금지 사항

- `agents/` 에 서빙 로직 넣지 않기 (에이전트와 서빙의 관심사 분리)
- `app/` 에서 노드나 State를 직접 정의하지 않기
- `state.py` 외의 파일에서 State TypedDict를 새로 정의하지 않기
- 루트에 Python 소스 파일 넣지 않기

## 코딩 컨벤션

### Python 스타일

- Python 3.12+ 기준
- `from __future__ import annotations` 를 모든 .py 파일에 추가 (독스트링이 있으면 독스트링 바로 다음)
- 타입 힌트 필수: PEP 604 스타일 (`str | None`, not `Optional[str]`), 소문자 제네릭 (`list[T]`, `dict[K, V]`)
- 독스트링: 한국어로 작성, 모듈·클래스·공개 함수에 필수
- 식별자(변수명, 함수명, 클래스명): 영어만 사용
- 주석: 한국어 또는 영어, 섹션 구분 시 `# ── 섹션명 ──────` 형식 사용

### Import 순서

```python
from __future__ import annotations          # 1. __future__

import os                                    # 2. 표준 라이브러리
from typing import Any, Literal

from langchain_core.messages import AnyMessage  # 3. 서드파티
from langgraph.graph import StateGraph

from agents.state import State               # 4. 로컬
```

### 노드 함수 작성 규칙

```python
async def my_node(state: State, **kwargs: Any) -> dict[str, Any]:
    """노드 설명 (한국어)."""
    # 구현
    return {"필드명": 값}
```

- 반드시 `async def`
- 시그니처: `(state: State, **kwargs: Any) -> dict[str, Any]`
- State 필드 접근 시 `.get()` 사용 (KeyError 방지): `state.get("messages", [])`
- 반환값은 State 필드명을 키로 하는 dict

### State 규칙

- 모든 State는 `agents/state.py` 에서 정의
- 4분리 패턴 유지: `InputState`, `InternalState`, `OutputState`, `Context`
- `State = InputState + InternalState + OutputState` (합집합)
- 내부 전용 필드는 `_` 접두사: `_worker_outputs`
- 새 필드 추가 시 어느 State에 속하는지 명확히 구분할 것
- `total=False` 유지 (모든 필드 선택적)

### Preset 규칙

- 모든 preset은 `CompiledStateGraph`를 반환
- 모든 preset은 `messages: list[AnyMessage]` 입출력 인터페이스를 사용
- custom preset의 worker 교체는 `worker_type` 파라미터 사용 (`_WORKER_MAP` 패턴)
- 주석으로 코드를 on/off 하지 않기

### 네이밍

| 대상 | 규칙 | 예시 |
|------|------|------|
| 파일명 | snake_case | `worker_chat.py` |
| 함수 | snake_case | `build_custom()` |
| 클래스 | PascalCase | `InputState` |
| 상수 | UPPER_SNAKE + `_` 접두사(모듈 private) | `_PRESET_DEEP_RESEARCH` |
| State 내부 필드 | `_` 접두사 | `_worker_outputs` |
| Literal 타입 | PascalCase | `WorkerType`, `Preset` |

## Git 규칙

- 브랜치: `dev` → `feat/기능명` 분기
- 커밋 메시지: 한국어 본문, conventional commits prefix (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`)
- `.env` 파일은 절대 커밋하지 않기 (`.gitignore`에 포함됨)
- `.idea/`, `__pycache__/`, `.venv/` 커밋하지 않기
