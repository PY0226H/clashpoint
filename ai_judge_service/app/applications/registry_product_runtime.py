from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infra.db.models import JudgeRegistryAuditModel, JudgeRegistryReleaseModel

from .policy_registry import (
    JudgePolicyProfile,
    PolicyRegistryRuntime,
    PolicyValidationResult,
    build_policy_registry_runtime,
)
from .registry_runtime import (
    PromptRegistryRuntime,
    PromptSetProfile,
    ToolRegistryRuntime,
    ToolsetProfile,
    build_prompt_registry_runtime,
    build_tool_registry_runtime,
)

REGISTRY_TYPE_POLICY = "policy"
REGISTRY_TYPE_PROMPT = "prompt"
REGISTRY_TYPE_TOOL = "tool"
REGISTRY_TYPE_VALUES = {
    REGISTRY_TYPE_POLICY,
    REGISTRY_TYPE_PROMPT,
    REGISTRY_TYPE_TOOL,
}
REGISTRY_STATUS_PUBLISHED = "published"
REGISTRY_ACTION_BOOTSTRAP = "bootstrap"
REGISTRY_ACTION_PUBLISH = "publish"
REGISTRY_ACTION_ACTIVATE = "activate"
REGISTRY_ACTION_ROLLBACK = "rollback"
REGISTRY_ACTOR_SYSTEM = "system"
REGISTRY_ACTOR_BOOTSTRAP = "system_bootstrap"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_registry_type(value: str) -> str:
    token = str(value or "").strip().lower()
    if token not in REGISTRY_TYPE_VALUES:
        raise ValueError("invalid_registry_type")
    return token


def _normalize_version(value: str) -> str:
    token = str(value or "").strip()
    if not token:
        raise ValueError("invalid_registry_version")
    return token


def _build_builtin_policy_runtime(*, settings: Any) -> PolicyRegistryRuntime:
    return build_policy_registry_runtime(
        settings=SimpleNamespace(
            policy_registry_default_version=str(
                getattr(settings, "policy_registry_default_version", "v3-default")
            ).strip()
            or "v3-default",
            policy_registry_json="",
        )
    )


def _build_builtin_prompt_runtime(*, settings: Any) -> PromptRegistryRuntime:
    return build_prompt_registry_runtime(
        settings=SimpleNamespace(
            prompt_registry_default_version=str(
                getattr(settings, "prompt_registry_default_version", "promptset-v3-default")
            ).strip()
            or "promptset-v3-default",
            prompt_registry_json="",
        )
    )


def _build_builtin_tool_runtime(*, settings: Any) -> ToolRegistryRuntime:
    return build_tool_registry_runtime(
        settings=SimpleNamespace(
            tool_registry_default_version=str(
                getattr(settings, "tool_registry_default_version", "toolset-v3-default")
            ).strip()
            or "toolset-v3-default",
            tool_registry_json="",
        )
    )


@dataclass
class MutablePolicyRegistryRuntime:
    _runtime: PolicyRegistryRuntime

    def replace(self, runtime: PolicyRegistryRuntime) -> None:
        self._runtime = runtime

    @property
    def default_version(self) -> str:
        return self._runtime.default_version

    def list_profiles(self) -> list[JudgePolicyProfile]:
        return self._runtime.list_profiles()

    def get_profile(self, version: str) -> JudgePolicyProfile | None:
        return self._runtime.get_profile(version)

    def resolve(self, *, requested_version: str, rubric_version: str, topic_domain: str) -> PolicyValidationResult:
        return self._runtime.resolve(
            requested_version=requested_version,
            rubric_version=rubric_version,
            topic_domain=topic_domain,
        )

    @staticmethod
    def serialize_profile(profile: JudgePolicyProfile) -> dict[str, Any]:
        return PolicyRegistryRuntime.serialize_profile(profile)

    @staticmethod
    def build_trace_snapshot(profile: JudgePolicyProfile) -> dict[str, Any]:
        return PolicyRegistryRuntime.build_trace_snapshot(profile)


