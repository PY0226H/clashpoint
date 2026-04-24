from __future__ import annotations

from functools import partial
from typing import Any, Awaitable, Callable

from fastapi import HTTPException

from .registry_governance_routes import (
    RegistryGovernanceRouteDependencyPack as RegistryGovernanceRouteDependencyPack_v3,
)
from .registry_governance_routes import (
    serialize_policy_profile_with_domain_family as serialize_policy_profile_with_domain_family_v3,
)
from .registry_ops_views import (
    build_registry_audit_ops_view as build_registry_audit_ops_view_v3,
)
from .registry_ops_views import (
    build_registry_dependency_overview as build_registry_dependency_overview_v3,
)
from .registry_ops_views import (
    build_registry_dependency_trend as build_registry_dependency_trend_v3,
)
from .registry_ops_views import (
    build_registry_prompt_tool_action_hints as build_registry_prompt_tool_action_hints_v3,
)
from .registry_ops_views import (
    build_registry_prompt_tool_risk_items as build_registry_prompt_tool_risk_items_v3,
)
from .registry_ops_views import (
    build_registry_prompt_tool_usage_rows as build_registry_prompt_tool_usage_rows_v3,
)
from .registry_ops_views import (
    normalize_registry_audit_action as normalize_registry_audit_action_v3,
)
from .registry_ops_views import (
    normalize_registry_dependency_trend_status as normalize_registry_dependency_trend_status_v3,
)
from .registry_routes import RegistryRouteError as RegistryRouteErrorV3
from .registry_routes import build_registry_audits_payload as build_registry_audits_payload_v3
from .registry_routes import build_registry_profile_payload as build_registry_profile_payload_v3
from .registry_routes import build_registry_profiles_payload as build_registry_profiles_payload_v3
from .registry_routes import build_registry_release_payload as build_registry_release_payload_v3
from .registry_routes import build_registry_releases_payload as build_registry_releases_payload_v3


async def run_registry_route_guard_for_runtime(
    self_awaitable: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    try:
        return await self_awaitable
    except RegistryRouteErrorV3 as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail) from err


def raise_policy_registry_not_found_lookup_error(*, err: LookupError) -> None:
    if str(err) == "policy_registry_not_found":
        raise HTTPException(status_code=404, detail="policy_registry_not_found") from err


def raise_registry_version_not_found_lookup_error(*, err: LookupError) -> None:
    raise HTTPException(status_code=404, detail="registry_version_not_found") from err


def raise_registry_value_error(
    *,
    err: ValueError,
    default_detail: str,
    unprocessable_codes: set[str],
    conflict_codes: set[str] | None = None,
) -> None:
    code = str(err)
    if isinstance(conflict_codes, set) and code in conflict_codes:
        raise HTTPException(status_code=409, detail=code) from err
    if code in unprocessable_codes:
        raise HTTPException(status_code=422, detail=code) from err
    raise HTTPException(status_code=422, detail=default_detail) from err


def serialize_policy_profile_with_domain_family_for_runtime(
    profile: Any,
    *,
    runtime: Any,
    resolve_policy_domain_judge_family_state: Callable[..., tuple[str, bool, str | None]],
) -> dict[str, Any]:
    return serialize_policy_profile_with_domain_family_v3(
        profile=profile,
        serialize_policy_profile=runtime.policy_registry_runtime.serialize_profile,
        resolve_policy_domain_judge_family_state=resolve_policy_domain_judge_family_state,
    )


def evaluate_policy_registry_dependency_health_for_governance(
    version: str,
    *,
    evaluate_policy_registry_dependency_health: Callable[[str], Awaitable[dict[str, Any]]],
) -> Awaitable[dict[str, Any]]:
    return evaluate_policy_registry_dependency_health(policy_version=version)


def evaluate_policy_release_fairness_gate_for_governance(
    version: str,
    *,
    evaluate_policy_release_fairness_gate: Callable[[str], Awaitable[dict[str, Any]]],
) -> Awaitable[dict[str, Any]]:
    return evaluate_policy_release_fairness_gate(policy_version=version)


