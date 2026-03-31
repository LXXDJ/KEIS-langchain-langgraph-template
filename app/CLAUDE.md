# app/ 컨벤션

이 폴더는 서빙 레이어입니다. 에이전트 구현(`agents/`)과 관심사가 분리되어 있습니다.

## 구조

```
app/
├─ run.py           # uvicorn 진입점 (app 인스턴스 export)
└─ utils/
   ├─ server.py     # create_app() FastAPI 팩토리
   ├─ langgraph_loader.py  # langgraph.json 파서
   └─ schema.py     # langgraph.json용 dataclass
```

## 규칙

- `app/` 에서 노드 함수나 State TypedDict를 직접 정의하지 않기
- 에이전트 관련 import는 `agents` 패키지의 공개 API만 사용:
  ```python
  from agents import build_graph, list_presets
  ```
- `langgraph.json`을 파싱하여 서비스 이름, URI 경로 등을 동적으로 결정
- preset별 LangServe 설정이 다를 경우 `server.py`에서 분기 (상수 사용, magic string 금지)

## 엔드포인트 추가

- `server.py`의 `create_app()` 내부에 `@application.get/post` 데코레이터로 추가
- 에이전트 호출 엔드포인트는 LangServe `add_routes()`에 위임
- 커스텀 엔드포인트(health, presets 등)만 직접 정의
