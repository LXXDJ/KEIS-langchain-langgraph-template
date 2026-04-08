# 고용24 AI 검색 결과 요약 (SVC-3)

고용24(work24.go.kr) 통합검색 결과를 GPT-4o mini로 한국어 2~3줄 요약해 사용자에게
돌려주는 단일 에이전트 서비스. LangChain / LangGraph / LangServe 기반.

이 레포는 SVC-3 전용으로 정리되어 있어, 사용 가능한 에이전트(preset)는
[`ai_search_summary`](src/agents/presets/ai_search_summary.py) 하나입니다.

---

# Part 1 — 기획

## 배경과 목표

고용24 통합검색은 9개 카테고리(신고·신청 / 정책 / 채용 / 기업 / 훈련 / 뉴스·자료 /
직업·진로 / 자격 / 기타)에 결과가 흩어져 있어, 사용자가 검색어를 입력해도 어떤
카테고리부터 봐야 의도에 맞는 정보가 있는지 한눈에 파악하기 어렵습니다.

본 서비스는 검색 결과 페이지 상단에 **2~3줄 AI 요약 카드**를 띄워, 사용자가:

- 핵심 정보를 즉시 확인하고
- 의도에 맞는 1순위 결과로 바로 이동하며
- 자연스럽게 다음 탐색 경로를 따라갈 수 있도록 합니다.

## 서비스가 하는 일

사용자가 검색어를 입력하면:

1. 검색어 의도에 맞는 **카테고리 우선순위**를 산출
2. work24 통합검색을 호출해 결과 수집
3. 1순위 카테고리의 핵심 결과를 선별하여 **한국어 2~3줄 요약** 생성
4. 다음 정보를 한 번에 묶어서 반환:
   - 1순위 결과의 **원문 이동 URL**
   - 2·3순위 카테고리의 **추가 탐색 경로**
   - work24가 제공하는 **연관검색어**·**연관직종**

## 모델 정책 — 왜 외부 LLM(GPT-4o mini)을 써도 되는가

요약 대상이 **공개 검색 결과만**이고 개인정보를 포함하지 않기 때문입니다.
일자리검색(SVC-1)은 개인정보를 다루므로 별도 에이전트로 분리되며, 본 서비스(SVC-3)는
공개 데이터만 외부 API로 보내는 구조이기에 GPT-4o mini 같은 상용 LLM을 자유롭게
사용할 수 있습니다.

GPT-4o mini를 선택한 이유:
- 짧은 한국어 요약(2~3줄)에 충분한 품질
- 응답 속도 빠름 (검색 결과 페이지 상단에 즉시 노출되어야 하므로 latency가 중요)
- 토큰 비용 저렴

## SVC-1 과의 관계

본 preset은 그 자체로 컴파일된 LangGraph 서브그래프(`CompiledStateGraph`)이므로,
나중에 SVC-1(일자리검색) 에이전트가 추가될 때 **상위 멀티에이전트 그래프의 한 노드**로
임베드할 수 있습니다. 본 작업 범위에서는 SVC-3만 단독으로 동작하지만, 합성 가능한
구조로 설계해 두었습니다.

## 출력 스키마

서비스는 검색어 한 건당 다음 JSON을 반환합니다 (LangChain `AIMessage.content` 안에
직렬화된 문자열로 담김).

```json
{
  "query": "AI 직업훈련",
  "summary": "한국어 2~3줄 요약 텍스트",
  "primary": {
    "category": "훈련",
    "url": "https://www.work24.go.kr/...",
    "title": "AI 융합 백엔드 개발자 과정"
  },
  "related_categories": [
    {"category": "정책", "url": "...", "title": "..."},
    {"category": "직업·진로", "url": "...", "title": "..."}
  ],
  "related_queries": ["연관검색어1", "연관검색어2", "..."],
  "related_jobs": ["대분류 > 중분류 > 직종명1", "대분류 > 중분류 > 직종명2"],
  "meta": {
    "ranking": ["훈련", "직업·진로", "정책", "채용", "자격", "기업", "신고·신청", "뉴스·자료", "기타"],
    "result_count": 26,
    "fetched_at": "2026-04-07T06:42:11+00:00"
  }
}
```

`primary` 와 `related_categories` 의 각 항목은 모두 동일한 ``{category, url, title}``
모양을 가집니다. UI 가 같은 카드 컴포넌트로 1순위와 2·3순위를 일관되게 그릴 수 있도록
의도된 구조입니다. 1순위 결과가 없으면 `primary` 는 세 필드가 모두 빈 문자열인
빈 카드(`{"category": "", "url": "", "title": ""}`)가 됩니다.

| 필드 | 설명 | 비고 |
|---|---|---|
| `query` | 호출자가 보낸 검색어 (preprocess 로 strip 됨) | 응답을 self-contained 로 만들기 위해 함께 echo |
| `summary` | LLM 생성 한국어 요약 | 2~3줄 / 200자 이내 |
| `primary` | 1순위 카테고리의 top1 결과 카드 | `{category, url, title}` |
| `related_categories` | 2·3순위 카테고리에서 각 1개씩 | 같은 카드 모양, 최대 2개 |
| `related_queries` | work24 페이지의 `form_keyword1` 영역 | 최대 5개 |
| `related_jobs` | work24 페이지의 `form_keyword2` 영역 | 최대 2개 |
| `meta.ranking` | 의도 분류 LLM 이 매긴 9개 카테고리 우선순위 전체 | 디버깅·분석용 |
| `meta.result_count` | work24 에서 가져와 정규화한 전체 결과 건수 | 디버깅·모니터링용 |
| `meta.fetched_at` | 응답 생성 시각 (UTC ISO 8601, 초 단위) | 캐시·로그 정합성용 |

`meta` 는 화면에 직접 노출할 의무 없이, 호출자가 디버깅·로그·캐시 정합성·A/B 분석에
참고할 수 있도록 부수적으로 담아 두는 영역입니다.

---

# Part 2 — 개발

## 빠른 시작

```bash
# 1. 의존성 설치
uv sync

# 2. 환경변수 설정
cp .env.example .env
# .env 안의 OPENAI_API_KEY 를 본인 키로 교체

# 3. 한 번 호출해 보기 (서버 없이)
uv run python scripts/try_search_summary.py "AI 직업훈련"

# 4. LangServe 로 띄우기
./scripts/run-local.sh
# → http://localhost:8000/agent/playground/
```

