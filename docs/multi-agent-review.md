# Multi-Agent Review Pipeline

`src/multi_agent_review.py`는 다음 구조로 동작합니다.

1. 요약 (`MainAgent`)
2. 병렬 분석 (`LegalAuditorAgent`, `RiskReviewerAgent`, `ComplianceAgent`)
3. 통합 (`MultiAgentReviewPipeline._integrate`)

## 에이전트 구성
- `MainAgent`: 질문+컨텍스트를 요약
- `LegalAuditorAgent`: 법령 근거/조문/시점 명시 여부 점검
- `RiskReviewerAgent`: `RiskClassifier`로 위험도 점수 기반 판정 반영
- `ComplianceAgent`: 금지 표현/컴플라이언스 누락 여부 점검

## 토큰 제한 옵션
`TokenLimitOptions`로 요청별 제한값을 지정할 수 있습니다.
- `summary_max_tokens`
- `agent_output_max_tokens`
- `final_output_max_tokens`

## 사용 예시
```python
from src.multi_agent_review import MultiAgentReviewPipeline, TokenLimitOptions

pipeline = MultiAgentReviewPipeline(
    token_options=TokenLimitOptions(
        summary_max_tokens=120,
        agent_output_max_tokens=150,
        final_output_max_tokens=280,
    )
)

result = pipeline.run(
    question="개인정보 처리 위법성과 감독기관 조사 대응을 검토해줘",
    context="기준시점: 2025-01-01"
)
```

## 비용 로그 연동
- `run_with_logging(...)`를 사용하면 파이프라인 실행 후 SQLite 비용 로그(`CostLogger`)에 자동 저장합니다.
