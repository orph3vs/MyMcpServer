import io
import json
import unittest

from src.mcp_stdio_server import McpServer, _read_message, _write_message
from src.request_pipeline import PipelineResponse


class FakeLawApi:
    def search_law(self, query):
        return {"LawSearch": {"law": [{"법령ID": "011357", "법령명한글": "개인정보 보호법"}], "키워드": query}}

    def get_article(self, law_id, article_no):
        return {"law_id": law_id, "article_no": article_no, "found": True, "article_text": "제1조 본문"}

    def get_version(self, law_id):
        return {"law_id": law_id, "source_target": "law_fallback", "version_fields": {"시행일자": "20251002"}}

    def validate_article(self, law_id, article_no):
        return {"law_id": law_id, "article_no": article_no, "is_valid": True}


class FakePipeline:
    def __init__(self):
        self.law_api = FakeLawApi()

    def process(self, req):
        return PipelineResponse(
            request_id=req.request_id or "req-1",
            risk_level="LOW",
            mode="single_agent",
            answer="테스트 답변",
            citations={"law_search": {"used_search_query": "개인정보 보호법"}},
            score=83.0,
            latency_ms=12.3,
            error=None,
        )


class McpServerTests(unittest.TestCase):
    def setUp(self):
        self.server = McpServer(pipeline=FakePipeline())

    def test_initialize_and_list_tools(self):
        init_response = self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}},
            }
        )

        self.assertEqual(init_response["result"]["protocolVersion"], "2025-03-26")
        list_response = self.server.handle_message(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        tool_names = [tool["name"] for tool in list_response["result"]["tools"]]
        self.assertIn("ask", tool_names)
        self.assertIn("answer_with_citations", tool_names)
        self.assertIn("get_article", tool_names)

    def test_tools_call_ask(self):
        self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}},
            }
        )
        response = self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "ask", "arguments": {"user_query": "개인정보 보호법 제1조 설명"}},
            }
        )

        self.assertFalse(response["result"]["isError"])
        self.assertIn("structuredContent", response["result"])
        payload = response["result"]["structuredContent"]
        self.assertEqual(payload["answer"], "테스트 답변")
        self.assertEqual(payload["citations"]["law_search"]["used_search_query"], "개인정보 보호법")
        self.assertIn("테스트 답변", response["result"]["content"][0]["text"])

    def test_tools_call_answer_with_citations_alias(self):
        self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}},
            }
        )
        response = self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "answer_with_citations", "arguments": {"user_query": "개인정보 보호법 제1조 설명"}},
            }
        )

        self.assertFalse(response["result"]["isError"])
        payload = response["result"]["structuredContent"]
        self.assertEqual(payload["answer"], "테스트 답변")

    def test_tools_call_missing_argument_returns_tool_error(self):
        self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}},
            }
        )
        response = self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "get_article", "arguments": {"law_id": "011357"}},
            }
        )

        self.assertTrue(response["result"]["isError"])
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(payload["error"], "missing_article_no")

    def test_resources_methods_return_empty_lists(self):
        self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}},
            }
        )

        resources_response = self.server.handle_message(
            {"jsonrpc": "2.0", "id": 2, "method": "resources/list", "params": {}}
        )
        templates_response = self.server.handle_message(
            {"jsonrpc": "2.0", "id": 3, "method": "resources/templates/list", "params": {}}
        )

        self.assertEqual(resources_response["result"]["resources"], [])
        self.assertEqual(templates_response["result"]["resourceTemplates"], [])

    def test_transport_roundtrip(self):
        buffer = io.BytesIO()
        _write_message(buffer, {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        buffer.seek(0)
        message = _read_message(buffer)
        self.assertEqual(message["method"], "ping")


if __name__ == "__main__":
    unittest.main()