`OPENAI_API_KEY`만 있으면 바로 동작합니다. 다른 외부 인프라(OpenSearch / DB / 벡터스토어 등)는
필요 없습니다 — work24 페이지 HTML을 직접 가져와서 파싱하기 때문입니다.

## 폴더 구조

```
.
├─ src/
│  ├─ graph.py                        # langgraph.json 의 진입점 (compiled graph 노출)
│  └─ agents/
│      ├─ __init__.py                 # 공개 API: build_graph, list_presets, State 등
│      ├─ graph_builder.py            # build_graph(preset=...) 단일 진입점
│      ├─ state.py                    # InputState/InternalState/OutputState/Context
│      ├─ registry.py                 # PresetInfo 등록부
│      ├─ _utils.py                   # find_project_root 등 패키지 내부 유틸
│      ├─ presets/
│      │  └─ ai_search_summary.py     # ⭐ 그래프 빌더 (StateGraph 조립)
│      └─ nodes/
│         ├─ preprocess.py            # 입력 메시지 정규화
│         ├─ worker_search_summary.py # ⭐ 핵심 worker — LLM + HTTP + 파서 모두 포함
│         └─ postprocessor.py         # _worker_outputs → AIMessage 변환
├─ app/
│  ├─ run.py                          # uvicorn 진입점
│  └─ utils/
│      ├─ server.py                   # FastAPI + LangServe create_app()
│      ├─ langgraph_loader.py         # langgraph.json 로딩
│      └─ schema.py                   # langgraph.json dataclass
├─ tests/
│  ├─ conftest.py                     # 더미 OPENAI_API_KEY 자동 주입
│  ├─ test_ai_search_summary.py       # 20건 단위/통합 테스트
│  └─ fixtures/work24_sample.html     # 실제 work24 응답 캡처 (파서 회귀 방지)
├─ scripts/
│  ├─ run-local.sh                    # LangServe 로컬 실행
│  ├─ run-docker.sh                   # Docker 실행
│  └─ try_search_summary.py           # 서버 없이 직접 호출하는 CLI
├─ langgraph.json                     # preset / 그래프 경로 / 서비스 메타
├─ pyproject.toml
├─ .env.example
├─ CLAUDE.md                          # 루트 작업 컨벤션
└─ src/agents/CLAUDE.md, app/CLAUDE.md
```

⭐ 표시한 두 파일이 SVC-3의 핵심입니다. 나머지는 그래프 조립·서빙 인프라.

## 아키텍처

### 큰 그림 — 요청이 들어와서 응답이 나가기까지

```
HTTP POST /agent/invoke              사용자 / 호출자
        │
        ▼
┌──────────────────────┐
│ FastAPI + LangServe  │  app/run.py + app/utils/server.py
│  (add_routes 가      │  preset 메타를 langgraph.json 에서 읽어 그래프 등록
│   /agent/* 노출)     │
└──────────┬───────────┘
           │  graph.ainvoke({"messages": [HumanMessage("AI 직업훈련")]})
           ▼
┌────────────────────────────────────────────────────────────┐
│  CompiledStateGraph  (build_ai_search_summary 가 컴파일)   │
│                                                            │
│   START → preprocess → worker_search_summary → postprocessor → END
│                                                            │
└────────────────────────────────────────────────────────────┘
           │
           ▼
   AIMessage(content=<JSON 문자열>) 반환
```

핵심 포인트:

- **그래프는 1번만 컴파일**되어 프로세스 기동 시 메모리에 상주합니다
  ([src/graph.py](src/graph.py) 의 `graph = build_graph(preset=_read_preset())`).
- 매 요청마다 **새 인스턴스를 만들지 않고** 같은 컴파일된 그래프를 공유합니다.
- LangServe 가 `/agent/invoke`, `/agent/stream`, `/agent/playground/` 등의 표준
  엔드포인트를 자동으로 만들어줍니다.

### 그래프 내부 — 3개 노드의 선형 파이프라인

```
                  ┌──────────────┐
   입력 messages  │  preprocess  │  마지막 HumanMessage 를 strip 정규화
       ───►       └──────┬───────┘
                         ▼
                  ┌──────────────────────────┐
                  │  worker_search_summary   │  ← 이 노드 안에서
                  │                          │     의도분류·검색·요약·navigation
                  │   (LLM × 2 + HTTP × 1)   │     이 모두 순차 실행됨
                  └──────────┬───────────────┘
                             │  _worker_outputs[0]["data"]["response"] = JSON 문자열
                             ▼
                  ┌──────────────────┐
                  │  postprocessor   │  _worker_outputs → AIMessage 변환
                  └──────┬───────────┘
                         ▼
                   출력 messages
                  (마지막이 AIMessage(content=JSON))
```

**왜 노드를 잘게 쪼개지 않았나?** 의도분류 → 검색 → 선별 → 요약은 본질적으로 선형이고
중간에 분기·재시도·HITL이 필요 없습니다. LangGraph 의 노드 경계는 분기/스트리밍/체크포인트가
필요할 때 의미가 있는데, 우리 흐름엔 그게 없으므로 노드를 늘리면 state 직렬화·트레이싱
스팬만 더해지고 가독성은 떨어집니다. **단일 worker 노드 + 결정론적 헬퍼 함수**가
가장 깔끔합니다.

### worker_search_summary 내부 — 7단계 흐름

```
state["messages"] (입력)
        │
        ▼ ① _extract_query()                  (worker_search_summary.py:494)
   query 문자열
        │
        ├──────────────────────────────────┐
        ▼                                  ▼
② _classify_intent(query)         ③ fetch_work24_search(query)
   LLM #1 (gpt-4o-mini,                HTTP GET work24 통합검색
           structured output)           → BeautifulSoup 파싱
        │                                  │
        ▼                                  ▼
   ranking: list[str]            results: list[dict]
   ["훈련", "직업·진로", ...]      related_queries, related_jobs
        │                                  │
        └──────────┬───────────────────────┘
                   ▼
   ④ _select_top_k_by_category(results, ranking, k=SUMMARY_INPUT_COUNT)   (결정론, LLM 미사용)
        │
        ▼
   selected: list[dict]  (요약 LLM 에 넘길 핵심 결과 SUMMARY_INPUT_COUNT 건)
        │
        ▼
   ⑤ _summarize(query, selected)
        LLM #2 (gpt-4o-mini, plain ainvoke)
        │
        ▼
   summary: str  (한국어 2~3줄)
        │
        ▼
   ⑥ _build_navigation(results, ranking, related_queries, related_jobs)
        │
        ▼
   navigation: dict
        │
        ▼
   ⑦ payload = {query, summary, primary, related_categories, related_queries, related_jobs, meta}
        json.dumps(...) → _worker_outputs 에 push
```

