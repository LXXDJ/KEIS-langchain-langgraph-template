# AI 검색 결과 요약 (SVC-3)

[고용24(work24.go.kr)](https://www.work24.go.kr/cm/main.do) 통합검색 결과를 **AI 요약 제공** 하는 서비스.

## 목차

### Part 1 — 기획
- [배경과 목표](#배경과-목표)
- [핵심 기능](#핵심-기능)
- [서비스 흐름도 (아키텍처)](#서비스-흐름도-아키텍처)
- [요약 대상 카테고리와 제외 카테고리](#요약-대상-카테고리와-제외-카테고리)
- [카테고리별 요약 방식](#카테고리별-요약-방식)
- [실행 결과 예시](#실행-결과-예시)
- [출력 스키마](#출력-스키마)
- [모델 정책 — 외부 LLM (GPT-4o mini)](#모델-정책--외부-llm-gpt-4o-mini)
- [설계 결정 배경 — 의도 기반에서 카테고리별 요약으로](#설계-결정-배경--의도-기반-접근에서-카테고리별-요약으로)
- [SVC-1 과의 관계](#svc-1-과의-관계)

### Part 2 — 개발
- [빠른 시작](#빠른-시작)
- [폴더 구조](#폴더-구조)
- [아키텍처](#아키텍처)
- [각 노드 상세](#각-노드-상세)
- [State 정의](#state-정의--srcagentsstatepy)
- [graph_builder](#graph_builder--srcagentsgraph_builderpy)
- [서빙 레이어](#서빙-레이어--app)
- [사용 방법](#사용-방법)
- [환경변수](#환경변수)
- [안정성 — 모든 실패 지점에 fallback](#안정성--모든-실패-지점에-fallback)
- [테스트](#테스트--teststest_ai_search_summarypy)
- [의존성](#의존성--pyprojecttoml)
- [다음에 누가 이 코드를 확장한다면](#다음에-누가-이-코드를-확장한다면)
- [main 템플릿 정렬 작업](#main-템플릿-정렬-작업)
- [참고 문서](#참고-문서)

---

# Part 1 — 기획

## 배경과 목표

AI 검색 결과 사용자의 질문 의도에 맞는 핵심 정보만 선별하여 2~3줄로 요약 제공하는 서비스
- 요약정보를 통해 검색 결과를 한눈에 파악
- 원문 url 제공하여 손쉽게 상세 페이지로 이동 가능

## 핵심 기능

| 기능 | 설명 |
|---|---|
| **카테고리별 데이터 수집** | work24 통합검색 API 를 호출하여 9개 카테고리의 검색 결과를 수집 |
| **카테고리별 전용 프롬프트** | 카테고리별 데이터 특성에 맞추어 요약 생성 |
| **병렬 LLM 요약** | 5개 카테고리를 동시 호출하여 응답 속도를 단일 호출 수준으로 유지 |
| **요약 대상 선별** | 데이터 형태 기반으로 9개 중 5개만 요약 |
| **Fallback** | LLM 실패 시 최상위 결과 title 로 대체, fetch 실패 시 빈 응답으로 정상 반환 |

*결과가 0건인 카테고리는 응답에서 **완전히 제외**됩니다.

## 서비스 흐름도 (아키텍처)

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


## 요약 대상 카테고리와 제외 카테고리

### 요약 제공 카테고리 (5개)

| 카테고리 | 요약하는 이유 | 데이터 형태 |
|---|---|---|
| **정책** | 정책명, 지원대상, 신청방법이 구조화되어 있어 핵심 정보 추출이 가능 | 정책명 + 지원대상 설명 + 신청방법 |
| **채용** | 회사명, 직무, 지역, 마감일, 임금 등 풍부한 메타데이터로 의미 있는 요약 생성 가능 | 회사 / 직무 / 지역 / 임금 / D-day 뱃지 |
| **훈련** | 과정명, 기관, 기간, 비용, NCS 분야, 취업률 등 다양한 정보를 압축할 수 있음 | 과정명 / 기관 / 기간 / 비용 / NCS |
| **뉴스·자료** | 본문 발췌 텍스트가 함께 제공되어 LLM 요약이 가장 효과적 | 제목 + 발행일 + 본문 발췌 + 출처 + 태그 |
| **직업·진로** | 가이드 글 형태로 본문 발췌가 있어 주제 파악과 요약이 가능 | 제목 + 발행일 + 본문 발췌 + 출처 + 태그 |

### 요약 미제공 카테고리 (4개)

| 카테고리 | 제외 이유 |
|---|---|
| **신고·신청** | 메뉴 경로(예: `기업지원금>신규채용>고령자 고용지원금 신청서`)와 양식 파일명(예: `[별지 10] 신중년 적합직무 고용 지원 참여 신청서`)만 존재. 본문이나 설명이 전혀 없어 LLM 이 생성하는 요약은 "다양한 신청서가 있습니다" 같은 무의미한 일반화가 됨 |
| **기업** | 기업명, 업종, 주소 정도만 제공. LLM 요약보다 기업 리스트 직접 노출이 더 자연스럽지만, work24 검색 결과 바로 아래에 동일한 리스트가 이미 표시되므로 **중복 제공의 가치가 없음** |
| **자격** | 자격증명과 시행기관(대부분 "고용노동부")만 존재하고, work24 의 키워드 매칭 품질이 낮아 검색어와 무관한 자격증이 섞임 (예: "고용" 검색 → 굴삭기운전기능사). AI 요약이 오히려 **잘못된 신호**를 줄 위험 |
| **기타** | 다른 8개 카테고리에 분류되지 않은 모든 것의 catch-all. 콘텐츠 종류가 통일되어 있지 않고 (프로모션 배너, 잡다한 페이지 등 혼합) 요약 품질을 보장할 수 없음 |


## 카테고리별 요약 방식

카테고리별 **전용 프롬프트**를 사용하여 각 카테고리 데이터 특성에 맞는 요약 생성
*각 요약 카드에는 최상위 결과 URL 포함 (기본적으로 정확도순 정렬, 훈련만 날짜순 정렬)

| 카테고리 | 프롬프트 강조점 | 파서가 추출하는 주요 필드 |
|---|---|---|
| **채용** | 채용 건수 / 대표 직무 / 지역 분포 / **마감 임박(D-7 이내) 건수** | 회사명, 고용형태, 경력, 학력, 임금, 근무지, D-day 뱃지, 마감일 |
| **훈련** | 과정 수 / **국비지원 vs 유료 비율** / 주요 분야 / 평균 훈련기간 | 기관명, 훈련유형, 훈련기간, 비용, 자기부담금, NCS직종/취업률 |
| **정책** | 정책 건수 / **주요 대상자 그룹** / 핵심 지원 내용 1~2개 | 정책명, 지원대상/신청방법 설명 (풍부한 텍스트) |
| **뉴스·자료** | 자료 수 / 주요 주제 / **최근 자료의 핵심 내용** | 제목, 발행일, 본문 발췌, 출처, 주제어 |
| **직업·진로** | 자료 수 / 주요 직업/진로 주제 / **가장 관련성 높은 자료** | 제목, 발행일, 본문 발췌, 출처, 주제어 |

같은 검색어 "고용" 에 대해 카테고리별로 다른 관점의 요약 생성
- **채용**: "현재 5건의 채용 공고. 주요 직무는 통계조사관. 강원도/대전/세종/경북 분포. 마감 임박 1건(D-7 이내)."
- **훈련**: "총 5개 과정. 국비지원 3개, 유료 2개. 주요 분야는 외국인 고용 및 직업 상담. 평균 훈련기간 약 30일."
- **정책**: "상시근로자 5인 이상 50인 미만 사업주가 장애인 근로자를 신규 고용하고 6개월 이상 유지 시 장려금 지원. 주요 대상자는 사업주와 장애인."


## 실행 결과 예시

"고용" 검색 (2026-04-10 기준)

```
검색어: 고용
============================================================

📊 카테고리 카드 (5)

[정책] (summary, 20건)
  고용 관련 정책은 총 3가지를 소개합니다. 장애인 신규 고용 장려금은
  상시근로자 5인 이상 50인 미만 사업주가 신규 장애인 근로자를 6개월 이상
  고용할 경우 지원됩니다. 특별 고용 지원 업종 지정은 사업주 및 단체가
  신청할 수 있으며, 해당 업종에 대한 지원을 받을 수 있도록 합니다.
  ↳ 최상위: 고용 촉진장려금
    https://www.work24.go.kr/cm/c/f/1100/selecSystInfo.do?...

[채용] (summary, 20건)
  채용 건수는 5건으로, 주로 계약직의 통계조사관 모집이 포함되어 있습니다.
  지역은 강원, 대전, 세종, 대구 등으로 다양합니다.
  마감 임박 건수는 3건(D-7 이내)입니다.
  ↳ 최상위: 중부지방 고용 노동청 기간제근로자(통계조사관) 채용
    https://www.work24.go.kr/wk/a/b/1500/empDetailAuthView.do?...

[훈련] (summary, 20건)
  총 5개의 교육 과정이 포함되어 있습니다. 이 중 4개 과정은 국비지원으로
  자기부담금이 0이고, 1개 과정은 유료로 자기부담금이 존재합니다.
  주요 과정 분야는 외국인의 고용, 직업상담사, 간호조무사 자격 취득입니다.
  평균적인 훈련 기간은 약 418일입니다.
  ↳ 최상위: 외국인의 고용 과 VISA 실무
    https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl.do?...

[뉴스·자료] (summary, 18건)
  총 6개의 자료가 검색되었습니다. 주요 주제는 AI 고용 서비스와
  워킹맘&대디 멘토단 모집입니다. 가장 최근 자료는 고용노동부에서
  2025년 12월 8일에 발표한 워킹맘&대디 멘토단 공개 모집으로,
  육아기 자녀를 둔 근로자들이 정책 의견을 수렴할 기회를 제공합니다.
  ↳ 최상위: 고용 AI 4종 공개…좋은 질문하면 기프티콘이 쏟아진다!
    https://www.work24.go.kr/cm/c/b/0130/selectBbttInfo.do?...

[직업·진로] (summary, 20건)
  총 5개의 자료가 검색되었습니다. 주요 직업/진로 관련 주제로는
  고용 변동 요인 분석과 고용 안정성이 있습니다. 가장 관련성 높은
  자료에서는 다양한 직종의 고용 변동 요인을 분석하며, 특히 보건의료,
  디자인, 건설, 기계 및 정보통신 직종에 대한 고용 전망이 다루어졌습니다.
  ↳ 최상위: 직종별 고용 변동 요인 분석
    https://www.wagework.go.kr/pt/z/a/retrieveBoardDtal.do?...

ℹ️  전체 결과 수: 178건
   카테고리별: 신고·신청=20, 정책=20, 채용=20, 기업=20, 훈련=20,
              뉴스·자료=18, 직업·진로=20, 자격=20, 기타=20
```


## 출력 스키마

서비스는 검색어 한 건당 다음 JSON 반환

```json
{
  "query": "AI 직업훈련",
  "categories": [
    {
      "category": "정책",
      "type": "summary",
      "summary": "AI 관련 청년 정책 4건. 주요 대상은 만 34세 이하 미취업자...",
      "top_result": {
        "title": "청년 디지털 일자리 사업",
        "url": "https://www.work24.go.kr/..."
      },
      "result_count": 4
    },
    {
      "category": "채용",
      "type": "summary",
      "summary": "AI 관련 채용공고 12건. 머신러닝 엔지니어 위주, 서울 8건...",
      "top_result": { "title": "...", "url": "..." },
      "result_count": 12
    }
  ],
  "meta": {
    "result_count_total": 178,
    "result_count_by_category": {
      "신고·신청": 20, "정책": 4, "채용": 12, "기업": 8,
      "훈련": 7, "뉴스·자료": 18, "직업·진로": 20, "자격": 20, "기타": 20
    },
    "fetched_at": "2026-04-10T06:42:11+00:00"
  }
}
```

### 필드 설명

| 필드 | 설명 |
|---|---|
| `query` | 사용자가 입력한 검색어 (전후 공백 제거됨) |
| `categories` | **요약 카테고리 카드 배열** (요약 미제공 카테고리는 포함되지 않음) |
| `categories[].category` | 카테고리 이름 |
| `categories[].type` | 항상 `"summary"` |
| `categories[].summary` | LLM 이 생성한 한국어 2~3줄 요약 (200자 이내) |
| `categories[].top_result` | 해당 카테고리의 최상위 결과 `{title, url}`. 결과가 없으면 `null` |
| `categories[].result_count` | 해당 카테고리에서 가져온 결과 건수 |
| `meta.result_count_total` | 전체 결과 건수 (요약 미제공 카테고리 포함) |
| `meta.result_count_by_category` | **모든 9개 카테고리의 건수** (요약 미제공 카테고리도 포함) |
| `meta.fetched_at` | 응답 생성 시각 (UTC ISO 8601) |

## 모델 정책 — 외부 LLM (GPT-4o mini)

요약 대상이 **공개 검색 결과만**이고 개인정보를 포함하지 않음
일자리검색(SVC-1)은 개인정보를 다루므로 별도 에이전트로 분리
본 서비스(SVC-3)는 공개 데이터만 외부 API로 보내는 구조이기에 상용 LLM을 자유롭게 사용 가능

GPT-4o mini 선택 이유
- 짧은 한국어 요약(2~3줄)에 충분한 품질
- 응답 속도 빠름 — 최대 5개 카테고리를 병렬 호출하므로 전체 latency 는 단일 호출 1회 수준 (약 1~2초)
- 토큰 비용 저렴

요약 품질이 좋은 사용 LLM
1. **GPT-4o mini** : 짧은 요약에 최적, 빠른 응답속도, 저렴한 비용
2. Claude 3.5 Haiku : 지시 준수 우수, 2~3줄 길이 제어 정확
3. Gemini 1.5 Flash : 빠르고 저렴, Google 검색 연동 유리

## 설계 결정 배경 — 의도 기반 접근에서 카테고리별 요약으로


실제 구현 과정에서 다음 문제들이 확인되었습니다.

1. **키워드 검색에서는 의도 파악이 본질적으로 어렵습니다.**
work24 의 통합검색은 자연어 질문이 아니라 **키워드 검색**입니다.
사용자가 "고용", "ai", "정책" 같은 단어만 입력하는 환경에서 LLM 이 의도를 정확히 추측하기 어렵습니다.

2. 의도 추측이 틀리면 사용자에게 잘못된 정보를 제공합니다.
LLM 이 1순위로 선정한 카테고리에 실제 결과가 0건인 경우, 요약 카드가 비어버리는 문제가 발생했습니다.


### 어떻게 풀어냈는가

의도 추측 대신, **결과에 대한 요약을 카테고리별로 유의미하게 제공**하는 방식으로 전환

초기 기획의 "관련성 높은 콘텐츠 선별" 은 work24 의 자체 정확도순(RANK) 정렬에 위임하고,
"사용자 의도 기반 요약" 은 카테고리별 전용 프롬프트로 각 카테고리의 특성에 맞는 핵심 정보를 추출·강조하는 방식으로 대체했습니다.

## SVC-1 과의 관계

본 preset 은 그 자체로 컴파일된 LangGraph 서브그래프(`CompiledStateGraph`)이므로,
나중에 SVC-1(일자리검색) 에이전트가 추가될 때 **상위 멀티에이전트 그래프의 한 노드**로 임베드할 수 있습니다.
본 작업 범위에서는 SVC-3 만 단독으로 동작하지만, 합성 가능한 구조로 설계해 두었습니다.

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
uv run python scripts/try_search_summary.py "고용"

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

**왜 노드를 잘게 쪼개지 않았나?** 검색 → 그룹화 → 카드 빌드(요약은 병렬) 흐름은 본질적으로
선형이고 중간에 분기·재시도·HITL 이 필요 없습니다. LangGraph 의 노드 경계는 분기/스트리밍/
체크포인트가 필요할 때 의미가 있는데, 우리 흐름엔 그게 없으므로 노드를 늘리면 state
직렬화·트레이싱 스팬만 더해지고 가독성은 떨어집니다. **단일 worker 노드 + 결정론적 헬퍼
함수 + 카테고리별 병렬 LLM 호출**이 가장 깔끔합니다.

### worker_search_summary 내부 — 5단계 흐름 (Phase 1)

```
state["messages"] (입력)
        │
        ▼ ① _extract_query()
   query 문자열
        │
        ▼
② fetch_work24_search(query)
   HTTP GET work24 통합검색 → BeautifulSoup 파싱
        │
        ▼
   results: list[dict]
        │
        ▼
③ _group_by_category(results)
   카테고리별 dict 로 그룹화 (입력 순서 유지)
        │
        ▼
④ _build_category_cards(query, by_category, summary_input_count)
   ┌──────────────────────────────────────────────────────────┐
   │ for category in _CATEGORY_DISPLAY_ORDER:                 │
   │   if category not in _SUMMARY_CATEGORIES: skip           │
   │   if 결과 0건: skip                                       │
   │   → placeholder + summary_inputs 등록                     │
   │                                                          │
   │ asyncio.gather(*_summarize_for_category(...))            │
   │   → placeholder 채움 (병렬 LLM 호출, 최대 5개 동시)       │
   └──────────────────────────────────────────────────────────┘
        │
        ▼
   cards: list[dict]   (summary 카드만)
        │
        ▼
⑤ payload = {query, categories, meta}
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

SVC-3 의 핵심. 5단계 흐름이 한 함수 안에서 순차 실행되며, summary 카드 LLM 호출만 병렬입니다.

```python
async def worker_search_summary(state: State, **kwargs: Any) -> dict[str, Any]:
    query = _extract_query(state)
    if not query:
        # 빈 query → LLM/HTTP 호출 생략, 빈 payload 즉시 반환
        ...

    search_result_count = _search_result_count()      # SEARCH_RESULT_COUNT (env)
    summary_input_count = _summary_input_count()      # SUMMARY_INPUT_COUNT (env)

    results = await fetch_work24_search(query, list_count=search_result_count)
    by_category = _group_by_category(results)
    cards = await _build_category_cards(query, by_category, summary_input_count)

    payload = {
        "query": query,
        "categories": cards,
        "meta": {
            "result_count_total": len(results),
            "result_count_by_category": {
                cat: len(items) for cat, items in by_category.items()
            },
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

`worker_search_summary()` 함수 자체는 헬퍼 함수들을 순서대로 호출만 하고,
실제 일(HTML 파싱, LLM 호출, 카드 생성 등)은 `_parse_work24_html`,
`_summarize_for_category`, `_build_summary_card` 같은 별도 함수들이 담당합니다.
테스트할 때도 전체를 돌리지 않고 헬퍼 함수 단위로 독립적으로 검증합니다.

#### ① work24 검색 호출 — `fetch_work24_search` ([worker_search_summary.py](src/agents/nodes/worker_search_summary.py))

work24 통합검색 페이지를 그대로 GET 해서 HTML 을 받고 `_parse_work24_html` 에 넘깁니다.

```python
async def fetch_work24_search(
    query: str, *, list_count: int = _DEFAULT_SEARCH_RESULT_COUNT,
) -> list[dict[str, Any]]:
    if not query:
        return []

    params = {
        "topQuerySearchArea": "all",
        "topQueryData": query,
        ...
        "listCount": str(list_count),
        "reportSort": "RANK",       # 신고·신청도 정확도순 (기본은 가나다순)
        "workinfoSort": "RANK",
        "trainingSort": "DATE",     # 훈련만 날짜순 유지 (모집 임박 우선)
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
        return []
    ...
    return _parse_work24_html(html)
```

핵심 디테일:

- **카테고리별 정렬 옵션을 명시.** work24 는 카테고리마다 별도의 sort 파라미터를
  받습니다. 대부분 RANK(정확도순) 이지만 두 가지 예외가 있습니다:
  - `reportSort=RANK` — 신고·신청은 work24 브라우저 기본이 가나다순(TITLE) 인데,
    가나다순 top-N 은 ㄱ/ㄴ/ㄷ 으로 시작하는 항목들일 뿐이라 list 카드가 잘못된
    신호를 주므로 명시적으로 RANK 로 덮어씁니다.
  - `trainingSort=DATE` — 훈련만 의도적으로 날짜순. 사용자에게 가치 있는 정보가
    "지금 신청 가능한 / 모집 임박" 인 과정이지 키워드 정확도가 높은 과정이 아니기
    때문입니다.
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

#### ② HTML 파서 — `_parse_work24_html` ([worker_search_summary.py](src/agents/nodes/worker_search_summary.py))

BeautifulSoup 으로 work24 의 결과 HTML 을 정규화된 dict 리스트로 변환합니다.

```python
def _parse_work24_html(html: str) -> list[dict[str, Any]]:
    if not html:
        return []
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        _log.exception("BeautifulSoup parsing failed")
        return []

    results: list[dict[str, Any]] = []
    for stit in soup.select("div.stit_area"):
        cat_span = stit.select_one("span.t2_sb")
        if not cat_span:
            continue
        category = " ".join(cat_span.get_text(" ", strip=True).split())
        ...
        section = header.find_next_sibling("div", class_="result_view")

        # 카테고리별 전용 파서가 있으면 사용, 없으면 범용 _parse_li
        if category == "신고·신청":
            results.extend(_parse_report_section(section, category))
        elif category == "채용":
            parsed = _parse_recruit_li(li)
        elif category == "훈련":
            parsed = _parse_training_li(li)
        elif category == "정책":
            parsed = _parse_policy_li(li)
        elif category in ("뉴스·자료", "직업·진로"):
            parsed = _parse_news_li(li, category)
        else:
            parsed = _parse_li(li, category)
        ...

    return results
```

work24 의 마크업 구조 ↔ 우리가 추출하는 데이터 매핑:

| HTML 위치 | 추출 대상 |
|---|---|
| `div.stit_area span.t2_sb` | 카테고리 이름 (채용/훈련/...) |
| 카테고리 헤더의 형제 `div.result_view > ul.srch_list_default > li` | 결과 항목들 |
| 의미있는 첫 `<a href>` (javascript:/# 제외) | 결과 URL (상대→절대 변환) |
| `<a>` 텍스트 / `<strong>` fallback | 결과 title |
| `span.item` 들 + `<strong>` | snippet |

파서는 의도적으로 **정규화된 단일 스키마**(`{title, snippet, url, category, meta}`)를
출력합니다. 카테고리마다 채용/훈련/뉴스 등 필드 구조가 다르지만, 그 이질성은
`meta.items` 안의 자유 형식 텍스트 리스트에 담아 LLM 이 직접 해석하도록 위임했습니다.
이렇게 해야 카테고리가 추가되거나 변경돼도 파서·worker 코드를 거의 안 건드려도 됩니다.

부수적으로 **placeholder li 필터링**(`_is_placeholder_title`)을 통해 메뉴 카운트
숫자(`"0"`, `"9"`, `"62,370"`)가 결과로 잡히지 않게 막고 있습니다. work24 가 일부
섹션에서 결과가 없을 때 카운트 숫자만 들어 있는 li 를 렌더링하기 때문입니다.

#### ③ 카테고리 그룹화 — `_group_by_category`

순수 함수 — 파서가 뽑은 단일 결과 리스트를 카테고리별 dict 로 묶습니다. 이후 카드
빌드 단계가 카테고리별로 결과를 빠르게 조회할 수 있도록 하기 위함입니다. 입력 순서
(work24 의 정렬 결과 그대로) 를 그대로 유지합니다.

#### ④ 카드 빌드 — `_build_category_cards`

Phase 1 의 핵심. `_CATEGORY_DISPLAY_ORDER` (UI 탭 순서) 를 따라 카테고리별로 분기하고,
summary type 카테고리만 ``asyncio.gather`` 로 LLM 호출을 병렬 디스패치합니다.

```python
async def _build_category_cards(
    query: str,
    by_category: dict[str, list[dict[str, Any]]],
    summary_input_count: int,
) -> list[dict[str, Any]]:
    summary_inputs: list[tuple[int, str, list[dict[str, Any]]]] = []
    cards: list[dict[str, Any] | None] = []

    for category in _CATEGORY_DISPLAY_ORDER:
        if category not in _SUMMARY_CATEGORIES:
            continue
        items = by_category.get(category, [])
        if not items:
            continue

        selected = items[:summary_input_count]
        summary_inputs.append((len(cards), category, selected))
        cards.append(None)  # placeholder, 병렬 호출 끝나면 채움

    # summary 호출을 병렬 실행
    if summary_inputs:
        summaries = await asyncio.gather(*(
            _summarize_for_category(query, category, selected)
            for _, category, selected in summary_inputs
        ))
        for (idx, category, _), summary_text in zip(summary_inputs, summaries):
            full_items = by_category.get(category, [])
            cards[idx] = _build_summary_card(category, full_items, summary_text)

    return [c for c in cards if c is not None]
```

세 가지 디테일:

1. **결정론적 카드 순서.** `_CATEGORY_DISPLAY_ORDER` 는 UI 탭의 왼쪽→오른쪽 순서를
   그대로 박아놓은 상수이므로 응답이 항상 같은 모양으로 떨어집니다. 프론트엔드가
   카드 위치를 캐싱하기 쉽고, 의도 분류 LLM 같은 동적 신호에 의존하지 않습니다.
2. **병렬 LLM 호출.** summary 카테고리(최대 5개)의 LLM 호출이 동시에 시작되므로
   전체 latency 는 단일 호출 1회 수준 (1~2초). 한 카테고리의 호출이 실패해도
   `_summarize_for_category` 안에서 fallback (top-1 title echo) 으로 잡히므로 전체
   응답이 깨지지 않습니다.
3. **placeholder 패턴.** summary 호출이 병렬로 실행되는 동안 카드 슬롯의 위치를
   `None` 으로 점유해 두고, gather 결과가 돌아오면 같은 인덱스에 채웁니다. 이렇게
   해야 최종 카드 순서가 고정됩니다.

#### ⑤ 카테고리별 요약 — `_summarize_for_category`

선별된 결과(`SUMMARY_INPUT_COUNT` 건, 기본 5)를 JSON 으로 직렬화해서 GPT-4o mini 에
넘기고 한국어 2~3줄을 받습니다. 5개 카테고리 모두 **전용 프롬프트**가 있으며,
`_CATEGORY_PROMPTS` dict 에서 카테고리별로 다른 시스템 프롬프트를 사용합니다.

```python
# 공통 규칙 (모든 카테고리가 공유)
_SUMMARY_RULES = (
    "규칙: (1) 핵심 정보만 담을 것, (2) 과장·추측 금지, 제공된 결과에 근거할 것, "
    "(3) 2~3개 문장으로 총 길이는 200자 이내, (4) 마크다운/특수문자 없이 평문으로."
)

# 카테고리별 전용 프롬프트 (강조점이 다름)
_CATEGORY_PROMPTS: dict[str, str] = {
    "채용": "... 채용 건수, 대표 직무, 지역 분포, 마감 임박(D-7) 강조 ..." + _SUMMARY_RULES,
    "훈련": "... 과정 수, 국비/유료 비율, 주요 분야, 평균 훈련기간 강조 ..." + _SUMMARY_RULES,
    "정책": "... 정책 건수, 대상자 그룹, 핵심 지원 내용 강조 ..." + _SUMMARY_RULES,
    "뉴스·자료": "... 자료 수, 주요 주제, 최근 자료 핵심 내용 강조 ..." + _SUMMARY_RULES,
    "직업·진로": "... 자료 수, 주요 주제, 가장 관련성 높은 자료 강조 ..." + _SUMMARY_RULES,
}

def _summary_system_prompt(category: str) -> str:
    """카테고리별 전용 프롬프트가 있으면 사용, 없으면 generic 프롬프트."""
    if category in _CATEGORY_PROMPTS:
        return _CATEGORY_PROMPTS[category]
    return (
        f"... '{category}' 카테고리에 맞는 핵심 정보를 우선적으로 다루세요. "
        + _SUMMARY_RULES
    )
```

LLM 호출이 실패하면 top-1 결과의 title 을 그대로 echo 합니다. 사용자에게는 항상
최소한 무언가 의미 있는 텍스트가 노출됩니다.

#### ⑥ 출력 직렬화

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
uv run python scripts/try_search_summary.py "고용"
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
    for card in payload["categories"]:
        print(card["category"], card["result_count"])
        print("  요약:", card["summary"])
        print("  최상위 결과:", card["top_result"])
    print(payload["meta"])                 # result_count_total / by_category / fetched_at

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
| `OPENAI_API_KEY` | ✅ | — | summary 카드 LLM 호출에 사용. 없으면 fallback 으로만 동작 |
| `LLM_MODEL` | | `openai:gpt-4o-mini` | summary 카드 요약에 쓰는 모델. `provider:model-id` 형식 |
| `SEARCH_RESULT_COUNT` | | `20` | work24 에서 카테고리당 받아올 결과 개수 (1~100) |
| `SUMMARY_INPUT_COUNT` | | `5` | summary 카드 LLM 에 입력으로 넘길 카테고리당 결과 개수 (1~100) |
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

두 변수는 같은 "결과 개수" 지만 그래프의 다른 단계에 영향을 줍니다.

```
work24 호출
   │
   ▼
results (전체 풀)  ← SEARCH_RESULT_COUNT 가 결정
   │              ── 카테고리당 최대 N개씩 받아옴
   │              ── 9개 카테고리 합쳐 보통 13~40건
   │
   ▼
_group_by_category(results)  → 카테고리별 dict
   │
   ▼
카테고리별 카드 빌드
   │
   ├─ _SUMMARY_CATEGORIES 에 포함된 카테고리만 카드 생성
   │
   └─ 카테고리별로 상위 N건만 선별 → 병렬 LLM 요약
      ↑
      └── 여기서 SUMMARY_INPUT_COUNT 가 카테고리당 LLM 입력 개수 결정
```

| 변수 | 무엇을 결정 | 늘리면 | 줄이면 |
|---|---|---|---|
| `SEARCH_RESULT_COUNT` | work24 에서 카테고리당 받아올 결과 개수 | 카드 풍부, 응답 무거움 | 카드 빈약 |
| `SUMMARY_INPUT_COUNT` | summary 카드 LLM 입력으로 넘길 카테고리당 결과 개수 | 요약 풍부, LLM 토큰·비용·지연 ↑ | 요약 빈약, 토큰 절약 |

선별 동작 (Phase 1): **카테고리별로 입력 순서 그대로 앞에서부터 N건**. work24 의
정렬 결과를 그대로 신뢰합니다 (대부분 RANK 정렬이라 정확도 높은 것이 위에 옴).

> 예: `SUMMARY_INPUT_COUNT=5` 이고 채용 카테고리에 12건의 결과가 있으면, work24 가
> 정렬한 상위 5건이 채용 카드의 LLM 요약 입력으로 들어갑니다. 같은 시점에 훈련
> 카테고리도 자체적으로 상위 5건을 LLM 요약 입력으로 받습니다 (병렬).

검증:
- 1~100 범위의 정수만 허용
- 정수가 아니거나 범위를 벗어나면 그래프 첫 호출 시점에 `_InvalidCountError`
  로 즉시 실패 (운영자가 설정 오류를 즉시 인지하도록)

## 안정성 — 모든 실패 지점에 fallback

본 서비스는 사용자에게 절대 5xx 를 돌려주지 않는다는 원칙을 따릅니다. 모든 실패
지점에 graceful degradation 이 있습니다.

| 실패 지점 | fallback 동작 |
|---|---|
| summary 카드 LLM 실패 (카테고리별) | top-1 결과의 title 을 그대로 echo. 다른 카드는 정상 (각 호출이 독립) |
| work24 fetch 실패 (network/timeout/HTTPError) | 빈 결과 + 경고 로그, 카드 0개로 정상 응답 |
| HTML 파싱 실패 | 동일 (빈 결과 + 경고 로그) |
| 빈 query | LLM/fetch 호출 생략, 빈 payload 즉시 반환 |

각각의 fallback 은 대응되는 단위 테스트가 있어서 회귀가 발생하면 즉시 잡힙니다.

## 테스트 — [tests/test_ai_search_summary.py](tests/test_ai_search_summary.py)

### 전략

I/O 경계(LLM, HTTP)에서만 mock 하고, 순수 함수는 그대로 호출합니다. 실제 LLM 호출이나
HTTP 호출 없이 30개 테스트가 모두 통과합니다.

```bash
uv run pytest tests/test_ai_search_summary.py -v
```

### 테스트 목록 (Phase 1)

| 분류 | 테스트 개수 | 검증 대상 |
|---|---|---|
| **HTML 파서** | 6 | fixture 파싱, 필수 필드, 카테고리 커버리지, URL 절대화, edge case (빈/잘못된/잘린 입력) |
| **카테고리 그룹화** | 2 | `_group_by_category` 입력 순서 유지, 빈 카테고리 skip |
| **카드 빌더** | 3 | summary 카드 모양, top_result 처리, 비-summary 카테고리 제외 검증 |
| **모델 ID 해석** | 5 | LLM_MODEL 환경변수 검증 및 자동 prefix |
| **count 환경변수 해석** | 5 | SEARCH_RESULT_COUNT / SUMMARY_INPUT_COUNT 검증 |
| **summary fallback** | 3 | LLM 실패/빈 selection 처리, 카테고리 인지형 프롬프트 검증 |
| **E2E** | 4 | 카드 고정 순서, 빈 카테고리 skip, 카테고리별 type 매핑, summary 카드 모양, 빈 query 처리 |

총 **30건**, 회귀 0.

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
| `langchain` | `init_chat_model` |
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

- **새 카테고리를 work24 가 추가하면** → `_CATEGORY_DISPLAY_ORDER` 에 순서 추가,
  요약 대상이면 `_SUMMARY_CATEGORIES` 와 `_CATEGORY_PROMPTS` 에도 추가.
  파서는 그대로 두면 됨 (카테고리 이름을 동적으로 인식).
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
