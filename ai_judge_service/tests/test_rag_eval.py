import unittest
from types import SimpleNamespace

from app.rag_eval import (
    RagEvalCase,
    build_eval_profile,
    compare_rag_profiles,
    evaluate_rag_profile,
)
from app.rag_retriever import RetrievedContext


def _ctx(chunk_id: str) -> RetrievedContext:
    return RetrievedContext(
        chunk_id=chunk_id,
        title=chunk_id,
        source_url="https://example.com",
        content=chunk_id,
        score=0.8,
    )


class RagEvalTests(unittest.TestCase):
    def test_build_eval_profile_should_fallback_to_default(self) -> None:
        profile = build_eval_profile("unknown-profile")
        self.assertEqual(profile.requested_name, "unknown-profile")
        self.assertEqual(profile.resolved_name, "hybrid_v1")
        self.assertEqual(profile.fallback_reason, "unknown_profile")
        self.assertTrue(profile.retrieve_overrides["hybrid_enabled"])

    def test_evaluate_rag_profile_should_compute_recall_and_mrr(self) -> None:
        cases = [
            RagEvalCase(
                case_id="c1",
                request=SimpleNamespace(case_id="c1"),
                expected_chunk_ids=("a", "b"),
            ),
            RagEvalCase(
                case_id="c2",
                request=SimpleNamespace(case_id="c2"),
                expected_chunk_ids=("c",),
            ),
        ]

        def fake_retrieve(request: object, **_kwargs: object) -> list[RetrievedContext]:
            case_id = getattr(request, "case_id", "")
            if case_id == "c1":
                return [_ctx("x"), _ctx("b"), _ctx("a")]
            return [_ctx("z")]

        summary = evaluate_rag_profile(
            cases=cases,
            profile_name="hybrid_v1",
            base_retrieve_kwargs={"enabled": True, "knowledge_file": "", "max_snippets": 4},
            retrieve_contexts_fn=fake_retrieve,
        )
        self.assertEqual(summary.case_count, 2)
        self.assertAlmostEqual(summary.avg_recall, 0.5)
        self.assertAlmostEqual(summary.mrr, 0.25)
        self.assertAlmostEqual(summary.hit_case_rate, 0.5)
        self.assertAlmostEqual(summary.full_coverage_rate, 0.5)
        self.assertAlmostEqual(summary.avg_hit_count, 1.0)

    def test_compare_rag_profiles_should_rank_by_metrics(self) -> None:
        cases = [
            RagEvalCase(
                case_id="c1",
                request=SimpleNamespace(case_id="c1"),
                expected_chunk_ids=("a",),
            )
        ]

        def fake_retrieve(request: object, **kwargs: object) -> list[RetrievedContext]:
            if kwargs.get("rerank_enabled"):
                return [_ctx("a")]
            return [_ctx("x"), _ctx("a")]

        payload = compare_rag_profiles(
            cases=cases,
            profile_names=["hybrid_v1", "hybrid_recall_v1"],
            base_retrieve_kwargs={"enabled": True, "knowledge_file": "", "max_snippets": 4},
            retrieve_contexts_fn=fake_retrieve,
        )
        self.assertEqual(payload["recommendedProfile"], "hybrid_v1")
        self.assertEqual(payload["ranked"][0]["resolvedProfile"], "hybrid_v1")


if __name__ == "__main__":
    unittest.main()