각 단계의 자세한 코드 위치는 다음 섹션에서 설명합니다.

## 각 노드 상세

### preprocess — [src/agents/nodes/preprocess.py](src/agents/nodes/preprocess.py)

입력 messages 의 마지막 `HumanMessage` 를 strip 정규화합니다. 단순한 입력 위생
처리이며 변경이 없으면 빈 dict 를 반환해 state 를 건드리지 않습니다.

```python
async def preprocess(state: State, **kwargs: Any) -> dict[str, Any]:
    messages = state.get("messages", [])
    if not messages:
        return {}
    last_message = messages[-1]
    if isinstance(last_message, HumanMessage) and isinstance(last_message.content, str):
        cleaned = last_message.content.strip()
        if cleaned != last_message.content:
            return {"messages": [HumanMessage(content=cleaned)]}
    return {}
```

### worker_search_summary — [src/agents/nodes/worker_search_summary.py](src/agents/nodes/worker_search_summary.py)

SVC-3 의 핵심. 7단계 흐름이 한 함수 안에서 순차 실행됩니다.

```python
async def worker_search_summary(state: State, **kwargs: Any) -> dict[str, Any]:
    query = _extract_query(state)
    if not query:
        # 빈 query → LLM/HTTP 호출 생략, 빈 payload 즉시 반환
        ...

    search_result_count = _search_result_count()      # SEARCH_RESULT_COUNT (env)
    summary_input_count = _summary_input_count()      # SUMMARY_INPUT_COUNT (env)

    ranking = await _classify_intent(query)
    results, related_queries, related_jobs = await fetch_work24_search(
        query, list_count=search_result_count
    )
    selected = _select_top_k_by_category(results, ranking, k=summary_input_count)
    summary = await _summarize(query, selected)
    navigation = _build_navigation(results, ranking, related_queries, related_jobs)

    payload = {
        "query": query,
        "summary": summary,
        "primary": navigation["primary"],
        "related_categories": navigation["related_categories"],
        "related_queries": navigation["related_queries"],
        "related_jobs": navigation["related_jobs"],
        "meta": {
            "ranking": ranking,
            "result_count": len(results),
            "fetched_at": _now_iso(),
        },
    }
    return {
        "_worker_outputs": [
            {"status": "success",
             "data": {"response": json.dumps(payload, ensure_ascii=False)}}
        ]
    }
```

함수 본체는 **얇고**, 실제 일은 모듈 레벨 헬퍼 함수들이 합니다. 각 헬퍼는 단일 책임을
가지며 단위 테스트도 헬퍼 단위로 작성됩니다.

#### ① 의도 분류 — `_classify_intent` ([worker_search_summary.py:443](src/agents/nodes/worker_search_summary.py#L443))

GPT-4o mini 에게 "이 검색어는 어떤 카테고리부터 봐야 하느냐"를 물어 9개 카테고리
우선순위 리스트를 받습니다. Pydantic `_IntentResult` 를 `with_structured_output` 으로
강제해 LLM 출력이 항상 같은 스키마로 떨어지도록 합니다.

```python
class _IntentResult(BaseModel):
    category_ranking: list[str] = Field(
        ..., description="카테고리 우선순위 (중복 없이 모든 카테고리를 포함)."
    )

async def _classify_intent(query: str) -> list[str]:
    try:
        llm = init_chat_model(_MODEL_ID).with_structured_output(_IntentResult)
        result = await llm.ainvoke([
            SystemMessage(content=_INTENT_SYSTEM_PROMPT),
            HumanMessage(content=query),
        ])
        ranking = list(result.category_ranking) if result else []
        # LLM 이 일부 카테고리를 빼먹으면 뒤에 보충
        seen = set(ranking)
        for cat in _ALL_CATEGORIES:
            if cat not in seen:
                ranking.append(cat)
        return ranking
    except Exception:
        _log.exception("intent classification failed; using default ranking")
        return list(_DEFAULT_CATEGORY_RANKING)
```

세 가지 디테일:

1. **`_ALL_CATEGORIES` 에 "전체"가 없습니다.** work24 의 "전체" 탭은 9개를 한 화면에
   모은 필터일 뿐 별도 결과 섹션이 아닙니다. 후보에 포함하면 LLM 이 의미 없는
   안전선택으로 늘 1순위로 잡아 의도 분류가 무력화되기 때문에 의식적으로 제외했습니다.
2. **누락 카테고리 보정.** LLM 이 9개 중 일부만 답하면 나머지를 뒤에 붙여 항상
   완전한 ranking 을 만듭니다. `_select_top_k_by_category` 가 ranking 을 인덱스로
   사용하므로 누락이 있으면 결과 순서가 망가집니다.
3. **항상 무언가 반환.** 예외가 나면 `_DEFAULT_CATEGORY_RANKING`(중립 순서)으로
   fallback. 사용자에게는 절대 5xx 를 돌려주지 않는다는 원칙입니다.

#### ② work24 검색 호출 — `fetch_work24_search` ([worker_search_summary.py:304](src/agents/nodes/worker_search_summary.py#L304))

work24 통합검색 페이지를 그대로 GET 해서 HTML 을 받고 `_parse_work24_html` 에 넘깁니다.

```python
async def fetch_work24_search(
    query: str, *, list_count: int = _DEFAULT_SEARCH_RESULT_COUNT,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    if not query:
        return [], [], []

    params = {
        "topQuerySearchArea": "all",
        "topQueryData": query,
        ...
        "listCount": str(list_count),
        "reportSort": "TITLE",
        "workinfoSort": "RANK",
        "trainingSort": "DATE",
        ...
    }
    headers = {"User-Agent": _WORK24_USER_AGENT}

    try:
        async with httpx.AsyncClient(
            base_url=_WORK24_BASE,
            timeout=_WORK24_HTTP_TIMEOUT,
            headers=headers,
            follow_redirects=True,
        ) as client:
            response = await client.get(_WORK24_SEARCH_PATH, params=params)
            response.raise_for_status()
            html = response.text
    except httpx.HTTPError:
        _log.exception("work24 fetch failed for query=%r", query)
        return [], [], []
    ...
    return _parse_work24_html(html)
```

