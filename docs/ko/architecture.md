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

---

## 디렉토리 구조

```text
src/
├── graph.py              # 컴파일된 그래프 모듈 (langgraph.json에서 참조)
└── agents/
    ├── graph_builder.py  # build_graph() 통합 진입점
    ├── state.py          # State 정의 (Input/Internal/Output/Context)
    ├── presets/          # 그래프 빌더 (custom, chat, deep_research)
    ├── nodes/            # 노드 함수 (preprocess, worker, postprocessor)
    ├── tools/            # 도구 — OpenSearch 검색, 스킬 조회, 예시(mock)
    ├── backends/         # 백엔드 팩토리 (filesystem, shell, composite, store)
    ├── middlewares/      # 미들웨어 팩토리 12종
    └── skills/           # 스킬 경로 해석 유틸

skills/                   # SKILL.md 파일 (에이전트가 탐색·조회)
app/
├── run.py                # 서버 진입점
└── utils/
    ├── server.py         # LangServe 기반 서빙
    ├── langgraph_loader.py # langgraph.json 파싱 + 그래프 동적 로드
    └── schema.py         # langgraph.json용 dataclass

langgraph.json            # 서비스 설정 (preset, graphs, name, version)
```

---

## 도구 (Tools)

`src/agents/tools/`에 에이전트가 사용하는 도구를 정의합니다.

| 분류 | 도구 | 설명 |
|------|------|------|
| OpenSearch | `search_opensearch` | 의도 기반 파라미터(query, filters, date_range, sort)로 검색 |
| OpenSearch | `describe_opensearch_index` | 인덱스 매핑/필드 조회 |
| 스킬 | `list_skills` | 사용 가능한 스킬 목록 (Progressive disclosure) |
| 스킬 | `read_skill` | 특정 스킬의 SKILL.md 전체 내용 |
| 예시 (mock) | `search_web`, `search_database`, `read_document`, `get_current_time` | 교체 필요한 샘플 구현 |

도구 추가 규칙:
- 특정 worker 전용 → 해당 `worker_*.py` 파일 안에 `@tool` 정의
- 범용 → `src/agents/tools/`에 파일 생성, `__init__.py`에 export

---

## 백엔드 (Backends)

`src/agents/backends/`에 Deep Agents용 백엔드 팩토리를 정의합니다.

| 팩토리 | 적합한 경우 |
|--------|------------|
| `create_filesystem_backend()` | 단순 파일 I/O만 필요할 때 |
| `create_local_shell_backend()` | 셸 명령(git, pip, pytest 등)도 필요할 때 |
| `create_composite_backend()` | 런타임 상태 + 파일 영속성이 모두 필요할 때 |
| `create_store_backend()` | 멀티 세션 간 데이터 공유가 필요할 때 |

---

## 스킬 시스템

`skills/` 디렉토리에 SKILL.md 파일을 두면 에이전트가 자동으로 탐색합니다.

```text
skills/
├── code-review/SKILL.md    # 코드 리뷰 스킬
└── web-research/SKILL.md   # 웹 리서치 스킬
```

에이전트 흐름: `list_skills()` → 필요한 스킬 식별 → `read_skill(name)` → 지침에 따라 실행

---

## 설계 원칙

1. **graph가 개발/실행/배포의 기본 단위**
2. **middleware는 운영 정책** — 요약, tool 호출 제한, fallback, human approval 등
3. **serving은 구현과 분리** — 같은 graph를 LangServe로 서빙
4. **생태계 내장 기능 우선** — 직접 구현보다 LangChain/LangGraph/Deep Agents의 내장 함수 활용
5. **State 분리로 명확한 경계** — 입력/내부/출력/컨텍스트를 분리하여 유지보수성 확보
6. **통합 입출력** — 모든 preset이 messages 기반 동일 인터페이스 사용
