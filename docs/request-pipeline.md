# Request Pipeline

전체 요청 흐름을 단일 파이프라인으로 구성합니다.

## Flow
User
→ RiskClassifier
→ PromptBuilder
→ LawAPI
→ AgentEngine
→ Validator
→ Scorer
→ Logger
→ Response

## 구현
- `src/request_pipeline.py`
  - `RequestPipeline`
  - `PipelineRequest`
  - `PipelineResponse`
  - `PipelineStageError`

## 에러 처리
- 단계별 오류(`PipelineStageError`) 발생 시:
  - `mode=error:<stage>`로 응답
  - 오류 정보를 `error` 필드에 포함
  - 비용 로그는 항상 SQLite에 기록
- 예기치 못한 오류는 `error:Unhandled`로 처리


## 로컬 실행
- 단일 질의 실행:
  - `python run_local.py "개인정보 제3자 제공 기준" --context "기준시점: 2025-01-01"`
- HTTP 서버 실행:
  - `python -m src.http_server`
  - `GET /health`
  - `POST /ask` (`{"user_query":"...","context":"..."}`)


## 자동 context 조립
- 실제 사용에서는 사용자가 `context`를 직접 넣지 않아도 됩니다.
- `/ask` 요청의 `metadata`(dict), `history`(list)를 서버가 받아 내부 `context`로 자동 조립합니다.
- `context`를 함께 보내면 자동 조립 결과에 포함됩니다.


## 부가 엔드포인트
- `POST /tools/search_law`
- `POST /tools/get_article`
- `POST /tools/get_version`
- `POST /tools/validate_article`
- `GET /logs/recent?limit=10`
