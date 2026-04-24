from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, Query, Request

from .judge_command_routes import extract_optional_bool as extract_optional_bool_v3
from .registry_governance_routes import (
    build_policy_domain_judge_families_route_payload_from_pack as build_policy_domain_judge_families_route_payload_from_pack_v3,
)
from .registry_governance_routes import (
    build_policy_gate_simulation_route_payload_from_pack as build_policy_gate_simulation_route_payload_from_pack_v3,
)
from .registry_governance_routes import (
    build_policy_registry_dependency_health_route_payload_from_pack as build_policy_registry_dependency_health_route_payload_from_pack_v3,
)
from .registry_governance_routes import (
    build_registry_governance_overview_route_payload_from_pack as build_registry_governance_overview_route_payload_from_pack_v3,
)
from .registry_governance_routes import (
    build_registry_prompt_tool_governance_route_payload_from_pack as build_registry_prompt_tool_governance_route_payload_from_pack_v3,
)
from .registry_routes import (
    build_registry_activate_payload as build_registry_activate_payload_v3,
)
from .registry_routes import (
    build_registry_publish_payload as build_registry_publish_payload_v3,
)
from .registry_routes import (
    build_registry_rollback_payload as build_registry_rollback_payload_v3,
)
from .registry_routes import (
    parse_registry_publish_request_payload as parse_registry_publish_request_payload_v3,
)

