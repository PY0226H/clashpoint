import unittest

from app.callback_client import CallbackClientConfig
from app.wiring import bind_callback_failed, bind_callback_report, build_dispatch_callbacks


class WiringTests(unittest.IsolatedAsyncioTestCase):
    async def test_bind_callback_report_should_bind_cfg_and_forward_args(self) -> None:
        cfg = CallbackClientConfig(
            ai_internal_key="k1",
            chat_server_base_url="http://chat",
            report_path_template="/r/{job_id}",
            failed_path_template="/f/{job_id}",
            callback_timeout_secs=8.0,
        )
        calls: list[tuple[CallbackClientConfig, int, dict]] = []

        async def fake_callback_report(*, cfg: CallbackClientConfig, job_id: int, payload: dict) -> None:
            calls.append((cfg, job_id, payload))

        bound = bind_callback_report(
            cfg=cfg,
            callback_report_impl=fake_callback_report,
        )
        payload = {"winner": "pro"}
        await bound(12, payload)

        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][0], cfg)
        self.assertEqual(calls[0][1], 12)
        self.assertEqual(calls[0][2], payload)

    async def test_bind_callback_failed_should_bind_cfg_and_forward_args(self) -> None:
        cfg = CallbackClientConfig(
            ai_internal_key="k2",
            chat_server_base_url="http://chat",
            report_path_template="/r/{job_id}",
            failed_path_template="/f/{job_id}",
            callback_timeout_secs=9.0,
        )
        calls: list[tuple[CallbackClientConfig, int, str]] = []

        async def fake_callback_failed(*, cfg: CallbackClientConfig, job_id: int, error_message: str) -> None:
            calls.append((cfg, job_id, error_message))

        bound = bind_callback_failed(
            cfg=cfg,
            callback_failed_impl=fake_callback_failed,
        )
        await bound(99, "runtime failed")

        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][0], cfg)
        self.assertEqual(calls[0][1], 99)
        self.assertEqual(calls[0][2], "runtime failed")

    async def test_build_dispatch_callbacks_should_return_bound_pair(self) -> None:
        cfg = CallbackClientConfig(
            ai_internal_key="k3",
            chat_server_base_url="http://chat",
            report_path_template="/r/{job_id}",
            failed_path_template="/f/{job_id}",
            callback_timeout_secs=10.0,
        )
        report_calls: list[tuple[CallbackClientConfig, int, dict]] = []
        failed_calls: list[tuple[CallbackClientConfig, int, str]] = []

        async def fake_callback_report(*, cfg: CallbackClientConfig, job_id: int, payload: dict) -> None:
            report_calls.append((cfg, job_id, payload))

        async def fake_callback_failed(*, cfg: CallbackClientConfig, job_id: int, error_message: str) -> None:
            failed_calls.append((cfg, job_id, error_message))

        report_fn, failed_fn = build_dispatch_callbacks(
            cfg=cfg,
            callback_report_impl=fake_callback_report,
            callback_failed_impl=fake_callback_failed,
        )

        await report_fn(1, {"jobId": 1})
        await failed_fn(1, "oops")

        self.assertEqual(report_calls[0][0], cfg)
        self.assertEqual(report_calls[0][1], 1)
        self.assertEqual(report_calls[0][2], {"jobId": 1})
        self.assertEqual(failed_calls[0][0], cfg)
        self.assertEqual(failed_calls[0][1], 1)
        self.assertEqual(failed_calls[0][2], "oops")


if __name__ == "__main__":
    unittest.main()
