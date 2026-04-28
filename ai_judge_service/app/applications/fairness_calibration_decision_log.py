from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4

FAIRNESS_CALIBRATION_DECISION_LOG_VERSION = (
    "ai-judge-fairness-calibration-decision-log-v1"
)

FAIRNESS_CALIBRATION_DECISIONS: tuple[str, ...] = (
    "accept_for_review",
    "reject",
    "defer",
    "request_more_evidence",
)

FAIRNESS_CALIBRATION_REASON_CODES: tuple[str, ...] = (
    "calibration_real_samples_missing",
    "calibration_shadow_drift",
    "calibration_release_gate_blocked",
    "calibration_local_reference_only",
    "calibration_manual_reject",
)

FAIRNESS_CALIBRATION_DECISION_LOG_FORBIDDEN_KEYS: tuple[str, ...] = (
    "apiKey",
    "secret",
    "provider",
    "providerConfig",
    "rawPrompt",
    "rawTrace",
    "prompt",
    "trace",
    "traceId",
    "internalAuditPayload",
    "privateAudit",
    "auditPayload",
    "artifactRef",
    "artifactRefs",
    "objectKey",
    "bucket",
    "signedUrl",
    "endpoint",
    "url",
    "path",
)


class InMemoryFairnessCalibrationDecisionLogStore:
    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []

    async def append(self, entry: dict[str, Any]) -> dict[str, Any]:
        decision_id = str(entry.get("decisionId") or "").strip()
        if any(str(row.get("decisionId") or "") == decision_id for row in self._items):
            raise ValueError("duplicate_calibration_decision_id")
        self._items.append(deepcopy(entry))
        return deepcopy(entry)

    async def list(
        self,
        *,
        policy_version: str | None = None,
        source_recommendation_id: str | None = None,
        decision: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        normalized_policy_version = _token(policy_version)
        normalized_source_recommendation_id = _token(source_recommendation_id)
        normalized_decision = _lower_token(decision)
        capped_limit = max(1, min(int(limit), 500))
        items: list[dict[str, Any]] = []
        for row in reversed(self._items):
            if (
                normalized_policy_version is not None
                and row.get("policyVersion") != normalized_policy_version
            ):
                continue
            if (
                normalized_source_recommendation_id is not None
                and row.get("sourceRecommendationId")
                != normalized_source_recommendation_id
            ):
                continue
            if (
                normalized_decision is not None
                and row.get("decision") != normalized_decision
            ):
                continue
            items.append(deepcopy(row))
            if len(items) >= capped_limit:
                break
        return items


class WorkflowFactsFairnessCalibrationDecisionLogStore:
    def __init__(
        self,
        *,
        facts: Any,
        ensure_schema_ready: Callable[[], Awaitable[None]],
    ) -> None:
        self._facts = facts
        self._ensure_schema_ready = ensure_schema_ready

    async def append(self, entry: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_schema_ready()
        row = await self._facts.append_fairness_calibration_decision(
            version=str(entry.get("version") or ""),
            decision_id=str(entry.get("decisionId") or ""),
            source_recommendation_id=str(entry.get("sourceRecommendationId") or ""),
            policy_version=str(entry.get("policyVersion") or ""),
            decision=str(entry.get("decision") or ""),
            actor=dict(entry.get("actor") or {}),
            reason_code=str(entry.get("reasonCode") or ""),
            evidence_refs=list(entry.get("evidenceRefs") or []),
            visibility=dict(entry.get("visibility") or {}),
            release_gate_input=dict(entry.get("releaseGateInput") or {}),
            created_at=_parse_datetime(entry.get("createdAt")),
        )
        return fairness_calibration_decision_record_to_log_entry(row)

    async def list(
        self,
        *,
        policy_version: str | None = None,
        source_recommendation_id: str | None = None,
        decision: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        await self._ensure_schema_ready()
        rows = await self._facts.list_fairness_calibration_decisions(
            policy_version=policy_version,
            source_recommendation_id=source_recommendation_id,
            decision=decision,
            limit=limit,
        )
        return [fairness_calibration_decision_record_to_log_entry(row) for row in rows]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _token(value: Any) -> str | None:
    token = str(value or "").strip()
    return token or None


def _lower_token(value: Any) -> str | None:
    token = _token(value)
    return token.lower() if token is not None else None


def _payload_token(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        token = _token(payload.get(key))
        if token is not None:
            return token
    return None


def _payload_bool(payload: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    return False


def _parse_datetime(value: Any) -> datetime | None:
    token = _token(value)
    if token is None:
        return None
    try:
        return datetime.fromisoformat(token.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError:
        return None


def fairness_calibration_decision_record_to_log_entry(record: Any) -> dict[str, Any]:
    return {
        "version": _token(getattr(record, "version", None))
        or FAIRNESS_CALIBRATION_DECISION_LOG_VERSION,
        "decisionId": _token(getattr(record, "decision_id", None)),
        "sourceRecommendationId": _token(
            getattr(record, "source_recommendation_id", None)
        ),
        "policyVersion": _token(getattr(record, "policy_version", None)),
        "decision": _lower_token(getattr(record, "decision", None)),
        "actor": dict(getattr(record, "actor", None) or {}),
        "reasonCode": _token(getattr(record, "reason_code", None)),
        "evidenceRefs": [
            dict(item)
            for item in list(getattr(record, "evidence_refs", None) or [])
            if isinstance(item, dict)
        ],
        "createdAt": _normalize_datetime_to_iso(getattr(record, "created_at", None)),
        "visibility": dict(getattr(record, "visibility", None) or {}),
        "releaseGateInput": dict(getattr(record, "release_gate_input", None) or {}),
    }


def _normalize_datetime_to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        normalized = (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )
    else:
        normalized = _utcnow()
    return normalized.isoformat()


def _ensure_no_forbidden_keys(value: Any, *, path: str = "payload") -> None:
    forbidden = {
        str(key).replace("_", "").replace("-", "").lower()
        for key in FAIRNESS_CALIBRATION_DECISION_LOG_FORBIDDEN_KEYS
    }
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).replace("_", "").replace("-", "").lower()
            if normalized_key in forbidden:
                raise ValueError(f"calibration_decision_forbidden_key:{path}.{key}")
            _ensure_no_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _ensure_no_forbidden_keys(child, path=f"{path}[{index}]")


def _normalize_actor(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        _ensure_no_forbidden_keys(value, path="actor")
        actor_id = _payload_token(value, "id", "actorId", "userId", "email")
        actor_type = _lower_token(value.get("type") or value.get("role")) or "ops"
    else:
        actor_id = _token(value)
        actor_type = "ops"
    if actor_id is None:
        raise ValueError("missing_calibration_decision_actor")
    return {
        "id": actor_id,
        "type": actor_type,
    }


def _normalize_evidence_ref(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        token = _token(value)
        if token is None:
            raise ValueError("invalid_calibration_decision_evidence_ref")
        return {"kind": "manual", "ref": token}
    if not isinstance(value, dict):
        raise ValueError("invalid_calibration_decision_evidence_ref")

    _ensure_no_forbidden_keys(value, path="evidenceRefs")
    kind = _payload_token(value, "kind", "type") or "manual"
    ref = _payload_token(value, "ref", "id", "evidenceId", "manifestHash")
    digest = _payload_token(value, "hash", "sha256", "digest")
    if ref is None and digest is None:
        raise ValueError("invalid_calibration_decision_evidence_ref")

    item: dict[str, Any] = {"kind": kind}
    if ref is not None:
        item["ref"] = ref
    if digest is not None:
        item["hash"] = digest
    for source_key, target_key in (
        ("status", "status"),
        ("reasonCode", "reasonCode"),
        ("description", "description"),
    ):
        token = _token(value.get(source_key))
        if token is not None:
            item[target_key] = token
    count_value = value.get("count")
    if isinstance(count_value, int) and count_value >= 0:
        item["count"] = count_value
    return item


def _normalize_evidence_refs(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("invalid_calibration_decision_evidence_refs")
    return [_normalize_evidence_ref(item) for item in value[:20]]


def _build_visibility_contract() -> dict[str, Any]:
    return {
        "opsVisible": True,
        "releaseGateVisible": True,
        "publicVisible": False,
        "rawPromptVisible": False,
        "rawTraceVisible": False,
        "internalAuditPayloadVisible": False,
        "providerConfigVisible": False,
        "artifactRefsVisible": False,
        "officialVerdictSemanticsChanged": False,
        "autoPublishAllowed": False,
        "autoActivateAllowed": False,
    }


def _build_release_gate_input(
    *,
    policy_version: str,
    source_recommendation_id: str,
    decision: str,
    reason_code: str,
    local_reference_only: bool,
    evidence_ref_count: int,
) -> dict[str, Any]:
    eligible_for_production_ready = (
        decision == "accept_for_review" and not local_reference_only
    )
    return {
        "policyVersion": policy_version,
        "sourceRecommendationId": source_recommendation_id,
        "decision": decision,
        "reasonCode": reason_code,
        "eligibleForProductionReady": eligible_for_production_ready,
        "localReferenceOnly": bool(local_reference_only),
        "blocksProductionReady": not eligible_for_production_ready,
        "evidenceRefCount": max(0, int(evidence_ref_count)),
        "autoPublishAllowed": False,
        "autoActivateAllowed": False,
        "officialVerdictSemanticsChanged": False,
    }


def build_fairness_calibration_decision_log_entry(
    raw_payload: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(raw_payload, dict):
        raise ValueError("invalid_calibration_decision_payload")
    _ensure_no_forbidden_keys(raw_payload)

    decision_id = (
        _payload_token(raw_payload, "decisionId", "decision_id")
        or f"calibration-decision-{uuid4().hex}"
    )
    source_recommendation_id = _payload_token(
        raw_payload,
        "sourceRecommendationId",
        "source_recommendation_id",
        "actionId",
        "action_id",
    )
    policy_version = _payload_token(raw_payload, "policyVersion", "policy_version")
    decision = _lower_token(raw_payload.get("decision"))
    reason_code = _payload_token(raw_payload, "reasonCode", "reason_code")

    if source_recommendation_id is None:
        raise ValueError("missing_calibration_decision_source_recommendation_id")
    if policy_version is None:
        raise ValueError("missing_calibration_decision_policy_version")
    if decision not in FAIRNESS_CALIBRATION_DECISIONS:
        raise ValueError("invalid_calibration_decision")
    if reason_code not in FAIRNESS_CALIBRATION_REASON_CODES:
        raise ValueError("invalid_calibration_decision_reason_code")
    if _payload_bool(
        raw_payload,
        "autoPublish",
        "auto_publish",
        "autoActivate",
        "auto_activate",
        "autoApplyPolicy",
        "auto_apply_policy",
    ):
        raise ValueError("calibration_decision_auto_apply_forbidden")

    local_reference_only = (
        reason_code == "calibration_local_reference_only"
        or _lower_token(raw_payload.get("environmentMode")) == "local_reference"
        or _payload_bool(raw_payload, "localReferenceOnly", "local_reference_only")
    )
    if local_reference_only and _payload_bool(
        raw_payload,
        "productionReady",
        "production_ready",
        "eligibleForProductionReady",
        "eligible_for_production_ready",
    ):
        raise ValueError("calibration_local_reference_cannot_be_production_ready")

    evidence_refs = _normalize_evidence_refs(
        raw_payload.get("evidenceRefs", raw_payload.get("evidence_refs"))
    )
    actor = _normalize_actor(raw_payload.get("actor"))
    created_at = (now or _utcnow()).astimezone(timezone.utc).isoformat()
    release_gate_input = _build_release_gate_input(
        policy_version=policy_version,
        source_recommendation_id=source_recommendation_id,
        decision=decision,
        reason_code=reason_code,
        local_reference_only=local_reference_only,
        evidence_ref_count=len(evidence_refs),
    )
    return {
        "version": FAIRNESS_CALIBRATION_DECISION_LOG_VERSION,
        "decisionId": decision_id,
        "sourceRecommendationId": source_recommendation_id,
        "policyVersion": policy_version,
        "decision": decision,
        "actor": actor,
        "reasonCode": reason_code,
        "evidenceRefs": evidence_refs,
        "createdAt": created_at,
        "visibility": _build_visibility_contract(),
        "releaseGateInput": release_gate_input,
    }


def _build_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    decision_counts = {
        decision: sum(1 for row in items if row.get("decision") == decision)
        for decision in FAIRNESS_CALIBRATION_DECISIONS
    }
    local_reference_only_count = sum(
        1
        for row in items
        if bool((row.get("releaseGateInput") or {}).get("localReferenceOnly"))
    )
    production_ready_count = sum(
        1
        for row in items
        if bool((row.get("releaseGateInput") or {}).get("eligibleForProductionReady"))
    )
    return {
        "totalCount": len(items),
        "acceptedForReviewCount": decision_counts["accept_for_review"],
        "rejectedCount": decision_counts["reject"],
        "deferredCount": decision_counts["defer"],
        "requestMoreEvidenceCount": decision_counts["request_more_evidence"],
        "localReferenceOnlyCount": local_reference_only_count,
        "productionReadyDecisionCount": production_ready_count,
        "autoPublishAllowed": False,
        "autoActivateAllowed": False,
        "officialVerdictSemanticsChanged": False,
    }


def _build_release_gate_reference(items: list[dict[str, Any]]) -> dict[str, Any]:
    eligible_count = sum(
        1
        for row in items
        if bool((row.get("releaseGateInput") or {}).get("eligibleForProductionReady"))
    )
    blocking_count = sum(
        1
        for row in items
        if bool((row.get("releaseGateInput") or {}).get("blocksProductionReady"))
    )
    latest_decision_id = items[0].get("decisionId") if items else None
    latest_created_at = items[0].get("createdAt") if items else None
    return {
        "eligibleDecisionCount": eligible_count,
        "blockingDecisionCount": blocking_count,
        "latestDecisionId": latest_decision_id,
        "latestDecisionCreatedAt": latest_created_at,
        "localReferenceOnlyBlocksProductionReady": True,
        "autoPublishAllowed": False,
        "autoActivateAllowed": False,
        "officialVerdictSemanticsChanged": False,
    }


def build_fairness_calibration_decision_log_payload(
    *,
    items: list[dict[str, Any]],
    filters: dict[str, Any],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    normalized_items = [deepcopy(row) for row in items]
    payload = {
        "version": FAIRNESS_CALIBRATION_DECISION_LOG_VERSION,
        "generatedAt": (generated_at or _utcnow()).astimezone(timezone.utc).isoformat(),
        "summary": _build_summary(normalized_items),
        "items": normalized_items,
        "filters": {
            "policyVersion": _token(filters.get("policyVersion")),
            "sourceRecommendationId": _token(filters.get("sourceRecommendationId")),
            "decision": _lower_token(filters.get("decision")),
            "limit": max(1, min(int(filters.get("limit") or 50), 500)),
        },
        "releaseGateReference": _build_release_gate_reference(normalized_items),
        "visibilityContract": _build_visibility_contract(),
    }
    _ensure_no_forbidden_keys(payload)
    return payload


async def build_fairness_calibration_decision_create_payload(
    *,
    raw_payload: dict[str, Any],
    store: Any,
    now: datetime | None = None,
) -> dict[str, Any]:
    entry = build_fairness_calibration_decision_log_entry(
        raw_payload,
        now=now,
    )
    created = await store.append(entry)
    related_items = await store.list(
        policy_version=str(created.get("policyVersion") or ""),
        source_recommendation_id=str(created.get("sourceRecommendationId") or ""),
        limit=50,
    )
    payload = build_fairness_calibration_decision_log_payload(
        items=related_items,
        filters={
            "policyVersion": created.get("policyVersion"),
            "sourceRecommendationId": created.get("sourceRecommendationId"),
            "decision": None,
            "limit": 50,
        },
        generated_at=now,
    )
    return {
        "version": FAIRNESS_CALIBRATION_DECISION_LOG_VERSION,
        "generatedAt": payload["generatedAt"],
        "entry": created,
        "decisionLog": payload,
        "visibilityContract": _build_visibility_contract(),
    }


async def build_fairness_calibration_decision_list_payload(
    *,
    store: Any,
    policy_version: str | None,
    source_recommendation_id: str | None,
    decision: str | None,
    limit: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    normalized_decision = _lower_token(decision)
    if (
        normalized_decision is not None
        and normalized_decision not in FAIRNESS_CALIBRATION_DECISIONS
    ):
        raise ValueError("invalid_calibration_decision")
    items = await store.list(
        policy_version=policy_version,
        source_recommendation_id=source_recommendation_id,
        decision=normalized_decision,
        limit=limit,
    )
    return build_fairness_calibration_decision_log_payload(
        items=items,
        filters={
            "policyVersion": policy_version,
            "sourceRecommendationId": source_recommendation_id,
            "decision": normalized_decision,
            "limit": limit,
        },
        generated_at=now,
    )
