import json
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.rag_retriever import (
    RAG_BACKEND_FILE,
    RAG_BACKEND_MILVUS,
    RagMilvusConfig,
    parse_rag_backend,
    parse_source_whitelist,
    retrieve_contexts,
    summarize_retrieved_contexts,
)
from app.token_budget import count_tokens


def _build_request():
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        job=SimpleNamespace(
            job_id=100,
            scope_id=1,
            session_id=2,
            requested_by=3,
            style_mode="rational",
            rejudge_triggered=False,
            requested_at=now,
        ),
        session=SimpleNamespace(
            status="judging",
            scheduled_start_at=now,
            actual_start_at=now,
            end_at=now,
        ),
        topic=SimpleNamespace(
            title="云顶之弈前排版本答案",
            description="讨论谁是当前版本最强前排",
            category="game",
            stance_pro="重装前排强",
            stance_con="高爆发更强",
            context_seed="版本补丁提升前排护甲收益",
        ),
        messages=[
            SimpleNamespace(
                message_id=1,
                user_id=10,
                side="pro",
                content="前排站得住才有后排输出空间",
                created_at=now,
            ),
            SimpleNamespace(
                message_id=2,
                user_id=11,
                side="con",
                content="后排爆发也能在前排倒下前结束战斗",
                created_at=now,
            ),
        ],
        message_window_size=100,
        rubric_version="v1",
    )


