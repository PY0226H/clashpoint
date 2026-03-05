import unittest

from app.rag_profiles import resolve_retrieval_profile


class RagProfilesTests(unittest.TestCase):
    def test_resolve_retrieval_profile_should_return_default_for_empty(self) -> None:
        profile, reason = resolve_retrieval_profile("")
        self.assertEqual(profile.name, "hybrid_v1")
        self.assertIsNone(reason)

    def test_resolve_retrieval_profile_should_map_alias(self) -> None:
        profile, reason = resolve_retrieval_profile("hybrid_precision")
        self.assertEqual(profile.name, "hybrid_precision_v1")
        self.assertIsNone(reason)

    def test_resolve_retrieval_profile_should_fallback_for_unknown(self) -> None:
        profile, reason = resolve_retrieval_profile("x-unknown")
        self.assertEqual(profile.name, "hybrid_v1")
        self.assertEqual(reason, "unknown_profile")


if __name__ == "__main__":
    unittest.main()
