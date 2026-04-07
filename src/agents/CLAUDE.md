# src/agents/ 컨벤션

이 폴더는 에이전트 구현 레이어입니다. 서빙(`app/`)과 관심사가 분리되어 있습니다.

> 프로젝트 전체 코딩 스타일(Python 스타일, import 순서, 네이밍 등)은 [루트 CLAUDE.md](../../CLAUDE.md)를 참고하세요.

## 구조

```
src/agents/
├─ __init__.py        # 공개 API만 export (build_graph, State 등)
├─ graph_builder.py   # build_graph(preset=...) — 유일한 그래프 생성 진입점
├─ state.py           # State 정의 — 이 파일에서만 TypedDict 관리
├─ presets/           # 그래프 빌더 함수
├─ nodes/             # 개별 노드 함수 (async only)
├─ tools/             # 범용 도구 (@tool)
├─ skills/            # Deep Agents 스킬
├─ backends/          # 백엔드 구현 (파일시스템, 스토리지, 메모리)
└─ middlewares/       # 커스텀 미들웨어 (운영 정책)
```

## 추가 절차

### 노드

1. `src/agents/nodes/` 에 파일 생성 (snake_case)
2. `src/agents/nodes/__init__.py` 에 export 추가
3. 필요 시 preset에서 참조

### preset

1. `src/agents/presets/{name}.py` 에 `build_{name}()` 함수 생성
   - 반환 타입은 반드시 `CompiledStateGraph`
   - messages 기반 입출력 인터페이스 유지
2. `src/agents/graph_builder.py` 의 `_BUILDERS` 맵과 `Preset` Literal 에 이름 추가

### worker

1. `src/agents/nodes/worker_{name}.py` 로 생성
2. `src/agents/nodes/__init__.py` 에 export
3. custom preset에서 사용하려면 `custom.py`의 worker import를 교체

### 도구(@tool)

- 특정 worker 전용 → 해당 `worker_*.py` 파일 안에 `@tool` 정의
- 범용 → `src/agents/tools/` 에 파일 생성, `__init__.py`에 export

### 백엔드

`src/agents/backends/`에 자주 쓰는 백엔드 조합을 팩토리 함수로 정의합니다.
함수명은 `create_*_backend` 패턴을 따릅니다.

- `create_filesystem_backend()` — 로컬 파일시스템만 사용 (가장 단순)
- `create_local_shell_backend()` — 파일시스템 + 셸 명령 실행 (코딩 에이전트용)
- `create_composite_backend()` — StateBackend + FilesystemBackend 조합
- `create_store_backend()` — LangGraph BaseStore 기반 크로스스레드 영속 저장

새 백엔드 추가 시:
1. `src/agents/backends/` 에 `{name}.py` 파일 생성
2. `def create_{name}_backend(...)` 팩토리 함수 정의
3. `src/agents/backends/__init__.py`에 export
4. 독스트링에 "적합한 경우" 섹션을 반드시 포함

### 미들웨어

`src/agents/middlewares/`에 에이전트 실행 정책을 팩토리 함수로 정의합니다.
함수명은 `create_*_middleware` 패턴을 따릅니다.

컨텍스트 관리:
- `create_summarization_middleware()` — 대화 요약 (토큰 초과 방지)
- `create_context_editing_middleware()` — 오래된 도구 출력 정리

실행 제어:
- `create_hitl_middleware()` — 도구 실행 전 사람 승인
- `create_model_call_limit_middleware()` — 모델 호출 횟수 제한
- `create_tool_call_limit_middleware()` — 도구 호출 횟수 제한

안정성:
- `create_model_fallback_middleware()` — 모델 실패 시 대체 모델 전환
- `create_model_retry_middleware()` — 모델 API 재시도
- `create_tool_retry_middleware()` — 도구 호출 재시도

보안/정책:
- `create_pii_detection_middleware()` — 개인정보 탐지·마스킹

에이전트 능력:
- `create_todo_list_middleware()` — 작업 계획·추적
- `create_tool_selector_middleware()` — LLM 기반 도구 필터링

테스트:
- `create_tool_emulator_middleware()` — LLM으로 도구 응답 에뮬레이션

새 미들웨어 추가 시:
1. `src/agents/middlewares/` 에 `{name}.py` 파일 생성
2. `def create_{name}_middleware(...)` 팩토리 함수 정의
3. `src/agents/middlewares/__init__.py`에 export
4. 독스트링에 "적합한 경우" 섹션을 반드시 포함

### 스킬

`src/agents/skills/`에 Deep Agents 기반 재사용 가능한 능력 단위를 정의합니다.
스킬은 특정 에이전트의 특화된 능력을 캡슐화하며, 다른 에이전트와 공유할 수 있습니다.

스킬 정의:
- 단일 책임 원칙: 하나의 스킬은 하나의 능력을 담당
- 파일명: snake_case (`research_skill.py`, `code_analysis_skill.py`)
- 클래스명: PascalCase로 끝에 `Skill` 추가 (`ResearchSkill`, `CodeAnalysisSkill`)

스킬 구성 요소:
- `name`: 스킬 고유 이름 (영어, snake_case)
- `description`: 스킬 기능 설명 (한국어)
- `tools`: 스킬에서 사용하는 도구 리스트
- `run()` 또는 `__call__()`: 스킬 실행 메서드

새 스킬 추가 시:
1. `src/agents/skills/` 에 `{name}_skill.py` 파일 생성
2. 스킬 클래스 정의 (예: `class ResearchSkill`)
3. `src/agents/skills/__init__.py`에 export
4. 필요한 preset에서 스킬 인스턴스 생성 및 등록

## State 변경 규칙

- 새 필드 추가 시 `InputState`, `InternalState`, `OutputState`, `Context` 중 하나에 배치
- 외부에 노출할 필드 → `InputState` 또는 `OutputState`
- 내부 전용 필드 → `InternalState`, `_` 접두사 사용
- reducer가 필요하면 `Annotated[타입, reducer_fn]` 사용
- `State`는 직접 수정하지 않음 (자동으로 상위 클래스 합집합)
