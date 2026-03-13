"""Local runner for RequestPipeline."""

from __future__ import annotations

import argparse
import json

from src.request_pipeline import PipelineRequest, RequestPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RequestPipeline locally")
    parser.add_argument("user_query", help="User query text")
    parser.add_argument("--context", default=None, help="Optional context text")
    parser.add_argument("--request-id", default=None, help="Optional request id")
    args = parser.parse_args()

    pipeline = RequestPipeline()
    result = pipeline.process(
        PipelineRequest(
            user_query=args.user_query,
            context=args.context,
            request_id=args.request_id,
        )
    )
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
