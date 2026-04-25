import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.applications import build_gateway_runtime
from app.openai_judge_client import OPENAI_META_KEY
from app.runtime_rag import RuntimeRagResult


class GatewayRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_llm_gateway_should_delegate_to_openai_client(self) -> None:
        runtime = build_gateway_runtime(
            settings=SimpleNamespace(
                provider="openai",
                openai_model="gpt-test",
                openai_timeout_secs=8.0,
                openai_temperature=0.1,
                openai_max_retries=1,
                openai_fallback_to_mock=False,
                rag_backend="file",
                rag_source_whitelist=("https://example.test/docs",),
                rag_hybrid_enabled=True,
                rag_rerank_enabled=True,
            )
        )
        cfg = SimpleNamespace(
            api_key="sk-test",
            model="gpt-test",
            base_url="https://api.openai.com/v1",
            timeout_secs=8.0,
            temperature=0.1,
            max_retries=1,
        )
        with patch(
            "app.infra.gateways.default.call_openai_json",
            new=AsyncMock(return_value={"ok": True}),
        ) as mocked:
            payload = await runtime.llm.call_json(
                cfg=cfg,
                system_prompt="system",
                user_prompt="user",
            )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload[OPENAI_META_KEY]["gateway"]["provider"], "openai")
        self.assertTrue(payload[OPENAI_META_KEY]["gateway"]["structuredOutput"])
        mocked.assert_awaited_once()

    async def test_knowledge_gateway_should_delegate_to_runtime_rag(self) -> None:
        runtime = build_gateway_runtime(
            settings=SimpleNamespace(
                provider="mock",
                openai_model="gpt-test",
                openai_timeout_secs=8.0,
                openai_temperature=0.1,
                openai_max_retries=1,
                openai_fallback_to_mock=True,
                rag_backend="file",
                rag_source_whitelist=("https://example.test/docs",),
                rag_hybrid_enabled=True,
                rag_rerank_enabled=False,
            )
        )
        fake_result = RuntimeRagResult(
            retrieved_contexts=[],
            requested_backend="file",
            effective_backend="file",
            backend_fallback_reason=None,
            retrieval_diagnostics={},
        )
        with patch(
            "app.infra.gateways.default.retrieve_runtime_contexts_with_meta",
            return_value=fake_result,
        ) as mocked:
            result = runtime.knowledge.retrieve_with_meta(
                request=SimpleNamespace(),
                settings=SimpleNamespace(),
            )
        self.assertEqual(result, fake_result)
        self.assertEqual(
            result.retrieval_diagnostics["gateway"]["sourceWhitelist"],
            ["https://example.test/docs"],
        )
        self.assertFalse(result.retrieval_diagnostics["gateway"]["rerankEnabled"])
        mocked.assert_called_once()

    async def test_gateway_runtime_should_build_core_trace_snapshot(self) -> None:
        runtime = build_gateway_runtime(
            settings=SimpleNamespace(
                provider="mock",
                openai_model="gpt-test",
                openai_timeout_secs=8.0,
                openai_temperature=0.1,
                openai_max_retries=1,
                openai_fallback_to_mock=True,
                rag_backend="file",
                rag_source_whitelist=("https://example.test/docs",),
                rag_hybrid_enabled=True,
                rag_rerank_enabled=True,
            )
        )

        snapshot = runtime.build_trace_snapshot(
            trace_id="trace-1",
            requested_policy_version="v3-default",
            requested_retrieval_profile="hybrid_precision",
            use_case="judge",
        )

        self.assertEqual(snapshot["version"], "gateway-core-v1")
        self.assertEqual(snapshot["traceId"], "trace-1")
        self.assertEqual(snapshot["llm"]["provider"], "mock")
        self.assertEqual(snapshot["knowledge"]["retrievalProfile"], "hybrid_v1")
        self.assertEqual(snapshot["policyBinding"]["policyVersion"], "v3-default")
        self.assertTrue(snapshot["policyBinding"]["officialVerdictPolicy"])
        self.assertIn("npc_coach", snapshot["policyBinding"]["advisoryOnlyUseCases"])
        self.assertTrue(snapshot["noLangChainLangGraph"])


if __name__ == "__main__":
    unittest.main()
