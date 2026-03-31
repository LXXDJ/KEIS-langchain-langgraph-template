# 아키텍처 정리

## 한 줄 요약

이 프로젝트는 **LangChain/LangGraph/Deep Agents 생태계의 내장 기능을 최대한 활용**하여 에이전트를 개발하고, 서빙하는 템플릿입니다.

---

## 레이어별 역할

### LangChain: 개발 프레임워크

에이전트 개발에 필요한 추상화를 제공합니다.

- 모델 연결, 툴 연결, 메시지 구조화
- 미들웨어 적용, 에이전트 루프 구성
- `create_agent()` — 대화형 에이전트의 표준 팩토리

### LangGraph: 실행 런타임

에이전트를 상태 기반으로 실행하는 런타임입니다.

- state 기반 orchestration
- durable execution, checkpoint / persistence
- streaming, human-in-the-loop

### Deep Agents: batteries-included harness

LangGraph 위에 built-in 기능을 얹은 상위 레이어입니다.

- planning (todo 기반), virtual filesystem
- subagent delegation, summarization
- memory / skills / human-in-the-loop 확장
- `create_deep_agent()` — 리서치 에이전트의 표준 팩토리

### 서빙: LangServe

에이전트를 HTTP API로 노출하는 계층입니다.

- `add_routes()`로 자동 엔드포인트 + Playground UI 구성
- `langgraph.json`의 `graphs` 설정으로 URI 경로 결정

---

## Preset 시스템

`build_graph(preset=...)`가 통합 진입점이며, 모든 preset은 `CompiledStateGraph`를 반환합니다.
모든 preset은 동일한 messages 기반 입출력을 사용합니다.

```text
build_graph("chat")           → create_agent()         → CompiledStateGraph
build_graph("deep_research")  → create_deep_agent()    → CompiledStateGraph
build_graph("custom")         → 수동 StateGraph 조합    → CompiledStateGraph
```

### custom preset의 핵심 패턴

실제 서비스에서 검증된 구조:

```text
START → preprocess → worker → postprocessor → END
         (전처리)    (서브에이전트)   (후처리)
```

- **State 분리**: `InputState` / `InternalState` / `OutputState` / `Context`
- **노드 안에서 create_agent()**: worker 노드에서 LLM 에이전트를 서브에이전트로 호출
- **스트리밍**: LangServe의 내장 스트리밍으로 중간 과정 전달

---

## State 분리 패턴

```python
class InputState(TypedDict):    # 외부 입력 (messages)
class InternalState(TypedDict): # 내부 처리 (_worker_outputs, 외부 비노출)
class OutputState(TypedDict):   # 최종 출력 (messages)
class State(InputState, InternalState, OutputState): # 전체 합집합
class Context(TypedDict):       # 런타임 설정 (state에 포함 안 됨)
```

StateGraph 생성 시:

```python
StateGraph(
    state_schema=State,
    input_schema=InputState,
    output_schema=OutputState,
    context_schema=Context,
)
```

API 문서화용 Pydantic 스키마(`InputStateSchema`, `OutputStateSchema`)도 `agents/state.py`에 함께 정의합니다.

---

## 디렉토리 구조

```text
agents/
├── graph_builder.py      # build_graph() 통합 진입점
├── state.py              # State 정의 + Pydantic 스키마
├── registry.py           # preset 메타 정보
├── presets/
│   ├── chat.py           # create_agent() 래퍼
│   ├── deep_research.py  # create_deep_agent() 래퍼
│   └── custom.py         # 수동 StateGraph + State 분리
└── nodes/
    ├── preprocess.py     # 입력 전처리
    ├── worker.py         # 서브 에이전트 패턴 (create_agent)
    └── postprocessor.py  # 후처리

app/
├── run.py                # 서버 진입점
└── utils/
    ├── server.py         # LangServe 기반 서빙
    ├── langgraph_loader.py # langgraph.json 파싱
    └── schema.py         # langgraph.json용 dataclass

langgraph.json            # 서비스 설정 (name, version, graphs 등)
```

---

## 설계 원칙

1. **graph가 개발/실행/배포의 기본 단위**
2. **middleware는 운영 정책** — 요약, tool 호출 제한, fallback, human approval 등
3. **serving은 구현과 분리** — 같은 graph를 LangServe로 서빙
4. **생태계 내장 기능 우선** — 직접 구현보다 LangChain/LangGraph/Deep Agents의 내장 함수 활용
5. **State 분리로 명확한 경계** — 입력/내부/출력/컨텍스트를 분리하여 유지보수성 확보
6. **통합 입출력** — 모든 preset이 messages 기반 동일 인터페이스 사용
