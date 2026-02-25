import json
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.rag_retriever import retrieve_contexts, summarize_retrieved_contexts


def _build_request():
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        job=SimpleNamespace(
            job_id=100,
            ws_id=1,
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
            contexts = retrieve_contexts(
                request,
                enabled=True,
                knowledge_file=f.name,
                max_snippets=3,
                max_chars_per_snippet=120,
                query_message_limit=50,
            )

        self.assertGreaterEqual(len(contexts), 2)
        self.assertEqual(contexts[0].chunk_id, "topic-context-seed")
        self.assertEqual(contexts[1].chunk_id, "tft-frontline")
        self.assertLessEqual(len(contexts[1].content), 120)

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


if __name__ == "__main__":
    unittest.main()
