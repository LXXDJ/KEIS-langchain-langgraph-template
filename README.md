# AI 검색 결과 요약 (SVC-3) — `ai_search_summary` preset

고용24(work24.go.kr) 통합검색 결과를 한국어 2~3줄로 요약하는 에이전트 preset.
이 문서는 `feat/ai-search-summary` 브랜치에서 진행 중인 작업의 설계와 현재 진행 상황을 기록한다.

---

## 목표

고용24 검색 결과 페이지 상단에 2~3줄 AI 요약 카드를 표시한다. 사용자가 검색어를 입력하면:

1. 의도에 맞는 카테고리 우선순위를 산출
2. work24 통합검색을 호출해 결과 수집
3. 핵심 결과를 선별하여 한국어 요약 생성
4. 원문 이동 URL + 추가 탐색 경로(2·3순위 카테고리 대표 결과 + 연관검색어) 제공

요약 대상은 **공개 검색 결과만**(개인정보 미포함)이므로 외부 LLM(GPT-4o mini) 사용이 허용된다.
SVC-1(일자리검색, 개인정보 포함)은 별도 에이전트로 분리되며, 본 작업은 SVC-3(요약)만 다룬다.
SVC-1과의 멀티에이전트 합성을 위해 본 preset은 그 자체로 임베드 가능한 서브그래프로 설계되었다.

---

## 아키텍처

### 파이프라인

```
START → preprocess → worker_search_summary → postprocessor → END
```

기존 템플릿의 `custom` preset과 동일한 3단 구조를 따른다. `preprocess`와 `postprocessor`는
기존 노드를 그대로 재사용하고, 핵심 로직은 신규 worker 노드 한 곳에 모았다.

### `worker_search_summary` 내부 흐름

단일 노드 안에서 결정론적으로 순차 실행:

1. `messages`의 마지막 `HumanMessage`에서 query 추출
2. `_classify_intent(query)` — LLM(gpt-4o-mini, structured output)로 카테고리 우선순위 산출
3. `fetch_work24_search(query)` — work24 통합검색 호출, 정규화된 결과 + 연관검색어 반환
4. `_select_top_k_by_category(results, ranking, k=5)` — 결정론적 top-k 선별 (LLM 미사용)
5. `_summarize(query, selected)` — LLM(gpt-4o-mini)로 한국어 2~3줄 요약 생성
6. `_build_navigation(results, ranking, related_queries)` — primary_url, related_categories, related_queries 구성
7. 최종 payload를 JSON 직렬화하여 `_worker_outputs[0]["data"]["response"]`에 push

기존 `postprocessor`가 `_worker_outputs[0]["data"]["response"]`를 그대로 `AIMessage.content`에
넣기 때문에, worker가 그 자리에 JSON 문자열을 넣어주면 별도 postprocessor 없이도 동작한다.

### 출력 JSON 구조

```json
{
  "summary": "한국어 2~3줄 요약 텍스트",
  "primary_url": "1순위 카테고리의 top1 결과 URL",
  "related_categories": [
    {"category": "정책", "url": "...", "title": "..."},
    {"category": "훈련", "url": "...", "title": "..."}
  ],
  "related_queries": ["연관검색어1", "연관검색어2", "..."]
}
```

`AIMessage.content`에 위 JSON 문자열이 그대로 담긴다.

---

## 핵심 설계 원칙

1. **선형 결정론 파이프라인 + 두 번의 LLM 호출.** 멀티에이전트 워크플로가 아니므로
   `worker_chat.py`처럼 단일 노드에 전부 담는다. 각 단계를 별도 노드로 쪼개지 않는다.
2. **`state.py`를 건드리지 않는다.** 모든 중간 결과는 기존 `_worker_outputs` 필드에 dict로 담는다.
3. **검색 fetcher는 plain async 함수.** worker 파일 안에 모듈 레벨 헬퍼로 둔다
   (CLAUDE.md의 "worker 전용 도구는 worker 파일 안에" 규칙). `@tool` 래핑은 멀티에이전트
   합성이 필요해질 때 추가.
4. **단계별 구현(stub → parser → HTTP).** HTML 셀렉터를 모르는 상태에서 전체가 막히지 않도록
   1단계는 stub fetcher로 파이프라인 전체를 끝내고 머지 가능 상태로 만든다.
