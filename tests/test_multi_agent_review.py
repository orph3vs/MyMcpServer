import unittest

from src.multi_agent_review import MultiAgentReviewPipeline, TokenLimitOptions


class MultiAgentReviewPipelineTests(unittest.TestCase):
    def test_pipeline_runs_with_all_agents(self):
        pipeline = MultiAgentReviewPipeline()
        result = pipeline.run(
            question="개인정보 위법 과징금 조사 대응과 법령 충돌 여부를 검토해줘",
            context="기준시점: 2025-01-01",
        )

        self.assertTrue(result.summary)
        self.assertIn("LegalAuditorAgent", result.analyses)
        self.assertIn("RiskReviewerAgent", result.analyses)
        self.assertIn("ComplianceAgent", result.analyses)
        self.assertIn("[통합검토]", result.integrated_review)

    def test_token_limit_applies(self):
        pipeline = MultiAgentReviewPipeline(
            token_options=TokenLimitOptions(
                summary_max_tokens=5,
                agent_output_max_tokens=7,
                final_output_max_tokens=20,
            )
        )
        long_question = " ".join(["개인정보"] * 100)
        result = pipeline.run(question=long_question)

        self.assertLessEqual(len(result.summary.split()), 5)
        for content in result.analyses.values():
            self.assertLessEqual(len(content.split()), 7)
        self.assertLessEqual(len(result.integrated_review.split()), 20)


if __name__ == "__main__":
    unittest.main()