class RagRetrieverTests(unittest.TestCase):
    def test_parse_rag_backend_should_default_to_file(self) -> None:
        self.assertEqual(parse_rag_backend(""), RAG_BACKEND_FILE)
        self.assertEqual(parse_rag_backend(None), RAG_BACKEND_FILE)
        self.assertEqual(parse_rag_backend("unknown"), RAG_BACKEND_FILE)
        self.assertEqual(parse_rag_backend("MILVUS"), RAG_BACKEND_MILVUS)

    def test_parse_source_whitelist_should_normalize_and_deduplicate(self) -> None:
        ret = parse_source_whitelist(" https://a.com/x/ ; https://b.com/y \nhttps://a.com/x ")
        self.assertEqual(ret, ("https://a.com/x", "https://b.com/y"))

    def test_retrieve_contexts_should_rank_relevant_chunks_and_keep_context_seed(self) -> None:
        request = _build_request()
        chunks = [
            {
                "chunkId": "tft-frontline",
                "title": "前排改动说明",
                "sourceUrl": "https://example.com/frontline",
                "content": "该版本前排羁绊获得额外护甲和魔抗加成。",
                "tags": ["tft", "frontline"],
            },
            {
                "chunkId": "unrelated",
                "title": "足球资讯",
                "sourceUrl": "https://example.com/football",
                "content": "本周足球联赛焦点战回顾。",
                "tags": ["sports"],
            },
        ]
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False)
            f.flush()
            with tempfile.TemporaryDirectory() as cache_dir:
                contexts = retrieve_contexts(
                    request,
                    enabled=True,
                    knowledge_file=f.name,
                    max_snippets=3,
                    max_chars_per_snippet=120,
                    query_message_limit=50,
                    bm25_cache_dir=cache_dir,
                )

        self.assertGreaterEqual(len(contexts), 2)
        self.assertEqual(contexts[0].chunk_id, "topic-context-seed")
        self.assertEqual(contexts[1].chunk_id, "tft-frontline")
        self.assertLessEqual(len(contexts[1].content), 120)

    def test_retrieve_contexts_should_filter_non_whitelisted_sources(self) -> None:
        request = _build_request()
        chunks = [
            {
                "chunkId": "allowed",
                "title": "云顶之弈新闻",
                "sourceUrl": "https://teamfighttactics.leagueoflegends.com/en-us/news/game-updates-14-3",
                "content": "前排羁绊在该版本增强。",
                "tags": ["tft", "news"],
            },
            {
                "chunkId": "blocked",
                "title": "其他站点新闻",
                "sourceUrl": "https://example.com/tft-news",
                "content": "同样提到前排增强。",
                "tags": ["tft"],
            },
        ]
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False)
            f.flush()
            with tempfile.TemporaryDirectory() as cache_dir:
                contexts = retrieve_contexts(
                    request,
                    enabled=True,
                    knowledge_file=f.name,
                    max_snippets=5,
                    max_chars_per_snippet=120,
                    query_message_limit=50,
                    allowed_source_prefixes=parse_source_whitelist(
                        "https://teamfighttactics.leagueoflegends.com/en-us/news/"
                    ),
                    bm25_cache_dir=cache_dir,
                )

        chunk_ids = [item.chunk_id for item in contexts]
        self.assertIn("topic-context-seed", chunk_ids)
        self.assertIn("allowed", chunk_ids)
        self.assertNotIn("blocked", chunk_ids)

    def test_retrieve_contexts_should_return_empty_when_disabled(self) -> None:
        request = _build_request()
        contexts = retrieve_contexts(
            request,
            enabled=False,
            knowledge_file="",
            max_snippets=3,
            max_chars_per_snippet=120,
            query_message_limit=50,
        )
        self.assertEqual(contexts, [])

    def test_summarize_retrieved_contexts_should_keep_public_fields(self) -> None:
        request = _build_request()
        contexts = retrieve_contexts(
            request,
            enabled=True,
            knowledge_file="",
            max_snippets=2,
            max_chars_per_snippet=80,
            query_message_limit=20,
        )
        summary = summarize_retrieved_contexts(contexts)
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["chunkId"], "topic-context-seed")
        self.assertIn("score", summary[0])
        self.assertIn("sourceUrl", summary[0])

    @patch("app.rag_retriever._embed_query_with_openai")
    @patch("app.rag_retriever._fetch_milvus_candidates")
    def test_retrieve_contexts_milvus_should_use_backend_and_whitelist(
        self,
        mock_fetch_milvus_candidates,
        mock_embed_query_with_openai,
    ) -> None:
        request = _build_request()
        mock_embed_query_with_openai.return_value = [0.1, 0.2, 0.3]
        mock_fetch_milvus_candidates.return_value = [
            {
                "distance": 0.91,
                "entity": {
                    "chunk_id": "milvus-ok",
                    "title": "云顶前排版本分析",
                    "source_url": "https://teamfighttactics.leagueoflegends.com/en-us/news/tft-14-5",
                    "content": "前排羁绊在本版本仍旧具备较高承伤价值。",
                },
            },
            {
                "distance": 0.95,
                "entity": {
                    "chunk_id": "milvus-blocked",
                    "title": "站外转载",
                    "source_url": "https://example.com/tft",
                    "content": "该内容应被白名单过滤。",
                },
            },
        ]
        contexts = retrieve_contexts(
            request,
            enabled=True,
            knowledge_file="",
            max_snippets=4,
            max_chars_per_snippet=120,
            query_message_limit=50,
            backend=RAG_BACKEND_MILVUS,
            milvus_config=RagMilvusConfig(
                uri="http://milvus:19530",
                collection="debate_knowledge",
            ),
            openai_api_key="sk-test",
            openai_base_url="https://api.openai.com/v1",
            openai_embedding_model="text-embedding-3-small",
            openai_timeout_secs=8,
            allowed_source_prefixes=parse_source_whitelist(
                "https://teamfighttactics.leagueoflegends.com/en-us/news/"
            ),
        )

        chunk_ids = [item.chunk_id for item in contexts]
        self.assertEqual(chunk_ids[0], "topic-context-seed")
        self.assertIn("milvus-ok", chunk_ids)
        self.assertNotIn("milvus-blocked", chunk_ids)
        mock_embed_query_with_openai.assert_called_once()
        mock_fetch_milvus_candidates.assert_called_once()

    def test_retrieve_contexts_file_should_support_rerank_and_diagnostics(self) -> None:
        request = _build_request()
        chunks = [
            {
                "chunkId": "c1",
                "title": "前排护甲收益",
                "sourceUrl": "https://example.com/c1",
                "content": "前排护甲收益与版本改动有关。",
                "tags": ["frontline"],
            },
            {
                "chunkId": "c2",
                "title": "后排爆发收益",
                "sourceUrl": "https://example.com/c2",
                "content": "后排爆发在短局中更强。",
                "tags": ["backline"],
            },
        ]
        diagnostics: dict = {}
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False)
            f.flush()
            with tempfile.TemporaryDirectory() as cache_dir:
                contexts = retrieve_contexts(
                    request,
                    enabled=True,
                    knowledge_file=f.name,
                    max_snippets=2,
                    max_chars_per_snippet=120,
                    query_message_limit=50,
                    rerank_enabled=True,
                    rerank_engine="heuristic",
                    bm25_cache_dir=cache_dir,
                    diagnostics=diagnostics,
                )
        self.assertLessEqual(len(contexts), 2)
        self.assertEqual(diagnostics["strategy"], "file_lexical")
        self.assertTrue(diagnostics["rerankApplied"])
        self.assertEqual(diagnostics["lexicalEngineConfigured"], "bm25")
        self.assertEqual(diagnostics["lexicalEngineEffective"], "bm25")
        self.assertIn("lexicalIndexCacheHit", diagnostics)
        self.assertIn("lexicalIndexBuildMs", diagnostics)
        self.assertIn("lexicalDocCount", diagnostics)
        self.assertEqual(diagnostics["finalCount"], len(contexts))
        self.assertEqual(diagnostics["tuning"]["lexicalLimitMultiplier"], 2)
        self.assertEqual(diagnostics["tuning"]["rerankQueryWeight"], 0.7)
        self.assertEqual(diagnostics["tuning"]["rerankBaseWeight"], 0.3)
        self.assertEqual(diagnostics["rerankEngineConfigured"], "heuristic")
        self.assertEqual(diagnostics["rerankEngineEffective"], "heuristic")
        self.assertIn("rerankLatencyMs", diagnostics)
        self.assertIn("candidateBeforeRerank", diagnostics)
        self.assertIn("candidateAfterRerank", diagnostics)

    @patch("app.rag_retriever._embed_query_with_openai")
    @patch("app.rag_retriever._fetch_milvus_candidates")
    def test_retrieve_contexts_milvus_should_support_hybrid_and_rerank(
        self,
        mock_fetch_milvus_candidates,
        mock_embed_query_with_openai,
    ) -> None:
        request = _build_request()
        mock_embed_query_with_openai.return_value = [0.1, 0.2, 0.3]
        mock_fetch_milvus_candidates.return_value = [
            {
                "distance": 0.93,
                "entity": {
                    "chunk_id": "milvus-ok",
                    "title": "向量召回前排分析",
                    "source_url": "https://example.com/milvus-ok",
                    "content": "向量召回命中前排分析内容。",
                },
            }
        ]
        diagnostics: dict = {}
        chunks = [
            {
                "chunkId": "file-ok",
                "title": "词法召回前排版本",
                "sourceUrl": "https://example.com/file-ok",
                "content": "词法召回命中前排关键词。",
                "tags": ["frontline", "patch"],
            }
        ]
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False)
            f.flush()
            with tempfile.TemporaryDirectory() as cache_dir:
                contexts = retrieve_contexts(
                    request,
                    enabled=True,
                    knowledge_file=f.name,
                    max_snippets=4,
                    max_chars_per_snippet=120,
                    query_message_limit=50,
                    backend=RAG_BACKEND_MILVUS,
                    milvus_config=RagMilvusConfig(
                        uri="http://milvus:19530",
                        collection="debate_knowledge",
                    ),
                    openai_api_key="sk-test",
                    openai_base_url="https://api.openai.com/v1",
                    openai_embedding_model="text-embedding-3-small",
                    openai_timeout_secs=8,
                    hybrid_enabled=True,
                    rerank_enabled=True,
                    rerank_engine="heuristic",
                    bm25_cache_dir=cache_dir,
                    diagnostics=diagnostics,
                )
        chunk_ids = [item.chunk_id for item in contexts]
        self.assertIn("milvus-ok", chunk_ids)
        self.assertIn("file-ok", chunk_ids)
        self.assertEqual(diagnostics["strategy"], "milvus_hybrid")
        self.assertGreaterEqual(diagnostics["vectorCandidateCount"], 1)
        self.assertGreaterEqual(diagnostics["lexicalCandidateCount"], 1)
        self.assertTrue(diagnostics["rerankApplied"])
        self.assertEqual(diagnostics["lexicalEngineConfigured"], "bm25")
        self.assertEqual(diagnostics["lexicalEngineEffective"], "bm25")
        self.assertEqual(diagnostics["tuning"]["rrfK"], 60)
        self.assertEqual(diagnostics["tuning"]["vectorLimitMultiplier"], 1)
        self.assertEqual(diagnostics["rerankEngineConfigured"], "heuristic")
        self.assertEqual(diagnostics["rerankEngineEffective"], "heuristic")

    def test_retrieve_contexts_should_clamp_invalid_tuning_values(self) -> None:
        request = _build_request()
        diagnostics: dict = {}
        with tempfile.TemporaryDirectory() as cache_dir:
            contexts = retrieve_contexts(
                request,
                enabled=True,
                knowledge_file="",
                max_snippets=2,
                max_chars_per_snippet=120,
                query_message_limit=50,
                rerank_enabled=True,
                hybrid_rrf_k=-10,
                hybrid_vector_limit_multiplier=-2,
                hybrid_lexical_limit_multiplier=99,
                rerank_query_weight=2.5,
                rerank_base_weight=-1.0,
                rerank_engine="heuristic",
                bm25_cache_dir=cache_dir,
                diagnostics=diagnostics,
            )
        self.assertGreaterEqual(len(contexts), 1)
        self.assertEqual(diagnostics["tuning"]["rrfK"], 1)
        self.assertEqual(diagnostics["tuning"]["vectorLimitMultiplier"], 1)
        self.assertEqual(diagnostics["tuning"]["lexicalLimitMultiplier"], 8)
        self.assertEqual(diagnostics["lexicalEngineConfigured"], "bm25")
        self.assertEqual(diagnostics["tuning"]["rerankQueryWeight"], 1.0)
        self.assertEqual(diagnostics["tuning"]["rerankBaseWeight"], 0.0)
        self.assertEqual(diagnostics["rerankEngineConfigured"], "heuristic")
        self.assertEqual(diagnostics["rerankEngineEffective"], "heuristic")

    def test_retrieve_contexts_should_apply_query_and_snippet_token_cap(self) -> None:
        request = _build_request()
        request.messages = request.messages + [
            SimpleNamespace(
                message_id=3,
                user_id=12,
                side="pro",
                content="超长消息 " * 400,
                created_at=request.messages[0].created_at,
            )
        ]
        chunks = [
            {
                "chunkId": "long-chunk",
                "title": "长片段",
                "sourceUrl": "https://example.com/long",
                "content": "超长知识片段 " * 500,
                "tags": ["long"],
            },
        ]
        diagnostics: dict = {}
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False)
            f.flush()
            with tempfile.TemporaryDirectory() as cache_dir:
                contexts = retrieve_contexts(
                    request,
                    enabled=True,
                    knowledge_file=f.name,
                    max_snippets=3,
                    max_chars_per_snippet=6000,
                    query_message_limit=100,
                    query_max_tokens=40,
                    snippet_max_tokens=30,
                    bm25_cache_dir=cache_dir,
                    diagnostics=diagnostics,
                )
        self.assertTrue(diagnostics["queryTokenClip"]["clipped"])
        for item in contexts:
            self.assertLessEqual(
                count_tokens("gpt-4.1-mini", item.content, fallback_encoding="o200k_base"),
                30,
            )

    @patch("app.rag_retriever._fetch_milvus_candidates")
    @patch("app.rag_retriever._embed_query_with_openai")
    def test_retrieve_contexts_milvus_should_forward_embed_budget_and_capped_query(
        self,
        mock_embed_query_with_openai,
        mock_fetch_milvus_candidates,
    ) -> None:
        request = _build_request()
        request.messages = request.messages + [
            SimpleNamespace(
                message_id=3,
                user_id=12,
                side="pro",
                content="query-message " * 400,
                created_at=request.messages[0].created_at,
            )
        ]
        mock_fetch_milvus_candidates.return_value = []

        captured: dict[str, object] = {}

        def _fake_embed(**kwargs):
            captured.update(kwargs)
            return []

        mock_embed_query_with_openai.side_effect = _fake_embed
        diagnostics: dict = {}
        _ = retrieve_contexts(
            request,
            enabled=True,
            knowledge_file="",
            max_snippets=2,
            max_chars_per_snippet=400,
            query_message_limit=100,
            query_max_tokens=24,
            snippet_max_tokens=50,
            backend=RAG_BACKEND_MILVUS,
            milvus_config=RagMilvusConfig(
                uri="http://milvus:19530",
                collection="debate_knowledge",
            ),
            openai_api_key="sk-test",
            embed_input_max_tokens=18,
            diagnostics=diagnostics,
        )
        self.assertEqual(captured["embed_input_max_tokens"], 18)
        self.assertLessEqual(
            count_tokens(
                "gpt-4.1-mini",
                str(captured["query_text"]),
                fallback_encoding="o200k_base",
            ),
            24,
        )
        self.assertTrue(diagnostics["queryTokenClip"]["clipped"])


if __name__ == "__main__":
    unittest.main()
