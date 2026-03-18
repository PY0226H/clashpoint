import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.models import PhaseDispatchRequest
from app.phase_pipeline import build_phase_report_payload
from tests.test_app_factory import _build_settings


def _build_phase_request_for_pipeline() -> PhaseDispatchRequest:
    now = datetime.now(timezone.utc)
    return PhaseDispatchRequest(
        job_id=301,
        scope_id=1,
        session_id=77,
        phase_no=3,
        message_start_id=1,
        message_end_id=4,
        message_count=4,
        messages=[
            {
                "message_id": 1,
                "side": "pro",
                "content": "正方认为龙族经济可以稳住前期节奏。",
                "created_at": now,
                "speaker_tag": "pro_1",
            },
            {
                "message_id": 2,
                "side": "con",
                "content": "反方质疑龙族在高压对局容易崩盘。",
                "created_at": now,
                "speaker_tag": "con_1",
            },
            {
                "message_id": 3,
                "side": "pro",
                "content": "正方反驳：运营细节可以降低崩盘风险。",
                "created_at": now,
                "speaker_tag": "pro_2",
            },
            {
                "message_id": 4,
                "side": "con",
                "content": "反方补充：转型窗口过晚会丢失血量。",
                "created_at": now,
                "speaker_tag": "con_2",
            },
        ],
        rubric_version="v3",
        judge_policy_version="v3-default",
        topic_domain="tft",
        retrieval_profile="hybrid_v1",
        trace_id="trace-phase-301",
        idempotency_key="phase-key-301",
    )


