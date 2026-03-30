# Deep Agents 개요

## Deep Agents란?

Deep Agents는 LangGraph 위에서 동작하는 **batteries-included agent harness**입니다.

쉽게 말하면, 일반적인 에이전트 루프에 다음 기능이 미리 얹혀 있는 형태입니다.

- 작업 계획(planning)
- 파일시스템 기반 컨텍스트 관리
- 서브에이전트 위임
- 긴 대화의 요약
- 장기 메모리 확장
- 사람 승인(human-in-the-loop) 확장

즉, 단순히 "모델 + 툴 몇 개" 수준을 넘어서, **복잡한 멀티스텝 작업을 안정적으로 처리할 수 있는 기본 골격**을 제공합니다.

---

## 언제 Deep Agents를 쓰면 좋은가

다음과 같은 경우에 잘 맞습니다.

### 1. 작업이 길고 단계가 많을 때
예:
- 리서치 후 보고서 작성
- 여러 파일을 읽고 수정하는 작업
- 검색, 정리, 초안 작성이 이어지는 작업

### 2. 컨텍스트가 쉽게 커질 때
예:
- 검색 결과가 많음
- 생성 중간 산출물이 많음
- 파일 여러 개를 읽고 편집해야 함

### 3. 세부 작업을 분리하고 싶을 때
예:
- 조사 전용 subagent
- 코드 분석 전용 subagent
- 문서 작성 전용 subagent

### 4. thread 단위 상태와 장기 메모리가 필요할 때
예:
- 같은 사용자와 여러 번 대화
- 이전 작업 맥락을 재사용
- 대화 간 기억 유지

---

## 기본 생성 방식

