import unittest

from src.multi_agent_review import MultiAgentReviewPipeline


class MultiAgentReviewPipelineTests(unittest.TestCase):
    def test_run_low_risk_uses_core_agents_only(self):
        pipeline = MultiAgentReviewPipeline()

        result = pipeline.run(
            question="개인정보 보호법 제1조 설명",
            context="기준시점: 2025-01-01",
            risk_level="LOW",
            law_enrichment={"primary_law": {"law_name": "개인정보 보호법"}},
        )

        self.assertIn("StatuteReviewAgent", result.analyses)
        self.assertIn("ComplianceAgent", result.analyses)
        self.assertNotIn("PrecedentReviewAgent", result.analyses)
        self.assertNotIn("RiskReviewerAgent", result.analyses)
        self.assertFalse(result.review_summary["has_conflict"])

    def test_run_high_risk_adds_precedent_and_risk_agents(self):
        pipeline = MultiAgentReviewPipeline()

        result = pipeline.run(
            question="개인정보 보호법 제75조가 위법 판단 기준인지 설명해줘",
            context="기준시점: 2025-01-01",
            risk_level="HIGH",
            law_enrichment={
                "primary_law": {"law_name": "개인정보 보호법"},
                "article": {"article_no": "제75조", "found": True},
                "primary_precedent": {"사건명": "개인정보 보호법 사건", "사건번호": "2025두2345"},
                "used_precedent_query": "개인정보 보호법 제75조 판례",
            },
        )

        self.assertIn("StatuteReviewAgent", result.analyses)
        self.assertIn("ComplianceAgent", result.analyses)
        self.assertIn("PrecedentReviewAgent", result.analyses)
        self.assertIn("RiskReviewerAgent", result.analyses)
        self.assertIn("risk_level: HIGH", result.integrated_review)
        self.assertTrue(result.review_summary["requires_caution"])
        self.assertTrue(result.review_summary["has_precedent"])
        self.assertTrue(result.review_summary["precedent_relevant"])

    def test_run_high_risk_marks_conflict_when_grounding_is_thin(self):
        pipeline = MultiAgentReviewPipeline()

        result = pipeline.run(
            question="위법 여부를 판단해줘",
            context="기준시점: 2025-01-01",
            risk_level="HIGH",
            law_enrichment={"primary_law": {"law_name": "가상 법령"}},
        )

        self.assertTrue(result.review_summary["has_conflict"])
        self.assertTrue(result.review_summary["needs_more_facts"])
        self.assertIn("보수적으로 정리", result.integrated_review)


if __name__ == "__main__":
    unittest.main()
