import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from app.dispatch_controller import DispatchRuntimeConfig, process_dispatch_request
from app.runtime_errors import JudgeRuntimeError


class _FakeReport:
    def __init__(self, *, winner: str = "pro", needs_draw_vote: bool = False, provider: str = "openai") -> None:
        self.winner = winner
        self.needs_draw_vote = needs_draw_vote
        self.payload = {"provider": provider}

    def model_dump(self, *, mode: str = "python") -> dict:
        return {"winner": self.winner, "needsDrawVote": self.needs_draw_vote, "mode": mode}


def _build_request(messages: list[object] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        job=SimpleNamespace(
            job_id=42,
            style_mode="rational",
        ),
        messages=messages if messages is not None else [SimpleNamespace(message_id=1)],
    )


def _runtime_cfg(
    *,
    process_delay_ms: int = 0,
    runtime_retry_max_attempts: int = 1,
    retry_backoff_ms: int = 0,
) -> DispatchRuntimeConfig:
    return DispatchRuntimeConfig(
        process_delay_ms=process_delay_ms,
        judge_style_mode="rational",
        runtime_retry_max_attempts=runtime_retry_max_attempts,
        retry_backoff_ms=retry_backoff_ms,
    )


class DispatchControllerTests(unittest.IsolatedAsyncioTestCase):
    async def test_process_dispatch_request_should_mark_failed_when_messages_empty(self) -> None:
        request = _build_request(messages=[])
        failed_calls: list[tuple[int, str]] = []

        async def build_report_by_runtime(*_args: object, **_kwargs: object) -> _FakeReport:
            raise AssertionError("should not build report when no messages")

        async def callback_failed(job_id: int, error_message: str) -> None:
            failed_calls.append((job_id, error_message))

        async def callback_report(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("should not call callback_report on empty messages")

        result = await process_dispatch_request(
            request=request,
            runtime_cfg=_runtime_cfg(),
            build_report_by_runtime=build_report_by_runtime,
            callback_report=callback_report,
            callback_failed=callback_failed,
        )

        self.assertEqual(result["status"], "marked_failed")
        self.assertEqual(failed_calls, [(42, "empty debate messages, cannot judge")])

    async def test_process_dispatch_request_should_mark_failed_when_runtime_error(self) -> None:
        request = _build_request()
        failed_calls: list[tuple[int, str]] = []

        async def build_report_by_runtime(*_args: object, **_kwargs: object) -> _FakeReport:
            raise RuntimeError("runtime exploded")

        async def callback_failed(job_id: int, error_message: str) -> None:
            failed_calls.append((job_id, error_message))

        async def callback_report(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("should not call callback_report after runtime error")

        result = await process_dispatch_request(
            request=request,
            runtime_cfg=_runtime_cfg(),
            build_report_by_runtime=build_report_by_runtime,
            callback_report=callback_report,
            callback_failed=callback_failed,
        )

        self.assertEqual(result["status"], "marked_failed")
        self.assertEqual(result["errorCode"], "model_overload")
        self.assertEqual(len(failed_calls), 1)
        self.assertEqual(failed_calls[0][0], 42)
        self.assertIn("judge runtime failed", failed_calls[0][1])
        self.assertIn("model_overload", failed_calls[0][1])

    async def test_process_dispatch_request_should_raise_when_runtime_error_and_callback_failed_error(self) -> None:
        request = _build_request()

        async def build_report_by_runtime(*_args: object, **_kwargs: object) -> _FakeReport:
            raise RuntimeError("runtime exploded")

        async def callback_failed(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("callback failed also exploded")

        async def callback_report(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("should not call callback_report after runtime error")

        with self.assertRaises(HTTPException) as ctx:
            await process_dispatch_request(
                request=request,
                runtime_cfg=_runtime_cfg(),
                build_report_by_runtime=build_report_by_runtime,
                callback_report=callback_report,
                callback_failed=callback_failed,
            )

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("runtime failed and callback_failed failed", str(ctx.exception.detail))

    async def test_process_dispatch_request_should_forward_runtime_error_code(self) -> None:
        request = _build_request()
        failed_calls: list[tuple[int, str]] = []

        async def build_report_by_runtime(*_args: object, **_kwargs: object) -> _FakeReport:
            raise JudgeRuntimeError(code="judge_timeout", message="openai request timeout")

        async def callback_failed(job_id: int, error_message: str) -> None:
            failed_calls.append((job_id, error_message))

        async def callback_report(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("should not call callback_report after runtime error")

        result = await process_dispatch_request(
            request=request,
            runtime_cfg=_runtime_cfg(),
            build_report_by_runtime=build_report_by_runtime,
            callback_report=callback_report,
            callback_failed=callback_failed,
        )
        self.assertEqual(result["errorCode"], "judge_timeout")
        self.assertIn("judge_timeout", failed_calls[0][1])

    async def test_process_dispatch_request_should_raise_when_callback_report_error(self) -> None:
        request = _build_request()

        async def build_report_by_runtime(*_args: object, **_kwargs: object) -> _FakeReport:
            return _FakeReport()

        async def callback_failed(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("should not call callback_failed on success path")

        async def callback_report(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("callback report failed")

        with self.assertRaises(HTTPException) as ctx:
            await process_dispatch_request(
                request=request,
                runtime_cfg=_runtime_cfg(),
                build_report_by_runtime=build_report_by_runtime,
                callback_report=callback_report,
                callback_failed=callback_failed,
            )

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("callback report failed", str(ctx.exception.detail))

    async def test_process_dispatch_request_should_return_summary_when_success(self) -> None:
        request = _build_request()
        callback_payloads: list[tuple[int, dict]] = []
        sleep_calls: list[float] = []

        async def build_report_by_runtime(
            req: SimpleNamespace,
            effective_style_mode: str,
            style_mode_source: str,
        ) -> _FakeReport:
            self.assertEqual(req.job.job_id, 42)
            self.assertEqual(effective_style_mode, "rational")
            self.assertEqual(style_mode_source, "system_config")
            return _FakeReport(winner="con", needs_draw_vote=True, provider="openai")

        async def callback_report(job_id: int, payload: dict) -> None:
            callback_payloads.append((job_id, payload))

        async def callback_failed(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("should not call callback_failed on success path")

        async def fake_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        result = await process_dispatch_request(
            request=request,
            runtime_cfg=_runtime_cfg(process_delay_ms=250),
            build_report_by_runtime=build_report_by_runtime,
            callback_report=callback_report,
            callback_failed=callback_failed,
            sleep_fn=fake_sleep,
        )

        self.assertEqual(sleep_calls, [0.25])
        self.assertEqual(callback_payloads[0][0], 42)
        self.assertEqual(result["accepted"], True)
        self.assertEqual(result["winner"], "con")
        self.assertEqual(result["needsDrawVote"], True)
        self.assertEqual(result["provider"], "openai")
        self.assertEqual(result["attemptCount"], 1)
        self.assertEqual(result["retryCount"], 0)

    async def test_process_dispatch_request_should_retry_retryable_error_then_succeed(self) -> None:
        request = _build_request()
        build_attempts = {"n": 0}
        callback_payloads: list[tuple[int, dict]] = []
        failed_calls: list[tuple[int, str]] = []

        async def build_report_by_runtime(*_args: object, **_kwargs: object) -> _FakeReport:
            build_attempts["n"] += 1
            if build_attempts["n"] == 1:
                raise JudgeRuntimeError(code="judge_timeout", message="timeout")
            return _FakeReport(winner="pro", provider="openai")

        async def callback_report(job_id: int, payload: dict) -> None:
            callback_payloads.append((job_id, payload))

        async def callback_failed(job_id: int, error_message: str) -> None:
            failed_calls.append((job_id, error_message))

        result = await process_dispatch_request(
            request=request,
            runtime_cfg=_runtime_cfg(runtime_retry_max_attempts=2, retry_backoff_ms=0),
            build_report_by_runtime=build_report_by_runtime,
            callback_report=callback_report,
            callback_failed=callback_failed,
        )

        self.assertEqual(build_attempts["n"], 2)
        self.assertEqual(len(callback_payloads), 1)
        self.assertEqual(failed_calls, [])
        self.assertEqual(result["winner"], "pro")
        self.assertEqual(result["attemptCount"], 2)
        self.assertEqual(result["retryCount"], 1)

    async def test_process_dispatch_request_should_not_retry_non_retryable_error(self) -> None:
        request = _build_request()
        build_attempts = {"n": 0}
        failed_calls: list[tuple[int, str]] = []

        async def build_report_by_runtime(*_args: object, **_kwargs: object) -> _FakeReport:
            build_attempts["n"] += 1
            raise JudgeRuntimeError(code="consistency_conflict", message="winner mismatch")

        async def callback_failed(job_id: int, error_message: str) -> None:
            failed_calls.append((job_id, error_message))

        async def callback_report(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("should not call callback_report")

        result = await process_dispatch_request(
            request=request,
            runtime_cfg=_runtime_cfg(runtime_retry_max_attempts=3, retry_backoff_ms=0),
            build_report_by_runtime=build_report_by_runtime,
            callback_report=callback_report,
            callback_failed=callback_failed,
        )

        self.assertEqual(build_attempts["n"], 1)
        self.assertEqual(len(failed_calls), 1)
        self.assertEqual(result["status"], "marked_failed")
        self.assertEqual(result["errorCode"], "consistency_conflict")
        self.assertEqual(result["attemptCount"], 1)
        self.assertEqual(result["retryCount"], 0)


if __name__ == "__main__":
    unittest.main()
