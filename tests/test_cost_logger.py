import tempfile
import unittest
from pathlib import Path

from src.cost_logger import CostLogEntry, CostLogger
from src.multi_agent_review import MultiAgentReviewPipeline, RequestMetrics


class CostLoggerTests(unittest.TestCase):
    def test_log_and_get_by_request_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cost_logs.db"
            logger = CostLogger(db_path=str(db_path))
            entry = CostLogEntry(
                request_id="req-1",
                risk_level="HIGH",
                mode="multi_agent",
                tokens_in=120,
                tokens_out=80,
                cost=0.0123,
                latency=210.5,
                score=87.5,
            )
            logger.log_request(entry)

            loaded = logger.get_by_request_id("req-1")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.request_id, "req-1")
            self.assertEqual(loaded.risk_level, "HIGH")

    def test_pipeline_run_with_logging(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cost_logs.db"
            logger = CostLogger(db_path=str(db_path))
            pipeline = MultiAgentReviewPipeline()

            pipeline.run_with_logging(
                question="개인정보 위법성과 감독기관 조사 대응 검토",
                context="기준시점: 2025-01-01",
                request_id="req-2",
                metrics=RequestMetrics(
                    risk_level="HIGH",
                    mode="parallel_review",
                    tokens_in=50,
                    tokens_out=60,
                    cost=0.01,
                    score=90.0,
                ),
                cost_logger=logger,
            )

            loaded = logger.get_by_request_id("req-2")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.mode, "parallel_review")
            self.assertEqual(loaded.tokens_in, 50)
            self.assertGreaterEqual(loaded.latency, 0)


if __name__ == "__main__":
    unittest.main()
