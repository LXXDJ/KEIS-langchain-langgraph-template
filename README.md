# langchain-deep-agent-template

LangChain, LangGraph, Deep Agents 생태계를 기반으로 **바로 개발에 사용할 수 있는 에이전트 개발 보일러플레이트 템플릿**입니다.

생태계의 내장 기능(미들웨어, 샌드박스, 서브에이전트 등)을 최대한 활용하고, 이런 기능들을 쉽게 찾아 쓸 수 있도록 하는 것이 핵심 목표입니다.

## 프로젝트 구조

```text
langchain-deep-agent-template/
├─ agents/
│  ├─ __init__.py           # 공개 API
│  ├─ graph_builder.py      # build_graph(preset=...) 통합 진입점
│  ├─ state.py              # State 정의 (messages 기반 Input/Internal/Output/Context)
│  ├─ registry.py           # preset 메타 정보
│  ├─ presets/
│  │  ├─ chat.py            # create_agent() 기반
│  │  ├─ deep_research.py   # create_deep_agent() 기반
│  │  └─ custom.py          # 수동 StateGraph 노드 조합
│  └─ nodes/
│     ├─ preprocess.py      # 입력 전처리
│     ├─ worker.py          # 서브 에이전트 (create_agent) 패턴
│     └─ postprocessor.py   # 후처리
├─ app/
│  ├─ run.py                # 서버 진입점
│  └─ utils/
│     ├─ server.py          # LangServe 기반 서빙
│     ├─ langgraph_loader.py # langgraph.json 파싱
│     └─ schema.py          # langgraph.json용 dataclass
├─ examples/
├─ docs/ko/
├─ scripts/
│  ├─ run-local.sh
│  └─ run-docker.sh
├─ langgraph.json           # 서비스 설정 (name, version, graphs 등)
├─ pyproject.toml
├─ Dockerfile
└─ .env.example
```

## 빠른 시작

```bash
# 1. 환경 설정
cp .env.example .env
# .env 파일에서 AGENT_PRESET, OPENAI_API_KEY 등 설정

# 2. 로컬 실행 (uv 필요)
./scripts/run-local.sh

# 3. Docker 실행
./scripts/run-docker.sh
```

## Preset

`build_graph(preset=...)`로 에이전트 유형을 선택합니다. 모든 preset은 `CompiledStateGraph`를 반환하며, 동일한 messages 기반 입출력을 사용합니다.

| preset | 팩토리 | 설명 |
|--------|--------|------|
| `custom` (기본) | 수동 StateGraph | LLM 없이 테스트/프로토타이핑. 노드 안에서 `create_agent()`를 서브에이전트로 사용 가능 |
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

## State 분리 패턴

custom preset은 실제 서비스에서 사용하는 State 분리 패턴을 적용합니다:

```python
from agents.state import State, InputState, OutputState, Context

# InputState  : 외부 입력 (messages)
# InternalState: 내부 처리 (_worker_outputs 등, 외부 비노출)
# OutputState : 최종 출력 (messages)
# Context     : 런타임 설정 (state에 포함되지 않음)
# State       : Input + Internal + Output 합집합
```

## 서빙

LangServe 기반으로 서빙합니다. `langgraph.json`의 `graphs` 설정에 따라 URI 경로가 결정됩니다.

- `/{graph_name}/invoke` — 동기식 실행
- `/{graph_name}/stream` — 스트리밍
- `/{graph_name}/playground/` — Playground UI

```json
// langgraph.json 예시
{
  "graphs": { "agent": "./src/graph.py:graph" }
}
// → /agent/invoke, /agent/playground/ 등
```

## 노드 안에서 create_agent() 사용

`agents/nodes/worker.py`에 구현된 핵심 패턴입니다:

```python
from langchain.agents import create_agent

async def worker(state, **kwargs):
    agent = create_agent(
        model="openai:gpt-4o-mini",
        tools=[my_tool],
        system_prompt="...",
    )
    result = await agent.ainvoke({"messages": state["messages"]})
    return {"_worker_outputs": [{"status": "success", "data": {...}}]}
```

수동 StateGraph의 노드 안에서 `create_agent()`를 서브 에이전트로 호출하여, 파이프라인의 유연성과 LLM 에이전트의 기능을 동시에 활용합니다.

## 문서

- [docs/ko/architecture.md](docs/ko/architecture.md) — 레이어 아키텍처
- [docs/ko/deepagents-overview.md](docs/ko/deepagents-overview.md) — Deep Agents 개요
- [docs/ko/middleware-guide.md](docs/ko/middleware-guide.md) — 미들웨어 가이드