5. **graceful degradation.** LLM 호출과 HTTP 호출 모두 실패 시 fallback을 제공해
   사용자에게 항상 응답을 반환한다.

### Fallback 전략

| 실패 지점 | 동작 |
|---|---|
| 의도 분류 LLM 실패 | 중립 기본 ranking (`["전체", "신고·신청", "정책", ...]`) 사용 |
| 요약 LLM 실패 | top-1 결과의 title을 echo |
| work24 fetch 실패 | 빈 결과 + 경고 로그, 파이프라인 계속 진행 |
| HTML 파싱 실패 | 동일 (빈 결과 + 경고 로그) |
| 빈 query | LLM/fetch 호출 생략, 빈 payload 즉시 반환 |

---

## 단계별 구현 로드맵

| Phase | 내용 | 상태 |
|---|---|---|
| **Phase 1** | 스켈레톤 + stub fetcher (하드코딩 fake 결과). 모든 노드/preset/등록/테스트 완성. 머지 가능 상태. | ✅ 완료 |
| **Phase 2** | 실제 work24 페이지 HTML을 fixture로 캡처(`tests/fixtures/work24_sample.html`)하고 BeautifulSoup 파서(`_parse_work24_html`) 구현. 카테고리별 셀렉터 + 연관검색어 추출 + URL 절대화. 파서 단위 테스트 7건 추가. | ✅ 완료 |
| **Phase 3** | `httpx.AsyncClient`로 실제 HTTP 호출 결선. 명시 User-Agent, `timeout=5.0`, `follow_redirects=True`, 모든 예외 catch → 빈 결과 + 경고 로그. | ✅ 완료 |

### 완료된 작업 (Phase 1 + 2 + 3)

**신규 파일 (4):**
- `src/agents/nodes/worker_search_summary.py` — worker 노드 + 모든 private 헬퍼
  - `_classify_intent`, `_summarize` (LLM 호출, 테스트에서 monkeypatch)
  - `_select_top_k_by_category`, `_build_navigation` (결정론, 순수 함수)
  - `_parse_work24_html` (BeautifulSoup으로 카테고리/제목/URL/snippet/연관검색어 추출)
  - `fetch_work24_search` (httpx.AsyncClient로 work24 통합검색 호출)
  - `_IntentResult` Pydantic 모델, `_INTENT_SYSTEM_PROMPT` / `_SUMMARY_SYSTEM_PROMPT` 상수
  - `_DEFAULT_CATEGORY_RANKING` (LLM 실패 시 fallback)
- `src/agents/presets/ai_search_summary.py` — `build_ai_search_summary()` 빌더 (custom.py 구조 그대로)
- `tests/test_ai_search_summary.py` — 단위/통합 테스트 18건
- `tests/fixtures/work24_sample.html` — 실제 work24 응답 캡처 (파서 회귀 방지)

**수정 파일 (6):**
- `pyproject.toml` — `beautifulsoup4>=4.12`, `httpx>=0.28` 추가
- `src/agents/nodes/__init__.py` — `worker_search_summary` export
- `src/agents/presets/__init__.py` — `build_ai_search_summary` export
- `src/agents/registry.py` — `PresetInfo` 등록
- `src/agents/graph_builder.py` — `Preset` Literal과 `_BUILDERS`에 추가
- `src/graph.py` — `langgraph.json` 읽을 때 `encoding="utf-8"` 명시 (Windows cp949 회귀 수정)

**의도적으로 건드리지 않은 파일:**
- `src/agents/state.py` — 새 필드 추가 없음 (`_worker_outputs` 재사용)
- `langgraph.json` — default preset 변경하지 않음 (사용자가 필요시 수동으로)

---

## 사용 방법

### Python에서 직접 사용

```python
import asyncio, json
from langchain_core.messages import HumanMessage
from agents import build_graph

graph = build_graph("ai_search_summary")
result = asyncio.run(
    graph.ainvoke({"messages": [HumanMessage("서울 카페 아르바이트")]})
)
payload = json.loads(result["messages"][-1].content)
print(payload["summary"])
print(payload["primary_url"])
print(payload["related_categories"])
print(payload["related_queries"])
```

### LangServe로 서빙

`langgraph.json`의 `preset` 필드를 변경:

```json
{
  "preset": "ai_search_summary",
  ...
}
```

이후 `./scripts/run-local.sh`로 띄우면 LangServe가 새 preset의 그래프를 expose한다.

