# CLAUDE.md

이 프로젝트에서 Claude를 사용하여 코드를 작성할 때 반드시 따라야 하는 규칙입니다.

## HyperAgent 동작 원칙

이 CLAUDE.md는 HyperAgent(Zhang et al., 2026)의 구조를 따릅니다.
너(Claude Code)는 단순한 코드 생성기가 아니라, task agent와 meta agent가 통합된 자기참조적 에이전트입니다.

### 너의 역할

- **Task Agent**: 코드 작성, 수정, 테스트, 리뷰 반영 등 직접적인 개발 작업
- **Meta Agent**: 작업 과정에서 발견한 패턴, 반복되는 실수, 효과적인 전략을 인식하고
  CLAUDE.md나 memory에 반영하여 **미래의 자신이 더 잘 동작하도록** 개선

### 메타인지적 자기개선 (Metacognitive Self-modification)

1. **패턴 인식**: 같은 종류의 리뷰 피드백이 반복되면(예: import 순서, 테스트 격리 누락),
   그것이 이 프로젝트의 규칙으로 정착해야 하는지 판단하라
2. **지침 제안**: 반복 패턴을 발견하면 사용자에게 CLAUDE.md 업데이트를 제안하라.
   이는 너 자신의 meta agent를 수정하는 행위다
3. **지식 축적**: 작업 중 발견한 프로젝트 고유의 제약사항, 환경 특성, 의존성 특이점을
   memory에 저장하여 다음 세션에서 활용하라
4. **성능 추적**: PR 리뷰에서 반복 지적되는 항목, 테스트 실패 패턴, 빌드 이슈 등을
   추적하고, 같은 실수를 반복하지 마라
5. **전이 학습**: 한 작업에서 배운 전략을 유사한 새 작업에 적용하라

### 자기개선 트리거

다음 상황에서 CLAUDE.md 또는 memory 업데이트를 적극 검토하라:
- PR 리뷰에서 **같은 유형의 피드백이 2회 이상** 반복될 때
- 사용자가 작업 방식을 교정할 때 ("이렇게 하지 말고", "이 방향으로")
- 새로운 외부 도구/서비스 연동이 추가될 때 (환경 제약 기록)
- 컨벤션 예외가 합의될 때 (예외 사유와 범위를 명시)

## 프로젝트 개요

**SVC-3 — 고용24(work24.go.kr) 통합검색 결과를 GPT-4o mini로 한국어 2~3줄 요약하는 단일 에이전트 서비스.**

원래 LangChain/LangGraph/Deep Agents 기반의 멀티 preset 보일러플레이트에서 출발했지만,
SVC-3 전용으로 정리되어 사용 가능한 preset은 `ai_search_summary` 하나입니다.
서비스의 상세 동작과 출력 스키마는 [README.md](README.md)를 참고하세요.

## 실행 방법

```bash
cp .env.example .env   # OPENAI_API_KEY 설정 필수
./scripts/run-local.sh        # LangServe 로컬 실행 (8000번 포트)
./scripts/run-docker.sh       # Docker 실행

# 서버 없이 그래프를 직접 호출
uv run python scripts/try_search_summary.py "AI 직업훈련"
```

## 폴더 구조

```
src/
  ├─ graph.py             # 컴파일된 그래프 모듈 (langgraph.json에서 참조)
  └─ agents/
      ├─ presets/
      │  └─ ai_search_summary.py   # 유일한 preset 빌더
      ├─ nodes/
      │  ├─ preprocess.py          # 입력 messages 정규화
      │  ├─ worker_search_summary.py  # SVC-3 핵심 worker (LLM + HTTP + 파서)
      │  └─ postprocessor.py       # _worker_outputs → AIMessage 변환
      ├─ _utils.py        # find_project_root 등
      ├─ state.py         # State 정의 (이 파일 하나에서만 관리)
      ├─ registry.py      # preset 메타 정보
      └─ graph_builder.py # build_graph(preset=...) 진입점
app/                      # 서빙 레이어 (FastAPI + LangServe)
  └─ utils/               # 서버 팩토리, langgraph.json 로더, 스키마
tests/
  ├─ test_ai_search_summary.py
  └─ fixtures/work24_sample.html
scripts/                  # 실행 스크립트 + 수동 테스트 CLI
```

