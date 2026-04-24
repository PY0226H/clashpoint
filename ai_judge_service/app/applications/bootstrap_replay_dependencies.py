from __future__ import annotations

from typing import Any, Awaitable, Callable

from ..core.judge_core import JUDGE_CORE_STAGE_REPLAY_COMPUTED, JUDGE_CORE_VERSION
from ..models import FinalDispatchRequest, PhaseDispatchRequest
from .judge_command_routes import (
    resolve_winner as resolve_winner_v3,
)
from .judge_command_routes import (
    safe_float as safe_float_v3,
)
from .judge_command_routes import (
    validate_final_dispatch_request as validate_final_dispatch_request_v3,
)
from .judge_command_routes import (
    validate_phase_dispatch_request as validate_phase_dispatch_request_v3,
)
from .judge_mainline import (
    validate_final_report_payload_contract as validate_final_report_payload_contract_v3,
)
from .judge_trace_replay_routes import (
    ReplayContextDependencyPack,
    ReplayFinalizeDependencyPack,
    ReplayReportDependencyPack,
)
from .judge_trace_replay_routes import (
    build_replay_route_payload as build_replay_route_payload_v3,
)
from .judge_trace_replay_routes import (
    choose_replay_dispatch_receipt as choose_replay_dispatch_receipt_v3,
)
from .judge_trace_replay_routes import (
    extract_replay_request_snapshot as extract_replay_request_snapshot_v3,
)
from .judge_trace_replay_routes import (
    normalize_replay_dispatch_type as normalize_replay_dispatch_type_v3,
)
from .judge_trace_replay_routes import (
    resolve_replay_trace_id as resolve_replay_trace_id_v3,
)
from .replay_audit_ops import build_verdict_contract as build_verdict_contract_v3
from .trust_attestation import attach_report_attestation as attach_report_attestation_v3


def build_replay_dependency_packs(
    *,
    runtime: Any,
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    resolve_policy_profile: Callable[..., Any],
    resolve_prompt_profile: Callable[..., Any],
    resolve_tool_profile: Callable[..., Any],
    build_final_report_payload: Callable[..., dict[str, Any]],
    resolve_panel_runtime_profiles: Callable[..., dict[str, dict[str, Any]]],
    build_phase_report_payload: Callable[..., Awaitable[dict[str, Any]]],
    attach_judge_agent_runtime_trace: Callable[..., Awaitable[None]],
    attach_policy_trace_snapshot: Callable[..., None],
    get_dispatch_receipt: Callable[..., Awaitable[Any | None]],
    list_dispatch_receipts: Callable[..., Awaitable[list[Any]]],
    append_replay_record: Callable[..., Awaitable[Any]],
    workflow_mark_replay: Callable[..., Awaitable[None]],
    upsert_claim_ledger_record: Callable[..., Awaitable[Any | None]],
) -> tuple[
    ReplayContextDependencyPack,
    ReplayReportDependencyPack,
    ReplayFinalizeDependencyPack,
]:
    context_dependencies = ReplayContextDependencyPack(
        normalize_replay_dispatch_type=normalize_replay_dispatch_type_v3,
        get_dispatch_receipt=get_dispatch_receipt,
        choose_replay_dispatch_receipt=choose_replay_dispatch_receipt_v3,
        extract_replay_request_snapshot=extract_replay_request_snapshot_v3,
        resolve_replay_trace_id=resolve_replay_trace_id_v3,
    )
    report_dependencies = ReplayReportDependencyPack(
        ensure_registry_runtime_ready=ensure_registry_runtime_ready,
        final_request_model_validate=FinalDispatchRequest.model_validate,
        phase_request_model_validate=PhaseDispatchRequest.model_validate,
        validate_final_dispatch_request=validate_final_dispatch_request_v3,
        validate_phase_dispatch_request=validate_phase_dispatch_request_v3,
        resolve_policy_profile=resolve_policy_profile,
        resolve_prompt_profile=resolve_prompt_profile,
        resolve_tool_profile=resolve_tool_profile,
        list_dispatch_receipts=list_dispatch_receipts,
        build_final_report_payload=build_final_report_payload,
        resolve_panel_runtime_profiles=resolve_panel_runtime_profiles,
        build_phase_report_payload=build_phase_report_payload,
        attach_judge_agent_runtime_trace=attach_judge_agent_runtime_trace,
        attach_policy_trace_snapshot=attach_policy_trace_snapshot,
        attach_report_attestation=attach_report_attestation_v3,
        validate_final_report_payload_contract=validate_final_report_payload_contract_v3,
        settings=runtime.settings,
        gateway_runtime=runtime.gateway_runtime,
    )
    finalize_dependencies = ReplayFinalizeDependencyPack(
        provider=runtime.settings.provider,
        get_trace=runtime.trace_store.get_trace,
        trace_register_start=runtime.trace_store.register_start,
        trace_mark_replay=runtime.trace_store.mark_replay,
        append_replay_record=append_replay_record,
        workflow_mark_replay=workflow_mark_replay,
        upsert_claim_ledger_record=upsert_claim_ledger_record,
        build_verdict_contract=build_verdict_contract_v3,
        build_replay_route_payload=build_replay_route_payload_v3,
        safe_float=safe_float_v3,
        resolve_winner=resolve_winner_v3,
        draw_margin=0.8,
        judge_core_stage=JUDGE_CORE_STAGE_REPLAY_COMPUTED,
        judge_core_version=JUDGE_CORE_VERSION,
    )
    return context_dependencies, report_dependencies, finalize_dependencies
