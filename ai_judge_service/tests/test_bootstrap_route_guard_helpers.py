from __future__ import annotations

import unittest

from app.applications.bootstrap_route_guard_helpers import (
    await_payload_or_raise_http_404_for_runtime,
    await_payload_or_raise_http_422_404_for_runtime,
    await_payload_or_raise_http_422_for_runtime,
    await_payload_or_raise_http_500_for_runtime,
    build_payload_or_raise_http_404_for_runtime,
    validate_contract_or_raise_http_500_for_runtime,
)
from fastapi import HTTPException


async def _payload() -> dict[str, object]:
    return {"ok": True}


async def _value_error() -> dict[str, object]:
    raise ValueError("bad_payload")


async def _lookup_error() -> dict[str, object]:
    raise LookupError("missing_payload")


class BootstrapRouteGuardHelpersTests(unittest.IsolatedAsyncioTestCase):
    async def test_validate_contract_should_return_payload_or_raise_500(self) -> None:
        payload = {"ok": True}

        self.assertIs(
            validate_contract_or_raise_http_500_for_runtime(
                payload=payload,
                validate_contract=lambda _payload: None,
                code="contract_bad",
            ),
            payload,
        )

        def _invalid(_payload: dict[str, object]) -> None:
            raise ValueError("contract missing")

        with self.assertRaises(HTTPException) as ctx:
            validate_contract_or_raise_http_500_for_runtime(
                payload=payload,
                validate_contract=_invalid,
                code="contract_bad",
            )

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(
            ctx.exception.detail,
            {"code": "contract_bad", "message": "contract missing"},
        )

    async def test_await_payload_helpers_should_map_value_and_lookup_errors(self) -> None:
        self.assertEqual(
            await await_payload_or_raise_http_500_for_runtime(
                self_awaitable=_payload(),
                code="contract_bad",
            ),
            {"ok": True},
        )

        with self.assertRaises(HTTPException) as ctx_500:
            await await_payload_or_raise_http_500_for_runtime(
                self_awaitable=_value_error(),
                code="contract_bad",
            )
        self.assertEqual(ctx_500.exception.status_code, 500)
        self.assertEqual(ctx_500.exception.detail["code"], "contract_bad")

        with self.assertRaises(HTTPException) as ctx_422:
            await await_payload_or_raise_http_422_for_runtime(
                self_awaitable=_value_error()
            )
        self.assertEqual(ctx_422.exception.status_code, 422)
        self.assertEqual(ctx_422.exception.detail, "bad_payload")

        with self.assertRaises(HTTPException) as ctx_404:
            await await_payload_or_raise_http_404_for_runtime(
                self_awaitable=_lookup_error()
            )
        self.assertEqual(ctx_404.exception.status_code, 404)
        self.assertEqual(ctx_404.exception.detail, "missing_payload")

        with self.assertRaises(HTTPException) as ctx_mixed:
            await await_payload_or_raise_http_422_404_for_runtime(
                self_awaitable=_lookup_error()
            )
        self.assertEqual(ctx_mixed.exception.status_code, 404)

    async def test_build_payload_should_map_lookup_error_to_404(self) -> None:
        self.assertEqual(
            build_payload_or_raise_http_404_for_runtime(
                builder=lambda **kwargs: dict(kwargs),
                case_id=42,
            ),
            {"case_id": 42},
        )

        def _missing(**_kwargs: object) -> dict[str, object]:
            raise LookupError("not_found")

        with self.assertRaises(HTTPException) as ctx:
            build_payload_or_raise_http_404_for_runtime(
                builder=_missing,
                case_id=42,
            )

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "not_found")