AsyncPayloadFn = Callable[..., Awaitable[dict[str, Any]]]
RequireInternalKeyFn = Callable[[Any, str | None], None]
RegistryRouteGuardFn = Callable[[Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class RegistryRouteHandles:
    get_policy_registry_dependency_health: AsyncPayloadFn
    get_registry_governance_overview: AsyncPayloadFn
    get_registry_prompt_tool_governance: AsyncPayloadFn
    simulate_policy_release_gate: AsyncPayloadFn


def register_registry_routes(
    *,
    app: FastAPI,
    runtime: Any,
    require_internal_key_fn: RequireInternalKeyFn,
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    serialize_policy_profile_with_domain_family: Callable[..., dict[str, Any]],
    build_registry_governance_dependency_pack: Callable[[], Any],
    registry_release_gate_dependencies: dict[str, Any],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    read_json_object_or_raise_422: Callable[..., Awaitable[dict[str, Any]]],
    run_registry_route_guard: RegistryRouteGuardFn,
    build_policy_registry_profiles_payload_with_ready: AsyncPayloadFn,
    build_policy_registry_profile_payload_with_ready: AsyncPayloadFn,
    build_registry_profiles_payload_with_ready: AsyncPayloadFn,
    build_registry_profile_payload_with_ready: AsyncPayloadFn,
    build_registry_audits_payload: AsyncPayloadFn,
    build_registry_releases_payload: AsyncPayloadFn,
    build_registry_release_payload: AsyncPayloadFn,
    enforce_policy_domain_judge_family_profile_payload: Callable[..., None],
    raise_http_422_from_value_error: Callable[..., None],
    raise_http_404_from_lookup_error: Callable[..., None],
    raise_registry_value_error: Callable[..., None],
    raise_registry_version_not_found_lookup_error: Callable[..., None],
) -> RegistryRouteHandles:
    @app.get("/internal/judge/policies")
    async def list_judge_policies(
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await build_policy_registry_profiles_payload_with_ready(
            ensure_registry_runtime_ready=ensure_registry_runtime_ready,
            runtime=runtime,
            serialize_policy_profile_with_domain_family=(
                serialize_policy_profile_with_domain_family
            ),
        )

    @app.get("/internal/judge/policies/{policy_version}")
    async def get_judge_policy(
        policy_version: str,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await build_policy_registry_profile_payload_with_ready(
            ensure_registry_runtime_ready=ensure_registry_runtime_ready,
            policy_version=policy_version,
            runtime=runtime,
            serialize_policy_profile_with_domain_family=(
                serialize_policy_profile_with_domain_family
            ),
        )

    @app.get("/internal/judge/registries/prompts")
    async def list_prompt_registries(
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await build_registry_profiles_payload_with_ready(
            ensure_registry_runtime_ready=ensure_registry_runtime_ready,
            list_profiles=runtime.prompt_registry_runtime.list_profiles,
            default_version=runtime.prompt_registry_runtime.default_version,
            serializer=runtime.prompt_registry_runtime.serialize_profile,
        )

    @app.get("/internal/judge/registries/prompts/{prompt_version}")
    async def get_prompt_registry(
        prompt_version: str,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await build_registry_profile_payload_with_ready(
            ensure_registry_runtime_ready=ensure_registry_runtime_ready,
            version=prompt_version,
            get_profile=runtime.prompt_registry_runtime.get_profile,
            serializer=runtime.prompt_registry_runtime.serialize_profile,
            not_found_detail="prompt_registry_not_found",
        )

    @app.get("/internal/judge/registries/tools")
    async def list_tool_registries(
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await build_registry_profiles_payload_with_ready(
            ensure_registry_runtime_ready=ensure_registry_runtime_ready,
            list_profiles=runtime.tool_registry_runtime.list_profiles,
            default_version=runtime.tool_registry_runtime.default_version,
            serializer=runtime.tool_registry_runtime.serialize_profile,
        )

    @app.get("/internal/judge/registries/tools/{toolset_version}")
    async def get_tool_registry(
        toolset_version: str,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await build_registry_profile_payload_with_ready(
            ensure_registry_runtime_ready=ensure_registry_runtime_ready,
            version=toolset_version,
            get_profile=runtime.tool_registry_runtime.get_profile,
            serializer=runtime.tool_registry_runtime.serialize_profile,
            not_found_detail="tool_registry_not_found",
        )

    @app.get("/internal/judge/registries/policy/dependencies/health")
    async def get_policy_registry_dependency_health(
        x_ai_internal_key: str | None = Header(default=None),
        policy_version: str | None = Query(default=None),
        include_all_versions: bool = Query(default=False),
        include_overview: bool = Query(default=True),
        include_trend: bool = Query(default=True),
        trend_status: str | None = Query(default=None),
        trend_policy_version: str | None = Query(default=None),
        trend_offset: int = Query(default=0, ge=0, le=5000),
        trend_limit: int = Query(default=50, ge=1, le=500),
        overview_window_minutes: int = Query(default=1440, ge=10, le=43200),
        limit: int = Query(default=20, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        await ensure_registry_runtime_ready()
        dependency_pack = build_registry_governance_dependency_pack()
        return await run_registry_route_guard(
            build_policy_registry_dependency_health_route_payload_from_pack_v3(
                pack=dependency_pack,
                policy_version=policy_version,
                include_all_versions=include_all_versions,
                include_overview=include_overview,
                include_trend=include_trend,
                trend_status=trend_status,
                trend_policy_version=trend_policy_version,
                trend_offset=trend_offset,
                trend_limit=trend_limit,
                overview_window_minutes=overview_window_minutes,
                limit=limit,
            )
        )

    @app.get("/internal/judge/registries/governance/overview")
    async def get_registry_governance_overview(
        x_ai_internal_key: str | None = Header(default=None),
        dependency_limit: int = Query(default=200, ge=1, le=500),
        usage_preview_limit: int = Query(default=20, ge=1, le=200),
        release_limit: int = Query(default=50, ge=1, le=200),
        audit_limit: int = Query(default=100, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        await ensure_registry_runtime_ready()
        dependency_pack = build_registry_governance_dependency_pack()
        return await run_registry_route_guard(
            build_registry_governance_overview_route_payload_from_pack_v3(
                pack=dependency_pack,
                dependency_limit=dependency_limit,
                usage_preview_limit=usage_preview_limit,
                release_limit=release_limit,
                audit_limit=audit_limit,
            )
        )

    @app.get("/internal/judge/registries/prompt-tool/governance")
    async def get_registry_prompt_tool_governance(
        x_ai_internal_key: str | None = Header(default=None),
        dependency_limit: int = Query(default=200, ge=1, le=500),
        usage_preview_limit: int = Query(default=20, ge=1, le=200),
        release_limit: int = Query(default=50, ge=1, le=200),
        audit_limit: int = Query(default=100, ge=1, le=200),
        risk_limit: int = Query(default=50, ge=1, le=500),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        await ensure_registry_runtime_ready()
        dependency_pack = build_registry_governance_dependency_pack()
        return await run_registry_route_guard(
            build_registry_prompt_tool_governance_route_payload_from_pack_v3(
                pack=dependency_pack,
                dependency_limit=dependency_limit,
                usage_preview_limit=usage_preview_limit,
                release_limit=release_limit,
                audit_limit=audit_limit,
                risk_limit=risk_limit,
            )
        )

    @app.get("/internal/judge/registries/policy/domain-families")
    async def list_policy_domain_judge_families(
        x_ai_internal_key: str | None = Header(default=None),
        preview_limit: int = Query(default=20, ge=1, le=200),
        include_versions: bool = Query(default=True),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        await ensure_registry_runtime_ready()
        dependency_pack = build_registry_governance_dependency_pack()
        return await run_registry_route_guard(
            build_policy_domain_judge_families_route_payload_from_pack_v3(
                pack=dependency_pack,
                preview_limit=preview_limit,
                include_versions=include_versions,
            )
        )

    @app.get("/internal/judge/registries/policy/gate-simulation")
    async def simulate_policy_release_gate(
        x_ai_internal_key: str | None = Header(default=None),
        policy_version: str | None = Query(default=None),
        include_all_versions: bool = Query(default=False),
        limit: int = Query(default=20, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        await ensure_registry_runtime_ready()
        dependency_pack = build_registry_governance_dependency_pack()
        return await run_registry_route_guard(
            build_policy_gate_simulation_route_payload_from_pack_v3(
                pack=dependency_pack,
                policy_version=policy_version,
                include_all_versions=include_all_versions,
                limit=limit,
            )
        )

    @app.post("/internal/judge/registries/{registry_type}/publish")
    async def publish_registry_release(
        registry_type: str,
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        payload = await read_json_object_or_raise_422(request=request)
        try:
            parsed = parse_registry_publish_request_payload_v3(
                payload=payload,
                extract_optional_bool=extract_optional_bool_v3,
            )
        except ValueError as err:
            raise_http_422_from_value_error(err=err)
        await ensure_registry_runtime_ready()
        try:
            return await run_registry_route_guard(
                build_registry_publish_payload_v3(
                    registry_type=registry_type,
                    version=parsed["version"],
                    profile_payload=parsed["profilePayload"],
                    activate=bool(parsed["activate"]),
                    override_fairness_gate=bool(parsed["overrideFairnessGate"]),
                    actor=parsed["actor"],
                    reason=parsed["reason"],
                    **registry_release_gate_dependencies,
                    enforce_policy_domain_judge_family_profile_payload=(
                        enforce_policy_domain_judge_family_profile_payload
                    ),
                    publish_release=runtime.registry_product_runtime.publish_release,
                )
            )
        except LookupError as err:
            raise_http_404_from_lookup_error(err=err)
        except ValueError as err:
            raise_registry_value_error(
                err=err,
                default_detail="registry_publish_invalid",
                unprocessable_codes={
                    "invalid_registry_type",
                    "invalid_registry_version",
                    "invalid_policy_profile",
                    "invalid_policy_domain_judge_family",
                    "policy_domain_family_topic_domain_mismatch",
                    "invalid_prompt_profile",
                    "invalid_tool_profile",
                    "registry_fairness_gate_override_reason_required",
                },
                conflict_codes={"registry_version_already_exists"},
            )

    @app.post("/internal/judge/registries/{registry_type}/{version}/activate")
    async def activate_registry_release(
        registry_type: str,
        version: str,
        x_ai_internal_key: str | None = Header(default=None),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
        override_fairness_gate: bool = Query(default=False),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        await ensure_registry_runtime_ready()
        try:
            return await run_registry_route_guard(
                build_registry_activate_payload_v3(
                    registry_type=registry_type,
                    version=version,
                    actor=actor,
                    reason=reason,
                    override_fairness_gate=override_fairness_gate,
                    **registry_release_gate_dependencies,
                    activate_release=runtime.registry_product_runtime.activate_release,
                )
            )
        except LookupError as err:
            raise_registry_version_not_found_lookup_error(err=err)
        except ValueError as err:
            raise_registry_value_error(
                err=err,
                default_detail="registry_activate_invalid",
                unprocessable_codes={
                    "invalid_registry_type",
                    "invalid_registry_version",
                    "registry_fairness_gate_override_reason_required",
                },
            )

    @app.post("/internal/judge/registries/{registry_type}/rollback")
    async def rollback_registry_release(
        registry_type: str,
        x_ai_internal_key: str | None = Header(default=None),
        target_version: str | None = Query(default=None),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        await ensure_registry_runtime_ready()
        try:
            return await build_registry_rollback_payload_v3(
                registry_type=registry_type,
                target_version=target_version,
                actor=actor,
                reason=reason,
                rollback_release=runtime.registry_product_runtime.rollback_release,
            )
        except LookupError as err:
            raise_registry_version_not_found_lookup_error(err=err)
        except ValueError as err:
            raise_registry_value_error(
                err=err,
                default_detail="registry_rollback_invalid",
                unprocessable_codes={
                    "invalid_registry_type",
                    "invalid_registry_version",
                },
                conflict_codes={"registry_rollback_target_not_found"},
            )

    @app.get("/internal/judge/registries/{registry_type}/audits")
    async def list_registry_audits(
        registry_type: str,
        x_ai_internal_key: str | None = Header(default=None),
        action: str | None = Query(default=None),
        version: str | None = Query(default=None),
        actor: str | None = Query(default=None),
        gate_code: str | None = Query(default=None),
        override_applied: bool | None = Query(default=None),
        include_gate_view: bool = Query(default=True),
        link_limit: int = Query(default=5, ge=1, le=20),
        offset: int = Query(default=0, ge=0, le=5000),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        await ensure_registry_runtime_ready()
        return await build_registry_audits_payload(
            runtime=runtime,
            list_audit_alerts=list_audit_alerts,
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
        )

    @app.get("/internal/judge/registries/{registry_type}/releases")
    async def list_registry_releases(
        registry_type: str,
        x_ai_internal_key: str | None = Header(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        include_payload: bool = Query(default=True),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        await ensure_registry_runtime_ready()
        return await build_registry_releases_payload(
            runtime=runtime,
            registry_type=registry_type,
            limit=limit,
            include_payload=include_payload,
        )

    @app.get("/internal/judge/registries/{registry_type}/releases/{version}")
    async def get_registry_release(
        registry_type: str,
        version: str,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key_fn(runtime.settings, x_ai_internal_key)
        await ensure_registry_runtime_ready()
        return await build_registry_release_payload(
            runtime=runtime,
            registry_type=registry_type,
            version=version,
            not_found_detail="registry_version_not_found",
        )

    return RegistryRouteHandles(
        get_policy_registry_dependency_health=get_policy_registry_dependency_health,
        get_registry_governance_overview=get_registry_governance_overview,
        get_registry_prompt_tool_governance=get_registry_prompt_tool_governance,
        simulate_policy_release_gate=simulate_policy_release_gate,
    )
