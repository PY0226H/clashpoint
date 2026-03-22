import unittest
from unittest.mock import patch

from app.reranker_engine import (
    RerankCandidate,
    RerankRequest,
    RerankResult,
    rerank_with_fallback,
)


class RerankerEngineTests(unittest.TestCase):
    def test_heuristic_rerank_should_prioritize_query_aligned_candidate(self) -> None:
        request = RerankRequest(
            query_text="前排 护甲 版本",
            candidates=[
                RerankCandidate(
                    chunk_id="unrelated",
                    title="足球赛事",
                    content="本周联赛回顾",
                    score=0.9,
                ),
                RerankCandidate(
                    chunk_id="target",
                    title="前排护甲改动",
                    content="版本提升前排抗性",
                    score=0.3,
                ),
            ],
            top_n=2,
            configured_engine="heuristic",
        )
        result = rerank_with_fallback(request)
        self.assertEqual(result.effective_engine, "heuristic")
        self.assertEqual(result.candidates[0].chunk_id, "target")
        self.assertIsNone(result.error_code)

    @patch("app.reranker_engine.BgeCrossEncoderReranker.rerank")
    def test_bge_rerank_should_fallback_when_engine_failed(self, mock_rerank) -> None:
        mock_rerank.side_effect = RuntimeError("model_not_ready")
        request = RerankRequest(
            query_text="tft frontline",
            candidates=[
                RerankCandidate(
                    chunk_id="a",
                    title="A",
                    content="A",
                    score=0.5,
                )
            ],
            top_n=1,
            configured_engine="bge",
        )
        result = rerank_with_fallback(request)
        self.assertEqual(result.configured_engine, "bge")
        self.assertEqual(result.effective_engine, "heuristic")
        self.assertEqual(result.error_code, "rag_rerank_unavailable")
        self.assertIn("model_not_ready", str(result.fallback_reason))

    @patch("app.reranker_engine.BgeCrossEncoderReranker.rerank")
    def test_bge_rerank_should_return_model_result_when_success(self, mock_rerank) -> None:
        mock_rerank.return_value = RerankResult(
            candidates=[
                RerankCandidate(
                    chunk_id="target",
                    title="target",
                    content="target",
                    score=0.97,
                ),
                RerankCandidate(
                    chunk_id="other",
                    title="other",
                    content="other",
                    score=0.21,
                ),
            ],
            configured_engine="bge",
            effective_engine="bge",
            model_name="BAAI/bge-reranker-v2-m3",
            latency_ms=12.4,
            fallback_reason=None,
            error_code=None,
            candidate_before=2,
            candidate_after=2,
        )
        request = RerankRequest(
            query_text="target relevance",
            candidates=[
                RerankCandidate(chunk_id="other", title="other", content="other", score=0.8),
                RerankCandidate(chunk_id="target", title="target", content="target", score=0.2),
            ],
            top_n=2,
            configured_engine="bge",
        )
        result = rerank_with_fallback(request)
        self.assertEqual(result.effective_engine, "bge")
        self.assertEqual(result.candidates[0].chunk_id, "target")
        self.assertIsNone(result.error_code)


if __name__ == "__main__":
    unittest.main()
