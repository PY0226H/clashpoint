import os
import unittest
from unittest.mock import patch

from app.runtime_policy import PROVIDER_MOCK, PROVIDER_OPENAI
from app.settings import (
    build_callback_client_config,
    build_dispatch_runtime_config,
    load_settings,
    validate_for_runtime_env,
)


class SettingsTests(unittest.TestCase):
    def test_load_settings_should_use_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings()

        self.assertEqual(settings.provider, PROVIDER_OPENAI)
        self.assertEqual(settings.ai_internal_key, "dev-ai-internal-key")
        self.assertEqual(settings.chat_server_base_url, "http://127.0.0.1:6688")
        self.assertEqual(settings.openai_base_url, "https://api.openai.com/v1")
        self.assertFalse(settings.openai_fallback_to_mock)
        self.assertTrue(settings.rag_enabled)
        self.assertEqual(
            settings.rag_source_whitelist,
            ("https://teamfighttactics.leagueoflegends.com/en-us/news",),
        )
        self.assertEqual(settings.stage_agent_max_chunks, 12)
        self.assertTrue(settings.reflection_enabled)
        self.assertTrue(settings.topic_memory_enabled)
        self.assertTrue(settings.rag_hybrid_enabled)
        self.assertTrue(settings.rag_rerank_enabled)
        self.assertEqual(settings.rag_lexical_engine, "bm25")
        self.assertTrue(settings.rag_bm25_use_disk_cache)
        self.assertTrue(settings.rag_bm25_fallback_to_simple)
        self.assertIn(".cache/bm25", settings.rag_bm25_cache_dir)
        self.assertEqual(settings.rag_rerank_engine, "bge")
        self.assertEqual(settings.rag_rerank_model, "BAAI/bge-reranker-v2-m3")
        self.assertEqual(settings.rag_rerank_batch_size, 16)
        self.assertEqual(settings.rag_rerank_candidate_cap, 50)
        self.assertEqual(settings.rag_rerank_timeout_ms, 12000)
        self.assertEqual(settings.rag_rerank_device, "cpu")
        self.assertEqual(settings.reflection_policy, "winner_mismatch_only")
        self.assertEqual(settings.reflection_low_margin_threshold, 3)
        self.assertEqual(settings.fault_injection_nodes, ())
        self.assertEqual(settings.degrade_max_level, 3)
        self.assertEqual(settings.trace_ttl_secs, 86400)
        self.assertEqual(settings.idempotency_ttl_secs, 86400)
        self.assertFalse(settings.redis_enabled)
        self.assertFalse(settings.redis_required)
        self.assertEqual(settings.redis_url, "redis://127.0.0.1:6379/0")
        self.assertEqual(settings.redis_pool_size, 20)
        self.assertEqual(settings.redis_key_prefix, "ai_judge:v2")
        self.assertEqual(settings.topic_memory_limit, 5)
        self.assertEqual(settings.topic_memory_min_evidence_refs, 1)
        self.assertEqual(settings.topic_memory_min_rationale_chars, 20)
        self.assertEqual(settings.topic_memory_min_quality_score, 0.55)
        self.assertEqual(settings.tokenizer_fallback_encoding, "o200k_base")
        self.assertEqual(settings.phase_prompt_max_tokens, 3200)
        self.assertEqual(settings.agent2_prompt_max_tokens, 3600)
        self.assertEqual(settings.rag_query_max_tokens, 1600)
        self.assertEqual(settings.rag_snippet_max_tokens, 180)
        self.assertEqual(settings.embed_input_max_tokens, 2000)
        self.assertEqual(settings.runtime_retry_max_attempts, 2)
        self.assertEqual(settings.runtime_retry_backoff_ms, 200)
        self.assertTrue(settings.compliance_block_enabled)

    def test_load_settings_should_apply_env_overrides(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_JUDGE_PROVIDER": "OPENAI",
                "AI_JUDGE_INTERNAL_KEY": "k1",
                "CHAT_SERVER_BASE_URL": "https://chat.example.com",
                "CHAT_SERVER_REPORT_PATH_TEMPLATE": "/r/{job_id}",
                "CHAT_SERVER_FAILED_PATH_TEMPLATE": "/f/{job_id}",
                "CALLBACK_TIMEOUT_SECONDS": "15.5",
                "JUDGE_PROCESS_DELAY_MS": "300",
                "JUDGE_STYLE_MODE": "entertaining",
                "OPENAI_API_KEY": "sk-xx",
                "AI_JUDGE_OPENAI_MODEL": "gpt-x",
                "AI_JUDGE_OPENAI_BASE_URL": "https://api.openai.com/v1/",
                "AI_JUDGE_OPENAI_TIMEOUT_SECONDS": "40",
                "AI_JUDGE_OPENAI_TEMPERATURE": "0.35",
                "AI_JUDGE_OPENAI_MAX_RETRIES": "5",
                "AI_JUDGE_OPENAI_FALLBACK_TO_MOCK": "true",
                "AI_JUDGE_RAG_ENABLED": "0",
                "AI_JUDGE_RAG_KNOWLEDGE_FILE": "/tmp/kb.json",
                "AI_JUDGE_RAG_MAX_SNIPPETS": "8",
                "AI_JUDGE_RAG_MAX_CHARS_PER_SNIPPET": "500",
                "AI_JUDGE_RAG_QUERY_MESSAGE_LIMIT": "120",
                "AI_JUDGE_RAG_SOURCE_WHITELIST": "https://a.com/news/ , https://a.com/news , https://b.com/path",
                "AI_JUDGE_RAG_BACKEND": "milvus",
                "AI_JUDGE_RAG_OPENAI_EMBEDDING_MODEL": "text-embedding-3-large",
                "AI_JUDGE_RAG_MILVUS_URI": "http://milvus:19530",
                "AI_JUDGE_RAG_MILVUS_TOKEN": "t",
                "AI_JUDGE_RAG_MILVUS_DB_NAME": "db1",
                "AI_JUDGE_RAG_MILVUS_COLLECTION": "col1",
                "AI_JUDGE_RAG_MILVUS_VECTOR_FIELD": "vec",
                "AI_JUDGE_RAG_MILVUS_CONTENT_FIELD": "body",
                "AI_JUDGE_RAG_MILVUS_TITLE_FIELD": "title2",
                "AI_JUDGE_RAG_MILVUS_SOURCE_URL_FIELD": "src",
                "AI_JUDGE_RAG_MILVUS_CHUNK_ID_FIELD": "cid",
                "AI_JUDGE_RAG_MILVUS_TAGS_FIELD": "tags2",
                "AI_JUDGE_RAG_MILVUS_METRIC_TYPE": "IP",
                "AI_JUDGE_RAG_MILVUS_SEARCH_LIMIT": "33",
                "AI_JUDGE_STAGE_AGENT_MAX_CHUNKS": "20",
                "AI_JUDGE_REFLECTION_ENABLED": "false",
                "AI_JUDGE_TOPIC_MEMORY_ENABLED": "false",
                "AI_JUDGE_RAG_HYBRID_ENABLED": "false",
                "AI_JUDGE_RAG_RERANK_ENABLED": "false",
                "AI_JUDGE_RAG_LEXICAL_ENGINE": "bm25",
                "AI_JUDGE_RAG_BM25_CACHE_DIR": "/tmp/bm25-cache",
                "AI_JUDGE_RAG_BM25_USE_DISK_CACHE": "false",
                "AI_JUDGE_RAG_BM25_FALLBACK_TO_SIMPLE": "false",
                "AI_JUDGE_RAG_RERANK_ENGINE": "heuristic",
                "AI_JUDGE_RAG_RERANK_MODEL": "BAAI/bge-reranker-v2-m3",
                "AI_JUDGE_RAG_RERANK_BATCH_SIZE": "8",
                "AI_JUDGE_RAG_RERANK_CANDIDATE_CAP": "40",
                "AI_JUDGE_RAG_RERANK_TIMEOUT_MS": "5000",
                "AI_JUDGE_RAG_RERANK_DEVICE": "cuda",
                "AI_JUDGE_REFLECTION_POLICY": "winner_mismatch_or_low_margin",
                "AI_JUDGE_REFLECTION_LOW_MARGIN_THRESHOLD": "6",
                "AI_JUDGE_FAULT_INJECTION_NODES": "final_pass_1, display",
                "AI_JUDGE_DEGRADE_MAX_LEVEL": "2",
                "AI_JUDGE_TRACE_TTL_SECS": "600",
                "AI_JUDGE_IDEMPOTENCY_TTL_SECS": "900",
                "AI_JUDGE_REDIS_ENABLED": "true",
                "AI_JUDGE_REDIS_REQUIRED": "true",
                "AI_JUDGE_REDIS_URL": "redis://redis:6379/4",
                "AI_JUDGE_REDIS_POOL_SIZE": "32",
                "AI_JUDGE_REDIS_KEY_PREFIX": "ai_judge:v2:test",
                "AI_JUDGE_TOPIC_MEMORY_LIMIT": "7",
                "AI_JUDGE_TOPIC_MEMORY_MIN_EVIDENCE_REFS": "2",
                "AI_JUDGE_TOPIC_MEMORY_MIN_RATIONALE_CHARS": "60",
                "AI_JUDGE_TOPIC_MEMORY_MIN_QUALITY_SCORE": "0.7",
                "AI_JUDGE_TOKENIZER_FALLBACK_ENCODING": "cl100k_base",
                "AI_JUDGE_PHASE_PROMPT_MAX_TOKENS": "4096",
                "AI_JUDGE_AGENT2_PROMPT_MAX_TOKENS": "5000",
                "AI_JUDGE_RAG_QUERY_MAX_TOKENS": "1200",
                "AI_JUDGE_RAG_SNIPPET_MAX_TOKENS": "220",
                "AI_JUDGE_EMBED_INPUT_MAX_TOKENS": "1800",
                "AI_JUDGE_RUNTIME_RETRY_MAX_ATTEMPTS": "4",
                "AI_JUDGE_RUNTIME_RETRY_BACKOFF_MS": "500",
                "AI_JUDGE_COMPLIANCE_BLOCK_ENABLED": "false",
            },
            clear=True,
        ):
            settings = load_settings()

        self.assertEqual(settings.provider, PROVIDER_OPENAI)
        self.assertEqual(settings.ai_internal_key, "k1")
        self.assertEqual(settings.chat_server_base_url, "https://chat.example.com")
        self.assertEqual(settings.report_path_template, "/r/{job_id}")
        self.assertEqual(settings.failed_path_template, "/f/{job_id}")
        self.assertEqual(settings.callback_timeout_secs, 15.5)
        self.assertEqual(settings.process_delay_ms, 300)
        self.assertEqual(settings.judge_style_mode, "entertaining")
        self.assertEqual(settings.openai_api_key, "sk-xx")
        self.assertEqual(settings.openai_model, "gpt-x")
        self.assertEqual(settings.openai_base_url, "https://api.openai.com/v1")
        self.assertEqual(settings.openai_timeout_secs, 40.0)
        self.assertEqual(settings.openai_temperature, 0.35)
        self.assertEqual(settings.openai_max_retries, 5)
        self.assertTrue(settings.openai_fallback_to_mock)
        self.assertFalse(settings.rag_enabled)
        self.assertEqual(settings.rag_knowledge_file, "/tmp/kb.json")
        self.assertEqual(settings.rag_max_snippets, 8)
        self.assertEqual(settings.rag_max_chars_per_snippet, 500)
        self.assertEqual(settings.rag_query_message_limit, 120)
        self.assertEqual(
            settings.rag_source_whitelist,
            ("https://a.com/news", "https://b.com/path"),
        )
        self.assertEqual(settings.rag_backend, "milvus")
        self.assertEqual(settings.rag_milvus_collection, "col1")
        self.assertEqual(settings.rag_milvus_search_limit, 33)
        self.assertEqual(settings.stage_agent_max_chunks, 20)
        self.assertFalse(settings.reflection_enabled)
        self.assertFalse(settings.topic_memory_enabled)
        self.assertFalse(settings.rag_hybrid_enabled)
        self.assertFalse(settings.rag_rerank_enabled)
        self.assertEqual(settings.rag_lexical_engine, "bm25")
        self.assertEqual(settings.rag_bm25_cache_dir, "/tmp/bm25-cache")
        self.assertFalse(settings.rag_bm25_use_disk_cache)
        self.assertFalse(settings.rag_bm25_fallback_to_simple)
        self.assertEqual(settings.rag_rerank_engine, "heuristic")
        self.assertEqual(settings.rag_rerank_model, "BAAI/bge-reranker-v2-m3")
        self.assertEqual(settings.rag_rerank_batch_size, 8)
        self.assertEqual(settings.rag_rerank_candidate_cap, 40)
        self.assertEqual(settings.rag_rerank_timeout_ms, 5000)
        self.assertEqual(settings.rag_rerank_device, "cuda")
        self.assertEqual(settings.reflection_policy, "winner_mismatch_or_low_margin")
        self.assertEqual(settings.reflection_low_margin_threshold, 6)
        self.assertEqual(settings.fault_injection_nodes, ("final_pass_1", "display"))
        self.assertEqual(settings.degrade_max_level, 2)
        self.assertEqual(settings.trace_ttl_secs, 600)
        self.assertEqual(settings.idempotency_ttl_secs, 900)
        self.assertTrue(settings.redis_enabled)
        self.assertTrue(settings.redis_required)
        self.assertEqual(settings.redis_url, "redis://redis:6379/4")
        self.assertEqual(settings.redis_pool_size, 32)
        self.assertEqual(settings.redis_key_prefix, "ai_judge:v2:test")
        self.assertEqual(settings.topic_memory_limit, 7)
        self.assertEqual(settings.topic_memory_min_evidence_refs, 2)
        self.assertEqual(settings.topic_memory_min_rationale_chars, 60)
        self.assertEqual(settings.topic_memory_min_quality_score, 0.7)
        self.assertEqual(settings.tokenizer_fallback_encoding, "cl100k_base")
        self.assertEqual(settings.phase_prompt_max_tokens, 4096)
        self.assertEqual(settings.agent2_prompt_max_tokens, 5000)
        self.assertEqual(settings.rag_query_max_tokens, 1200)
        self.assertEqual(settings.rag_snippet_max_tokens, 220)
        self.assertEqual(settings.embed_input_max_tokens, 1800)
        self.assertEqual(settings.runtime_retry_max_attempts, 4)
        self.assertEqual(settings.runtime_retry_backoff_ms, 500)
        self.assertFalse(settings.compliance_block_enabled)

    def test_build_callback_and_dispatch_configs_should_map_fields(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings()

        callback_cfg = build_callback_client_config(settings)
        runtime_cfg = build_dispatch_runtime_config(settings)

        self.assertEqual(callback_cfg.ai_internal_key, settings.ai_internal_key)
        self.assertEqual(callback_cfg.chat_server_base_url, settings.chat_server_base_url)
        self.assertEqual(callback_cfg.callback_timeout_secs, settings.callback_timeout_secs)
        self.assertEqual(runtime_cfg.process_delay_ms, settings.process_delay_ms)
        self.assertEqual(runtime_cfg.judge_style_mode, settings.judge_style_mode)
        self.assertEqual(runtime_cfg.runtime_retry_max_attempts, settings.runtime_retry_max_attempts)
        self.assertEqual(runtime_cfg.retry_backoff_ms, settings.runtime_retry_backoff_ms)
        self.assertEqual(runtime_cfg.compliance_block_enabled, settings.compliance_block_enabled)

    def test_load_settings_should_map_invalid_provider_to_openai(self) -> None:
        with patch.dict(os.environ, {"AI_JUDGE_PROVIDER": "invalid"}, clear=True):
            settings = load_settings()
        self.assertEqual(settings.provider, PROVIDER_OPENAI)

    def test_load_settings_should_reject_mock_in_production(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ECHOISLE_ENV": "production",
                "AI_JUDGE_PROVIDER": "mock",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "AI_JUDGE_PROVIDER=mock is forbidden"):
                load_settings()

    def test_load_settings_should_reject_openai_fallback_in_production(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ECHOISLE_ENV": "production",
                "AI_JUDGE_PROVIDER": "openai",
                "OPENAI_API_KEY": "sk-xx",
                "AI_JUDGE_OPENAI_FALLBACK_TO_MOCK": "true",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "AI_JUDGE_OPENAI_FALLBACK_TO_MOCK=true is forbidden",
            ):
                load_settings()

    def test_load_settings_should_reject_missing_openai_key_in_production(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ECHOISLE_ENV": "prod",
                "AI_JUDGE_PROVIDER": "openai",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY cannot be empty"):
                load_settings()

    def test_validate_for_runtime_env_should_allow_mock_in_non_production(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_JUDGE_PROVIDER": "mock",
            },
            clear=True,
        ):
            settings = load_settings()
        validate_for_runtime_env(settings, runtime_env="staging")

    def test_load_settings_should_reject_invalid_degrade_level(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_JUDGE_DEGRADE_MAX_LEVEL": "9",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "AI_JUDGE_DEGRADE_MAX_LEVEL must be between 0 and 3"):
                load_settings()

    def test_load_settings_should_reject_invalid_runtime_retry_max_attempts(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_JUDGE_RUNTIME_RETRY_MAX_ATTEMPTS": "0",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "AI_JUDGE_RUNTIME_RETRY_MAX_ATTEMPTS must be between 1 and 10",
            ):
                load_settings()

    def test_load_settings_should_reject_invalid_runtime_retry_backoff_ms(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_JUDGE_RUNTIME_RETRY_BACKOFF_MS": "-1",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "AI_JUDGE_RUNTIME_RETRY_BACKOFF_MS must be between 0 and 10000",
            ):
                load_settings()

    def test_load_settings_should_reject_invalid_phase_prompt_max_tokens(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_JUDGE_PHASE_PROMPT_MAX_TOKENS": "100",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "AI_JUDGE_PHASE_PROMPT_MAX_TOKENS must be between 256 and 32000",
            ):
                load_settings()

    def test_load_settings_should_reject_invalid_reflection_policy(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_JUDGE_REFLECTION_POLICY": "invalid",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "AI_JUDGE_REFLECTION_POLICY must be one of"):
                load_settings()

    def test_load_settings_should_reject_fault_injection_nodes_in_production(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ECHOISLE_ENV": "production",
                "AI_JUDGE_PROVIDER": "openai",
                "OPENAI_API_KEY": "sk-test",
                "AI_JUDGE_FAULT_INJECTION_NODES": "display",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "AI_JUDGE_FAULT_INJECTION_NODES is forbidden",
            ):
                load_settings()

    def test_load_settings_should_accept_runtime_fault_injection_nodes_in_non_production(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_JUDGE_FAULT_INJECTION_NODES": "provider_timeout,rag_retrieve_unavailable,topic_memory_unavailable",
            },
            clear=True,
        ):
            settings = load_settings()
        self.assertEqual(
            settings.fault_injection_nodes,
            ("provider_timeout", "rag_retrieve_unavailable", "topic_memory_unavailable"),
        )

    def test_load_settings_should_reject_empty_redis_url_when_enabled(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_JUDGE_REDIS_ENABLED": "true",
                "AI_JUDGE_REDIS_URL": "",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "AI_JUDGE_REDIS_URL cannot be empty"):
                load_settings()

    def test_load_settings_should_reject_invalid_topic_memory_limit(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_JUDGE_TOPIC_MEMORY_LIMIT": "100",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "AI_JUDGE_TOPIC_MEMORY_LIMIT must be between 1 and 20"):
                load_settings()

    def test_load_settings_should_reject_invalid_topic_memory_quality_threshold(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_JUDGE_TOPIC_MEMORY_MIN_QUALITY_SCORE": "1.2",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "AI_JUDGE_TOPIC_MEMORY_MIN_QUALITY_SCORE must be between 0 and 1"):
                load_settings()


if __name__ == "__main__":
    unittest.main()
