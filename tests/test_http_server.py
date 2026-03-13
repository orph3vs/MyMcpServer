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
        self.assertEqual(req.context, "기준시점: 2025-01-01")
        self.assertEqual(req.request_id, "req-123")
        self.assertIn("user_query", data)

    def test_parse_ask_request_missing_query(self):
        with self.assertRaises(ValueError):
            parse_ask_request(json.dumps({"context": "x"}).encode("utf-8"))

    def test_parse_ask_request_invalid_json(self):
        with self.assertRaises(ValueError):
            parse_ask_request(b"{bad-json")


if __name__ == "__main__":
    unittest.main()
