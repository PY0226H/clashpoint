import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

import app.openai_judge as openai_judge
from app.openai_judge import OpenAiJudgeConfig, build_report_with_openai
from app.rag_retriever import RetrievedContext


def _build_request() -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        job=SimpleNamespace(
            job_id=11,
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
        messages=[
            SimpleNamespace(
                message_id=1,
                user_id=1,
                side="pro",
                content="前排装备决定上限",
            )
        ],
        message_window_size=100,
        rubric_version="v1",
    )


def _build_cfg() -> OpenAiJudgeConfig:
    return OpenAiJudgeConfig(
        api_key="test-key",
        model="gpt-test",
        base_url="https://api.example.com/v1",
        timeout_secs=3.0,
        temperature=0.2,
        max_retries=1,
        max_stage_agent_chunks=4,
    )


class OpenAiJudgeReportTests(unittest.IsolatedAsyncioTestCase):
    async def test_build_report_with_openai_should_include_final_fallback_count(self) -> None:
        request = _build_request()
        cfg = _build_cfg()
        contexts = [
            RetrievedContext(
                chunk_id="chunk-1",
                title="14.3 版本更新",
                source_url="https://example.com/tft/14-3",
                content="官方说明前排羁绊获得额外护甲收益。",
                score=0.8,
            )
        ]

        captured: dict[str, object] = {}

        async def fake_pipeline(**kwargs: object) -> SimpleNamespace:
            captured.update(kwargs)
            return SimpleNamespace(
                stage_summaries=[
                    {
                        "stage_no": 1,
                        "from_message_id": 1,
                        "to_message_id": 1,
                        "pro_score": 80,
                        "con_score": 70,
                        "summary": {"winnerHint": "pro"},
                    }
                ],
                stage_fallback_count=0,
                aggregate_summary={
                    "winner_hint": "pro",
                    "pro_score_hint": 80,
                    "con_score_hint": 70,
                },
                aggregate_fallback=False,
                final_fallback_count=1,
                merged={
                    "winner": "draw",
                    "winner_first": "draw",
                    "winner_second": "pro",
                    "rejudge_triggered": True,
                    "needs_draw_vote": True,
                    "pro_score": 50,
                    "con_score": 50,
                    "logic_pro": 50,
                    "logic_con": 50,
                    "evidence_pro": 50,
                    "evidence_con": 50,
                    "rebuttal_pro": 50,
                    "rebuttal_con": 50,
                    "clarity_pro": 50,
                    "clarity_con": 50,
                    "pro_summary": "pro raw",
                    "con_summary": "con raw",
                    "rationale": "rationale raw",
                },
                display={
                    "pro_summary": "pro display",
                    "con_summary": "con display",
                    "rationale": "rationale display",
                },
                display_fallback=False,
            )

        original = openai_judge.run_openai_judge_pipeline
        openai_judge.run_openai_judge_pipeline = fake_pipeline
        try:
            report = await build_report_with_openai(
                request=request,
                effective_style_mode="rational",
                style_mode_source="system_config",
                cfg=cfg,
                retrieved_contexts=contexts,
            )
        finally:
            openai_judge.run_openai_judge_pipeline = original

        self.assertEqual(captured["max_stage_agent_chunks"], cfg.max_stage_agent_chunks)
        self.assertEqual(captured["style_mode"], "rational")
        self.assertEqual(report.payload["agentPipeline"]["finalPassFallbackCount"], 1)
        self.assertEqual(report.payload["winnerFirst"], "draw")
        self.assertEqual(report.payload["winnerSecond"], "pro")
        self.assertTrue(report.needs_draw_vote)
        self.assertTrue(report.rejudge_triggered)


if __name__ == "__main__":
    unittest.main()
