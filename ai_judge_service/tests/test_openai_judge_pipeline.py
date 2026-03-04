import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

import app.openai_judge_pipeline as openai_judge_pipeline
from app.openai_judge import OpenAiJudgeConfig


def _build_request() -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
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
        messages=[
            SimpleNamespace(
                message_id=1,
                user_id=1,
                side="pro",
                content="我认为前排装备决定上限",
            )
        ],
        message_window_size=100,
        rubric_version="v1",
    )


def _build_config() -> OpenAiJudgeConfig:
    return OpenAiJudgeConfig(
        api_key="test-key",
        model="gpt-test",
        base_url="https://api.example.com/v1",
        timeout_secs=3.0,
        temperature=0.2,
        max_retries=1,
        max_stage_agent_chunks=4,
    )


class OpenAiJudgePipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_pipeline_should_use_fallbacks_and_mark_rejudge(self) -> None:
        cfg = _build_config()
        request = _build_request()

        responses = iter(
            [
                RuntimeError("stage fail"),
                RuntimeError("aggregate fail"),
                {
                    "winner": "pro",
                    "logic_pro": 90,
                    "logic_con": 60,
                    "evidence_pro": 88,
                    "evidence_con": 58,
                    "rebuttal_pro": 82,
                    "rebuttal_con": 59,
                    "clarity_pro": 75,
                    "clarity_con": 64,
                    "pro_summary": "first pro",
                    "con_summary": "first con",
                    "rationale": "first rationale",
                },
                {
                    "winner": "con",
                    "logic_pro": 60,
                    "logic_con": 90,
                    "evidence_pro": 58,
                    "evidence_con": 87,
                    "rebuttal_pro": 57,
                    "rebuttal_con": 82,
                    "clarity_pro": 65,
                    "clarity_con": 78,
                    "pro_summary": "second pro",
                    "con_summary": "second con",
                    "rationale": "second rationale",
                },
                RuntimeError("display fail"),
            ]
        )

        async def fake_call_openai_json(**_: object) -> dict[str, object]:
            value = next(responses)
            if isinstance(value, Exception):
                raise value
            return value

        original = openai_judge_pipeline.call_openai_json
        openai_judge_pipeline.call_openai_json = fake_call_openai_json
        try:
            result = await openai_judge_pipeline.run_openai_judge_pipeline(
                cfg=cfg,
                request=request,
                style_mode="rational",
                retrieved_contexts=[],
                max_stage_agent_chunks=cfg.max_stage_agent_chunks,
            )
        finally:
            openai_judge_pipeline.call_openai_json = original

        self.assertEqual(len(result.stage_summaries), 1)
        self.assertEqual(result.stage_fallback_count, 1)
        self.assertTrue(result.aggregate_fallback)
        self.assertTrue(result.display_fallback)
        self.assertEqual(result.final_fallback_count, 0)
        self.assertEqual(result.merged["winner"], "draw")
        self.assertTrue(result.merged["rejudge_triggered"])
        self.assertEqual(result.display["pro_summary"], result.merged["pro_summary"])
        self.assertEqual(result.reflection.action, "draw_protection")
        self.assertGreaterEqual(len(result.graph_nodes), 6)
        self.assertEqual(result.compliance["status"], "ok")

    async def test_run_pipeline_should_return_openai_outputs_when_calls_succeed(self) -> None:
        cfg = _build_config()
        request = _build_request()

        responses = iter(
            [
                {
                    "pro_score": 78,
                    "con_score": 70,
                    "winner_hint": "pro",
                    "pro_summary": "stage pro",
                    "con_summary": "stage con",
                    "rationale": "stage rationale",
                },
                {
                    "pro_summary": "agg pro",
                    "con_summary": "agg con",
                    "rationale": "agg rationale",
                    "winner_hint": "pro",
                },
                {
                    "winner": "pro",
                    "logic_pro": 90,
                    "logic_con": 70,
                    "evidence_pro": 88,
                    "evidence_con": 68,
                    "rebuttal_pro": 82,
                    "rebuttal_con": 66,
                    "clarity_pro": 76,
                    "clarity_con": 65,
                    "pro_summary": "first pro",
                    "con_summary": "first con",
                    "rationale": "first rationale",
                },
                {
                    "winner": "pro",
                    "logic_pro": 89,
                    "logic_con": 69,
                    "evidence_pro": 87,
                    "evidence_con": 67,
                    "rebuttal_pro": 81,
                    "rebuttal_con": 65,
                    "clarity_pro": 75,
                    "clarity_con": 64,
                    "pro_summary": "second pro",
                    "con_summary": "second con",
                    "rationale": "second rationale",
                },
                {
                    "pro_summary_display": "display pro",
                    "con_summary_display": "display con",
                    "rationale_display": "display rationale",
                },
            ]
        )

        async def fake_call_openai_json(**_: object) -> dict[str, object]:
            return next(responses)

        original = openai_judge_pipeline.call_openai_json
        openai_judge_pipeline.call_openai_json = fake_call_openai_json
        try:
            result = await openai_judge_pipeline.run_openai_judge_pipeline(
                cfg=cfg,
                request=request,
                style_mode="rational",
                retrieved_contexts=[],
                max_stage_agent_chunks=cfg.max_stage_agent_chunks,
            )
        finally:
            openai_judge_pipeline.call_openai_json = original

        self.assertEqual(result.stage_fallback_count, 0)
        self.assertFalse(result.aggregate_fallback)
        self.assertFalse(result.display_fallback)
        self.assertEqual(result.final_fallback_count, 0)
        self.assertEqual(result.merged["winner"], "pro")
        self.assertFalse(result.merged["needs_draw_vote"])
        self.assertEqual(result.display["pro_summary"], "display pro")
        self.assertEqual(result.display["rationale"], "display rationale")
        self.assertEqual(result.reflection.action, "consistency_confirmed")

    async def test_run_pipeline_should_degrade_when_final_pass_failed(self) -> None:
        cfg = _build_config()
        request = _build_request()

        responses = iter(
            [
                {
                    "pro_score": 80,
                    "con_score": 70,
                    "winner_hint": "pro",
                    "pro_summary": "stage pro",
                    "con_summary": "stage con",
                    "rationale": "stage rationale",
                },
                {
                    "pro_summary": "agg pro",
                    "con_summary": "agg con",
                    "rationale": "agg rationale",
                    "winner_hint": "pro",
                },
                RuntimeError("first final pass failed"),
                {
                    "winner": "con",
                    "logic_pro": 62,
                    "logic_con": 86,
                    "evidence_pro": 60,
                    "evidence_con": 84,
                    "rebuttal_pro": 61,
                    "rebuttal_con": 83,
                    "clarity_pro": 62,
                    "clarity_con": 81,
                    "pro_summary": "second pro",
                    "con_summary": "second con",
                    "rationale": "second rationale",
                },
                {
                    "pro_summary_display": "display pro",
                    "con_summary_display": "display con",
                    "rationale_display": "display rationale",
                },
            ]
        )

        async def fake_call_openai_json(**_: object) -> dict[str, object]:
            value = next(responses)
            if isinstance(value, Exception):
                raise value
            return value

        original = openai_judge_pipeline.call_openai_json
        openai_judge_pipeline.call_openai_json = fake_call_openai_json
        try:
            result = await openai_judge_pipeline.run_openai_judge_pipeline(
                cfg=cfg,
                request=request,
                style_mode="rational",
                retrieved_contexts=[],
                max_stage_agent_chunks=cfg.max_stage_agent_chunks,
            )
        finally:
            openai_judge_pipeline.call_openai_json = original

        self.assertEqual(result.final_fallback_count, 1)
        self.assertEqual(result.merged["winner_first"], "draw")
        self.assertEqual(result.merged["winner_second"], "con")
        self.assertEqual(result.merged["winner"], "draw")
        self.assertTrue(result.merged["rejudge_triggered"])
        self.assertEqual(result.reflection.action, "draw_protection")

    async def test_run_pipeline_should_skip_reflection_when_disabled(self) -> None:
        cfg = _build_config()
        request = _build_request()

        responses = iter(
            [
                {
                    "pro_score": 80,
                    "con_score": 70,
                    "winner_hint": "pro",
                    "pro_summary": "stage pro",
                    "con_summary": "stage con",
                    "rationale": "stage rationale",
                },
                {
                    "pro_summary": "agg pro",
                    "con_summary": "agg con",
                    "rationale": "agg rationale",
                    "winner_hint": "pro",
                },
                {
                    "winner": "pro",
                    "logic_pro": 86,
                    "logic_con": 70,
                    "evidence_pro": 84,
                    "evidence_con": 68,
                    "rebuttal_pro": 82,
                    "rebuttal_con": 66,
                    "clarity_pro": 80,
                    "clarity_con": 67,
                    "pro_summary": "first pro",
                    "con_summary": "first con",
                    "rationale": "first rationale",
                },
                {
                    "winner": "pro",
                    "logic_pro": 88,
                    "logic_con": 69,
                    "evidence_pro": 85,
                    "evidence_con": 67,
                    "rebuttal_pro": 83,
                    "rebuttal_con": 65,
                    "clarity_pro": 79,
                    "clarity_con": 66,
                    "pro_summary": "second pro",
                    "con_summary": "second con",
                    "rationale": "second rationale",
                },
                {
                    "pro_summary_display": "display pro",
                    "con_summary_display": "display con",
                    "rationale_display": "display rationale",
                },
            ]
        )

        async def fake_call_openai_json(**_: object) -> dict[str, object]:
            return next(responses)

        original = openai_judge_pipeline.call_openai_json
        openai_judge_pipeline.call_openai_json = fake_call_openai_json
        try:
            result = await openai_judge_pipeline.run_openai_judge_pipeline(
                cfg=cfg,
                request=request,
                style_mode="rational",
                retrieved_contexts=[],
                max_stage_agent_chunks=cfg.max_stage_agent_chunks,
                reflection_enabled=False,
            )
        finally:
            openai_judge_pipeline.call_openai_json = original

        self.assertFalse(result.reflection.enabled)
        self.assertEqual(result.reflection.action, "merge_only")


if __name__ == "__main__":
    unittest.main()
