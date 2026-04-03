# langchain-deep-agent-template

LangChain, LangGraph, Deep Agents 생태계를 기반으로 **바로 개발에 사용할 수 있는 에이전트 개발 보일러플레이트 템플릿**입니다.

생태계의 내장 기능(미들웨어, 샌드박스, 서브에이전트 등)을 최대한 활용하고, 이런 기능들을 쉽게 찾아 쓸 수 있도록 하는 것이 핵심 목표입니다.

## 프로젝트 구조

```text
langchain-deep-agent-template/
├─ src/
│  ├─ graph.py                 # 컴파일된 그래프 모듈 (langgraph.json에서 참조)
│  └─ agents/
│     ├─ __init__.py           # 공개 API (build_graph, list_presets)
│     ├─ graph_builder.py      # build_graph(preset=...) 통합 진입점
│     ├─ state.py              # State 정의 (messages 기반 Input/Internal/Output/Context)
│     ├─ registry.py           # preset 메타 정보
│     ├─ presets/
│     │  ├─ custom.py          # 수동 StateGraph 노드 조합
│     │  ├─ chat.py            # create_agent() 기반
│     │  └─ deep_research.py   # create_deep_agent() 기반
│     └─ nodes/
│        ├─ preprocess.py      # 입력 전처리 (async)
│        ├─ postprocessor.py   # 후처리 (async)
│        ├─ worker.py          # 기본 worker — LLM 없이 테스트용 (async)
│        ├─ worker_chat.py     # create_agent() 활용 worker 예시 (async)
│        └─ worker_deep.py     # create_deep_agent() 활용 worker 예시 (async)
├─ app/
│  ├─ run.py                   # 서버 진입점
│  └─ utils/
│     ├─ server.py             # LangServe 기반 서빙
│     ├─ langgraph_loader.py   # langgraph.json 파싱
│     └─ schema.py             # langgraph.json용 dataclass
├─ docs/ko/
│  ├─ architecture.md          # 레이어 아키텍처
│  ├─ deepagents-overview.md   # Deep Agents 개요
│  └─ middleware-guide.md      # 미들웨어 가이드
├─ examples/
│  ├─ chat/                    # chat preset 사용 예시
│  └─ deep_research/           # deep_research preset 사용 예시
├─ scripts/
│  ├─ run-local.sh             # uv 기반 로컬 실행
│  └─ run-docker.sh            # Docker 빌드 & 실행
├─ langgraph.json              # 서비스 설정 (name, version, graphs 등)
├─ pyproject.toml
├─ Dockerfile
└─ .env.example
```

## 빠른 시작

```bash
# 1. 환경 설정
cp .env.example .env
# .env 파일에서 OPENAI_API_KEY 등 설정
# langgraph.json의 "preset" 필드로 에이전트 유형 선택

# 2. 로컬 실행 (uv 필요)
./scripts/run-local.sh

# 3. Docker 실행
./scripts/run-docker.sh
```

실행 후 `http://localhost:8000/agent/playground/` 에서 Playground UI를 확인할 수 있습니다.

### API 호출 예시

```bash
curl -X POST http://localhost:8000/agent/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "messages": [
        {"type": "human", "content": "최근 매출 데이터를 알려주세요."}
      ]
    }
  }'
```

## Preset

`build_graph(preset=...)`로 에이전트 유형을 선택합니다. 모든 preset은 `CompiledStateGraph`를 반환하며, 동일한 messages 기반 입출력을 사용합니다.

| preset | 팩토리 | 설명 |
|--------|--------|------|
| `custom` (기본) | 수동 StateGraph | preprocess → worker → postprocessor 파이프라인. 노드를 직접 조합 |
| `chat` | `langchain.agents.create_agent()` | 대화형 에이전트. 미들웨어, response_format 등 내장 기능 활용 |
| `deep_research` | `deepagents.create_deep_agent()` | planning, filesystem, subagent, summarization 미들웨어 자동 구성 |

