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
- `src/answer_composer.py`
  - 법령 근거 기반 최종 설명형 답변 조립 모듈

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

## 법령 enrichment
- `/ask` 처리 중 `search_law` 결과에서 대표 법령을 1건 선택합니다.
- 대표 법령이 식별되면 `get_version`을 추가 호출해 시행일자/공포일자/제개정구분을 보강합니다.
- 질문에 `제1조`, `제10조의2` 같은 조문 표현이 있으면 `get_article`도 함께 호출합니다.
- 보강된 법령 정보는 내부 `context`에 `[LAW_CONTEXT]` 블록으로 합쳐져 에이전트 입력에 전달됩니다.
- `/ask` 응답은 MCP 소비를 위해 요약된 citation 구조를 반환합니다.
- 최종 답변은 검토 로그가 아니라 설명형 문장으로 조립합니다.
- 조문 본문이 있으면 `법령명 + 조문번호 + 원문 + 쉬운 설명` 순서로 답합니다.
- 조문 본문이 없으면 대표 법령과 시행일자, 추가 확인 필요 사항을 설명형으로 안내합니다.
- 프롬프트 파일의 원칙(근거 없는 문장 금지, 추정 금지, 시점 불명확 시 확인 필요 안내)은 답변 조립 규칙의 제약으로 반영됩니다.
- 답변 조립 규칙은 `AnswerComposer`에 분리되어, 목적조항/정의조항/제재조항 등 유형별 문구를 다르게 처리합니다.
- 응답 `citations`에는 아래 구조가 포함됩니다.
  - `law_search.used_search_query`
  - `law_search.search_hit_count`
  - `law_search.results`
  - `law_context.primary_law`
  - `law_context.version`
  - `law_context.article`
- 원본 API payload가 필요하면 `/tools/search_law`, `/tools/get_article`, `/tools/get_version`을 직접 사용합니다.


## 부가 엔드포인트
- `POST /tools/search_law`
- `POST /tools/get_article`
- `POST /tools/get_version`
- `POST /tools/validate_article`
- `GET /logs/recent?limit=10`
