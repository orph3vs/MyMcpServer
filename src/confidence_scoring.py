"""Confidence scoring engine (100-point scale).

Scoring criteria and weights:
- evidence_fidelity(근거 충실도): 40
- risk_control(위험통제): 25
- procedural_compliance(절차준수): 20
- reproducibility(재현성): 15
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ConfidenceInput:
    evidence_fidelity: float
    risk_control: float
    procedural_compliance: float
    reproducibility: float


@dataclass(frozen=True)
class ConfidenceResult:
    total_score: float
    breakdown: Dict[str, float]
    max_score: int = 100


class ConfidenceScoringEngine:
    """Automatically calculates confidence score out of 100."""

    WEIGHTS: Dict[str, int] = {
        "evidence_fidelity": 40,
        "risk_control": 25,
        "procedural_compliance": 20,
        "reproducibility": 15,
    }

    def _clamp(self, value: float) -> float:
        if value < 0:
            return 0.0
        if value > 1:
            return 1.0
        return float(value)

    def calculate(self, metrics: ConfidenceInput) -> ConfidenceResult:
        normalized = {
            "evidence_fidelity": self._clamp(metrics.evidence_fidelity),
            "risk_control": self._clamp(metrics.risk_control),
            "procedural_compliance": self._clamp(metrics.procedural_compliance),
            "reproducibility": self._clamp(metrics.reproducibility),
        }

        breakdown = {
            key: round(normalized[key] * weight, 2)
            for key, weight in self.WEIGHTS.items()
        }
        total = round(sum(breakdown.values()), 2)

        return ConfidenceResult(total_score=total, breakdown=breakdown)


def calculate_confidence_score(
    evidence_fidelity: float,
    risk_control: float,
    procedural_compliance: float,
    reproducibility: float,
) -> ConfidenceResult:
    engine = ConfidenceScoringEngine()
    return engine.calculate(
        ConfidenceInput(
            evidence_fidelity=evidence_fidelity,
            risk_control=risk_control,
            procedural_compliance=procedural_compliance,
            reproducibility=reproducibility,
        )
    )
