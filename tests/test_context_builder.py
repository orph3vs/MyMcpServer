import unittest

from src.context_builder import build_context


class ContextBuilderTests(unittest.TestCase):
    def test_build_context_none_when_empty(self):
        self.assertIsNone(build_context())

    def test_build_context_from_explicit(self):
        out = build_context(explicit_context="기준시점: 2025-01-01")
        self.assertIn("[EXPLICIT_CONTEXT]", out or "")

    def test_build_context_with_metadata_and_history(self):
        out = build_context(
            metadata={"tenant": "acme", "locale": "ko-KR"},
            history=["q1", "q2", "q3"],
        )
        self.assertIn("[METADATA]", out or "")
        self.assertIn("tenant", out or "")
        self.assertIn("[RECENT_HISTORY]", out or "")


if __name__ == "__main__":
    unittest.main()
