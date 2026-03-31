# agents/ 컨벤션

이 폴더는 에이전트 구현 레이어입니다. 서빙(`app/`)과 관심사가 분리되어 있습니다.

## 구조

```
agents/
├─ __init__.py        # 공개 API만 export (build_graph, list_presets, State 등)
├─ graph_builder.py   # build_graph(preset=...) — 유일한 그래프 생성 진입점
├─ state.py           # State 정의 — 이 파일에서만 TypedDict 관리
├─ registry.py        # preset 메타 정보 (PresetInfo)
├─ presets/           # 그래프 빌더 함수
└─ nodes/             # 개별 노드 함수
```

## 노드 추가 절차

1. `agents/nodes/` 에 파일 생성 (snake_case)
2. async 함수로 작성:
   ```python
   async def my_node(state: State, **kwargs: Any) -> Dict[str, Any]:
   ```
3. `agents/nodes/__init__.py` 에 export 추가
4. 필요 시 preset에서 참조

## preset 추가 절차

1. `agents/presets/` 에 `build_{name}()` 함수 생성
2. 반환 타입은 반드시 `CompiledStateGraph`
3. messages 기반 입출력 인터페이스 유지
4. `agents/presets/__init__.py` 에 export 추가
5. `agents/registry.py` 에 `PresetInfo` 등록
6. `agents/graph_builder.py` 의 `Preset` Literal과 `_BUILDERS` 맵에 추가

## State 변경 규칙

- 새 필드 추가 시 `InputState`, `InternalState`, `OutputState`, `Context` 중 하나에 배치
- 외부에 노출할 필드 → `InputState` 또는 `OutputState`
- 내부 전용 필드 → `InternalState`, `_` 접두사 사용
- reducer가 필요하면 `Annotated[타입, reducer_fn]` 사용
- `State`는 직접 수정하지 않음 (자동으로 상위 클래스 합집합)

## worker 추가 규칙

1. `agents/nodes/worker_{name}.py` 로 생성
2. `agents/nodes/__init__.py` 에 export
3. `agents/presets/custom.py` 의 `_WORKER_MAP`에 등록
4. `WorkerType` Literal에 키 추가
