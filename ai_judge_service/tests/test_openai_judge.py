import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.openai_judge import (
    _build_user_prompt,
    _merge_two_pass,
    _normalize_aggregate_eval,
    _normalize_display_eval,
    _normalize_eval,
    _normalize_stage_eval,
    _split_message_chunks,
)
from app.rag_retriever import RetrievedContext
from app.scoring_core import DebateMessage


class OpenAiJudgeTests(unittest.TestCase):
    def test_normalize_eval_should_clamp_and_derive_scores(self) -> None:
        normalized = _normalize_eval(
            {
                "winner": "invalid",
                "logic_pro": 120,
                "logic_con": 5,
                "evidence_pro": "80",
                "evidence_con": "30",
                "rebuttal_pro": 70.2,
                "rebuttal_con": 66.7,
                "clarity_pro": 50,
                "clarity_con": 40,
                "pro_summary": " pro summary ",
                "con_summary": "",
                "rationale": " reason ",
            }
        )
        self.assertEqual(normalized["logic_pro"], 100)
        self.assertEqual(normalized["evidence_pro"], 80)
        self.assertEqual(normalized["rebuttal_con"], 67)
        self.assertEqual(normalized["winner"], "pro")
        self.assertGreater(normalized["pro_score"], normalized["con_score"])
        self.assertEqual(normalized["con_summary"], "信息不足。")

    def test_merge_two_pass_should_trigger_draw_on_winner_mismatch(self) -> None:
        first = {
            "winner": "pro",
            "logic_pro": 85,
            "logic_con": 60,
            "evidence_pro": 83,
            "evidence_con": 62,
            "rebuttal_pro": 79,
            "rebuttal_con": 58,
            "clarity_pro": 70,
            "clarity_con": 65,
            "pro_score": 80,
            "con_score": 61,
            "pro_summary": "p1",
            "con_summary": "c1",
            "rationale": "first",
        }
        second = {
            "winner": "con",
            "logic_pro": 70,
            "logic_con": 82,
            "evidence_pro": 68,
            "evidence_con": 84,
            "rebuttal_pro": 64,
            "rebuttal_con": 78,
            "clarity_pro": 69,
            "clarity_con": 75,
            "pro_score": 68,
            "con_score": 80,
            "pro_summary": "p2",
            "con_summary": "c2",
            "rationale": "second",
        }

        merged = _merge_two_pass(first, second)
        self.assertEqual(merged["winner"], "draw")
        self.assertTrue(merged["needs_draw_vote"])
        self.assertTrue(merged["rejudge_triggered"])
        self.assertIn("双次评估胜方不一致", merged["rationale"])

    def test_build_user_prompt_should_include_retrieved_contexts(self) -> None:
        now = datetime.now(timezone.utc)
        request = SimpleNamespace(
            job=SimpleNamespace(
                job_id=10,
                ws_id=1,
                session_id=99,
                requested_by=1,
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
                title="云顶之弈版本最强阵容",
                description="围绕当前版本阵容强度展开辩论",
                category="game",
                stance_pro="某阵容更强",
                stance_con="另一阵容更强",
                context_seed="版本补丁强调前排坦度",
            ),
            messages=[],
            message_window_size=100,
            rubric_version="v1",
        )
        messages = [
            DebateMessage(
                message_id=1,
                user_id=1,
                side="pro",
                content="我认为前排装备决定上限",
            )
        ]
        contexts = [
            RetrievedContext(
                chunk_id="chunk-1",
                title="14.3 版本更新",
                source_url="https://example.com/tft/14-3",
                content="官方说明前排羁绊获得额外护甲收益。",
                score=0.8123,
            )
        ]

        prompt = _build_user_prompt(request, messages, contexts)
        self.assertIn("Retrieved background knowledge", prompt)
        self.assertIn("14.3 版本更新", prompt)
        self.assertIn("https://example.com/tft/14-3", prompt)
        self.assertIn("前排羁绊获得额外护甲收益", prompt)

    def test_split_message_chunks_should_keep_recent_chunks_when_capped(self) -> None:
        messages = [
            DebateMessage(
                message_id=idx,
                user_id=1000 + idx,
                side="pro" if idx % 2 == 0 else "con",
                content=f"msg-{idx}",
            )
            for idx in range(1, 251)
        ]
        chunks = _split_message_chunks(messages, window_size=100, max_chunks=2)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0][0], 2)
        self.assertEqual(chunks[0][1][0].message_id, 101)
        self.assertEqual(chunks[1][0], 3)
        self.assertEqual(chunks[1][1][-1].message_id, 250)

    def test_normalize_stage_eval_should_keep_message_range_and_winner_hint(self) -> None:
        chunk = [
            DebateMessage(message_id=11, user_id=1, side="pro", content="pro msg"),
            DebateMessage(message_id=12, user_id=2, side="con", content="con msg"),
        ]
        normalized = _normalize_stage_eval(
            {
                "pro_score": 78,
                "con_score": 68,
                "winner_hint": "pro",
                "pro_summary": "pro stage summary",
                "con_summary": "con stage summary",
                "rationale": "stage rationale",
            },
            chunk,
            stage_no=2,
        )
        self.assertEqual(normalized["stage_no"], 2)
        self.assertEqual(normalized["from_message_id"], 11)
        self.assertEqual(normalized["to_message_id"], 12)
        self.assertEqual(normalized["summary"]["winnerHint"], "pro")

    def test_normalize_aggregate_and_display_should_fallback_to_safe_text(self) -> None:
        stage_summaries = [
            {
                "stage_no": 1,
                "from_message_id": 1,
                "to_message_id": 2,
                "pro_score": 60,
                "con_score": 55,
                "summary": {"winnerHint": "pro"},
            }
        ]
        aggregate = _normalize_aggregate_eval({}, stage_summaries)
        self.assertIn("信息不足", aggregate["pro_summary"])
        self.assertEqual(aggregate["winner_hint"], "pro")

        display = _normalize_display_eval(
            {},
            {"pro_summary": "p raw", "con_summary": "c raw", "rationale": "r raw"},
        )
        self.assertEqual(display["pro_summary"], "p raw")
        self.assertEqual(display["con_summary"], "c raw")
        self.assertEqual(display["rationale"], "r raw")


if __name__ == "__main__":
    unittest.main()
