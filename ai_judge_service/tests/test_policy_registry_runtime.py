import unittest

from app.applications.policy_registry import build_policy_registry_runtime
from app.settings import Settings


def _build_settings(**overrides: object) -> Settings:
    base = {
        "ai_internal_key": "k",
        "chat_server_base_url": "http://chat",
        "phase_report_path_template": "/r/phase/{case_id}",
        "final_report_path_template": "/r/final/{case_id}",
        "phase_failed_path_template": "/f/phase/{case_id}",
        "final_failed_path_template": "/f/final/{case_id}",
        "callback_timeout_secs": 8.0,
        "process_delay_ms": 0,
        "judge_style_mode": "rational",
        "provider": "mock",
        "openai_api_key": "",
        "openai_model": "gpt-4.1-mini",
        "openai_base_url": "https://api.openai.com/v1",
        "openai_timeout_secs": 25.0,
        "openai_temperature": 0.1,
        "openai_max_retries": 2,
        "openai_fallback_to_mock": True,
        "rag_enabled": True,
        "rag_knowledge_file": "",
        "rag_max_snippets": 4,
        "rag_max_chars_per_snippet": 280,
        "rag_query_message_limit": 80,
        "rag_source_whitelist": ("https://teamfighttactics.leagueoflegends.com/en-us/news",),
        "rag_backend": "file",
        "rag_openai_embedding_model": "text-embedding-3-small",
        "rag_milvus_uri": "",
        "rag_milvus_token": "",
        "rag_milvus_db_name": "",
        "rag_milvus_collection": "",
        "rag_milvus_vector_field": "embedding",
        "rag_milvus_content_field": "content",
        "rag_milvus_title_field": "title",
        "rag_milvus_source_url_field": "source_url",
        "rag_milvus_chunk_id_field": "chunk_id",
        "rag_milvus_tags_field": "tags",
        "rag_milvus_metric_type": "COSINE",
        "rag_milvus_search_limit": 20,
        "stage_agent_max_chunks": 12,
        "reflection_enabled": True,
        "topic_memory_enabled": True,
        "rag_hybrid_enabled": True,
        "rag_rerank_enabled": True,
        "reflection_policy": "winner_mismatch_only",
        "reflection_low_margin_threshold": 3,
        "fault_injection_nodes": (),
        "degrade_max_level": 3,
        "trace_ttl_secs": 86400,
        "idempotency_ttl_secs": 86400,
        "redis_enabled": False,
        "redis_required": False,
        "redis_url": "redis://127.0.0.1:6379/0",
        "redis_pool_size": 20,
        "redis_key_prefix": "ai_judge:v2",
        "db_url": "sqlite+aiosqlite:////tmp/echoisle_ai_judge_service_test.db",
        "db_echo": False,
        "db_pool_size": 10,
        "db_max_overflow": 20,
        "db_auto_create_schema": True,
        "topic_memory_limit": 5,
        "topic_memory_min_evidence_refs": 1,
        "topic_memory_min_rationale_chars": 20,
        "topic_memory_min_quality_score": 0.55,
        "runtime_retry_max_attempts": 2,
        "runtime_retry_backoff_ms": 200,
        "compliance_block_enabled": True,
    }
    base.update(overrides)
    return Settings(**base)


class PolicyRegistryRuntimeTests(unittest.TestCase):
    def test_build_policy_registry_runtime_should_return_builtin_profile(self) -> None:
        runtime = build_policy_registry_runtime(settings=_build_settings())
        self.assertEqual(runtime.default_version, "v3-default")
        profile = runtime.get_profile("v3-default")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.prompt_registry_version, "promptset-v3-default")
        self.assertEqual(profile.tool_registry_version, "toolset-v3-default")
        self.assertEqual(profile.prompt_versions["claimGraphVersion"], "v1-claim-graph-bootstrap")

    def test_build_policy_registry_runtime_should_parse_custom_registry_json(self) -> None:
        runtime = build_policy_registry_runtime(
            settings=_build_settings(
                policy_registry_json=(
                    '{"defaultVersion":"v4-pro","profiles":[{"version":"v4-pro","rubricVersion":"v4",'
                    '"topicDomain":"tft","promptRegistryVersion":"promptset-v4","toolRegistryVersion":"toolset-v4",'
                    '"promptVersions":{"claimGraphVersion":"v2"},"toolIds":["x"],'
                    '"fairnessThresholds":{"drawRateMax":0.22},"metadata":{"status":"active"}}]}'
                )
            )
        )
        self.assertEqual(runtime.default_version, "v4-pro")
        profile = runtime.get_profile("v4-pro")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.rubric_version, "v4")
        self.assertEqual(profile.topic_domain, "tft")
        self.assertEqual(profile.prompt_registry_version, "promptset-v4")
        self.assertEqual(profile.tool_registry_version, "toolset-v4")
        self.assertEqual(profile.prompt_versions["claimGraphVersion"], "v2")
        self.assertEqual(profile.tool_ids, ("x",))

    def test_policy_resolve_should_validate_version_rubric_and_topic(self) -> None:
        runtime = build_policy_registry_runtime(settings=_build_settings())
        unknown = runtime.resolve(
            requested_version="v99",
            rubric_version="v3",
            topic_domain="tft",
        )
        self.assertEqual(unknown.error_code, "unknown_judge_policy_version")

        mismatch = runtime.resolve(
            requested_version="v3-default",
            rubric_version="v2",
            topic_domain="tft",
        )
        self.assertEqual(mismatch.error_code, "judge_policy_rubric_mismatch")

        ok = runtime.resolve(
            requested_version="v3-default",
            rubric_version="v3",
            topic_domain="tft",
        )
        self.assertIsNone(ok.error_code)
        self.assertIsNotNone(ok.profile)


if __name__ == "__main__":
    unittest.main()
