import json
import tempfile
import unittest
from datetime import datetime, timezone

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

        payload = build_phase_report_payload(
            request=request,
            settings=settings,
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

            payload = build_phase_report_payload(
                request=request,
                settings=settings,
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
        self.assertEqual(payload["judgeTrace"]["pipelineVersion"], "v3-phase-m4-baseline")
        self.assertIn("retrievalDiagnostics", payload["judgeTrace"])


if __name__ == "__main__":
    unittest.main()