class PhasePipelineTests(unittest.TestCase):
    def test_build_phase_report_payload_should_keep_side_summary_complete(self) -> None:
        request = _build_phase_request_for_pipeline()
        settings = _build_settings(
            rag_enabled=False,
            rag_knowledge_file="",
            rag_source_whitelist=(),
        )

        payload = asyncio.run(
            build_phase_report_payload(
                request=request,
                settings=settings,
            )
        )

        self.assertEqual(payload["sessionId"], 77)
        self.assertEqual(payload["phaseNo"], 3)
        self.assertEqual(payload["proSummaryGrounded"]["messageIds"], [1, 3])
        self.assertEqual(payload["conSummaryGrounded"]["messageIds"], [2, 4])
        self.assertIn("龙族经济", payload["proSummaryGrounded"]["text"])
        self.assertIn("崩盘", payload["conSummaryGrounded"]["text"])
        self.assertNotIn("龙族经济", payload["conSummaryGrounded"]["text"])
        self.assertGreaterEqual(len(payload["proRetrievalBundle"]["queries"]), 1)
        self.assertGreaterEqual(len(payload["conRetrievalBundle"]["queries"]), 1)
        self.assertEqual(payload["proRetrievalBundle"]["items"], [])
        self.assertEqual(payload["conRetrievalBundle"]["items"], [])
        self.assertIn("rag_no_hit_pro", payload["errorCodes"])
        self.assertIn("rag_no_hit_con", payload["errorCodes"])
        self.assertEqual(payload["degradationLevel"], 2)

    def test_build_phase_report_payload_should_emit_agent1_four_dimension_scorecard(self) -> None:
        request = _build_phase_request_for_pipeline()
        settings = _build_settings(
            rag_enabled=False,
            rag_knowledge_file="",
            rag_source_whitelist=(),
        )

        payload = asyncio.run(
            build_phase_report_payload(
                request=request,
                settings=settings,
            )
        )

        agent1 = payload["agent1Score"]
        self.assertIn("weights", agent1)
        self.assertEqual(set(agent1["dimensions"]["pro"].keys()), {"logic", "evidence", "rebuttal", "expression"})
        self.assertEqual(set(agent1["dimensions"]["con"].keys()), {"logic", "evidence", "rebuttal", "expression"})
        for side in ("pro", "con"):
            for key in ("logic", "evidence", "rebuttal", "expression"):
                value = float(agent1["dimensions"][side][key])
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 100.0)
            refs = agent1["evidenceRefs"][side]
            self.assertGreaterEqual(len(refs["messageIds"]), 1)
            self.assertIn("chunkIds", refs)
        self.assertIn("balanceSignals", agent1)

    def test_build_phase_report_payload_should_attach_retrieval_items_when_knowledge_available(self) -> None:
        request = _build_phase_request_for_pipeline()
        with tempfile.NamedTemporaryFile("w+", suffix=".json", encoding="utf-8") as tmp:
            json.dump(
                [
                    {
                        "chunk_id": "chunk-pro-1",
                        "title": "龙族经济运营",
                        "source_url": "https://example.com/tft/pro-eco",
                        "content": "龙族经济在前期通过连败管理可以稳定收益并提高后续转型上限。",
                        "tags": ["龙族", "经济", "运营"],
                    },
                    {
                        "chunk_id": "chunk-con-1",
                        "title": "高压对局节奏",
                        "source_url": "https://example.com/tft/con-pressure",
                        "content": "高压对局里转型太晚会丢失血量，容易在中期被带走。",
                        "tags": ["高压", "转型", "血量"],
                    },
                ],
                tmp,
                ensure_ascii=False,
            )
            tmp.flush()
            settings = _build_settings(
                rag_enabled=True,
                rag_knowledge_file=tmp.name,
                rag_source_whitelist=(),
                rag_max_snippets=3,
                rag_query_message_limit=20,
            )

            payload = asyncio.run(
                build_phase_report_payload(
                    request=request,
                    settings=settings,
                )
            )

        pro_items = payload["proRetrievalBundle"]["items"]
        con_items = payload["conRetrievalBundle"]["items"]
        self.assertTrue(pro_items or con_items)
        for item in pro_items + con_items:
            self.assertIn("chunkId", item)
            self.assertIn("title", item)
            self.assertIn("sourceUrl", item)
            self.assertIn("score", item)
            self.assertIn("snippet", item)
            self.assertIn("conflict", item)

        self.assertEqual(set(payload["promptHashes"].keys()), {"a2", "a3", "a4", "a5", "a6", "a7"})
        self.assertEqual(payload["judgeTrace"]["pipelineVersion"], "v3-phase-m5-agent2-bidirectional-v2")
        self.assertIn("retrievalDiagnostics", payload["judgeTrace"])
        self.assertIn("agent2Audit", payload["judgeTrace"])

    def test_build_phase_report_payload_should_mark_conflicts_and_dedupe_after_query_fusion(self) -> None:
        request = _build_phase_request_for_pipeline()
        with tempfile.NamedTemporaryFile("w+", suffix=".json", encoding="utf-8") as tmp:
            json.dump(
                [
                    {
                        "chunk_id": "chunk-1",
                        "title": "龙族运营要点",
                        "source_url": "https://example.com/source/a",
                        "content": "龙族前期经济稳定，收益提升，后续转型可行。",
                        "tags": ["龙族", "经济"],
                    },
                    {
                        "chunk_id": "chunk-2",
                        "title": "龙族运营要点",
                        "source_url": "https://example.com/source/b",
                        "content": "高压对局下龙族容易崩盘，存在明显风险。",
                        "tags": ["龙族", "风险"],
                    },
                    {
                        "chunk_id": "chunk-3",
                        "title": "转型窗口",
                        "source_url": "https://example.com/source/c",
                        "content": "转型窗口过晚会掉血，需要提前规划。",
                        "tags": ["转型", "节奏"],
                    },
                ],
                tmp,
                ensure_ascii=False,
            )
            tmp.flush()
            settings = _build_settings(
                rag_enabled=True,
                rag_knowledge_file=tmp.name,
                rag_source_whitelist=(),
                rag_max_snippets=6,
                rag_query_message_limit=20,
            )
            payload = asyncio.run(
                build_phase_report_payload(
                    request=request,
                    settings=settings,
                )
            )

        for side in ("proRetrievalBundle", "conRetrievalBundle"):
            items = payload[side]["items"]
            chunk_ids = [item["chunkId"] for item in items if item.get("chunkId")]
            self.assertEqual(len(chunk_ids), len(set(chunk_ids)))

        merged_items = payload["proRetrievalBundle"]["items"] + payload["conRetrievalBundle"]["items"]
        self.assertTrue(any(item.get("conflict") for item in merged_items))
        self.assertEqual(
            payload["judgeTrace"]["retrievalDiagnostics"]["pro"]["fusion"]["method"],
            "rrf+rerank",
        )
        self.assertGreaterEqual(
            payload["judgeTrace"]["retrievalDiagnostics"]["pro"]["queryCount"],
            1,
        )

    def test_build_phase_report_payload_should_run_bidirectional_agent2_with_llm(self) -> None:
        request = _build_phase_request_for_pipeline()
        settings = _build_settings(
            provider="openai",
            openai_api_key="test-key",
            rag_enabled=False,
            rag_knowledge_file="",
            rag_source_whitelist=(),
        )

        async def _mock_call_openai_json(*, cfg, system_prompt, user_prompt):
            if "辩论阶段总结Agent" in system_prompt:
                if "当前阵营: pro" in system_prompt:
                    return {"summary_text": "正方总结", "message_ids": [1, 3]}
                return {"summary_text": "反方总结", "message_ids": [2, 4]}
            if "顶级辩手" in system_prompt:
                if "source_side=pro, target_side=con" in system_prompt:
                    return {"ideal_rebuttal": "理想反方反驳", "key_points": ["高压崩盘", "转型风险"]}
                if "source_side=con, target_side=pro" in system_prompt:
                    return {"ideal_rebuttal": "理想正方反驳", "key_points": ["运营细节", "经济稳定"]}
            if "命中度评估器" in system_prompt:
                if "target_side=con" in system_prompt:
                    return {
                        "score": 78,
                        "hit_points": ["高压崩盘"],
                        "miss_points": ["转型风险"],
                        "rationale": "命中部分核心点",
                        "dimension_scores": {
                            "coverage": 80,
                            "depth": 76,
                            "evidence_fit": 74,
                            "key_point_hit_rate": 70,
                        },
                    }
                return {
                    "score": 66,
                    "hit_points": ["运营细节"],
                    "miss_points": ["经济稳定"],
                    "rationale": "命中一个关键点",
                    "dimension_scores": {
                        "coverage": 67,
                        "depth": 64,
                        "evidence_fit": 62,
                        "key_point_hit_rate": 60,
                    },
                }
            raise AssertionError("unexpected prompt")

        with patch("app.phase_pipeline.call_openai_json", new=AsyncMock(side_effect=_mock_call_openai_json)):
            payload = asyncio.run(
                build_phase_report_payload(
                    request=request,
                    settings=settings,
                )
            )

        self.assertGreater(payload["agent2Score"]["pro"], 55.0)
        self.assertGreater(payload["agent2Score"]["con"], payload["agent2Score"]["pro"])
        self.assertEqual(payload["judgeTrace"]["agent2Audit"]["paths"]["pro"]["source"], "llm")
        self.assertEqual(payload["judgeTrace"]["agent2Audit"]["paths"]["con"]["source"], "llm")
        self.assertIn("dimensionScores", payload["judgeTrace"]["agent2Audit"]["paths"]["pro"])
        self.assertIn("weights", payload["judgeTrace"]["agent2Audit"])
        self.assertFalse(payload["judgeTrace"]["agent2Audit"]["resilience"]["pro"]["usedBaselineFallback"])
        self.assertFalse(payload["judgeTrace"]["agent2Audit"]["resilience"]["con"]["usedBaselineFallback"])
        self.assertAlmostEqual(payload["agent3WeightedScore"]["w1"], 0.35, places=2)
        self.assertAlmostEqual(payload["agent3WeightedScore"]["w2"], 0.65, places=2)

    def test_build_phase_report_payload_should_degrade_to_baseline_when_one_agent2_path_failed(self) -> None:
        request = _build_phase_request_for_pipeline()
        settings = _build_settings(
            provider="openai",
            openai_api_key="test-key",
            rag_enabled=False,
            rag_knowledge_file="",
            rag_source_whitelist=(),
        )

        async def _mock_call_openai_json(*, cfg, system_prompt, user_prompt):
            if "辩论阶段总结Agent" in system_prompt:
                if "当前阵营: pro" in system_prompt:
                    return {"summary_text": "正方总结", "message_ids": [1, 3]}
                return {"summary_text": "反方总结", "message_ids": [2, 4]}
            if "顶级辩手" in system_prompt:
                if "target_side=pro" in system_prompt:
                    raise RuntimeError("mocked a6 failure for pro path")
                return {"ideal_rebuttal": "理想反方反驳", "key_points": ["高压崩盘", "转型风险"]}
            if "命中度评估器" in system_prompt:
                return {
                    "score": 75,
                    "hit_points": ["高压崩盘"],
                    "miss_points": ["转型风险"],
                    "dimension_scores": {
                        "coverage": 78,
                        "depth": 74,
                        "evidence_fit": 70,
                        "key_point_hit_rate": 68,
                    },
                }
            raise AssertionError("unexpected prompt")

        with patch("app.phase_pipeline.call_openai_json", new=AsyncMock(side_effect=_mock_call_openai_json)):
            payload = asyncio.run(
                build_phase_report_payload(
                    request=request,
                    settings=settings,
                )
            )

        self.assertIn("agent2_partial_degraded", payload["errorCodes"])
        self.assertEqual(payload["judgeTrace"]["agent2Audit"]["paths"]["pro"]["pathStatus"], "failed_baseline_fallback")
        self.assertTrue(payload["judgeTrace"]["agent2Audit"]["resilience"]["pro"]["usedBaselineFallback"])
        self.assertFalse(payload["judgeTrace"]["agent2Audit"]["resilience"]["con"]["usedBaselineFallback"])
        self.assertAlmostEqual(payload["agent3WeightedScore"]["w1"], 0.7, places=2)
        self.assertAlmostEqual(payload["agent3WeightedScore"]["w2"], 0.3, places=2)

    def test_build_phase_report_payload_should_fallback_when_summary_coverage_low(self) -> None:
        request = _build_phase_request_for_pipeline()
        settings = _build_settings(
            provider="openai",
            openai_api_key="test-key",
            rag_enabled=False,
            rag_knowledge_file="",
            rag_source_whitelist=(),
        )
        mocked = AsyncMock(
            side_effect=[
                {"summary_text": "仅覆盖第一条", "message_ids": [1]},
                {"summary_text": "仅覆盖一条反方", "message_ids": [2]},
            ]
        )
        with patch("app.phase_pipeline.call_openai_json", mocked):
            payload = asyncio.run(
                build_phase_report_payload(
                    request=request,
                    settings=settings,
                )
            )

        self.assertIn("summary_coverage_low_pro", payload["errorCodes"])
        self.assertIn("summary_coverage_low_con", payload["errorCodes"])
        self.assertEqual(payload["proSummaryGrounded"]["messageIds"], [1, 3])
        self.assertEqual(payload["conSummaryGrounded"]["messageIds"], [2, 4])
        self.assertEqual(payload["judgeTrace"]["summaryAudit"]["pro"]["source"], "extractive_fallback")
        self.assertEqual(payload["judgeTrace"]["summaryAudit"]["con"]["source"], "extractive_fallback")


if __name__ == "__main__":
    unittest.main()
