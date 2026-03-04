import unittest

from app.scoring_core import DebateMessage, build_report_core


class ScoringCoreTests(unittest.TestCase):
    def _message(self, message_id: int, side: str, content: str) -> DebateMessage:
        return DebateMessage(
            message_id=message_id,
            user_id=1000 + message_id,
            side=side,
            content=content,
        )

    def test_empty_messages_should_produce_draw_and_no_stage(self) -> None:
        report = build_report_core(
            job_id=100,
            style_mode="rational",
            rejudge_triggered=False,
            messages=[],
            message_window_size=100,
            rubric_version="v1",
        )
        self.assertEqual(report["winner"], "draw")
        self.assertTrue(report["needs_draw_vote"])
        self.assertEqual(report["stage_summaries"], [])

    def test_inconsistent_two_pass_winner_should_force_draw_and_rejudge(self) -> None:
        messages = [
            self._message(1, "pro", "because data shows patch trend"),
            self._message(2, "con", "because data shows patch trend"),
        ]
        report = build_report_core(
            job_id=1,
            style_mode="rational",
            rejudge_triggered=False,
            messages=messages,
            message_window_size=100,
            rubric_version="v1",
        )
        self.assertNotEqual(report["winner_first"], report["winner_second"])
        self.assertEqual(report["winner"], "draw")
        self.assertTrue(report["needs_draw_vote"])
        self.assertTrue(report["rejudge_triggered"])

    def test_stage_summary_should_follow_window_size(self) -> None:
        messages = []
        for idx in range(1, 206):
            side = "pro" if idx % 2 == 0 else "con"
            messages.append(self._message(idx, side, f"msg-{idx} because source data"))
        report = build_report_core(
            job_id=7,
            style_mode="rational",
            rejudge_triggered=False,
            messages=messages,
            message_window_size=100,
            rubric_version="v1",
        )
        stages = report["stage_summaries"]
        self.assertEqual(len(stages), 3)
        self.assertEqual(stages[0]["from_message_id"], 1)
        self.assertEqual(stages[0]["to_message_id"], 100)
        self.assertEqual(stages[2]["from_message_id"], 201)
        self.assertEqual(stages[2]["to_message_id"], 205)
        refs = report["payload"]["verdictEvidenceRefs"]
        self.assertTrue(refs)
        self.assertIn("messageId", refs[0])
        self.assertIn("role", refs[0])
        self.assertIn("reason", refs[0])


if __name__ == "__main__":
    unittest.main()
