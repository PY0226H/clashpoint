from __future__ import annotations

from typing import Any

from ..domain.judge import (
    build_final_report_payload as build_domain_final_report_payload,
)
from ..domain.judge import (
    validate_final_report_payload_contract as validate_domain_final_report_payload_contract,
)
from ..models import FinalDispatchRequest, PhaseDispatchRequest
from ..phase_pipeline import build_phase_report_payload as build_phase_report_payload_v3
from ..settings import Settings
from .gateway_runtime import GatewayRuntime


def build_final_report_payload(
    *,
    request: FinalDispatchRequest,
    phase_receipts: list[Any],
    judge_style_mode: str,
    fairness_thresholds: dict[str, Any] | None = None,
    panel_runtime_profiles: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return build_domain_final_report_payload(
        request=request,
        phase_receipts=phase_receipts,
        judge_style_mode=judge_style_mode,
        fairness_thresholds=fairness_thresholds,
        panel_runtime_profiles=panel_runtime_profiles,
    )


def validate_final_report_payload_contract(payload: dict[str, Any]) -> list[str]:
    return validate_domain_final_report_payload_contract(payload)


async def build_phase_report_payload(
    *,
    request: PhaseDispatchRequest,
    settings: Settings,
    gateway_runtime: GatewayRuntime,
) -> dict[str, Any]:
    payload = await build_phase_report_payload_v3(
        request=request,
        settings=settings,
        llm_gateway=gateway_runtime.llm,
        knowledge_gateway=gateway_runtime.knowledge,
    )
    if isinstance(payload, dict):
        trace = payload.get("judgeTrace")
        if not isinstance(trace, dict):
            trace = {}
            payload["judgeTrace"] = trace
        trace["gatewayCore"] = gateway_runtime.build_trace_snapshot(
            trace_id=request.trace_id,
            requested_policy_version=request.judge_policy_version,
            requested_retrieval_profile=request.retrieval_profile,
            use_case="judge",
        )
    return payload