핵심 디테일:

- **카테고리별 정렬 옵션을 명시.** work24 는 카테고리마다 별도의 sort 파라미터를
  받습니다 (`workinfoSort=RANK`, `trainingSort=DATE`, `reportSort=TITLE`, ...).
  파라미터가 누락되면 일부 동적 영역(연관검색어 등)이 다르게 렌더링되어 사용자가
  브라우저에서 보는 결과와 어긋납니다. 브라우저가 실제로 보내는 파라미터셋을 그대로
  복제해 두었습니다.
- **`list_count`**: 카테고리당 최대 N개. 기본 20 이며 환경변수
  `SEARCH_RESULT_COUNT` 로 1~100 사이에서 조정 가능. 너무 작으면 navigation
  카드가 빈약해지고, 너무 크면 한 호출이 무거워집니다.
- **명시적 User-Agent**: httpx 기본 UA 가 차단될 가능성을 피해 Chrome UA 로 위장.
- **`timeout=5.0`**: 한 번의 검색에 5초 이상 걸리면 그냥 빈 결과로 fallback.
  사용자 경험상 검색 결과 페이지 상단에 5초 이상 걸리는 카드는 아예 없는 게 낫습니다.
- **모든 예외 catch**: `httpx.HTTPError` 뿐 아니라 모든 `Exception` 도 잡습니다. 절대
  worker 가 raise 하지 않도록 해서 그래프 전체가 깨지지 않게 합니다.

> ⚠️ 이 부분은 공식 API 가 아니라 공개 페이지의 HTML 스크래핑입니다. work24 가
> 셀렉터를 변경하면 파서가 깨질 수 있고, 그때는 [tests/fixtures/work24_sample.html](tests/fixtures/work24_sample.html)
> 을 새로 캡처한 뒤 `_parse_work24_html` 의 셀렉터를 보수하면 됩니다. 공식 API 가
> 제공되면 fetcher 본문을 그쪽으로 교체하는 것이 본질적인 해결책입니다.

#### ③ HTML 파서 — `_parse_work24_html` ([worker_search_summary.py:251](src/agents/nodes/worker_search_summary.py#L251))

BeautifulSoup 으로 work24 의 결과 HTML 을 정규화된 dict 리스트로 변환합니다.

```python
def _parse_work24_html(
    html: str,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    if not html:
        return [], [], []
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        _log.exception("BeautifulSoup parsing failed")
        return [], [], []

    results: list[dict[str, Any]] = []
    for stit in soup.select("div.stit_area"):
        cat_span = stit.select_one("span.t2_sb")
        if not cat_span:
            continue
        category = " ".join(cat_span.get_text(" ", strip=True).split())
        ...
        section = header.find_next_sibling("div", class_="result_view")
        ul = section.select_one("ul.srch_list_default")
        for li in ul.find_all("li", recursive=False):
            parsed = _parse_li(li, category)
            if parsed is not None:
                results.append(parsed)

    related_queries = _parse_related_queries(soup)
    related_jobs = _parse_related_jobs(soup)
    return results, related_queries, related_jobs
```

work24 의 마크업 구조 ↔ 우리가 추출하는 데이터 매핑:

