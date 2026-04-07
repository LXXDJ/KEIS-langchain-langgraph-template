# src/agents/ 컨벤션

이 폴더는 에이전트 구현 레이어입니다. 서빙(`app/`)과 관심사가 분리되어 있습니다.

이 레포는 SVC-3 (고용24 검색 결과 요약) 전용으로 정리되어 있어 유일한 preset은
`ai_search_summary` 입니다.

> 프로젝트 전체 코딩 스타일(Python 스타일, import 순서, 네이밍 등)은 [루트 CLAUDE.md](../../CLAUDE.md)를 참고하세요.

## 구조

```
src/agents/
├─ __init__.py        # 공개 API만 export (build_graph, list_presets, State 등)
├─ graph_builder.py   # build_graph(preset=...) — 유일한 그래프 생성 진입점
├─ state.py           # State 정의 — 이 파일에서만 TypedDict 관리
├─ registry.py        # preset 메타 정보 (PresetInfo)
├─ _utils.py          # find_project_root 등 패키지 내부 공통 유틸
├─ presets/
│  └─ ai_search_summary.py
└─ nodes/
   ├─ preprocess.py
   ├─ worker_search_summary.py   # SVC-3 핵심 worker
   └─ postprocessor.py
```

## 추가 절차

### 노드

1. `src/agents/nodes/` 에 파일 생성 (snake_case)
2. `src/agents/nodes/__init__.py` 에 export 추가
3. 필요 시 preset에서 참조

### preset

1. `src/agents/presets/` 에 `build_{name}()` 함수 생성
2. 반환 타입은 반드시 `CompiledStateGraph`
3. messages 기반 입출력 인터페이스 유지
4. `src/agents/presets/__init__.py` 에 export 추가
5. `src/agents/registry.py` 에 `PresetInfo` 등록
6. `src/agents/graph_builder.py` 의 `Preset` Literal과 `_BUILDERS` 맵에 추가

### worker

1. `src/agents/nodes/worker_{name}.py` 로 생성
2. `src/agents/nodes/__init__.py` 에 export
3. 새 preset 빌더에서 import 하여 사용

### worker 전용 도구

`@tool` 데코레이터를 쓰는 도구든, fetcher/parser 같은 헬퍼 함수든
**해당 worker 파일 안에 모듈 레벨 함수로 정의**합니다. 별도의 `tools/` 패키지를
다시 만들지 마세요. 여러 worker가 공유할 정도로 일반화될 때 별도 모듈 분리.

## State 변경 규칙

- 새 필드 추가 시 `InputState`, `InternalState`, `OutputState`, `Context` 중 하나에 배치
- 외부에 노출할 필드 → `InputState` 또는 `OutputState`
- 내부 전용 필드 → `InternalState`, `_` 접두사 사용 (예: `_worker_outputs`)
- reducer가 필요하면 `Annotated[타입, reducer_fn]` 사용
- `State`는 직접 수정하지 않음 (자동으로 상위 클래스 합집합)
- 가능하면 새 필드를 추가하기보다 기존 `_worker_outputs` dict 안에 데이터를 담아
  state.py를 건드리지 않는 쪽을 우선 검토하세요.
