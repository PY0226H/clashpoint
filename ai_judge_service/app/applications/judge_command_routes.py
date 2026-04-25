from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable

from pydantic import ValidationError

from ..domain.workflow import WORKFLOW_STATUS_QUEUED, WorkflowJob

_BLIND_SENSITIVE_KEY_TOKENS = {
    "user_id",
    "userid",
    "vip",
    "balance",
    "wallet_balance",
    "is_vip",
}


@dataclass(frozen=True)
class JudgeCommandRouteError(Exception):
    status_code: int
    detail: Any


def _raise_route_error_from_http_exception(err: Exception) -> None:
    status_code = getattr(err, "status_code", None)
    detail = getattr(err, "detail", None)
    if isinstance(status_code, int):
        raise JudgeCommandRouteError(status_code=status_code, detail=detail) from err
    if status_code is not None:
        try:
            normalized_status_code = int(status_code)
        except (TypeError, ValueError):
            return
        raise JudgeCommandRouteError(
            status_code=normalized_status_code,
            detail=detail,
        ) from err


def _normalize_key_token(value: Any) -> str:
    lowered = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return lowered


def _collect_sensitive_key_hits(
    value: Any,
    *,
    path: str,
    out: list[str],
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            key_token = _normalize_key_token(key_text)
            compact = key_token.replace("_", "")
            if (
                key_token in _BLIND_SENSITIVE_KEY_TOKENS
                or compact in _BLIND_SENSITIVE_KEY_TOKENS
            ):
                out.append(f"{path}.{key_text}" if path else key_text)
            next_path = f"{path}.{key_text}" if path else key_text
            _collect_sensitive_key_hits(child, path=next_path, out=out)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            next_path = f"{path}[{index}]" if path else f"[{index}]"
            _collect_sensitive_key_hits(child, path=next_path, out=out)


def find_sensitive_key_hits(payload: Any) -> list[str]:
    out: list[str] = []
    _collect_sensitive_key_hits(payload, path="", out=out)
    dedup: list[str] = []
    seen: set[str] = set()
    for item in out:
        if item in seen:
            continue
        seen.add(item)
        dedup.append(item)
    return dedup


def build_error_contract(
    *,
    error_code: str,
    error_message: str,
    dispatch_type: str,
    trace_id: str,
    retryable: bool,
    category: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": str(error_code or "").strip(),
        "message": str(error_message or "").strip(),
        "dispatchType": str(dispatch_type or "").strip().lower(),
        "traceId": str(trace_id or "").strip(),
        "retryable": bool(retryable),
        "category": str(category or "").strip().lower(),
        "details": dict(details or {}),
    }


def with_error_contract(
    payload: dict[str, Any],
    *,
    error_code: str,
    error_message: str,
    dispatch_type: str,
    trace_id: str,
    retryable: bool,
    category: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(payload)
    out["errorCode"] = str(error_code or "").strip()
    out["errorMessage"] = str(error_message or "").strip()
    out["error"] = build_error_contract(
        error_code=error_code,
        error_message=error_message,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        retryable=retryable,
        category=category,
        details=details,
    )
    return out


def build_failed_callback_payload(
    *,
    case_id: int,
    error_code: str,
    error_message: str,
    dispatch_type: str,
    trace_id: str,
    retryable: bool = False,
    category: str = "failed_callback",
    degradation_level: int | None = None,
    audit_alert_ids: list[str] | None = None,
) -> dict[str, Any]:
    payload = {
        "accepted": False,
        "status": "callback_failed",
        "caseId": case_id,
        "dispatchType": dispatch_type,
        "traceId": trace_id,
        "errorCode": error_code,
        "errorMessage": error_message,
        "auditAlertIds": list(audit_alert_ids or []),
    }
    if degradation_level is not None:
        payload["degradationLevel"] = int(degradation_level)
    payload["error"] = build_error_contract(
        error_code=error_code,
        error_message=error_message,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        retryable=retryable,
        category=category,
    )
    return payload


def extract_raw_field(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload.get(key)
    return None


def extract_optional_int(payload: dict[str, Any], *keys: str) -> int | None:
    value = extract_raw_field(payload, *keys)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_optional_float(payload: dict[str, Any], *keys: str) -> float | None:
    value = extract_raw_field(payload, *keys)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_optional_str(payload: dict[str, Any], *keys: str) -> str | None:
    value = extract_raw_field(payload, *keys)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract_optional_bool(payload: dict[str, Any], *keys: str) -> bool | None:
    value = extract_raw_field(payload, *keys)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    token = str(value).strip().lower()
    if token in {"1", "true", "yes", "on"}:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    return None


def extract_optional_datetime(
    payload: dict[str, Any],
    *keys: str,
    normalize_query_datetime: Callable[[datetime | None], datetime | None] | None = None,
) -> datetime | None:
    value = extract_raw_field(payload, *keys)
    if value is None:
        return None
    if isinstance(value, datetime):
        if normalize_query_datetime is None:
            return value
        return normalize_query_datetime(value)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if normalize_query_datetime is None:
        return parsed
    return normalize_query_datetime(parsed)


def build_dispatch_meta_from_raw(
    payload: dict[str, Any],
    *,
    extract_optional_int: Callable[..., int | None],
    extract_optional_str: Callable[..., str | None],
) -> dict[str, Any]:
    return {
        "caseId": extract_optional_int(payload, "case_id", "caseId"),
        "scopeId": extract_optional_int(payload, "scope_id", "scopeId") or 1,
        "sessionId": extract_optional_int(payload, "session_id", "sessionId"),
        "traceId": extract_optional_str(payload, "trace_id", "traceId") or "",
        "idempotencyKey": extract_optional_str(payload, "idempotency_key", "idempotencyKey")
        or "",
        "rubricVersion": extract_optional_str(payload, "rubric_version", "rubricVersion")
        or "",
        "judgePolicyVersion": extract_optional_str(
            payload,
            "judge_policy_version",
            "judgePolicyVersion",
        )
        or "",
        "topicDomain": extract_optional_str(payload, "topic_domain", "topicDomain") or "",
        "retrievalProfile": extract_optional_str(
            payload,
            "retrieval_profile",
            "retrievalProfile",
        ),
    }


def build_receipt_dims_from_raw(
    dispatch_type: str,
    payload: dict[str, Any],
    *,
    extract_optional_int: Callable[..., int | None],
) -> dict[str, int | None]:
    if dispatch_type == "phase":
        return {
            "phaseNo": extract_optional_int(payload, "phase_no", "phaseNo"),
            "phaseStartNo": None,
            "phaseEndNo": None,
            "messageStartId": extract_optional_int(payload, "message_start_id", "messageStartId"),
            "messageEndId": extract_optional_int(payload, "message_end_id", "messageEndId"),
            "messageCount": extract_optional_int(payload, "message_count", "messageCount"),
        }
    return {
        "phaseNo": None,
        "phaseStartNo": extract_optional_int(payload, "phase_start_no", "phaseStartNo"),
        "phaseEndNo": extract_optional_int(payload, "phase_end_no", "phaseEndNo"),
        "messageStartId": None,
        "messageEndId": None,
        "messageCount": None,
    }


def build_workflow_job(
    *,
    dispatch_type: str,
    job_id: int,
    trace_id: str,
    scope_id: int,
    session_id: int,
    idempotency_key: str,
    rubric_version: str,
    judge_policy_version: str,
    topic_domain: str,
    retrieval_profile: str | None,
) -> WorkflowJob:
    return WorkflowJob(
        job_id=max(0, int(job_id)),
        dispatch_type=str(dispatch_type or "").strip().lower(),
        trace_id=str(trace_id or "").strip(),
        status=WORKFLOW_STATUS_QUEUED,
        scope_id=max(0, int(scope_id)),
        session_id=max(0, int(session_id)),
        idempotency_key=str(idempotency_key or "").strip(),
        rubric_version=str(rubric_version or "").strip(),
        judge_policy_version=str(judge_policy_version or "").strip(),
        topic_domain=str(topic_domain or "").strip().lower() or "default",
        retrieval_profile=(
            str(retrieval_profile).strip()
            if retrieval_profile is not None and str(retrieval_profile).strip()
            else None
        ),
    )


def resolve_idempotency_or_raise(
    *,
    resolve_idempotency: Callable[..., Any],
    key: str,
    job_id: int,
    ttl_secs: int,
    conflict_detail: str,
) -> dict[str, Any] | None:
    resolution = resolve_idempotency(
        key=key,
        job_id=job_id,
        ttl_secs=ttl_secs,
    )
    if resolution.status == "replay" and resolution.record and resolution.record.response:
        replayed = dict(resolution.record.response)
        replayed["idempotentReplay"] = True
        return replayed
    if resolution.status != "acquired":
        raise JudgeCommandRouteError(status_code=409, detail=conflict_detail)
    return None


def validate_phase_dispatch_request(request: Any) -> None:
    if request.message_count <= 0:
        raise JudgeCommandRouteError(status_code=422, detail="invalid_message_count")
    if request.message_end_id < request.message_start_id:
        raise JudgeCommandRouteError(status_code=422, detail="invalid_message_range")
    if request.message_count != len(request.messages):
        raise JudgeCommandRouteError(status_code=422, detail="message_count_mismatch")
    for message in request.messages:
        if (
            message.message_id < request.message_start_id
            or message.message_id > request.message_end_id
        ):
            raise JudgeCommandRouteError(status_code=422, detail="message_id_out_of_range")


def validate_final_dispatch_request(request: Any) -> None:
    if request.phase_start_no <= 0 or request.phase_end_no <= 0:
        raise JudgeCommandRouteError(status_code=422, detail="invalid_phase_no")
    if request.phase_start_no > request.phase_end_no:
        raise JudgeCommandRouteError(status_code=422, detail="invalid_phase_range")


def resolve_failed_callback_fn_for_dispatch(
    *,
    dispatch_type: str,
    callback_phase_failed_fn: Any,
    callback_final_failed_fn: Any,
) -> Any:
    return callback_phase_failed_fn if dispatch_type == "phase" else callback_final_failed_fn


def resolve_report_callback_fn_for_dispatch(
    *,
    dispatch_type: str,
    callback_phase_report_fn: Any,
    callback_final_report_fn: Any,
) -> Any:
    return callback_phase_report_fn if dispatch_type == "phase" else callback_final_report_fn


async def invoke_callback_with_retry(
    *,
    callback_fn: Callable[[int, dict[str, Any]], Awaitable[Any]],
    job_id: int,
    payload: dict[str, Any],
    max_attempts: int,
    backoff_ms: int,
    sleep_fn: Callable[[float], Awaitable[None]],
) -> tuple[int, int]:
    normalized_max_attempts = max(1, int(max_attempts))
    normalized_backoff_ms = max(0, int(backoff_ms))
    attempt = 0
    last_error: Exception | None = None
    while attempt < normalized_max_attempts:
        attempt += 1
        try:
            await callback_fn(job_id, payload)
            return attempt, max(0, attempt - 1)
        except Exception as err:
            last_error = err
            if attempt >= normalized_max_attempts:
                break
            if normalized_backoff_ms > 0:
                await sleep_fn((normalized_backoff_ms * attempt) / 1000.0)
    raise RuntimeError(
        f"v3 callback failed after {normalized_max_attempts} attempts: {last_error or 'unknown'}"
    ) from last_error


def save_dispatch_receipt(
    *,
    save_dispatch_receipt_fn: Callable[..., Any],
    dispatch_type: str,
    job_id: int,
    scope_id: int,
    session_id: int,
    trace_id: str,
    idempotency_key: str,
    rubric_version: str,
    judge_policy_version: str,
    topic_domain: str,
    retrieval_profile: str | None,
    phase_no: int | None,
    phase_start_no: int | None,
    phase_end_no: int | None,
    message_start_id: int | None,
    message_end_id: int | None,
    message_count: int | None,
    status: str,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any] | None,
) -> None:
    save_dispatch_receipt_fn(
        dispatch_type=dispatch_type,
        job_id=job_id,
        scope_id=scope_id,
        session_id=session_id,
        trace_id=trace_id,
        idempotency_key=idempotency_key,
        rubric_version=rubric_version,
        judge_policy_version=judge_policy_version,
        topic_domain=topic_domain,
        retrieval_profile=retrieval_profile,
        phase_no=phase_no,
        phase_start_no=phase_start_no,
        phase_end_no=phase_end_no,
        message_start_id=message_start_id,
        message_end_id=message_end_id,
        message_count=message_count,
        status=status,
        request=request_payload,
        response=response_payload,
    )


def safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def resolve_winner(pro_score: float, con_score: float, *, margin: float = 1.0) -> str:
    if pro_score - con_score >= margin:
        return "pro"
    if con_score - pro_score >= margin:
        return "con"
    return "draw"


def build_final_report_payload_for_dispatch(
    *,
    request: Any,
    phase_receipts: list[Any] | None,
    fairness_thresholds: dict[str, Any] | None,
    panel_runtime_profiles: dict[str, dict[str, Any]] | None,
    list_dispatch_receipts: Callable[..., list[Any]],
    build_final_report_payload: Callable[..., dict[str, Any]],
    judge_style_mode: str,
) -> dict[str, Any]:
    receipts = (
        phase_receipts
        if phase_receipts is not None
        else list_dispatch_receipts(
            dispatch_type="phase",
            session_id=request.session_id,
            status="reported",
            limit=1000,
        )
    )
    return build_final_report_payload(
        request=request,
        phase_receipts=list(receipts),
        judge_style_mode=judge_style_mode,
        fairness_thresholds=fairness_thresholds,
        panel_runtime_profiles=panel_runtime_profiles,
    )


def resolve_policy_profile_or_raise(
    *,
    resolve_policy_profile: Callable[..., Any],
    judge_policy_version: str,
    rubric_version: str,
    topic_domain: str,
) -> Any:
    outcome = resolve_policy_profile(
        requested_version=judge_policy_version,
        rubric_version=rubric_version,
        topic_domain=topic_domain,
    )
    profile = getattr(outcome, "profile", None)
    if profile is not None:
        return profile
    error_code = getattr(outcome, "error_code", None)
    raise JudgeCommandRouteError(
        status_code=422,
        detail=error_code or "judge_policy_invalid",
    )


def resolve_prompt_profile_or_raise(
    *,
    get_prompt_profile: Callable[[str], Any | None],
    prompt_registry_version: str,
) -> Any:
    profile = get_prompt_profile(prompt_registry_version)
    if profile is not None:
        return profile
    raise JudgeCommandRouteError(
        status_code=422,
        detail="unknown_prompt_registry_version",
    )


def resolve_tool_profile_or_raise(
    *,
    get_tool_profile: Callable[[str], Any | None],
    tool_registry_version: str,
) -> Any:
    profile = get_tool_profile(tool_registry_version)
    if profile is not None:
        return profile
    raise JudgeCommandRouteError(
        status_code=422,
        detail="unknown_tool_registry_version",
    )


def attach_policy_trace_snapshot(
    *,
    report_payload: Any,
    profile: Any,
    prompt_profile: Any,
    tool_profile: Any,
    build_policy_trace_snapshot: Callable[[Any], dict[str, Any]],
    build_prompt_trace_snapshot: Callable[[Any], dict[str, Any]],
    build_tool_trace_snapshot: Callable[[Any], dict[str, Any]],
) -> None:
    if not isinstance(report_payload, dict):
        return
    judge_trace = report_payload.get("judgeTrace")
    if not isinstance(judge_trace, dict):
        judge_trace = {}
        report_payload["judgeTrace"] = judge_trace
    judge_trace["policyRegistry"] = build_policy_trace_snapshot(profile)
    judge_trace["promptRegistry"] = build_prompt_trace_snapshot(prompt_profile)
    judge_trace["toolRegistry"] = build_tool_trace_snapshot(tool_profile)
    judge_trace["registryVersions"] = {
        "policyVersion": str(getattr(profile, "version", "") or "").strip(),
        "promptVersion": str(getattr(prompt_profile, "version", "") or "").strip(),
        "toolsetVersion": str(getattr(tool_profile, "version", "") or "").strip(),
    }


def resolve_panel_runtime_profiles(
    *,
    profile: Any,
    panel_judge_ids: tuple[str, ...] | list[str],
    panel_runtime_profile_defaults: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    def _normalize_text_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        seen: set[str] = set()
        for item in value:
            token = str(item or "").strip()
            if not token or token in seen:
                continue
            seen.add(token)
            out.append(token)
        return out

    def _to_bool(value: Any, *, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
        return default

    prompt_versions = (
        getattr(profile, "prompt_versions", None)
        if isinstance(getattr(profile, "prompt_versions", None), dict)
        else {}
    )
    metadata = (
        getattr(profile, "metadata", None)
        if isinstance(getattr(profile, "metadata", None), dict)
        else {}
    )
    raw_profiles = metadata.get("panelRuntimeProfiles")
    if not isinstance(raw_profiles, dict):
        raw_profiles = metadata.get("panel_runtime_profiles")
    runtime_context = metadata.get("panelRuntimeContext")
    if not isinstance(runtime_context, dict):
        runtime_context = metadata.get("panel_runtime_context")
    runtime_context = runtime_context if isinstance(runtime_context, dict) else {}
    normalized: dict[str, dict[str, Any]] = {}
    policy_version = str(getattr(profile, "version", "") or "").strip()
    toolset_version = str(getattr(profile, "tool_registry_version", "") or "").strip()
    raw_topic_domain = str(getattr(profile, "topic_domain", "") or "").strip().lower()
    topic_domain = raw_topic_domain if raw_topic_domain not in {"", "*"} else "general"
    default_domain_slot = (
        str(
            runtime_context.get("defaultDomainSlot")
            or runtime_context.get("default_domain_slot")
            or ""
        ).strip()
        or topic_domain
    )
    default_runtime_stage = (
        str(
            runtime_context.get("runtimeStage")
            or runtime_context.get("runtime_stage")
            or "bootstrap"
        ).strip()
        or "bootstrap"
    )
    default_adaptive_enabled = _to_bool(
        runtime_context.get("adaptiveEnabled")
        if runtime_context.get("adaptiveEnabled") is not None
        else runtime_context.get("adaptive_enabled"),
        default=False,
    )
    default_candidate_models = _normalize_text_list(
        runtime_context.get("candidateModels")
        if runtime_context.get("candidateModels") is not None
        else runtime_context.get("candidate_models")
    )
    default_strategy_metadata = (
        dict(runtime_context.get("strategyMetadata"))
        if isinstance(runtime_context.get("strategyMetadata"), dict)
        else (
            dict(runtime_context.get("strategy_metadata"))
            if isinstance(runtime_context.get("strategy_metadata"), dict)
            else {}
        )
    )
    default_shadow_enabled = _to_bool(
        runtime_context.get("shadowEnabled")
        if runtime_context.get("shadowEnabled") is not None
        else runtime_context.get("shadow_enabled"),
        default=False,
    )
    default_shadow_model_strategy = str(
        runtime_context.get("shadowModelStrategy")
        or runtime_context.get("shadow_model_strategy")
        or ""
    ).strip()
    default_shadow_cost_estimate = safe_float(
        runtime_context.get("shadowCostEstimate")
        if runtime_context.get("shadowCostEstimate") is not None
        else runtime_context.get("shadow_cost_estimate"),
        default=0.0,
    )
    default_shadow_latency_estimate = safe_float(
        runtime_context.get("shadowLatencyEstimate")
        if runtime_context.get("shadowLatencyEstimate") is not None
        else runtime_context.get("shadow_latency_estimate"),
        default=0.0,
    )

    for judge_id in panel_judge_ids:
        defaults = panel_runtime_profile_defaults[judge_id]
        raw_row = raw_profiles.get(judge_id) if isinstance(raw_profiles, dict) else None
        row = raw_row if isinstance(raw_row, dict) else {}
        prompt_version_key = defaults["promptVersionKey"]
        prompt_version = str(
            row.get("promptVersion")
            or row.get("prompt_version")
            or prompt_versions.get(prompt_version_key)
            or ""
        ).strip()
        normalized[judge_id] = {
            "judgeId": judge_id,
            "profileId": str(
                row.get("profileId")
                or row.get("profile_id")
                or defaults["profileId"]
            ).strip()
            or defaults["profileId"],
            "modelStrategy": str(
                row.get("modelStrategy")
                or row.get("model_strategy")
                or defaults["modelStrategy"]
            ).strip()
            or defaults["modelStrategy"],
            "strategySlot": str(
                row.get("strategySlot")
                or row.get("strategy_slot")
                or defaults["strategySlot"]
            ).strip()
            or defaults["strategySlot"],
            "scoreSource": str(
                row.get("scoreSource")
                or row.get("score_source")
                or defaults["scoreSource"]
            ).strip()
            or defaults["scoreSource"],
            "decisionMargin": safe_float(
                row.get("decisionMargin") or row.get("decision_margin"),
                default=float(defaults["decisionMargin"]),
            ),
            "promptVersion": prompt_version or None,
            "toolsetVersion": (
                str(row.get("toolsetVersion") or row.get("toolset_version") or "").strip()
                or toolset_version
                or None
            ),
            "policyVersion": policy_version or None,
            "domainSlot": str(
                row.get("domainSlot")
                or row.get("domain_slot")
                or default_domain_slot
                or defaults["domainSlot"]
            ).strip()
            or default_domain_slot
            or defaults["domainSlot"],
            "runtimeStage": str(
                row.get("runtimeStage")
                or row.get("runtime_stage")
                or default_runtime_stage
                or defaults["runtimeStage"]
            ).strip()
            or default_runtime_stage
            or defaults["runtimeStage"],
            "adaptiveEnabled": _to_bool(
                row.get("adaptiveEnabled")
                if row.get("adaptiveEnabled") is not None
                else row.get("adaptive_enabled"),
                default=default_adaptive_enabled,
            ),
            "candidateModels": (
                _normalize_text_list(
                    row.get("candidateModels")
                    if row.get("candidateModels") is not None
                    else row.get("candidate_models")
                )
                or list(default_candidate_models)
            ),
            "strategyMetadata": (
                dict(row.get("strategyMetadata"))
                if isinstance(row.get("strategyMetadata"), dict)
                else (
                    dict(row.get("strategy_metadata"))
                    if isinstance(row.get("strategy_metadata"), dict)
                    else dict(default_strategy_metadata)
                )
            ),
            "shadowEnabled": _to_bool(
                row.get("shadowEnabled")
                if row.get("shadowEnabled") is not None
                else row.get("shadow_enabled"),
                default=default_shadow_enabled,
            ),
            "shadowModelStrategy": (
                str(
                    row.get("shadowModelStrategy")
                    or row.get("shadow_model_strategy")
                    or default_shadow_model_strategy
                    or row.get("modelStrategy")
                    or row.get("model_strategy")
                    or defaults["modelStrategy"]
                ).strip()
                or defaults["modelStrategy"]
            ),
            "shadowCostEstimate": safe_float(
                row.get("shadowCostEstimate")
                if row.get("shadowCostEstimate") is not None
                else row.get("shadow_cost_estimate"),
                default=default_shadow_cost_estimate,
            ),
            "shadowLatencyEstimate": safe_float(
                row.get("shadowLatencyEstimate")
                if row.get("shadowLatencyEstimate") is not None
                else row.get("shadow_latency_estimate"),
                default=default_shadow_latency_estimate,
            ),
            # 这里显式记录来源，便于重放时判断是策略配置还是默认值导致的分歧。
            "profileSource": "policy_metadata" if row else "builtin_default",
        }
    return normalized


async def build_case_create_route_payload(
    *,
    raw_payload: dict[str, Any],
    case_create_model_validate: Callable[[dict[str, Any]], Any],
    resolve_idempotency_or_raise: Callable[..., dict[str, Any] | None],
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    resolve_policy_profile: Callable[..., Any],
    resolve_prompt_profile: Callable[..., Any],
    resolve_tool_profile: Callable[..., Any],
    workflow_get_job: Callable[..., Awaitable[Any | None]],
    build_workflow_job: Callable[..., Any],
    workflow_register_and_mark_case_built: Callable[..., Awaitable[Any]],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
    trace_register_start: Callable[..., Any],
    trace_register_success: Callable[..., Any],
    build_trace_report_summary: Callable[..., dict[str, Any]],
    set_idempotency_success: Callable[..., Any],
    idempotency_ttl_secs: int,
) -> dict[str, Any]:
    try:
        parsed = case_create_model_validate(raw_payload)
    except ValidationError as err:
        raise JudgeCommandRouteError(status_code=422, detail=err.errors()) from err

    replayed = resolve_idempotency_or_raise(
        key=parsed.idempotency_key,
        job_id=parsed.case_id,
        conflict_detail="idempotency_conflict:case_create",
    )
    if replayed is not None:
        return replayed

    await ensure_registry_runtime_ready()
    policy_profile = resolve_policy_profile(
        judge_policy_version=parsed.judge_policy_version,
        rubric_version=parsed.rubric_version,
        topic_domain=parsed.topic_domain,
    )
    prompt_profile = resolve_prompt_profile(
        prompt_registry_version=policy_profile.prompt_registry_version,
    )
    tool_profile = resolve_tool_profile(
        tool_registry_version=policy_profile.tool_registry_version,
    )

    existing_job = await workflow_get_job(job_id=parsed.case_id)
    if existing_job is not None:
        raise JudgeCommandRouteError(status_code=409, detail="case_already_exists")

    request_payload = parsed.model_dump(mode="json")
    workflow_job = build_workflow_job(
        dispatch_type="phase",
        job_id=parsed.case_id,
        trace_id=parsed.trace_id,
        scope_id=parsed.scope_id,
        session_id=parsed.session_id,
        idempotency_key=parsed.idempotency_key,
        rubric_version=parsed.rubric_version,
        judge_policy_version=parsed.judge_policy_version,
        topic_domain=parsed.topic_domain,
        retrieval_profile=parsed.retrieval_profile,
    )
    transitioned_job = await workflow_register_and_mark_case_built(
        job=workflow_job,
        event_payload={
            "dispatchType": "case",
            "scopeId": parsed.scope_id,
            "sessionId": parsed.session_id,
            "traceId": parsed.trace_id,
            "policyVersion": policy_profile.version,
            "promptVersion": prompt_profile.version,
            "toolsetVersion": tool_profile.version,
            "caseStatus": "case_built",
        },
    )
    response = {
        "accepted": True,
        "status": "case_built",
        "caseId": parsed.case_id,
        "scopeId": parsed.scope_id,
        "sessionId": parsed.session_id,
        "traceId": parsed.trace_id,
        "idempotencyKey": parsed.idempotency_key,
        "registryVersions": {
            "policyVersion": policy_profile.version,
            "promptVersion": prompt_profile.version,
            "toolsetVersion": tool_profile.version,
        },
        "workflow": serialize_workflow_job(transitioned_job),
    }
    trace_register_start(
        job_id=parsed.case_id,
        trace_id=parsed.trace_id,
        request=request_payload,
    )
    trace_register_success(
        job_id=parsed.case_id,
        response=response,
        callback_status="case_built",
        report_summary=build_trace_report_summary(
            dispatch_type="case",
            payload={},
            callback_status="case_built",
            callback_error=None,
        ),
    )
    set_idempotency_success(
        key=parsed.idempotency_key,
        job_id=parsed.case_id,
        response=response,
        ttl_secs=idempotency_ttl_secs,
    )
    return response


async def build_phase_dispatch_preflight_route_payload(
    *,
    raw_payload: dict[str, Any],
    phase_dispatch_model_validate: Callable[[dict[str, Any]], Any],
    validate_phase_dispatch_request: Callable[[Any], None],
    resolve_idempotency_or_raise: Callable[..., dict[str, Any] | None],
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    resolve_policy_profile: Callable[..., Any],
    resolve_prompt_profile: Callable[..., Any],
    resolve_tool_profile: Callable[..., Any],
    build_phase_dispatch_accepted_response: Callable[..., dict[str, Any]],
    build_workflow_job: Callable[..., Any],
    trace_register_start: Callable[..., Any],
    persist_dispatch_receipt: Callable[..., Awaitable[Any]],
    workflow_register_and_mark_blinded: Callable[..., Awaitable[Any]],
    build_phase_workflow_register_payload: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    try:
        parsed = phase_dispatch_model_validate(raw_payload)
    except ValidationError as err:
        raise JudgeCommandRouteError(status_code=422, detail=err.errors()) from err

    try:
        validate_phase_dispatch_request(parsed)
    except Exception as err:
        _raise_route_error_from_http_exception(err)
        raise

    replayed = resolve_idempotency_or_raise(
        key=parsed.idempotency_key,
        job_id=parsed.case_id,
        conflict_detail="idempotency_conflict:phase_dispatch",
    )
    if replayed is not None:
        return {"replayedResponse": replayed}

    await ensure_registry_runtime_ready()
    policy_profile = resolve_policy_profile(
        judge_policy_version=parsed.judge_policy_version,
        rubric_version=parsed.rubric_version,
        topic_domain=parsed.topic_domain,
    )
    prompt_profile = resolve_prompt_profile(
        prompt_registry_version=policy_profile.prompt_registry_version,
    )
    tool_profile = resolve_tool_profile(
        tool_registry_version=policy_profile.tool_registry_version,
    )

    response = build_phase_dispatch_accepted_response(request=parsed)
    request_payload = parsed.model_dump(mode="json")
    workflow_job = build_workflow_job(
        dispatch_type="phase",
        job_id=parsed.case_id,
        trace_id=parsed.trace_id,
        scope_id=parsed.scope_id,
        session_id=parsed.session_id,
        idempotency_key=parsed.idempotency_key,
        rubric_version=parsed.rubric_version,
        judge_policy_version=parsed.judge_policy_version,
        topic_domain=parsed.topic_domain,
        retrieval_profile=parsed.retrieval_profile,
    )
    trace_register_start(
        job_id=parsed.case_id,
        trace_id=parsed.trace_id,
        request=request_payload,
    )
    await persist_dispatch_receipt(
        dispatch_type="phase",
        job_id=parsed.case_id,
        scope_id=parsed.scope_id,
        session_id=parsed.session_id,
        trace_id=parsed.trace_id,
        idempotency_key=parsed.idempotency_key,
        rubric_version=parsed.rubric_version,
        judge_policy_version=parsed.judge_policy_version,
        topic_domain=parsed.topic_domain,
        retrieval_profile=parsed.retrieval_profile,
        phase_no=parsed.phase_no,
        phase_start_no=None,
        phase_end_no=None,
        message_start_id=parsed.message_start_id,
        message_end_id=parsed.message_end_id,
        message_count=parsed.message_count,
        status="queued",
        request_payload=request_payload,
        response_payload=response,
    )
    await workflow_register_and_mark_blinded(
        job=workflow_job,
        event_payload=build_phase_workflow_register_payload(
            request=parsed,
            policy_version=policy_profile.version,
            prompt_version=prompt_profile.version,
            toolset_version=tool_profile.version,
        ),
    )
    return {
        "parsed": parsed,
        "response": response,
        "requestPayload": request_payload,
        "policyProfile": policy_profile,
        "promptProfile": prompt_profile,
        "toolProfile": tool_profile,
    }


async def build_final_dispatch_preflight_route_payload(
    *,
    raw_payload: dict[str, Any],
    final_dispatch_model_validate: Callable[[dict[str, Any]], Any],
    validate_final_dispatch_request: Callable[[Any], None],
    resolve_idempotency_or_raise: Callable[..., dict[str, Any] | None],
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    resolve_policy_profile: Callable[..., Any],
    resolve_prompt_profile: Callable[..., Any],
    resolve_tool_profile: Callable[..., Any],
    build_final_dispatch_accepted_response: Callable[..., dict[str, Any]],
    build_workflow_job: Callable[..., Any],
    trace_register_start: Callable[..., Any],
    persist_dispatch_receipt: Callable[..., Awaitable[Any]],
    workflow_register_and_mark_blinded: Callable[..., Awaitable[Any]],
    build_final_workflow_register_payload: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    try:
        parsed = final_dispatch_model_validate(raw_payload)
    except ValidationError as err:
        raise JudgeCommandRouteError(status_code=422, detail=err.errors()) from err

    try:
        validate_final_dispatch_request(parsed)
    except Exception as err:
        _raise_route_error_from_http_exception(err)
        raise

    replayed = resolve_idempotency_or_raise(
        key=parsed.idempotency_key,
        job_id=parsed.case_id,
        conflict_detail="idempotency_conflict:final_dispatch",
    )
    if replayed is not None:
        return {"replayedResponse": replayed}

    await ensure_registry_runtime_ready()
    policy_profile = resolve_policy_profile(
        judge_policy_version=parsed.judge_policy_version,
        rubric_version=parsed.rubric_version,
        topic_domain=parsed.topic_domain,
    )
    prompt_profile = resolve_prompt_profile(
        prompt_registry_version=policy_profile.prompt_registry_version,
    )
    tool_profile = resolve_tool_profile(
        tool_registry_version=policy_profile.tool_registry_version,
    )

    response = build_final_dispatch_accepted_response(request=parsed)
    request_payload = parsed.model_dump(mode="json")
    workflow_job = build_workflow_job(
        dispatch_type="final",
        job_id=parsed.case_id,
        trace_id=parsed.trace_id,
        scope_id=parsed.scope_id,
        session_id=parsed.session_id,
        idempotency_key=parsed.idempotency_key,
        rubric_version=parsed.rubric_version,
        judge_policy_version=parsed.judge_policy_version,
        topic_domain=parsed.topic_domain,
        retrieval_profile=None,
    )
    trace_register_start(
        job_id=parsed.case_id,
        trace_id=parsed.trace_id,
        request=request_payload,
    )
    await persist_dispatch_receipt(
        dispatch_type="final",
        job_id=parsed.case_id,
        scope_id=parsed.scope_id,
        session_id=parsed.session_id,
        trace_id=parsed.trace_id,
        idempotency_key=parsed.idempotency_key,
        rubric_version=parsed.rubric_version,
        judge_policy_version=parsed.judge_policy_version,
        topic_domain=parsed.topic_domain,
        retrieval_profile=None,
        phase_no=None,
        phase_start_no=parsed.phase_start_no,
        phase_end_no=parsed.phase_end_no,
        message_start_id=None,
        message_end_id=None,
        message_count=None,
        status="queued",
        request_payload=request_payload,
        response_payload=response,
    )
    await workflow_register_and_mark_blinded(
        job=workflow_job,
        event_payload=build_final_workflow_register_payload(
            request=parsed,
            policy_version=policy_profile.version,
            prompt_version=prompt_profile.version,
            toolset_version=tool_profile.version,
        ),
    )
    return {
        "parsed": parsed,
        "response": response,
        "requestPayload": request_payload,
        "policyProfile": policy_profile,
        "promptProfile": prompt_profile,
        "toolProfile": tool_profile,
    }


async def build_blindization_rejection_route_payload(
    *,
    dispatch_type: str,
    raw_payload: dict[str, Any],
    sensitive_hits: list[str],
    extract_dispatch_meta_from_raw: Callable[[dict[str, Any]], dict[str, Any]],
    extract_receipt_dims_from_raw: Callable[[str, dict[str, Any]], dict[str, int | None]],
    build_workflow_job: Callable[..., Any],
    trace_register_start: Callable[..., Any],
    workflow_register_and_mark_blinded: Callable[..., Awaitable[Any]],
    build_failed_callback_payload: Callable[..., dict[str, Any]],
    invoke_failed_callback_with_retry: Callable[..., Awaitable[tuple[int, int]]],
    with_error_contract: Callable[..., dict[str, Any]],
    persist_dispatch_receipt: Callable[..., Awaitable[Any]],
    trace_register_failure: Callable[..., Any],
    workflow_mark_failed: Callable[..., Awaitable[Any]],
) -> dict[str, Any]:
    meta = extract_dispatch_meta_from_raw(raw_payload)
    job_id = int(meta.get("caseId") or 0)
    session_id = int(meta.get("sessionId") or 0)
    trace_id = str(meta.get("traceId") or "")
    if job_id <= 0 or session_id <= 0 or not trace_id:
        raise JudgeCommandRouteError(status_code=422, detail="input_not_blinded")

    scope_id = int(meta.get("scopeId") or 1)
    dims = extract_receipt_dims_from_raw(dispatch_type, raw_payload)
    request_payload = dict(raw_payload)
    workflow_job = build_workflow_job(
        dispatch_type=dispatch_type,
        job_id=job_id,
        trace_id=trace_id,
        scope_id=scope_id,
        session_id=session_id,
        idempotency_key=str(meta.get("idempotencyKey") or ""),
        rubric_version=str(meta.get("rubricVersion") or ""),
        judge_policy_version=str(meta.get("judgePolicyVersion") or ""),
        topic_domain=str(meta.get("topicDomain") or ""),
        retrieval_profile=(
            str(meta.get("retrievalProfile"))
            if meta.get("retrievalProfile") is not None
            else None
        ),
    )
    trace_register_start(
        job_id=job_id,
        trace_id=trace_id,
        request=request_payload,
    )
    await workflow_register_and_mark_blinded(
        job=workflow_job,
        event_payload={
            "dispatchType": dispatch_type,
            "scopeId": scope_id,
            "sessionId": session_id,
            "phaseNo": dims.get("phaseNo"),
            "phaseStartNo": dims.get("phaseStartNo"),
            "phaseEndNo": dims.get("phaseEndNo"),
            "messageCount": dims.get("messageCount"),
            "traceId": trace_id,
            "rejectionCode": "input_not_blinded",
            "sensitiveHits": sensitive_hits[:12],
        },
    )
    response = {
        "accepted": False,
        "dispatchType": dispatch_type,
        "status": "callback_failed",
        "caseId": job_id,
        "scopeId": scope_id,
        "sessionId": session_id,
        "traceId": trace_id,
    }
    if dispatch_type == "phase":
        response["phaseNo"] = dims.get("phaseNo")
        response["messageCount"] = dims.get("messageCount")
    else:
        response["phaseStartNo"] = dims.get("phaseStartNo")
        response["phaseEndNo"] = dims.get("phaseEndNo")

    error_code = "input_not_blinded"
    error_message = "sensitive fields detected in judge input: " + ",".join(sensitive_hits[:12])
    failed_payload = build_failed_callback_payload(
        case_id=job_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        error_code=error_code,
        error_message=error_message,
    )
    try:
        failed_attempts, failed_retries = await invoke_failed_callback_with_retry(
            case_id=job_id,
            payload=failed_payload,
        )
    except Exception as failed_err:
        receipt_response = with_error_contract(
            {
                **response,
                "callbackStatus": "failed_callback_failed",
                "callbackError": error_message,
                "failedCallbackPayload": failed_payload,
                "failedCallbackError": str(failed_err),
            },
            error_code=f"{dispatch_type}_failed_callback_failed",
            error_message=str(failed_err),
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            retryable=False,
            category="blindization_rejection",
            details={"sensitiveHits": sensitive_hits[:12]},
        )
        await persist_dispatch_receipt(
            dispatch_type=dispatch_type,
            job_id=job_id,
            scope_id=scope_id,
            session_id=session_id,
            trace_id=trace_id,
            idempotency_key=str(meta.get("idempotencyKey") or ""),
            rubric_version=str(meta.get("rubricVersion") or ""),
            judge_policy_version=str(meta.get("judgePolicyVersion") or ""),
            topic_domain=str(meta.get("topicDomain") or ""),
            retrieval_profile=(
                str(meta.get("retrievalProfile"))
                if meta.get("retrievalProfile") is not None
                else None
            ),
            phase_no=dims.get("phaseNo"),
            phase_start_no=dims.get("phaseStartNo"),
            phase_end_no=dims.get("phaseEndNo"),
            message_start_id=dims.get("messageStartId"),
            message_end_id=dims.get("messageEndId"),
            message_count=dims.get("messageCount"),
            status="callback_failed",
            request_payload=request_payload,
            response_payload=receipt_response,
        )
        trace_register_failure(
            job_id=job_id,
            response=receipt_response,
            callback_status="failed_callback_failed",
            callback_error=str(failed_err),
        )
        await workflow_mark_failed(
            job_id=job_id,
            error_code=f"{dispatch_type}_failed_callback_failed",
            error_message=str(failed_err),
            event_payload={
                "dispatchType": dispatch_type,
                "phaseNo": dims.get("phaseNo"),
                "phaseStartNo": dims.get("phaseStartNo"),
                "phaseEndNo": dims.get("phaseEndNo"),
                "callbackStatus": "failed_callback_failed",
                "sensitiveHits": sensitive_hits[:12],
            },
        )
        raise JudgeCommandRouteError(
            status_code=502,
            detail=f"{dispatch_type}_failed_callback_failed: {failed_err}",
        ) from failed_err

    receipt_response = with_error_contract(
        {
            **response,
            "callbackStatus": "failed_reported",
            "callbackError": error_message,
            "failedCallbackPayload": failed_payload,
            "failedCallbackAttempts": failed_attempts,
            "failedCallbackRetries": failed_retries,
        },
        error_code=error_code,
        error_message=error_message,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        retryable=False,
        category="blindization_rejection",
        details={"sensitiveHits": sensitive_hits[:12]},
    )
    await persist_dispatch_receipt(
        dispatch_type=dispatch_type,
        job_id=job_id,
        scope_id=scope_id,
        session_id=session_id,
        trace_id=trace_id,
        idempotency_key=str(meta.get("idempotencyKey") or ""),
        rubric_version=str(meta.get("rubricVersion") or ""),
        judge_policy_version=str(meta.get("judgePolicyVersion") or ""),
        topic_domain=str(meta.get("topicDomain") or ""),
        retrieval_profile=(
            str(meta.get("retrievalProfile"))
            if meta.get("retrievalProfile") is not None
            else None
        ),
        phase_no=dims.get("phaseNo"),
        phase_start_no=dims.get("phaseStartNo"),
        phase_end_no=dims.get("phaseEndNo"),
        message_start_id=dims.get("messageStartId"),
        message_end_id=dims.get("messageEndId"),
        message_count=dims.get("messageCount"),
        status="callback_failed",
        request_payload=request_payload,
        response_payload=receipt_response,
    )
    trace_register_failure(
        job_id=job_id,
        response=receipt_response,
        callback_status="failed_reported",
        callback_error=error_message,
    )
    await workflow_mark_failed(
        job_id=job_id,
        error_code=error_code,
        error_message=error_message,
        event_payload={
            "dispatchType": dispatch_type,
            "phaseNo": dims.get("phaseNo"),
            "phaseStartNo": dims.get("phaseStartNo"),
            "phaseEndNo": dims.get("phaseEndNo"),
            "callbackStatus": "failed_reported",
            "sensitiveHits": sensitive_hits[:12],
        },
    )
    raise JudgeCommandRouteError(status_code=422, detail=error_code)


async def build_phase_dispatch_report_materialization_route_payload(
    *,
    parsed: Any,
    request_payload: dict[str, Any],
    policy_profile: Any,
    prompt_profile: Any,
    tool_profile: Any,
    build_phase_report_payload: Callable[..., Awaitable[dict[str, Any]]],
    attach_judge_agent_runtime_trace: Callable[..., Awaitable[None]],
    attach_policy_trace_snapshot: Callable[..., None],
    attach_report_attestation: Callable[..., None],
    upsert_claim_ledger_record: Callable[..., Awaitable[Any]],
    build_phase_judge_workflow_payload: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    report_payload = await build_phase_report_payload(request=parsed)
    await attach_judge_agent_runtime_trace(
        report_payload=report_payload,
        dispatch_type="phase",
        case_id=parsed.case_id,
        scope_id=parsed.scope_id,
        session_id=parsed.session_id,
        trace_id=parsed.trace_id,
        phase_no=parsed.phase_no,
    )
    attach_policy_trace_snapshot(
        report_payload=report_payload,
        profile=policy_profile,
        prompt_profile=prompt_profile,
        tool_profile=tool_profile,
    )
    attach_report_attestation(
        report_payload=report_payload,
        dispatch_type="phase",
    )
    await upsert_claim_ledger_record(
        case_id=parsed.case_id,
        dispatch_type="phase",
        trace_id=parsed.trace_id,
        report_payload=report_payload,
        request_payload=request_payload,
    )
    phase_judge_workflow_payload = build_phase_judge_workflow_payload(
        request=parsed,
        report_payload=report_payload,
    )
    return {
        "reportPayload": report_payload,
        "phaseJudgeWorkflowPayload": phase_judge_workflow_payload,
    }


async def build_phase_dispatch_callback_delivery_route_payload(
    *,
    parsed: Any,
    report_payload: dict[str, Any],
    deliver_report_callback_with_failed_fallback: Callable[..., Awaitable[Any]],
    report_callback_fn: Callable[..., Any],
    failed_callback_fn: Callable[..., Any],
    invoke_with_retry: Callable[..., Awaitable[tuple[int, int]]],
    build_failed_callback_payload: Callable[..., dict[str, Any]],
) -> Any:
    return await deliver_report_callback_with_failed_fallback(
        job_id=parsed.case_id,
        report_payload=report_payload,
        report_callback_fn=report_callback_fn,
        failed_callback_fn=failed_callback_fn,
        invoke_with_retry=invoke_with_retry,
        build_failed_payload=lambda error_message: build_failed_callback_payload(
            case_id=parsed.case_id,
            dispatch_type="phase",
            trace_id=parsed.trace_id,
            error_code="phase_callback_retry_exhausted",
            error_message=error_message,
            degradation_level=int(report_payload.get("degradationLevel") or 0),
        ),
    )


async def build_final_dispatch_callback_delivery_route_payload(
    *,
    parsed: Any,
    report_payload: dict[str, Any],
    deliver_report_callback_with_failed_fallback: Callable[..., Awaitable[Any]],
    report_callback_fn: Callable[..., Any],
    failed_callback_fn: Callable[..., Any],
    invoke_with_retry: Callable[..., Awaitable[tuple[int, int]]],
    build_failed_callback_payload: Callable[..., dict[str, Any]],
) -> Any:
    return await deliver_report_callback_with_failed_fallback(
        job_id=parsed.case_id,
        report_payload=report_payload,
        report_callback_fn=report_callback_fn,
        failed_callback_fn=failed_callback_fn,
        invoke_with_retry=invoke_with_retry,
        build_failed_payload=lambda error_message: build_failed_callback_payload(
            case_id=parsed.case_id,
            dispatch_type="final",
            trace_id=parsed.trace_id,
            error_code="final_callback_retry_exhausted",
            error_message=error_message,
            degradation_level=int(report_payload.get("degradationLevel") or 0),
        ),
    )


async def build_phase_dispatch_callback_result_route_payload(
    *,
    parsed: Any,
    response: dict[str, Any],
    request_payload: dict[str, Any],
    report_payload: dict[str, Any],
    callback_outcome: Any,
    callback_status_reported: str,
    callback_status_failed_reported: str,
    callback_status_failed_callback_failed: str,
    with_error_contract: Callable[..., dict[str, Any]],
    persist_dispatch_receipt: Callable[..., Awaitable[Any]],
    trace_register_failure: Callable[..., Any],
    trace_register_success: Callable[..., Any],
    workflow_mark_failed: Callable[..., Awaitable[Any]],
    workflow_mark_completed: Callable[..., Awaitable[Any]],
    build_phase_workflow_reported_payload: Callable[..., dict[str, Any]],
    build_trace_report_summary: Callable[..., dict[str, Any]],
    clear_idempotency: Callable[[str], Any],
    set_idempotency_success: Callable[..., Any],
    idempotency_ttl_secs: int,
    phase_judge_workflow_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if callback_outcome.callback_status == callback_status_failed_callback_failed:
        error_message = str(callback_outcome.report_error or "")
        failed_error = str(callback_outcome.failed_error or "unknown")
        failed_payload = (
            dict(callback_outcome.failed_payload)
            if isinstance(callback_outcome.failed_payload, dict)
            else {}
        )
        receipt_response = with_error_contract(
            {
                **response,
                "status": "callback_failed",
                "callbackStatus": "failed_callback_failed",
                "callbackError": error_message,
                "reportPayload": report_payload,
                "failedCallbackPayload": failed_payload,
                "failedCallbackError": failed_error,
            },
            error_code="phase_failed_callback_failed",
            error_message=failed_error,
            dispatch_type="phase",
            trace_id=parsed.trace_id,
            retryable=False,
            category="callback_delivery",
            details={"reportError": error_message},
        )
        await persist_dispatch_receipt(
            dispatch_type="phase",
            job_id=parsed.case_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=parsed.retrieval_profile,
            phase_no=parsed.phase_no,
            phase_start_no=None,
            phase_end_no=None,
            message_start_id=parsed.message_start_id,
            message_end_id=parsed.message_end_id,
            message_count=parsed.message_count,
            status="callback_failed",
            request_payload=request_payload,
            response_payload=receipt_response,
        )
        trace_register_failure(
            job_id=parsed.case_id,
            response=receipt_response,
            callback_status="failed_callback_failed",
            callback_error=failed_error,
        )
        await workflow_mark_failed(
            job_id=parsed.case_id,
            error_code="phase_failed_callback_failed",
            error_message=failed_error,
            event_payload=build_phase_workflow_reported_payload(
                request=parsed,
                callback_status="failed_callback_failed",
            ),
        )
        clear_idempotency(parsed.idempotency_key)
        raise JudgeCommandRouteError(
            status_code=502,
            detail=f"phase_failed_callback_failed: {failed_error}",
        )

    if callback_outcome.callback_status == callback_status_failed_reported:
        error_message = str(callback_outcome.report_error or "")
        failed_payload = (
            dict(callback_outcome.failed_payload)
            if isinstance(callback_outcome.failed_payload, dict)
            else {}
        )
        failed_attempts = int(callback_outcome.failed_attempts or 0)
        failed_retries = int(callback_outcome.failed_retries or 0)
        receipt_response = with_error_contract(
            {
                **response,
                "status": "callback_failed",
                "callbackStatus": "failed_reported",
                "callbackError": error_message,
                "reportPayload": report_payload,
                "failedCallbackPayload": failed_payload,
                "failedCallbackAttempts": failed_attempts,
                "failedCallbackRetries": failed_retries,
            },
            error_code="phase_callback_retry_exhausted",
            error_message=error_message,
            dispatch_type="phase",
            trace_id=parsed.trace_id,
            retryable=False,
            category="callback_delivery",
            details={
                "failedCallbackAttempts": failed_attempts,
                "failedCallbackRetries": failed_retries,
            },
        )
        await persist_dispatch_receipt(
            dispatch_type="phase",
            job_id=parsed.case_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=parsed.retrieval_profile,
            phase_no=parsed.phase_no,
            phase_start_no=None,
            phase_end_no=None,
            message_start_id=parsed.message_start_id,
            message_end_id=parsed.message_end_id,
            message_count=parsed.message_count,
            status="callback_failed",
            request_payload=request_payload,
            response_payload=receipt_response,
        )
        trace_register_failure(
            job_id=parsed.case_id,
            response=receipt_response,
            callback_status="failed_reported",
            callback_error=error_message,
        )
        await workflow_mark_failed(
            job_id=parsed.case_id,
            error_code="phase_callback_retry_exhausted",
            error_message=error_message,
            event_payload=build_phase_workflow_reported_payload(
                request=parsed,
                callback_status="failed_reported",
            ),
        )
        clear_idempotency(parsed.idempotency_key)
        raise JudgeCommandRouteError(
            status_code=502,
            detail=f"phase_callback_failed: {error_message}",
        )

    if callback_outcome.callback_status != callback_status_reported:
        raise RuntimeError("phase_callback_outcome_status_invalid")

    callback_attempts = int(callback_outcome.callback_attempts or 0)
    callback_retries = int(callback_outcome.callback_retries or 0)
    reported_response = {
        **response,
        "callbackStatus": callback_status_reported,
        "callbackAttempts": callback_attempts,
        "callbackRetries": callback_retries,
        "reportPayload": report_payload,
    }
    await persist_dispatch_receipt(
        dispatch_type="phase",
        job_id=parsed.case_id,
        scope_id=parsed.scope_id,
        session_id=parsed.session_id,
        trace_id=parsed.trace_id,
        idempotency_key=parsed.idempotency_key,
        rubric_version=parsed.rubric_version,
        judge_policy_version=parsed.judge_policy_version,
        topic_domain=parsed.topic_domain,
        retrieval_profile=parsed.retrieval_profile,
        phase_no=parsed.phase_no,
        phase_start_no=None,
        phase_end_no=None,
        message_start_id=parsed.message_start_id,
        message_end_id=parsed.message_end_id,
        message_count=parsed.message_count,
        status="reported",
        request_payload=request_payload,
        response_payload=reported_response,
    )
    trace_register_success(
        job_id=parsed.case_id,
        response=reported_response,
        callback_status="reported",
        report_summary=build_trace_report_summary(
            dispatch_type="phase",
            payload=report_payload,
            callback_status="reported",
            callback_error=None,
            judge_workflow=phase_judge_workflow_payload,
        ),
    )
    await workflow_mark_completed(
        job_id=parsed.case_id,
        event_payload=build_phase_workflow_reported_payload(
            request=parsed,
            callback_status=callback_status_reported,
        ),
    )
    set_idempotency_success(
        key=parsed.idempotency_key,
        job_id=parsed.case_id,
        response=response,
        ttl_secs=idempotency_ttl_secs,
    )
    return response


async def build_final_dispatch_callback_result_route_payload(
    *,
    parsed: Any,
    response: dict[str, Any],
    request_payload: dict[str, Any],
    report_payload: dict[str, Any],
    callback_outcome: Any,
    callback_status_reported: str,
    callback_status_failed_reported: str,
    callback_status_failed_callback_failed: str,
    with_error_contract: Callable[..., dict[str, Any]],
    persist_dispatch_receipt: Callable[..., Awaitable[Any]],
    trace_register_failure: Callable[..., Any],
    trace_register_success: Callable[..., Any],
    workflow_mark_failed: Callable[..., Awaitable[Any]],
    workflow_mark_review_required: Callable[..., Awaitable[Any]],
    workflow_mark_completed: Callable[..., Awaitable[Any]],
    build_final_workflow_reported_payload: Callable[..., dict[str, Any]],
    build_trace_report_summary: Callable[..., dict[str, Any]],
    clear_idempotency: Callable[[str], Any],
    set_idempotency_success: Callable[..., Any],
    idempotency_ttl_secs: int,
    final_judge_workflow_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if callback_outcome.callback_status == callback_status_failed_callback_failed:
        error_message = str(callback_outcome.report_error or "")
        failed_error = str(callback_outcome.failed_error or "unknown")
        failed_payload = (
            dict(callback_outcome.failed_payload)
            if isinstance(callback_outcome.failed_payload, dict)
            else {}
        )
        receipt_response = with_error_contract(
            {
                **response,
                "status": "callback_failed",
                "callbackStatus": "failed_callback_failed",
                "callbackError": error_message,
                "reportPayload": report_payload,
                "failedCallbackPayload": failed_payload,
                "failedCallbackError": failed_error,
            },
            error_code="final_failed_callback_failed",
            error_message=failed_error,
            dispatch_type="final",
            trace_id=parsed.trace_id,
            retryable=False,
            category="callback_delivery",
            details={"reportError": error_message},
        )
        await persist_dispatch_receipt(
            dispatch_type="final",
            job_id=parsed.case_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=None,
            phase_no=None,
            phase_start_no=parsed.phase_start_no,
            phase_end_no=parsed.phase_end_no,
            message_start_id=None,
            message_end_id=None,
            message_count=None,
            status="callback_failed",
            request_payload=request_payload,
            response_payload=receipt_response,
        )
        trace_register_failure(
            job_id=parsed.case_id,
            response=receipt_response,
            callback_status="failed_callback_failed",
            callback_error=failed_error,
        )
        await workflow_mark_failed(
            job_id=parsed.case_id,
            error_code="final_failed_callback_failed",
            error_message=failed_error,
            event_payload={
                "dispatchType": "final",
                "phaseStartNo": parsed.phase_start_no,
                "phaseEndNo": parsed.phase_end_no,
                "callbackStatus": "failed_callback_failed",
            },
        )
        clear_idempotency(parsed.idempotency_key)
        raise JudgeCommandRouteError(
            status_code=502,
            detail=f"final_failed_callback_failed: {failed_error}",
        )

    if callback_outcome.callback_status == callback_status_failed_reported:
        error_message = str(callback_outcome.report_error or "")
        failed_payload = (
            dict(callback_outcome.failed_payload)
            if isinstance(callback_outcome.failed_payload, dict)
            else {}
        )
        failed_attempts = int(callback_outcome.failed_attempts or 0)
        failed_retries = int(callback_outcome.failed_retries or 0)
        receipt_response = with_error_contract(
            {
                **response,
                "status": "callback_failed",
                "callbackStatus": "failed_reported",
                "callbackError": error_message,
                "reportPayload": report_payload,
                "failedCallbackPayload": failed_payload,
                "failedCallbackAttempts": failed_attempts,
                "failedCallbackRetries": failed_retries,
            },
            error_code="final_callback_retry_exhausted",
            error_message=error_message,
            dispatch_type="final",
            trace_id=parsed.trace_id,
            retryable=False,
            category="callback_delivery",
            details={
                "failedCallbackAttempts": failed_attempts,
                "failedCallbackRetries": failed_retries,
            },
        )
        await persist_dispatch_receipt(
            dispatch_type="final",
            job_id=parsed.case_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=None,
            phase_no=None,
            phase_start_no=parsed.phase_start_no,
            phase_end_no=parsed.phase_end_no,
            message_start_id=None,
            message_end_id=None,
            message_count=None,
            status="callback_failed",
            request_payload=request_payload,
            response_payload=receipt_response,
        )
        trace_register_failure(
            job_id=parsed.case_id,
            response=receipt_response,
            callback_status="failed_reported",
            callback_error=error_message,
        )
        await workflow_mark_failed(
            job_id=parsed.case_id,
            error_code="final_callback_retry_exhausted",
            error_message=error_message,
            event_payload={
                "dispatchType": "final",
                "phaseStartNo": parsed.phase_start_no,
                "phaseEndNo": parsed.phase_end_no,
                "callbackStatus": "failed_reported",
            },
        )
        clear_idempotency(parsed.idempotency_key)
        raise JudgeCommandRouteError(
            status_code=502,
            detail=f"final_callback_failed: {error_message}",
        )

    if callback_outcome.callback_status != callback_status_reported:
        raise RuntimeError("final_callback_outcome_status_invalid")

    callback_attempts = int(callback_outcome.callback_attempts or 0)
    callback_retries = int(callback_outcome.callback_retries or 0)
    reported_response = {
        **response,
        "callbackStatus": callback_status_reported,
        "callbackAttempts": callback_attempts,
        "callbackRetries": callback_retries,
        "reportPayload": report_payload,
    }
    await persist_dispatch_receipt(
        dispatch_type="final",
        job_id=parsed.case_id,
        scope_id=parsed.scope_id,
        session_id=parsed.session_id,
        trace_id=parsed.trace_id,
        idempotency_key=parsed.idempotency_key,
        rubric_version=parsed.rubric_version,
        judge_policy_version=parsed.judge_policy_version,
        topic_domain=parsed.topic_domain,
        retrieval_profile=None,
        phase_no=None,
        phase_start_no=parsed.phase_start_no,
        phase_end_no=parsed.phase_end_no,
        message_start_id=None,
        message_end_id=None,
        message_count=None,
        status="reported",
        request_payload=request_payload,
        response_payload=reported_response,
    )
    trace_register_success(
        job_id=parsed.case_id,
        response=reported_response,
        callback_status=callback_status_reported,
        report_summary=build_trace_report_summary(
            dispatch_type="final",
            payload=report_payload,
            callback_status="reported",
            callback_error=None,
            judge_workflow=final_judge_workflow_payload,
        ),
    )
    review_required = bool(report_payload.get("reviewRequired"))
    workflow_event_payload = build_final_workflow_reported_payload(
        request=parsed,
        report_payload=report_payload,
        callback_status=callback_status_reported,
    )
    if review_required:
        await workflow_mark_review_required(
            job_id=parsed.case_id,
            event_payload=workflow_event_payload,
        )
    else:
        await workflow_mark_completed(
            job_id=parsed.case_id,
            event_payload=workflow_event_payload,
        )
    set_idempotency_success(
        key=parsed.idempotency_key,
        job_id=parsed.case_id,
        response=response,
        ttl_secs=idempotency_ttl_secs,
    )
    return response


async def build_final_contract_blocked_route_payload(
    *,
    parsed: Any,
    response: dict[str, Any],
    request_payload: dict[str, Any],
    report_payload: dict[str, Any],
    contract_missing_fields: list[str],
    upsert_audit_alert: Callable[..., Any],
    sync_audit_alert_to_facts: Callable[..., Awaitable[Any]],
    build_failed_callback_payload: Callable[..., dict[str, Any]],
    invoke_failed_callback_with_retry: Callable[..., Awaitable[tuple[int, int]]],
    with_error_contract: Callable[..., dict[str, Any]],
    persist_dispatch_receipt: Callable[..., Awaitable[Any]],
    trace_register_failure: Callable[..., Any],
    workflow_mark_failed: Callable[..., Awaitable[Any]],
    clear_idempotency: Callable[[str], Any],
) -> None:
    error_text = "final_contract_violation: missing_fields=" + ",".join(
        contract_missing_fields[:12]
    )
    alert = upsert_audit_alert(
        job_id=parsed.case_id,
        scope_id=parsed.scope_id,
        trace_id=parsed.trace_id,
        alert_type="final_contract_violation",
        severity="critical",
        title="AI Judge Final Contract Violation",
        message=error_text,
        details={
            "dispatchType": "final",
            "sessionId": parsed.session_id,
            "phaseRange": {
                "startNo": parsed.phase_start_no,
                "endNo": parsed.phase_end_no,
            },
            "missingFields": contract_missing_fields,
            "errorCode": "final_contract_blocked",
        },
    )
    await sync_audit_alert_to_facts(alert=alert)
    failed_payload = build_failed_callback_payload(
        case_id=parsed.case_id,
        dispatch_type="final",
        trace_id=parsed.trace_id,
        error_code="final_contract_blocked",
        error_message=error_text,
        audit_alert_ids=[alert.alert_id],
        degradation_level=int(report_payload.get("degradationLevel") or 0),
    )
    try:
        failed_attempts, failed_retries = await invoke_failed_callback_with_retry(
            case_id=parsed.case_id,
            payload=failed_payload,
        )
    except Exception as failed_err:
        receipt_response = with_error_contract(
            {
                **response,
                "status": "callback_failed",
                "callbackStatus": "failed_callback_failed",
                "callbackError": error_text,
                "auditAlertIds": [alert.alert_id],
                "reportPayload": report_payload,
                "failedCallbackPayload": failed_payload,
                "failedCallbackError": str(failed_err),
            },
            error_code="final_failed_callback_failed",
            error_message=str(failed_err),
            dispatch_type="final",
            trace_id=parsed.trace_id,
            retryable=False,
            category="contract_blocked",
            details={
                "auditAlertId": alert.alert_id,
                "blockedReason": error_text,
            },
        )
        await persist_dispatch_receipt(
            dispatch_type="final",
            job_id=parsed.case_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=None,
            phase_no=None,
            phase_start_no=parsed.phase_start_no,
            phase_end_no=parsed.phase_end_no,
            message_start_id=None,
            message_end_id=None,
            message_count=None,
            status="callback_failed",
            request_payload=request_payload,
            response_payload=receipt_response,
        )
        trace_register_failure(
            job_id=parsed.case_id,
            response=receipt_response,
            callback_status="failed_callback_failed",
            callback_error=str(failed_err),
        )
        await workflow_mark_failed(
            job_id=parsed.case_id,
            error_code="final_failed_callback_failed",
            error_message=str(failed_err),
            event_payload={
                "dispatchType": "final",
                "phaseStartNo": parsed.phase_start_no,
                "phaseEndNo": parsed.phase_end_no,
                "callbackStatus": "failed_callback_failed",
            },
        )
        clear_idempotency(parsed.idempotency_key)
        raise JudgeCommandRouteError(
            status_code=502,
            detail=f"final_failed_callback_failed: {failed_err}",
        )

    receipt_response = with_error_contract(
        {
            **response,
            "status": "callback_failed",
            "callbackStatus": "blocked_failed_reported",
            "callbackError": error_text,
            "auditAlertIds": [alert.alert_id],
            "reportPayload": report_payload,
            "failedCallbackPayload": failed_payload,
            "failedCallbackAttempts": failed_attempts,
            "failedCallbackRetries": failed_retries,
        },
        error_code="final_contract_blocked",
        error_message=error_text,
        dispatch_type="final",
        trace_id=parsed.trace_id,
        retryable=False,
        category="contract_blocked",
        details={
            "auditAlertId": alert.alert_id,
            "failedCallbackAttempts": failed_attempts,
            "failedCallbackRetries": failed_retries,
            "missingFields": contract_missing_fields[:12],
        },
    )
    await persist_dispatch_receipt(
        dispatch_type="final",
        job_id=parsed.case_id,
        scope_id=parsed.scope_id,
        session_id=parsed.session_id,
        trace_id=parsed.trace_id,
        idempotency_key=parsed.idempotency_key,
        rubric_version=parsed.rubric_version,
        judge_policy_version=parsed.judge_policy_version,
        topic_domain=parsed.topic_domain,
        retrieval_profile=None,
        phase_no=None,
        phase_start_no=parsed.phase_start_no,
        phase_end_no=parsed.phase_end_no,
        message_start_id=None,
        message_end_id=None,
        message_count=None,
        status="callback_failed",
        request_payload=request_payload,
        response_payload=receipt_response,
    )
    trace_register_failure(
        job_id=parsed.case_id,
        response=receipt_response,
        callback_status="blocked_failed_reported",
        callback_error=error_text,
    )
    await workflow_mark_failed(
        job_id=parsed.case_id,
        error_code="final_contract_blocked",
        error_message=error_text,
        event_payload={
            "dispatchType": "final",
            "phaseStartNo": parsed.phase_start_no,
            "phaseEndNo": parsed.phase_end_no,
            "callbackStatus": "blocked_failed_reported",
            "missingFields": contract_missing_fields[:12],
        },
    )
    clear_idempotency(parsed.idempotency_key)
    raise JudgeCommandRouteError(
        status_code=502,
        detail="final_contract_blocked: missing_critical_fields",
    )


async def build_final_dispatch_report_materialization_route_payload(
    *,
    parsed: Any,
    request_payload: dict[str, Any],
    policy_profile: Any,
    prompt_profile: Any,
    tool_profile: Any,
    list_dispatch_receipts: Callable[..., Awaitable[list[Any]]],
    build_final_report_payload: Callable[..., dict[str, Any]],
    resolve_panel_runtime_profiles: Callable[..., dict[str, dict[str, Any]]],
    attach_judge_agent_runtime_trace: Callable[..., Awaitable[None]],
    attach_policy_trace_snapshot: Callable[..., None],
    attach_report_attestation: Callable[..., None],
    upsert_claim_ledger_record: Callable[..., Awaitable[Any]],
    build_final_judge_workflow_payload: Callable[..., dict[str, Any]],
    validate_final_report_payload_contract: Callable[[dict[str, Any]], list[str]],
) -> dict[str, Any]:
    phase_receipts = await list_dispatch_receipts(
        dispatch_type="phase",
        session_id=parsed.session_id,
        status="reported",
        limit=1000,
    )
    report_payload = build_final_report_payload(
        request=parsed,
        phase_receipts=phase_receipts,
        fairness_thresholds=policy_profile.fairness_thresholds,
        panel_runtime_profiles=resolve_panel_runtime_profiles(profile=policy_profile),
    )
    await attach_judge_agent_runtime_trace(
        report_payload=report_payload,
        dispatch_type="final",
        case_id=parsed.case_id,
        scope_id=parsed.scope_id,
        session_id=parsed.session_id,
        trace_id=parsed.trace_id,
        phase_start_no=parsed.phase_start_no,
        phase_end_no=parsed.phase_end_no,
    )
    attach_policy_trace_snapshot(
        report_payload=report_payload,
        profile=policy_profile,
        prompt_profile=prompt_profile,
        tool_profile=tool_profile,
    )
    attach_report_attestation(
        report_payload=report_payload,
        dispatch_type="final",
    )
    await upsert_claim_ledger_record(
        case_id=parsed.case_id,
        dispatch_type="final",
        trace_id=parsed.trace_id,
        report_payload=report_payload,
        request_payload=request_payload,
    )
    final_judge_workflow_payload = build_final_judge_workflow_payload(
        request=parsed,
        report_payload=report_payload,
    )
    contract_missing_fields = validate_final_report_payload_contract(report_payload)
    return {
        "reportPayload": report_payload,
        "finalJudgeWorkflowPayload": final_judge_workflow_payload,
        "contractMissingFields": contract_missing_fields,
    }
