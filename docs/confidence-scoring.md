# Confidence Scoring Engine

`src/confidence_scoring.py`는 답변 신뢰도 점수를 자동 계산합니다.

## 점수 기준 (100점 만점)
- 근거 충실도(`evidence_fidelity`): 40점
- 위험통제(`risk_control`): 25점
- 절차준수(`procedural_compliance`): 20점
- 재현성(`reproducibility`): 15점

각 입력값은 0.0~1.0 범위를 기대하며, 범위를 벗어나면 자동 보정(clamp)됩니다.

## 결과
- `total_score`: 0~100
- `breakdown`: 항목별 가중 점수

## 사용 예시
```python
from src.confidence_scoring import calculate_confidence_score

result = calculate_confidence_score(
    evidence_fidelity=0.9,
    risk_control=0.8,
    procedural_compliance=0.7,
    reproducibility=1.0,
)
```
