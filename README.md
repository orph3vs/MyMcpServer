# MyMCPServer

국가법령정보센터 API 기반 MCP 서버 프로젝트입니다.

## 문서 안내
- 전체 구조 설계: `docs/nlic-mcp-architecture.md`
- Multi-Agent Review: `docs/multi-agent-review.md`
- NLIC API Wrapper: `docs/nlic-api-wrapper.md`
- Confidence Scoring: `docs/confidence-scoring.md`

## Prompt 구성
- `config/prompts/manifest.json`: 프롬프트 버전 매니페스트
- `config/prompts/<version>/system_prompt.md`
- `config/prompts/<version>/orchestration_prompt.md`
- `src/prompt_loader.py`: 요청마다 자동 결합하는 로더 모듈
- `src/risk_classifier.py`: 질문 위험도(HIGH/LOW) 점수 기반 분기 모듈
- `src/multi_agent_review.py`: 요약→병렬분석→통합 Multi-Agent Review 파이프라인
- `src/nlic_api_wrapper.py`: 국가법령정보센터 API wrapper(search_law/get_article/get_version/validate_article + cache)
- `src/confidence_scoring.py`: 답변 신뢰도 점수(100점 만점) 자동 계산 엔진

## 진행 방식
- 본 저장소의 상세 설계/정책/플로우는 README가 아닌 `docs/` 하위 문서에서 관리합니다.
- 다음 작업은 사용자께서 전달하는 **단계별 프롬프트**를 기준으로 순차 반영합니다.