@dataclass
class MutablePromptRegistryRuntime:
    _runtime: PromptRegistryRuntime

    def replace(self, runtime: PromptRegistryRuntime) -> None:
        self._runtime = runtime

    @property
    def default_version(self) -> str:
        return self._runtime.default_version

    def list_profiles(self) -> list[PromptSetProfile]:
        return self._runtime.list_profiles()

    def get_profile(self, version: str) -> PromptSetProfile | None:
        return self._runtime.get_profile(version)

    @staticmethod
    def serialize_profile(profile: PromptSetProfile) -> dict[str, Any]:
        return PromptRegistryRuntime.serialize_profile(profile)

    @staticmethod
    def build_trace_snapshot(profile: PromptSetProfile) -> dict[str, Any]:
        return PromptRegistryRuntime.build_trace_snapshot(profile)


@dataclass
class MutableToolRegistryRuntime:
    _runtime: ToolRegistryRuntime

    def replace(self, runtime: ToolRegistryRuntime) -> None:
        self._runtime = runtime

    @property
    def default_version(self) -> str:
        return self._runtime.default_version

    def list_profiles(self) -> list[ToolsetProfile]:
        return self._runtime.list_profiles()

    def get_profile(self, version: str) -> ToolsetProfile | None:
        return self._runtime.get_profile(version)

    @staticmethod
    def serialize_profile(profile: ToolsetProfile) -> dict[str, Any]:
        return ToolRegistryRuntime.serialize_profile(profile)

    @staticmethod
    def build_trace_snapshot(profile: ToolsetProfile) -> dict[str, Any]:
        return ToolRegistryRuntime.build_trace_snapshot(profile)


