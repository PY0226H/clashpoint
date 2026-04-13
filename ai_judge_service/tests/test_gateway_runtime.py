import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.applications import build_gateway_runtime


class GatewayRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_llm_gateway_should_delegate_to_openai_client(self) -> None:
        runtime = build_gateway_runtime(settings=SimpleNamespace())
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
        self.assertEqual(payload, {"ok": True})
        mocked.assert_awaited_once()

    async def test_knowledge_gateway_should_delegate_to_runtime_rag(self) -> None:
        runtime = build_gateway_runtime(settings=SimpleNamespace())
        fake_result = {"requested_backend": "file", "effective_backend": "file"}
        with patch(
            "app.infra.gateways.default.retrieve_runtime_contexts_with_meta",
            return_value=fake_result,
        ) as mocked:
            result = runtime.knowledge.retrieve_with_meta(
                request=SimpleNamespace(),
                settings=SimpleNamespace(),
            )
        self.assertEqual(result, fake_result)
        mocked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
