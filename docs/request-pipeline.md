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