> Phase 3까지 완료되어 실제 work24 통합검색을 호출한다. `OPENAI_API_KEY`가
> 설정돼 있으면 의도 분류 + 한국어 2~3줄 요약까지 정상 동작.

---

## 테스트 전략

I/O 경계에서만 mock하고 순수 함수는 직접 단위 테스트.

### 테스트 목록 (`tests/test_ai_search_summary.py`)

총 18건. 실제 LLM/HTTP 호출 없이 모두 통과한다.

| 테스트 | 대상 | 방식 |
|---|---|---|
| `test_parse_work24_html_returns_results_and_related` | `_parse_work24_html` | fixture HTML |
| `test_parse_work24_html_results_have_required_fields` | 동일 | 필수 필드 검증 |
| `test_parse_work24_html_covers_multiple_categories` | 동일 | 채용/훈련/뉴스·자료 포함 |
| `test_parse_work24_html_absolutizes_relative_urls` | 동일 | URL 절대화 |
| `test_parse_work24_html_empty_input_returns_empty` | 동일 | 빈 입력 처리 |
| `test_parse_work24_html_garbage_input_returns_empty` | 동일 | work24 구조 아닌 HTML |
| `test_parse_work24_html_truncated_input_does_not_raise` | 동일 | 잘린 HTML 예외 안 던짐 |
| `test_select_top_k_orders_by_ranking` | `_select_top_k_by_category` | 순수 함수 단위 |
| `test_select_top_k_truncates_to_k` | 동일 | 순수 함수 단위 |
| `test_select_top_k_unknown_category_goes_last` | 동일 | 순수 함수 단위 |
| `test_build_navigation_picks_primary_and_related` | `_build_navigation` | 순수 함수 단위 |
| `test_build_navigation_handles_missing_categories` | 동일 | 순수 함수 단위 |
| `test_build_navigation_caps_related_queries_at_5` | 동일 | 순수 함수 단위 |
| `test_classify_intent_fallback_on_failure` | `_classify_intent` | LLM monkeypatch → 예외 → fallback 검증 |
| `test_summarize_fallback_on_failure` | `_summarize` | LLM monkeypatch → 예외 → top1 title echo |
| `test_summarize_fallback_on_empty_selection` | 동일 | 빈 selection 시 빈 문자열 |
| `test_preset_e2e_returns_json_ai_message` | preset 전체 | fetch/classify/summarize 모두 monkeypatch, AIMessage 검증 |
| `test_preset_e2e_handles_empty_query` | preset 전체 | 빈 query 시 빈 payload 즉시 반환 |

### 실행

```bash
uv run pytest tests/test_ai_search_summary.py -v
```

### 주의: 모듈 재노출 vs monkeypatch

`agents.nodes.__init__.py`가 `worker_search_summary`라는 이름으로 함수를 재노출하기
때문에, `from agents.nodes import worker_search_summary as wss`나
`import agents.nodes.worker_search_summary as wss`는 모두 **모듈이 아닌 함수**에 바인딩된다.
모듈 객체에 monkeypatch하려면 `importlib.import_module(...)`로 우회해야 한다:

```python
import importlib
wss = importlib.import_module("agents.nodes.worker_search_summary")
```

---

## 의도적으로 하지 않은 것 (이번 범위 밖)

- `state.py` 수정 — 오버엔지니어링 회피
- 전용 postprocessor 추가 — 기존 것 재사용 가능
- `prompts/` 패키지 신설 — 상수 두 개를 위해 폴더 생성하지 않음
- 새 미들웨어/백엔드
- `langgraph.json`의 default preset 변경 — 사용자 선택 영역
- SVC-1(일자리검색) 통합 — subgraph 합성 가능하도록 설계만 유지
- 키워드 검색 → 하이브리드 검색 전환 — 검색 인프라 단의 별개 작업
- HITL, 재시도 미들웨어 등 운영 정책 — MVP 이후

---

## 참고 파일

- 루트 컨벤션: [CLAUDE.md](CLAUDE.md)
- 에이전트 컨벤션: [src/agents/CLAUDE.md](src/agents/CLAUDE.md)
- 참고 preset: [src/agents/presets/custom.py](src/agents/presets/custom.py)
- 참고 worker: [src/agents/nodes/worker_chat.py](src/agents/nodes/worker_chat.py)
