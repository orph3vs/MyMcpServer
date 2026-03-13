import tempfile
import unittest
from pathlib import Path

from src.cost_logger import CostLogger
from src.request_pipeline import PipelineRequest, RequestPipeline


class FakeLawApiOk:
    def search_law(self, query):
        return {"law": [{"name": query, "id": "L1"}]}


class FakeLawApiEmpty:
    def search_law(self, query):
        return {}


class RequestPipelineTests(unittest.TestCase):
    def test_process_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            logger = CostLogger(db_path=str(Path(tmp) / "cost_logs.db"))
            pipeline = RequestPipeline(law_api=FakeLawApiOk(), logger=logger)

            result = pipeline.process(
                PipelineRequest(
                    user_query="개인정보 처리 위법 여부와 조사 대응", context="기준시점: 2025-01-01"
                )
            )

            self.assertIsNone(result.error)
            self.assertTrue(result.answer)
            self.assertIn("law_api_result", result.citations)
            self.assertGreaterEqual(result.score, 0)

            logged = logger.get_by_request_id(result.request_id)
            self.assertIsNotNone(logged)
            self.assertEqual(logged.request_id, result.request_id)

    def test_process_error_path_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            logger = CostLogger(db_path=str(Path(tmp) / "cost_logs.db"))
            pipeline = RequestPipeline(law_api=FakeLawApiEmpty(), logger=logger)

            result = pipeline.process(PipelineRequest(user_query="테스트"))

            self.assertIsNotNone(result.error)
            self.assertEqual(result.error["stage"], "LawAPI")
            self.assertTrue(result.mode.startswith("error:"))

            logged = logger.get_by_request_id(result.request_id)
            self.assertIsNotNone(logged)
            self.assertTrue(logged.mode.startswith("error:"))


if __name__ == "__main__":
    unittest.main()
