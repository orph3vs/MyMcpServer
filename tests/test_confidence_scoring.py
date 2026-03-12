import unittest

from src.confidence_scoring import (
    ConfidenceInput,
    ConfidenceScoringEngine,
    calculate_confidence_score,
)


class ConfidenceScoringTests(unittest.TestCase):
    def test_full_score(self):
        engine = ConfidenceScoringEngine()
        result = engine.calculate(
            ConfidenceInput(
                evidence_fidelity=1,
                risk_control=1,
                procedural_compliance=1,
                reproducibility=1,
            )
        )
        self.assertEqual(result.total_score, 100.0)

    def test_weighted_score(self):
        result = calculate_confidence_score(
            evidence_fidelity=0.5,
            risk_control=0.8,
            procedural_compliance=0.5,
            reproducibility=0.2,
        )
        # 20 + 20 + 10 + 3 = 53
        self.assertEqual(result.total_score, 53.0)
        self.assertEqual(result.breakdown["evidence_fidelity"], 20.0)
        self.assertEqual(result.breakdown["risk_control"], 20.0)

    def test_clamps_out_of_range(self):
        result = calculate_confidence_score(
            evidence_fidelity=3,
            risk_control=-1,
            procedural_compliance=1,
            reproducibility=0,
        )
        # 40 + 0 + 20 + 0 = 60
        self.assertEqual(result.total_score, 60.0)


if __name__ == "__main__":
    unittest.main()