@dataclass
class RegistryProductRuntime:
    session_factory: async_sessionmaker[AsyncSession]
    settings: Any
    policy_runtime: MutablePolicyRegistryRuntime = field(init=False)
    prompt_runtime: MutablePromptRegistryRuntime = field(init=False)
    tool_runtime: MutableToolRegistryRuntime = field(init=False)
    _loaded: bool = field(default=False, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self) -> None:
        self.policy_runtime = MutablePolicyRegistryRuntime(
            _runtime=_build_builtin_policy_runtime(settings=self.settings)
        )
        self.prompt_runtime = MutablePromptRegistryRuntime(
            _runtime=_build_builtin_prompt_runtime(settings=self.settings)
        )
        self.tool_runtime = MutableToolRegistryRuntime(
            _runtime=_build_builtin_tool_runtime(settings=self.settings)
        )

    async def ensure_loaded(self, *, force: bool = False) -> None:
        if self._loaded and not force:
            return
        async with self._lock:
            if self._loaded and not force:
                return
            async with self.session_factory() as session:
                async with session.begin():
                    await self._seed_builtins_if_needed(session=session)
                rows = await self._list_release_rows(session=session)
            self._hydrate_from_rows(rows)
            self._loaded = True

    async def publish_release(
        self,
        *,
        registry_type: str,
        version: str,
        profile_payload: dict[str, Any],
        actor: str | None,
        reason: str | None,
        activate: bool,
    ) -> dict[str, Any]:
        normalized_registry_type = _normalize_registry_type(registry_type)
        normalized_version = _normalize_version(version)
        normalized_actor = str(actor or "").strip() or REGISTRY_ACTOR_SYSTEM
        normalized_reason = str(reason or "").strip() or None
        normalized_payload = self._normalize_profile_payload(
            registry_type=normalized_registry_type,
            version=normalized_version,
            payload=profile_payload,
        )
        now = _utcnow()
        await self.ensure_loaded()
        async with self.session_factory() as session:
            async with session.begin():
                existing = await session.execute(
                    select(JudgeRegistryReleaseModel).where(
                        JudgeRegistryReleaseModel.registry_type == normalized_registry_type,
                        JudgeRegistryReleaseModel.version == normalized_version,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    raise ValueError("registry_version_already_exists")

                previous_active_version = await self._get_active_version(
                    session=session,
                    registry_type=normalized_registry_type,
                )
                if activate:
                    await session.execute(
                        update(JudgeRegistryReleaseModel)
                        .where(JudgeRegistryReleaseModel.registry_type == normalized_registry_type)
                        .values(is_active=False, updated_at=now)
                    )

                release = JudgeRegistryReleaseModel(
                    registry_type=normalized_registry_type,
                    version=normalized_version,
                    payload=normalized_payload,
                    is_active=bool(activate),
                    status=REGISTRY_STATUS_PUBLISHED,
                    created_by=normalized_actor,
                    created_at=now,
                    updated_at=now,
                    activated_by=normalized_actor if activate else None,
                    activated_at=now if activate else None,
                )
                session.add(release)
                session.add(
                    JudgeRegistryAuditModel(
                        registry_type=normalized_registry_type,
                        action=REGISTRY_ACTION_PUBLISH,
                        version=normalized_version,
                        actor=normalized_actor,
                        reason=normalized_reason,
                        details={
                            "activate": bool(activate),
                        },
                        created_at=now,
                    )
                )
                if activate:
                    session.add(
                        JudgeRegistryAuditModel(
                            registry_type=normalized_registry_type,
                            action=REGISTRY_ACTION_ACTIVATE,
                            version=normalized_version,
                            actor=normalized_actor,
                            reason=normalized_reason or "publish_and_activate",
                            details={
                                "fromVersion": previous_active_version,
                                "toVersion": normalized_version,
                                "source": "publish",
                            },
                            created_at=now,
                        )
                    )
                await session.flush()
                serialized = self._serialize_release_row(release)
        await self.ensure_loaded(force=True)
        return serialized

    async def activate_release(
        self,
        *,
        registry_type: str,
        version: str,
        actor: str | None,
        reason: str | None,
    ) -> dict[str, Any]:
        normalized_registry_type = _normalize_registry_type(registry_type)
        normalized_version = _normalize_version(version)
        normalized_actor = str(actor or "").strip() or REGISTRY_ACTOR_SYSTEM
        normalized_reason = str(reason or "").strip() or None
        now = _utcnow()
        await self.ensure_loaded()
        async with self.session_factory() as session:
            async with session.begin():
                current_active_version = await self._get_active_version(
                    session=session,
                    registry_type=normalized_registry_type,
                )
                target_stmt: Select[tuple[JudgeRegistryReleaseModel]] = select(
                    JudgeRegistryReleaseModel
                ).where(
                    JudgeRegistryReleaseModel.registry_type == normalized_registry_type,
                    JudgeRegistryReleaseModel.version == normalized_version,
                )
                target = (await session.execute(target_stmt)).scalar_one_or_none()
                if target is None:
                    raise LookupError("registry_version_not_found")

                await session.execute(
                    update(JudgeRegistryReleaseModel)
                    .where(JudgeRegistryReleaseModel.registry_type == normalized_registry_type)
                    .values(is_active=False, updated_at=now)
                )
                target.is_active = True
                target.updated_at = now
                target.activated_by = normalized_actor
                target.activated_at = now
                session.add(
                    JudgeRegistryAuditModel(
                        registry_type=normalized_registry_type,
                        action=REGISTRY_ACTION_ACTIVATE,
                        version=normalized_version,
                        actor=normalized_actor,
                        reason=normalized_reason,
                        details={
                            "fromVersion": current_active_version,
                            "toVersion": normalized_version,
                            "source": "activate",
                        },
                        created_at=now,
                    )
                )
                await session.flush()
                serialized = self._serialize_release_row(target)
        await self.ensure_loaded(force=True)
        return serialized

    async def rollback_release(
        self,
        *,
        registry_type: str,
        actor: str | None,
        reason: str | None,
        target_version: str | None = None,
    ) -> dict[str, Any]:
        normalized_registry_type = _normalize_registry_type(registry_type)
        normalized_target_version = (
            _normalize_version(target_version) if target_version is not None else None
        )
        normalized_actor = str(actor or "").strip() or REGISTRY_ACTOR_SYSTEM
        normalized_reason = str(reason or "").strip() or None
        now = _utcnow()
        await self.ensure_loaded()
        async with self.session_factory() as session:
            async with session.begin():
                active_stmt: Select[tuple[JudgeRegistryReleaseModel]] = select(
                    JudgeRegistryReleaseModel
                ).where(
                    JudgeRegistryReleaseModel.registry_type == normalized_registry_type,
                    JudgeRegistryReleaseModel.is_active.is_(True),
                )
                active_row = (await session.execute(active_stmt)).scalar_one_or_none()
                from_version = active_row.version if active_row is not None else None

                if normalized_target_version is not None:
                    target_stmt: Select[tuple[JudgeRegistryReleaseModel]] = select(
                        JudgeRegistryReleaseModel
                    ).where(
                        JudgeRegistryReleaseModel.registry_type == normalized_registry_type,
                        JudgeRegistryReleaseModel.version == normalized_target_version,
                    )
                else:
                    target_stmt = (
                        select(JudgeRegistryReleaseModel)
                        .where(JudgeRegistryReleaseModel.registry_type == normalized_registry_type)
                        .where(
                            JudgeRegistryReleaseModel.version
                            != (from_version or "__none__")
                        )
                        .order_by(
                            JudgeRegistryReleaseModel.activated_at.desc().nullslast(),
                            JudgeRegistryReleaseModel.updated_at.desc(),
                            JudgeRegistryReleaseModel.created_at.desc(),
                            JudgeRegistryReleaseModel.id.desc(),
                        )
                    )
                target = (await session.execute(target_stmt)).scalars().first()
                if target is None:
                    raise ValueError("registry_rollback_target_not_found")

                await session.execute(
                    update(JudgeRegistryReleaseModel)
                    .where(JudgeRegistryReleaseModel.registry_type == normalized_registry_type)
                    .values(is_active=False, updated_at=now)
                )
                target.is_active = True
                target.updated_at = now
                target.activated_by = normalized_actor
                target.activated_at = now
                session.add(
                    JudgeRegistryAuditModel(
                        registry_type=normalized_registry_type,
                        action=REGISTRY_ACTION_ROLLBACK,
                        version=target.version,
                        actor=normalized_actor,
                        reason=normalized_reason,
                        details={
                            "fromVersion": from_version,
                            "toVersion": target.version,
                        },
                        created_at=now,
                    )
                )
                await session.flush()
                serialized = self._serialize_release_row(target)
        await self.ensure_loaded(force=True)
        return serialized

    async def list_audits(
        self,
        *,
        registry_type: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        normalized_registry_type = _normalize_registry_type(registry_type)
        cap = max(1, min(int(limit), 200))
        await self.ensure_loaded()
        async with self.session_factory() as session:
            stmt: Select[tuple[JudgeRegistryAuditModel]] = (
                select(JudgeRegistryAuditModel)
                .where(JudgeRegistryAuditModel.registry_type == normalized_registry_type)
                .order_by(JudgeRegistryAuditModel.created_at.desc(), JudgeRegistryAuditModel.id.desc())
                .limit(cap)
            )
            rows = (await session.execute(stmt)).scalars().all()
        return [self._serialize_audit_row(row) for row in rows]

    async def _seed_builtins_if_needed(self, *, session: AsyncSession) -> None:
        now = _utcnow()
        for registry_type in (
            REGISTRY_TYPE_POLICY,
            REGISTRY_TYPE_PROMPT,
            REGISTRY_TYPE_TOOL,
        ):
            count_stmt: Select[tuple[int]] = select(func.count()).where(
                JudgeRegistryReleaseModel.registry_type == registry_type
            )
            existing_count = int((await session.execute(count_stmt)).scalar_one() or 0)
            if existing_count > 0:
                continue

            if registry_type == REGISTRY_TYPE_POLICY:
                runtime = _build_builtin_policy_runtime(settings=self.settings)
                profiles = [PolicyRegistryRuntime.serialize_profile(item) for item in runtime.list_profiles()]
                default_version = runtime.default_version
            elif registry_type == REGISTRY_TYPE_PROMPT:
                runtime = _build_builtin_prompt_runtime(settings=self.settings)
                profiles = [PromptRegistryRuntime.serialize_profile(item) for item in runtime.list_profiles()]
                default_version = runtime.default_version
            else:
                runtime = _build_builtin_tool_runtime(settings=self.settings)
                profiles = [ToolRegistryRuntime.serialize_profile(item) for item in runtime.list_profiles()]
                default_version = runtime.default_version

            for item in profiles:
                version = str(item.get("version") or "").strip()
                if not version:
                    continue
                payload = dict(item)
                payload["version"] = version
                row = JudgeRegistryReleaseModel(
                    registry_type=registry_type,
                    version=version,
                    payload=payload,
                    is_active=(version == default_version),
                    status=REGISTRY_STATUS_PUBLISHED,
                    created_by=REGISTRY_ACTOR_BOOTSTRAP,
                    created_at=now,
                    updated_at=now,
                    activated_by=REGISTRY_ACTOR_BOOTSTRAP if version == default_version else None,
                    activated_at=now if version == default_version else None,
                )
                session.add(row)
            session.add(
                JudgeRegistryAuditModel(
                    registry_type=registry_type,
                    action=REGISTRY_ACTION_BOOTSTRAP,
                    version=default_version,
                    actor=REGISTRY_ACTOR_BOOTSTRAP,
                    reason="bootstrap_builtin_registry",
                    details={"profileCount": len(profiles)},
                    created_at=now,
                )
            )

    async def _list_release_rows(self, *, session: AsyncSession) -> list[JudgeRegistryReleaseModel]:
        stmt: Select[tuple[JudgeRegistryReleaseModel]] = (
            select(JudgeRegistryReleaseModel)
            .where(JudgeRegistryReleaseModel.status == REGISTRY_STATUS_PUBLISHED)
            .order_by(
                JudgeRegistryReleaseModel.registry_type.asc(),
                JudgeRegistryReleaseModel.created_at.asc(),
                JudgeRegistryReleaseModel.id.asc(),
            )
        )
        return list((await session.execute(stmt)).scalars().all())

    def _hydrate_from_rows(self, rows: list[JudgeRegistryReleaseModel]) -> None:
        grouped: dict[str, list[JudgeRegistryReleaseModel]] = {
            REGISTRY_TYPE_POLICY: [],
            REGISTRY_TYPE_PROMPT: [],
            REGISTRY_TYPE_TOOL: [],
        }
        for row in rows:
            token = str(row.registry_type or "").strip().lower()
            if token in grouped:
                grouped[token].append(row)

        self.policy_runtime.replace(
            self._build_policy_runtime_from_rows(grouped[REGISTRY_TYPE_POLICY])
        )
        self.prompt_runtime.replace(
            self._build_prompt_runtime_from_rows(grouped[REGISTRY_TYPE_PROMPT])
        )
        self.tool_runtime.replace(
            self._build_tool_runtime_from_rows(grouped[REGISTRY_TYPE_TOOL])
        )

    def _build_policy_runtime_from_rows(
        self, rows: list[JudgeRegistryReleaseModel]
    ) -> PolicyRegistryRuntime:
        if not rows:
            return _build_builtin_policy_runtime(settings=self.settings)
        default_version = self._resolve_default_version(rows=rows)
        profiles: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row.payload) if isinstance(row.payload, dict) else {}
            payload["version"] = row.version
            metadata = dict(payload.get("metadata")) if isinstance(payload.get("metadata"), dict) else {}
            metadata.setdefault("status", row.status)
            metadata["releaseSource"] = "db"
            metadata["publishedBy"] = row.created_by
            metadata["publishedAt"] = row.created_at.isoformat()
            if row.activated_at is not None:
                metadata["activatedAt"] = row.activated_at.isoformat()
                metadata["activatedBy"] = row.activated_by
            payload["metadata"] = metadata
            profiles.append(payload)
        json_text = json.dumps(
            {
                "defaultVersion": default_version,
                "profiles": profiles,
            },
            ensure_ascii=False,
        )
        return build_policy_registry_runtime(
            settings=SimpleNamespace(
                policy_registry_default_version=default_version,
                policy_registry_json=json_text,
            )
        )

    def _build_prompt_runtime_from_rows(
        self, rows: list[JudgeRegistryReleaseModel]
    ) -> PromptRegistryRuntime:
        if not rows:
            return _build_builtin_prompt_runtime(settings=self.settings)
        default_version = self._resolve_default_version(rows=rows)
        profiles: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row.payload) if isinstance(row.payload, dict) else {}
            payload["version"] = row.version
            metadata = dict(payload.get("metadata")) if isinstance(payload.get("metadata"), dict) else {}
            metadata.setdefault("status", row.status)
            metadata["releaseSource"] = "db"
            metadata["publishedBy"] = row.created_by
            metadata["publishedAt"] = row.created_at.isoformat()
            payload["metadata"] = metadata
            profiles.append(payload)
        json_text = json.dumps(
            {
                "defaultVersion": default_version,
                "profiles": profiles,
            },
            ensure_ascii=False,
        )
        return build_prompt_registry_runtime(
            settings=SimpleNamespace(
                prompt_registry_default_version=default_version,
                prompt_registry_json=json_text,
            )
        )

    def _build_tool_runtime_from_rows(
        self, rows: list[JudgeRegistryReleaseModel]
    ) -> ToolRegistryRuntime:
        if not rows:
            return _build_builtin_tool_runtime(settings=self.settings)
        default_version = self._resolve_default_version(rows=rows)
        profiles: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row.payload) if isinstance(row.payload, dict) else {}
            payload["version"] = row.version
            metadata = dict(payload.get("metadata")) if isinstance(payload.get("metadata"), dict) else {}
            metadata.setdefault("status", row.status)
            metadata["releaseSource"] = "db"
            metadata["publishedBy"] = row.created_by
            metadata["publishedAt"] = row.created_at.isoformat()
            payload["metadata"] = metadata
            profiles.append(payload)
        json_text = json.dumps(
            {
                "defaultVersion": default_version,
                "profiles": profiles,
            },
            ensure_ascii=False,
        )
        return build_tool_registry_runtime(
            settings=SimpleNamespace(
                tool_registry_default_version=default_version,
                tool_registry_json=json_text,
            )
        )

    @staticmethod
    def _resolve_default_version(*, rows: list[JudgeRegistryReleaseModel]) -> str:
        for row in rows:
            if row.is_active:
                return str(row.version)
        latest = rows[-1]
        return str(latest.version)

    @staticmethod
    async def _get_active_version(
        *,
        session: AsyncSession,
        registry_type: str,
    ) -> str | None:
        stmt: Select[tuple[JudgeRegistryReleaseModel]] = select(JudgeRegistryReleaseModel).where(
            JudgeRegistryReleaseModel.registry_type == registry_type,
            JudgeRegistryReleaseModel.is_active.is_(True),
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return str(row.version)

    def _normalize_profile_payload(
        self,
        *,
        registry_type: str,
        version: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        source = dict(payload) if isinstance(payload, dict) else {}
        source["version"] = version
        if registry_type == REGISTRY_TYPE_POLICY:
            runtime = build_policy_registry_runtime(
                settings=SimpleNamespace(
                    policy_registry_default_version=version,
                    policy_registry_json=json.dumps(
                        {"defaultVersion": version, "profiles": [source]},
                        ensure_ascii=False,
                    ),
                )
            )
            profile = runtime.get_profile(version)
            if profile is None:
                raise ValueError("invalid_policy_profile")
            serialized = PolicyRegistryRuntime.serialize_profile(profile)
        elif registry_type == REGISTRY_TYPE_PROMPT:
            runtime = build_prompt_registry_runtime(
                settings=SimpleNamespace(
                    prompt_registry_default_version=version,
                    prompt_registry_json=json.dumps(
                        {"defaultVersion": version, "profiles": [source]},
                        ensure_ascii=False,
                    ),
                )
            )
            profile = runtime.get_profile(version)
            if profile is None:
                raise ValueError("invalid_prompt_profile")
            serialized = PromptRegistryRuntime.serialize_profile(profile)
        else:
            runtime = build_tool_registry_runtime(
                settings=SimpleNamespace(
                    tool_registry_default_version=version,
                    tool_registry_json=json.dumps(
                        {"defaultVersion": version, "profiles": [source]},
                        ensure_ascii=False,
                    ),
                )
            )
            profile = runtime.get_profile(version)
            if profile is None:
                raise ValueError("invalid_tool_profile")
            serialized = ToolRegistryRuntime.serialize_profile(profile)
        serialized["version"] = version
        return serialized

    @staticmethod
    def _serialize_release_row(row: JudgeRegistryReleaseModel) -> dict[str, Any]:
        return {
            "registryType": row.registry_type,
            "version": row.version,
            "isActive": bool(row.is_active),
            "status": row.status,
            "payload": dict(row.payload) if isinstance(row.payload, dict) else {},
            "createdBy": row.created_by,
            "createdAt": row.created_at.isoformat() if row.created_at is not None else None,
            "updatedAt": row.updated_at.isoformat() if row.updated_at is not None else None,
            "activatedBy": row.activated_by,
            "activatedAt": row.activated_at.isoformat() if row.activated_at is not None else None,
        }

    @staticmethod
    def _serialize_audit_row(row: JudgeRegistryAuditModel) -> dict[str, Any]:
        return {
            "registryType": row.registry_type,
            "action": row.action,
            "version": row.version,
            "actor": row.actor,
            "reason": row.reason,
            "details": dict(row.details) if isinstance(row.details, dict) else {},
            "createdAt": row.created_at.isoformat() if row.created_at is not None else None,
        }


def build_registry_product_runtime(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Any,
) -> RegistryProductRuntime:
    return RegistryProductRuntime(
        session_factory=session_factory,
        settings=settings,
    )
