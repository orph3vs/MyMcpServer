# Cost Logging (SQLite)

모든 요청의 비용 로그를 SQLite에 저장합니다.

## 저장 필드
- `request_id`
- `risk_level`
- `mode`
- `tokens_in`
- `tokens_out`
- `cost`
- `latency`
- `score`

## 구현
- `src/cost_logger.py`
  - `CostLogger`
  - `CostLogEntry`

## 기본 DB 경로
- `data/cost_logs.db`

## 파이프라인 연동
- `src/multi_agent_review.py`의 `run_with_logging(...)`에서 실행 후 자동 기록