def build_registry_governance_route_dependency_pack_for_runtime(
    *,
    runtime: Any,
    registry_type_policy: str,
    dependency_trend_status_values: set[str],
    resolve_policy_domain_judge_family_state: Callable[..., tuple[str, bool, str | None]],
    build_policy_domain_judge_family_overview: Callable[..., dict[str, Any]],
    evaluate_policy_registry_dependency_health: Callable[[str], Awaitable[dict[str, Any]]],
    evaluate_policy_release_fairness_gate: Callable[[str], Awaitable[dict[str, Any]]],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
) -> RegistryGovernanceRouteDependencyPack_v3:
    serialize_policy_profile = partial(
        serialize_policy_profile_with_domain_family_for_runtime,
        runtime=runtime,
        resolve_policy_domain_judge_family_state=resolve_policy_domain_judge_family_state,
    )
    evaluate_dependency_health = partial(
        evaluate_policy_registry_dependency_health_for_governance,
        evaluate_policy_registry_dependency_health=(
            evaluate_policy_registry_dependency_health
        ),
    )
    evaluate_fairness_gate = partial(
        evaluate_policy_release_fairness_gate_for_governance,
        evaluate_policy_release_fairness_gate=evaluate_policy_release_fairness_gate,
    )
    return RegistryGovernanceRouteDependencyPack_v3(
        default_policy_version=runtime.policy_registry_runtime.default_version,
        default_prompt_registry_version=runtime.prompt_registry_runtime.default_version,
        default_tool_registry_version=runtime.tool_registry_runtime.default_version,
        policy_registry_type=registry_type_policy,
        prompt_registry_type="prompt",
        tool_registry_type="tool",
        list_policy_profiles=runtime.policy_registry_runtime.list_profiles,
        list_prompt_profiles=runtime.prompt_registry_runtime.list_profiles,
        list_tool_profiles=runtime.tool_registry_runtime.list_profiles,
        get_policy_profile=runtime.policy_registry_runtime.get_profile,
        serialize_policy_profile=serialize_policy_profile,
        evaluate_policy_registry_dependency_health=evaluate_dependency_health,
        evaluate_policy_release_fairness_gate=evaluate_fairness_gate,
        list_releases=runtime.registry_product_runtime.list_releases,
        list_audits=runtime.registry_product_runtime.list_audits,
        normalize_registry_dependency_trend_status=(
            normalize_registry_dependency_trend_status_v3
        ),
        dependency_trend_status_values=dependency_trend_status_values,
        list_audit_alerts=list_audit_alerts,
        build_registry_dependency_overview=build_registry_dependency_overview_v3,
        build_registry_dependency_trend=build_registry_dependency_trend_v3,
        build_policy_domain_judge_family_overview=(
            build_policy_domain_judge_family_overview
        ),
        build_registry_prompt_tool_usage_rows=build_registry_prompt_tool_usage_rows_v3,
        build_registry_prompt_tool_risk_items=build_registry_prompt_tool_risk_items_v3,
        build_registry_prompt_tool_action_hints=build_registry_prompt_tool_action_hints_v3,
    )