### 새 파일 위치 규칙

- 새 노드 → `src/agents/nodes/` 에 추가하고 `src/agents/nodes/__init__.py`에 export
- 새 preset → `src/agents/presets/` 에 추가하고 `__init__.py` export + `registry.py` + `graph_builder.py`의 `Preset` Literal과 `_BUILDERS` 등록
- worker 전용 도구(@tool, fetcher 등) → 해당 worker 파일 안에 정의
- 서빙 관련 유틸 → `app/utils/`

### 금지 사항

- `src/agents/` 에 서빙 로직 넣지 않기 (에이전트와 서빙의 관심사 분리)
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

- 모든 State는 `src/agents/state.py` 에서 정의
- 4분리 패턴 유지: `InputState`, `InternalState`, `OutputState`, `Context`
- `State = InputState + InternalState + OutputState` (합집합)
- 내부 전용 필드는 `_` 접두사: `_worker_outputs`
- 새 필드 추가 시 어느 State에 속하는지 명확히 구분할 것
- `total=False` 유지 (모든 필드 선택적)

### Preset 규칙

- 모든 preset은 `CompiledStateGraph`를 반환
- 모든 preset은 `messages: list[AnyMessage]` 입출력 인터페이스를 사용
- 주석으로 코드를 on/off 하지 않기

### 네이밍

| 대상 | 규칙 | 예시 |
|------|------|------|
| 파일명 | snake_case | `worker_search_summary.py` |
| 함수 | snake_case | `build_ai_search_summary()` |
| 클래스 | PascalCase | `InputState` |
| 상수 | UPPER_SNAKE + `_` 접두사(모듈 private) | `_DEFAULT_CATEGORY_RANKING` |
| State 내부 필드 | `_` 접두사 | `_worker_outputs` |
| Literal 타입 | PascalCase | `Preset` |

## 로컬 서버 백그라운드 운영 규칙

Claude Code 가 LangServe 서버를 백그라운드로 띄울 때 좀비 프로세스를
남기지 않기 위한 규칙. (실제로 이전에 같은 실수가 반복되어 정착됨.)

1. **백그라운드로 띄울 때는 항상 ``RELOAD=false``**
   uvicorn 의 ``--reload`` 는 부모 + 자식 워커 두 프로세스를 만들기 때문에
   부모만 죽이면 자식이 포트를 잡고 남는다. 검증·디버깅 목적의 단발성
   기동에는 reload 가 불필요하므로 무조건 끈다.
   ```bash
   PORT=8001 RELOAD=false uv run python -m app.run    # 좋음
   ```

2. **종료는 셸 job control(``kill %1``) 대신 PID 기반으로**
   매 Bash 호출이 새 셸이라 ``%1`` 같은 job spec 은 의미가 없다.
   ``netstat -ano | grep ':PORT.*LISTENING'`` 로 PID 를 찾고
   ``Stop-Process -Id <PID> -Force`` (powershell) 또는
   harness 의 ``KillBash`` 도구로 직접 종료한다.

3. **종료 직후에 반드시 검증**
   "명령은 실행했으니 죽었겠지" 로 넘어가지 않는다. 종료 명령 후
   ``netstat`` 으로 포트가 비었는지, ``Get-Process python`` 으로 프로세스가
   사라졌는지 한 번 더 확인한다. 안 죽었으면 다른 방법으로 다시 시도.

4. **포트가 안 비면 우회**
   netstat 에는 LISTENING 으로 보이는데 ``Get-Process`` 에는 해당 PID 가
   없는 경우 — Windows 커널의 TCP 소켓 leak. 이때는 같은 PID 를 죽이려
   하지 말고 다른 포트로 띄운다 (``PORT=8001``).

## Git 규칙

- 브랜치: `main` → `feat/기능명` 분기
- 커밋 메시지: 한국어 본문, conventional commits prefix (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`)
- `.env` 파일은 절대 커밋하지 않기 (`.gitignore`에 포함됨)
- `.idea/`, `__pycache__/`, `.venv/` 커밋하지 않기