```python
from agents import build_graph
from langchain_core.messages import HumanMessage

# LLM 없이 테스트
graph = build_graph()
result = graph.invoke({"messages": [HumanMessage(content="hello")]})

# LangChain 대화형 에이전트
graph = build_graph("chat", model="openai:gpt-4o")

# DeepAgents 리서치 에이전트
graph = build_graph("deep_research", model="openai:gpt-4o")
```

## Custom Preset — Worker 교체

custom preset은 기본적으로 LLM 없이 테스트용 worker를 사용합니다.
다른 worker를 사용하려면 `src/agents/presets/custom.py`의 import를 교체하세요:

| worker 모듈 | 파일 | 설명 |
|-------------|------|------|
| `worker` (기본) | `worker.py` | LLM 없이 테스트용. 입력을 그대로 반환 |
| `worker_chat` | `worker_chat.py` | `create_agent()` + `@tool`로 대화형 서브에이전트 |
| `worker_deep` | `worker_deep.py` | `create_deep_agent()` + `@tool`로 리서치 서브에이전트 |

```python
# src/agents/presets/custom.py에서 import 교체
from agents.nodes import worker_chat as worker  # create_agent() 기반
# 또는
from agents.nodes import worker_deep as worker  # create_deep_agent() 기반
```

### 노드 안에서 create_agent() 사용

`src/agents/nodes/worker_chat.py`에 구현된 핵심 패턴입니다. 수동 StateGraph의 노드 안에서 `create_agent()`를 서브에이전트로 호출하여, 파이프라인의 유연성과 LLM 에이전트의 기능을 동시에 활용합니다.

```python
from langchain.agents import create_agent
from langchain.tools import tool

@tool
def search_database(query: str) -> str:
    """데이터베이스에서 정보를 검색합니다."""
    return f"검색 결과: {query}"

async def worker_chat(state, **kwargs):
    agent = create_agent(
        model="openai:gpt-4o-mini",
        tools=[search_database],
        system_prompt="당신은 데이터 분석 어시스턴트입니다.",
    )
    result = await agent.ainvoke({"messages": state["messages"]})
    return {"_worker_outputs": [{"status": "success", "data": {...}}]}
```

## State 분리 패턴

custom preset은 실제 서비스에서 사용하는 State 분리 패턴을 적용합니다:

```python
from agents.state import State, InputState, InternalState, OutputState, Context
```

| State | 역할 | 필드 |
|-------|------|------|
| `InputState` | 외부 입력 | `messages` |
| `InternalState` | 내부 처리 (외부 비노출) | `_worker_outputs` |
| `OutputState` | 최종 출력 | `messages` |
| `State` | Input + Internal + Output 합집합 | 전체 |
| `Context` | 런타임 설정 (state에 포함되지 않음) | `debug` |

## 서빙

LangServe 기반으로 서빙합니다. `langgraph.json`의 `graphs` 키에서 URI 경로가 결정됩니다.

```json
{
  "graphs": { "agent": "./src/graph.py:graph" }
}
```

위 설정의 경우 아래 엔드포인트가 생성됩니다:

- `/agent/invoke` — 동기식 실행
- `/agent/stream` — 스트리밍
- `/agent/playground/` — Playground UI
- `/health` — 서비스 상태 확인
- `/presets` — 사용 가능한 preset 목록
- `/docs` — Swagger UI

### 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `OPENAI_API_KEY` | — | chat, deep_research preset에서 필요 |
| `HOST` | `0.0.0.0` | 서버 바인딩 호스트 |
| `PORT` | `8000` | 서버 포트 |

## 문서

- [docs/ko/architecture.md](docs/ko/architecture.md) — 레이어 아키텍처
- [docs/ko/deepagents-overview.md](docs/ko/deepagents-overview.md) — Deep Agents 개요
- [docs/ko/middleware-guide.md](docs/ko/middleware-guide.md) — 미들웨어 가이드
