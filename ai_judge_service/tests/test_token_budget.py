import unittest
from unittest.mock import patch

from app.token_budget import (
    TokenSegment,
    count_tokens,
    pack_segments_with_budget,
    resolve_encoding,
    truncate_text_to_tokens,
)


class TokenBudgetTests(unittest.TestCase):
    def test_count_tokens_should_support_mixed_language_text(self) -> None:
        text = "hello 世界 this is token 预算 test"
        total = count_tokens("gpt-4.1-mini", text)
        self.assertGreater(total, 0)

    def test_truncate_text_to_tokens_should_clip_to_budget(self) -> None:
        text = "这是一个很长的中文句子 " * 60
        result = truncate_text_to_tokens("gpt-4.1-mini", text, 50)
        self.assertTrue(result.clipped)
        self.assertLessEqual(result.final_tokens, 50)
        self.assertLessEqual(
            count_tokens("gpt-4.1-mini", result.text),
            50,
        )

    @patch("app.token_budget._resolve_tiktoken_encoding", return_value=None)
    def test_resolve_encoding_should_fallback_when_tiktoken_unavailable(
        self, _mock_resolve
    ) -> None:
        resolution = resolve_encoding("unknown-model", fallback_encoding="o200k_base")
        self.assertEqual(resolution.encoding_name, "o200k_base")
        self.assertTrue(resolution.estimated)

    def test_pack_segments_should_prioritize_high_priority_content(self) -> None:
        segments = [
            TokenSegment(segment_id="must_keep", text="关键内容 " * 20, priority=0, required=True),
            TokenSegment(
                segment_id="secondary", text="次要内容 " * 40, priority=10, required=False
            ),
            TokenSegment(segment_id="tail", text="尾部内容 " * 40, priority=20, required=False),
        ]
        packed = pack_segments_with_budget("gpt-4.1-mini", segments, budget=80)
        mapped = packed.segment_map()
        self.assertIn("must_keep", mapped)
        self.assertLessEqual(packed.total_tokens, 80)
        self.assertTrue(packed.clipped)


if __name__ == "__main__":
    unittest.main()