def build_registry_profiles_payload_for_runtime(
    *,
    list_profiles: Callable[[], list[Any]],
    default_version: str,
    serializer: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    return build_registry_profiles_payload_v3(
        default_version=default_version,
        profiles=list_profiles(),
        serializer=serializer,
    )


async def build_registry_profiles_payload_with_ready_for_runtime(
    *,
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    list_profiles: Callable[[], list[Any]],
    default_version: str,
    serializer: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    await ensure_registry_runtime_ready()
    return build_registry_profiles_payload_for_runtime(
        list_profiles=list_profiles,
        default_version=default_version,
        serializer=serializer,
    )


def build_registry_profile_payload_for_runtime(
    *,
    version: str,
    get_profile: Callable[[str], Any | None],
    serializer: Callable[[Any], dict[str, Any]],
    not_found_detail: str,
) -> dict[str, Any]:
    profile = get_profile(version)
    if profile is None:
        raise HTTPException(status_code=404, detail=not_found_detail)
    return build_registry_profile_payload_v3(
        profile=profile,
        serializer=serializer,
    )


async def build_registry_profile_payload_with_ready_for_runtime(
    *,
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    version: str,
    get_profile: Callable[[str], Any | None],
    serializer: Callable[[Any], dict[str, Any]],
    not_found_detail: str,
) -> dict[str, Any]:
    await ensure_registry_runtime_ready()
    return build_registry_profile_payload_for_runtime(
        version=version,
        get_profile=get_profile,
        serializer=serializer,
        not_found_detail=not_found_detail,
    )


def build_policy_registry_profiles_payload_for_runtime(
    *,
    runtime: Any,
    serialize_policy_profile_with_domain_family: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    return build_registry_profiles_payload_for_runtime(
        list_profiles=runtime.policy_registry_runtime.list_profiles,
        default_version=runtime.policy_registry_runtime.default_version,
        serializer=serialize_policy_profile_with_domain_family,
    )


async def build_policy_registry_profiles_payload_with_ready_for_runtime(
    *,
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    runtime: Any,
    serialize_policy_profile_with_domain_family: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    await ensure_registry_runtime_ready()
    return build_policy_registry_profiles_payload_for_runtime(
        runtime=runtime,
        serialize_policy_profile_with_domain_family=(
            serialize_policy_profile_with_domain_family
        ),
    )


def build_policy_registry_profile_payload_for_runtime(
    *,
    policy_version: str,
    runtime: Any,
    serialize_policy_profile_with_domain_family: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    return build_registry_profile_payload_for_runtime(
        version=policy_version,
        get_profile=runtime.policy_registry_runtime.get_profile,
        serializer=serialize_policy_profile_with_domain_family,
        not_found_detail="judge_policy_not_found",
    )


async def build_policy_registry_profile_payload_with_ready_for_runtime(
    *,
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    policy_version: str,
    runtime: Any,
    serialize_policy_profile_with_domain_family: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    await ensure_registry_runtime_ready()
    return build_policy_registry_profile_payload_for_runtime(
        policy_version=policy_version,
        runtime=runtime,
        serialize_policy_profile_with_domain_family=(
            serialize_policy_profile_with_domain_family
        ),
    )


async def build_registry_audits_payload_for_runtime(
    *,
    runtime: Any,
    registry_audit_action_values: set[str],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
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
) -> dict[str, Any]:
    try:
        return await build_registry_audits_payload_v3(
            registry_type=registry_type,
            action=action,
            version=version,
            actor=actor,
            gate_code=gate_code,
            override_applied=override_applied,
            include_gate_view=include_gate_view,
            link_limit=link_limit,
            offset=offset,
            limit=limit,
            normalize_registry_audit_action=normalize_registry_audit_action_v3,
            registry_audit_action_values=registry_audit_action_values,
            list_registry_audits=runtime.registry_product_runtime.list_audits,
            list_audit_alerts=list_audit_alerts,
            list_alert_outbox=runtime.trace_store.list_alert_outbox,
            build_registry_audit_ops_view=build_registry_audit_ops_view_v3,
        )
    except ValueError as err:
        raise_registry_value_error(
            err=err,
            default_detail="registry_audit_query_invalid",
            unprocessable_codes={
                "invalid_registry_audit_action",
                "invalid_registry_type",
            },
        )


async def build_registry_releases_payload_for_runtime(
    *,
    runtime: Any,
    registry_type: str,
    limit: int,
    include_payload: bool,
) -> dict[str, Any]:
    try:
        items = await runtime.registry_product_runtime.list_releases(
            registry_type=registry_type,
            limit=limit,
            include_payload=include_payload,
        )
    except ValueError as err:
        raise_registry_value_error(
            err=err,
            default_detail="registry_release_query_invalid",
            unprocessable_codes={"invalid_registry_type"},
        )
    return build_registry_releases_payload_v3(
        registry_type=registry_type,
        items=items,
        limit=limit,
        include_payload=include_payload,
    )


async def build_registry_release_payload_for_runtime(
    *,
    runtime: Any,
    registry_type: str,
    version: str,
    not_found_detail: str,
) -> dict[str, Any]:
    try:
        item = await runtime.registry_product_runtime.get_release(
            registry_type=registry_type,
            version=version,
        )
    except ValueError as err:
        raise_registry_value_error(
            err=err,
            default_detail="registry_release_query_invalid",
            unprocessable_codes={
                "invalid_registry_type",
                "invalid_registry_version",
            },
        )
    if item is None:
        raise HTTPException(status_code=404, detail=not_found_detail)
    return build_registry_release_payload_v3(item=item)
