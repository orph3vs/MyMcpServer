"""Score-based risk classifier for legal question triage.

Classifies user questions into LOW/HIGH risk using weighted criteria:
- 개인정보/가명/익명
- 위법/제재
- 감독기관 대응
- 법령 충돌
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class RiskAssessment:
    risk_level: str
    total_score: int
    matched_criteria: Dict[str, List[str]]
    reasons: List[str]


class RiskClassifier:
    """Classifies risk using additive scores and threshold branching."""

    _CRITERIA_WEIGHTS: Dict[str, int] = {
        "privacy": 2,
        "sanction": 3,
        "supervision": 2,
        "legal_conflict": 3,
    }

    _KEYWORDS: Dict[str, Tuple[str, ...]] = {
        "privacy": (
            "개인정보",
            "민감정보",
            "가명정보",
            "익명정보",
            "재식별",
            "주민등록번호",
            "고유식별",
        ),
        "sanction": (
            "위법",
            "불법",
            "제재",
            "과징금",
            "과태료",
            "형사처벌",
            "벌칙",
            "처분",
        ),
        "supervision": (
            "감독기관",
            "조사",
            "점검",
            "시정명령",
            "자료제출",
            "행정지도",
            "소명",
        ),
        "legal_conflict": (
            "법령 충돌",
            "상충",
            "모순",
            "우선 적용",
            "특별법",
            "일반법",
            "해석 충돌",
        ),
    }

    def __init__(self, high_threshold: int = 5) -> None:
        if high_threshold <= 0:
            raise ValueError("high_threshold must be a positive integer")
        self.high_threshold = high_threshold

    def classify(self, question: str) -> RiskAssessment:
        text = (question or "").strip()
        if not text:
            return RiskAssessment(
                risk_level="LOW",
                total_score=0,
                matched_criteria={},
                reasons=["empty_question"],
            )

        total_score = 0
        matched: Dict[str, List[str]] = {}

        for criterion, keywords in self._KEYWORDS.items():
            found = [kw for kw in keywords if kw in text]
            if not found:
                continue

            criterion_score = len(found) * self._CRITERIA_WEIGHTS[criterion]
            total_score += criterion_score
            matched[criterion] = found

        # branch: score-based LOW/HIGH
        risk_level = "HIGH" if total_score >= self.high_threshold else "LOW"

        reasons = []
        for criterion, keywords in matched.items():
            reasons.append(
                f"{criterion}: matched={keywords}, weight={self._CRITERIA_WEIGHTS[criterion]}"
            )

        if not reasons:
            reasons.append("no_high_risk_keywords_matched")

        return RiskAssessment(
            risk_level=risk_level,
            total_score=total_score,
            matched_criteria=matched,
            reasons=reasons,
        )