Deep Agents의 중심 진입점은 보통 `create_deep_agent()`입니다.

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    tools=[...],
    system_prompt="You are a helpful assistant",
)
```

중요한 점은 이 결과가 단순한 헬퍼 객체가 아니라, **LangGraph 런타임 위에서 동작하는 compiled graph 성격의 실행 단위**라는 점입니다.

그래서 이 프로젝트에서는 이를 사실상 **하나의 agent graph**로 취급하는 것이 자연스럽습니다.

---

## 핵심 기능

## 1. Planning / Task decomposition
Deep Agents는 todo 기반 planning 기능을 내장합니다.

핵심 포인트:
- 복잡한 요청을 여러 단계로 분해
- 현재 진행 중인 작업을 추적
- 계획을 중간에 수정 가능

이 기능은 단순한 "답변 생성"보다, **해야 할 일을 관리하면서 진행하는 에이전트**에 가깝게 만들어 줍니다.

---

## 2. Context management with filesystem
Deep Agents의 큰 장점 중 하나는 파일시스템 도구입니다.

대표 도구:
- `ls`
- `read_file`
- `write_file`
- `edit_file`

이 구조가 중요한 이유:
- 긴 내용을 전부 메시지 히스토리에 넣지 않아도 됨
- 중간 결과를 파일처럼 저장 가능
- 큰 컨텍스트를 외부 저장소로 밀어낼 수 있음
- 모델 컨텍스트 창을 아껴서 더 긴 작업을 수행 가능

즉, 파일시스템은 단순한 I/O 기능이 아니라, **컨텍스트 엔지니어링 장치**입니다.

---

## 3. Pluggable filesystem backend
Deep Agents의 virtual filesystem은 백엔드를 교체할 수 있습니다.

문서상 대표 선택지:
- `StateBackend`: thread 범위의 일시적 저장
- local disk
- LangGraph store 기반 지속 저장
- sandbox backend
- custom backend

이 말은 곧, 같은 agent 구조를 유지한 채 저장 전략만 바꿀 수 있다는 뜻입니다.

예:
- 로컬 개발: state backend
- 운영 환경: durable backend
- 격리 실행: sandbox backend

---

## 4. Subagent spawning
Deep Agents는 서브에이전트를 생성해 세부 작업을 위임할 수 있습니다.

이 기능의 목적은 단순 병렬화보다 **컨텍스트 분리**에 가깝습니다.

장점:
- 메인 agent 컨텍스트 오염 감소
- 세부 조사/분석을 독립적으로 수행
- 역할별 전문 agent 구성 가능

예:
- research-agent
- code-review-agent
- summarizer-agent

문서에서는 이 점을 꼭 강조하는 편이 좋습니다.

> subagent의 핵심 가치는 역할 분할보다도, 메인 컨텍스트를 깨끗하게 유지하는 데 있다.

---

## 5. Long-term memory
Deep Agents는 LangGraph의 memory/store 기능과 연결되어 장기 메모리를 지원할 수 있습니다.

활용 예:
- 사용자 선호 저장
- 작업 이력 저장
- 이전 대화 맥락 재사용

주의할 점:
- 메모리는 편리하지만, 저장 기준과 갱신 정책이 중요함
- 무엇을 기억할지, 언제 버릴지를 정책으로 정해야 함

---

## 6. Summarization
긴 대화가 이어질 때 과거 메시지를 요약해 컨텍스트를 유지합니다.

이 기능은 다음 상황에서 매우 중요합니다.
- 장시간 세션
- tool 결과가 길어지는 작업
- 여러 단계가 이어지는 멀티턴 흐름

요약은 단순한 토큰 절약이 아니라, **오래 가는 agent를 위한 생존 장치**에 가깝습니다.

---

## Deep Agents의 기본 내장 middleware

Deep Agents 문서 기준으로 기본 포함되는 핵심 middleware는 다음과 같습니다.

- `TodoListMiddleware`
- `FilesystemMiddleware`
- `SubAgentMiddleware`
- `SummarizationMiddleware`
- `AnthropicPromptCachingMiddleware`
- `PatchToolCallsMiddleware`

추가 조건이 있을 때 활성화되는 것들:
- `MemoryMiddleware`
- `SkillsMiddleware`
- `HumanInTheLoopMiddleware`

이 프로젝트 문서에서는 이들을 다음처럼 분류하는 것을 권장합니다.

### A. 작업 수행 구조용
- TodoList
- Filesystem
- SubAgent

### B. 안정성/운영용
- Summarization
- PatchToolCalls
- PromptCaching

### C. 확장 기능용
- Memory
- Skills
- HumanInTheLoop

이렇게 나누면 독자가 "무엇이 필수 골격이고, 무엇이 운영 보강이며, 무엇이 옵션 확장인지" 빠르게 이해할 수 있습니다.

---

## Deep Agents를 템플릿에서 어떻게 다루면 좋은가

이 프로젝트에서는 Deep Agents를 다음 방식으로 다루는 것이 좋습니다.

### 1. 최소 템플릿은 `create_deep_agent()` 기반으로 시작
초기 진입 장벽이 낮습니다.

### 2. graph 중심 구조를 유지
최종 결과물은 graph/runnable 단위라는 관점을 유지합니다.

### 3. 미들웨어와 툴을 분리된 파일로 관리
- `tools.py`
- `middleware.py`
- `prompts.py`
- `graph.py`

### 4. 서빙은 별도 계층으로 분리
LangServe는 `serve/` 아래에서 다루고, graph 구현과 분리합니다.

---

## 템플릿 문서에 넣으면 좋은 핵심 문장

다음 문장은 한국어 문서 전반에서 반복 사용하기 좋습니다.

> Deep Agents는 LangGraph 위에 planning, filesystem, subagent, memory 같은 실전 기능을 기본 탑재한 agent harness다.

> 이 템플릿에서 하나의 agent는 보통 하나의 LangGraph graph로 구현되며, 필요 시 LangServe를 통해 외부 API로 서빙된다.

> Deep Agents의 핵심 가치는 단순한 tool calling이 아니라, 긴 작업을 계획하고, 외부 저장소를 활용해 컨텍스트를 관리하며, subagent로 세부 작업을 분리할 수 있다는 점에 있다.
