import unittest

from src.nlic_api_wrapper import NlicApiWrapper


class FakeNlicApiWrapper(NlicApiWrapper):
    def __init__(self):
        super().__init__(oc="test_oc", cache_ttl_seconds=300)
        self.calls = []

    def _request(self, params):
        self.calls.append(params)
        target = params.get("target")
        if target == "law" and params.get("query"):
            return {"law": [{"id": "L1", "name": params["query"]}]}
        if target == "law" and params.get("ID") and params.get("JO"):
            return {"조문내용": f"{params['ID']}:{params['JO']}"}
        if target == "law" and params.get("ID"):
            return {"시행일자": "2025-01-01", "공포일자": "2024-12-01"}
        if target == "history":
            return {"versions": [{"id": params.get("ID"), "ver": "2025-01-01"}]}
        return {}


class BlankHistoryFakeNlicApiWrapper(FakeNlicApiWrapper):
    def _request(self, params):
        if params.get("target") == "history":
            return {"raw": "   "}
        return super()._request(params)


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
        self.assertEqual(article["article_text"], "L1:제1조")
        self.assertTrue(validated["is_valid"])

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


if __name__ == "__main__":
    unittest.main()