| HTML 위치 | 추출 대상 |
|---|---|
| `div.stit_area span.t2_sb` | 카테고리 이름 (채용/훈련/...) |
| 카테고리 헤더의 형제 `div.result_view > ul.srch_list_default > li` | 결과 항목들 |
| 의미있는 첫 `<a href>` (javascript:/# 제외) | 결과 URL (상대→절대 변환) |
| `<a>` 텍스트 / `<strong>` fallback | 결과 title |
| `span.item` 들 + `<strong>` | snippet |
| `div#form_keyword1 button[name=_btn_recommend]` | 연관검색어 (최대 5) |
| `div#form_keyword2 button[name=_btn_jobsCategor]` | 연관직종 (최대 2) |

파서는 의도적으로 **정규화된 단일 스키마**(`{title, snippet, url, category, meta}`)를
출력합니다. 카테고리마다 채용/훈련/뉴스 등 필드 구조가 다르지만, 그 이질성은
`meta.items` 안의 자유 형식 텍스트 리스트에 담아 LLM 이 직접 해석하도록 위임했습니다.
이렇게 해야 카테고리가 추가되거나 변경돼도 파서·worker 코드를 거의 안 건드려도 됩니다.

부수적으로 **placeholder li 필터링**(`_is_placeholder_title`)을 통해 메뉴 카운트
숫자(`"0"`, `"9"`, `"62,370"`)가 결과로 잡히지 않게 막고 있습니다. work24 가 일부
섹션에서 결과가 없을 때 카운트 숫자만 들어 있는 li 를 렌더링하기 때문입니다.

#### ④ top-k 선별 — `_select_top_k_by_category` ([worker_search_summary.py:373](src/agents/nodes/worker_search_summary.py#L373))

LLM 이 만든 ranking 을 기준으로 결과를 stable sort 후 상위 k개를 자릅니다.
순수 함수 — LLM/HTTP 호출 없음.

```python
def _select_top_k_by_category(
    results: list[dict[str, Any]],
    ranking: list[str],
    *,
    k: int = 5,
) -> list[dict[str, Any]]:
    rank_index = {cat: idx for idx, cat in enumerate(ranking)}
    fallback = len(ranking)
    sorted_results = sorted(
        results,
        key=lambda r: rank_index.get(r.get("category", ""), fallback),
    )
    return sorted_results[:k]
```

이 N건이 ⑤ 요약 LLM 의 컨텍스트로 들어갑니다. 기본값은 5 이며 환경변수
`SUMMARY_INPUT_COUNT` 로 1~100 사이에서 조정 가능합니다. 더 많이 넣으면 토큰·지연이
늘고, 너무 적게 넣으면 요약이 빈약해집니다. 5가 현재 균형점.

#### ⑤ 요약 — `_summarize` ([worker_search_summary.py:468](src/agents/nodes/worker_search_summary.py#L468))

선별된 결과(`SUMMARY_INPUT_COUNT` 건)를 JSON 으로 직렬화해서 GPT-4o mini 에 넘기고
한국어 2~3줄을 받습니다.
시스템 프롬프트에 "200자 이내, 평문, 추측 금지, 결과에 근거" 같은 제약을 걸어
출력 톤을 일관되게 유지합니다.

```python
_SUMMARY_SYSTEM_PROMPT = (
    "당신은 고용24 검색 결과 요약 어시스턴트입니다. "
    "사용자의 질의와 검색 결과(JSON)를 받아 한국어로 2~3줄 요약을 생성합니다. "
    "규칙: "
    "(1) 핵심 정보만 담을 것, "
    "(2) 과장·추측 금지, 제공된 결과에 근거할 것, "
    "(3) 2~3개 문장으로 총 길이는 200자 이내, "
    "(4) 마크다운/특수문자 없이 평문으로."
)

async def _summarize(query: str, selected: list[dict[str, Any]]) -> str:
    try:
        llm = init_chat_model(_MODEL_ID)
        payload = json.dumps(selected, ensure_ascii=False)
        result = await llm.ainvoke([
            SystemMessage(content=_SUMMARY_SYSTEM_PROMPT),
            HumanMessage(content=f"질의: {query}\n검색결과: {payload}"),
        ])
        text = result.content if hasattr(result, "content") else str(result)
        return text.strip() if isinstance(text, str) else str(text)
    except Exception:
        _log.exception("summarization failed; using fallback title echo")
        if selected:
            return str(selected[0].get("title", ""))
        return ""
```

LLM 호출이 실패하면 top-1 결과의 title 을 그대로 echo 합니다. 사용자에게는 항상
최소한 무언가 의미 있는 텍스트가 노출됩니다.

#### ⑥ navigation 구성 — `_build_navigation` ([worker_search_summary.py:393](src/agents/nodes/worker_search_summary.py#L393))

순수 함수 — primary URL, 추가 탐색 경로, 연관검색어/직종 을 dict 로 묶습니다.

- `primary` ← ranking 1순위 카테고리에서 첫 번째 결과의 카드 `{category, url, title}`
- `related_categories` ← ranking 2·3순위에서 각 1개씩, primary 와 동일한 모양
- `related_queries` ← 파서가 뽑아둔 연관검색어 (캡: 5)
- `related_jobs` ← 파서가 뽑아둔 연관직종 (캡: 2)

primary 와 related_categories 는 같은 dict 모양을 공유하므로 호출자가 동일한
카드 컴포넌트로 1순위와 2·3순위를 동시에 처리할 수 있습니다.

#### ⑦ 출력 직렬화

worker 함수의 마지막 단계 — payload 를 `json.dumps(..., ensure_ascii=False)` 로
직렬화해 `_worker_outputs[0]["data"]["response"]` 에 넣습니다.

### postprocessor — [src/agents/nodes/postprocessor.py](src/agents/nodes/postprocessor.py)

`_worker_outputs[0]["data"]["response"]` 를 그대로 `AIMessage.content` 로 변환합니다.
worker 가 이미 JSON 문자열을 만들어 두었으므로 별도 변환 없이 그대로 통과시킵니다.

```python
async def postprocessor(state: State, **kwargs: Any) -> dict[str, Any]:
    worker_outputs = state.get("_worker_outputs", [])
    if not worker_outputs:
        return {"messages": [AIMessage(content="No worker output received.")]}
    worker_output = worker_outputs[0]
    response = worker_output.get("data", {}).get("response", "")
    return {"messages": [AIMessage(content=response)]}
```

이 노드는 SVC-3 전용이 아니라 **여러 worker 가 공유할 수 있는 범용 어댑터**입니다.
나중에 SVC-1 등 다른 worker 가 추가돼도 같은 `_worker_outputs` 컨벤션을 따르면
postprocessor 를 그대로 재사용할 수 있습니다.

## State 정의 — [src/agents/state.py](src/agents/state.py)

LangGraph state 는 4분리 패턴을 따릅니다.

```python
class InputState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]

class InternalState(TypedDict, total=False):
    _worker_outputs: Annotated[list[dict[str, Any]], add]

class OutputState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]

class State(InputState, InternalState, OutputState, total=False):
    pass

class Context(TypedDict, total=False):
    debug: bool
```

| 분류 | 역할 | 외부 노출 |
|---|---|---|
| `InputState` | 그래프에 들어오는 입력 | ✅ |
| `InternalState` | 노드 사이에서만 쓰는 작업 영역 (`_` 접두사) | ❌ |
| `OutputState` | 최종 응답 | ✅ |
| `Context` | 런타임 설정 (state 에 안 들어감) | ✅ |

핵심 설계 결정: **SVC-3 추가 시 `state.py` 를 한 줄도 건드리지 않았습니다.** 검색 의도,
검색 결과, 요약, navigation 등 모든 중간 데이터는 기존 `_worker_outputs` 의 dict 안에
담깁니다. 이렇게 한 이유:

- `state.py` 는 모든 노드가 공유하는 최상위 스키마이므로 변경 영향이 큽니다.
- 한 번 추가한 필드는 지우기 어려워집니다.
- "내부 작업 데이터는 `_worker_outputs` 한 곳에 모은다"는 컨벤션이 일관성 있게
  유지됩니다.

대신 worker 가 출력 직전에 모든 데이터를 JSON 으로 직렬화해서 `_worker_outputs[0].data.response`
하나의 string 필드에 담는 방식으로 풉니다. postprocessor 가 그 string 을 그대로
`AIMessage.content` 로 옮기는 단일 책임만 갖게 되어 둘 다 단순해집니다.

## graph_builder — [src/agents/graph_builder.py](src/agents/graph_builder.py)

`build_graph(preset=...)` 단일 진입점. 현재는 등록된 preset 이 하나뿐이므로 dict 가
1줄짜리지만, 다른 에이전트(SVC-1 등)가 추가되면 여기에 등록만 하면 됩니다.

```python
_BUILDERS: dict[str, Any] = {
    "ai_search_summary": build_ai_search_summary,
}

def build_graph(
    preset: str = "ai_search_summary",
    **kwargs: Any,
) -> CompiledStateGraph:
    builder_fn = _BUILDERS.get(preset)
    if builder_fn is None:
        available = ", ".join(_BUILDERS.keys())
        raise ValueError(f"Unknown preset '{preset}'. Available: {available}")
    return builder_fn(**kwargs)
```

> 이 단순한 형태(`Preset` Literal 없음, `registry.py` 없음)는 main 템플릿이
> 의도적으로 채택한 방향입니다. 자세한 정렬 이력은 본 문서 하단의
> [main 템플릿 정렬 작업](#main-템플릿-정렬-작업) 섹션을 참고하세요.

## 서빙 레이어 — [app/](app/)

LangServe 가 그래프 한 줄을 받아 표준 HTTP 엔드포인트를 만들어 줍니다.

```
/agent/invoke           POST  단일 호출
/agent/stream           POST  스트리밍
/agent/playground/      GET   브라우저 UI
/health                 GET   서비스 상태
/docs                   GET   Swagger UI
```

진입점은 [app/run.py](app/run.py) 이며, 환경변수(`HOST` / `PORT` / `RELOAD`)는
`.env` 또는 셸에서 모두 주입할 수 있습니다.

```python
if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = _env_bool("RELOAD", default=True)
    uvicorn.run("app.run:app", host=host, port=port, reload=reload)
```

`./scripts/run-local.sh` 도 같은 환경변수를 본 후 `uv run uvicorn app.run:app ...` 을
호출합니다. 두 진입점이 동일한 `.env` 를 보고 동일한 기본값을 갖습니다.

## 사용 방법

### 방법 1 — CLI 스크립트로 직접 호출 (가장 빠름)

서버 없이 파이썬에서 그래프를 직접 invoke 합니다. 결과를 보기 좋은 형식으로 출력합니다.

```bash
uv run python scripts/try_search_summary.py "AI 직업훈련"
uv run python scripts/try_search_summary.py "청년 취업 지원금"
uv run python scripts/try_search_summary.py "ai"
```

출력 예:

```
검색어: AI 직업훈련
============================================================

📝 요약:
  AI 직업훈련 관련 정보가 다양합니다. 대구에서 Spring Boot & AI 융합 백엔드
  개발자 과정을 2026년부터 2027년까지 진행하며, 훈련 시간은 총 1408시간입니다.
  ...

🔗 1순위 결과:
  - [훈련] AI 융합 백엔드 개발자 과정
    https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl.do?tracseId=...

📂 추가 탐색 경로:
  - [채용] 우리와 함께 미래를 만들어갈 AI 교육 강사를 찾습니다.
    https://www.work24.go.kr/wk/a/b/1500/...
  - [직업·진로] 4차 산업혁명 미래 일자리 전망

🔍 연관검색어:
  인공지능 개발, 머신러닝, 알고리즘 최적화, 자연어 처리, 컴퓨터 비전

💼 연관직종:
  - 연구 및 공학기술 > 데이터 및 정보시스템·웹 운영 > 데이터 분석가(빅데이터 분석가)
  - 연구 및 공학기술 > 소프트웨어 > 응용 소프트웨어 개발자
```

### 방법 2 — Python 코드에서 직접 호출

```python
import asyncio, json
from langchain_core.messages import HumanMessage
from agents import build_graph

async def main():
    graph = build_graph("ai_search_summary")
    result = await graph.ainvoke(
        {"messages": [HumanMessage("AI 직업훈련")]}
    )
    payload = json.loads(result["messages"][-1].content)
    print(payload["query"])                # echo 된 검색어
    print(payload["summary"])
    print(payload["primary"])              # {"category", "url", "title"}
    print(payload["related_categories"])   # 같은 모양의 카드 리스트
    print(payload["related_queries"])
    print(payload["related_jobs"])
    print(payload["meta"])                 # ranking / result_count / fetched_at

asyncio.run(main())
```

### 방법 3 — LangServe 서버로 띄우기

```bash
./scripts/run-local.sh
```

기본값 `http://0.0.0.0:8000` 에서 기동합니다. 브라우저로 접속:

- Playground UI: <http://localhost:8000/agent/playground/>
- API 문서(Swagger): <http://localhost:8000/docs>
- 헬스 체크: <http://localhost:8000/health>

curl 예시:

```bash
# Windows Git Bash 에서 한글이 들어간 body 는 utf-8 인코딩 문제로
# --data 직접 전달 대신 파일로 보내는 것이 안전합니다.
echo '{"input":{"messages":[{"type":"human","content":"AI 직업훈련"}]}}' > payload.json
curl -X POST http://localhost:8000/agent/invoke \
  -H "Content-Type: application/json" \
  --data-binary @payload.json
```

## 환경변수

| 변수 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `OPENAI_API_KEY` | ✅ | — | 의도 분류 + 요약에 사용. 없으면 fallback 으로만 동작 |
| `LLM_MODEL` | | `openai:gpt-4o-mini` | 의도 분류·요약에 쓰는 모델. `provider:model-id` 형식 |
| `SEARCH_RESULT_COUNT` | | `20` | work24 에서 카테고리당 받아올 결과 개수 (1~100) |
| `SUMMARY_INPUT_COUNT` | | `5` | 요약 LLM 에 입력으로 넘길 결과 개수 (1~100) |
| `HOST` | | `0.0.0.0` | LangServe bind host |
| `PORT` | | `8000` | LangServe bind port |
| `RELOAD` | | `true` | uvicorn auto-reload (개발용) |

`.env.example` 을 복사해서 사용하세요. 자세한 사용은 [.env.example](.env.example) 참고.

### `LLM_MODEL` 형식 자세히

`init_chat_model("provider:model-id")` 형식을 따릅니다. 모델 ID 는 langchain 이
공식 지원하는 provider 만 사용 가능합니다.

```bash
LLM_MODEL=openai:gpt-4o-mini                       # 기본
LLM_MODEL=openai:gpt-4o                            # 더 정확한 요약
LLM_MODEL=anthropic:claude-haiku-4-5-20251001      # Anthropic
LLM_MODEL=gpt-4o-mini                              # prefix 생략 → openai 자동 보정
```

세 가지 안전장치:

1. **자동 prefix** — `LLM_MODEL=gpt-4o-mini` 처럼 provider 없이 모델명만 적으면
   `openai:` 가 자동 부착됩니다.
2. **provider 검증** — 알려진 provider (openai / anthropic / google_genai /
   azure_openai / bedrock / cohere / fireworks / groq / huggingface / mistralai /
   ollama / together / xai) 가 아니면 그래프 첫 호출 시점에 명확한 에러로
   실패합니다 (`_InvalidModelIdError`).
3. **빈 모델명 검증** — `LLM_MODEL=openai:` 처럼 모델 부분이 비어 있으면 동일하게
   에러로 실패합니다.

`OPENAI_API_KEY` 외에 다른 provider 를 쓰려면 그 provider 가 요구하는 API 키도
함께 설정해야 합니다 (예: `ANTHROPIC_API_KEY`).

### `SEARCH_RESULT_COUNT` / `SUMMARY_INPUT_COUNT` 자세히

두 변수는 같은 "결과 개수"지만 그래프의 다른 단계에 영향을 줍니다.

```
work24 호출
   │
   ▼
results (전체 풀)  ← SEARCH_RESULT_COUNT 가 결정
   │              ── 카테고리당 최대 N개씩 받아옴
   │              ── 9개 카테고리 합쳐 보통 13~40건
   │
   ├─ navigation 만드는 데 사용 (primary, related_categories, meta.result_count)
   │  → 풀이 클수록 1~3순위 카테고리에 결과가 있을 확률 ↑
   │
   ▼
selected (부분집합)  ← SUMMARY_INPUT_COUNT 가 결정
   │                ── ranking 우선순위 정렬 후 상위 N건
   │
   ▼
요약 LLM 입력
```

| 변수 | 무엇을 결정 | 늘리면 | 줄이면 |
|---|---|---|---|
| `SEARCH_RESULT_COUNT` | work24 에서 카테고리당 받아올 결과 개수 | navigation 다양성 ↑, 응답 무거움 | navigation 빈약 |
| `SUMMARY_INPUT_COUNT` | 요약 LLM 에 입력으로 넘길 결과 개수 | 요약 풍부, LLM 토큰·비용·지연 ↑ | 요약 빈약, 토큰 절약 |

선별 동작은 **카테고리 우선순위 순서로 stable sort 후 앞에서부터 N건**:

> 예: `SUMMARY_INPUT_COUNT=10` 이고 ranking 1순위가 "훈련" (8건), 2순위가
> "직업·진로" (3건) 이면, 훈련 8건 + 직업·진로 2건 = 10건이 LLM 에 들어갑니다.
> 1순위 카테고리에 결과가 충분하면 그 카테고리만으로 채워질 수 있습니다.

검증:
- 1~100 범위의 정수만 허용
- 정수가 아니거나 범위를 벗어나면 그래프 첫 호출 시점에 `_InvalidCountError`
  로 즉시 실패 (운영자가 설정 오류를 즉시 인지하도록)

## 안정성 — 모든 실패 지점에 fallback

본 서비스는 사용자에게 절대 5xx 를 돌려주지 않는다는 원칙을 따릅니다. 모든 실패
지점에 graceful degradation 이 있습니다.

| 실패 지점 | fallback 동작 |
|---|---|
| 의도 분류 LLM 실패 | `_DEFAULT_CATEGORY_RANKING` 사용 (9개 카테고리 중립 순서) |
| 요약 LLM 실패 | top-1 결과의 title 을 그대로 echo |
| work24 fetch 실패 (network/timeout/HTTPError) | 빈 결과 + 경고 로그, 파이프라인 계속 |
| HTML 파싱 실패 | 동일 (빈 결과 + 경고 로그) |
| 빈 query | LLM/fetch 호출 생략, 빈 payload 즉시 반환 |

각각의 fallback 은 대응되는 단위 테스트가 있어서 회귀가 발생하면 즉시 잡힙니다.

## 테스트 — [tests/test_ai_search_summary.py](tests/test_ai_search_summary.py)

### 전략

I/O 경계(LLM, HTTP)에서만 mock 하고, 순수 함수는 그대로 호출합니다. 실제 LLM 호출이나
HTTP 호출 없이 20개 테스트가 모두 통과합니다.

```bash
uv run pytest tests/test_ai_search_summary.py -v
```

### 테스트 목록

| 분류 | 테스트 | 검증 대상 |
|---|---|---|
| **HTML 파서** (8) | `test_parse_work24_html_returns_results_and_related` | 정상 fixture 파싱 |
| | `test_parse_work24_html_results_have_required_fields` | 결과 dict 의 필수 필드 |
| | `test_parse_work24_html_covers_multiple_categories` | 카테고리 커버리지 |
| | `test_parse_work24_html_absolutizes_relative_urls` | URL 절대화 |
| | `test_parse_work24_html_extracts_related_jobs` | 연관직종 추출 |
| | `test_parse_work24_html_empty_input_returns_empty` | 빈 입력 처리 |
| | `test_parse_work24_html_garbage_input_returns_empty` | work24 가 아닌 HTML |
| | `test_parse_work24_html_truncated_input_does_not_raise` | 잘린 HTML 예외 안 던짐 |
| **선별 로직** (3) | `test_select_top_k_orders_by_ranking` | ranking 순서 적용 |
| | `test_select_top_k_truncates_to_k` | k개 컷 |
| | `test_select_top_k_unknown_category_goes_last` | 미지 카테고리 처리 |
| **navigation** (4) | `test_build_navigation_picks_primary_and_related` | primary + related 구성 |
| | `test_build_navigation_handles_missing_categories` | 카테고리 결과 부재 |
| | `test_build_navigation_caps_related_queries_at_5` | 연관검색어 cap |
| | `test_build_navigation_caps_related_jobs_at_2` | 연관직종 cap |
| **LLM fallback** (3) | `test_classify_intent_fallback_on_failure` | 분류 실패 시 default ranking |
| | `test_summarize_fallback_on_failure` | 요약 실패 시 title echo |
| | `test_summarize_fallback_on_empty_selection` | 빈 selection 처리 |
| **E2E** (2) | `test_preset_e2e_returns_json_ai_message` | preset 전체 흐름 (모두 mock) |
| | `test_preset_e2e_handles_empty_query` | 빈 query → 빈 payload |

총 **20건**, 회귀 0.

### 주의: 모듈 재노출 vs monkeypatch

`agents.nodes.__init__.py` 가 `worker_search_summary` 라는 이름을 함수로 재노출하기
때문에, 일반적인 `import agents.nodes.worker_search_summary as wss` 는 모듈이 아니라
함수에 바인딩됩니다. 모듈 객체에 monkeypatch 하려면 `importlib` 로 우회해야 합니다:

```python
import importlib
wss = importlib.import_module("agents.nodes.worker_search_summary")
# 이제 wss 는 모듈이므로 wss.fetch_work24_search 등에 monkeypatch 가능
```

## 의존성 — [pyproject.toml](pyproject.toml)

런타임에 필요한 패키지는 다음 9개뿐입니다:

| 패키지 | 용도 |
|---|---|
| `langchain` | `init_chat_model`, `with_structured_output` |
| `langchain-core` | `HumanMessage` / `SystemMessage` / `AIMessage` |
| `langchain-openai` | OpenAI 모델 어댑터 |
| `langgraph` | `StateGraph`, `CompiledStateGraph` |
| `langserve[all]` | FastAPI 라우트 자동 생성 |
| `httpx` | work24 비동기 HTTP 호출 |
| `beautifulsoup4` | work24 HTML 파싱 |
| `python-dotenv` | `.env` 로딩 |
| `uvicorn` | LangServe 진입점 |

OpenSearch / DeepAgents / 미들웨어 / 백엔드 등은 SVC-3 가 사용하지 않으므로 제거되었습니다.

## 다음에 누가 이 코드를 확장한다면

- **새 카테고리를 work24 가 추가하면** → `_ALL_CATEGORIES` 와 `_INTENT_SYSTEM_PROMPT`
  에 한 줄씩 추가. 파서는 그대로 두면 됨 (카테고리 이름을 동적으로 인식).
- **work24 마크업이 변경되면** → [tests/fixtures/work24_sample.html](tests/fixtures/work24_sample.html)
  을 새로 캡처하고 `_parse_work24_html` 의 셀렉터를 보수.
- **다른 LLM 으로 갈아끼우려면** → `_MODEL_ID` 한 줄만 수정
  (예: `"anthropic:claude-haiku-4-5"`).
- **새 에이전트(SVC-1 등)를 추가하려면** → [src/agents/CLAUDE.md](src/agents/CLAUDE.md)
  의 "preset 추가 절차" 따라가기.
- **공식 work24 API 가 나오면** → `fetch_work24_search` 본문만 교체.
  나머지(파서·worker·preset)는 그대로 둬도 됨.

## main 템플릿 정렬 작업

이 브랜치는 한때 자체적인 preset 메타데이터 레이어(`registry.py`, `Preset` Literal,
`/presets` 엔드포인트)를 도입했었지만, **상위 main 템플릿이 이후 단순화 방향으로
진화**하면서(`fix: Preset Literal 삭제`, `fix: 복잡한 Preset 관련 내용 삭제` 커밋 등)
양쪽이 정반대로 갈라진 시점이 있었습니다.

본 브랜치를 main 의 단순화 방향에 다시 맞춰 정리한 작업 내역입니다. 비즈니스
로직(work24 fetcher, 파서, LLM 요약, 테스트, fixture)은 **전혀 손대지 않았습니다.**

### 변경 요약 — Before / After

| 항목 | Before (이 브랜치 자체 방향) | After (main 정렬) |
|---|---|---|
| `src/agents/registry.py` | `PresetInfo` dataclass + `PRESETS` dict + `list_presets()` / `get_preset()` 존재 | **파일 삭제**. preset 메타데이터 레이어를 두지 않음 |
| `src/agents/graph_builder.py` | `Preset = Literal["ai_search_summary"]` 정의, `preset: Preset` 시그니처 | `Literal` 제거, `preset: str` 로 환원. `_BUILDERS` dict 만 단일 진실의 원천으로 유지 |
| `src/agents/__init__.py` | `Preset`, `PresetInfo`, `get_preset`, `list_presets` 추가 export | `build_graph` 와 State 타입만 export — main 과 동일한 단순한 표면 |
| `app/utils/server.py` | `/presets` REST 엔드포인트 + `list_presets` import + `# type: ignore[arg-type]` 주석 | `/presets` 엔드포인트 제거, `list_presets` import 제거, `type: ignore` 도 제거 |
| `app/CLAUDE.md` | `from agents import build_graph, list_presets` 안내 + "presets 등" 문구 | `from agents import build_graph` 로 환원 |
| `src/agents/CLAUDE.md` | preset 추가 절차에 "registry.py 등록" + "Preset Literal 추가" 단계 포함 | 두 단계 삭제. `_BUILDERS` dict 한 줄 추가만 남김 |
| `README.md` (graph_builder 스니펫) | `Preset = Literal[...]` 가 포함된 코드 예시 | `_BUILDERS` dict 만 보여주는 단순화된 예시 + 본 섹션으로의 링크 |

### 변경하지 않은 것 (의도적으로 그대로 둔 것)

- **`src/agents/state.py`** — main 과 두 브랜치가 동일하므로 손대지 않음
- **`src/agents/nodes/worker_search_summary.py`** (727 줄) — SVC-3 핵심 로직, 전부 유지
- **`src/agents/nodes/preprocess.py` / `postprocessor.py`** — 그대로 재사용
- **`tests/test_ai_search_summary.py` / `tests/fixtures/work24_sample.html`** — 변경 없음
- **`scripts/try_search_summary.py`** — 변경 없음
- **`pyproject.toml` / `uv.lock`** — 의존성 변경 없음
- **삭제됐던 backends/middlewares/skills/tools 등** — 본 브랜치에서는 이미 없는 상태이며, 본 정렬 작업에서 되살리지도 않음 (필요해지면 그때 main 에서 가져오면 됨)

### 정렬 후 효과

- 새 preset 을 추가할 때 손대야 할 파일이 **3개 → 2개** 로 줄어듦
  (registry.py 등록 단계 사라짐, `Preset` Literal 갱신 단계 사라짐)
- main 과의 구조적 차이가 SVC-3 전용 코드 자체에만 집중되어, 추후 main 의
  upstream 변경을 다시 가져올 때 충돌 가능성이 줄어듦
- 공개 API 표면(`agents.__init__`)이 main 과 동일해져 향후 임베드/재사용이 단순해짐

### 향후 main 에서 변경이 또 들어올 때

1. `git fetch upstream && git log main..upstream/main` 로 incoming 커밋 확인
2. 비즈니스 로직(`worker_search_summary.py` 등)과 무관한 변경이면 cherry-pick 또는 merge 시도
3. 충돌 시 — 본 섹션 표를 참고하여 main 의 단순화 방향을 우선 채택

## 참고 문서

- [CLAUDE.md](CLAUDE.md) — 루트 작업 컨벤션 (Python 스타일 / 네이밍 / Git / 로컬 서버 운영 규칙)
- [src/agents/CLAUDE.md](src/agents/CLAUDE.md) — 에이전트 레이어 컨벤션 (노드/preset/worker 추가 절차, State 변경 규칙)
- [app/CLAUDE.md](app/CLAUDE.md) — 서빙 레이어 컨벤션
