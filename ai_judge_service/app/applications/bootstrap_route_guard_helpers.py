from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import HTTPException


def _raise_http_422_from_value_error(*, err: ValueError) -> None:
    raise HTTPException(status_code=422, detail=str(err)) from err


def _raise_http_404_from_lookup_error(*, err: LookupError) -> None:
    raise HTTPException(status_code=404, detail=str(err)) from err


def _raise_http_500_contract_violation(*, err: ValueError, code: str) -> None:
    raise HTTPException(
        status_code=500,
        detail={
            "code": str(code),
            "message": str(err),
        },
    ) from err


def validate_contract_or_raise_http_500_for_runtime(
    *,
    payload: dict[str, Any],
    validate_contract: Callable[[dict[str, Any]], None],
    code: str,
) -> dict[str, Any]:
    try:
        validate_contract(payload)
    except ValueError as err:
        _raise_http_500_contract_violation(err=err, code=code)
    return payload


async def await_payload_or_raise_http_500_for_runtime(
    *,
    self_awaitable: Awaitable[dict[str, Any]],
    code: str,
) -> dict[str, Any]:
    try:
        return await self_awaitable
    except ValueError as err:
        _raise_http_500_contract_violation(err=err, code=code)


async def await_payload_or_raise_http_422_for_runtime(
    *,
    self_awaitable: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    try:
        return await self_awaitable
    except ValueError as err:
        _raise_http_422_from_value_error(err=err)


async def await_payload_or_raise_http_404_for_runtime(
    *,
    self_awaitable: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    try:
        return await self_awaitable
    except LookupError as err:
        _raise_http_404_from_lookup_error(err=err)


async def await_payload_or_raise_http_422_404_for_runtime(
    *,
    self_awaitable: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    try:
        return await self_awaitable
    except ValueError as err:
        _raise_http_422_from_value_error(err=err)
    except LookupError as err:
        _raise_http_404_from_lookup_error(err=err)


def build_payload_or_raise_http_404_for_runtime(
    *,
    builder: Callable[..., dict[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        return builder(**kwargs)
    except LookupError as err:
        _raise_http_404_from_lookup_error(err=err)
