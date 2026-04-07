# langchain-deep-agent-template

LangChain, LangGraph, Deep Agents 생태계를 기반으로 **바로 개발에 사용할 수 있는 에이전트 개발 보일러플레이트 템플릿**입니다.

생태계의 내장 기능(미들웨어, 샌드박스, 서브에이전트 등)을 최대한 활용하고, 이런 기능들을 쉽게 찾아 쓸 수 있도록 하는 것이 핵심 목표입니다.

## 전제 조건

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — 패키지 관리 및 실행 (`pip install uv` 또는 `brew install uv`)
- **OPENAI_API_KEY** — chat, deep_research preset 사용 시 필요

## 빠른 시작

```bash
# 1. 환경 설정
cp .env.example .env
# .env 파일에서 OPENAI_API_KEY 등 설정
# langgraph.json의 "preset" 필드로 에이전트 유형 선택 (custom, chat, deep_research)

# 2. 로컬 실행
./scripts/run-local.sh

# 3. Docker 실행
./scripts/run-docker.sh
```

실행 후 `http://localhost:8000/agent/playground/` 에서 Playground UI를 확인할 수 있습니다.

> **참고**: 기본 preset `custom`은 LLM 없이 동작하는 테스트용 에코 에이전트입니다.
> 실제 LLM 에이전트를 사용하려면 `langgraph.json`에서 preset을 `chat` 또는 `deep_research`로 변경하세요.

### API 호출 예시

```bash
curl -X POST http://localhost:8000/agent/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "messages": [
        {"type": "human", "content": "안녕하세요"}
      ]
    }
  }'
```

## 프로젝트 구조

```text
langchain-deep-agent-template/
├─ src/
│  ├─ graph.py                 # 컴파일된 그래프 모듈 (langgraph.json에서 참조)
│  └─ agents/
│     ├─ graph_builder.py      # build_graph(preset=...) 통합 진입점
│     ├─ state.py              # State 정의 (Input/Internal/Output/Context)
│     ├─ presets/              # 그래프 빌더 함수 (custom, chat, deep_research)
│     ├─ nodes/                # 개별 노드 함수 (preprocess, worker, postprocessor)
│     ├─ tools/                # 도구 (@tool) — OpenSearch 검색, 스킬 조회, 예시 도구
│     ├─ skills/               # 스킬 경로 해석 유틸
│     ├─ backends/             # 백엔드 팩토리 (파일시스템, 셸, 복합, 스토어)
│     └─ middlewares/          # 미들웨어 팩토리 12종
├─ app/                        # 서빙 레이어 (FastAPI + LangServe)
├─ skills/                     # SKILL.md 파일 (에이전트가 탐색·조회)
├─ docs/ko/                    # 한국어 문서
├─ examples/                   # preset별 사용 예시
├─ tests/                      # 단위 테스트
├─ scripts/                    # 실행 스크립트
├─ langgraph.json              # 서비스 설정 (preset, graphs, name, version)
└─ .env.example                # 환경변수 템플릿
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

## 도구 (Tools)

`src/agents/tools/`에 에이전트가 사용하는 도구를 정의합니다.

### OpenSearch 검색

```python
from agents.tools import search_opensearch, describe_opensearch_index
```

| 도구 | 설명 |
|------|------|
| `search_opensearch` | 의도 기반 파라미터(query, filters, date_range, sort)로 검색. 내부에서 DSL 조립 |
| `describe_opensearch_index` | 인덱스 매핑 조회 — text/keyword/date/numeric 필드 분류 |

연결 설정은 환경변수로 관리합니다 (`.env.example` 참조).

### 스킬 도구

```python
from agents.tools import list_skills, read_skill
```

| 도구 | 설명 |
|------|------|
| `list_skills` | 사용 가능한 스킬 목록 조회 (이름, 설명만 — 토큰 절약) |
| `read_skill` | 특정 스킬의 전체 SKILL.md 내용 반환 |

스킬은 `skills/{skill-name}/SKILL.md` 형식으로 정의합니다. 에이전트가 `list_skills` → `read_skill` 순서로 필요한 스킬을 탐색합니다.

### 예시 도구 (mock — 교체 필요)

| 도구 | 설명 | 교체 대상 |
|------|------|-----------|
| `search_web` | 웹 검색 | Tavily, SerpAPI 등 |
| `search_database` | DB 검색 | 실제 DB 연동 |
| `read_document` | 문서 읽기 | S3, 파일시스템 등 |
| `get_current_time` | 현재 시각 | 그대로 사용 가능 |

> `src/agents/tools/examples.py`의 함수 본문을 실제 API 호출로 교체하세요.

## 백엔드 (Backends)

`deep_research` preset에서 사용하는 백엔드입니다. `src/agents/backends/`에 팩토리 함수로 정의됩니다.

```python
from agents.backends import create_filesystem_backend

graph = build_graph("deep_research", backend=create_filesystem_backend())
```

| 팩토리 | 설명 |
|--------|------|
| `create_filesystem_backend()` | 로컬 파일시스템 (가장 단순) |
| `create_local_shell_backend()` | 파일시스템 + 셸 명령 실행 (⚠️ 신뢰 환경에서만) |
| `create_composite_backend()` | StateBackend + FilesystemBackend 조합 |
| `create_store_backend()` | LangGraph BaseStore 기반 크로스스레드 영속 저장 |

## 미들웨어 (Middlewares)

`src/agents/middlewares/`에 12종의 범용 미들웨어 팩토리가 있습니다.

```python
from agents.middlewares import create_summarization_middleware, create_model_fallback_middleware

