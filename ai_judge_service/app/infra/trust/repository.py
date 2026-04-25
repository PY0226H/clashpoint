from __future__ import annotations

import hashlib
import json
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


_TRUST_CHALLENGE_OPEN_STATES = {
    "challenge_requested",
    "challenge_accepted",
    "under_internal_review",
}
_TRUST_CHALLENGE_DECISION_STATES = {
    "verdict_upheld",
    "verdict_overturned",
    "draw_after_review",
    "review_retained",
}


def _sha256_hex(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _event_seq(challenge_review: dict[str, Any]) -> int:
    registry_events = challenge_review.get("registryEvents")
    if isinstance(registry_events, list):
        return len(registry_events)
    timeline = challenge_review.get("timeline")
    if isinstance(timeline, list):
        return len(timeline) + 1
    return 1


def _append_challenge_timeline_event(
    *,
    challenge_review: dict[str, Any],
    event: TrustChallengeEvent,
) -> dict[str, Any]:
    payload = event.to_payload()
    challenge_id = str(payload.get("challengeId") or "").strip()
    state = str(payload.get("state") or "").strip().lower()
    actor = str(payload.get("actor") or "").strip() or None
    reason_code = str(payload.get("reasonCode") or "").strip() or None
    reason = str(payload.get("reason") or "").strip() or None
    created_at = str(payload.get("createdAt") or "").strip() or None
    event_seq = _event_seq(challenge_review)

    timeline = (
        list(challenge_review.get("timeline"))
        if isinstance(challenge_review.get("timeline"), list)
        else []
    )
    timeline.append(
        {
            "eventSeq": event_seq,
            "challengeId": challenge_id,
            "state": state,
            "actor": actor,
            "reasonCode": reason_code,
            "reason": reason,
            "createdAt": created_at,
        }
    )

    challenges = (
        list(challenge_review.get("challenges"))
        if isinstance(challenge_review.get("challenges"), list)
        else []
    )
    challenge_entry = next(
        (
            row
            for row in challenges
            if isinstance(row, dict)
            and str(row.get("challengeId") or "").strip() == challenge_id
        ),
        None,
    )
    if challenge_entry is None:
        challenge_entry = {
            "challengeId": challenge_id,
            "currentState": state,
            "reasonCode": reason_code,
            "reason": reason,
            "requestedBy": None,
            "requestedAt": None,
            "acceptedBy": None,
            "acceptedAt": None,
            "reviewStartedAt": None,
            "decision": None,
            "decisionBy": None,
            "decisionReason": None,
            "decisionAt": None,
            "closedBy": None,
            "closedAt": None,
            "latestEventSeq": event_seq,
            "stateHistory": [],
        }
        challenges.append(challenge_entry)

    challenge_entry["currentState"] = state
    challenge_entry["latestEventSeq"] = event_seq
    if reason_code and not challenge_entry.get("reasonCode"):
        challenge_entry["reasonCode"] = reason_code
    if reason and not challenge_entry.get("reason"):
        challenge_entry["reason"] = reason
    state_history = (
        list(challenge_entry.get("stateHistory"))
        if isinstance(challenge_entry.get("stateHistory"), list)
        else []
    )
    state_history.append(timeline[-1])
    challenge_entry["stateHistory"] = state_history

    if state == "challenge_requested":
        challenge_entry["requestedBy"] = challenge_entry.get("requestedBy") or actor
        challenge_entry["requestedAt"] = challenge_entry.get("requestedAt") or created_at
    elif state == "challenge_accepted":
        challenge_entry["acceptedBy"] = challenge_entry.get("acceptedBy") or actor
        challenge_entry["acceptedAt"] = challenge_entry.get("acceptedAt") or created_at
    elif state == "under_internal_review":
        challenge_entry["reviewStartedAt"] = (
            challenge_entry.get("reviewStartedAt") or created_at
        )
    elif state in _TRUST_CHALLENGE_DECISION_STATES:
        challenge_entry["decision"] = state
        challenge_entry["decisionBy"] = actor
        challenge_entry["decisionReason"] = reason
        challenge_entry["decisionAt"] = created_at
    elif state == "challenge_closed":
        challenge_entry["closedBy"] = actor
        challenge_entry["closedAt"] = created_at

    challenge_reasons = (
        list(challenge_review.get("challengeReasons"))
        if isinstance(challenge_review.get("challengeReasons"), list)
        else []
    )
    if reason_code and reason_code not in challenge_reasons:
        challenge_reasons.append(reason_code)

    review_decisions = (
        list(challenge_review.get("reviewDecisions"))
        if isinstance(challenge_review.get("reviewDecisions"), list)
        else []
    )
    review_decision = None
    if state == "verdict_upheld":
        review_decision = "approve"
    elif state in {"verdict_overturned", "draw_after_review"}:
        review_decision = "reject"
    elif state == "review_retained":
        review_decision = "retain"
    if review_decision is not None:
        review_decisions.append(
            {
                "eventSeq": event_seq,
                "decision": review_decision,
                "actor": actor,
                "reason": reason,
                "createdAt": created_at,
            }
        )

    active_challenge_id = challenge_id if state in _TRUST_CHALLENGE_OPEN_STATES else None
    if active_challenge_id is None:
        for row in challenges:
            if (
                isinstance(row, dict)
                and str(row.get("currentState") or "").strip().lower()
                in _TRUST_CHALLENGE_OPEN_STATES
            ):
                active_challenge_id = str(row.get("challengeId") or "").strip() or None
                break

    if state in {"challenge_requested", "challenge_accepted", "under_internal_review", "review_retained"}:
        review_state = "pending_review"
    elif state == "verdict_upheld":
        review_state = "approved"
    elif state in {"verdict_overturned", "draw_after_review"}:
        review_state = "rejected"
    else:
        review_state = str(challenge_review.get("reviewState") or "").strip() or "not_required"

    registry_basis = {
        **challenge_review,
        "challengeState": state,
        "activeChallengeId": active_challenge_id,
        "totalChallenges": len(challenges),
        "challenges": challenges,
        "timeline": timeline,
        "reviewState": review_state,
        "reviewRequired": bool(active_challenge_id or review_state == "pending_review"),
        "reviewDecisions": review_decisions,
        "challengeReasons": challenge_reasons,
    }
    registry_basis.pop("registryHash", None)
    registry_hash = _sha256_hex(registry_basis)
    return {**registry_basis, "registryHash": registry_hash}


def _update_public_verify_challenge_review(
    *,
    public_verify: dict[str, Any],
    challenge_review: dict[str, Any],
) -> dict[str, Any]:
    verify_payload = (
        dict(public_verify.get("verifyPayload"))
        if isinstance(public_verify.get("verifyPayload"), dict)
        else {}
    )
    verify_payload["challengeReview"] = {
        "version": challenge_review.get("version"),
        "registryHash": challenge_review.get("registryHash"),
        "reviewState": challenge_review.get("reviewState"),
        "reviewRequired": bool(challenge_review.get("reviewRequired")),
        "challengeState": challenge_review.get("challengeState"),
        "activeChallengeId": challenge_review.get("activeChallengeId"),
        "totalChallenges": int(challenge_review.get("totalChallenges") or 0),
        "alertSummary": (
            dict(challenge_review.get("alertSummary"))
            if isinstance(challenge_review.get("alertSummary"), dict)
            else {}
        ),
        "challengeReasons": (
            list(challenge_review.get("challengeReasons"))
            if isinstance(challenge_review.get("challengeReasons"), list)
            else []
        ),
    }
    return {**public_verify, "verifyPayload": verify_payload}


def _refresh_hash_surfaces(
    *,
    row: JudgeTrustRegistrySnapshotModel,
    challenge_review: dict[str, Any],
) -> None:
    component_hashes = dict(row.component_hashes) if isinstance(row.component_hashes, dict) else {}
    challenge_hash = str(challenge_review.get("registryHash") or "").strip()
    if challenge_hash:
        component_hashes["challengeReviewHash"] = challenge_hash
    audit_anchor = dict(row.audit_anchor) if isinstance(row.audit_anchor, dict) else {}
    anchor_component_hashes = (
        dict(audit_anchor.get("componentHashes"))
        if isinstance(audit_anchor.get("componentHashes"), dict)
        else {}
    )
    anchor_component_hashes.update(
        {key: value for key, value in component_hashes.items() if key != "auditAnchorHash"}
    )
    audit_anchor["componentHashes"] = anchor_component_hashes
    anchor_basis = {
        "version": audit_anchor.get("version") or "trust-phaseA-audit-anchor-v1",
        "caseId": int(row.case_id),
        "dispatchType": normalize_trust_dispatch_type(row.dispatch_type),
        "traceId": str(row.trace_id or "").strip(),
        "componentHashes": anchor_component_hashes,
    }
    audit_anchor["anchorHash"] = _sha256_hex(anchor_basis)
    component_hashes["auditAnchorHash"] = audit_anchor["anchorHash"]
    row.component_hashes = component_hashes
    row.audit_anchor = audit_anchor
    row.public_verify = _update_public_verify_challenge_review(
        public_verify=dict(row.public_verify) if isinstance(row.public_verify, dict) else {},
        challenge_review=challenge_review,
    )


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
                challenge_review = _append_challenge_timeline_event(
                    challenge_review=challenge_review,
                    event=event,
                )
                row.challenge_review = challenge_review
                _refresh_hash_surfaces(row=row, challenge_review=challenge_review)
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
