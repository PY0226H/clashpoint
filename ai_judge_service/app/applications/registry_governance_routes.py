from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .registry_routes import (
    REGISTRY_DEPENDENCY_NOT_FOUND_CODE,
    RegistryRouteError,
    build_policy_domain_judge_families_payload,
    build_policy_gate_simulation_payload,
    build_policy_registry_dependency_health_payload,
    build_registry_governance_overview_payload,
    build_registry_prompt_tool_governance_payload,
)


@dataclass(frozen=True)
class RegistryGovernanceRouteDependencyPack:
    default_policy_version: str
    default_prompt_registry_version: str
    default_tool_registry_version: str
    policy_registry_type: str
    prompt_registry_type: str
    tool_registry_type: str
    list_policy_profiles: Callable[[], list[Any]]
    list_prompt_profiles: Callable[[], list[Any]]
    list_tool_profiles: Callable[[], list[Any]]
    get_policy_profile: Callable[[str], Any | None]
    serialize_policy_profile: Callable[[Any], dict[str, Any]]
    evaluate_policy_registry_dependency_health: Callable[[str], Awaitable[dict[str, Any]]]
    evaluate_policy_release_fairness_gate: Callable[[str], Awaitable[dict[str, Any]]]
    list_releases: Callable[..., Awaitable[list[dict[str, Any]]]]
    list_audits: Callable[..., Awaitable[list[dict[str, Any]]]]
    normalize_registry_dependency_trend_status: Callable[[str | None], str | None]
    dependency_trend_status_values: set[str] | frozenset[str]
    list_audit_alerts: Callable[..., Awaitable[list[Any]]]
    build_registry_dependency_overview: Callable[..., dict[str, Any]]
    build_registry_dependency_trend: Callable[..., dict[str, Any]]
    build_policy_domain_judge_family_overview: Callable[..., dict[str, Any]]
    build_registry_prompt_tool_usage_rows: Callable[..., tuple[list[dict[str, Any]], int]]
    build_registry_prompt_tool_risk_items: Callable[..., list[dict[str, Any]]]
    build_registry_prompt_tool_action_hints: Callable[..., list[dict[str, Any]]]


def serialize_policy_profile_with_domain_family(
    *,
    profile: Any,
    serialize_policy_profile: Callable[[Any], dict[str, Any]],
    resolve_policy_domain_judge_family_state: Callable[..., tuple[str, bool, str | None]],
) -> dict[str, Any]:
    payload = serialize_policy_profile(profile)
    metadata = (
        dict(payload.get("metadata"))
        if isinstance(payload.get("metadata"), dict)
        else {}
    )
    family, valid, error_code = resolve_policy_domain_judge_family_state(
        topic_domain=payload.get("topicDomain") or payload.get("topic_domain"),
        metadata=metadata,
    )
    metadata["domainJudgeFamily"] = family
    metadata["domainJudgeFamilyValid"] = bool(valid)
    if error_code:
        metadata["domainJudgeFamilyError"] = error_code
    else:
        metadata.pop("domainJudgeFamilyError", None)
    payload["metadata"] = metadata
    return payload