agent = create_agent(
    middleware=[
        create_summarization_middleware(trigger=("tokens", 4000)),
        create_model_fallback_middleware(models=["openai:gpt-4o", "openai:gpt-4o-mini"]),
    ]
)
```

| 분류 | 미들웨어 | 설명 |
|------|----------|------|
| 컨텍스트 | `create_summarization_middleware` | 토큰 초과 시 대화 요약 |
| 컨텍스트 | `create_context_editing_middleware` | 오래된 도구 출력 정리 |
| 실행 제어 | `create_hitl_middleware` | 도구 실행 전 사람 승인 |
| 실행 제어 | `create_model_call_limit_middleware` | 모델 호출 횟수 제한 |
| 실행 제어 | `create_tool_call_limit_middleware` | 도구 호출 횟수 제한 |
| 안정성 | `create_model_fallback_middleware` | 모델 실패 시 대체 모델 전환 |
| 안정성 | `create_model_retry_middleware` | 모델 API 재시도 |
| 안정성 | `create_tool_retry_middleware` | 도구 호출 재시도 |
| 보안 | `create_pii_detection_middleware` | 개인정보 탐지·마스킹 |
| 능력 | `create_todo_list_middleware` | 작업 계획·추적 |
| 능력 | `create_tool_selector_middleware` | LLM 기반 도구 필터링 |
| 테스트 | `create_tool_emulator_middleware` | LLM으로 도구 응답 에뮬레이션 |

자세한 내용은 [docs/ko/middleware-guide.md](docs/ko/middleware-guide.md)를 참고하세요.

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

## State 분리 패턴

custom preset은 실제 서비스에서 사용하는 State 분리 패턴을 적용합니다:

| State | 역할 | 필드 |
|-------|------|------|
| `InputState` | 외부 입력 | `messages` |
| `InternalState` | 내부 처리 (외부 비노출) | `_worker_outputs` |
| `OutputState` | 최종 출력 | `messages` |
| `State` | Input + Internal + Output 합집합 | 전체 |
| `Context` | 런타임 설정 (state에 포함되지 않음) | `debug` |

## 실서비스 커스터마이징 가이드

이 템플릿을 실제 서비스로 만들려면:

### 1. preset 선택

`langgraph.json`에서 용도에 맞는 preset을 선택합니다:
- 단순 대화형 → `chat`
- 복잡한 조사/분석 → `deep_research`
- 노드 단위 제어 필요 → `custom`

### 2. mock 도구 교체

`src/agents/tools/examples.py`의 mock 도구를 실제 API로 교체합니다:
- `search_web` → Tavily, SerpAPI 등
- `search_database` → 실제 DB 클라이언트
- `read_document` → S3, 로컬 파일시스템 등

### 3. OpenSearch 연결

`.env`에서 `OPENSEARCH_*` 환경변수를 설정하면 `search_opensearch`, `describe_opensearch_index` 도구가 바로 동작합니다.

### 4. 스킬 추가

`skills/{skill-name}/SKILL.md`를 작성하면 에이전트가 자동으로 탐색합니다:

```markdown
---
name: my-skill
description: 이 스킬이 하는 일을 설명합니다.
---

# 스킬 상세 내용

에이전트가 이 스킬을 읽고 따라야 할 지침을 작성합니다.
```

### 5. 미들웨어 적용

운영 환경에 맞는 미들웨어를 조합합니다. 권장 구성:

```python
# 최소 구성
middleware = [create_summarization_middleware()]

# 운영 구성
middleware = [
    create_summarization_middleware(trigger=("tokens", 4000)),
    create_model_fallback_middleware(models=["openai:gpt-4o", "openai:gpt-4o-mini"]),
    create_model_retry_middleware(max_retries=3),
    create_tool_call_limit_middleware(max_calls=30),
]
```

## 서빙

LangServe 기반으로 서빙합니다. `langgraph.json`의 `graphs` 키에서 URI 경로가 결정됩니다.

```json
{
  "graphs": { "agent": "./src/graph.py:graph" },
  "preset": "custom"
}
```

위 설정의 경우 아래 엔드포인트가 생성됩니다:

- `/agent/invoke` — 동기식 실행
- `/agent/stream` — 스트리밍
- `/agent/playground/` — Playground UI
- `/health` — 서비스 상태 확인
- `/presets` — 사용 가능한 preset 목록
- `/docs` — Swagger UI

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| **LLM** | | |
| `OPENAI_API_KEY` | — | chat, deep_research preset에서 필요 |
| **OpenSearch** | | |
| `OPENSEARCH_HOST` | `localhost` | OpenSearch 호스트 |
| `OPENSEARCH_PORT` | `9200` | OpenSearch 포트 |
| `OPENSEARCH_INDEX` | — | 기본 검색 인덱스 |
| `OPENSEARCH_USER` | — | 인증 사용자 (선택) |
| `OPENSEARCH_PASSWORD` | — | 인증 비밀번호 (선택) |
| `OPENSEARCH_USE_SSL` | `false` | TLS 사용 여부 |
| `OPENSEARCH_VERIFY_CERTS` | `true` | 인증서 검증 (사설 CA 시 false) |
| `OPENSEARCH_CA_CERTS` | — | CA 인증서 경로 |
| `OPENSEARCH_SORT_FIELD` | `created_at` | 날짜 정렬 기준 필드 |
| **서버** | | |
| `HOST` | `0.0.0.0` | 서버 바인딩 호스트 |
| `PORT` | `8000` | 서버 포트 |
| **기타** | | |
| `AGENT_OUTPUT_DIR` | `./outputs` | 에이전트 파일 출력 디렉토리 |

## 문서

- [docs/ko/architecture.md](docs/ko/architecture.md) — 레이어 아키텍처
- [docs/ko/deepagents-overview.md](docs/ko/deepagents-overview.md) — Deep Agents 개요
- [docs/ko/middleware-guide.md](docs/ko/middleware-guide.md) — 미들웨어 가이드
