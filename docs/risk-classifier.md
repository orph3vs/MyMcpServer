# Risk Classifier

질문 문장을 분석해 점수 기반으로 `HIGH`/`LOW` 위험도를 분기합니다.

## 기준(요구사항 반영)
- 개인정보/가명/익명
- 위법/제재
- 감독기관 대응
- 법령 충돌

## 구현 파일
- `src/risk_classifier.py`

## 점수 규칙
- privacy: 키워드 1개당 +2
- sanction: 키워드 1개당 +3
- supervision: 키워드 1개당 +2
- legal_conflict: 키워드 1개당 +3

총점이 `high_threshold` 이상이면 `HIGH`, 미만이면 `LOW`.
기본 임계값(`high_threshold`)은 5.

## 반환 구조
- `risk_level`: `HIGH` | `LOW`
- `total_score`: 누적 점수
- `matched_criteria`: 기준별 매칭 키워드
- `reasons`: 판별 근거 텍스트

## 사용 예시
```python
from src.risk_classifier import RiskClassifier

classifier = RiskClassifier(high_threshold=5)
result = classifier.classify("개인정보 재식별과 과징금 처분 리스크가 있는지")

# result.risk_level -> "HIGH"
# result.total_score -> 10 (예시)
```
