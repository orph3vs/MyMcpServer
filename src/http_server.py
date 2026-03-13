"""Lightweight HTTP entrypoint for RequestPipeline.

Endpoints:
- GET /health
- POST /ask
"""

from __future__ import annotations

import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple

from src.request_pipeline import PipelineRequest, RequestPipeline


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def parse_ask_request(raw_body: bytes) -> Tuple[PipelineRequest, Dict[str, Any]]:
    try:
        data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid_json:{exc}") from exc

    user_query = str(data.get("user_query", "")).strip()
    if not user_query:
        raise ValueError("missing_user_query")

    req = PipelineRequest(
        user_query=user_query,
        context=data.get("context"),
        request_id=data.get("request_id"),
    )
    return req, data


class PipelineHttpHandler(BaseHTTPRequestHandler):
    _pipeline: Optional[RequestPipeline] = None

    @classmethod
    def get_pipeline(cls) -> RequestPipeline:
        if cls._pipeline is None:
            cls._pipeline = RequestPipeline()
        return cls._pipeline

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            _json_response(self, 200, {"status": "ok"})
            return
        _json_response(self, 404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/ask":
            _json_response(self, 404, {"error": "not_found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length)
            req, _ = parse_ask_request(raw_body)
            result = self.get_pipeline().process(req)
            _json_response(self, 200, asdict(result))
        except ValueError as exc:
            _json_response(self, 400, {"error": str(exc)})
        except Exception as exc:  # defensive fallback
            _json_response(self, 500, {"error": f"internal_error:{exc}"})


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), PipelineHttpHandler)
    print(f"[request-pipeline-server] listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
