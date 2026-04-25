from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.trust import (
    TRUST_REGISTRY_VERSION,
    TrustChallengeEvent,
    TrustRegistrySnapshot,
    normalize_trust_dispatch_type,
    validate_trust_registry_snapshot,
)
from app.infra.db.models import JudgeTrustRegistrySnapshotModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_version(value: str | None) -> str:
    return str(value or "").strip() or TRUST_REGISTRY_VERSION


class TrustRegistryRepository:
    def __init__(self, *, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def upsert_trust_registry_snapshot(
        self,
        *,
        snapshot: TrustRegistrySnapshot,
    ) -> TrustRegistrySnapshot:
        validation_errors = validate_trust_registry_snapshot(snapshot)
        if validation_errors:
            raise ValueError(f"invalid_trust_registry_snapshot:{','.join(validation_errors)}")
        normalized = snapshot.normalized()

        now = _utcnow()
        stmt: Select[tuple[JudgeTrustRegistrySnapshotModel]] = select(
            JudgeTrustRegistrySnapshotModel
        ).where(
            and_(
                JudgeTrustRegistrySnapshotModel.case_id == int(normalized.case_id),
                JudgeTrustRegistrySnapshotModel.dispatch_type == normalized.dispatch_type,
                JudgeTrustRegistrySnapshotModel.trace_id == normalized.trace_id,
                JudgeTrustRegistrySnapshotModel.registry_version
                == normalized.registry_version,
            )
        )
        async with self._session_factory() as session:
            async with session.begin():
                row = (await session.execute(stmt)).scalars().first()
                if row is None:
                    row = JudgeTrustRegistrySnapshotModel(
                        case_id=int(normalized.case_id),
                        dispatch_type=normalized.dispatch_type,
                        trace_id=normalized.trace_id,
                        registry_version=normalized.registry_version,
                        created_at=normalized.created_at or now,
                    )
                    session.add(row)
                row.case_commitment = dict(normalized.case_commitment)
                row.verdict_attestation = dict(normalized.verdict_attestation)
                row.challenge_review = dict(normalized.challenge_review)
                row.kernel_version = dict(normalized.kernel_version)
                row.audit_anchor = dict(normalized.audit_anchor)
                row.public_verify = dict(normalized.public_verify)
                row.component_hashes = dict(normalized.component_hashes)
                row.updated_at = normalized.updated_at or now
            await session.refresh(row)
            return self._to_snapshot(row)

    async def get_trust_registry_snapshot(
        self,
        *,
        case_id: int,
        dispatch_type: str | None = None,
        trace_id: str | None = None,
        registry_version: str | None = None,
    ) -> TrustRegistrySnapshot | None:
        stmt: Select[tuple[JudgeTrustRegistrySnapshotModel]] = select(
            JudgeTrustRegistrySnapshotModel
        ).where(JudgeTrustRegistrySnapshotModel.case_id == int(case_id))
        if dispatch_type is not None:
            stmt = stmt.where(
                JudgeTrustRegistrySnapshotModel.dispatch_type
                == normalize_trust_dispatch_type(dispatch_type)
            )
        if trace_id is not None:
            stmt = stmt.where(
                JudgeTrustRegistrySnapshotModel.trace_id == str(trace_id or "").strip()
            )
        if registry_version is not None:
            stmt = stmt.where(
                JudgeTrustRegistrySnapshotModel.registry_version
                == _normalize_version(registry_version)
            )
        stmt = stmt.order_by(
            JudgeTrustRegistrySnapshotModel.updated_at.desc(),
            JudgeTrustRegistrySnapshotModel.id.desc(),
        )
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
            if row is None:
                return None
            return self._to_snapshot(row)

    async def list_trust_registry_snapshots(
        self,
        *,
        case_id: int,
        dispatch_type: str | None = None,
        limit: int = 20,
    ) -> list[TrustRegistrySnapshot]:
        stmt: Select[tuple[JudgeTrustRegistrySnapshotModel]] = (
            select(JudgeTrustRegistrySnapshotModel)
            .where(JudgeTrustRegistrySnapshotModel.case_id == int(case_id))
            .order_by(
                JudgeTrustRegistrySnapshotModel.updated_at.desc(),
                JudgeTrustRegistrySnapshotModel.id.desc(),
            )
            .limit(max(1, min(200, int(limit))))
        )
        if dispatch_type is not None:
            stmt = stmt.where(
                JudgeTrustRegistrySnapshotModel.dispatch_type
                == normalize_trust_dispatch_type(dispatch_type)
            )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
            return [self._to_snapshot(row) for row in rows]

    async def append_challenge_event(
        self,
        *,
        case_id: int,
        dispatch_type: str,
        trace_id: str,
        registry_version: str | None,
        event: TrustChallengeEvent,
    ) -> TrustRegistrySnapshot | None:
        normalized_dispatch_type = normalize_trust_dispatch_type(dispatch_type)
        normalized_trace_id = str(trace_id or "").strip()
        normalized_version = _normalize_version(registry_version)
        stmt: Select[tuple[JudgeTrustRegistrySnapshotModel]] = select(
            JudgeTrustRegistrySnapshotModel
        ).where(
            and_(
                JudgeTrustRegistrySnapshotModel.case_id == int(case_id),
                JudgeTrustRegistrySnapshotModel.dispatch_type == normalized_dispatch_type,
                JudgeTrustRegistrySnapshotModel.trace_id == normalized_trace_id,
                JudgeTrustRegistrySnapshotModel.registry_version == normalized_version,
            )
        )
        async with self._session_factory() as session:
            async with session.begin():
                row = (await session.execute(stmt)).scalars().first()
                if row is None:
                    return None
                challenge_review = (
                    dict(row.challenge_review)
                    if isinstance(row.challenge_review, dict)
                    else {}
                )
                registry_events = (
                    list(challenge_review.get("registryEvents"))
                    if isinstance(challenge_review.get("registryEvents"), list)
                    else []
                )
                registry_events.append(event.to_payload())
                challenge_review["registryEvents"] = registry_events
                challenge_review["latestRegistryEvent"] = event.to_payload()
                row.challenge_review = challenge_review
                row.updated_at = _utcnow()
            await session.refresh(row)
            return self._to_snapshot(row)

    def _to_snapshot(self, row: JudgeTrustRegistrySnapshotModel) -> TrustRegistrySnapshot:
        return TrustRegistrySnapshot(
            case_id=int(row.case_id),
            dispatch_type=row.dispatch_type,
            trace_id=row.trace_id,
            registry_version=row.registry_version,
            case_commitment=_dict(row.case_commitment),
            verdict_attestation=_dict(row.verdict_attestation),
            challenge_review=_dict(row.challenge_review),
            kernel_version=_dict(row.kernel_version),
            audit_anchor=_dict(row.audit_anchor),
            public_verify=_dict(row.public_verify),
            component_hashes=_dict(row.component_hashes),
            created_at=row.created_at,
            updated_at=row.updated_at,
        ).normalized()


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
