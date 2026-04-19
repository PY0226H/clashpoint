from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

REGISTRY_FAIRNESS_ALERT_TYPE_BLOCKED = "registry_fairness_gate_blocked"
REGISTRY_FAIRNESS_ALERT_TYPE_OVERRIDE = "registry_fairness_gate_override"
REGISTRY_DEPENDENCY_ALERT_TYPE_BLOCKED = "registry_dependency_health_blocked"
OPS_REGISTRY_ALERT_TYPES = {
    REGISTRY_FAIRNESS_ALERT_TYPE_BLOCKED,
    REGISTRY_FAIRNESS_ALERT_TYPE_OVERRIDE,
    REGISTRY_DEPENDENCY_ALERT_TYPE_BLOCKED,
}


def _normalize_aware_datetime(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _normalize_query_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _extract_raw_field(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload.get(key)
    return None


def _extract_optional_bool(payload: dict[str, Any], *keys: str) -> bool | None:
    value = _extract_raw_field(payload, *keys)
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


def _extract_optional_datetime(payload: dict[str, Any], *keys: str) -> datetime | None:
    value = _extract_raw_field(payload, *keys)
    if value is None:
        return None
    if isinstance(value, datetime):
        return _normalize_query_datetime(value)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return _normalize_query_datetime(parsed)


def _normalize_ops_alert_status(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def _normalize_ops_alert_delivery_status(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def _normalize_ops_alert_fields_mode(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return "full"
    return normalized


def _normalize_registry_audit_action(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def _build_alert_outbox_index(events: list[Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for event in events:
        alert_id = str(getattr(event, "alert_id", "") or "").strip()
        if not alert_id:
            continue
        delivery_status = (
            str(getattr(event, "delivery_status", "") or "").strip().lower() or "unknown"
        )
        updated_at = _normalize_aware_datetime(
            getattr(event, "updated_at", None)
        ) or _normalize_aware_datetime(getattr(event, "created_at", None)) or datetime.now(timezone.utc)
        created_at = _normalize_aware_datetime(getattr(event, "created_at", None)) or updated_at
        row = index.setdefault(
            alert_id,
            {
                "alertId": alert_id,
                "totalEvents": 0,
                "deliveryCounts": {
                    "pending": 0,
                    "sent": 0,
                    "failed": 0,
                    "unknown": 0,
                },
                "latestEventId": None,
                "latestDeliveryStatus": None,
                "latestErrorMessage": None,
                "latestUpdatedAt": None,
                "_latestUpdatedAt": None,
                "_latestCreatedAt": None,
            },
        )
        row["totalEvents"] += 1
        if delivery_status in row["deliveryCounts"]:
            row["deliveryCounts"][delivery_status] += 1
        else:
            row["deliveryCounts"]["unknown"] += 1

        latest_updated_at = row.get("_latestUpdatedAt")
        latest_created_at = row.get("_latestCreatedAt")
        should_replace_latest = (
            not isinstance(latest_updated_at, datetime)
            or updated_at > latest_updated_at
            or (
                updated_at == latest_updated_at
                and (
                    not isinstance(latest_created_at, datetime)
                    or created_at >= latest_created_at
                )
            )
        )
        if should_replace_latest:
            row["_latestUpdatedAt"] = updated_at
            row["_latestCreatedAt"] = created_at
            row["latestEventId"] = str(getattr(event, "event_id", "") or "").strip() or None
            row["latestDeliveryStatus"] = delivery_status
            row["latestErrorMessage"] = (
                str(getattr(event, "error_message", "") or "").strip() or None
            )
            row["latestUpdatedAt"] = updated_at.isoformat()

    for row in index.values():
        row.pop("_latestUpdatedAt", None)
        row.pop("_latestCreatedAt", None)
    return index


def _build_registry_alert_ops_trend(
    *,
    rows: list[dict[str, Any]],
    window_minutes: int,
    bucket_minutes: int,
) -> dict[str, Any]:
    window = max(10, min(int(window_minutes), 43200))
    requested_bucket = max(5, min(int(bucket_minutes), 1440))
    max_buckets = 240
    effective_bucket = max(requested_bucket, math.ceil(window / max_buckets))

    now = datetime.now(timezone.utc)
    window_from = now - timedelta(minutes=window)
    bucket_count = max(1, math.ceil(window / effective_bucket))
    bucket_span_seconds = max(60, effective_bucket * 60)

    timeline: list[dict[str, Any]] = []
    for idx in range(bucket_count):
        bucket_start = window_from + timedelta(minutes=idx * effective_bucket)
        bucket_end = min(now, bucket_start + timedelta(minutes=effective_bucket))
        timeline.append(
            {
                "bucketStart": bucket_start.isoformat(),
                "bucketEnd": bucket_end.isoformat(),
                "count": 0,
                "byType": {},
                "byStatus": {},
                "byDeliveryStatus": {},
                "_bucketStart": bucket_start,
                "_bucketEnd": bucket_end,
            }
        )

    type_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    delivery_counts: dict[str, int] = {
        "pending": 0,
        "sent": 0,
        "failed": 0,
        "none": 0,
        "unknown": 0,
    }
    matched_rows = 0
    for row in rows:
        updated_at = row.get("_updatedAt")
        if not isinstance(updated_at, datetime):
            updated_at = _normalize_aware_datetime(row.get("updatedAt"))
        if not isinstance(updated_at, datetime):
            continue
        if updated_at < window_from or updated_at > now:
            continue

        matched_rows += 1
        row_type = str(row.get("type") or "").strip() or "unknown"
        row_status = str(row.get("status") or "").strip().lower() or "unknown"
        row_delivery_status = str(row.get("_deliveryStatus") or "").strip().lower()
        if not row_delivery_status:
            row_delivery_status = "none"
        elif row_delivery_status not in {"pending", "sent", "failed"}:
            row_delivery_status = "unknown"

        type_counts[row_type] = type_counts.get(row_type, 0) + 1
        status_counts[row_status] = status_counts.get(row_status, 0) + 1
        delivery_counts[row_delivery_status] = delivery_counts.get(row_delivery_status, 0) + 1

        bucket_index = int((updated_at - window_from).total_seconds() // bucket_span_seconds)
        if bucket_index < 0:
            continue
        if bucket_index >= len(timeline):
            bucket_index = len(timeline) - 1
        bucket = timeline[bucket_index]
        bucket["count"] += 1
        bucket_type = bucket["byType"]
        bucket_status = bucket["byStatus"]
        bucket_delivery = bucket["byDeliveryStatus"]
        bucket_type[row_type] = bucket_type.get(row_type, 0) + 1
        bucket_status[row_status] = bucket_status.get(row_status, 0) + 1
        bucket_delivery[row_delivery_status] = bucket_delivery.get(row_delivery_status, 0) + 1

    timeline_rows: list[dict[str, Any]] = []
    for bucket in timeline:
        if int(bucket.get("count") or 0) <= 0:
            continue
        bucket.pop("_bucketStart", None)
        bucket.pop("_bucketEnd", None)
        bucket["byType"] = dict(sorted(bucket["byType"].items(), key=lambda kv: kv[0]))
        bucket["byStatus"] = dict(sorted(bucket["byStatus"].items(), key=lambda kv: kv[0]))
        bucket["byDeliveryStatus"] = dict(
            sorted(bucket["byDeliveryStatus"].items(), key=lambda kv: kv[0])
        )
        timeline_rows.append(bucket)

    return {
        "windowMinutes": window,
        "bucketMinutes": effective_bucket,
        "requestedBucketMinutes": requested_bucket,
        "window": {
            "from": window_from.isoformat(),
            "to": now.isoformat(),
        },
        "count": matched_rows,
        "typeCounts": dict(sorted(type_counts.items(), key=lambda kv: kv[0])),
        "statusCounts": dict(sorted(status_counts.items(), key=lambda kv: kv[0])),
        "deliveryStatusCounts": delivery_counts,
        "timeline": timeline_rows,
    }


def _serialize_registry_alert_ops_item(
    row: dict[str, Any],
    *,
    fields_mode: str,
) -> dict[str, Any]:
    if fields_mode == "full":
        payload = dict(row)
        payload.pop("_updatedAt", None)
        payload.pop("_createdAt", None)
        payload.pop("_deliveryStatus", None)
        return payload

    outbox_payload = dict(row.get("outbox")) if isinstance(row.get("outbox"), dict) else {}
    return {
        "alertId": row.get("alertId"),
        "caseId": row.get("caseId"),
        "scopeId": row.get("scopeId"),
        "traceId": row.get("traceId"),
        "type": row.get("type"),
        "status": row.get("status"),
        "severity": row.get("severity"),
        "title": row.get("title"),
        "registryType": row.get("registryType"),
        "policyVersion": row.get("policyVersion"),
        "action": row.get("action"),
        "gateCode": row.get("gateCode"),
        "gateMessage": row.get("gateMessage"),
        "gateSource": row.get("gateSource"),
        "overrideApplied": row.get("overrideApplied"),
        "gateActor": row.get("gateActor"),
        "gateReason": row.get("gateReason"),
        "gateBenchmarkPassed": row.get("gateBenchmarkPassed"),
        "gateShadowApplied": row.get("gateShadowApplied"),
        "gateShadowPassed": row.get("gateShadowPassed"),
        "gateLatestRunId": row.get("gateLatestRunId"),
        "gateLatestRunStatus": row.get("gateLatestRunStatus"),
        "gateLatestRunThresholdDecision": row.get("gateLatestRunThresholdDecision"),
        "gateLatestRunEnvironmentMode": row.get("gateLatestRunEnvironmentMode"),
        "gateLatestRunNeedsRemediation": row.get("gateLatestRunNeedsRemediation"),
        "gateLatestShadowRunId": row.get("gateLatestShadowRunId"),
        "gateLatestShadowRunStatus": row.get("gateLatestShadowRunStatus"),
        "gateLatestShadowRunThresholdDecision": row.get("gateLatestShadowRunThresholdDecision"),
        "gateLatestShadowRunEnvironmentMode": row.get("gateLatestShadowRunEnvironmentMode"),
        "gateLatestShadowRunNeedsRemediation": row.get("gateLatestShadowRunNeedsRemediation"),
        "dependencyCode": row.get("dependencyCode"),
        "createdAt": row.get("createdAt"),
        "updatedAt": row.get("updatedAt"),
        "outbox": {
            "totalEvents": int(outbox_payload.get("totalEvents", 0) or 0),
            "latestEventId": outbox_payload.get("latestEventId"),
            "latestDeliveryStatus": outbox_payload.get("latestDeliveryStatus"),
            "latestErrorMessage": outbox_payload.get("latestErrorMessage"),
            "latestUpdatedAt": outbox_payload.get("latestUpdatedAt"),
        },
    }


def _build_registry_alert_link_index_for_audits(
    *,
    alerts: list[Any],
    outbox_events: list[Any],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    outbox_index = _build_alert_outbox_index(outbox_events)
    rows_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for alert in alerts:
        row_type = str(getattr(alert, "alert_type", "") or "").strip()
        if row_type not in OPS_REGISTRY_ALERT_TYPES:
            continue
        details = (
            dict(getattr(alert, "details"))
            if isinstance(getattr(alert, "details", None), dict)
            else {}
        )
        row_registry_type = str(details.get("registryType") or "").strip().lower() or None
        row_policy_version = str(details.get("version") or "").strip() or None
        if row_registry_type is None or row_policy_version is None:
            continue

        gate_payload = details.get("gate") if isinstance(details.get("gate"), dict) else {}
        dependency_payload = (
            details.get("dependency") if isinstance(details.get("dependency"), dict) else {}
        )
        row_outbox = outbox_index.get(str(getattr(alert, "alert_id", "") or "").strip())
        created_at = _normalize_aware_datetime(getattr(alert, "created_at", None)) or datetime.now(
            timezone.utc
        )
        updated_at = _normalize_aware_datetime(getattr(alert, "updated_at", None)) or created_at

        row = {
            "alertId": str(getattr(alert, "alert_id", "") or "").strip() or None,
            "caseId": int(getattr(alert, "job_id", 0) or 0),
            "scopeId": int(getattr(alert, "scope_id", 0) or 0),
            "traceId": str(getattr(alert, "trace_id", "") or "").strip() or None,
            "type": row_type,
            "status": str(getattr(alert, "status", "") or "").strip().lower() or "unknown",
            "severity": str(getattr(alert, "severity", "") or "").strip() or None,
            "title": str(getattr(alert, "title", "") or "").strip() or None,
            "message": str(getattr(alert, "message", "") or "").strip() or None,
            "registryType": row_registry_type,
            "policyVersion": row_policy_version,
            "gateCode": str(gate_payload.get("code") or "").strip() or None,
            "overrideApplied": _extract_optional_bool(
                {"overrideApplied": details.get("overrideApplied")},
                "overrideApplied",
            ),
            "gateActor": str(details.get("actor") or "").strip() or None,
            "gateReason": str(details.get("reason") or "").strip() or None,
            "dependencyCode": str(dependency_payload.get("code") or "").strip() or None,
            "createdAt": created_at.isoformat(),
            "updatedAt": updated_at.isoformat(),
            "outbox": (
                dict(row_outbox)
                if isinstance(row_outbox, dict)
                else {
                    "alertId": str(getattr(alert, "alert_id", "") or "").strip() or None,
                    "totalEvents": 0,
                    "deliveryCounts": {
                        "pending": 0,
                        "sent": 0,
                        "failed": 0,
                        "unknown": 0,
                    },
                    "latestEventId": None,
                    "latestDeliveryStatus": None,
                    "latestErrorMessage": None,
                    "latestUpdatedAt": None,
                }
            ),
            "_updatedAt": updated_at,
        }
        rows_by_key.setdefault((row_registry_type, row_policy_version), []).append(row)

    for key, rows in rows_by_key.items():
        rows.sort(
            key=lambda row: (
                row.get("_updatedAt"),
                str(row.get("alertId") or ""),
            ),
            reverse=True,
        )
        cleaned_rows: list[dict[str, Any]] = []
        for row in rows:
            row_copy = dict(row)
            row_copy.pop("_updatedAt", None)
            cleaned_rows.append(row_copy)
        rows_by_key[key] = cleaned_rows
    return rows_by_key


def build_registry_audit_ops_view(
    *,
    registry_type: str,
    audit_items: list[dict[str, Any]],
    alerts: list[Any],
    outbox_events: list[Any],
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
    normalized_registry_type = str(registry_type or "").strip().lower()
    normalized_action = _normalize_registry_audit_action(action)
    normalized_version = str(version or "").strip() or None
    normalized_actor = str(actor or "").strip() or None
    normalized_gate_code = str(gate_code or "").strip() or None
    page_offset = max(0, int(offset))
    page_limit = max(1, min(int(limit), 500))
    resolved_link_limit = max(1, min(int(link_limit), 20))

    alert_link_index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    if include_gate_view:
        alert_link_index = _build_registry_alert_link_index_for_audits(
            alerts=alerts,
            outbox_events=outbox_events,
        )

    rows: list[dict[str, Any]] = []
    counts_by_action: dict[str, int] = {}
    counts_by_version: dict[str, int] = {"unknown": 0}
    counts_by_actor: dict[str, int] = {}
    counts_by_gate_code: dict[str, int] = {"unknown": 0}
    counts_by_override_applied: dict[str, int] = {
        "true": 0,
        "false": 0,
        "unknown": 0,
    }
    with_gate_review_count = 0
    with_linked_alerts_count = 0
    linked_outbox_failed_count = 0

    for item in audit_items:
        row_registry_type = str(item.get("registryType") or "").strip().lower()
        if normalized_registry_type and row_registry_type != normalized_registry_type:
            continue
        row_action = str(item.get("action") or "").strip().lower() or "unknown"
        if normalized_action is not None and row_action != normalized_action:
            continue
        row_version = str(item.get("version") or "").strip() or None
        if normalized_version is not None and row_version != normalized_version:
            continue
        row_actor = str(item.get("actor") or "").strip() or None
        if normalized_actor is not None and row_actor != normalized_actor:
            continue
        row_reason = str(item.get("reason") or "").strip() or None
        details = dict(item.get("details")) if isinstance(item.get("details"), dict) else {}

        fairness_gate = (
            details.get("fairnessGate")
            if isinstance(details.get("fairnessGate"), dict)
            else {}
        )
        dependency_health = (
            details.get("dependencyHealth")
            if isinstance(details.get("dependencyHealth"), dict)
            else {}
        )
        latest_run = (
            fairness_gate.get("latestRun")
            if isinstance(fairness_gate.get("latestRun"), dict)
            else {}
        )
        latest_shadow_run = (
            fairness_gate.get("latestShadowRun")
            if isinstance(fairness_gate.get("latestShadowRun"), dict)
            else {}
        )
        row_gate_code = str(fairness_gate.get("code") or "").strip() or None
        if normalized_gate_code is not None and row_gate_code != normalized_gate_code:
            continue
        row_override_applied = _extract_optional_bool(
            {"overrideApplied": fairness_gate.get("overrideApplied")},
            "overrideApplied",
        )
        if (
            override_applied is not None
            and row_override_applied is not None
            and row_override_applied != override_applied
        ):
            continue
        if override_applied is not None and row_override_applied is None:
            continue

        row_created_at_text = str(item.get("createdAt") or "").strip() or None
        row_created_at = _extract_optional_datetime(
            {"createdAt": row_created_at_text},
            "createdAt",
        ) or datetime.now(timezone.utc)

        gate_review = {
            "hasFairnessGate": bool(fairness_gate),
            "hasDependencyHealth": bool(dependency_health),
            "gateCode": row_gate_code,
            "gateMessage": str(fairness_gate.get("message") or "").strip() or None,
            "gatePassed": _extract_optional_bool({"passed": fairness_gate.get("passed")}, "passed"),
            "gateSource": str(fairness_gate.get("source") or "").strip() or None,
            "overrideApplied": row_override_applied,
            "thresholdDecision": str(fairness_gate.get("thresholdDecision") or "").strip() or None,
            "needsRemediation": _extract_optional_bool(
                {"needsRemediation": fairness_gate.get("needsRemediation")},
                "needsRemediation",
            ),
            "benchmarkGatePassed": _extract_optional_bool(
                {"benchmarkGatePassed": fairness_gate.get("benchmarkGatePassed")},
                "benchmarkGatePassed",
            ),
            "shadowGateApplied": _extract_optional_bool(
                {"shadowGateApplied": fairness_gate.get("shadowGateApplied")},
                "shadowGateApplied",
            ),
            "shadowGatePassed": _extract_optional_bool(
                {"shadowGatePassed": fairness_gate.get("shadowGatePassed")},
                "shadowGatePassed",
            ),
            "dependencyOk": _extract_optional_bool(
                {"ok": dependency_health.get("ok")},
                "ok",
            ),
            "dependencyCode": str(dependency_health.get("code") or "").strip() or None,
            "latestRunId": str(latest_run.get("runId") or "").strip() or None,
            "latestRunStatus": str(latest_run.get("status") or "").strip() or None,
            "latestRunThresholdDecision": (
                str(latest_run.get("thresholdDecision") or "").strip() or None
            ),
            "latestRunEnvironmentMode": (
                str(latest_run.get("environmentMode") or "").strip() or None
            ),
            "latestRunNeedsRemediation": _extract_optional_bool(
                {"needsRemediation": latest_run.get("needsRemediation")},
                "needsRemediation",
            ),
            "latestShadowRunId": str(latest_shadow_run.get("runId") or "").strip() or None,
            "latestShadowRunStatus": str(latest_shadow_run.get("status") or "").strip() or None,
            "latestShadowRunThresholdDecision": (
                str(latest_shadow_run.get("thresholdDecision") or "").strip() or None
            ),
            "latestShadowRunEnvironmentMode": (
                str(latest_shadow_run.get("environmentMode") or "").strip() or None
            ),
            "latestShadowRunNeedsRemediation": _extract_optional_bool(
                {"needsRemediation": latest_shadow_run.get("needsRemediation")},
                "needsRemediation",
            ),
            "actor": row_actor,
            "reason": row_reason,
        }

        linked_alerts: list[dict[str, Any]] = []
        linked_alert_summary: dict[str, Any] | None = None
        if include_gate_view and row_version is not None:
            candidates = alert_link_index.get((row_registry_type, row_version), [])
            linked_alerts = [dict(row) for row in candidates[:resolved_link_limit]]

            linked_by_type: dict[str, int] = {}
            linked_by_status: dict[str, int] = {}
            linked_by_delivery: dict[str, int] = {
                "pending": 0,
                "sent": 0,
                "failed": 0,
                "none": 0,
                "unknown": 0,
            }
            linked_open_count = 0
            linked_resolved_count = 0
            linked_failed_count = 0
            for row in linked_alerts:
                alert_type = str(row.get("type") or "").strip() or "unknown"
                alert_status = str(row.get("status") or "").strip().lower() or "unknown"
                latest_delivery = str(
                    (row.get("outbox") or {}).get("latestDeliveryStatus") or ""
                ).strip().lower()
                if latest_delivery in linked_by_delivery:
                    linked_by_delivery[latest_delivery] += 1
                elif latest_delivery:
                    linked_by_delivery["unknown"] += 1
                else:
                    linked_by_delivery["none"] += 1
                if alert_status in {"raised", "acked"}:
                    linked_open_count += 1
                if alert_status == "resolved":
                    linked_resolved_count += 1
                if latest_delivery == "failed":
                    linked_failed_count += 1
                linked_by_type[alert_type] = linked_by_type.get(alert_type, 0) + 1
                linked_by_status[alert_status] = linked_by_status.get(alert_status, 0) + 1

            linked_alert_summary = {
                "count": len(linked_alerts),
                "byType": dict(sorted(linked_by_type.items(), key=lambda kv: kv[0])),
                "byStatus": dict(sorted(linked_by_status.items(), key=lambda kv: kv[0])),
                "byDeliveryStatus": linked_by_delivery,
                "openCount": linked_open_count,
                "resolvedCount": linked_resolved_count,
                "outboxFailedCount": linked_failed_count,
            }

        has_gate_review = bool(gate_review.get("hasFairnessGate")) or bool(
            gate_review.get("hasDependencyHealth")
        )
        if has_gate_review:
            with_gate_review_count += 1
        if include_gate_view and linked_alerts:
            with_linked_alerts_count += 1
            linked_outbox_failed_count += int(
                (linked_alert_summary or {}).get("outboxFailedCount") or 0
            )

        counts_by_action[row_action] = counts_by_action.get(row_action, 0) + 1
        if row_version:
            counts_by_version[row_version] = counts_by_version.get(row_version, 0) + 1
        else:
            counts_by_version["unknown"] += 1
        if row_actor:
            counts_by_actor[row_actor] = counts_by_actor.get(row_actor, 0) + 1
        if row_gate_code:
            counts_by_gate_code[row_gate_code] = counts_by_gate_code.get(row_gate_code, 0) + 1
        else:
            counts_by_gate_code["unknown"] += 1
        if row_override_applied is True:
            counts_by_override_applied["true"] += 1
        elif row_override_applied is False:
            counts_by_override_applied["false"] += 1
        else:
            counts_by_override_applied["unknown"] += 1

        rows.append(
            {
                "registryType": row_registry_type,
                "action": row_action,
                "version": row_version,
                "actor": row_actor,
                "reason": row_reason,
                "details": details,
                "createdAt": row_created_at_text,
                "gateReview": gate_review,
                "linkedAlerts": linked_alerts if include_gate_view else None,
                "linkedAlertSummary": linked_alert_summary if include_gate_view else None,
                "_createdAt": row_created_at,
            }
        )

    rows.sort(
        key=lambda row: (
            row.get("_createdAt"),
            str(row.get("action") or ""),
            str(row.get("version") or ""),
        ),
        reverse=True,
    )
    total_count = len(rows)
    paged_rows = rows[page_offset : page_offset + page_limit]
    for row in paged_rows:
        row.pop("_createdAt", None)

    return {
        "registryType": normalized_registry_type,
        "count": total_count,
        "returned": len(paged_rows),
        "items": paged_rows,
        "aggregations": {
            "byAction": dict(sorted(counts_by_action.items(), key=lambda kv: kv[0])),
            "byVersion": dict(sorted(counts_by_version.items(), key=lambda kv: kv[0])),
            "byActor": dict(sorted(counts_by_actor.items(), key=lambda kv: kv[0])),
            "byGateCode": dict(sorted(counts_by_gate_code.items(), key=lambda kv: kv[0])),
            "byOverrideApplied": counts_by_override_applied,
            "withGateReviewCount": with_gate_review_count,
            "withLinkedAlertsCount": with_linked_alerts_count,
            "linkedOutboxFailedCount": linked_outbox_failed_count,
        },
        "filters": {
            "action": normalized_action,
            "version": normalized_version,
            "actor": normalized_actor,
            "gateCode": normalized_gate_code,
            "overrideApplied": override_applied,
            "includeGateView": bool(include_gate_view),
            "linkLimit": resolved_link_limit,
            "offset": page_offset,
            "limit": page_limit,
        },
        "limit": page_limit,
    }


def build_registry_alert_ops_view(
    *,
    alerts: list[Any],
    outbox_events: list[Any],
    alert_type: str | None,
    status: str | None,
    delivery_status: str | None,
    registry_type: str | None,
    policy_version: str | None,
    gate_code: str | None,
    gate_actor: str | None,
    override_applied: bool | None,
    fields_mode: str,
    include_trend: bool,
    trend_window_minutes: int,
    trend_bucket_minutes: int,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    normalized_alert_type = str(alert_type or "").strip() or None
    normalized_status = _normalize_ops_alert_status(status)
    normalized_delivery_status = _normalize_ops_alert_delivery_status(delivery_status)
    normalized_fields_mode = _normalize_ops_alert_fields_mode(fields_mode)
    normalized_registry_type = str(registry_type or "").strip().lower() or None
    normalized_policy_version = str(policy_version or "").strip() or None
    normalized_gate_code = str(gate_code or "").strip() or None
    normalized_gate_actor = str(gate_actor or "").strip() or None
    page_offset = max(0, int(offset))
    page_limit = max(1, min(int(limit), 500))
    outbox_index = _build_alert_outbox_index(outbox_events)

    rows: list[dict[str, Any]] = []
    counts_by_type: dict[str, int] = {}
    counts_by_status: dict[str, int] = {}
    counts_by_delivery: dict[str, int] = {
        "pending": 0,
        "sent": 0,
        "failed": 0,
        "none": 0,
        "unknown": 0,
    }
    counts_by_gate_code: dict[str, int] = {"unknown": 0}
    counts_by_gate_actor: dict[str, int] = {}
    counts_by_override_applied: dict[str, int] = {
        "true": 0,
        "false": 0,
        "unknown": 0,
    }
    counts_by_registry_type: dict[str, int] = {}
    counts_by_policy_version: dict[str, int] = {"unknown": 0}
    open_count = 0
    resolved_count = 0
    outbox_failed_count = 0
    override_applied_count = 0
    blocked_without_override_count = 0

    for alert in alerts:
        row_type = str(getattr(alert, "alert_type", "") or "").strip()
        if row_type not in OPS_REGISTRY_ALERT_TYPES:
            continue
        if normalized_alert_type is not None and row_type != normalized_alert_type:
            continue
        row_status = str(getattr(alert, "status", "") or "").strip().lower() or "unknown"
        if normalized_status == "open":
            if row_status not in {"raised", "acked"}:
                continue
        elif normalized_status is not None and row_status != normalized_status:
            continue
        details = (
            dict(getattr(alert, "details"))
            if isinstance(getattr(alert, "details", None), dict)
            else {}
        )
        gate_payload = details.get("gate") if isinstance(details.get("gate"), dict) else {}
        row_gate_code = str(gate_payload.get("code") or "").strip() or None
        row_gate_actor = str(details.get("actor") or "").strip() or None
        row_gate_reason = str(details.get("reason") or "").strip() or None
        row_override_applied = _extract_optional_bool(
            {"overrideApplied": details.get("overrideApplied")},
            "overrideApplied",
        )
        if normalized_gate_code is not None and row_gate_code != normalized_gate_code:
            continue
        if normalized_gate_actor is not None and row_gate_actor != normalized_gate_actor:
            continue
        if (
            override_applied is not None
            and row_override_applied is not None
            and row_override_applied != override_applied
        ):
            continue
        if override_applied is not None and row_override_applied is None:
            continue

        row_registry_type = str(details.get("registryType") or "").strip().lower() or None
        if normalized_registry_type is not None and row_registry_type != normalized_registry_type:
            continue
        row_policy_version = str(details.get("version") or "").strip() or None
        if normalized_policy_version is not None and row_policy_version != normalized_policy_version:
            continue

        row_outbox = outbox_index.get(str(getattr(alert, "alert_id", "") or "").strip())
        latest_delivery = (
            str(row_outbox.get("latestDeliveryStatus") or "").strip().lower()
            if isinstance(row_outbox, dict)
            else ""
        )
        if normalized_delivery_status is not None and latest_delivery != normalized_delivery_status:
            continue
        if row_status in {"raised", "acked"}:
            open_count += 1
        if row_status == "resolved":
            resolved_count += 1
        if latest_delivery == "failed":
            outbox_failed_count += 1

        counts_by_type[row_type] = counts_by_type.get(row_type, 0) + 1
        counts_by_status[row_status] = counts_by_status.get(row_status, 0) + 1
        if latest_delivery in counts_by_delivery:
            counts_by_delivery[latest_delivery] += 1
        elif latest_delivery:
            counts_by_delivery["unknown"] += 1
        else:
            counts_by_delivery["none"] += 1
        if row_gate_code:
            counts_by_gate_code[row_gate_code] = counts_by_gate_code.get(row_gate_code, 0) + 1
        else:
            counts_by_gate_code["unknown"] += 1
        if row_gate_actor:
            counts_by_gate_actor[row_gate_actor] = counts_by_gate_actor.get(row_gate_actor, 0) + 1
        if row_override_applied is True:
            counts_by_override_applied["true"] += 1
            override_applied_count += 1
        elif row_override_applied is False:
            counts_by_override_applied["false"] += 1
            if row_type == REGISTRY_FAIRNESS_ALERT_TYPE_BLOCKED:
                blocked_without_override_count += 1
        else:
            counts_by_override_applied["unknown"] += 1

        if row_registry_type:
            counts_by_registry_type[row_registry_type] = (
                counts_by_registry_type.get(row_registry_type, 0) + 1
            )
        if row_policy_version:
            counts_by_policy_version[row_policy_version] = (
                counts_by_policy_version.get(row_policy_version, 0) + 1
            )
        else:
            counts_by_policy_version["unknown"] += 1

        created_at = _normalize_aware_datetime(getattr(alert, "created_at", None)) or datetime.now(
            timezone.utc
        )
        updated_at = _normalize_aware_datetime(getattr(alert, "updated_at", None)) or created_at
        dependency_payload = (
            details.get("dependency") if isinstance(details.get("dependency"), dict) else {}
        )
        latest_run_payload = (
            gate_payload.get("latestRun") if isinstance(gate_payload.get("latestRun"), dict) else {}
        )
        latest_shadow_run_payload = (
            gate_payload.get("latestShadowRun")
            if isinstance(gate_payload.get("latestShadowRun"), dict)
            else {}
        )
        rows.append(
            {
                "alertId": str(getattr(alert, "alert_id", "") or "").strip() or None,
                "caseId": int(getattr(alert, "job_id", 0) or 0),
                "scopeId": int(getattr(alert, "scope_id", 0) or 0),
                "traceId": str(getattr(alert, "trace_id", "") or "").strip() or None,
                "type": row_type,
                "status": row_status,
                "severity": str(getattr(alert, "severity", "") or "").strip() or None,
                "title": str(getattr(alert, "title", "") or "").strip() or None,
                "message": str(getattr(alert, "message", "") or "").strip() or None,
                "registryType": row_registry_type,
                "policyVersion": row_policy_version,
                "action": str(details.get("action") or "").strip() or None,
                "gateCode": row_gate_code,
                "gateMessage": str(gate_payload.get("message") or "").strip() or None,
                "gateSource": str(gate_payload.get("source") or "").strip() or None,
                "overrideApplied": row_override_applied,
                "gateActor": row_gate_actor,
                "gateReason": row_gate_reason,
                "gateBenchmarkPassed": _extract_optional_bool(
                    {"benchmarkGatePassed": gate_payload.get("benchmarkGatePassed")},
                    "benchmarkGatePassed",
                ),
                "gateShadowApplied": _extract_optional_bool(
                    {"shadowGateApplied": gate_payload.get("shadowGateApplied")},
                    "shadowGateApplied",
                ),
                "gateShadowPassed": _extract_optional_bool(
                    {"shadowGatePassed": gate_payload.get("shadowGatePassed")},
                    "shadowGatePassed",
                ),
                "gateLatestRunId": str(latest_run_payload.get("runId") or "").strip() or None,
                "gateLatestRunStatus": str(latest_run_payload.get("status") or "").strip() or None,
                "gateLatestRunThresholdDecision": (
                    str(latest_run_payload.get("thresholdDecision") or "").strip() or None
                ),
                "gateLatestRunEnvironmentMode": (
                    str(latest_run_payload.get("environmentMode") or "").strip() or None
                ),
                "gateLatestRunNeedsRemediation": _extract_optional_bool(
                    {"needsRemediation": latest_run_payload.get("needsRemediation")},
                    "needsRemediation",
                ),
                "gateLatestShadowRunId": (
                    str(latest_shadow_run_payload.get("runId") or "").strip() or None
                ),
                "gateLatestShadowRunStatus": (
                    str(latest_shadow_run_payload.get("status") or "").strip() or None
                ),
                "gateLatestShadowRunThresholdDecision": (
                    str(latest_shadow_run_payload.get("thresholdDecision") or "").strip() or None
                ),
                "gateLatestShadowRunEnvironmentMode": (
                    str(latest_shadow_run_payload.get("environmentMode") or "").strip() or None
                ),
                "gateLatestShadowRunNeedsRemediation": _extract_optional_bool(
                    {"needsRemediation": latest_shadow_run_payload.get("needsRemediation")},
                    "needsRemediation",
                ),
                "dependencyCode": str(dependency_payload.get("code") or "").strip() or None,
                "createdAt": created_at.isoformat(),
                "updatedAt": updated_at.isoformat(),
                "outbox": (
                    dict(row_outbox)
                    if isinstance(row_outbox, dict)
                    else {
                        "alertId": str(getattr(alert, "alert_id", "") or "").strip() or None,
                        "totalEvents": 0,
                        "deliveryCounts": {
                            "pending": 0,
                            "sent": 0,
                            "failed": 0,
                            "unknown": 0,
                        },
                        "latestEventId": None,
                        "latestDeliveryStatus": None,
                        "latestErrorMessage": None,
                        "latestUpdatedAt": None,
                    }
                ),
                "_updatedAt": updated_at,
                "_createdAt": created_at,
                "_deliveryStatus": latest_delivery or "none",
            }
        )

    rows.sort(
        key=lambda row: (
            row.get("_updatedAt"),
            row.get("_createdAt"),
            str(row.get("alertId") or ""),
        ),
        reverse=True,
    )
    total_count = len(rows)
    paged_rows = rows[page_offset : page_offset + page_limit]
    serialized_rows = [
        _serialize_registry_alert_ops_item(
            row,
            fields_mode=normalized_fields_mode,
        )
        for row in paged_rows
    ]
    trend_payload = (
        _build_registry_alert_ops_trend(
            rows=rows,
            window_minutes=trend_window_minutes,
            bucket_minutes=trend_bucket_minutes,
        )
        if include_trend
        else None
    )

    return {
        "count": total_count,
        "returned": len(serialized_rows),
        "items": serialized_rows,
        "aggregations": {
            "byType": dict(sorted(counts_by_type.items(), key=lambda kv: kv[0])),
            "byStatus": dict(sorted(counts_by_status.items(), key=lambda kv: kv[0])),
            "byDeliveryStatus": counts_by_delivery,
            "byGateCode": dict(sorted(counts_by_gate_code.items(), key=lambda kv: kv[0])),
            "byGateActor": dict(sorted(counts_by_gate_actor.items(), key=lambda kv: kv[0])),
            "byOverrideApplied": counts_by_override_applied,
            "byRegistryType": dict(sorted(counts_by_registry_type.items(), key=lambda kv: kv[0])),
            "byPolicyVersion": dict(sorted(counts_by_policy_version.items(), key=lambda kv: kv[0])),
            "openCount": open_count,
            "resolvedCount": resolved_count,
            "outboxFailedCount": outbox_failed_count,
            "overrideAppliedCount": override_applied_count,
            "blockedWithoutOverrideCount": blocked_without_override_count,
        },
        "trend": trend_payload,
        "filters": {
            "alertType": normalized_alert_type,
            "status": normalized_status,
            "deliveryStatus": normalized_delivery_status,
            "registryType": normalized_registry_type,
            "policyVersion": normalized_policy_version,
            "gateCode": normalized_gate_code,
            "gateActor": normalized_gate_actor,
            "overrideApplied": override_applied,
            "fieldsMode": normalized_fields_mode,
            "includeTrend": bool(include_trend),
            "trendWindowMinutes": int(trend_window_minutes),
            "trendBucketMinutes": int(trend_bucket_minutes),
            "offset": page_offset,
            "limit": page_limit,
        },
    }


__all__ = [
    "build_registry_audit_ops_view",
    "build_registry_alert_ops_view",
]
