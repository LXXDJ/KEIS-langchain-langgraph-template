# 미들웨어 가이드

## 왜 미들웨어가 중요한가

LangChain / Deep Agents에서 미들웨어는 단순 부가기능이 아니라, **운영 정책을 코드로 선언하는 레이어**입니다.

실무에서는 agent 품질이 모델 성능만으로 결정되지 않습니다.
오히려 다음 요소가 훨씬 중요할 때가 많습니다.

- 호출 실패 시 어떻게 복구할지
- tool 남용을 어떻게 막을지
- 긴 대화를 어떻게 유지할지
- 사람이 언제 개입할지
- 민감정보를 어떻게 처리할지

이런 정책이 대부분 미들웨어에 들어갑니다.

---

## Deep Agents 기본 포함 미들웨어

Deep Agents 문서 기준 기본 내장 항목:

- `TodoListMiddleware`
- `FilesystemMiddleware`
- `SubAgentMiddleware`
- `SummarizationMiddleware`
- `AnthropicPromptCachingMiddleware`
- `PatchToolCallsMiddleware`

옵션에 따라 추가:
- `MemoryMiddleware`
- `SkillsMiddleware`
- `HumanInTheLoopMiddleware`

---

## 권장 분류

## 1. 구조적 기능 미들웨어
에이전트의 작동 방식 자체를 만든다.

### TodoListMiddleware
역할:
- 할 일 목록 관리
- 멀티스텝 작업 계획
- 현재 진행 상황 추적

적합한 경우:
- 긴 작업
- 순차 처리 작업
- 보고서 작성, 조사, 정리 작업

### FilesystemMiddleware
역할:
- 파일 읽기/쓰기/편집
- 컨텍스트 외부화
- 중간 산출물 저장

적합한 경우:
- 긴 문서 생성
- 검색 결과 정리
- 여러 파일 편집

### SubAgentMiddleware
역할:
- 세부 작업 위임
- 컨텍스트 분리
- 역할별 하위 agent 운용

적합한 경우:
- 조사와 작성의 분리
- 코드 분석과 수정 분리
- 고비용 세부 작업 격리

---

## 2. 운영 안정성 미들웨어
장기 실행과 복구, 비용 제어를 담당한다.

### SummarizationMiddleware
역할:
- 긴 히스토리 요약
- 최근 메시지 유지
- 토큰 초과 방지

추천 이유:
- 장기 대화에서는 거의 필수에 가깝습니다.

설정 관점:
- 언제 요약할지: `trigger`
- 얼마나 남길지: `keep`
- 어떤 모델로 요약할지: `model`

예시:

```python
from agents.middlewares import create_summarization_middleware

middleware = [
    create_summarization_middleware(
        model="openai:gpt-4.1-mini",
        trigger=("tokens", 4000),
        keep=("messages", 20),
    )
]
```

### PatchToolCallsMiddleware
역할:
- 중단/취소된 tool call로 인해 메시지 히스토리가 어긋나는 상황을 자동 보정

추천 이유:
- tool 기반 agent는 예상외의 인터럽트에 취약할 수 있으므로 기본 보정 장치가 중요합니다.

### AnthropicPromptCachingMiddleware
역할:
- Anthropic 계열 모델에서 반복 프롬프트 처리 비용 감소

추천 이유:
- 같은 컨텍스트를 자주 재사용하는 긴 세션에서 효율 향상 가능

---

## 3. 확장/제어 미들웨어
운영 요구사항에 맞춰 안전장치를 추가한다.

### HumanInTheLoopMiddleware
역할:
- tool 실행 전 승인/수정/거부

적합한 경우:
- 외부 API 쓰기
- 이메일 발송
- 금전/데이터 변경
- 민감 작업

주의:
- checkpointer가 필요합니다.

### MemoryMiddleware
역할:
- thread 간 기억 유지
- 이전 대화 맥락 재사용

적합한 경우:
- 사용자 맞춤형 agent
- 반복 작업 환경

### SkillsMiddleware
역할:
- 재사용 가능한 스킬 로드
- 프로젝트 특화 능력 확장

적합한 경우:
- 도메인별 작업 패턴이 반복될 때

---

## LangChain의 추가 prebuilt middleware

Deep Agents 외에도 LangChain은 여러 prebuilt middleware를 제공합니다.
문서 기준으로 특히 템플릿에 유용한 것은 다음입니다.

### ModelCallLimitMiddleware
역할:
- 모델 호출 횟수 제한
- 무한 루프/비용 폭주 방지

언제 넣나:
- 운영 환경 거의 전반
- 비용 한도가 분명할 때

### ToolCallLimitMiddleware
역할:
- tool 호출 횟수 제한
- 특정 툴 남용 방지

언제 넣나:
- 검색 API 비용이 클 때
- 스크래핑/DB 호출을 제한해야 할 때

### ModelFallbackMiddleware
역할:
- 기본 모델 실패 시 대체 모델 사용

언제 넣나:
- 안정성이 중요한 운영 서비스
- provider 장애 대비 필요 시

### PIIMiddleware
역할:
- 개인정보 탐지 및 mask/redact/block 처리

언제 넣나:
- 이메일, 전화번호, 카드정보 등 민감정보가 오갈 수 있을 때

---

## 템플릿에서 추천하는 기본 정책

문서 템플릿 기준으로는 아래 3단계 구성이 좋습니다.

### Level 1. Minimal
- Deep Agents 기본 제공 미들웨어만 사용
- 학습용 / 로컬 실험용

### Level 2. Practical
- 기본 제공 + `ToolCallLimitMiddleware`
- 기본 제공 + `ModelCallLimitMiddleware`
- 기본 제공 + 필요 시 `ModelFallbackMiddleware`

실서비스 직전 기본값으로 적합합니다.

### Level 3. Production
- Practical 구성 포함
- `HumanInTheLoopMiddleware`
- `PIIMiddleware`
- memory/checkpoint/persistence 구성
- tracing / observability 추가

---

## 문서화 팁

미들웨어를 소개할 때는 API 나열보다 아래 형식이 더 실용적입니다.

- 무엇을 해결하는가
- 언제 켜야 하는가
- 어떤 비용/부작용이 있는가
- 최소 예제는 무엇인가

예를 들어:

### SummarizationMiddleware
- 해결 문제: 긴 대화로 인한 컨텍스트 초과
- 켜는 시점: 멀티턴/장기 세션
- 비용: 추가 모델 호출 발생
- 권장도: 높음

이 형식으로 문서를 통일하면 실무자가 훨씬 빨리 판단할 수 있습니다.

---

## 템플릿 관점의 핵심 메시지

- 미들웨어는 옵션 모음이 아니라 운영 정책 계층이다.
- Deep Agents는 이미 강한 기본값을 제공한다.
- 실제 서비스에서는 limit / fallback / approval / pii 정책을 추가로 설계해야 한다.
- 좋은 agent 템플릿은 모델 선택보다 미들웨어 설계가 더 중요할 때가 많다.
