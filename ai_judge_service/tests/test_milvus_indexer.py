import json
import tempfile
import unittest
from unittest.mock import patch

from app.milvus_indexer import (
    MilvusIndexerConfig,
    _build_embedding_input,
    import_knowledge_to_milvus,
    load_knowledge_records,
)
from app.token_budget import count_tokens


class _FakeMilvusClient:
    def __init__(self) -> None:
        self.upsert_calls: list[dict] = []
        self.collection_created = False

    def has_collection(self, collection_name: str) -> bool:
        _ = collection_name
        return False

    def create_collection(self, **kwargs) -> None:
        _ = kwargs
        self.collection_created = True

    def upsert(self, *, collection_name: str, data: list[dict]) -> None:
        self.upsert_calls.append(
            {
                "collection_name": collection_name,
                "data": data,
            }
        )


class MilvusIndexerTests(unittest.TestCase):
    def test_load_knowledge_records_should_skip_invalid_rows(self) -> None:
        rows = [
            {
                "chunkId": "a",
                "title": "A",
                "sourceUrl": "https://example.com/a",
                "content": "content a",
                "tags": ["x", "Y"],
            },
            {"chunkId": "b", "title": "B", "content": ""},
            "invalid",
        ]
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", encoding="utf-8") as file:
            json.dump(rows, file, ensure_ascii=False)
            file.flush()
            records = load_knowledge_records(file.name)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].chunk_id, "a")
        self.assertEqual(records[0].tags, ("x", "y"))

    def test_build_embedding_input_should_include_tags(self) -> None:
        rows = [
            {
                "chunkId": "a",
                "title": "A",
                "sourceUrl": "https://example.com/a",
                "content": "content a",
                "tags": ["x", "Y"],
            }
        ]
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", encoding="utf-8") as file:
            json.dump(rows, file, ensure_ascii=False)
            file.flush()
            records = load_knowledge_records(file.name)
        text = _build_embedding_input(records[0])
        self.assertIn("A", text)
        self.assertIn("content a", text)
        self.assertIn("x y", text)

    def test_build_embedding_input_should_apply_token_cap(self) -> None:
        rows = [
            {
                "chunkId": "a",
                "title": "A",
                "sourceUrl": "https://example.com/a",
                "content": "很长内容 " * 300,
                "tags": ["x", "Y"],
            }
        ]
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", encoding="utf-8") as file:
            json.dump(rows, file, ensure_ascii=False)
            file.flush()
            records = load_knowledge_records(file.name)
        text = _build_embedding_input(
            records[0],
            embed_input_max_tokens=60,
            tokenizer_model="gpt-4.1-mini",
            tokenizer_fallback_encoding="o200k_base",
        )
        self.assertLessEqual(
            count_tokens("gpt-4.1-mini", text, fallback_encoding="o200k_base"),
            60,
        )

    @patch("app.milvus_indexer._embed_batch_with_openai")
    @patch("app.milvus_indexer._new_milvus_client")
    def test_import_knowledge_to_milvus_should_batch_upsert(
        self,
        mock_new_milvus_client,
        mock_embed_batch_with_openai,
    ) -> None:
        rows = [
            {
                "chunkId": "a",
                "title": "A",
                "sourceUrl": "https://example.com/a",
                "content": "content a",
                "tags": ["x"],
            },
            {
                "chunkId": "b",
                "title": "B",
                "sourceUrl": "https://example.com/b",
                "content": "content b",
                "tags": ["y"],
            },
            {
                "chunkId": "c",
                "title": "C",
                "sourceUrl": "https://example.com/c",
                "content": "content c",
                "tags": ["z"],
            },
        ]
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", encoding="utf-8") as file:
            json.dump(rows, file, ensure_ascii=False)
            file.flush()

            fake_client = _FakeMilvusClient()
            mock_new_milvus_client.return_value = fake_client
            mock_embed_batch_with_openai.side_effect = [
                [[0.1, 0.2], [0.3, 0.4]],
                [[0.5, 0.6]],
            ]

            stats = import_knowledge_to_milvus(
                MilvusIndexerConfig(
                    input_file=file.name,
                    milvus_uri="http://milvus:19530",
                    milvus_collection="debate_knowledge",
                    openai_api_key="sk-test",
                    batch_size=2,
                    ensure_collection=True,
                )
            )

        self.assertEqual(stats["totalRecords"], 3)
        self.assertEqual(stats["indexedRecords"], 3)
        self.assertEqual(stats["batchCount"], 2)
        self.assertEqual(stats["embeddingCallCount"], 2)
        self.assertTrue(stats["collectionCreated"])
        self.assertEqual(len(fake_client.upsert_calls), 2)
        first_data = fake_client.upsert_calls[0]["data"][0]
        self.assertIn("chunk_id", first_data)
        self.assertIn("embedding", first_data)

    @patch("app.milvus_indexer._embed_batch_with_openai")
    @patch("app.milvus_indexer._new_milvus_client")
    def test_import_knowledge_to_milvus_should_fail_on_embedding_size_mismatch(
        self,
        mock_new_milvus_client,
        mock_embed_batch_with_openai,
    ) -> None:
        rows = [
            {
                "chunkId": "a",
                "title": "A",
                "sourceUrl": "https://example.com/a",
                "content": "content a",
                "tags": ["x"],
            },
            {
                "chunkId": "b",
                "title": "B",
                "sourceUrl": "https://example.com/b",
                "content": "content b",
                "tags": ["y"],
            },
        ]
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", encoding="utf-8") as file:
            json.dump(rows, file, ensure_ascii=False)
            file.flush()
            mock_new_milvus_client.return_value = _FakeMilvusClient()
            mock_embed_batch_with_openai.return_value = [[0.1, 0.2]]

            with self.assertRaisesRegex(RuntimeError, "embedding size mismatch"):
                import_knowledge_to_milvus(
                    MilvusIndexerConfig(
                        input_file=file.name,
                        milvus_uri="http://milvus:19530",
                        milvus_collection="debate_knowledge",
                        openai_api_key="sk-test",
                        batch_size=16,
                    )
                )


if __name__ == "__main__":
    unittest.main()
