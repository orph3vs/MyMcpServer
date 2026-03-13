import unittest

from src.nlic_api_wrapper import NlicApiWrapper


class FakeNlicApiWrapper(NlicApiWrapper):
    def __init__(self):
        super().__init__(oc="test_oc", cache_ttl_seconds=300)
        self.calls = []

    def _request(self, params, endpoint_url=None):
        self.calls.append({"params": params, "endpoint_url": endpoint_url})
        target = params.get("target")

        if target == "law" and params.get("query"):
            return {"law": [{"id": "L1", "name": params["query"]}]}

        if target == "law" and params.get("ID") and not params.get("JO"):
            return {
                "LawSearch": {
                    "law": {
                        "법령일련번호": "270351",
                        "시행일자": "2025-01-01",
                        "공포일자": "2024-12-01",
                        "제개정구분명": "일부개정",
                    }
                }
            }

        if endpoint_url == self.service_url and params.get("MST") and params.get("JO") and target in ("law", "jo"):
            if params.get("JO") == "제1조":
                return {
                    "조문": {
                        "조문단위": [
                            {
                                "조문번호": "제1조",
                                "조문내용": "제1조(목적) 이 법은 개인정보의 처리 및 보호에 관한 사항을 정한다.",
                            }
                        ]
                    }
                }
            return {"raw": "   "}

        # noisy summary-like payload (contains unrelated `content`)
        if params.get("ID") and params.get("JO"):
            return {
                "법령": {
                    "기본정보": {
                        "소관부처": {"content": "개인정보보호위원회"}
                    }
                }
            }

        if target == "history":
            return {"versions": [{"id": params.get("ID"), "ver": "2025-01-01"}]}

        return {}


class BlankHistoryFakeNlicApiWrapper(FakeNlicApiWrapper):
    def _request(self, params, endpoint_url=None):
        if params.get("target") == "history":
            return {"raw": "   "}
        return super()._request(params, endpoint_url=endpoint_url)


class NlicApiWrapperTests(unittest.TestCase):
    def test_search_law_and_cache(self):
        api = FakeNlicApiWrapper()
        a = api.search_law("개인정보보호법")
        b = api.search_law("개인정보보호법")

        self.assertEqual(a, b)
        self.assertEqual(len(api.calls), 1)

    def test_get_article_and_validate_article(self):
        api = FakeNlicApiWrapper()
        article = api.get_article("L1", "제1조")
        validated = api.validate_article("L1", "제1조")

        self.assertEqual(article["law_id"], "L1")
        self.assertEqual(article["article_no"], "제1조")
        self.assertTrue(article["found"])
        self.assertIn("제1조(목적)", article["article_text"])
        self.assertTrue(article["matched_via"])
        self.assertGreater(len(article["attempted_queries"]), 0)
        self.assertTrue(validated["is_valid"])

    def test_get_article_does_not_pick_unrelated_content_field(self):
        api = FakeNlicApiWrapper()
        article = api.get_article("L1", "제999조")
        self.assertFalse(article["found"])
        self.assertIsNone(article["article_text"])

    def test_get_version(self):
        api = FakeNlicApiWrapper()
        versions = api.get_version("L1")
        self.assertEqual(versions["source_target"], "history")
        self.assertEqual(versions["data"]["versions"][0]["id"], "L1")

    def test_get_version_falls_back_when_history_is_blank(self):
        api = BlankHistoryFakeNlicApiWrapper()
        versions = api.get_version("L1")

        self.assertEqual(versions["source_target"], "law_fallback")
        self.assertEqual(versions["version_fields"]["시행일자"], "2025-01-01")
        self.assertEqual(versions["version_fields"]["공포일자"], "2024-12-01")
        self.assertEqual(versions["version_fields"]["제개정구분명"], "일부개정")


if __name__ == "__main__":
    unittest.main()
