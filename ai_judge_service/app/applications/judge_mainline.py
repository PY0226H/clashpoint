from __future__ import annotations

from typing import Any

from ..domain.judge import (
    build_final_report_payload as build_domain_final_report_payload,
)
from ..domain.judge import (
    validate_final_report_payload_contract as validate_domain_final_report_payload_contract,
)
from ..models import FinalDispatchRequest


def build_final_report_payload(
    *,
    request: FinalDispatchRequest,
    phase_receipts: list[Any],
    judge_style_mode: str,
) -> dict[str, Any]:
    return build_domain_final_report_payload(
        request=request,
        phase_receipts=phase_receipts,
        judge_style_mode=judge_style_mode,
    )


def validate_final_report_payload_contract(payload: dict[str, Any]) -> list[str]:
    return validate_domain_final_report_payload_contract(payload)
