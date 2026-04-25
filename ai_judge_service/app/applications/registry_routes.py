from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .registry_release_gate import build_policy_release_gate_decision

REGISTRY_DEPENDENCY_NOT_FOUND_CODE = "policy_registry_not_found"


class RegistryRouteError(Exception):
    def __init__(self, *, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


def build_registry_profiles_payload(
    *,
    default_version: str,
    profiles: list[Any],
    serializer: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    return {
        "defaultVersion": default_version,
        "count": len(profiles),
        "items": [serializer(item) for item in profiles],
    }


def build_registry_profile_payload(
    *,
    profile: Any,
    serializer: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    return {"item": serializer(profile)}


def build_registry_releases_payload(
    *,
    registry_type: str,
    items: list[dict[str, Any]],
    limit: int,
    include_payload: bool,
) -> dict[str, Any]:
    return {
        "registryType": str(registry_type or "").strip().lower(),
        "count": len(items),
        "items": list(items),
        "limit": int(limit),
        "includePayload": bool(include_payload),
    }


def build_registry_release_payload(*, item: dict[str, Any]) -> dict[str, Any]:
    return {"item": dict(item)}


async def build_policy_registry_dependency_health_payload(
    *,
    policy_version: str | None,
    default_policy_version: str,
    default_prompt_registry_version: str,
    default_tool_registry_version: str,
    include_all_versions: bool,
    include_overview: bool,
    include_trend: bool,
    trend_status: str | None,
    trend_policy_version: str | None,
    trend_offset: int,
    trend_limit: int,
    overview_window_minutes: int,
    limit: int,
    list_policy_profiles: Callable[[], list[Any]],
    evaluate_policy_registry_dependency_health: Callable[[str], Awaitable[dict[str, Any]]],
    normalize_registry_dependency_trend_status: Callable[[str | None], str | None],
    dependency_trend_status_values: set[str] | frozenset[str],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    build_registry_dependency_overview: Callable[..., dict[str, Any]],
    build_registry_dependency_trend: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    selected_policy_version = str(policy_version or "").strip() or default_policy_version
    selected_item = await evaluate_policy_registry_dependency_health(selected_policy_version)
    if selected_item.get("code") == REGISTRY_DEPENDENCY_NOT_FOUND_CODE:
        raise LookupError(REGISTRY_DEPENDENCY_NOT_FOUND_CODE)

    items: list[dict[str, Any]] = [selected_item]
    if include_all_versions:
        policy_versions: list[str] = []
        seen_versions: set[str] = set()
        for row in list_policy_profiles():
            version_token = str(getattr(row, "version", "") or "").strip()
            if not version_token or version_token in seen_versions:
                continue
            seen_versions.add(version_token)
            policy_versions.append(version_token)
        if selected_policy_version not in seen_versions:
            policy_versions.insert(0, selected_policy_version)

        items = []
        normalized_limit = max(1, min(int(limit), 200))
        for version_token in policy_versions[:normalized_limit]:
            dependency_item = await evaluate_policy_registry_dependency_health(version_token)
            if dependency_item.get("code") == REGISTRY_DEPENDENCY_NOT_FOUND_CODE:
                continue
            items.append(dependency_item)

    normalized_trend_status = normalize_registry_dependency_trend_status(trend_status)
    if (
        normalized_trend_status is not None
        and normalized_trend_status not in dependency_trend_status_values
    ):
        raise ValueError("invalid_trend_status")

    alerts: list[Any] = []
    if include_overview or include_trend:
        alerts = await list_audit_alerts(job_id=0, status=None, limit=5000)

    dependency_overview = None
    if include_overview:
        dependency_overview = build_registry_dependency_overview(
            items=items,
            alerts=alerts,
            registry_type="policy",
            window_minutes=overview_window_minutes,
        )

    dependency_trend = None
    if include_trend:
        dependency_trend = build_registry_dependency_trend(
            alerts=alerts,
            registry_type="policy",
            window_minutes=overview_window_minutes,
            status_filter=normalized_trend_status,
            policy_version_filter=trend_policy_version,
            offset=trend_offset,
            limit=trend_limit,
        )

    return {
        "activeVersions": {
            "policyVersion": default_policy_version,
            "promptRegistryVersion": default_prompt_registry_version,
            "toolRegistryVersion": default_tool_registry_version,
        },
        "selectedPolicyVersion": selected_policy_version,
        "item": selected_item,
        "count": len(items),
        "items": items,
        "includeAllVersions": bool(include_all_versions),
        "includeOverview": bool(include_overview),
        "includeTrend": bool(include_trend),
        "trendStatus": normalized_trend_status,
        "trendPolicyVersion": str(trend_policy_version or "").strip() or None,
        "trendOffset": int(trend_offset),
        "trendLimit": int(trend_limit),
        "overviewWindowMinutes": int(overview_window_minutes),
        "dependencyOverview": dependency_overview,
        "dependencyTrend": dependency_trend,
        "limit": int(limit),
    }


async def build_registry_audits_payload(
    *,
    registry_type: str,
    action: str | None,
    version: str | None,
    actor: str | None,
    gate_code: str | None,
    override_applied: bool | None,
    include_gate_view: bool,
    link_limit: int,
    offset: int,
    limit: int,
    normalize_registry_audit_action: Callable[[str | None], str | None],
    registry_audit_action_values: set[str] | frozenset[str],
    list_registry_audits: Callable[..., Awaitable[list[dict[str, Any]]]],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    list_alert_outbox: Callable[..., list[Any]],
    build_registry_audit_ops_view: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    normalized_action = normalize_registry_audit_action(action)
    if (
        normalized_action is not None
        and normalized_action not in registry_audit_action_values
    ):
        raise ValueError("invalid_registry_audit_action")

    fetch_limit = max(1, min(int(limit) + int(offset), 200))
    items = await list_registry_audits(
        registry_type=registry_type,
        limit=fetch_limit,
    )
    alerts: list[Any] = []
    outbox_events: list[Any] = []
    if include_gate_view:
        alerts = await list_audit_alerts(job_id=0, status=None, limit=5000)
        outbox_events = list_alert_outbox(limit=500)

    return build_registry_audit_ops_view(
        registry_type=registry_type,
        audit_items=items,
        alerts=alerts,
        outbox_events=outbox_events,
        action=normalized_action,
        version=version,
        actor=actor,
        gate_code=gate_code,
        override_applied=override_applied,
        include_gate_view=include_gate_view,
        link_limit=link_limit,
        offset=offset,
        limit=limit,
    )


def parse_registry_publish_request_payload(
    *,
    payload: dict[str, Any],
    extract_optional_bool: Callable[..., bool | None],
) -> dict[str, Any]:
    version = str(payload.get("version") or "").strip()
    profile_payload = payload.get("profile")
    if not isinstance(profile_payload, dict):
        raise ValueError("invalid_registry_profile")
    activate = bool(payload.get("activate"))
    override_fairness_gate = bool(
        extract_optional_bool(
            payload,
            "override_fairness_gate",
            "overrideFairnessGate",
        )
    )
    actor = str(payload.get("actor") or "").strip() or None
    reason = str(payload.get("reason") or "").strip() or None
    return {
        "version": version,
        "profilePayload": profile_payload,
        "activate": activate,
        "overrideFairnessGate": override_fairness_gate,
        "actor": actor,
        "reason": reason,
    }


def build_registry_extra_details_payload(
    *,
    dependency_health: dict[str, Any] | None,
    fairness_gate: dict[str, Any] | None,
    release_gate: dict[str, Any] | None,
    override_fairness_gate: bool,
) -> dict[str, Any] | None:
    extra_details_payload: dict[str, Any] = {}
    if dependency_health is not None:
        extra_details_payload["dependencyHealth"] = dict(dependency_health)
    if release_gate is not None:
        extra_details_payload["releaseGate"] = {
            **(release_gate or {}),
            "overrideApplied": bool(
                override_fairness_gate
                and release_gate is not None
                and not bool(release_gate.get("allowed"))
            ),
        }
    if fairness_gate is not None:
        extra_details_payload["fairnessGate"] = {
            **(fairness_gate or {}),
            "overrideApplied": bool(
                override_fairness_gate
                and fairness_gate is not None
                and not bool(fairness_gate.get("passed"))
            ),
        }
    return extra_details_payload or None


async def build_registry_publish_payload(
    *,
    registry_type: str,
    version: str,
    profile_payload: dict[str, Any],
    activate: bool,
    override_fairness_gate: bool,
    actor: str | None,
    reason: str | None,
    policy_registry_type: str,
    enforce_policy_domain_judge_family_profile_payload: Callable[..., tuple[dict[str, Any], str | None]],
    evaluate_policy_registry_dependency_health: Callable[..., Awaitable[dict[str, Any]]],
    emit_registry_dependency_health_alert: Callable[..., Awaitable[dict[str, Any]]],
    resolve_registry_dependency_health_alerts: Callable[..., Awaitable[list[dict[str, Any]]]],
    evaluate_policy_release_fairness_gate: Callable[..., Awaitable[dict[str, Any]]],
    emit_registry_fairness_gate_alert: Callable[..., Awaitable[dict[str, Any]]],
    publish_release: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    registry_type_token = str(registry_type or "").strip().lower()
    normalized_profile_payload = dict(profile_payload)
    fairness_gate: dict[str, Any] | None = None
    fairness_alert: dict[str, Any] | None = None
    dependency_alert: dict[str, Any] | None = None
    dependency_alert_resolved: list[dict[str, Any]] = []
    dependency_health: dict[str, Any] | None = None
    release_gate: dict[str, Any] | None = None
    policy_domain_judge_family: str | None = None

    if registry_type_token == policy_registry_type:
        normalized_profile_payload, policy_domain_judge_family = (
            enforce_policy_domain_judge_family_profile_payload(
                profile_payload=normalized_profile_payload,
            )
        )
        dependency_health = await evaluate_policy_registry_dependency_health(
            policy_version=version,
            profile_payload=normalized_profile_payload,
        )
        if not bool(dependency_health.get("ok")):
            dependency_alert = await emit_registry_dependency_health_alert(
                registry_type=registry_type_token,
                version=version,
                dependency_health=dependency_health,
                action="publish",
            )
            raise RegistryRouteError(
                status_code=422,
                detail={
                    "code": "registry_policy_dependency_invalid",
                    "dependency": dependency_health,
                    "alert": dependency_alert,
                },
            )
        dependency_alert_resolved = await resolve_registry_dependency_health_alerts(
            registry_type=registry_type_token,
            version=version,
            actor=actor,
            reason=reason,
            action="publish",
        )

    if registry_type_token == policy_registry_type and activate:
        fairness_gate = await evaluate_policy_release_fairness_gate(
            policy_version=version,
        )
        release_gate = build_policy_release_gate_decision(
            dependency_health=dependency_health,
            fairness_gate=fairness_gate,
        )
        if not bool(fairness_gate.get("passed")):
            if override_fairness_gate:
                if reason is None:
                    raise ValueError("registry_fairness_gate_override_reason_required")
                fairness_alert = await emit_registry_fairness_gate_alert(
                    registry_type=registry_type_token,
                    version=version,
                    gate_result=fairness_gate,
                    override_applied=True,
                    actor=actor,
                    reason=reason,
                )
            else:
                fairness_alert = await emit_registry_fairness_gate_alert(
                    registry_type=registry_type_token,
                    version=version,
                    gate_result=fairness_gate,
                    override_applied=False,
                    actor=actor,
                    reason=reason,
                )
                raise RegistryRouteError(
                    status_code=409,
                    detail={
                        "code": "registry_fairness_gate_blocked",
                        "releaseGate": release_gate,
                        "gate": fairness_gate,
                        "alert": fairness_alert,
                    },
                )
        elif not bool(release_gate.get("allowed")):
            if override_fairness_gate:
                if reason is None:
                    raise ValueError("registry_fairness_gate_override_reason_required")
                fairness_alert = await emit_registry_fairness_gate_alert(
                    registry_type=registry_type_token,
                    version=version,
                    gate_result=release_gate,
                    override_applied=True,
                    actor=actor,
                    reason=reason,
                )
            else:
                fairness_alert = await emit_registry_fairness_gate_alert(
                    registry_type=registry_type_token,
                    version=version,
                    gate_result=release_gate,
                    override_applied=False,
                    actor=actor,
                    reason=reason,
                )
                raise RegistryRouteError(
                    status_code=409,
                    detail={
                        "code": release_gate["code"],
                        "releaseGate": release_gate,
                        "gate": fairness_gate,
                        "alert": fairness_alert,
                    },
                )

    extra_details = build_registry_extra_details_payload(
        dependency_health=dependency_health,
        fairness_gate=fairness_gate,
        release_gate=release_gate,
        override_fairness_gate=override_fairness_gate,
    )
    item = await publish_release(
        registry_type=registry_type,
        version=version,
        profile_payload=normalized_profile_payload,
        actor=actor,
        reason=reason,
        activate=activate,
        extra_details=extra_details,
    )
    return {
        "ok": True,
        "item": item,
        "policyDomainJudgeFamily": policy_domain_judge_family,
        "dependencyHealth": dependency_health,
        "dependencyAlert": dependency_alert,
        "resolvedDependencyAlerts": dependency_alert_resolved,
        "fairnessGate": fairness_gate,
        "releaseGate": release_gate,
        "alert": fairness_alert,
    }


async def build_registry_activate_payload(
    *,
    registry_type: str,
    version: str,
    actor: str | None,
    reason: str | None,
    override_fairness_gate: bool,
    policy_registry_type: str,
    evaluate_policy_registry_dependency_health: Callable[..., Awaitable[dict[str, Any]]],
    emit_registry_dependency_health_alert: Callable[..., Awaitable[dict[str, Any]]],
    resolve_registry_dependency_health_alerts: Callable[..., Awaitable[list[dict[str, Any]]]],
    evaluate_policy_release_fairness_gate: Callable[..., Awaitable[dict[str, Any]]],
    emit_registry_fairness_gate_alert: Callable[..., Awaitable[dict[str, Any]]],
    activate_release: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    registry_type_token = str(registry_type or "").strip().lower()
    fairness_gate: dict[str, Any] | None = None
    fairness_alert: dict[str, Any] | None = None
    dependency_alert: dict[str, Any] | None = None
    dependency_alert_resolved: list[dict[str, Any]] = []
    dependency_health: dict[str, Any] | None = None
    release_gate: dict[str, Any] | None = None

    if registry_type_token == policy_registry_type:
        dependency_health = await evaluate_policy_registry_dependency_health(
            policy_version=version,
        )
        if not bool(dependency_health.get("ok")):
            dependency_alert = await emit_registry_dependency_health_alert(
                registry_type=registry_type_token,
                version=version,
                dependency_health=dependency_health,
                action="activate",
            )
            raise RegistryRouteError(
                status_code=409,
                detail={
                    "code": "registry_policy_dependency_blocked",
                    "dependency": dependency_health,
                    "alert": dependency_alert,
                },
            )
        dependency_alert_resolved = await resolve_registry_dependency_health_alerts(
            registry_type=registry_type_token,
            version=version,
            actor=actor,
            reason=reason,
            action="activate",
        )
        fairness_gate = await evaluate_policy_release_fairness_gate(
            policy_version=version,
        )
        release_gate = build_policy_release_gate_decision(
            dependency_health=dependency_health,
            fairness_gate=fairness_gate,
        )
        if not bool(fairness_gate.get("passed")):
            if override_fairness_gate:
                if reason is None:
                    raise ValueError("registry_fairness_gate_override_reason_required")
                fairness_alert = await emit_registry_fairness_gate_alert(
                    registry_type=registry_type_token,
                    version=version,
                    gate_result=fairness_gate,
                    override_applied=True,
                    actor=actor,
                    reason=reason,
                )
            else:
                fairness_alert = await emit_registry_fairness_gate_alert(
                    registry_type=registry_type_token,
                    version=version,
                    gate_result=fairness_gate,
                    override_applied=False,
                    actor=actor,
                    reason=reason,
                )
                raise RegistryRouteError(
                    status_code=409,
                    detail={
                        "code": "registry_fairness_gate_blocked",
                        "releaseGate": release_gate,
                        "gate": fairness_gate,
                        "alert": fairness_alert,
                    },
                )
        elif not bool(release_gate.get("allowed")):
            if override_fairness_gate:
                if reason is None:
                    raise ValueError("registry_fairness_gate_override_reason_required")
                fairness_alert = await emit_registry_fairness_gate_alert(
                    registry_type=registry_type_token,
                    version=version,
                    gate_result=release_gate,
                    override_applied=True,
                    actor=actor,
                    reason=reason,
                )
            else:
                fairness_alert = await emit_registry_fairness_gate_alert(
                    registry_type=registry_type_token,
                    version=version,
                    gate_result=release_gate,
                    override_applied=False,
                    actor=actor,
                    reason=reason,
                )
                raise RegistryRouteError(
                    status_code=409,
                    detail={
                        "code": release_gate["code"],
                        "releaseGate": release_gate,
                        "gate": fairness_gate,
                        "alert": fairness_alert,
                    },
                )

    extra_details = build_registry_extra_details_payload(
        dependency_health=dependency_health,
        fairness_gate=fairness_gate,
        release_gate=release_gate,
        override_fairness_gate=override_fairness_gate,
    )
    item = await activate_release(
        registry_type=registry_type,
        version=version,
        actor=actor,
        reason=reason,
        extra_details=extra_details,
    )
    return {
        "ok": True,
        "item": item,
        "dependencyHealth": dependency_health,
        "dependencyAlert": dependency_alert,
        "resolvedDependencyAlerts": dependency_alert_resolved,
        "fairnessGate": fairness_gate,
        "releaseGate": release_gate,
        "alert": fairness_alert,
    }


async def build_registry_rollback_payload(
    *,
    registry_type: str,
    target_version: str | None,
    actor: str | None,
    reason: str | None,
    rollback_release: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    item = await rollback_release(
        registry_type=registry_type,
        target_version=target_version,
        actor=actor,
        reason=reason,
    )
    return {
        "ok": True,
        "item": item,
    }


async def build_registry_governance_overview_payload(
    *,
    dependency_limit: int,
    usage_preview_limit: int,
    release_limit: int,
    audit_limit: int,
    default_policy_version: str,
    default_prompt_registry_version: str,
    default_tool_registry_version: str,
    policy_registry_type: str,
    prompt_registry_type: str,
    tool_registry_type: str,
    list_policy_profiles: Callable[[], list[Any]],
    list_prompt_profiles: Callable[[], list[Any]],
    list_tool_profiles: Callable[[], list[Any]],
    evaluate_policy_registry_dependency_health: Callable[[str], Awaitable[dict[str, Any]]],
    evaluate_policy_release_fairness_gate: Callable[[str], Awaitable[dict[str, Any]]],
    list_releases: Callable[..., Awaitable[list[dict[str, Any]]]],
    list_audits: Callable[..., Awaitable[list[dict[str, Any]]]],
    build_policy_domain_judge_family_overview: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    policy_profiles = list_policy_profiles()
    prompt_profiles = list_prompt_profiles()
    tool_profiles = list_tool_profiles()

    dependency_rows: list[dict[str, Any]] = []
    dependency_invalid_count = 0
    dependency_by_prompt_registry: dict[str, int] = {}
    dependency_by_tool_registry: dict[str, int] = {}
    dependency_issue_code_counts: dict[str, int] = {}
    release_gate_decision_counts: dict[str, int] = {
        "allowed": 0,
        "blocked": 0,
        "env_blocked": 0,
        "needs_review": 0,
    }
    release_gate_component_block_counts: dict[str, int] = {}
    for profile in policy_profiles[: max(1, min(int(dependency_limit), 500))]:
        dependency_payload = await evaluate_policy_registry_dependency_health(
            str(getattr(profile, "version", "") or "").strip(),
        )
        fairness_gate = await evaluate_policy_release_fairness_gate(
            str(getattr(profile, "version", "") or "").strip(),
        )
        release_gate = build_policy_release_gate_decision(
            dependency_health=dependency_payload,
            fairness_gate=fairness_gate,
        )
        release_gate_decision = str(release_gate.get("decision") or "").strip()
        if release_gate_decision in release_gate_decision_counts:
            release_gate_decision_counts[release_gate_decision] += 1
        else:
            release_gate_decision_counts["needs_review"] += 1
        for reason in release_gate.get("reasons") or []:
            if not isinstance(reason, dict):
                continue
            component = str(reason.get("component") or "").strip()
            if not component:
                continue
            release_gate_component_block_counts[component] = (
                release_gate_component_block_counts.get(component, 0) + 1
            )
        issue_codes = [
            str(row.get("code") or "").strip()
            for row in (dependency_payload.get("issues") or [])
            if isinstance(row, dict) and str(row.get("code") or "").strip()
        ]
        prompt_registry_version = (
            str(dependency_payload.get("promptRegistryVersion") or "").strip() or "unknown"
        )
        tool_registry_version = (
            str(dependency_payload.get("toolRegistryVersion") or "").strip() or "unknown"
        )
        policy_kernel = (
            dependency_payload.get("policyKernel")
            if isinstance(dependency_payload.get("policyKernel"), dict)
            else {}
        )
        dependency_by_prompt_registry[prompt_registry_version] = (
            dependency_by_prompt_registry.get(prompt_registry_version, 0) + 1
        )
        dependency_by_tool_registry[tool_registry_version] = (
            dependency_by_tool_registry.get(tool_registry_version, 0) + 1
        )
        for code in issue_codes:
            dependency_issue_code_counts[code] = (
                dependency_issue_code_counts.get(code, 0) + 1
            )
        if not bool(dependency_payload.get("ok")):
            dependency_invalid_count += 1
        dependency_rows.append(
            {
                "policyVersion": str(dependency_payload.get("policyVersion") or "").strip()
                or str(getattr(profile, "version", "") or "").strip()
                or None,
                "ok": bool(dependency_payload.get("ok")),
                "code": str(dependency_payload.get("code") or "").strip() or None,
                "promptRegistryVersion": (
                    str(dependency_payload.get("promptRegistryVersion") or "").strip() or None
                ),
                "toolRegistryVersion": (
                    str(dependency_payload.get("toolRegistryVersion") or "").strip() or None
                ),
                "policyKernelVersion": (
                    str(policy_kernel.get("version") or "").strip() or None
                ),
                "policyKernelHash": (
                    str(policy_kernel.get("kernelHash") or "").strip() or None
                ),
                "issueCodes": issue_codes,
                "releaseGateDecision": release_gate_decision,
                "releaseGateCode": str(release_gate.get("code") or "").strip() or None,
                "releaseGateReasonCodes": [
                    str(reason.get("code") or "").strip()
                    for reason in release_gate.get("reasons") or []
                    if isinstance(reason, dict) and str(reason.get("code") or "").strip()
                ],
                "releaseGate": release_gate,
            }
        )

    prompt_refs_by_policy: dict[str, list[str]] = {}
    tool_refs_by_policy: dict[str, list[str]] = {}
    for profile in policy_profiles:
        policy_version = str(getattr(profile, "version", "") or "").strip()
        prompt_version = str(getattr(profile, "prompt_registry_version", "") or "").strip()
        tool_version = str(getattr(profile, "tool_registry_version", "") or "").strip()
        if prompt_version:
            prompt_refs_by_policy.setdefault(prompt_version, []).append(policy_version)
        if tool_version:
            tool_refs_by_policy.setdefault(tool_version, []).append(policy_version)

    preview_cap = max(1, min(int(usage_preview_limit), 200))
    domain_family_overview = build_policy_domain_judge_family_overview(
        policy_profiles=policy_profiles,
        active_policy_version=default_policy_version,
        preview_limit=preview_cap,
        include_versions=True,
    )
    prompt_usage_rows: list[dict[str, Any]] = []
    for profile in prompt_profiles:
        version_token = str(getattr(profile, "version", "") or "").strip()
        refs = prompt_refs_by_policy.get(version_token, [])
        prompt_usage_rows.append(
            {
                "version": version_token or None,
                "isActive": version_token == default_prompt_registry_version,
                "referencedByPolicyCount": len(refs),
                "referencedPolicyVersions": refs[:preview_cap],
                "hasMorePolicyRefs": len(refs) > preview_cap,
            }
        )
    prompt_usage_rows.sort(
        key=lambda row: (
            -int(row.get("referencedByPolicyCount") or 0),
            str(row.get("version") or ""),
        )
    )

    tool_usage_rows: list[dict[str, Any]] = []
    for profile in tool_profiles:
        version_token = str(getattr(profile, "version", "") or "").strip()
        refs = tool_refs_by_policy.get(version_token, [])
        tool_usage_rows.append(
            {
                "version": version_token or None,
                "isActive": version_token == default_tool_registry_version,
                "referencedByPolicyCount": len(refs),
                "referencedPolicyVersions": refs[:preview_cap],
                "hasMorePolicyRefs": len(refs) > preview_cap,
            }
        )
    tool_usage_rows.sort(
        key=lambda row: (
            -int(row.get("referencedByPolicyCount") or 0),
            str(row.get("version") or ""),
        )
    )

    known_prompt_versions = {
        str(getattr(profile, "version", "") or "").strip()
        for profile in prompt_profiles
        if str(getattr(profile, "version", "") or "").strip()
    }
    known_tool_versions = {
        str(getattr(profile, "version", "") or "").strip()
        for profile in tool_profiles
        if str(getattr(profile, "version", "") or "").strip()
    }
    missing_prompt_refs = sorted(
        {
            str(getattr(profile, "prompt_registry_version", "") or "").strip()
            for profile in policy_profiles
            if str(getattr(profile, "prompt_registry_version", "") or "").strip()
            and str(getattr(profile, "prompt_registry_version", "") or "").strip()
            not in known_prompt_versions
        }
    )
    missing_tool_refs = sorted(
        {
            str(getattr(profile, "tool_registry_version", "") or "").strip()
            for profile in policy_profiles
            if str(getattr(profile, "tool_registry_version", "") or "").strip()
            and str(getattr(profile, "tool_registry_version", "") or "").strip()
            not in known_tool_versions
        }
    )

    release_state: dict[str, dict[str, Any]] = {}
    for registry_type in (
        policy_registry_type,
        prompt_registry_type,
        tool_registry_type,
    ):
        releases = await list_releases(
            registry_type=registry_type,
            limit=max(1, min(int(release_limit), 200)),
            include_payload=False,
        )
        active_release = next((row for row in releases if bool(row.get("isActive"))), None)
        latest_release = releases[0] if releases else None
        release_state[registry_type] = {
            "count": len(releases),
            "activeVersion": (
                str(active_release.get("version") or "").strip()
                if isinstance(active_release, dict)
                else None
            ),
            "latestVersion": (
                str(latest_release.get("version") or "").strip()
                if isinstance(latest_release, dict)
                else None
            ),
            "hasRollbackCandidate": len(releases) > 1,
            "versionPreview": [
                str(row.get("version") or "").strip()
                for row in releases[:preview_cap]
                if str(row.get("version") or "").strip()
            ],
        }

    audit_counts_by_registry_type: dict[str, int] = {}
    audit_counts_by_action: dict[str, int] = {}
    latest_rollback_by_registry_type: dict[str, dict[str, Any] | None] = {}
    latest_action_by_registry_type: dict[str, dict[str, Any] | None] = {}
    for registry_type in (
        policy_registry_type,
        prompt_registry_type,
        tool_registry_type,
    ):
        audits = await list_audits(
            registry_type=registry_type,
            limit=max(1, min(int(audit_limit), 200)),
        )
        audit_counts_by_registry_type[registry_type] = len(audits)
        latest_action = audits[0] if audits else None
        latest_action_by_registry_type[registry_type] = (
            {
                "registryType": registry_type,
                "action": str(latest_action.get("action") or "").strip() or None,
                "version": str(latest_action.get("version") or "").strip() or None,
                "actor": str(latest_action.get("actor") or "").strip() or None,
                "reason": str(latest_action.get("reason") or "").strip() or None,
                "createdAt": str(latest_action.get("createdAt") or "").strip() or None,
            }
            if isinstance(latest_action, dict)
            else None
        )
        latest_rollback = next(
            (
                row
                for row in audits
                if str(row.get("action") or "").strip().lower() == "rollback"
            ),
            None,
        )
        latest_rollback_by_registry_type[registry_type] = (
            {
                "registryType": registry_type,
                "action": "rollback",
                "version": str(latest_rollback.get("version") or "").strip() or None,
                "actor": str(latest_rollback.get("actor") or "").strip() or None,
                "reason": str(latest_rollback.get("reason") or "").strip() or None,
                "createdAt": str(latest_rollback.get("createdAt") or "").strip() or None,
            }
            if isinstance(latest_rollback, dict)
            else None
        )
        for row in audits:
            action_token = str(row.get("action") or "").strip().lower() or "unknown"
            audit_counts_by_action[action_token] = (
                audit_counts_by_action.get(action_token, 0) + 1
            )

    return {
        "activeVersions": {
            "policyVersion": default_policy_version,
            "promptRegistryVersion": default_prompt_registry_version,
            "toolRegistryVersion": default_tool_registry_version,
        },
        "dependencyHealth": {
            "count": len(dependency_rows),
            "invalidCount": dependency_invalid_count,
            "items": dependency_rows,
            "byPromptRegistryVersion": dict(
                sorted(dependency_by_prompt_registry.items(), key=lambda kv: kv[0])
            ),
            "byToolRegistryVersion": dict(
                sorted(dependency_by_tool_registry.items(), key=lambda kv: kv[0])
            ),
            "issueCodeCounts": dict(
                sorted(dependency_issue_code_counts.items(), key=lambda kv: kv[0])
            ),
        },
        "reverseUsage": {
            "prompts": prompt_usage_rows,
            "tools": tool_usage_rows,
            "missingPromptRegistryRefs": missing_prompt_refs,
            "missingToolRegistryRefs": missing_tool_refs,
        },
        "domainJudgeFamilies": domain_family_overview,
        "releaseReadiness": {
            "decisionCounts": release_gate_decision_counts,
            "allowedCount": release_gate_decision_counts["allowed"],
            "blockedCount": release_gate_decision_counts["blocked"],
            "envBlockedCount": release_gate_decision_counts["env_blocked"],
            "needsReviewCount": release_gate_decision_counts["needs_review"],
            "componentBlockCounts": dict(
                sorted(release_gate_component_block_counts.items(), key=lambda kv: kv[0])
            ),
            "items": [
                {
                    "policyVersion": row.get("policyVersion"),
                    "decision": row.get("releaseGateDecision"),
                    "code": row.get("releaseGateCode"),
                    "reasonCodes": row.get("releaseGateReasonCodes"),
                }
                for row in dependency_rows
            ],
        },
        "releaseState": release_state,
        "auditSummary": {
            "countsByRegistryType": dict(
                sorted(audit_counts_by_registry_type.items(), key=lambda kv: kv[0])
            ),
            "countsByAction": dict(sorted(audit_counts_by_action.items(), key=lambda kv: kv[0])),
            "latestActionByRegistryType": latest_action_by_registry_type,
            "latestRollbackByRegistryType": latest_rollback_by_registry_type,
            "auditLimitPerRegistryType": max(1, min(int(audit_limit), 200)),
        },
        "filters": {
            "dependencyLimit": max(1, min(int(dependency_limit), 500)),
            "usagePreviewLimit": preview_cap,
            "releaseLimit": max(1, min(int(release_limit), 200)),
            "auditLimit": max(1, min(int(audit_limit), 200)),
        },
    }


def build_registry_prompt_tool_governance_payload(
    *,
    governance_overview: dict[str, Any],
    dependency_limit: int,
    usage_preview_limit: int,
    release_limit: int,
    audit_limit: int,
    risk_limit: int,
    build_registry_prompt_tool_usage_rows: Callable[..., tuple[list[dict[str, Any]], int]],
    build_registry_prompt_tool_risk_items: Callable[..., list[dict[str, Any]]],
    build_registry_prompt_tool_action_hints: Callable[..., list[dict[str, Any]]],
) -> dict[str, Any]:
    dependency_health = (
        governance_overview.get("dependencyHealth")
        if isinstance(governance_overview.get("dependencyHealth"), dict)
        else {}
    )
    reverse_usage = (
        governance_overview.get("reverseUsage")
        if isinstance(governance_overview.get("reverseUsage"), dict)
        else {}
    )
    release_state = (
        governance_overview.get("releaseState")
        if isinstance(governance_overview.get("releaseState"), dict)
        else {}
    )
    release_readiness = (
        governance_overview.get("releaseReadiness")
        if isinstance(governance_overview.get("releaseReadiness"), dict)
        else {}
    )
    audit_summary = (
        governance_overview.get("auditSummary")
        if isinstance(governance_overview.get("auditSummary"), dict)
        else {}
    )

    dependency_items = (
        dependency_health.get("items")
        if isinstance(dependency_health.get("items"), list)
        else []
    )
    prompt_usage_rows_raw = (
        reverse_usage.get("prompts")
        if isinstance(reverse_usage.get("prompts"), list)
        else []
    )
    tool_usage_rows_raw = (
        reverse_usage.get("tools")
        if isinstance(reverse_usage.get("tools"), list)
        else []
    )
    missing_prompt_refs = sorted(
        {
            str(item).strip()
            for item in (reverse_usage.get("missingPromptRegistryRefs") or [])
            if str(item).strip()
        }
    )
    missing_tool_refs = sorted(
        {
            str(item).strip()
            for item in (reverse_usage.get("missingToolRegistryRefs") or [])
            if str(item).strip()
        }
    )
    prompt_usage_rows, unreferenced_prompt_count = (
        build_registry_prompt_tool_usage_rows(usage_rows=prompt_usage_rows_raw)
    )
    tool_usage_rows, unreferenced_tool_count = (
        build_registry_prompt_tool_usage_rows(usage_rows=tool_usage_rows_raw)
    )
    all_risk_items = build_registry_prompt_tool_risk_items(
        dependency_items=dependency_items,
        prompt_usage_rows=prompt_usage_rows,
        tool_usage_rows=tool_usage_rows,
        missing_prompt_refs=missing_prompt_refs,
        missing_tool_refs=missing_tool_refs,
        release_state=release_state,
    )
    effective_risk_limit = max(1, min(int(risk_limit), 500))
    risk_items = all_risk_items[:effective_risk_limit]
    action_hints = build_registry_prompt_tool_action_hints(risk_items=all_risk_items)

    high_risk_count = sum(
        1
        for item in all_risk_items
        if str(item.get("severity") or "").strip().lower() == "high"
    )
    medium_risk_count = sum(
        1
        for item in all_risk_items
        if str(item.get("severity") or "").strip().lower() == "medium"
    )
    low_risk_count = sum(
        1
        for item in all_risk_items
        if str(item.get("severity") or "").strip().lower() == "low"
    )

    if high_risk_count > 0:
        risk_level = "high"
    elif medium_risk_count > 0:
        risk_level = "medium"
    elif low_risk_count > 0:
        risk_level = "low"
    else:
        risk_level = "healthy"

    try:
        dependency_invalid_count = max(
            0, int(dependency_health.get("invalidCount") or 0)
        )
    except (TypeError, ValueError):
        dependency_invalid_count = 0

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "activeVersions": governance_overview.get("activeVersions"),
        "summary": {
            "riskLevel": risk_level,
            "dependencyInvalidCount": dependency_invalid_count,
            "missingPromptRefCount": len(missing_prompt_refs),
            "missingToolRefCount": len(missing_tool_refs),
            "unreferencedPromptCount": unreferenced_prompt_count,
            "unreferencedToolCount": unreferenced_tool_count,
            "highRiskCount": high_risk_count,
            "mediumRiskCount": medium_risk_count,
            "lowRiskCount": low_risk_count,
            "riskTotalCount": len(all_risk_items),
            "riskReturned": len(risk_items),
            "riskTruncated": len(all_risk_items) > len(risk_items),
        },
        "dependencyHealth": {
            "count": dependency_health.get("count"),
            "invalidCount": dependency_invalid_count,
            "issueCodeCounts": (
                dependency_health.get("issueCodeCounts")
                if isinstance(dependency_health.get("issueCodeCounts"), dict)
                else {}
            ),
            "items": dependency_items,
        },
        "promptToolUsage": {
            "prompts": prompt_usage_rows,
            "tools": tool_usage_rows,
            "missingPromptRegistryRefs": missing_prompt_refs,
            "missingToolRegistryRefs": missing_tool_refs,
        },
        "releaseState": release_state,
        "releaseReadiness": release_readiness,
        "auditSummary": audit_summary,
        "domainJudgeFamilies": governance_overview.get("domainJudgeFamilies"),
        "riskItems": risk_items,
        "actionHints": action_hints,
        "filters": {
            "dependencyLimit": max(1, min(int(dependency_limit), 500)),
            "usagePreviewLimit": max(1, min(int(usage_preview_limit), 200)),
            "releaseLimit": max(1, min(int(release_limit), 200)),
            "auditLimit": max(1, min(int(audit_limit), 200)),
            "riskLimit": effective_risk_limit,
        },
        "notes": [
            (
                "prompt/tool governance view is read-only; actionHints never "
                "trigger publish, activate, or rollback automatically."
            )
        ],
    }


def build_policy_domain_judge_families_payload(
    *,
    default_policy_version: str,
    policy_profiles: list[Any],
    preview_limit: int,
    include_versions: bool,
    build_policy_domain_judge_family_overview: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    overview = build_policy_domain_judge_family_overview(
        policy_profiles=policy_profiles,
        active_policy_version=default_policy_version,
        preview_limit=preview_limit,
        include_versions=include_versions,
    )
    return {
        "activePolicyVersion": default_policy_version,
        "domainJudgeFamilies": overview,
        "filters": {
            "previewLimit": max(1, min(int(preview_limit), 200)),
            "includeVersions": bool(include_versions),
        },
    }


async def build_policy_gate_simulation_payload(
    *,
    policy_version: str | None,
    default_policy_version: str,
    include_all_versions: bool,
    limit: int,
    list_policy_profiles: Callable[[], list[Any]],
    get_policy_profile: Callable[[str], Any | None],
    serialize_policy_profile: Callable[[Any], dict[str, Any]],
    evaluate_policy_registry_dependency_health: Callable[[str], Awaitable[dict[str, Any]]],
    evaluate_policy_release_fairness_gate: Callable[[str], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    selected_policy_version = str(policy_version or "").strip() or default_policy_version
    if not selected_policy_version:
        raise ValueError("invalid_policy_version")

    policy_versions: list[str] = []
    if include_all_versions:
        seen_versions: set[str] = set()
        for row in list_policy_profiles():
            version_token = str(getattr(row, "version", "") or "").strip()
            if not version_token or version_token in seen_versions:
                continue
            seen_versions.add(version_token)
            policy_versions.append(version_token)
        if selected_policy_version not in seen_versions:
            policy_versions.insert(0, selected_policy_version)
    else:
        policy_versions = [selected_policy_version]

    evaluated_items: list[dict[str, Any]] = []
    for version_token in policy_versions[: max(1, min(int(limit), 200))]:
        profile = get_policy_profile(version_token)
        if profile is None:
            if version_token == selected_policy_version:
                raise LookupError("policy_registry_not_found")
            continue
        profile_payload = serialize_policy_profile(profile)
        metadata = (
            profile_payload.get("metadata")
            if isinstance(profile_payload.get("metadata"), dict)
            else {}
        )
        dependency_health = await evaluate_policy_registry_dependency_health(version_token)
        fairness_gate = await evaluate_policy_release_fairness_gate(version_token)
        release_gate = build_policy_release_gate_decision(
            dependency_health=dependency_health,
            fairness_gate=fairness_gate,
        )
        failing_components: list[str] = []
        if not bool(dependency_health.get("ok")):
            failing_components.append("dependency_health")
        if not bool(fairness_gate.get("passed")):
            failing_components.append("fairness_gate")
        if not bool(metadata.get("domainJudgeFamilyValid")):
            failing_components.append("domain_judge_family")
        for reason in release_gate.get("reasons") or []:
            if not isinstance(reason, dict):
                continue
            component = str(reason.get("component") or "").strip()
            if component and component not in failing_components:
                failing_components.append(component)
        simulated_passed = bool(release_gate.get("allowed")) and len(failing_components) == 0
        if simulated_passed:
            simulated_status = "allowed"
            simulated_code = "registry_policy_gate_simulation_passed"
        elif bool(release_gate.get("allowed")):
            simulated_status = "blocked"
            simulated_code = "registry_policy_gate_simulation_blocked"
        else:
            simulated_status = str(release_gate.get("status") or "").strip() or "blocked"
            simulated_code = str(release_gate.get("code") or "").strip() or (
                "registry_policy_gate_simulation_blocked"
            )

        evaluated_items.append(
            {
                "policyVersion": version_token,
                "topicDomain": str(profile_payload.get("topicDomain") or "").strip() or "general",
                "domainJudgeFamily": {
                    "family": str(metadata.get("domainJudgeFamily") or "").strip() or None,
                    "valid": bool(metadata.get("domainJudgeFamilyValid")),
                    "errorCode": str(metadata.get("domainJudgeFamilyError") or "").strip() or None,
                },
                "dependencyHealth": dependency_health,
                "fairnessGate": fairness_gate,
                "releaseGate": release_gate,
                "simulatedGate": {
                    "passed": simulated_passed,
                    "status": simulated_status,
                    "code": simulated_code,
                    "reason": (
                        "all checks passed"
                        if simulated_passed
                        else f"blocked by {','.join(failing_components)}"
                    ),
                    "failingComponents": failing_components,
                },
            }
        )

    pass_count = 0
    blocked_count = 0
    for row in evaluated_items:
        simulated_gate = (
            row.get("simulatedGate")
            if isinstance(row.get("simulatedGate"), dict)
            else {}
        )
        if bool(simulated_gate.get("passed")):
            pass_count += 1
        else:
            blocked_count += 1

    return {
        "activePolicyVersion": default_policy_version,
        "selectedPolicyVersion": selected_policy_version,
        "count": len(evaluated_items),
        "items": evaluated_items,
        "summary": {
            "passCount": pass_count,
            "blockedCount": blocked_count,
            "advisoryOnly": True,
        },
        "filters": {
            "policyVersion": selected_policy_version,
            "includeAllVersions": bool(include_all_versions),
            "limit": max(1, min(int(limit), 200)),
        },
        "notes": [
            (
                "simulation is advisory-only and never triggers publish/activate "
                "or emits registry gate alerts."
            )
        ],
    }
