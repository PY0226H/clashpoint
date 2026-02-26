import os
import unittest
from unittest.mock import patch

from app.runtime_policy import PROVIDER_MOCK, PROVIDER_OPENAI
from app.settings import (
    build_callback_client_config,
    build_dispatch_runtime_config,
    load_settings,
)


class SettingsTests(unittest.TestCase):
    def test_load_settings_should_use_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings()

        self.assertEqual(settings.provider, PROVIDER_MOCK)
        self.assertEqual(settings.ai_internal_key, "dev-ai-internal-key")
        self.assertEqual(settings.chat_server_base_url, "http://127.0.0.1:6688")
        self.assertEqual(settings.openai_base_url, "https://api.openai.com/v1")
        self.assertTrue(settings.openai_fallback_to_mock)
        self.assertTrue(settings.rag_enabled)
        self.assertEqual(
            settings.rag_source_whitelist,
            ("https://teamfighttactics.leagueoflegends.com/en-us/news",),
        )
        self.assertEqual(settings.stage_agent_max_chunks, 12)

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
                "AI_JUDGE_OPENAI_FALLBACK_TO_MOCK": "false",
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
        self.assertFalse(settings.openai_fallback_to_mock)
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

    def test_build_callback_and_dispatch_configs_should_map_fields(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings()

        callback_cfg = build_callback_client_config(settings)
        runtime_cfg = build_dispatch_runtime_config(settings)

        self.assertEqual(callback_cfg.ai_internal_key, settings.ai_internal_key)
        self.assertEqual(callback_cfg.chat_server_base_url, settings.chat_server_base_url)
        self.assertEqual(callback_cfg.report_path_template, settings.report_path_template)
        self.assertEqual(callback_cfg.failed_path_template, settings.failed_path_template)
        self.assertEqual(callback_cfg.callback_timeout_secs, settings.callback_timeout_secs)
        self.assertEqual(runtime_cfg.process_delay_ms, settings.process_delay_ms)
        self.assertEqual(runtime_cfg.judge_style_mode, settings.judge_style_mode)


if __name__ == "__main__":
    unittest.main()
