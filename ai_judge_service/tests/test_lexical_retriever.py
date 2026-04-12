import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app.lexical_retriever as lexical_module
from app.lexical_retriever import (
    LexicalDocument,
    LexicalSearchRequest,
    search_lexical,
)


def _build_documents() -> list[LexicalDocument]:
    return [
        LexicalDocument(
            chunk_id="title-hit",
            title="龙族经济运营",
            source_url="https://example.com/a",
            content="讲解前期连败管理与收益曲线。",
            tags=("龙族", "经济", "运营"),
        ),
        LexicalDocument(
            chunk_id="content-hit",
            title="高压对局节奏",
            source_url="https://example.com/b",
            content="龙族在部分对局也会提到经济，但重点是中期掉血。",
            tags=("高压", "节奏"),
        ),
    ]


class LexicalRetrieverTests(unittest.TestCase):
    def setUp(self) -> None:
        lexical_module._INDEX_CACHE.clear()

    def tearDown(self) -> None:
        lexical_module._INDEX_CACHE.clear()

    def test_search_lexical_should_prioritize_title_and_tags_hits(self) -> None:
        with tempfile.NamedTemporaryFile("w+", suffix=".json", encoding="utf-8") as knowledge_file:
            json.dump([{"chunk_id": "title-hit"}], knowledge_file, ensure_ascii=False)
            knowledge_file.flush()
            with tempfile.TemporaryDirectory() as cache_dir:
                result = search_lexical(
                    LexicalSearchRequest(
                        knowledge_file=knowledge_file.name,
                        documents=_build_documents(),
                        query_text="龙族经济运营",
                        top_k=2,
                        bm25_cache_dir=cache_dir,
                    )
                )

        self.assertEqual(result.configured_engine, "bm25")
        self.assertEqual(result.effective_engine, "bm25")
        self.assertEqual(result.hits[0].chunk_id, "title-hit")
        self.assertGreater(result.hits[0].score, result.hits[1].score)

    def test_search_lexical_should_reuse_disk_cache_when_signature_matches(self) -> None:
        documents = _build_documents()
        with tempfile.NamedTemporaryFile("w+", suffix=".json", encoding="utf-8") as knowledge_file:
            json.dump([{"chunk_id": "title-hit"}], knowledge_file, ensure_ascii=False)
            knowledge_file.flush()
            with tempfile.TemporaryDirectory() as cache_dir:
                first = search_lexical(
                    LexicalSearchRequest(
                        knowledge_file=knowledge_file.name,
                        documents=documents,
                        query_text="龙族经济运营",
                        top_k=2,
                        bm25_cache_dir=cache_dir,
                        bm25_use_disk_cache=True,
                    )
                )
                self.assertFalse(first.index_cache_hit)
                self.assertTrue(any(Path(cache_dir).iterdir()))

                lexical_module._INDEX_CACHE.clear()

                second = search_lexical(
                    LexicalSearchRequest(
                        knowledge_file=knowledge_file.name,
                        documents=documents,
                        query_text="龙族经济运营",
                        top_k=2,
                        bm25_cache_dir=cache_dir,
                        bm25_use_disk_cache=True,
                    )
                )

        self.assertEqual(second.effective_engine, "bm25")
        self.assertTrue(second.index_cache_hit)

    def test_search_lexical_should_invalidate_cache_when_knowledge_file_changes(self) -> None:
        documents = _build_documents()
        with tempfile.NamedTemporaryFile(
            "w+", suffix=".json", encoding="utf-8", delete=False
        ) as knowledge_file:
            knowledge_path = Path(knowledge_file.name)
            json.dump([{"version": 1}], knowledge_file, ensure_ascii=False)
            knowledge_file.flush()

        try:
            with tempfile.TemporaryDirectory() as cache_dir:
                first = search_lexical(
                    LexicalSearchRequest(
                        knowledge_file=str(knowledge_path),
                        documents=documents,
                        query_text="龙族经济运营",
                        top_k=2,
                        bm25_cache_dir=cache_dir,
                        bm25_use_disk_cache=True,
                    )
                )
                self.assertEqual(first.effective_engine, "bm25")
                first_dirs = sorted(path.name for path in Path(cache_dir).iterdir())
                self.assertEqual(len(first_dirs), 1)

                knowledge_path.write_text(
                    '[{"version": 2, "note": "invalidate", "padding": "bm25-cache-refresh"}]\n',
                    encoding="utf-8",
                )
                stat = knowledge_path.stat()
                os.utime(
                    knowledge_path,
                    ns=(stat.st_atime_ns + 5_000_000, stat.st_mtime_ns + 5_000_000),
                )
                lexical_module._INDEX_CACHE.clear()

                second = search_lexical(
                    LexicalSearchRequest(
                        knowledge_file=str(knowledge_path),
                        documents=documents,
                        query_text="龙族经济运营",
                        top_k=2,
                        bm25_cache_dir=cache_dir,
                        bm25_use_disk_cache=True,
                    )
                )
                self.assertEqual(second.effective_engine, "bm25")
                second_dirs = sorted(path.name for path in Path(cache_dir).iterdir())

            self.assertEqual(len(second_dirs), 2)
            self.assertNotEqual(set(first_dirs), set(second_dirs))
        finally:
            knowledge_path.unlink(missing_ok=True)

    def test_search_lexical_should_fallback_to_simple_when_bm25_fails(self) -> None:
        request = LexicalSearchRequest(
            knowledge_file="",
            documents=_build_documents(),
            query_text="龙族经济运营",
            top_k=2,
            fallback_to_simple=True,
        )
        with patch(
            "app.lexical_retriever.Bm25sLexicalRetriever.search",
            side_effect=RuntimeError("bm25-boom"),
        ):
            result = search_lexical(request)

        self.assertEqual(result.effective_engine, "simple")
        self.assertEqual(result.error_code, "rag_lexical_unavailable")
        self.assertEqual(result.hits[0].chunk_id, "title-hit")
        self.assertIn("bm25-boom", str(result.fallback_reason))


if __name__ == "__main__":
    unittest.main()
