import json
import unittest

from src.http_server import parse_ask_request


class HttpServerParsingTests(unittest.TestCase):
    def test_parse_ask_request_success(self):
        req, data = parse_ask_request(
            json.dumps(
                {
                    "user_query": "개인정보 제3자 제공 기준",
                    "context": "기준시점: 2025-01-01",
                    "request_id": "req-123",
                }
            ).encode("utf-8")
        )
        self.assertEqual(req.user_query, "개인정보 제3자 제공 기준")
        self.assertIn("기준시점: 2025-01-01", req.context or "")
        self.assertEqual(req.request_id, "req-123")
        self.assertIn("user_query", data)

    def test_parse_ask_request_success_cp949(self):
        payload = {
            "user_query": "개인정보 위탁과 제3자 제공 차이",
            "context": "기준시점: 2025-01-01",
        }
        req, data = parse_ask_request(
            json.dumps(payload, ensure_ascii=False).encode("cp949")
        )
        self.assertEqual(req.user_query, payload["user_query"])
        self.assertIn(payload["context"], req.context or "")
        self.assertEqual(data["context"], payload["context"])

    def test_parse_ask_request_with_metadata_and_history(self):
        req, _ = parse_ask_request(
            json.dumps(
                {
                    "user_query": "질문",
                    "metadata": {"tenant": "acme", "locale": "ko-KR"},
                    "history": ["이전 질문1", "이전 질문2"],
                },
                ensure_ascii=False,
            ).encode("utf-8")
        )
        self.assertIn("[METADATA]", req.context or "")
        self.assertIn("tenant", req.context or "")
        self.assertIn("[RECENT_HISTORY]", req.context or "")

    def test_parse_ask_request_missing_query(self):
        with self.assertRaises(ValueError):
            parse_ask_request(json.dumps({"context": "x"}).encode("utf-8"))

    def test_parse_ask_request_invalid_json(self):
        with self.assertRaises(ValueError):
            parse_ask_request(b"{bad-json")


if __name__ == "__main__":
    unittest.main()
