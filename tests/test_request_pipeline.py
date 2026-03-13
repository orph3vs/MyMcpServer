import tempfile
import unittest
from pathlib import Path

from src.cost_logger import CostLogger
from src.request_pipeline import PipelineRequest, RequestPipeline


class FakeLawApiOk:
    def __init__(self):
        self.search_queries = []
        self.article_calls = []

    def search_law(self, query):
        self.search_queries.append(query)
        return {
            "LawSearch": {
                "law": [
                    {
                        "법령ID": "011357",
                        "법령명한글": "개인정보 보호법",
                        "법령일련번호": "270351",
                    }
                ]
            }
        }

    def get_version(self, law_id):
        return {
            "law_id": law_id,
            "source_target": "law_fallback",
            "version_fields": {"시행일자": "20251002", "공포일자": "20250401", "제개정구분명": "일부개정"},
        }

    def get_article(self, law_id, article_no):
        self.article_calls.append((law_id, article_no))
        titles = {
            "제1조": "목적",
            "제2조": "정의",
            "제34조": "개인정보 유출 통지",
            "제34조의2": "유출 신고",
        }
        title = titles.get(article_no, "일반")
        return {
            "law_id": law_id,
            "article_no": article_no,
            "found": True,
            "matched_via": "service:law",
            "article_text": f"{article_no}({title}) 테스트 조문 본문",
        }


class FakeLawApiEmpty:
    def __init__(self):
        self.search_queries = []

    def search_law(self, query):
        self.search_queries.append(query)
        return {}


class FakeLawApiNeedsNormalizedQuery(FakeLawApiEmpty):
    def get_version(self, law_id):
        return {"law_id": law_id, "version_fields": {"시행일자": "20251002"}}

    def get_article(self, law_id, article_no):
        return {"law_id": law_id, "article_no": article_no, "found": True, "article_text": f"{article_no}(목적) 본문"}

    def search_law(self, query):
        self.search_queries.append(query)
        if query == "개인정보 보호법":
            return {
                "LawSearch": {
                    "law": [
                        {
                            "법령ID": "011357",
                            "법령명한글": "개인정보 보호법",
                            "법령일련번호": "270351",
                        }
                    ]
                }
            }
        return {"LawSearch": {"law": [], "totalCnt": "0"}}


class RequestPipelineTests(unittest.TestCase):
    def test_process_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            logger = CostLogger(db_path=str(Path(tmp) / "cost_logs.db"))
            pipeline = RequestPipeline(law_api=FakeLawApiOk(), logger=logger)

            result = pipeline.process(
                PipelineRequest(
                    user_query="개인정보 처리 위법 여부 조사 대상인지 설명",
                    context="기준시점: 2025-01-01",
                )
            )

            self.assertIsNone(result.error)
            self.assertTrue(result.answer)
            self.assertIn("law_search", result.citations)
            self.assertIn("law_context", result.citations)
            self.assertEqual(result.citations["law_context"]["primary_law"]["law_id"], "011357")
            self.assertNotIn("[통합검토]", result.answer)
            self.assertGreaterEqual(result.score, 0)

            logged = logger.get_by_request_id(result.request_id)
            self.assertIsNotNone(logged)
            self.assertEqual(logged.request_id, result.request_id)

    def test_process_enriches_context_with_article_and_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            logger = CostLogger(db_path=str(Path(tmp) / "cost_logs.db"))
            pipeline = RequestPipeline(law_api=FakeLawApiOk(), logger=logger)

            result = pipeline.process(
                PipelineRequest(
                    user_query="개인정보 보호법 제1조 설명",
                    context="기준시점: 2025-01-01",
                )
            )

            self.assertIsNone(result.error)
            self.assertIn("law_context", result.citations)
            self.assertEqual(result.citations["law_context"]["article"]["article_no"], "제1조")
            self.assertIn("개인정보 보호법 제1조는 목적에 관한 규정입니다.", result.answer)
            self.assertIn("현재 확인한 조문은 다음과 같습니다.", result.answer)
            self.assertIn("쉽게 말하면", result.answer)

    def test_process_uses_normalized_law_search_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            logger = CostLogger(db_path=str(Path(tmp) / "cost_logs.db"))
            law_api = FakeLawApiNeedsNormalizedQuery()
            pipeline = RequestPipeline(law_api=law_api, logger=logger)

            result = pipeline.process(
                PipelineRequest(
                    user_query="개인정보 보호법 제1조 설명",
                    context="기준시점: 2025-01-01",
                )
            )

            self.assertIsNone(result.error)
            self.assertEqual(law_api.search_queries[0], "개인정보 보호법")
            self.assertEqual(result.citations["law_context"]["used_search_query"], "개인정보 보호법")
            self.assertIn("개인정보 보호법", result.citations["law_context"]["search_queries"])
            self.assertEqual(result.citations["law_search"]["used_search_query"], "개인정보 보호법")

    def test_process_fetches_related_articles_for_difference_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            logger = CostLogger(db_path=str(Path(tmp) / "cost_logs.db"))
            law_api = FakeLawApiOk()
            pipeline = RequestPipeline(law_api=law_api, logger=logger)

            result = pipeline.process(
                PipelineRequest(
                    user_query="개인정보 보호법 제1조와 제2조 차이를 설명해줘",
                    context="기준시점: 2025-01-01",
                )
            )

            self.assertIsNone(result.error)
            self.assertEqual(law_api.article_calls, [("011357", "제1조"), ("011357", "제2조")])
            self.assertEqual(result.citations["law_context"]["related_articles"][0]["article_no"], "제2조")
            self.assertIn("[비교 참고 조문]", result.answer)

    def test_process_fetches_related_articles_for_procedure_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            logger = CostLogger(db_path=str(Path(tmp) / "cost_logs.db"))
            law_api = FakeLawApiOk()
            pipeline = RequestPipeline(law_api=law_api, logger=logger)

            result = pipeline.process(
                PipelineRequest(
                    user_query="개인정보 보호법 제34조와 제34조의2 절차를 설명해줘",
                    context="기준시점: 2025-01-01",
                )
            )

            self.assertIsNone(result.error)
            self.assertEqual(
                law_api.article_calls,
                [("011357", "제34조"), ("011357", "제34조의2")],
            )
            self.assertIn("[연관 조문]", result.answer)

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