async def build_policy_registry_dependency_health_route_payload(
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
    try:
        return await build_policy_registry_dependency_health_payload(
            policy_version=policy_version,
            default_policy_version=default_policy_version,
            default_prompt_registry_version=default_prompt_registry_version,
            default_tool_registry_version=default_tool_registry_version,
            include_all_versions=include_all_versions,
            include_overview=include_overview,
            include_trend=include_trend,
            trend_status=trend_status,
            trend_policy_version=trend_policy_version,
            trend_offset=trend_offset,
            trend_limit=trend_limit,
            overview_window_minutes=overview_window_minutes,
            limit=limit,
            list_policy_profiles=list_policy_profiles,
            evaluate_policy_registry_dependency_health=(
                evaluate_policy_registry_dependency_health
            ),
            normalize_registry_dependency_trend_status=(
                normalize_registry_dependency_trend_status
            ),
            dependency_trend_status_values=dependency_trend_status_values,
            list_audit_alerts=list_audit_alerts,
            build_registry_dependency_overview=build_registry_dependency_overview,
            build_registry_dependency_trend=build_registry_dependency_trend,
        )
    except ValueError as err:
        if str(err) == "invalid_trend_status":
            raise RegistryRouteError(status_code=422, detail="invalid_trend_status") from err
        raise
    except LookupError as err:
        if str(err) == REGISTRY_DEPENDENCY_NOT_FOUND_CODE:
            raise RegistryRouteError(
                status_code=404,
                detail=REGISTRY_DEPENDENCY_NOT_FOUND_CODE,
            ) from err
        raise


async def build_policy_registry_dependency_health_route_payload_from_pack(
    *,
    pack: RegistryGovernanceRouteDependencyPack,
    policy_version: str | None,
    include_all_versions: bool,
    include_overview: bool,
    include_trend: bool,
    trend_status: str | None,
    trend_policy_version: str | None,
    trend_offset: int,
    trend_limit: int,
    overview_window_minutes: int,
    limit: int,
) -> dict[str, Any]:
    return await build_policy_registry_dependency_health_route_payload(
        policy_version=policy_version,
        default_policy_version=pack.default_policy_version,
        default_prompt_registry_version=pack.default_prompt_registry_version,
        default_tool_registry_version=pack.default_tool_registry_version,
        include_all_versions=include_all_versions,
        include_overview=include_overview,
        include_trend=include_trend,
        trend_status=trend_status,
        trend_policy_version=trend_policy_version,
        trend_offset=trend_offset,
        trend_limit=trend_limit,
        overview_window_minutes=overview_window_minutes,
        limit=limit,
        list_policy_profiles=pack.list_policy_profiles,
        evaluate_policy_registry_dependency_health=(
            pack.evaluate_policy_registry_dependency_health
        ),
        normalize_registry_dependency_trend_status=(
            pack.normalize_registry_dependency_trend_status
        ),
        dependency_trend_status_values=pack.dependency_trend_status_values,
        list_audit_alerts=pack.list_audit_alerts,
        build_registry_dependency_overview=pack.build_registry_dependency_overview,
        build_registry_dependency_trend=pack.build_registry_dependency_trend,
    )


async def build_registry_governance_overview_route_payload(
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
    return await build_registry_governance_overview_payload(
        dependency_limit=dependency_limit,
        usage_preview_limit=usage_preview_limit,
        release_limit=release_limit,
        audit_limit=audit_limit,
        default_policy_version=default_policy_version,
        default_prompt_registry_version=default_prompt_registry_version,
        default_tool_registry_version=default_tool_registry_version,
        policy_registry_type=policy_registry_type,
        prompt_registry_type=prompt_registry_type,
        tool_registry_type=tool_registry_type,
        list_policy_profiles=list_policy_profiles,
        list_prompt_profiles=list_prompt_profiles,
        list_tool_profiles=list_tool_profiles,
        evaluate_policy_registry_dependency_health=(
            evaluate_policy_registry_dependency_health
        ),
        evaluate_policy_release_fairness_gate=evaluate_policy_release_fairness_gate,
        list_releases=list_releases,
        list_audits=list_audits,
        build_policy_domain_judge_family_overview=(
            build_policy_domain_judge_family_overview
        ),
    )


async def build_registry_governance_overview_route_payload_from_pack(
    *,
    pack: RegistryGovernanceRouteDependencyPack,
    dependency_limit: int,
    usage_preview_limit: int,
    release_limit: int,
    audit_limit: int,
) -> dict[str, Any]:
    return await build_registry_governance_overview_route_payload(
        dependency_limit=dependency_limit,
        usage_preview_limit=usage_preview_limit,
        release_limit=release_limit,
        audit_limit=audit_limit,
        default_policy_version=pack.default_policy_version,
        default_prompt_registry_version=pack.default_prompt_registry_version,
        default_tool_registry_version=pack.default_tool_registry_version,
        policy_registry_type=pack.policy_registry_type,
        prompt_registry_type=pack.prompt_registry_type,
        tool_registry_type=pack.tool_registry_type,
        list_policy_profiles=pack.list_policy_profiles,
        list_prompt_profiles=pack.list_prompt_profiles,
        list_tool_profiles=pack.list_tool_profiles,
        evaluate_policy_registry_dependency_health=(
            pack.evaluate_policy_registry_dependency_health
        ),
        evaluate_policy_release_fairness_gate=(
            pack.evaluate_policy_release_fairness_gate
        ),
        list_releases=pack.list_releases,
        list_audits=pack.list_audits,
        build_policy_domain_judge_family_overview=(
            pack.build_policy_domain_judge_family_overview
        ),
    )


async def build_registry_prompt_tool_governance_route_payload(
    *,
    dependency_limit: int,
    usage_preview_limit: int,
    release_limit: int,
    audit_limit: int,
    risk_limit: int,
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
    build_registry_prompt_tool_usage_rows: Callable[..., tuple[list[dict[str, Any]], int]],
    build_registry_prompt_tool_risk_items: Callable[..., list[dict[str, Any]]],
    build_registry_prompt_tool_action_hints: Callable[..., list[dict[str, Any]]],
) -> dict[str, Any]:
    governance_overview = await build_registry_governance_overview_route_payload(
        dependency_limit=dependency_limit,
        usage_preview_limit=usage_preview_limit,
        release_limit=release_limit,
        audit_limit=audit_limit,
        default_policy_version=default_policy_version,
        default_prompt_registry_version=default_prompt_registry_version,
        default_tool_registry_version=default_tool_registry_version,
        policy_registry_type=policy_registry_type,
        prompt_registry_type=prompt_registry_type,
        tool_registry_type=tool_registry_type,
        list_policy_profiles=list_policy_profiles,
        list_prompt_profiles=list_prompt_profiles,
        list_tool_profiles=list_tool_profiles,
        evaluate_policy_registry_dependency_health=(
            evaluate_policy_registry_dependency_health
        ),
        evaluate_policy_release_fairness_gate=evaluate_policy_release_fairness_gate,
        list_releases=list_releases,
        list_audits=list_audits,
        build_policy_domain_judge_family_overview=(
            build_policy_domain_judge_family_overview
        ),
    )
    return build_registry_prompt_tool_governance_payload(
        governance_overview=governance_overview,
        dependency_limit=dependency_limit,
        usage_preview_limit=usage_preview_limit,
        release_limit=release_limit,
        audit_limit=audit_limit,
        risk_limit=risk_limit,
        build_registry_prompt_tool_usage_rows=build_registry_prompt_tool_usage_rows,
        build_registry_prompt_tool_risk_items=build_registry_prompt_tool_risk_items,
        build_registry_prompt_tool_action_hints=build_registry_prompt_tool_action_hints,
    )


async def build_registry_prompt_tool_governance_route_payload_from_pack(
    *,
    pack: RegistryGovernanceRouteDependencyPack,
    dependency_limit: int,
    usage_preview_limit: int,
    release_limit: int,
    audit_limit: int,
    risk_limit: int,
) -> dict[str, Any]:
    return await build_registry_prompt_tool_governance_route_payload(
        dependency_limit=dependency_limit,
        usage_preview_limit=usage_preview_limit,
        release_limit=release_limit,
        audit_limit=audit_limit,
        risk_limit=risk_limit,
        default_policy_version=pack.default_policy_version,
        default_prompt_registry_version=pack.default_prompt_registry_version,
        default_tool_registry_version=pack.default_tool_registry_version,
        policy_registry_type=pack.policy_registry_type,
        prompt_registry_type=pack.prompt_registry_type,
        tool_registry_type=pack.tool_registry_type,
        list_policy_profiles=pack.list_policy_profiles,
        list_prompt_profiles=pack.list_prompt_profiles,
        list_tool_profiles=pack.list_tool_profiles,
        evaluate_policy_registry_dependency_health=(
            pack.evaluate_policy_registry_dependency_health
        ),
        evaluate_policy_release_fairness_gate=(
            pack.evaluate_policy_release_fairness_gate
        ),
        list_releases=pack.list_releases,
        list_audits=pack.list_audits,
        build_policy_domain_judge_family_overview=(
            pack.build_policy_domain_judge_family_overview
        ),
        build_registry_prompt_tool_usage_rows=pack.build_registry_prompt_tool_usage_rows,
        build_registry_prompt_tool_risk_items=pack.build_registry_prompt_tool_risk_items,
        build_registry_prompt_tool_action_hints=pack.build_registry_prompt_tool_action_hints,
    )


async def build_policy_domain_judge_families_route_payload(
    *,
    default_policy_version: str,
    policy_profiles: list[Any],
    preview_limit: int,
    include_versions: bool,
    build_policy_domain_judge_family_overview: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    return build_policy_domain_judge_families_payload(
        default_policy_version=default_policy_version,
        policy_profiles=policy_profiles,
        preview_limit=preview_limit,
        include_versions=include_versions,
        build_policy_domain_judge_family_overview=(
            build_policy_domain_judge_family_overview
        ),
    )


async def build_policy_domain_judge_families_route_payload_from_pack(
    *,
    pack: RegistryGovernanceRouteDependencyPack,
    preview_limit: int,
    include_versions: bool,
) -> dict[str, Any]:
    return await build_policy_domain_judge_families_route_payload(
        default_policy_version=pack.default_policy_version,
        policy_profiles=pack.list_policy_profiles(),
        preview_limit=preview_limit,
        include_versions=include_versions,
        build_policy_domain_judge_family_overview=(
            pack.build_policy_domain_judge_family_overview
        ),
    )


async def build_policy_gate_simulation_route_payload(
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
    try:
        return await build_policy_gate_simulation_payload(
            policy_version=policy_version,
            default_policy_version=default_policy_version,
            include_all_versions=include_all_versions,
            limit=limit,
            list_policy_profiles=list_policy_profiles,
            get_policy_profile=get_policy_profile,
            serialize_policy_profile=serialize_policy_profile,
            evaluate_policy_registry_dependency_health=(
                evaluate_policy_registry_dependency_health
            ),
            evaluate_policy_release_fairness_gate=(
                evaluate_policy_release_fairness_gate
            ),
        )
    except ValueError as err:
        if str(err) == "invalid_policy_version":
            raise RegistryRouteError(status_code=422, detail="invalid_policy_version") from err
        raise
    except LookupError as err:
        if str(err) == REGISTRY_DEPENDENCY_NOT_FOUND_CODE:
            raise RegistryRouteError(
                status_code=404,
                detail=REGISTRY_DEPENDENCY_NOT_FOUND_CODE,
            ) from err
        raise


async def build_policy_gate_simulation_route_payload_from_pack(
    *,
    pack: RegistryGovernanceRouteDependencyPack,
    policy_version: str | None,
    include_all_versions: bool,
    limit: int,
) -> dict[str, Any]:
    return await build_policy_gate_simulation_route_payload(
        policy_version=policy_version,
        default_policy_version=pack.default_policy_version,
        include_all_versions=include_all_versions,
        limit=limit,
        list_policy_profiles=pack.list_policy_profiles,
        get_policy_profile=pack.get_policy_profile,
        serialize_policy_profile=pack.serialize_policy_profile,
        evaluate_policy_registry_dependency_health=(
            pack.evaluate_policy_registry_dependency_health
        ),
        evaluate_policy_release_fairness_gate=(
            pack.evaluate_policy_release_fairness_gate
        ),
    )
